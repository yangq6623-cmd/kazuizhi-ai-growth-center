"""Final safety/state refinements for the R8 V2 content factory.

This layer closes the small gap between FFmpeg technical completion and optional
local post-processing. A worker-created FINAL.mp4 stays in a local finalizing
state until subtitles/TTS have finished and a second technical QC passes. It
also enforces the per-account daily publication cap before a plan is created.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from core.storage import now_iso
from promotion import content_factory as cf
from promotion import platform_rules


_INSTALLED = False
_ORIGINAL = {}


def _is_worker_final(payload):
    path = Path(str(payload.get("local_path") or ""))
    notes = str(payload.get("quality_notes") or "")
    return path.name.upper() == "FINAL.MP4" and "ChatGPT生产合同" in notes


def record_candidate(payload):
    if not _is_worker_final(payload):
        return _ORIGINAL["record_candidate"](payload)

    # Create the worker candidate directly in a non-reviewable finalizing state.
    # This avoids a millisecond-scale race where an HTTP poll could otherwise see
    # "等待ChatGPT质检" before subtitles/TTS and the second technical QC finish.
    data = cf._load()
    video = cf._by_id(data.get("videos", []), cf._clean(payload.get("video_id"), "视频ID", 64), "视频任务")
    local_path = cf._clean(payload.get("local_path"), "成片路径", 500)
    candidate = {
        "id": cf._id("CUT"), "created_at": now_iso(), "local_path": local_path,
        "exists": Path(local_path).is_file(), "duration_seconds": payload.get("duration_seconds"),
        "quality_notes": cf._clean(payload.get("quality_notes"), "质检说明", 800, False),
        "ai_score": payload.get("ai_score"),
        "technical_qc": payload.get("technical_qc") if isinstance(payload.get("technical_qc"), dict) else {},
        "source_summary": payload.get("source_summary") if isinstance(payload.get("source_summary"), list) else [],
        "enhancements": {},
    }
    video.setdefault("candidates", []).append(candidate)
    video["technical_qc"] = candidate["technical_qc"]
    if candidate["exists"] and candidate["technical_qc"].get("passed"):
        video["status"] = "后期增强中"
        video["bottleneck"] = "正在完成字幕、可选本地配音与第二次技术质检"
        video["auto_action"] = "本地执行器完成后自动进入ChatGPT成片质检，无需人工操作"
        video["chatgpt_qc"] = {"status": "not_requested_yet", "candidate_id": candidate.get("id")}
    else:
        video["status"] = "异常待处理"
        video["bottleneck"] = "FINAL.MP4初次技术质检未通过"
        video["auto_action"] = "本地执行器将进入自动重试/安全降级，不进入内容审核"
    events = data.setdefault("events", [])
    events.append({
        "id": cf._id("EVT"), "created_at": now_iso(), "kind": "final_candidate_created",
        "video_id": video.get("id"), "campaign_id": video.get("campaign_id"),
        "detail": {
            "candidate_id": candidate.get("id"),
            "technical_qc_passed": bool(candidate["technical_qc"].get("passed")),
            "state": video.get("status"),
        },
    })
    data["events"] = events[-1000:]
    cf._save(data)
    return candidate


def finish_enhancements(video_id, candidate_id, enhancements, technical_qc, source_summary=None):
    data = cf._load()
    video = cf._by_id(data.get("videos", []), str(video_id or ""), "视频任务")
    candidate = cf._by_id(video.get("candidates", []), str(candidate_id or ""), "成片候选")
    candidate["enhancements"] = enhancements if isinstance(enhancements, dict) else {}
    candidate["technical_qc"] = technical_qc if isinstance(technical_qc, dict) else {}
    if isinstance(source_summary, list):
        candidate["source_summary"] = source_summary
    video["technical_qc"] = candidate["technical_qc"]
    if candidate["technical_qc"].get("passed"):
        video["status"] = "等待ChatGPT质检"
        video["bottleneck"] = "等待ChatGPT执行成片内容质检"
        video["auto_action"] = "自动回传FINAL.MP4/预览、技术质检和素材来源；通过后只等待老板最终审核"
        video["chatgpt_qc"] = {
            "status": "pending", "candidate_id": candidate.get("id"),
            "requested_at": now_iso(), "plan_version": video.get("plan_version") or 0,
        }
    else:
        video["status"] = "异常待处理"
        video["bottleneck"] = "后期增强后的第二次技术质检未通过"
        video["auto_action"] = "本地执行器按重试/安全降级策略重新生产，不进入内容审核"
        video["last_error"] = str(candidate["technical_qc"].get("error") or "second-pass QC failed")[:1000]
    events = data.setdefault("events", [])
    events.append({
        "id": cf._id("EVT"), "created_at": now_iso(), "kind": "post_processing_finished",
        "video_id": video.get("id"), "campaign_id": video.get("campaign_id"),
        "detail": {
            "candidate_id": candidate.get("id"),
            "technical_qc_passed": bool(candidate["technical_qc"].get("passed")),
            "subtitle": (candidate.get("enhancements") or {}).get("subtitle"),
            "tts_status": ((candidate.get("enhancements") or {}).get("tts") or {}).get("status"),
            "whisper_status": ((candidate.get("enhancements") or {}).get("whisper_qc") or {}).get("status"),
        },
    })
    data["events"] = events[-1000:]
    cf._save(data)
    return candidate, video


def _today_key():
    return datetime.now().astimezone().date().isoformat()


def create_publish_plan(payload):
    data = cf._load()
    account_id = cf._clean(payload.get("account_id"), "账号ID", 64)
    video_id = cf._clean(payload.get("video_id"), "视频ID", 64)
    account = cf._by_id(data.get("accounts", []), account_id, "账号")
    platform = str(account.get("platform") or "通用")
    internal = platform_rules.INTERNAL_CAPS.get(platform, platform_rules.INTERNAL_CAPS["通用"])
    cap = min(max(1, int(account.get("daily_limit") or 1)), int(internal.get("daily_publish") or 1))
    today = _today_key()
    active_status = {"等待最佳时间", "发布执行中", "已验证发布"}
    today_plans = [
        plan for plan in data.get("publication_plans", [])
        if plan.get("account_id") == account_id
        and str(plan.get("created_at") or "")[:10] == today
        and plan.get("status") in active_status
    ]
    if len(today_plans) >= cap:
        raise ValueError(f"发布前硬规则未通过：该账号今天已达到内部发布上限 {cap} 条")
    duplicate = next((
        plan for plan in data.get("publication_plans", [])
        if plan.get("account_id") == account_id and plan.get("video_id") == video_id
        and plan.get("status") in active_status
    ), None)
    if duplicate:
        raise ValueError("发布前硬规则未通过：同一视频已为该账号建立有效发布计划，禁止重复排期")
    result = _ORIGINAL["create_publish_plan"](payload)
    data = cf._load()
    current = cf._by_id(data.get("publication_plans", []), result.get("id"), "发布计划")
    current["daily_cap"] = {"limit": cap, "used_before_this_plan": len(today_plans), "date": today}
    cf._save(data)
    return current


def install():
    global _INSTALLED
    if _INSTALLED:
        return
    _ORIGINAL["record_candidate"] = cf.record_candidate
    _ORIGINAL["create_publish_plan"] = cf.create_publish_plan
    cf.record_candidate = record_candidate
    cf.create_publish_plan = create_publish_plan
    cf.finish_local_enhancements = finish_enhancements
    try:
        from backend import server
        server.factory_record_candidate = record_candidate
        server.factory_create_publish_plan = create_publish_plan
    except (ImportError, AttributeError):
        pass
    _INSTALLED = True


install()
