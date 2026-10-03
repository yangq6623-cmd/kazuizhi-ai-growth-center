"""R8-23.2 real model collaboration for SEO/GEO.

This is an execution assistant, not an evidence source.  It uses the owner's
verified cloud OpenAI-compatible profile (Doubao/Ark in the current deployment)
for selected high-value SEO/GEO analysis and semantic QC.  Every result is
persisted as C-level auxiliary advice and can be consumed by the controller or
subsequent content work, but it never promotes publish/search/GEO truth states.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from copy import deepcopy
from datetime import datetime, timedelta

from core.storage import now_iso, read_json, write_json
from integrations import ai_gateway

STORE = "integrations/seo_geo_model_collaboration.json"
SCHEMA = "kazuizhi.r8_23_2.seo_geo_model_collaboration.v1"
MAX_RESPONSE_BYTES = 1024 * 1024
MIN_STAGE_INTERVAL_MINUTES = 30
MAX_STAGE_CALLS_PER_CYCLE = 2
TRANSIENT_HTTP = {408, 409, 425, 429, 500, 502, 503, 504}

REQUIRED_STAGES = {
    "seo_search_intent": "复核高价值SEO关键词的真实搜索意图、服务意图和页面类型，给出优先级建议。",
    "seo_semantic_qc": "对已生成或待发布SEO内容做语义质量检查，检查意图覆盖、重复、事实边界、FAQ价值和可读性。",
    "geo_gap_analysis": "分析正式GEO问题/缺口，识别为什么外部AI可能没有提及卡嘴子，并给出可验证的事实型内容补强建议。",
    "geo_content_optimization": "根据GEO缺口提出官网事实页、FAQ、服务区域、结构化信息的优化建议，但不得虚构引用、排名或外部验证。",
}


def _default():
    return {"schema": SCHEMA, "stage_state": {}, "receipts": [], "updated_at": now_iso()}


def _load():
    data = read_json(STORE, _default())
    if not isinstance(data, dict):
        data = _default()
    data.setdefault("stage_state", {})
    data.setdefault("receipts", [])
    return data


def _save(data):
    data["schema"] = SCHEMA
    data["receipts"] = (data.get("receipts") or [])[-200:]
    data["updated_at"] = now_iso()
    write_json(STORE, data)
    return data


def _dt(value):
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        return parsed.astimezone() if parsed.tzinfo else parsed.astimezone()
    except (TypeError, ValueError):
        return None


def _cloud_key():
    # Prefer the DPAPI-protected key attached to the selected cloud profile.
    profile = ai_gateway._profile("cloud")
    saved = ai_gateway._unprotect_windows(str(profile.get("protected_api_key") or ""))
    if saved:
        return saved, "windows_dpapi"
    return ai_gateway._api_key("cloud")


def _protocol(endpoint, configured):
    path = urllib.parse.urlsplit(str(endpoint or "")).path.rstrip("/").lower()
    if path.endswith("/chat/completions"):
        return "chat_completions"
    if path.endswith("/responses"):
        return "responses"
    return configured if configured in {"chat_completions", "responses"} else "chat_completions"


def status():
    route = ai_gateway._route_status("cloud")
    profile = ai_gateway._profile("cloud")
    key, source = _cloud_key()
    endpoint = str(profile.get("endpoint") or "").strip()
    model = str(profile.get("model") or "").strip()
    ready = bool(route.get("configured") and route.get("verified") and key and endpoint and model)
    data = _load()
    return {
        "ready": ready,
        "configured": bool(route.get("configured")),
        "verified": bool(route.get("verified")),
        "provider": route.get("provider"),
        "label": profile.get("label") or route.get("label") or "云端模型",
        "model": model,
        "endpoint": endpoint,
        "credential_source": source,
        "required_stages": sorted(REQUIRED_STAGES),
        "last_by_stage": deepcopy(data.get("stage_state") or {}),
        "receipt_count": len(data.get("receipts") or []),
        "evidence_level": "C_auxiliary",
        "truth_rule": "豆包在SEO/GEO关键节点真实参与分析/QC，但普通API输出不构成发布、收录、排名或正式GEO A/B Evidence。",
    }


def _extract(payload, protocol):
    if not isinstance(payload, dict):
        return ""
    if protocol == "responses":
        direct = payload.get("output_text")
        if isinstance(direct, str) and direct.strip():
            return direct.strip()
        rows = []
        for item in payload.get("output", []) if isinstance(payload.get("output"), list) else []:
            if not isinstance(item, dict):
                continue
            for content in item.get("content", []) if isinstance(item.get("content"), list) else []:
                if isinstance(content, dict) and isinstance(content.get("text"), str):
                    rows.append(content["text"].strip())
        return "\n".join(x for x in rows if x)
    choices = payload.get("choices") if isinstance(payload.get("choices"), list) else []
    rows = []
    for choice in choices:
        if not isinstance(choice, dict):
            continue
        message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
        content = message.get("content")
        if isinstance(content, str) and content.strip():
            rows.append(content.strip())
    return "\n".join(rows)


def _request(stage, context, transport=None):
    current = status()
    if not current.get("ready"):
        raise PermissionError("豆包/云模型尚未通过真实连接验证")
    profile = ai_gateway._profile("cloud")
    key, _ = _cloud_key()
    endpoint = ai_gateway._validate_endpoint(profile.get("endpoint"), "cloud")
    protocol = _protocol(endpoint, str(profile.get("protocol") or ""))
    task = REQUIRED_STAGES[stage]
    safe_context = json.dumps(context, ensure_ascii=False, separators=(",", ":"))[:18000]
    prompt = (
        "你是卡嘴子本地维修综合服务平台的SEO/GEO执行协作模型。"
        "只依据给出的真实上下文分析，不得虚构排名、收录、搜索、引用、用户、订单或外部证据。"
        "输出精简JSON对象，字段为 summary, findings, actions, quality_score, risks。"
        f"\n任务：{task}\n阶段：{stage}\n真实上下文：{safe_context}"
    )
    if protocol == "responses":
        body = {"model": current["model"], "input": prompt, "max_output_tokens": 1800}
    else:
        body = {
            "model": current["model"], "temperature": 0.1,
            "messages": [
                {"role": "system", "content": "只做SEO/GEO辅助分析；不虚构事实或外部证据；优先返回JSON。"},
                {"role": "user", "content": prompt},
            ],
        }
    headers = {"Authorization": f"Bearer {key}", "Content-Type": "application/json", "Accept": "application/json", "User-Agent": "Kazuizhi-R8-23.2-SEO-GEO-Collaboration/1.0"}
    if callable(transport):
        payload = transport(body, headers, endpoint, protocol)
    else:
        payload = None
        for attempt in range(3):
            request = urllib.request.Request(endpoint, data=json.dumps(body, ensure_ascii=False).encode("utf-8"), headers=headers, method="POST")
            try:
                with urllib.request.urlopen(request, timeout=90) as response:  # nosec B310 - validated HTTPS route
                    raw = response.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise RuntimeError("豆包SEO/GEO响应超过安全大小限制")
                payload = json.loads(raw.decode("utf-8") or "{}")
                break
            except urllib.error.HTTPError as error:
                detail = error.read(64 * 1024).decode("utf-8", errors="replace")[:800]
                if int(error.code) in {401, 403}:
                    raise PermissionError(f"豆包SEO/GEO授权失败 HTTP {error.code}: {detail}") from error
                if int(error.code) in TRANSIENT_HTTP and attempt < 2:
                    time.sleep(1.5 * (2 ** attempt)); continue
                raise RuntimeError(f"豆包SEO/GEO HTTP {error.code}: {detail}") from error
            except (urllib.error.URLError, TimeoutError, OSError) as error:
                if attempt < 2:
                    time.sleep(1.5 * (2 ** attempt)); continue
                raise RuntimeError(f"豆包SEO/GEO网络不可达: {getattr(error, 'reason', error)}") from error
    text = _extract(payload, protocol)
    if not text:
        raise RuntimeError("豆包SEO/GEO未返回可保存结果")
    parsed = None
    try:
        stripped = text.strip()
        if stripped.startswith("```"):
            stripped = stripped.strip("`")
            if stripped.startswith("json"):
                stripped = stripped[4:].lstrip()
        parsed = json.loads(stripped)
    except (ValueError, json.JSONDecodeError):
        parsed = {"summary": text[:4000], "findings": [], "actions": [], "risks": ["模型未返回标准JSON，已按文本辅助结果保存"]}
    return {"analysis": parsed, "raw_text": text[:12000], "response_id": str(payload.get("id") or "") if isinstance(payload, dict) else "", "model": str(payload.get("model") or current["model"]) if isinstance(payload, dict) else current["model"], "protocol": protocol}


def _due(data, stage, force=False):
    if force:
        return True
    row = (data.get("stage_state") or {}).get(stage) or {}
    last = _dt(row.get("last_success_at") or row.get("last_attempt_at"))
    return not last or datetime.now().astimezone() - last >= timedelta(minutes=MIN_STAGE_INTERVAL_MINUTES)


def _contexts():
    seo = {}
    geo = {}
    try:
        from core.seo_geo_growth import dashboard
        snap = dashboard()
        summary = snap.get("summary") or {}
        seo = {
            "summary": {k: summary.get(k) for k in ("today_opportunities", "planned_assets", "generated_assets", "qc_passed_assets", "public_pages", "submitted_urls", "crawled_urls", "indexed_urls") if k in summary},
            "opportunities": (snap.get("opportunities") or [])[:8],
            "assets": [{k: row.get(k) for k in ("id", "title", "stage", "description", "canonical")} for row in (snap.get("assets") or [])[:8] if isinstance(row, dict)],
        }
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError):
        pass
    try:
        from core import geo_analysis, geo_validation
        analysis = geo_analysis.snapshot()
        official = geo_validation.dashboard().get("official") or {}
        geo = {
            "formal": {"tested": official.get("tested"), "target": official.get("target"), "mentioned": official.get("mentioned")},
            "analysis_summary": analysis.get("summary") or {},
        }
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError):
        pass
    return seo, geo


def run_cycle(force=False, transport=None):
    current = status()
    if not current.get("ready"):
        return {"skipped": True, "reason": "doubao_not_verified", "status": current, "results": []}
    data = _load()
    seo, geo = _contexts()
    candidates = []
    if seo.get("opportunities"):
        candidates.append(("seo_search_intent", seo))
    if seo.get("assets"):
        candidates.append(("seo_semantic_qc", seo))
    candidates.append(("geo_gap_analysis", geo))
    candidates.append(("geo_content_optimization", geo))
    selected = [(stage, ctx) for stage, ctx in candidates if _due(data, stage, force=force)][:MAX_STAGE_CALLS_PER_CYCLE]
    if not selected:
        return {"skipped": True, "reason": "stage_throttle", "status": current, "results": []}

    results = []
    for stage, context in selected:
        row = data.setdefault("stage_state", {}).setdefault(stage, {})
        row["last_attempt_at"] = now_iso()
        try:
            answer = _request(stage, context, transport=transport)
            receipt = {
                "receipt_id": f"DOUBAO-AUX-{stage.upper()}-{int(time.time())}",
                "stage": stage, "created_at": now_iso(), "status": "completed",
                "provider": current.get("label"), "model": answer.get("model"),
                "response_id": answer.get("response_id"), "analysis": answer.get("analysis"),
                "evidence_level": "C_auxiliary", "formal_geo": False,
                "truth_rule": "证明豆包真实参与本阶段分析/QC；不证明公网发布、搜索抓取/收录/排名或正式GEO Evidence。",
            }
            data.setdefault("receipts", []).append(receipt)
            row.update(last_success_at=now_iso(), last_error="", last_receipt_id=receipt["receipt_id"], model=answer.get("model"))
            results.append(receipt)
        except (PermissionError, RuntimeError, OSError, ValueError, TypeError, KeyError) as error:
            row.update(last_error=str(error)[:500])
            results.append({"stage": stage, "status": "failed", "error": str(error)[:500], "evidence_level": "C_auxiliary"})
    _save(data)
    return {"skipped": False, "status": status(), "results": results, "completed": sum(x.get("status") == "completed" for x in results), "failed": sum(x.get("status") == "failed" for x in results)}


def receipts(limit=50):
    data = _load()
    return list(reversed(data.get("receipts") or []))[:max(1, min(int(limit or 50), 200))]
