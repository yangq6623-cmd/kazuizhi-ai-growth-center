"""Regression contract for the unified R7 -> ChatGPT -> R8 autonomous Mission loop."""
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "05_V2.0.0_Source"


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    old_local = os.environ.get("LOCALAPPDATA")
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["LOCALAPPDATA"] = tmp
        sys.path.insert(0, str(SRC))
        try:
            from backend import content_factory_patch  # noqa: F401
            from promotion import content_factory_v2_extensions  # noqa: F401
            from backend import deep_productization_patch  # noqa: F401
            from backend import growth_chain_patch  # noqa: F401
            from core import decision_center_mission_patch  # noqa: F401
            from backend import autonomous_ops_patch  # noqa: F401
            from core import autonomous_ops, decision_center
            from core.autonomous_mission_decisions import apply_chatgpt_mission_decision
            from promotion import content_factory as cf

            campaign = cf.create_campaign({
                "region": "涟水县",
                "service": "家电安装维修",
                "title": "空调不制冷的本地真实咨询机会",
                "evidence": "隔离测试中的可核验需求信号",
                "goal": "获得真实咨询并追踪到订单",
            })
            result = autonomous_ops.sync_from_runtime(autostart=True)
            mission = result.get("active_mission")
            check(mission and mission.get("growth_id") == campaign["id"], "active Mission did not share the R8 Growth ID")
            check(str(mission.get("mission_id") or "").startswith("MISSION-"), "Mission identity missing")

            factory = cf._load()
            videos = [x for x in factory.get("videos", []) if x.get("campaign_id") == campaign["id"]]
            check(len(videos) == 1, "ready R7/R8 campaign should automatically enter one R8 production task")
            check(videos[0].get("status") == "等待ChatGPT策划", "auto-started task must wait for real ChatGPT planning")
            check(mission.get("stage") in {"AI决策", "待自动立项"}, "Mission stage did not enter AI decision pipeline")

            handoff = cf.pending_chatgpt_handoff()
            item = next((x for x in handoff.get("items", []) if x.get("campaign_id") == campaign["id"]), None)
            check(item is not None, "ChatGPT handoff missing for active Mission")
            context = item.get("mission_context") or {}
            check(context.get("mission_id") == mission.get("mission_id"), "ChatGPT handoff lost shared Mission ID")
            check("r7_context" in context, "R7 decision context was not passed to R8 ChatGPT handoff")

            goal = autonomous_ops.set_owner_goal({
                "objective": "优先提高涟水县真实维修咨询和订单",
                "metric": "真实咨询/订单",
            })
            check(goal.get("source") == "owner", "owner goal source is not truthful")
            snapshot = autonomous_ops.snapshot(sync=False)
            check(snapshot.get("owner_goal", {}).get("objective") == goal["objective"], "owner goal not persisted")
            check(snapshot.get("autonomy", {}).get("default") == "L4", "autonomy boundary missing")

            report = decision_center.decision_snapshot()
            contract = (report.get("chatgpt_handoff") or {}).get("mission_decision_contract") or {}
            check(contract.get("kind") == "mission_decision", "R7 did not expose the ChatGPT Mission decision contract")
            check(set(contract.get("allowed_actions") or []) == {"continue", "stop", "create_mission"}, "Mission decision actions changed unexpectedly")

            stopped = apply_chatgpt_mission_decision({
                "action": "stop",
                "mission_id": mission["mission_id"],
                "reason": "隔离测试：停止当前非资金执行，验证停止权不会绕过真实性边界",
            })
            check(stopped.get("state") == "paused", "ChatGPT stop decision did not pause Mission")
            old_video = next(x for x in cf._load().get("videos", []) if x.get("id") == videos[0]["id"])
            check(old_video.get("status") == "已暂缓", "Mission stop did not safely pause the active R8 task")
            check(old_video.get("status") != "已授权发布", "Mission stop must never authorize publication")

            created = apply_chatgpt_mission_decision({
                "action": "create_mission",
                "reason": "隔离测试：基于R7复盘创建下一轮经营任务",
                "region": "涟水县",
                "service": "管道疏通维修",
                "title": "下水道堵塞的真实本地需求",
                "evidence": "隔离测试中的第二条可核验需求信号",
                "goal": "获得可追溯的真实咨询或订单",
            })
            check(str(created.get("mission_id") or "").startswith("MISSION-"), "create_mission did not create a Mission")
            check(created.get("growth_id") and created.get("growth_id") != campaign["id"], "create_mission did not create a new Growth ID")
            new_factory = cf._load()
            new_videos = [x for x in new_factory.get("videos", []) if x.get("campaign_id") == created.get("growth_id")]
            check(len(new_videos) == 1 and new_videos[0].get("status") == "等待ChatGPT策划", "new Mission did not automatically enter ChatGPT planning")

            continued = apply_chatgpt_mission_decision({
                "action": "continue",
                "mission_id": created["mission_id"],
                "reason": "隔离测试：保持当前有效方向继续",
            })
            check(continued.get("video_id") == new_videos[0]["id"], "continue should reuse the current active execution instead of duplicating it")
            check(len([x for x in cf._load().get("videos", []) if x.get("campaign_id") == created.get("growth_id")]) == 1, "continue created a duplicate active R8 task")

            feedback = autonomous_ops.feedback_for_r7()
            check(any(x.get("mission_id") == created.get("mission_id") for x in feedback.get("items", [])), "R8 Mission facts do not feed back into R7")
            check(all(x.get("status") != "已授权发布" for x in cf._load().get("videos", [])), "Mission automation bypassed owner review")

            print("PASS: boss goal, R7 decisions, ChatGPT Mission decisions, R8 execution and truthful feedback form one autonomous loop")
        finally:
            try:
                sys.path.remove(str(SRC))
            except ValueError:
                pass
            if old_local is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = old_local


if __name__ == "__main__":
    main()
