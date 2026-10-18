"""GEO additive job/context patch for the existing R7 employee engine.

The patch preserves old job semantics and stores a small allow-listed context
on GEO growth jobs. A context may come from formal A/B Evidence or from a
truth-labelled C-level operating Signal; the employee output must never upgrade
that source grade. Existing job types continue through the original executor.
"""
from __future__ import annotations

from copy import deepcopy

from core import r7_engine
from core.storage import now_iso, write_json

_ORIGINAL_CREATE_JOB = r7_engine.create_job
_ORIGINAL_EXECUTE_AUTONOMOUS = r7_engine.execute_autonomous
_ALLOWED_CONTEXT = {"region", "service", "keyword", "audience", "evidence", "geo_gap_code", "geo_question_id"}


def _clean_context(value):
    if not isinstance(value, dict):
        return {}
    cleaned = {}
    for key in _ALLOWED_CONTEXT:
        raw = value.get(key)
        if raw is None:
            continue
        text = str(raw).strip()
        if text:
            cleaned[key] = text[:500 if key == "evidence" else 160]
    return cleaned


def create_job(payload):
    payload = dict(payload or {})
    context = _clean_context(payload.get("context"))
    schedule_source = str(payload.get("schedule_source") or "").strip()[:80]
    source_ref = str(payload.get("source_ref") or "").strip()[:160]
    mission_id = str(payload.get("mission_id") or "").strip()[:160]
    command_id = str(payload.get("command_id") or "").strip()[:160]
    job = _ORIGINAL_CREATE_JOB(payload)
    if not any((context, schedule_source, source_ref, mission_id, command_id)):
        return job
    with r7_engine.LOCK:
        data = r7_engine._store()
        stored = r7_engine._find(data, job["id"])
        if context:
            stored["context"] = deepcopy(context)
        if schedule_source:
            stored["schedule_source"] = schedule_source
        if source_ref:
            stored["source_ref"] = source_ref
        if mission_id:
            stored["mission_id"] = mission_id
        if command_id:
            stored["command_id"] = command_id
            stored["authorization_state"] = "authorized"
            stored["authorization_note"] = "GEO任务已绑定已验证 ChatGPT Command。"
        stored["updated_at"] = now_iso()
        write_json(r7_engine.JOBS, data)
        r7_engine._audit("job_context_bound", job["id"], "geo_growth", {
            "schedule_source": schedule_source,
            "source_ref": source_ref,
            "has_context": bool(context),
            "command_bound": bool(command_id),
        })
        job = deepcopy(stored)
    return job


def execute_autonomous(job):
    context = _clean_context((job or {}).get("context"))
    task_type = str((job or {}).get("task_type") or "")
    if not context or task_type not in {"seo", "geo", "content", "video"}:
        return _ORIGINAL_EXECUTE_AUTONOMOUS(job)

    from promotion.content_center import generate_ad, generate_geo, generate_seo, generate_video

    payload = {
        "region": context.get("region") or "涟水县",
        "service": context.get("service") or "综合维修",
        "keyword": context.get("keyword") or "涟水县本地维修服务",
        "audience": context.get("audience") or "涟水县有本地服务需求的用户",
        "evidence": context.get("evidence") or "",
    }
    if task_type == "seo":
        record = generate_seo(payload)
    elif task_type == "geo":
        record = generate_geo(payload)
    elif task_type == "video":
        record = generate_video(payload)
    else:
        record = generate_ad(payload)
    return {
        "task_type": task_type,
        "summary": f"{record.get('kind', 'GEO优化草稿')}已按当前GEO缺口生成并保存。",
        "draft_id": record.get("id"),
        "kind": record.get("kind"),
        "geo_gap_code": context.get("geo_gap_code"),
        "geo_question_id": context.get("geo_question_id"),
        "keyword": payload["keyword"],
        "next_actions": ["进入SEO/GEO自治流水线生成公开页", "取得真实发布回执后再执行GEO复测"],
        "source_note": "输入来自带证据等级标记的GEO缺口信号；具体等级以任务context evidence为准。本地内容生成不会升级原始证据等级，也不代表发布、收录或AI推荐成功。",
    }


r7_engine.create_job = create_job
r7_engine.execute_autonomous = execute_autonomous
