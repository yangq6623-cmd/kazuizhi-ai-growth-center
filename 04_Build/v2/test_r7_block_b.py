"""Acceptance tests for R7 Block B: bridge, autonomous non-financial handoff and finance guardrail."""

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "05_V2.0.0_Source"))

from core import r7_engine  # noqa: E402
from integrations.bridge import (  # noqa: E402
    bridge_status, configure_bridge, list_bridge_commands, self_test, sync_once,
)
from integrations.manager import control_center, integration_status, system_diagnostics  # noqa: E402


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        old = os.environ.get("LOCALAPPDATA")
        os.environ["LOCALAPPDATA"] = tmp
        try:
            r7_engine.migrate_r6()
            status = bridge_status()
            check(status["status"] == "not_connected", "Unconfigured bridge was reported connected")
            check(status["operating_mode"] == "local_autonomous", "Offline autonomous mode missing")

            sync_parent = Path(tmp) / "SyncedCloudFolder"
            configured = configure_bridge({"root": str(sync_parent)})
            check(configured["status"] == "connected", "Bridge folder did not connect")
            bridge_root = Path(configured["bridge_root"])
            check((bridge_root / "inbox").is_dir() and (bridge_root / "outbox").is_dir(), "Bridge layout missing")

            first = sync_once()
            check(first["synced"], "Initial bridge sync failed")
            check((bridge_root / "outbox" / "latest_status.json").exists(), "Local report was not exported")
            report = json.loads((bridge_root / "outbox" / "latest_status.json").read_text(encoding="utf-8"))
            check(report["audit"]["integrity"] == "verified", "Bridge report lost audit integrity")
            check("truth_policy" in report, "Bridge report truth policy missing")

            command = {
                "id": "chatgpt-plan-001",
                "kind": "manual_task",
                "title": "收集并整理涟水县周边维修市场公开数据",
            }
            (bridge_root / "inbox" / "chatgpt-plan-001.json").write_text(
                json.dumps(command, ensure_ascii=False), encoding="utf-8"
            )
            second = sync_once()
            check(second["imported"] == 1, "Bridge command was not imported")
            jobs = r7_engine.list_jobs()["items"]
            matches = [x for x in jobs if x["title"] == command["title"]]
            check(len(matches) == 1, "Bridge command did not create exactly one job")
            job = matches[0]
            check(job["state"] == "queued", "Non-financial cloud command was not auto-approved")
            check(job["approval_policy"] == "auto_non_financial", "Autonomy policy missing")

            # Replaying the same command id must never duplicate the local job.
            (bridge_root / "inbox" / "chatgpt-plan-001.json").write_text(
                json.dumps(command, ensure_ascii=False), encoding="utf-8"
            )
            replay = sync_once()
            check(replay["imported"] == 0, "Duplicate bridge command was imported again")
            jobs = r7_engine.list_jobs()["items"]
            check(len([x for x in jobs if x["title"] == command["title"]]) == 1, "Duplicate job created")

            # Scheduler must execute the non-financial task without human clicks.
            receipt_path = bridge_root / "outbox" / "receipts" / "chatgpt-plan-001.json"
            check(receipt_path.exists(), "Command ACK receipt missing")
            accepted = json.loads(receipt_path.read_text(encoding="utf-8"))
            check(accepted["state"] == "queued", "Receipt did not expose auto-approved queue state")
            r7_engine.run_due_jobs()
            sync_once()
            completed = json.loads(receipt_path.read_text(encoding="utf-8"))
            check(completed["state"] == "completed" and completed["progress"] == 100, "Autonomous job receipt not refreshed")
            check(completed.get("result"), "Autonomous result missing from receipt")

            # Finance remains human-only even when the bridge asks for it.
            finance = {"id": "chatgpt-finance-001", "kind": "manual_task", "title": "给师傅结算并付款"}
            (bridge_root / "inbox" / "chatgpt-finance-001.json").write_text(
                json.dumps(finance, ensure_ascii=False), encoding="utf-8"
            )
            finance_sync = sync_once()
            check(finance_sync["imported"] == 1, "Finance command was not recorded")
            finance_job = next(x for x in r7_engine.list_jobs()["items"] if x["title"] == finance["title"])
            check(finance_job["state"] == "awaiting_approval", "Finance command bypassed human approval")
            check(finance_job["approval_policy"] == "finance_human_only", "Finance guardrail missing")
            check(r7_engine.run_due_jobs()["processed"] == 0, "Finance task executed automatically")

            # Unsupported executors remain rejected.
            bad = {"id": "chatgpt-plan-bad", "kind": "auto_publish", "title": "自动发布"}
            (bridge_root / "inbox" / "chatgpt-plan-bad.json").write_text(
                json.dumps(bad, ensure_ascii=False), encoding="utf-8"
            )
            rejected = sync_once()
            check(rejected["rejected"] == 1, "Unsafe remote command was not rejected")
            bad_receipt = json.loads((bridge_root / "outbox" / "receipts" / "chatgpt-plan-bad.json").read_text(encoding="utf-8"))
            check(bad_receipt["state"] == "rejected", "Unsafe command receipt missing rejection")

            one_click = self_test()
            check(one_click["passed"], "One-click bridge self-test did not pass")
            check(one_click["job_id"], "One-click bridge self-test did not create a job")
            check(all(item["passed"] for item in one_click["checks"]), "One-click bridge self-test has failed checks")
            self_receipt = one_click["receipt"]
            check(self_receipt["state"] == "queued", "Self-test did not use autonomous non-financial policy")
            check(self_receipt["job_id"] == one_click["job_id"], "Self-test receipt job mismatch")

            commands = list_bridge_commands()
            check(commands["count"] == 4, "Bridge command ledger count incorrect")
            integrations = integration_status()
            check(integrations["bridge"]["status"] == "connected", "Integration center did not expose bridge")
            center = control_center()
            check(center["bridge"]["status"] == "connected", "Command center did not expose bridge")
            check("本机扫描" in center["loop"] and "结果回执" in center["loop"], "Bidirectional command loop incomplete")
            diagnostics = system_diagnostics()
            check(any(x["id"] == "bridge" and x["status"] == "pass" for x in diagnostics["checks"]), "Diagnostics did not verify bridge")
            check(r7_engine.audit_history()["integrity"] == "verified", "Audit chain failed after bridge operations")

            print("PASS: R7 bridge autonomy, dedupe, finance guardrail, receipts and self-test")
        finally:
            if old is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = old


if __name__ == "__main__":
    main()
