import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))

from promotion import content_factory as cf
from promotion.local_mission_planner import build_local_mission_plan, recover_video


def main() -> None:
    old_local = os.environ.get("LOCALAPPDATA")
    with tempfile.TemporaryDirectory() as temp:
        os.environ["LOCALAPPDATA"] = temp
        try:
            campaign = cf.create_campaign({
                "region": "涟水县",
                "service": "水电安装维修",
                "title": "涟水县水电安装维修第一轮本地增长验证",
                "evidence": "老板通过普通ChatGPT下达真实低风险经营Mission。",
                "goal": "形成可追溯的本地内容和真实经营验证基线",
                "source_type": "ChatGPT自治经营决策",
                "owner_note": "普通ChatGPT负责战略，本机负责持续执行",
            })
            video = cf.create_video({"campaign_id": campaign["id"]})
            assert video["status"] == "等待ChatGPT策划"

            plan = build_local_mission_plan(campaign)
            assert plan["schema"] == "kazuizhi-content-production/v1"
            assert plan["campaign_id"] == campaign["id"]
            assert plan["storyboard"]
            assert plan["qc"]["owner_review_required"] is True
            assert "订单量" not in plan["script"]

            recovered = recover_video(video["id"])
            assert recovered is not None
            assert recovered["status"] == "等待生产"
            assert recovered["plan_source"] in {
                "local_autonomy_under_chatgpt_mission",
                "local_autonomy_under_active_mission",
            }

            current = cf._load()
            stored = next(x for x in current["videos"] if x["id"] == video["id"])
            assert stored["status"] == "等待生产"
            assert stored["production_plan"]
            assert stored["chatgpt_handoff"]["phase"] == "local_autonomy_plan"
            assert stored["last_error"] is None

            local_campaign = cf.create_campaign({
                "region": "涟水县",
                "service": "水电安装维修",
                "title": "普通本地草稿",
                "evidence": "本地人工创建",
                "goal": "准备草稿",
                "source_type": "本地需求信号",
            })
            local_video = cf.create_video({"campaign_id": local_campaign["id"]})
            assert recover_video(local_video["id"]) is None, "non-Mission local draft must not gain implicit strategic authorization"
        finally:
            if old_local is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = old_local

    print("PASS: authorized Mission can continue routine local content planning without API or a permanent chat window.")


if __name__ == "__main__":
    main()
