"""Local autonomous content QC for validated ChatGPT Missions.

Normal ChatGPT remains the strategic owner brain. Once a Mission was created
from a validated ChatGPT Decision Pack, routine post-render QC must not require
a permanently-open chat window or an OpenAI API key. This module wraps the
existing R8 candidate flow and replaces per-video ChatGPT QC with a conservative
local QC gate only for those authorized Missions.

Truth rules:
- never marks content as published;
- never bypasses the owner final-review gate;
- never touches finance or account verification;
- high-risk or unverifiable content becomes owner attention;
- repairable routine failures are automatically re-planned/re-rendered twice,
  then escalated instead of looping forever.
"""
from __future__ import annotations

from pathlib import Path

from core.storage import now_iso
from promotion import content_factory as cf
from promotion.local_mission_planner import build_local_mission_plan, mission_allows_local_content

MAX_LOCAL_QC_REWORKS = 2
_INSTALLED = False
_ORIGINAL_RECORD_CANDIDATE = None


def _campaign(data: dict, video: dict) -> dict | None:
    return next((x for x in data.get("campaigns", []) if x.get("id") == video.get("campaign_id")), None)


def _latest_candidate(video: dict) -> dict | None:
    candidates = [x for x in video.get("candidates", []) if isinstance(x, dict)]
    return candidates[-1] if candidates else None


def _event(data: dict, video: dict, kind: str, detail: dict) -> None:
    events = data.setdefault("events", [])
    events.append({
        "id": cf._id("EVT"),
        "created_at": now_iso(),
        "kind": kind,
        "video_id": video.get("id"),
        "campaign_id": video.get("campaign_id"),
        "detail": detail,
    })
    data["events"] = events[-1000:]


def _evaluate(video: dict, campaign: dict, candidate: dict) -> dict:
    repairable: list[str] = []
    high_risk: list[str] = []

    path = Path(str(candidate.get("local_path") or ""))
    technical_qc = candidate.get("technical_qc") or video.get("technical_qc") or {}
    plan = video.get("production_plan") if isinstance(video.get("production_plan"), dict) else {}
    storyboard = plan.get("storyboard") if isinstance(plan.get("storyboard"), list) else []
    source_summary = candidate.get("source_summary") if isinstance(candidate.get("source_summary"), list) else []

    if not path.is_file() or path.stat().st_size < 10 * 1024:
        repairable.append("FINAL.MP4不存在或文件过小")
    if not technical_qc.get("passed"):
        repairable.append("技术质检未通过")
    if not plan or not storyboard or not str(plan.get("script") or "").strip():
        repairable.append("生产合同缺少脚本或分镜")
    if storyboard and len(source_summary) < len(storyboard):
        repairable.append("成片素材来源记录与分镜数量不一致")

    if not cf._claims_safe(plan.get("script"), plan.get("titles"), plan.get("cta")):
        high_risk.append("脚本或标题包含绝对化/高风险宣传承诺")

    for item in source_summary:
        if not isinstance(item, dict):
            continue
        source = str(item.get("source") or "")
        disclosure = str(item.get("disclosure") or "").strip()
        asset_id = str(item.get("asset_id") or "").strip()
        if source == "ai_generated" and not disclosure:
            high_risk.append("AI辅助镜头缺少必要披露")
        if source == "local_real" and not asset_id:
            high_risk.append("真实素材来源无法追溯")

    policy = plan.get("material_policy") if isinstance(plan.get("material_policy"), dict) else {}
    if policy.get("never_fake_real_case") is not True:
        repairable.append("生产合同缺少“不伪造真实案例”约束")

    region = str(campaign.get("region") or "").strip()
    service = str(campaign.get("service") or "").strip()
    semantic_text = " ".join([
        str(plan.get("topic") or ""),
        str(plan.get("script") or ""),
        " ".join(str(x) for x in (plan.get("titles") or [])),
    ])
    if region and region not in semantic_text:
        repairable.append("内容与Mission区域目标关联不足")
    if service and service not in semantic_text:
        repairable.append("内容与Mission服务目标关联不足")

    if high_risk:
        decision = "human_required"
    elif repairable:
        decision = "rework"
    else:
        decision = "pass"

    return {
        "status": "passed" if decision == "pass" else decision,
        "decision": decision,
        "source": "local_autonomous_qc_under_chatgpt_mission",
        "checked_at": now_iso(),
        "candidate_id": candidate.get("id"),
        "plan_version": video.get("plan_version") or 0,
        "repairable_reasons": repairable,
        "high_risk_reasons": high_risk,
        "owner_review_required": True,
        "publish_authorized": False,
    }


def _apply(video: dict, campaign: dict, candidate: dict, data: dict) -> dict:
    result = _evaluate(video, campaign, candidate)
    video["local_qc"] = result
    video["chatgpt_qc"] = {
        "status": "not_required_for_authorized_mission",
        "source": "strategic_mission_guardrail",
        "candidate_id": candidate.get("id"),
        "updated_at": now_iso(),
    }
    handoff = video.get("chatgpt_handoff") if isinstance(video.get("chatgpt_handoff"), dict) else {}
    handoff.update({
        "kind": "content_qc",
        "phase": "local_autonomy_qc",
        "message": "ChatGPT已批准经营Mission；例行内容QC由本地自治规则完成，不等待API或常驻聊天窗口。",
        "response_at": now_iso(),
        "updated_at": now_iso(),
        "retry_count": 0,
    })
    video["chatgpt_handoff"] = handoff
    video["retry_count"] = 0
    video["last_error"] = None

    if result["decision"] == "pass":
        video["status"] = "等待人工审核"
        video["bottleneck"] = None
        video["auto_action"] = "本地自治内容QC已通过；FINAL.MP4保持未发布状态，只等待老板最终审核。"
    elif result["decision"] == "human_required":
        video["status"] = "异常待处理"
        video["bottleneck"] = "本地自治QC发现高风险或不可验证内容"
        video["auto_action"] = "已停止自动发布链；请老板确认高风险内容后再继续。"
    else:
        attempts = int(video.get("local_qc_rework_count") or 0) + 1
        video["local_qc_rework_count"] = attempts
        if attempts > MAX_LOCAL_QC_REWORKS:
            video["status"] = "异常待处理"
            video["bottleneck"] = "本地自治QC连续返工仍未通过"
            video["auto_action"] = f"已自动返工{MAX_LOCAL_QC_REWORKS}次仍未通过，停止循环并交老板处理。"
        else:
            plan = build_local_mission_plan(campaign)
            next_version = max(int(video.get("plan_version") or 0) + 1, int(plan.get("version") or 1))
            plan["version"] = next_version
            video.update({
                "script": plan["script"],
                "duration_target": plan["output"]["duration_seconds"],
                "cta": plan["cta"],
                "status": "等待生产",
                "production_plan": plan,
                "plan_version": next_version,
                "plan_source": "local_autonomy_qc_rework",
                "shot_tasks": list(plan["storyboard"]),
                "target_platforms": list(plan["target_platforms"]),
                "technical_qc": None,
                "bottleneck": "本地自治QC要求自动返工",
                "auto_action": f"已根据QC原因自动生成第{attempts}次返工方案并重新进入本地生产队列。",
            })
            campaign["status"] = "视频生产中"

    _event(data, video, "local_autonomous_content_qc", result)
    cf._save(data)
    return result


def recover_video(video_id: str) -> dict | None:
    data = cf._load()
    video = next((x for x in data.get("videos", []) if x.get("id") == video_id), None)
    if not video or video.get("status") not in {"等待ChatGPT质检", "异常待处理"}:
        return None
    campaign = _campaign(data, video)
    if not mission_allows_local_content(campaign):
        return None
    candidate = _latest_candidate(video)
    if not candidate:
        return None

    if video.get("status") == "异常待处理":
        handoff = video.get("chatgpt_handoff") if isinstance(video.get("chatgpt_handoff"), dict) else {}
        text = " ".join([
            str(handoff.get("kind") or ""), str(handoff.get("phase") or ""),
            str(video.get("bottleneck") or ""), str(video.get("last_error") or ""),
        ])
        if "content_qc" not in text and "ChatGPT" not in text and "质检" not in text and "QC" not in text:
            return None

    result = _apply(video, campaign, candidate, data)
    return {"video_id": video.get("id"), "status": video.get("status"), "local_qc": result}


def recover_authorized_qc(limit: int = 10) -> dict:
    data = cf._load()
    ids = []
    for video in data.get("videos", []):
        if video.get("status") not in {"等待ChatGPT质检", "异常待处理"}:
            continue
        campaign = _campaign(data, video)
        if mission_allows_local_content(campaign):
            ids.append(video.get("id"))
    items = []
    for video_id in ids[:max(1, int(limit or 10))]:
        try:
            item = recover_video(video_id)
            if item:
                items.append(item)
        except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
            items.append({"video_id": video_id, "status": "failed", "error": str(error)[:300]})
    return {"processed": len(items), "items": items}


def record_candidate(payload):
    candidate = _ORIGINAL_RECORD_CANDIDATE(payload)
    video_id = str(payload.get("video_id") or "").strip()
    if video_id:
        recover_video(video_id)
    return candidate


def install() -> None:
    global _INSTALLED, _ORIGINAL_RECORD_CANDIDATE
    if _INSTALLED:
        return
    _ORIGINAL_RECORD_CANDIDATE = cf.record_candidate
    cf.record_candidate = record_candidate
    try:
        from backend import server
        server.factory_record_candidate = record_candidate
    except (ImportError, AttributeError):
        pass
    _INSTALLED = True


install()
