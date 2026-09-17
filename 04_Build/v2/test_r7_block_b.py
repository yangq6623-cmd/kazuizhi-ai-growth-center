"""Acceptance tests for R7 Block B: command center, bridge and safe task handoff."""

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "05_V2.0.0_Source"))

from core import r7_engine  # noqa: E402
from core.storage import data_root  # noqa: E402
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
            # Without any cloud folder the runtime must remain truthful and autonomous.
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
                "title": "审核今日 SEO/GEO 草稿",
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
            check(job["state"] == "awaiting_approval", "Cloud command bypassed local approval")

            # Replaying the same command id must never duplicate the local job.
            (bridge_root / "inbox" / "chatgpt-plan-001.json").write_text(
                json.dumps(command, ensure_ascii=False), encoding="utf-8"
            )
            replay = sync_once()
            check(replay["imported"] == 0, "Duplicate bridge command was imported again")
            jobs = r7_engine.list_jobs()["items"]
            check(len([x for x in jobs if x["title"] == command["title"]]) == 1, "Duplicate job created")

            # The receipt must track the actual local lifecycle.
            receipt_path = bridge_root / "outbox" / "receipts" / "chatgpt-plan-001.json"
            check(receipt_path.exists(), "Command ACK receipt missing")
            accepted = json.loads(receipt_path.read_text(encoding="utf-8"))
            check(accepted["state"] == "awaiting_approval", "Receipt did not expose pending approval")
            r7_engine.command({"id": job["id"], "action": "approve"})
            r7_engine.command({"id": job["id"], "action": "start"})
            r7_engine.command({"id": job["id"], "action": "complete", "outcome": "草稿已核查"})
            sync_once()
            completed = json.loads(receipt_path.read_text(encoding="utf-8"))
            check(completed["state"] == "completed" and completed["progress"] == 100, "Completed job receipt not refreshed")
            check(completed["result"]["outcome"] == "草稿已核查", "Completion outcome missing from receipt")

            # A remote command can never introduce an unapproved executor such as finance or auto-publish.
            bad = {"id": "chatgpt-plan-bad", "kind": "auto_publish", "title": "自动发布"}
            (bridge_root / "inbox" / "chatgpt-plan-bad.json").write_text(
                json.dumps(bad, ensure_ascii=False), encoding="utf-8"
            )
            rejected = sync_once()
            check(rejected["rejected"] == 1, "Unsafe remote command was not rejected")
            bad_receipt = json.loads((bridge_root / "outbox" / "receipts" / "chatgpt-plan-bad.json").read_text(encoding="utf-8"))
            check(bad_receipt["state"] == "rejected", "Unsafe command receipt missing rejection")

            # One-click self-test must exercise the same bridge path and keep local approval intact.
            one_click = self_test()
            check(one_click["passed"], "One-click bridge self-test did not pass")
            check(one_click["job_id"], "One-click bridge self-test did not create a job")
            check(all(item["passed"] for item in one_click["checks"]), "One-click bridge self-test has failed checks")
            self_receipt = one_click["receipt"]
            check(self_receipt["state"] == "awaiting_approval", "Self-test bypassed local approval")
            check(self_receipt["job_id"] == one_click["job_id"], "Self-test receipt job mismatch")

            commands = list_bridge_commands()
            check(commands["count"] == 3, "Bridge command ledger count incorrect")
            integrations = integration_status()
            check(integrations["bridge"]["status"] == "connected", "Integration center did not expose bridge")
            center = control_center()
            check(center["bridge"]["status"] == "connected", "Command center did not expose bridge")
            check("本机扫描" in center["loop"] and "结果回执" in center["loop"], "Bidirectional command loop incomplete")
            diagnostics = system_diagnostics()
            check(any(x["id"] == "bridge" and x["status"] == "pass" for x in diagnostics["checks"]), "Diagnostics did not verify bridge")
            check(r7_engine.audit_history()["integrity"] == "verified", "Audit chain failed after bridge operations")

            print("PASS: R7 Block B bidirectional bridge, dedupe, approval, receipts and self-test")
        finally:
            if old is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = old


if __name__ == "__main__":
    main()
