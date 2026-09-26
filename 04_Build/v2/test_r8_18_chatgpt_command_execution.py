"""Acceptance test for R8-18 Command/Mission/task reconciliation."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))

from core import command_execution, daily_workforce, decision_center, mission_ledger, r7_engine
from core.storage import write_json
from integrations import kz_local_control


def main():
    with tempfile.TemporaryDirectory() as temp:
        previous = os.environ.get("LOCALAPPDATA")
        os.environ["LOCALAPPDATA"] = temp
        try:
            # A daily queue before a Command is visible but cannot self-authorize.
            daily_workforce.ensure_daily_workforce()
            initial = command_execution.reconcile()
            assert initial["jobs"]["command_id"] is None
            waiting = [x for x in r7_engine.list_jobs()["items"] if x.get("schedule_source") == "daily_workforce"]
            assert waiting and all(x.get("authorization_state") == "waiting_for_chatgpt" for x in waiting)

            kz_local_control.pair_webmcp({
                "challenge_id": "R818-CHALLENGE-001",
                "invocation_id": "R818-INVOKE-001",
                "client": "chatgpt-desktop-webmcp",
            })
            created = kz_local_control.execute_tool("create_mission", {
                "region": "涟水县",
                "service": "水电安装维修",
                "title": "R8-18 Command 执行链验收",
                "evidence": "仅验证本地 Command、Mission 与任务绑定，不发布任何外部内容",
                "goal": "真实验证控制链",
                "reason": "R8-18 验收",
                "objective": "验证 ChatGPT Command 到 Mission 和任务的真实绑定",
            }, request_id="R818-MISSION-001")["result"]
            command_id = created["receipt"]["command_id"]
            mission_id = created["receipt"]["mission_id"]

            reconciled = command_execution.reconcile()
            assert reconciled["jobs"]["command_id"] == command_id
            jobs = [x for x in r7_engine.list_jobs()["items"] if x.get("schedule_source") == "daily_workforce"]
            assert jobs and all(x.get("command_id") == command_id for x in jobs)
            assert all(x.get("mission_id") == mission_id for x in jobs)
            assert all(x.get("authorization_state") == "authorized" for x in jobs)

            # Diagnostics is a safe local-only task.  Its completion must write
            # a local execution receipt rather than falsely claiming a post or
            # a business outcome.
            diagnostic = r7_engine.create_job({"kind": "diagnostics"})
            with r7_engine.LOCK:
                data = r7_engine._store()
                target = next(x for x in data["items"] if x["id"] == diagnostic["id"])
                target.update(mission_id=mission_id, command_id=command_id, authorization_state="authorized")
                write_json(r7_engine.JOBS, data)
            r7_engine.run_due_jobs()
            completed = next(x for x in r7_engine.list_jobs()["items"] if x["id"] == diagnostic["id"])
            assert completed["state"] == "completed"
            assert completed["execution_receipt"]["proof_type"] == "local_execution_receipt"
            assert completed["execution_receipt"]["command_id"] == command_id

            ledger = mission_ledger.snapshot()
            active = ledger["active_mission"]
            assert active["mission_id"] == mission_id
            assert active["command"]["command_id"] == command_id
            assert active["command"]["transport"] == "kz_local_control"
            assert active["command_history"]
            execution = active["execution"]
            assert execution["task_count"] == len(jobs) + 1
            # CI runners use UTC while the desktop runs Asia/Shanghai time.
            # Additional already-due daily jobs may complete in CI; the
            # contract is that a local receipt exists, not that it is the only
            # receipt created during this test window.
            assert execution["local_execution_receipts"] >= 1
            assert "外网发布" in execution["truth"]

            # The Decision Center and owner workbench must read the same active
            # Mission identity as the ledger; a scheduled queue is not a reason
            # to report "no running Mission".
            decision = decision_center.refresh_decision_center()
            assert decision["active_mission"]["mission_id"] == mission_id

            status = command_execution.status()
            assert status["control_verified"] is True
            assert status["tasks"]["authorized"] >= len(jobs)
            assert "外部发布" in status["truth_rule"]
        finally:
            if previous is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = previous

    print("PASS: R8-18 binds verified ChatGPT Command to Mission and queued tasks without external publishing.")


if __name__ == "__main__":
    main()
