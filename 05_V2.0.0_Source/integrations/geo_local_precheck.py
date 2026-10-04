"""Local-model GEO precheck.

This module deliberately produces C-level auxiliary analysis only. It never
changes the official GEO 50-question score and never writes A/B Evidence.
"""
from __future__ import annotations

import json
import re
import socket
import urllib.parse

from core import geo_validation as geo
from core.storage import now_iso, read_json, write_json
from integrations import ai_gateway

PRECHECK_PATH = "geo_validation/local_precheck.json"


def _local_service_available(endpoint):
    """Perform a bounded TCP probe before advertising a local model as ready.

    Route verification is persisted so it survives application restarts.  That
    historical result is useful, but it is not proof that the local Router is
    still running now.  GEO precheck must therefore fail closed when its local
    endpoint is offline instead of showing a misleading "connected" badge.
    """
    try:
        parsed = urllib.parse.urlsplit(str(endpoint or ""))
        host = parsed.hostname
        if not host:
            return False
        port = parsed.port or (443 if parsed.scheme == "https" else 80)
        with socket.create_connection((host, port), timeout=0.35):
            return True
    except (OSError, ValueError):
        return False


def _load():
    value = read_json(PRECHECK_PATH, {"results": []})
    return value if isinstance(value, dict) else {"results": []}


def _save(value):
    value["updated_at"] = now_iso()
    return write_json(PRECHECK_PATH, value)


def status():
    route = ai_gateway._route_status("local")
    endpoint = str(route.get("endpoint") or "")
    configured = bool(route.get("configured"))
    previously_verified = bool(route.get("verified"))
    reachable = bool(configured and _local_service_available(endpoint))
    results = _load().get("results") or []
    tested = {item.get("question_id") for item in results if item.get("question_id")}
    total = len(geo.question_set().get("questions") or [])
    return {
        "id": "local_geo_precheck",
        "mode": "local_precheck",
        "configured": configured,
        "verified": bool(previously_verified and reachable),
        "ready": bool(configured and previously_verified and reachable),
        "provider": route.get("provider") or "local_model",
        "model": route.get("model") or "",
        "endpoint": endpoint,
        "tested": len(tested),
        "remaining": max(0, total - len(tested)),
        "total": total,
        "evidence_level": "C",
        "official_truth": False,
        "reason": route.get("last_error") or (
            "本地模型已验证" if previously_verified and reachable
            else "本地模型服务未运行或端口不可达，请启动本地 Router 后重试" if configured
            else "本地模型尚未完成连接验证"
        ),
        "truth_rule": "本地模型只做GEO预检、分类和缺口分析；结果固定为C级辅助，不计入正式GEO 50问成绩。",
    }


def _parse_json_text(text):
    value = str(text or "").strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*", "", value, flags=re.I)
        value = re.sub(r"\s*```$", "", value)
    parsed = json.loads(value)
    if not isinstance(parsed, dict):
        raise ValueError("local_geo_precheck_requires_json_object")
    return parsed


def _next_questions(limit=1, question_ids=None):
    questions = geo.question_set().get("questions") or []
    qmap = {item.get("question_id"): item for item in questions}
    if question_ids:
        selected = []
        for qid in question_ids:
            if qid not in qmap:
                raise ValueError(f"unknown_geo_question_id:{qid}")
            selected.append(qmap[qid])
        return selected[: max(1, min(int(limit or 1), 10))]
    existing = {item.get("question_id") for item in _load().get("results") or []}
    pending = [item for item in questions if item.get("question_id") not in existing]
    return pending[: max(1, min(int(limit or 1), 10))]


def run(limit=1, question_ids=None):
    current = status()
    if not current.get("ready"):
        raise PermissionError(current.get("reason") or "local_geo_precheck_not_ready")
    profile = ai_gateway._profile("local")
    profile["route"] = "local"
    api_key, _ = ai_gateway._api_key("local")
    model = str(profile.get("model") or current.get("model") or "").strip()
    selected = _next_questions(limit=limit, question_ids=question_ids)
    stored = _load()
    results = stored.setdefault("results", [])
    by_id = {item.get("question_id"): item for item in results}
    completed = []

    for question in selected:
        prompt = (
            "你正在做卡嘴子GEO本地预检。只返回一个JSON对象，不要Markdown。"
            "这是本地辅助分析，不得声称代表ChatGPT、Gemini、Copilot或任何真实外部AI产品。"
            "JSON字段必须包含 answer, likely_visibility, content_gaps, keywords, notes。"
            "likely_visibility只能是 unknown/low/medium/high。content_gaps和keywords必须是数组。\n\n"
            f"QUESTION_ID: {question['question_id']}\nQUESTION: {question['question_text']}"
        )
        payload = {"model": model, "input": prompt, "max_output_tokens": 1400}
        raw = ai_gateway._http_transport(payload, api_key, profile)
        text = ai_gateway._extract_text(raw)
        parsed = _parse_json_text(text)
        item = {
            "precheck_id": f"GEO-PRECHECK-{question['question_id']}",
            "question_id": question["question_id"],
            "question_text": question["question_text"],
            "question_type": question.get("question_type"),
            "service": question.get("service"),
            "provider": current.get("provider") or "local_model",
            "model": model,
            "tested_at": now_iso(),
            "answer": str(parsed.get("answer") or ""),
            "likely_visibility": str(parsed.get("likely_visibility") or "unknown"),
            "content_gaps": parsed.get("content_gaps") if isinstance(parsed.get("content_gaps"), list) else [],
            "keywords": parsed.get("keywords") if isinstance(parsed.get("keywords"), list) else [],
            "notes": str(parsed.get("notes") or ""),
            "evidence_level": "C",
            "official_truth": False,
        }
        by_id[item["question_id"]] = item
        completed.append(item)

    stored["results"] = list(by_id.values())
    _save(stored)
    return {"ok": True, "completed": len(completed), "results": completed, "status": status()}


def results(limit=200):
    items = list(reversed(_load().get("results") or []))
    return items[: max(1, min(int(limit or 200), 500))]
