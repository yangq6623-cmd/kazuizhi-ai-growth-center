"""R8-19 GEO Phase 1 external validation executor.

This executor is intentionally narrow: it can produce B-level GEO evidence only
when the configured *cloud* model route is the official OpenAI Responses API and
a hosted web_search call is actually present in the response. It never uses the
local model as evidence and it does not claim to reproduce the ChatGPT consumer
UI. ChatGPT remains the controller that created the Mission/Decision/Command.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from core import geo_validation as geo
from integrations import ai_gateway

EXECUTOR_ID = "openai_responses_web_search"
PROVIDER = "openai_web_search"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024


def _official_responses_endpoint(value: str) -> str:
    raw = str(value or "").strip()
    parsed = urllib.parse.urlsplit(raw)
    if parsed.scheme.lower() != "https" or (parsed.hostname or "").lower() != "api.openai.com":
        raise ValueError("GEO B级验证仅允许官方 OpenAI HTTPS Responses API")
    path = (parsed.path or "").rstrip("/")
    if path != "/v1/responses":
        raise ValueError("GEO B级验证要求 OpenAI /v1/responses 端点")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("OpenAI Responses API 地址不能包含账号、查询参数或片段")
    return "https://api.openai.com/v1/responses"


def status() -> dict:
    route = ai_gateway._route_status("cloud")
    profile = ai_gateway._profile("cloud")
    key, source = ai_gateway._api_key("cloud")
    model = str(profile.get("model") or "").strip()
    endpoint = str(profile.get("endpoint") or "").strip()
    endpoint_valid = False
    endpoint_error = ""
    try:
        _official_responses_endpoint(endpoint)
        endpoint_valid = True
    except ValueError as error:
        endpoint_error = str(error)
    configured = bool(route.get("configured") and key and model and endpoint_valid)
    verified = bool(configured and route.get("verified"))
    reason = ""
    if not key:
        reason = "OpenAI 云端 API 密钥未配置"
    elif not model:
        reason = "OpenAI 云端模型未配置"
    elif not endpoint_valid:
        reason = endpoint_error
    elif not route.get("verified"):
        reason = "OpenAI 云端模型已配置但尚未通过连接验证"
    return {
        "id": EXECUTOR_ID,
        "provider": PROVIDER,
        "test_method": "api",
        "evidence_level": "B",
        "configured": configured,
        "verified": verified,
        "ready": bool(configured and verified),
        "model": model,
        "endpoint": endpoint if endpoint_valid else "",
        "credential_source": source,
        "reason": reason,
        "truth_rule": (
            "只有官方 OpenAI Responses API 真正执行 web_search 并返回 response_id 后才可写入 B 级 GEO 证据；"
            "普通云模型回答、本地模型回答和未联网回答都不计入正式 GEO。"
        ),
    }


def _extract_response(payload: dict) -> tuple[str, list[str], bool]:
    texts: list[str] = []
    urls: list[str] = []
    web_search_used = False
    for item in payload.get("output", []) if isinstance(payload, dict) else []:
        if not isinstance(item, dict):
            continue
        if item.get("type") == "web_search_call":
            web_search_used = True
        if item.get("type") != "message":
            continue
        for content in item.get("content", []) if isinstance(item.get("content"), list) else []:
            if not isinstance(content, dict):
                continue
            if content.get("type") in {"output_text", "text"}:
                text = content.get("text")
                if isinstance(text, str) and text.strip():
                    texts.append(text.strip())
            for annotation in content.get("annotations", []) if isinstance(content.get("annotations"), list) else []:
                if not isinstance(annotation, dict) or annotation.get("type") != "url_citation":
                    continue
                url = annotation.get("url")
                if not url and isinstance(annotation.get("url_citation"), dict):
                    url = annotation["url_citation"].get("url")
                value = str(url or "").strip()
                if value and value not in urls:
                    urls.append(value)
    direct = payload.get("output_text") if isinstance(payload, dict) else None
    if isinstance(direct, str) and direct.strip() and direct.strip() not in texts:
        texts.append(direct.strip())
    return "\n".join(texts).strip(), urls, web_search_used


def _request(question: str) -> dict:
    current = status()
    if not current.get("ready"):
        raise PermissionError(current.get("reason") or "OpenAI GEO 验证执行器未就绪")
    profile = ai_gateway._profile("cloud")
    api_key, _ = ai_gateway._api_key("cloud")
    endpoint = _official_responses_endpoint(profile.get("endpoint"))
    body = {
        "model": current["model"],
        "input": (
            "请先搜索公开互联网，再像正常用户问答一样直接回答下面的问题。"
            "只使用你实际检索到或能够明确说明的不确定信息，不要因为这是评测而偏向任何品牌。\n\n"
            + str(question or "").strip()
        ),
        "tools": [{"type": "web_search"}],
        "tool_choice": "required",
        "max_output_tokens": 1600,
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
            "User-Agent": "Kazuizhi-R8-19-GEO/1.0",
        },
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:  # nosec B310 - endpoint is strictly pinned above
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise RuntimeError("OpenAI GEO 验证响应超过安全大小限制")
        payload = json.loads(raw.decode("utf-8") or "{}")
    except urllib.error.HTTPError as error:
        detail = error.read(64 * 1024).decode("utf-8", errors="replace")[:800]
        if int(error.code) in {401, 403}:
            raise PermissionError(f"OpenAI GEO 验证授权失败 HTTP {error.code}: {detail}") from error
        raise RuntimeError(f"OpenAI GEO 验证 HTTP {error.code}: {detail}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"OpenAI GEO 验证网络不可达: {error.reason}") from error
    except (ValueError, json.JSONDecodeError) as error:
        raise RuntimeError("OpenAI GEO 验证返回非有效 JSON") from error

    answer, citations, web_search_used = _extract_response(payload)
    response_id = str(payload.get("id") or "").strip()
    if not response_id or not answer:
        raise RuntimeError("OpenAI GEO 验证未返回可审计的 response_id 或文本答案")
    if not web_search_used:
        raise RuntimeError("OpenAI 本次回答未执行 web_search，不能计入正式 GEO")
    return {
        "response_id": response_id,
        "raw_answer": answer,
        "citation_urls": citations,
        "web_search_verified": True,
        "model": str(payload.get("model") or current["model"]),
    }


def run_once() -> dict:
    current = status()
    claim = geo.claim_next_task(
        {
            "real_external": True,
            "authorization_ready": bool(current.get("configured")),
            "provider_ready": bool(current.get("ready")),
            "provider": PROVIDER,
            "test_method": "api",
            "executor_id": EXECUTOR_ID,
            "reason": current.get("reason") or "",
        }
    )
    if claim.get("skipped"):
        return {"ok": True, "skipped": True, "reason": claim.get("reason"), "executor": current}
    task = claim.get("task") or {}
    if task.get("state") != "running":
        return {"ok": False, "task": task, "executor": current}

    try:
        answer = _request(task.get("question_text") or "")
        receipt = geo.record_result(
            {
                "task_id": task["task_id"],
                "provider": PROVIDER,
                "model": answer.get("model"),
                "model_version": answer.get("model"),
                "test_method": "api",
                "raw_answer": answer["raw_answer"],
                "citation_urls": answer.get("citation_urls") or [],
                "response_id": answer["response_id"],
                "evidence_ref": f"openai-response:{answer['response_id']}",
                "web_search_verified": True,
                "evidence_level": "B",
            }
        )
        return {"ok": True, "task_id": task["task_id"], "receipt": receipt, "executor": current}
    except PermissionError as error:
        task = geo._transition(task["task_id"], "authorization_required", str(error))
        return {"ok": False, "task": task, "executor": status(), "error": str(error)}
    except (OSError, RuntimeError, ValueError, TypeError, KeyError) as error:
        task = geo.fail_task(task["task_id"], str(error))
        return {"ok": False, "task": task, "executor": current, "error": str(error)}
