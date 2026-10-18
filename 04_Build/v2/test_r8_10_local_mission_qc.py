import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))

from promotion import content_factory as cf
from promotion import content_factory_v2_extensions  # noqa: F401
from promotion import local_mission_qc_patch  # noqa: F401
from promotion.local_mission_planner import build_local_mission_plan
from promotion.local_mission_qc_patch import recover_video


def _summary(plan):
    return [
        {
            "shot_id": shot.get("shot_id"),
            "source": "info_card",
            "asset_id": None,
            "disclosure": "信息卡",
            "note": "测试用可追溯信息卡",
        }
        for shot in plan.get("storyboard") or []
    ]


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
            })
            plan = build_local_mission_plan(campaign)
            video = cf.create_video({"campaign_id": campaign["id"], "production_plan": plan})
            output = Path(temp) / "FINAL.mp4"
            output.write_bytes(b"0" * 20000)
            candidate = cf.record_candidate({
                "video_id": video["id"],
                "local_path": str(output),
                "duration_seconds": 30,
                "quality_notes": "技术质检通过",
                "technical_qc": {"passed": True, "file_exists": True, "non_empty": True, "decode_ok": True},
                "source_summary": _summary(plan),
            })
            assert candidate["exists"] is True
            data = cf._load()
            stored = next(x for x in data["videos"] if x["id"] == video["id"])
            assert stored["status"] == "等待人工审核", stored
            assert stored["local_qc"]["decision"] == "pass"
            assert stored["chatgpt_qc"]["status"] == "not_required_for_authorized_mission"
            assert stored["local_qc"]["publish_authorized"] is False
            assert stored["bottleneck"] is None

            # Old #462-style QC timeout must recover locally instead of waiting
            # for a permanently-open ChatGPT conversation.
            stored["status"] = "异常待处理"
            stored["bottleneck"] = "ChatGPT生产/QC请求连续重发仍未返回"
            stored["last_error"] = "QC timeout"
            stored["retry_count"] = 3
            stored["chatgpt_handoff"] = {"kind": "content_qc", "phase": "retry_exhausted", "retry_count": 3}
            cf._save(data)
            recovered = recover_video(video["id"])
            assert recovered is not None
            assert recovered["status"] == "等待人工审核"
            data = cf._load()
            stored = next(x for x in data["videos"] if x["id"] == video["id"])
            assert stored["retry_count"] == 0
            assert stored["chatgpt_handoff"]["phase"] == "local_autonomy_qc"

            # Locally-created campaigns do not inherit ChatGPT strategic
            # authorization and therefore keep the existing ChatGPT QC path.
            local_campaign = cf.create_campaign({
                "region": "涟水县",
                "service": "水电安装维修",
                "title": "普通本地草稿",
                "evidence": "本地人工创建",
                "goal": "准备草稿",
                "source_type": "本地需求信号",
            })
            local_plan = build_local_mission_plan({**local_campaign, "source_type": "ChatGPT自治经营决策"})
            local_video = cf.create_video({"campaign_id": local_campaign["id"], "production_plan": local_plan})
            local_output = Path(temp) / "LOCAL.mp4"
            local_output.write_bytes(b"1" * 20000)
            cf.record_candidate({
                "video_id": local_video["id"],
                "local_path": str(local_output),
                "duration_seconds": 30,
                "quality_notes": "技术质检通过",
                "technical_qc": {"passed": True, "file_exists": True, "non_empty": True, "decode_ok": True},
                "source_summary": _summary(local_plan),
            })
            data = cf._load()
            local_stored = next(x for x in data["videos"] if x["id"] == local_video["id"])
            assert local_stored["status"] == "等待ChatGPT质检"
        finally:
            if old_local is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = old_local

    print("PASS: ChatGPT-authorized Missions use local autonomous QC and preserve owner final review without API dependency.")


if __name__ == "__main__":
    main()
