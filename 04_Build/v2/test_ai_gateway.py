"""Regression gate for the direct ChatGPT AI Gateway without live API usage."""
import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "05_V2.0.0_Source"


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def response(payload):
    return {"output": [{"type": "message", "content": [{"type": "output_text", "text": json.dumps(payload, ensure_ascii=False)}]}]}


def main():
    old_local = os.environ.get("LOCALAPPDATA")
    old_key = os.environ.get("OPENAI_API_KEY")
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["LOCALAPPDATA"] = tmp
        os.environ["OPENAI_API_KEY"] = "sk-test-regression-only-not-live"
        sys.path.insert(0, str(SRC))
        try:
            from backend import content_factory_patch  # noqa: F401
            from promotion import content_factory_v2_extensions  # noqa: F401
            from backend import autonomous_ops_patch  # noqa: F401
            from integrations import ai_gateway
            from promotion import content_factory as cf

            campaign = cf.create_campaign({
                "region": "涟水县",
                "service": "水电安装维修",
                "title": "东面灯坏了",
                "evidence": "隔离测试需求信号",
                "goal": "获得可追溯的真实咨询或订单",
            })
            video = cf.create_video({"campaign_id": campaign["id"]})
            data = cf._load()
            current = next(x for x in data["videos"] if x["id"] == video["id"])
            current["status"] = "异常待处理"
            current["chatgpt_handoff"] = {"kind": "content_production", "phase": "retry_exhausted", "retry_count": 3}
            cf._save(data)

            def planning_transport(request_payload, _key):
                check(request_payload.get("model"), "gateway model missing")
                plan = {
                    "kind": "content_production",
                    "video_id": video["id"],
                    "campaign_id": campaign["id"],
                    "production_plan": {
                        "schema": "kazuizhi-content-production/v1",
                        "version": 1,
                        "campaign_id": campaign["id"],
                        "objective": campaign["goal"],
                        "target_platforms": ["抖音", "视频号"],
                        "topic": "灯坏了先判断是否跳闸",
                        "pain_point": "用户担心故障扩大或维修过程不透明",
                        "titles": ["家里灯突然不亮，先检查这两步"],
                        "script": "灯突然不亮时，先确认是否只是单个灯具故障，再检查配电箱是否跳闸。涉及带电检修时请交给专业人员处理。",
                        "storyboard": [
                            {"shot_id": "S01", "purpose": "说明问题", "duration_seconds": 3, "narration": "灯突然不亮先别急", "subtitle": "灯不亮先判断范围", "material_query": "家庭照明示意", "required_real": False, "source_preference": ["ai_generated", "info_card"]},
                            {"shot_id": "S02", "purpose": "安全提示", "duration_seconds": 4, "narration": "涉及带电检修交给专业人员", "subtitle": "带电检修请找专业人员", "material_query": "安全提示卡", "required_real": False, "source_preference": ["info_card"]},
                        ],
                        "voice": {"enabled": True, "profile": "卡嘴子专业中文声线"},
                        "subtitle": {"enabled": True, "style": "竖屏大字安全区"},
                        "cover": {"title": "灯坏了先查什么"},
                        "cta": "通过小程序提交需求，等待师傅报价",
                        "output": {"width": 1080, "height": 1920, "fps": 30, "duration_seconds": 20},
                        "qc": {"owner_review_required": True},
                        "material_policy": {"local_material_optional": True, "quality_first": True, "never_fake_real_case": True, "missing_material_must_not_block": True},
                    },
                }
                return response(plan)

            result = ai_gateway.run_once(limit=1, transport=planning_transport)
            check(result["processed"] == 1, "direct gateway did not process planning")
            current = next(x for x in cf._load()["videos"] if x["id"] == video["id"])
            check(current["status"] == "等待生产", "retry-exhausted task did not recover into production")
            check(current.get("production_plan"), "validated production plan missing")

            candidate_path = Path(tmp) / "FINAL.MP4"
            candidate_path.write_bytes(b"regression-candidate")
            candidate = cf.record_candidate({
                "video_id": video["id"],
                "local_path": str(candidate_path),
                "duration_seconds": 20,
                "technical_qc": {"passed": True, "playable": True},
                "source_summary": [{"kind": "info_card", "truthful": True}],
            })
            check(next(x for x in cf._load()["videos"] if x["id"] == video["id"])["status"] == "等待ChatGPT质检", "candidate did not reach ChatGPT QC")

            def qc_transport(_request_payload, _key):
                return response({
                    "kind": "content_qc",
                    "video_id": video["id"],
                    "candidate_id": candidate["id"],
                    "decision": "pass",
                    "score": 92,
                    "reasons": ["目标一致", "无虚构真实维修案例"],
                    "shot_feedback": [],
                })

            result = ai_gateway.run_once(limit=1, transport=qc_transport)
            check(result["processed"] == 1, "direct gateway did not process content QC")
            current = next(x for x in cf._load()["videos"] if x["id"] == video["id"])
            check(current["status"] == "等待人工审核", "ChatGPT QC pass did not preserve owner review gate")
            check(current.get("approved_at") is None, "AI gateway must never approve publication")
            check(ai_gateway.gateway_status()["configured"], "environment credential was not detected")
            print("PASS: direct AI Gateway recovers planning, validates ChatGPT output, performs QC and preserves owner approval")
        finally:
            try:
                sys.path.remove(str(SRC))
            except ValueError:
                pass
            if old_local is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = old_local
            if old_key is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = old_key


if __name__ == "__main__":
    main()
