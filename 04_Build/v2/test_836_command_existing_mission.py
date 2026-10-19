"""Regression for owner Command -> existing Mission -> one SEO R7 Task.

Uses an isolated LOCALAPPDATA. Does not publish, submit search URLs, or
mutate any production ledger.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "05_V2.0.0_Source"


def main():
    before = os.environ.get("LOCALAPPDATA")
    with tempfile.TemporaryDirectory(prefix="kz-836-command-") as tmp:
        os.environ["LOCALAPPDATA"] = tmp
        sys.path.insert(0, str(SRC))
        try:
            from core.storage import now_iso, write_json
            from core import autonomous_ops, r7_engine
            from core import r8_22_autonomous_convergence as conv
            from integrations import chatgpt_control

            cmd = "CMD-20261019-073EED"
            old_id = "MISSION-20260924-DF7DB2"
            wrong_id = "MISSION-20261019-25F9E1"
            objective = (
                "继续现有 Mission MISSION-20260924-DF7DB2，执行一轮涟水县本地维修 SEO 增量验证，"
                "不创建重复 Mission。目标关键词优先选择“涟水县空调不制冷上门维修”。"
                "新 Asset ID、内容生成、QC、官网发布、搜索提交必须有真实回执。"
            )
            link = {
                "command_id": cmd,
                "status": "accepted",
                "created_at": now_iso(),
                "transport": "kz_local_control",
                "mission_id": wrong_id,  # existing #836 stale association
                "objective": objective,
                "control_receipt_id": None,
                "source": "owner_workbench",
            }
            old_mission = {
                "mission_id": old_id,
                "source": "r7_r8_shared_pipeline",
                "created_at": now_iso(),
                "goal": "涟水县水电维修第一轮增长",
                "region": "涟水县",
                "service": "水电维修",
                "state": "active",
                "children": {"video_ids": [], "publish_plan_ids": [], "receipt_ids": ["RECEIPT-OLD"]},
                "verified_publications": 1,
                "command_id": "CMD-OLD",
            }
            wrong_mission = {
                "mission_id": wrong_id,
                "source": "owner_command",
                "command_id": cmd,
                "command_objective": objective,
                "state": "active",
                "children": {"video_ids": [], "publish_plan_ids": [], "receipt_ids": []},
            }
            write_json(autonomous_ops.OPS_FILE, {
                "schema": 1,
                "missions": [wrong_mission, old_mission],
                "active_mission_id": wrong_id,
                "events": [],
                "owner_goal": None,
                "updated_at": now_iso(),
            })
            write_json(chatgpt_control.COMMANDS_FILE, [{
                "command_id": cmd,
                "kind": "owner_objective",
                "status": "accepted",
                "objective": objective,
                "mission_id": wrong_id,
            }])
            write_json(r7_engine.JOBS, {"schema": 1, "items": []})
            original = conv._latest_authorized_command
            conv._latest_authorized_command = lambda: dict(link)
            try:
                assert conv._referenced_existing_mission_id(link) == old_id
                mission = conv.ensure_command_mission()
                assert mission["mission_id"] == old_id
                assert mission["region"] == "涟水县"
                assert mission["children"]["receipt_ids"] == ["RECEIPT-OLD"]
                ops = autonomous_ops._load()
                assert ops["active_mission_id"] == old_id
                assert len(ops["missions"]) == 2
                assert next(x for x in ops["missions"] if x["mission_id"] == wrong_id)["state"] == "superseded"
                stored = chatgpt_control._load_list(chatgpt_control.COMMANDS_FILE)[0]
                assert stored["mission_id"] == old_id and stored["status"] == "accepted"
                assert not stored.get("receipt_id")

                plan = conv.ensure_controller_plan(mission)
                assert plan["mission_id"] == old_id and plan["command_id"] == cmd
                first = conv.ensure_owner_seo_incremental_task(mission, plan)
                assert first["id"] and not first["existing"]
                second = conv.ensure_owner_seo_incremental_task(mission, plan)
                assert first["id"] == second["id"] and second["existing"]
                rows = r7_engine._store()["items"]
                assert len(rows) == 1, rows
                assert rows[0]["command_id"] == cmd
                assert rows[0]["mission_id"] == old_id
                assert rows[0]["controller_plan_id"] == plan["plan_id"]
                assert rows[0]["task_type"] == "seo"
                assert rows[0]["risk"] == "non_financial"
                assert rows[0]["output_scope"] == "local_seo_draft_only"
                assert rows[0]["state"] == "queued"
                assert not rows[0].get("execution_receipt")
                assert "空调不制冷" in rows[0]["title"]

                # A different runtime may temporarily select the old active
                # campaign. Subsequent convergence must not spam audit events.
                data = autonomous_ops._load()
                data["active_mission_id"] = wrong_id
                write_json(autonomous_ops.OPS_FILE, data)
                conv.ensure_command_mission()
                count = sum(x.get("kind") == "mission_reactivated"
                            for x in autonomous_ops._load().get("events", []))
                data = autonomous_ops._load()
                data["active_mission_id"] = wrong_id
                write_json(autonomous_ops.OPS_FILE, data)
                conv.ensure_command_mission()
                assert sum(x.get("kind") == "mission_reactivated"
                           for x in autonomous_ops._load().get("events", [])) == count
                assert len(r7_engine._store()["items"]) == 1

                # Explicit missing IDs must not silently invent new Missions.
                missing = dict(link, objective=objective.replace(old_id, "MISSION-MISSING"))
                conv._latest_authorized_command = lambda: missing
                assert conv.ensure_command_mission() is None
                assert len(autonomous_ops._load()["missions"]) == 2
            finally:
                conv._latest_authorized_command = original

            print("PASS: existing Mission reused, Command linked, SEO R7 draft task exactly once; prior Receipt retained, no external publishing or duplicate reactivation")
        finally:
            if sys.path and sys.path[0] == str(SRC):
                sys.path.pop(0)
            if before is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = before


if __name__ == "__main__":
    main()
