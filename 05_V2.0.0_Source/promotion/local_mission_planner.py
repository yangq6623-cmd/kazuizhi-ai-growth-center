"""Local routine content planner for ChatGPT-authorized Missions.

Normal ChatGPT remains the strategic owner brain.  Once a Mission has been
created from a validated ChatGPT Decision Pack, routine non-financial content
planning must not block on a permanently-open chat window or an OpenAI API key.
This module creates a conservative executable production plan from the approved
Mission context and the existing local content rules.  It never publishes,
performs finance, or invents real customers/orders/cases.
"""
from __future__ import annotations

from core.storage import now_iso
from promotion.production_contract import normalize_contract
from promotion import content_factory as cf

MISSION_SOURCE = "ChatGPT自治经营决策"
RECOVERABLE_STATES = {"等待ChatGPT策划", "退回重做", "异常待处理"}


def mission_allows_local_content(campaign: dict) -> bool:
    return isinstance(campaign, dict) and str(campaign.get("source_type") or "").strip() == MISSION_SOURCE


def build_local_mission_plan(campaign: dict) -> dict:
    """Build one safe 30s production plan from an already-approved Mission."""
    if not mission_allows_local_content(campaign):
        raise ValueError("只有经ChatGPT Decision Pack创建的Mission才能启用本地自治策划")

    region = str(campaign.get("region") or "本地").strip()
    service = str(campaign.get("service") or "本地维修服务").strip()
    goal = str(campaign.get("goal") or "获得可追溯的真实咨询或订单").strip()
    evidence = str(campaign.get("evidence") or "当前没有可核验经营证据，因此不写订单量、排名或效果承诺。").strip()
    topic = str(campaign.get("title") or f"{region}{service}需求说明").strip()

    script = (
        f"在{region}遇到{service}需求，先把地点、问题现象和期望时间说明清楚。"
        "平台只展示实际开放范围和真实任务状态，不虚构订单、客户评价或维修案例。"
        "提交需求后，等待符合条件的服务者按平台规则响应；价格、时间和服务内容以双方实际确认记录为准。"
        "如果只是了解服务，也可以先查看平台当前开放范围和需求填写说明。"
    )

    raw = {
        "schema": "kazuizhi-content-production/v1",
        "version": 1,
        "campaign_id": campaign.get("id"),
        "objective": goal,
        "target_platforms": ["通用"],
        "topic": topic,
        "pain_point": evidence,
        "titles": [
            f"{region}{service}需求怎么发布？先把问题说明白",
            f"在{region}找{service}，先确认这4件事",
            f"{service}需求发布前的30秒检查清单",
        ],
        "script": script,
        "storyboard": [
            {
                "shot_id": "S01",
                "purpose": f"用信息卡说明{region}{service}常见需求，不冒充真实客户案例",
                "duration_seconds": 5,
                "narration": f"在{region}需要{service}，第一步先把问题说清楚。",
                "subtitle": "地点 + 问题现象 + 期望时间",
                "material_query": f"{region} {service} 信息卡 示意",
                "required_real": False,
                "source_preference": ["brand_card", "info_card", "ai_generated"],
                "synthetic_disclosure": "AI辅助示意",
            },
            {
                "shot_id": "S02",
                "purpose": "展示需求填写步骤和平台状态说明，不展示虚构订单",
                "duration_seconds": 8,
                "narration": "填写地点、问题现象和期望时间，再核对平台实际开放范围。",
                "subtitle": "需求写清楚，响应才更准确",
                "material_query": "需求表单 平台流程 信息图",
                "required_real": False,
                "source_preference": ["brand_card", "info_card", "ai_generated"],
                "synthetic_disclosure": "AI辅助示意",
            },
            {
                "shot_id": "S03",
                "purpose": "说明服务响应、价格和时间必须以真实确认记录为准",
                "duration_seconds": 9,
                "narration": "服务响应、价格和时间，以平台状态和双方实际确认记录为准。",
                "subtitle": "不承诺虚假价格 · 不虚构案例",
                "material_query": "服务确认 安全提示 信息卡",
                "required_real": False,
                "source_preference": ["info_card", "brand_card", "ai_generated"],
                "synthetic_disclosure": "AI辅助示意",
            },
            {
                "shot_id": "S04",
                "purpose": "品牌收口与低风险行动提示",
                "duration_seconds": 8,
                "narration": "打开卡嘴子，按实际情况填写需求，先确认当前服务范围。",
                "subtitle": "专业维修找师傅，生活小事也能发任务",
                "material_query": "卡嘴子 品牌卡 小程序 行动提示",
                "required_real": False,
                "source_preference": ["brand_card", "info_card"],
                "synthetic_disclosure": "",
            },
        ],
        "voice": {"enabled": True, "profile": "卡嘴子专业中文声线"},
        "subtitle": {"enabled": True, "style": "竖屏大字安全区"},
        "cover": {
            "title": f"{region}{service}需求怎么发布？",
            "subtitle": "先把地点、问题和时间说明白",
        },
        "cta": "通过小程序按实际情况提交需求；发布前请核对服务范围。",
        "output": {"width": 1080, "height": 1920, "fps": 30, "duration_seconds": 30},
        "qc": {
            "machine": ["playable", "non_empty", "video_stream", "correct_dimensions"],
            "chatgpt": ["goal_alignment", "truthfulness", "script_storyboard_match", "platform_fit"],
            "owner_review_required": True,
        },
        "material_policy": {
            "local_material_optional": True,
            "quality_first": True,
            "never_fake_real_case": True,
            "missing_material_must_not_block": True,
        },
    }
    return normalize_contract(raw, campaign)


def recover_video(video_id: str) -> dict | None:
    """Move one stuck production task into the local execution queue truthfully."""
    data = cf._load()
    video = next((x for x in data.get("videos", []) if x.get("id") == video_id), None)
    if not video or video.get("production_plan"):
        return None
    if video.get("status") not in RECOVERABLE_STATES:
        return None

    campaign = next((x for x in data.get("campaigns", []) if x.get("id") == video.get("campaign_id")), None)
    if not mission_allows_local_content(campaign):
        return None

    handoff = video.get("chatgpt_handoff") if isinstance(video.get("chatgpt_handoff"), dict) else {}
    if video.get("status") == "异常待处理" and handoff.get("kind") not in {None, "content_production"}:
        return None

    plan = build_local_mission_plan(campaign)
    if not cf._claims_safe(plan.get("script"), plan.get("titles"), plan.get("cta")):
        raise ValueError("本地自治生产方案包含不允许的宣传承诺")

    assets = cf._campaign_assets(data, campaign["id"])
    video.update({
        "script": plan["script"],
        "duration_target": plan["output"]["duration_seconds"],
        "cta": plan["cta"],
        "asset_ids": [x["id"] for x in assets],
        "status": "等待生产",
        "production_plan": plan,
        "plan_version": plan["version"],
        "plan_source": "local_autonomy_under_chatgpt_mission",
        "shot_tasks": list(plan["storyboard"]),
        "target_platforms": list(plan["target_platforms"]),
        "bottleneck": None,
        "auto_action": "ChatGPT已批准经营Mission；日常内容策划由本地自治员工继续执行，不等待API或常驻聊天窗口。",
        "last_error": None,
        "retry_count": 0,
        "technical_qc": None,
        "chatgpt_qc": {"status": "planned", "plan_version": plan["version"], "source": "strategic_mission_guardrail"},
        "material_policy": plan["material_policy"],
        "plan_received_at": now_iso(),
    })
    handoff.update({
        "kind": "content_production",
        "phase": "local_autonomy_plan",
        "message": "ChatGPT战略Mission已授权，本地自治策划器已生成安全生产合同。",
        "response_at": now_iso(),
        "updated_at": now_iso(),
        "retry_count": 0,
    })
    video["chatgpt_handoff"] = handoff
    campaign["status"] = "视频生产中"
    cf._save(data)
    return {"video_id": video["id"], "campaign_id": campaign["id"], "status": video["status"], "plan_source": video["plan_source"]}
