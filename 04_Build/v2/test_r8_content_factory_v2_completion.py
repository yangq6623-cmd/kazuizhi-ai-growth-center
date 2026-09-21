import json
import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SRC))


with tempfile.TemporaryDirectory() as temp_dir:
    os.environ["LOCALAPPDATA"] = temp_dir

    from core.storage import data_root
    from promotion import content_factory
    import promotion.content_factory_v2_extensions  # noqa: F401
    import promotion.content_factory_v2_finalization_patch  # noqa: F401
    from promotion import material_library, media_adapters, platform_rules

    campaign = content_factory.create_campaign({
        "region": "涟水县",
        "service": "家电安装维修",
        "title": "冰箱不制冷先检查什么",
        "evidence": "真实客服高频问题",
        "goal": "获得可追溯的本地咨询",
    })

    # Automatic material inbox: real material is indexed/promoted only with
    # explicit classification + consent metadata.
    inbox = data_root() / "r8" / "material_inbox" / campaign["id"]
    inbox.mkdir(parents=True, exist_ok=True)
    photo = inbox / "case.jpg"
    photo.write_bytes(b"fake-jpeg-for-index")
    (inbox / "case.jpg.json").write_text(json.dumps({
        "kind": "真实现场照片",
        "consent_confirmed": True,
        "tags": ["冰箱", "检测"],
        "note": "测试素材",
    }, ensure_ascii=False), encoding="utf-8")
    scan = material_library.scan_material_inbox()
    assert scan["summary"]["promoted"] == 1
    data = content_factory._load()
    indexed = next(x for x in data["assets"] if x.get("campaign_id") == campaign["id"])
    assert indexed["source_origin"] == "material_inbox"
    assert indexed["source_fingerprint"]
    assert indexed["media_metadata"]["media_class"] == "image"

    # Unknown files are indexed but never silently treated as publishable. The
    # unchanged first file must reuse its SHA256 instead of being rehashed.
    unknown = inbox / "unknown.png"
    unknown.write_bytes(b"unknown")
    scan = material_library.scan_material_inbox()
    assert scan["summary"]["unclassified"] >= 1
    assert scan["summary"]["hash_reused"] >= 1

    video = content_factory.create_video({"campaign_id": campaign["id"]})
    assert video["status"] == "等待ChatGPT策划"

    def production_plan(version, suffix=""):
        return {
            "schema": "kazuizhi-content-production/v1",
            "version": version,
            "campaign_id": campaign["id"],
            "objective": "获得可追溯的本地咨询",
            "target_platforms": ["抖音"],
            "topic": "冰箱不制冷先检查什么" + suffix,
            "pain_point": "用户担心维修前无法判断问题范围",
            "titles": ["冰箱不制冷，先检查这几项" + suffix],
            "script": "先检查电源、温控和散热状态，再由师傅现场检测后判断故障原因。",
            "storyboard": [
                {
                    "shot_id": "S01", "purpose": "提出问题", "duration_seconds": 3,
                    "subtitle": "冰箱不制冷先检查什么？",
                    "source_preference": ["local_real", "licensed_external", "ai_generated", "info_card"],
                },
                {
                    "shot_id": "S02", "purpose": "真实检测原则", "duration_seconds": 4,
                    "subtitle": "先检查，再检测，最后判断",
                    "required_real": True,
                    "source_preference": ["local_real", "licensed_external", "info_card"],
                },
            ],
            "platform_adaptation": {
                "抖音": {
                    "hook": "冰箱不制冷，先别急着换零件",
                    "title": "冰箱不制冷先检查这几项",
                    "caption": "先检查电源、温控和散热，再由师傅现场检测。",
                    "schedule_hint": "由ChatGPT结合真实账号历史效果选择",
                }
            },
            "cta": "通过小程序提交需求，等待师傅报价",
            "output": {"width": 1080, "height": 1920, "fps": 30, "duration_seconds": 12},
        }

    planned = content_factory.apply_chatgpt_plan({
        "video_id": video["id"], "campaign_id": campaign["id"],
        "production_plan": production_plan(1),
    })
    assert planned["production_plan"]["platform_adaptation"]["抖音"]["title"]
    assert planned["production_plan"]["rule_center"]["strategy_owner"] == "ChatGPT"

    output_root = data_root() / "r8" / "video_output" / campaign["id"] / video["id"]
    output_root.mkdir(parents=True, exist_ok=True)
    final = output_root / "FINAL.mp4"
    final.write_bytes(b"0" * 20000)
    candidate = content_factory.record_candidate({
        "video_id": video["id"], "local_path": str(final), "duration_seconds": 12,
        "quality_notes": "unit test", "technical_qc": {"passed": True},
        "source_summary": [
            {"shot_id": "S01", "source": "info_card"},
            {"shot_id": "S02", "source": "local_real"},
        ],
    })
    state = next(x for x in content_factory._load()["videos"] if x["id"] == video["id"])
    assert state["status"] == "等待ChatGPT质检"
    assert content_factory.pending_chatgpt_qc_handoff()["count"] == 1

    rework = content_factory.apply_chatgpt_qc({
        "video_id": video["id"], "candidate_id": candidate["id"],
        "decision": "rework", "score": 62,
        "reasons": ["开头表达需要更清楚"],
        "shot_feedback": [{"shot_id": "S01", "action": "改写开头"}],
    })
    assert rework["status"] == "等待ChatGPT策划"
    handoff = content_factory.pending_chatgpt_handoff()
    assert handoff["count"] == 1
    assert handoff["items"][0]["previous_chatgpt_qc"]["status"] == "rework"

    planned = content_factory.apply_chatgpt_plan({
        "video_id": video["id"], "campaign_id": campaign["id"],
        "production_plan": production_plan(2, "第二版"),
    })
    final2 = output_root / "FINAL_v2.mp4"
    final2.write_bytes(b"1" * 20000)
    candidate2 = content_factory.record_candidate({
        "video_id": video["id"], "local_path": str(final2), "duration_seconds": 12,
        "quality_notes": "unit test v2", "technical_qc": {"passed": True},
        "source_summary": [{"shot_id": "S02", "source": "local_real"}],
    })
    passed = content_factory.apply_chatgpt_qc({
        "video_id": video["id"], "candidate_id": candidate2["id"],
        "decision": "pass", "score": 90, "reasons": ["通过"],
    })
    assert passed["status"] == "等待人工审核"

    approved = content_factory.review_video({
        "video_id": video["id"], "candidate_id": candidate2["id"],
        "decision": "确认发布", "note": "老板验收通过",
    })
    assert approved["status"] == "已授权发布"

    account = content_factory.save_account({
        "platform": "抖音", "account_name": "测试账号", "region": "涟水县",
        "service": "家电安装维修", "connection_status": "已验证可发布",
    })

    # Hard rules cannot be overridden by ChatGPT or the caller.
    try:
        content_factory.create_publish_plan({
            "video_id": video["id"], "account_id": account["id"],
            "title": "全城第一保证修好", "caption": "测试", "scheduled_for": "今晚",
        })
        raise AssertionError("Risky absolute claim bypassed platform hard rules")
    except ValueError as error:
        assert "硬规则" in str(error) or "宣传承诺" in str(error)

    publish = content_factory.create_publish_plan({
        "video_id": video["id"], "account_id": account["id"],
    })
    assert publish["rule_check"]["passed"] is True
    assert publish["strategy_source"] == "chatgpt_platform_adaptation"
    assert publish["daily_cap"]["limit"] == 1

    receipt = content_factory.record_receipt({
        "plan_id": publish["id"], "result": "成功",
        "platform_content_id": "content-001", "url": "https://example.com/content-001",
        "reason": "测试真实回执结构",
    })
    assert receipt["learning_summary"]["samples"] == 1
    assert platform_rules.learning_summary()["samples"] == 1

    adapters = media_adapters.status(campaign["id"])
    assert adapters["licensed_external"]["ready"] is True
    assert adapters["ai_generated"]["ready"] is True

    dashboard = content_factory.dashboard()
    assert dashboard["platform_rule_center"]["strategy_owner"] == "ChatGPT"
    assert dashboard["material_library"]["summary"]["indexed"] >= 2
    assert dashboard["production_events"]

print("PASS: R8 content factory completion layer")
