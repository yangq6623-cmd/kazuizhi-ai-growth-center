"""Regression gate: SEO/GEO execution is permitted only by a ChatGPT daily plan."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    previous = os.environ.get("LOCALAPPDATA")
    with tempfile.TemporaryDirectory(prefix="kz-r818-control-") as temp:
        os.environ["LOCALAPPDATA"] = temp
        try:
            from integrations import chatgpt_control as control
            from core import chatgpt_execution_control as permits
            from core import seo_geo_autonomy as autonomy

            blocked = permits.execution_gate("MISSION-TEST")
            require(not blocked["allowed"], "unverified ChatGPT must not authorize SEO/GEO execution")
            require(blocked["code"] == "chatgpt_not_verified", "missing unverified control reason")

            control.record_verified_roundtrip(
                connector_id="test-chatgpt-control",
                proof_source="chatgpt_app",
                challenge_id="challenge-r818-control",
                command_id="CMD-VERIFY-R818",
                receipt_id="RECEIPT-VERIFY-R818",
                permissions=["read_missions", "start_content_production"],
            )
            command = control.create_owner_command({"objective": "按今日计划执行已批准的 SEO/GEO 工作"})
            control.acknowledge_command(command["command_id"], mission_id="MISSION-TEST")
            receipt = control.record_command_receipt(
                command["command_id"],
                {
                    "chatgpt_plan": {
                        "focus": "先完成涟水县水电维修的事实校验、页面质检与真实提交回执检查",
                        "actions": ["seo_plan", "seo_generate", "seo_qc", "seo_submit", "geo_baseline"],
                    }
                },
                mission_id="MISSION-TEST",
            )
            allowed = permits.execution_gate("MISSION-TEST")
            require(allowed["allowed"], "verified ChatGPT Command -> Receipt plan did not authorize execution")
            require(allowed["plan"]["receipt_id"] == receipt["receipt_id"], "execution permit lost its receipt link")
            require("seo_submit" in allowed["plan"]["actions"], "approved action list changed")

            # The same plan must constrain the wider workforce queue: an SEO/GEO
            # permit cannot silently schedule market, video, social or conversion
            # work that ChatGPT did not ask for.
            from core.daily_workforce import ensure_daily_workforce
            from core.r7_engine import list_jobs
            ensure_daily_workforce(allowed["plan"]["actions"], command_id=command["command_id"])
            worker_types = {
                row.get("task_type") for row in list_jobs()["items"]
                if row.get("schedule_source") == "daily_workforce"
            }
            require(worker_types.issubset({"seo", "geo"}), "daily workforce scheduled actions outside the ChatGPT plan")

            # With no active Mission in this isolated runtime, autonomy must stop
            # before planning/generation/deployment side effects.
            result = autonomy.run_once(force=True)
            require(result["skipped"], "SEO/GEO autonomy ran without an active ChatGPT Mission")
            require(result["reason"] == "chatgpt_mission_required", "autonomy did not explain the missing Mission gate")
            print("R8-18 ChatGPT-controlled SEO/GEO execution gate: PASS")
        finally:
            if previous is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = previous


if __name__ == "__main__":
    main()
