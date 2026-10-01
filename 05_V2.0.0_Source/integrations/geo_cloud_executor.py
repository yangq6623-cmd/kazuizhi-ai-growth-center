"""R8-19 GEO cloud-model autonomous executor.

This executor consumes the owner's already verified cloud OpenAI-compatible
route and can run the fixed GEO question set without per-question clicks.
A normal cloud-model answer is persisted as C-level auxiliary evidence only.
It is never promoted to formal A/B GEO evidence unless a future provider
adapter can prove a real external web-search operation and its traceable
citations/receipt.
"""
from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request

from core import geo_validation as geo
from integrations import ai_gateway

EXECUTOR_ID = "cloud_openai_compatible_geo_auto"
PROVIDER = "cloud_auto"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024
MAX_ATTEMPTS = 3
TRANSIENT_HTTP = {408, 409, 425, 429, 500, 502, 503, 504}


def _cloud_key():
    """Prefer the key saved for the selected UI profile over a global env key.

    The generic gateway historically lets OPENAI_API_KEY override the saved
    cloud profile. That is unsafe for a Doubao/Ark profile on a machine that
    also happens to have an OpenAI environment variable. GEO autonomy must use
    the credential that belongs to the configured cloud route first.
    """
    profile = ai_gateway._profile("cloud")
    saved = ai_gateway._unprotect_windows(str(profile.get("protected_api_key") or ""))
    if saved:
        return saved, "windows_dpapi"
    return ai_gateway._api_key("cloud")


def _effective_protocol(endpoint, configured):
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
    protocol = _effective_protocol(endpoint, str(profile.get("protocol") or ""))
    ready = bool(route.get("configured") and route.get("verified") and key and endpoint and model)
    reason = ""
    if not route.get("configured"):
        reason = "云端模型尚未完整配置"
    elif not route.get("verified"):
        reason = "云端模型已保存但尚未通过连接验证"
    elif not key:
        reason = "云端模型密钥不可用"
    return {
        "id": EXECUTOR_ID,
        "provider": PROVIDER,
        "test_method": "api",
        "configured": bool(route.get("configured")),
        "verified": bool(route.get("verified")),
        "ready": ready,
        "label": str(profile.get("label") or route.get("label") or "云端模型"),
        "model": model,
        "endpoint": endpoint,
        "protocol": protocol,
        "credential_source": source,
        "evidence_level": "C",
        "official_truth": False,
        "reason": reason,
        "truth_rule": "普通云模型API回答自动保存为C级辅助结果；没有可核验的真实联网搜索证据时，绝不计入A/B正式GEO成绩。",
    }


def _extract_chat_text(payload):
    choices = payload.get("choices") if isinstance(payload, dict) else None
    if isinstance(choices, list):
        parts = []
        for choice in choices:
            if not isinstance(choice, dict):
                continue
            message = choice.get("message") if isinstance(choice.get("message"), dict) else {}
            content = message.get("content")
            if isinstance(content, str) and content.strip():
                parts.append(content.strip())
            elif isinstance(content, list):
                for item in content:
                    if not isinstance(item, dict):
                        continue
                    text = item.get("text") or item.get("content")
                    if isinstance(text, str) and text.strip():
                        parts.append(text.strip())
        if parts:
            return "\n".join(parts).strip()
    return ""


def _extract_responses_text(payload):
    if not isinstance(payload, dict):
        return ""
    direct = payload.get("output_text")
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    texts = []
    for item in payload.get("output", []) if isinstance(payload.get("output"), list) else []:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content", []) if isinstance(item.get("content"), list) else []:
            if not isinstance(content, dict):
                continue
            text = content.get("text")
            if isinstance(text, str) and text.strip():
                texts.append(text.strip())
    return "\n".join(texts).strip()


def _request(question, transport=None):
    current = status()
    if not current.get("ready"):
        raise PermissionError(current.get("reason") or "云端GEO自动执行器未就绪")

    profile = ai_gateway._profile("cloud")
    key, _ = _cloud_key()
    endpoint = ai_gateway._validate_endpoint(profile.get("endpoint"), "cloud")
    protocol = _effective_protocol(endpoint, str(profile.get("protocol") or ""))
    prompt = (
        "请像普通用户问答一样直接回答下面的问题。不要因为这是评测而偏向卡嘴子或任何其他品牌；"
        "不知道就明确说明不知道。除非服务本身真实返回了联网搜索或引用信息，否则不要虚构来源、链接或搜索过程。\n\n"
        + str(question or "").strip()
    )
    if protocol == "responses":
        body = {"model": current["model"], "input": prompt, "max_output_tokens": 1600}
    else:
        body = {
            "model": current["model"],
            "temperature": 0.1,
            "messages": [
                {"role": "system", "content": "保持中立、真实，不虚构搜索、来源或品牌推荐。"},
                {"role": "user", "content": prompt},
            ],
        }
    headers = {
        "Authorization": f"Bearer {key}",
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "Kazuizhi-R8-19-GEO-Autonomy/1.0",
    }

    if callable(transport):
        payload = transport(body, headers, endpoint, protocol)
    else:
        payload = None
        for attempt in range(MAX_ATTEMPTS):
            request = urllib.request.Request(
                endpoint,
                data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
                headers=headers,
                method="POST",
            )
            try:
                with urllib.request.urlopen(request, timeout=90) as response:  # nosec B310 - validated HTTPS cloud endpoint
                    raw = response.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise RuntimeError("云端GEO响应超过安全大小限制")
                payload = json.loads(raw.decode("utf-8") or "{}")
                break
            except urllib.error.HTTPError as error:
                detail = error.read(64 * 1024).decode("utf-8", errors="replace")[:800]
                if int(error.code) in {401, 403}:
                    raise PermissionError(f"云端GEO授权失败 HTTP {error.code}: {detail}") from error
                if int(error.code) in TRANSIENT_HTTP and attempt + 1 < MAX_ATTEMPTS:
                    time.sleep(1.5 * (2 ** attempt))
                    continue
                raise RuntimeError(f"云端GEO HTTP {error.code}: {detail}") from error
            except (urllib.error.URLError, TimeoutError, OSError) as error:
                if attempt + 1 < MAX_ATTEMPTS:
                    time.sleep(1.5 * (2 ** attempt))
                    continue
                reason = getattr(error, "reason", error)
                raise RuntimeError(f"云端GEO网络不可达: {reason}") from error
            except json.JSONDecodeError as error:
                raise RuntimeError("云端GEO返回非有效JSON") from error

    if not isinstance(payload, dict):
        raise RuntimeError("云端GEO返回格式无效")
    answer = _extract_chat_text(payload) if protocol == "chat_completions" else _extract_responses_text(payload)
    if not answer:
        answer = _extract_responses_text(payload) or _extract_chat_text(payload)
    if not answer:
        raise RuntimeError("云端GEO未返回可保存的文本答案")
    return {
        "raw_answer": answer,
        "response_id": str(payload.get("id") or "").strip(),
        "model": str(payload.get("model") or current["model"]),
        "citation_urls": [],
        "web_search_verified": False,
        "protocol": protocol,
    }


def run_once(transport=None):
    current = status()
    queue = geo.queue_summary().get("tasks") or []
    first_queued = next((item for item in queue if item.get("state") == "queued"), None)
    if first_queued is None:
        return {"ok": True, "skipped": True, "reason": "queue_empty", "executor": current}
    if first_queued.get("provider") != PROVIDER:
        return {
            "ok": True,
            "skipped": True,
            "reason": "non_cloud_geo_task_precedes_autonomous_queue",
            "blocking_task_id": first_queued.get("task_id"),
            "executor": current,
        }

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
        return {"ok": False, "task": task, "executor": current, "error": task.get("authorization_reason") or task.get("failure_reason")}

    try:
        answer = _request(task.get("question_text") or "", transport=transport)
        receipt = geo.record_result(
            {
                "task_id": task["task_id"],
                "provider": PROVIDER,
                "model": answer.get("model"),
                "model_version": answer.get("model"),
                "test_method": "api",
                "raw_answer": answer["raw_answer"],
                "citation_urls": answer.get("citation_urls") or [],
                "response_id": answer.get("response_id") or "",
                "evidence_ref": f"cloud-response:{answer['response_id']}" if answer.get("response_id") else "",
                "web_search_verified": False,
                "evidence_level": "C",
                "analysis": {"cloud_protocol": answer.get("protocol"), "autonomous": True},
            }
        )
        return {"ok": True, "task_id": task["task_id"], "receipt": receipt, "executor": current}
    except PermissionError as error:
        task = geo._transition(task["task_id"], "authorization_required", str(error))
        return {"ok": False, "task": task, "executor": status(), "error": str(error)}
    except (OSError, RuntimeError, ValueError, TypeError, KeyError) as error:
        task = geo.fail_task(task["task_id"], str(error))
        return {"ok": False, "task": task, "executor": current, "error": str(error)}
