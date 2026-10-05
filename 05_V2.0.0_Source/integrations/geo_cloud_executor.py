"""R8-19 GEO cloud-model autonomous executor.

#644 hardens the unattended GEO cloud loop around the existing truth policy:
- Doubao/cloud API answers are saved automatically as C-level auxiliary evidence;
- every successful answer produces Evidence + Receipt and closes the task;
- the worker can immediately continue to the next question;
- request timeout, three automatic retries, stale-task recovery and
  skip/continue prevent one bad question from blocking the queue.

A normal cloud-model answer is never promoted to formal A/B GEO evidence unless
an external adapter can prove a real web-search operation and traceable sources.
"""
from __future__ import annotations

import json
import queue as queue_module
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

from core import geo_validation as geo
from core.storage import now_iso
from integrations import ai_gateway

EXECUTOR_ID = "cloud_openai_compatible_geo_auto"
PROVIDER = "cloud_auto"
MAX_RESPONSE_BYTES = 2 * 1024 * 1024

# #644 unattended-safety contract.
REQUEST_TIMEOUT_SECONDS = 120
NETWORK_TIMEOUT_SECONDS = 105
STALE_RUNNING_SECONDS = 5 * 60
MAX_AUTO_RETRIES = 3
RETRY_BACKOFF_SECONDS = (5, 15, 45)
TRANSIENT_HTTP = {408, 409, 425, 429, 500, 502, 503, 504}

_LEDGER_LOCK = threading.Lock()


def _cloud_key():
    """Prefer the key saved for the selected UI profile over a global env key."""
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
        "request_timeout_seconds": REQUEST_TIMEOUT_SECONDS,
        "stale_running_seconds": STALE_RUNNING_SECONDS,
        "max_auto_retries": MAX_AUTO_RETRIES,
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


def _parse_iso_epoch(value):
    text = str(value or "").strip()
    if not text:
        return 0.0
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except (TypeError, ValueError, OverflowError):
        return 0.0


def _task_event(task_id, event, **fields):
    """Persist owner-visible execution metadata without changing truth grading."""
    with _LEDGER_LOCK:
        payload = geo._load_queue()
        task = next((item for item in payload.get("tasks") or [] if item.get("task_id") == task_id), None)
        if task is None:
            return {}
        details = dict(fields or {})
        task.update(details)
        task["updated_at"] = now_iso()
        events = list(task.get("execution_events") or [])
        events.append(
            {
                "event": str(event),
                "at": now_iso(),
                "request_id": str(details.get("request_id") or task.get("request_id") or ""),
                "http_status": details.get("http_status", task.get("http_status")),
                "retry_count": int(task.get("retry_count") or 0),
                "error": str(details.get("last_error") or details.get("failure_reason") or "")[:800],
            }
        )
        task["execution_events"] = events[-50:]
        geo._save_queue(payload)
    geo._audit(
        "geo_cloud_execution_event",
        {
            "task_id": task_id,
            "question_id": task.get("question_id") or "",
            "event": str(event),
            "provider": PROVIDER,
            "model": str(task.get("model") or ""),
            "request_id": str(task.get("request_id") or ""),
            "http_status": task.get("http_status"),
            "retry_count": int(task.get("retry_count") or 0),
        },
    )
    return task


def _extract_request_id(payload, headers=None):
    headers = headers or {}
    for name in ("x-request-id", "x-tt-logid", "x-bce-request-id", "request-id"):
        try:
            value = headers.get(name) or headers.get(name.title())
        except AttributeError:
            value = ""
        if value:
            return str(value).strip()
    if isinstance(payload, dict):
        for key in ("id", "request_id", "requestId", "log_id", "logid"):
            value = payload.get(key)
            if value:
                return str(value).strip()
    return ""


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
        "User-Agent": "Kazuizhi-R8-23-GEO-Autonomy/644",
    }

    started = time.perf_counter()
    response_headers = {}
    http_status = 200
    if callable(transport):
        payload = transport(body, headers, endpoint, protocol)
    else:
        request = urllib.request.Request(
            endpoint,
            data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(
                request,
                timeout=NETWORK_TIMEOUT_SECONDS,
            ) as response:  # nosec B310 - validated HTTPS cloud endpoint
                http_status = int(getattr(response, "status", 200) or 200)
                response_headers = getattr(response, "headers", {}) or {}
                raw = response.read(MAX_RESPONSE_BYTES + 1)
            if len(raw) > MAX_RESPONSE_BYTES:
                raise RuntimeError("云端GEO响应超过安全大小限制")
            payload = json.loads(raw.decode("utf-8") or "{}")
        except urllib.error.HTTPError as error:
            detail = error.read(64 * 1024).decode("utf-8", errors="replace")[:800]
            code = int(error.code)
            if code in {401, 403}:
                raise PermissionError(f"云端GEO授权失败 HTTP {code}: {detail}") from error
            if code in TRANSIENT_HTTP:
                raise RuntimeError(f"云端GEO临时HTTP错误 {code}: {detail}") from error
            raise RuntimeError(f"云端GEO HTTP {code}: {detail}") from error
        except (urllib.error.URLError, TimeoutError, OSError) as error:
            reason = getattr(error, "reason", error)
            raise RuntimeError(f"云端GEO网络不可达: {reason}") from error
        except json.JSONDecodeError as error:
            raise RuntimeError("云端GEO返回非有效JSON") from error

    latency_ms = max(0, int((time.perf_counter() - started) * 1000))
    if not isinstance(payload, dict):
        raise RuntimeError("云端GEO返回格式无效")
    answer = _extract_chat_text(payload) if protocol == "chat_completions" else _extract_responses_text(payload)
    if not answer:
        answer = _extract_responses_text(payload) or _extract_chat_text(payload)
    if not answer:
        raise RuntimeError("云端GEO未返回可保存的文本答案")
    response_id = str(payload.get("id") or "").strip()
    return {
        "raw_answer": answer,
        "response_id": response_id,
        "request_id": _extract_request_id(payload, response_headers) or response_id,
        "http_status": http_status,
        "latency_ms": latency_ms,
        "model": str(payload.get("model") or current["model"]),
        "citation_urls": [],
        "web_search_verified": False,
        "protocol": protocol,
    }


def _bounded_request(question, transport=None):
    """Outer watchdog: a provider call can never hold the GEO worker forever."""
    result_queue = queue_module.Queue(maxsize=1)

    def invoke():
        try:
            result_queue.put(("ok", _request(question, transport=transport)))
        except BaseException as error:
            result_queue.put(("error", error))

    thread = threading.Thread(
        target=invoke,
        name="r8-23-geo-provider-request",
        daemon=True,
    )
    thread.start()
    thread.join(REQUEST_TIMEOUT_SECONDS)
    if thread.is_alive():
        raise TimeoutError(f"云端GEO请求超过 {REQUEST_TIMEOUT_SECONDS} 秒，已交给自动重试机制")
    try:
        kind, value = result_queue.get_nowait()
    except queue_module.Empty as error:
        raise RuntimeError("云端GEO请求线程结束但未返回结果") from error
    if kind == "error":
        raise value
    return value


def _eligible_for_retry(task):
    return int(task.get("retry_count") or 0) < MAX_AUTO_RETRIES


def _schedule_auto_retry(task_id, error_text, *, error_code="EXECUTION_FAILED"):
    """Queue up to three retries; after that leave failed and continue onward."""
    queue_payload = geo._load_queue()
    task = next((item for item in queue_payload.get("tasks") or [] if item.get("task_id") == task_id), None)
    if task is None:
        return {"scheduled": False, "reason": "task_not_found", "retry_count": 0}

    task["max_retries"] = MAX_AUTO_RETRIES
    geo._save_queue(queue_payload)
    if not _eligible_for_retry(task):
        _task_event(
            task_id,
            "TERMINAL_FAILED_CONTINUE",
            answer_status="failed",
            last_error=str(error_text)[:800],
            failure_code=error_code,
            finished_at=now_iso(),
            next_retry_at_epoch=0.0,
        )
        return {
            "scheduled": False,
            "reason": "retry_limit_reached",
            "retry_count": int(task.get("retry_count") or 0),
        }

    retried = geo.retry_task(task_id, approved_by=geo.CONTROLLER)
    retry_count = int(retried.get("retry_count") or 0)
    delay = RETRY_BACKOFF_SECONDS[min(max(retry_count - 1, 0), len(RETRY_BACKOFF_SECONDS) - 1)]
    next_retry = time.time() + delay
    _task_event(
        task_id,
        "AUTO_RETRY_SCHEDULED",
        answer_status="retry_wait",
        last_error=str(error_text)[:800],
        failure_code=error_code,
        max_retries=MAX_AUTO_RETRIES,
        next_retry_at_epoch=next_retry,
        finished_at="",
    )
    return {
        "scheduled": True,
        "retry_count": retry_count,
        "next_retry_at_epoch": next_retry,
        "delay_seconds": delay,
    }


def _recover_stale_running_tasks():
    """Recover tasks orphaned by a crash/restart before claiming new work."""
    payload = geo._load_queue()
    now_epoch = time.time()
    stale_ids = []
    for task in payload.get("tasks") or []:
        if task.get("provider") != PROVIDER or task.get("state") != "running":
            continue
        started_epoch = _parse_iso_epoch(task.get("started_at"))
        if started_epoch and now_epoch - started_epoch >= STALE_RUNNING_SECONDS:
            stale_ids.append(task.get("task_id"))
    recovered = []
    for task_id in stale_ids:
        if not task_id:
            continue
        reason = f"STALE_RUNNING: running 超过 {STALE_RUNNING_SECONDS} 秒，自动回收"
        geo.fail_task(task_id, reason)
        _task_event(
            task_id,
            "STALE_RECOVERED",
            answer_status="timeout",
            last_error=reason,
            failure_code="STALE_RUNNING",
            finished_at=now_iso(),
        )
        recovered.append(
            {
                "task_id": task_id,
                "retry": _schedule_auto_retry(
                    task_id,
                    reason,
                    error_code="STALE_RUNNING",
                ),
            }
        )
    return recovered


def _promote_next_cloud_task():
    """Move the next eligible cloud task ahead of unrelated queued browser work."""
    payload = geo._load_queue()
    tasks = payload.get("tasks") or []
    now_epoch = time.time()

    def eligible(item):
        if item.get("state") != "queued" or item.get("provider") != PROVIDER:
            return False
        return float(item.get("next_retry_at_epoch") or 0) <= now_epoch

    cloud_index = next((index for index, item in enumerate(tasks) if eligible(item)), None)
    if cloud_index is None:
        return None
    # claim_next_task() claims the first queued item without understanding
    # retry timestamps, so place the selected eligible cloud task before *all*
    # queued work (including a cloud retry that is still cooling down).
    first_queued_index = next(
        (index for index, item in enumerate(tasks) if item.get("state") == "queued"),
        None,
    )
    if first_queued_index is None or first_queued_index == cloud_index:
        return tasks[cloud_index]
    cloud_task = tasks.pop(cloud_index)
    tasks.insert(first_queued_index, cloud_task)
    geo._save_queue(payload)
    geo._audit(
        "geo_cloud_task_promoted_ahead_of_other_provider",
        {
            "task_id": cloud_task.get("task_id") or "",
            "question_id": cloud_task.get("question_id") or "",
            "preserved_blocking_tasks": True,
        },
    )
    return cloud_task


def run_once(transport=None):
    stale_recovered = _recover_stale_running_tasks()
    current = status()
    cloud_task = _promote_next_cloud_task()
    if cloud_task is None:
        return {
            "ok": True,
            "skipped": True,
            "reason": "cloud_queue_empty_or_retry_wait",
            "executor": current,
            "stale_recovered": stale_recovered,
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
        return {
            "ok": True,
            "skipped": True,
            "reason": claim.get("reason"),
            "executor": current,
            "stale_recovered": stale_recovered,
        }
    task = claim.get("task") or {}
    if task.get("state") != "running":
        return {
            "ok": False,
            "task": task,
            "executor": current,
            "error": task.get("authorization_reason") or task.get("failure_reason"),
            "stale_recovered": stale_recovered,
        }

    task_id = task["task_id"]
    _task_event(
        task_id,
        "REQUEST_STARTED",
        provider=PROVIDER,
        model=current.get("model") or "",
        answer_status="requesting",
        max_retries=MAX_AUTO_RETRIES,
        request_started_at=now_iso(),
        http_status=None,
        request_id="",
        last_error="",
    )

    try:
        answer = _bounded_request(task.get("question_text") or "", transport=transport)
        request_id = answer.get("request_id") or answer.get("response_id") or ""
        _task_event(
            task_id,
            "ANSWER_RECEIVED",
            provider=PROVIDER,
            model=answer.get("model") or current.get("model") or "",
            request_id=request_id,
            http_status=int(answer.get("http_status") or 200),
            latency_ms=int(answer.get("latency_ms") or 0),
            answer_status="received",
            response_id=answer.get("response_id") or "",
            request_finished_at=now_iso(),
        )

        receipt = geo.record_result(
            {
                "task_id": task_id,
                "provider": PROVIDER,
                "model": answer.get("model"),
                "model_version": answer.get("model"),
                "test_method": "api",
                "raw_answer": answer["raw_answer"],
                "citation_urls": answer.get("citation_urls") or [],
                "response_id": answer.get("response_id") or request_id,
                "evidence_ref": f"cloud-response:{request_id}" if request_id else "",
                "web_search_verified": False,
                "evidence_level": "C",
                "analysis": {
                    "cloud_protocol": answer.get("protocol"),
                    "autonomous": True,
                    "request_id": request_id,
                    "http_status": int(answer.get("http_status") or 200),
                    "latency_ms": int(answer.get("latency_ms") or 0),
                    "answer_status": "received",
                    "retry_count": int(task.get("retry_count") or 0),
                    "build_fix": "#644",
                },
            }
        )
        _task_event(
            task_id,
            "COMPLETED",
            answer_status="completed",
            evidence_id=receipt.get("evidence_id") or "",
            receipt_id=receipt.get("receipt_id") or "",
            request_id=request_id,
            http_status=int(answer.get("http_status") or 200),
            latency_ms=int(answer.get("latency_ms") or 0),
            finished_at=receipt.get("finished_at") or now_iso(),
            next_retry_at_epoch=0.0,
            last_error="",
        )
        return {
            "ok": True,
            "task_id": task_id,
            "question_id": task.get("question_id") or "",
            "receipt": receipt,
            "executor": current,
            "request_id": request_id,
            "http_status": int(answer.get("http_status") or 200),
            "latency_ms": int(answer.get("latency_ms") or 0),
            "answer_status": "completed",
            "stale_recovered": stale_recovered,
        }
    except PermissionError as error:
        blocked = geo._transition(task_id, "authorization_required", str(error))
        _task_event(
            task_id,
            "AUTHORIZATION_REQUIRED",
            answer_status="blocked",
            last_error=str(error)[:800],
            failure_code="AUTHORIZATION_REQUIRED",
            finished_at=now_iso(),
        )
        return {
            "ok": False,
            "task": blocked,
            "executor": status(),
            "error": str(error),
            "retry_scheduled": False,
            "stale_recovered": stale_recovered,
        }
    except TimeoutError as error:
        failed = geo.fail_task(task_id, str(error))
        _task_event(
            task_id,
            "REQUEST_TIMEOUT",
            answer_status="timeout",
            last_error=str(error)[:800],
            failure_code="REQUEST_TIMEOUT",
            finished_at=now_iso(),
        )
        retry = _schedule_auto_retry(task_id, str(error), error_code="REQUEST_TIMEOUT")
        return {
            "ok": False,
            "task": failed,
            "executor": current,
            "error": str(error),
            "retry_scheduled": bool(retry.get("scheduled")),
            "retry": retry,
            "stale_recovered": stale_recovered,
        }
    except (OSError, RuntimeError, ValueError, TypeError, KeyError) as error:
        failed = geo.fail_task(task_id, str(error))
        _task_event(
            task_id,
            "REQUEST_FAILED",
            answer_status="failed",
            last_error=str(error)[:800],
            failure_code="EXECUTION_FAILED",
            finished_at=now_iso(),
        )
        retry = _schedule_auto_retry(task_id, str(error), error_code="EXECUTION_FAILED")
        return {
            "ok": False,
            "task": failed,
            "executor": current,
            "error": str(error),
            "retry_scheduled": bool(retry.get("scheduled")),
            "retry": retry,
            "stale_recovered": stale_recovered,
        }
