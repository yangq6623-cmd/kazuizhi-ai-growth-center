"""Acceptance checks for R7 live AI employee status and truthful execution telemetry."""

import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "05_V2.0.0_Source"))

from core import r7_engine  # noqa: E402
from core.storage import read_json, write_json  # noqa: E402


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def agent(registry, agent_id):
    return next(item for item in registry["items"] if item["id"] == agent_id)


def main():
    with tempfile.TemporaryDirectory() as tmp:
        old = os.environ.get("LOCALAPPDATA")
        os.environ["LOCALAPPDATA"] = tmp
        try:
            r7_engine.migrate_r6()

            market = r7_engine.create_job({
                "kind": "market_research",
                "title": "扫描涟水县本地维修公开需求",
            })
            check(market["state"] == "queued", "Non-financial task did not enter automatic queue")
            check(market["agent_id"] == "market", "Market task was not assigned to market agent")
            waiting = r7_engine.agent_registry()
            check(agent(waiting, "market")["status"] == "waiting", "Queued market agent not shown waiting")
            check(waiting["truth_policy"] == "job_telemetry_only_no_simulated_progress", "Truthful progress policy missing")

            r7_engine.run_due_jobs()
            completed_job = next(x for x in r7_engine.list_jobs()["items"] if x["id"] == market["id"])
            check(completed_job["state"] == "completed", "Autonomous market task did not complete")
            check(completed_job["progress"] == 100, "Completed task did not reach truthful 100 percent")
            check(completed_job["started_at"] and completed_job["heartbeat_at"] and completed_job["finished_at"], "Execution timestamps missing")
            check(completed_job["current_step"] == "执行完成", "Final execution step missing")
            completed = r7_engine.agent_registry()
            market_status = agent(completed, "market")
            check(market_status["status"] == "completed", "Completed market agent state not exposed")
            check(market_status["completed_today"] >= 1, "Today completion counter missing")
            check(completed["summary"]["completed_today"] >= 1, "Management completion summary missing")

            video = r7_engine.create_job({"kind": "manual_task", "title": "生成本地维修短视频脚本"})
            check(video["agent_id"] == "video", "Generic task title did not infer video agent")

            data = read_json(r7_engine.JOBS, {"schema": 3, "items": []})
            target = next(x for x in data["items"] if x["id"] == video["id"])
            stale_time = (datetime.now().astimezone() - timedelta(minutes=10)).isoformat()
            target.update(state="running", progress=55, current_step="生成内容草稿",
                          started_at=stale_time, heartbeat_at=stale_time, updated_at=stale_time)
            write_json(r7_engine.JOBS, data)
            stale = agent(r7_engine.agent_registry(), "video")
            check(stale["status"] == "error" and stale["stale"], "Stale heartbeat was not detected")
            check(stale["progress"] == 55, "Stale detection changed persisted progress")

            print("PASS: R7 live agent status, truthful milestones, completion summary and stale heartbeat detection")
        finally:
            if old is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = old


if __name__ == "__main__":
    main()
