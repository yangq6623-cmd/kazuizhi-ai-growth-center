"""Offline release gate for R8-22 7x24 autonomous convergence.

The gate verifies the control-plane contract that the real owner test exposed:
newest authorized Command must become the current Mission automatically,
produce a Controller Plan, prioritize current work over legacy backlog, keep
optional social blockers out of the owner-critical path, and never fabricate
external publication/GEO truth.
"""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "05_V2.0.0_Source"
CORE = SRC / "core" / "r8_22_autonomous_convergence.py"
PATCH = SRC / "backend" / "r8_22_autonomy_convergence_patch.py"
UI = SRC / "web" / "r8_22_autonomy.js"
BUILD_INFO = SRC / "web" / "build_info.js"
TRUTH_PATCH = SRC / "core" / "r8_20_growth_truth_patch.py"
SCOPE = ROOT / "04_Build" / "v2" / "R8_22_7X24_AUTONOMY_SCOPE.md"


def main():
    old_local = os.environ.get("LOCALAPPDATA")
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["LOCALAPPDATA"] = tmp
        sys.path.insert(0, str(SRC))
        try:
            from core import autonomous_ops, command_execution, r7_engine
            from core.storage import now_iso, write_json
            from core import r8_22_autonomous_convergence as converge

            now = datetime.now().astimezone()
            command_time = (now - timedelta(minutes=2)).isoformat()
            fake_command = {
                "command_id": "CMD-R822-OWNER-001",
                "status": "accepted",
                "created_at": command_time,
                "transport": "kz_local_control",
                "objective": "未来2小时持续执行SEO/GEO增长、内容QC、公网页面发布、搜索提交和真实复测准备；社媒离线不得阻断核心任务。",
                "control_receipt_id": "RECEIPT-CMD-001",
                "source": "owner_workbench",
            }
            original_links = command_execution.command_links
            original_authorized = command_execution._authorized
            command_execution.command_links = lambda limit=200: [fake_command]
            command_execution._authorized = lambda link: bool(link and link.get("command_id"))

            # Import the real production convergence patch after the fake owner
            # Command is in place so the test exercises shipped monkeypatches.
            from backend import r8_22_autonomy_convergence_patch as _r8_22_patch  # noqa: F401

            # Seed the stale Mission that previously stayed visible after a new
            # owner Command arrived.
            stale = {
                "mission_id": "MISSION-OLD",
                "growth_id": "GROWTH-OLD",
                "created_at": (now - timedelta(days=1)).isoformat(),
                "updated_at": (now - timedelta(days=1)).isoformat(),
                "source": "r7_r8_shared_pipeline",
                "title": "旧 Mission",
                "goal": "旧目标",
                "priority": "P1",
                "state": "active",
                "stage": "自动发布",
                "user_state": "自动处理中",
                "children": {"video_ids": [], "publish_plan_ids": [], "receipt_ids": []},
                "verified_publications": 0,
            }
            write_json(autonomous_ops.OPS_FILE, {
                "schema": 1, "owner_goal": None, "active_mission_id": "MISSION-OLD",
                "missions": [stale], "events": [], "updated_at": now_iso(),
            })

            # Current task was created after the Command.
            new_job = {
                "id": "newjob", "kind": "manual_task", "title": "当前 SEO/GEO Mission 任务", "mode": "local",
                "agent": "SEO/GEO 增长员", "task_type": "seo", "risk": "non_financial",
                "execution": "autonomous", "state": "queued", "progress": 0, "completed_steps": 0,
                "total_steps": 1, "due_at": "", "created_at": (now - timedelta(minutes=1)).isoformat(),
                "updated_at": now_iso(), "approved_by": "autonomy_policy", "result": None,
                "error": None, "retry_count": 0,
            }
            # Daily workforce jobs may have been created before the owner Command
            # but are scheduled to run later; they must become P0 when due_at is
            # after the current Command.
            future_daily = {
                "id": "futurejob", "kind": "manual_task", "title": "今天稍后执行的SEO排班", "mode": "local",
                "agent": "SEO/GEO 增长员", "task_type": "seo", "risk": "non_financial",
                "execution": "autonomous", "state": "queued", "progress": 0, "completed_steps": 0,
                "total_steps": 1, "due_at": (now + timedelta(minutes=20)).isoformat(),
                "created_at": (now - timedelta(hours=5)).isoformat(), "updated_at": now_iso(),
                "approved_by": "autonomy_policy", "result": None, "error": None, "retry_count": 0,
                "schedule_source": "daily_workforce",
            }
            # Historical backlog remains historical.
            old_job = {
                "id": "oldjob", "kind": "manual_task", "title": "历史积压任务", "mode": "local",
                "agent": "内容运营员", "task_type": "content", "risk": "non_financial",
                "execution": "autonomous", "state": "queued", "progress": 0, "completed_steps": 0,
                "total_steps": 1, "due_at": "", "created_at": (now - timedelta(hours=4)).isoformat(),
                "updated_at": now_iso(), "approved_by": "autonomy_policy", "result": None,
                "error": None, "retry_count": 0,
            }
            # A task explicitly owned by an old Command must never be stolen by
            # the new Mission, even if its due time is in the future.
            old_bound = {
                "id": "oldbound", "kind": "manual_task", "title": "旧Mission后续任务", "mode": "local",
                "agent": "内容运营员", "task_type": "content", "risk": "non_financial",
                "execution": "autonomous", "state": "queued", "progress": 0, "completed_steps": 0,
                "total_steps": 1, "due_at": (now + timedelta(minutes=30)).isoformat(),
                "created_at": (now - timedelta(hours=3)).isoformat(), "updated_at": now_iso(),
                "approved_by": "autonomy_policy", "result": None, "error": None, "retry_count": 0,
                "command_id": "CMD-OLD", "mission_id": "MISSION-OLD-CMD", "priority_class": converge.CURRENT_PRIORITY,
            }
            write_json(r7_engine.JOBS, {"schema": 1, "items": [new_job, future_daily, old_job, old_bound]})

            mission = converge.ensure_command_mission()
            assert mission["command_id"] == fake_command["command_id"]
            assert mission["source"] == "owner_command"
            assert mission["priority"] == converge.CURRENT_PRIORITY
            ops = autonomous_ops._load()
            assert ops["active_mission_id"] == mission["mission_id"]
            assert ops["active_mission_id"] != "MISSION-OLD"
            assert ops["owner_goal"]["command_id"] == fake_command["command_id"]

            plan = converge.ensure_controller_plan(mission)
            assert plan["command_id"] == fake_command["command_id"]
            assert plan["mission_id"] == mission["mission_id"]
            lane_ids = {lane["id"] for lane in plan["lanes"]}
            assert {"health", "seo", "geo", "content", "publish", "measure"} <= lane_ids
            assert plan["execution_policy"]["optional_channel_offline"] == "defer_channel_and_continue_core_mission"
            assert "真实 Receipt/Evidence" in plan["execution_policy"]["truth"]

            binding = converge.bind_current_jobs()
            assert binding["command_id"] == fake_command["command_id"]
            rows = {x["id"]: x for x in r7_engine._store()["items"]}
            assert rows["newjob"]["priority_class"] == converge.CURRENT_PRIORITY
            assert rows["newjob"]["mission_id"] == mission["mission_id"]
            assert rows["newjob"]["authorization_state"] == "authorized"
            assert rows["futurejob"]["priority_class"] == converge.CURRENT_PRIORITY
            assert rows["futurejob"]["command_id"] == fake_command["command_id"]
            assert rows["oldjob"]["priority_class"] == converge.BACKLOG_PRIORITY
            assert not rows["oldjob"].get("command_id")
            assert rows["oldbound"]["priority_class"] == converge.BACKLOG_PRIORITY
            assert rows["oldbound"]["command_id"] == "CMD-OLD"

            due = converge.priority_due_job_ids()
            assert due[0] == "newjob", due
            assert len(due) <= 5, due

            receipt = converge.maybe_phase_receipt(force=True)
            assert receipt["command_id"] == fake_command["command_id"]
            assert receipt["mission_id"] == mission["mission_id"]
            assert "不把本地完成冒充外部发布" in receipt["truth_note"]
            assert "published" not in receipt or not receipt.get("published")

            state = converge.snapshot()
            assert state["command"]["command_id"] == fake_command["command_id"]
            assert state["mission"]["mission_id"] == mission["mission_id"]
            assert state["plan"]["plan_id"] == plan["plan_id"]
            assert state["progress"]["total"] >= 2
            assert "外部发布/搜索/GEO/经营结果" in state["truth_rule"]

            # Static integration gates: production import path, API/event UI and
            # R8-22 visible identity must all ship together.
            core_text = CORE.read_text(encoding="utf-8")
            patch_text = PATCH.read_text(encoding="utf-8")
            ui_text = UI.read_text(encoding="utf-8")
            truth_text = TRUTH_PATCH.read_text(encoding="utf-8")
            build_text = BUILD_INFO.read_text(encoding="utf-8")
            scope_text = SCOPE.read_text(encoding="utf-8")
            for marker in (
                "ensure_command_mission", "ensure_controller_plan", "P0_current_mission",
                "PHASE_RECEIPT_SECONDS", "defer_channel_and_continue_core_mission",
                "priority_due_job_ids", "event_stream",
            ):
                assert marker in core_text, marker
            for marker in (
                "/api/r8-22/autonomy", "/api/r8-22/autonomy/events", "/api/r8-22/autonomy/receipt",
                "command_execution.reconcile_jobs", "autonomous_ops.sync_from_runtime", "r7_engine.run_due_jobs",
                "deferred_channel_not_core_blocker", "current_job_ids", "MAX_CURRENT_JOBS_PER_TICK",
            ):
                assert marker in patch_text, marker
            for marker in (
                "R8-22 · 7×24 AUTONOMOUS CONVERGENCE", "当前 Mission", "Controller Plan",
                "实时工作动态", "老板介入 / 延后渠道", "历史兼容账本",
            ):
                assert marker in ui_text, marker
            for marker in (
                "7×24 小时持续运行", "事件驱动自治主线", "老板", "ChatGPT / Controller", "AI 员工",
                "现有能力全部保留", "真值红线", "24 小时无人值守", "7 天连续运行",
            ):
                assert marker in scope_text, marker
            assert "r8_22_autonomy_convergence_patch" in truth_text
            assert 'phase: "R8-22"' in build_text
            assert "7x24 Autonomous Convergence" in build_text

            command_execution.command_links = original_links
            command_execution._authorized = original_authorized
            print("PASS: R8-22 newest Command auto-takes Mission, auto-compiles Plan, owns future daily work, preserves old Command history, bounds P0 execution, emits truthful events/receipts, and defers optional channels without blocking the 7x24 core loop")
        finally:
            if sys.path and sys.path[0] == str(SRC):
                sys.path.pop(0)
            if old_local is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = old_local


if __name__ == "__main__":
    main()
