"""Direct, auditable AI gateway for the Kazuizhi autonomous Mission loop.

The legacy filesystem bridge stays as an offline/fallback transport. When an
OpenAI API credential is configured, this gateway sends pending R8 planning and
post-render QC requests directly to ChatGPT and applies only locally validated
structured results. It never approves publication, never performs financial
operations and never treats a transport write as proof of model processing.
"""
from __future__ import annotations

import base64
import ctypes
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from ctypes import wintypes

from core.storage import now_iso, read_json, write_json
from promotion import content_factory as cf

CONFIG_PATH = "integrations/ai_gateway.json"
STATE_PATH = "integrations/ai_gateway_state.json"
DEFAULT_ENDPOINT = "https://api.openai.com/v1/responses"
DEFAULT_MODEL = "gpt-5.6"
MAX_ERROR = 500

# The desktop deliberately treats cloud and local runtimes as separate routes.
# A local OpenAI-compatible server (for example Ollama, LM Studio or vLLM) is
# never assumed to be installed merely because this code knows its address.
LOCAL_RUNTIME_PRESETS = {
    "ollama": {"label": "Ollama（本机）", "endpoint": "http://127.0.0.1:11434/v1/chat/completions", "protocol": "chat_completions"},
    "lm_studio": {"label": "LM Studio（本机）", "endpoint": "http://127.0.0.1:1234/v1/chat/completions", "protocol": "chat_completions"},
    "vllm": {"label": "vLLM（本机）", "endpoint": "http://127.0.0.1:8000/v1/chat/completions", "protocol": "chat_completions"},
    "custom": {"label": "自定义本机兼容服务", "endpoint": "", "protocol": "chat_completions"},
}


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _config():
    """Read the versioned model-routing configuration and migrate R8-17 data.

    R8-17 had one hard-coded OpenAI route.  Migration is intentionally local
    and retains the DPAPI-protected secret instead of asking the owner to paste
    it again.
    """
    value = read_json(CONFIG_PATH, {})
    value = value if isinstance(value, dict) else {}
    if isinstance(value.get("profiles"), dict):
        return value
    legacy = value
    cloud = {
        "provider": "openai_compatible",
        "label": "云端 OpenAI 兼容模型",
        "endpoint": str(legacy.get("endpoint") or DEFAULT_ENDPOINT),
        "protocol": "responses",
        "model": str(legacy.get("model") or DEFAULT_MODEL),
        "protected_api_key": str(legacy.get("protected_api_key") or ""),
    }
    return {"schema": "kazuizhi-model-routing/v1", "active_route": "cloud", "fallback_enabled": True,
            "profiles": {"cloud": cloud, "local": {"provider": "ollama", "label": LOCAL_RUNTIME_PRESETS["ollama"]["label"],
            "endpoint": LOCAL_RUNTIME_PRESETS["ollama"]["endpoint"], "protocol": "chat_completions", "model": "", "protected_api_key": ""}}}


def _state():
    value = read_json(STATE_PATH, {})
    return value if isinstance(value, dict) else {}


def _save_state(**values):
    current = _state()
    current.update(values, updated_at=now_iso())
    write_json(STATE_PATH, current)
    return current


def _protect_windows(secret):
    if os.name != "nt":
        raise ValueError("当前系统不支持安全保存API密钥，请使用OPENAI_API_KEY环境变量")
    raw = secret.encode("utf-8")
    buffer = ctypes.create_string_buffer(raw)
    incoming = _DATA_BLOB(len(raw), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
    outgoing = _DATA_BLOB()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    if not crypt32.CryptProtectData(ctypes.byref(incoming), "Kazuizhi AI Gateway", None, None, None, 0, ctypes.byref(outgoing)):
        raise OSError("Windows DPAPI 加密失败")
    try:
        protected = ctypes.string_at(outgoing.pbData, outgoing.cbData)
        return base64.b64encode(protected).decode("ascii")
    finally:
        kernel32.LocalFree(outgoing.pbData)


def _unprotect_windows(encoded):
    if os.name != "nt" or not encoded:
        return ""
    protected = base64.b64decode(encoded.encode("ascii"))
    buffer = ctypes.create_string_buffer(protected)
    incoming = _DATA_BLOB(len(protected), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
    outgoing = _DATA_BLOB()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    if not crypt32.CryptUnprotectData(ctypes.byref(incoming), None, None, None, None, 0, ctypes.byref(outgoing)):
        return ""
    try:
        return ctypes.string_at(outgoing.pbData, outgoing.cbData).decode("utf-8")
    finally:
        kernel32.LocalFree(outgoing.pbData)


def _profile(route):
    route = "local" if route == "local" else "cloud"
    profile = (_config().get("profiles") or {}).get(route) or {}
    return dict(profile) if isinstance(profile, dict) else {}


def _api_key(route="cloud"):
    if route == "cloud":
        environment = str(os.environ.get("OPENAI_API_KEY") or "").strip()
        if environment:
            return environment, "environment"
    secret = _unprotect_windows(str(_profile(route).get("protected_api_key") or ""))
    return (secret, "windows_dpapi") if secret else ("", "none")


def _is_local_endpoint(endpoint):
    parsed = urllib.parse.urlsplit(str(endpoint or ""))
    return parsed.hostname in {"127.0.0.1", "localhost", "::1"}


def _validate_endpoint(endpoint, route):
    value = str(endpoint or "").strip().rstrip("/")
    parsed = urllib.parse.urlsplit(value)
    if not parsed.scheme or not parsed.netloc:
        raise ValueError("请填写完整模型服务地址")
    if route == "local":
        if not _is_local_endpoint(value) or parsed.scheme != "http":
            raise ValueError("本地模型只允许连接本机 127.0.0.1 或 localhost 的 HTTP 服务")
    elif parsed.scheme != "https":
        raise ValueError("云端模型服务必须使用 HTTPS")
    return value


def _route_status(route):
    profile = _profile(route)
    key, source = _api_key(route)
    model = str(profile.get("model") or "").strip()
    endpoint = str(profile.get("endpoint") or "").strip()
    needs_key = route == "cloud"
    configured = bool(model and endpoint and (key if needs_key else True))
    state = _state().get("routes") if isinstance(_state().get("routes"), dict) else {}
    check = state.get(route) if isinstance(state.get(route), dict) else {}
    verified = bool(configured and check.get("last_test_at") and not check.get("last_error"))
    return {"id": route, "route": route, "provider": str(profile.get("provider") or ("openai_compatible" if route == "cloud" else "ollama")),
            "label": str(profile.get("label") or ("云端模型" if route == "cloud" else "本地模型")),
            "endpoint": endpoint, "protocol": str(profile.get("protocol") or ("responses" if route == "cloud" else "chat_completions")),
            "model": model, "requires_api_key": needs_key, "configured": configured, "verified": verified,
            "credential_source": source, "last_test_at": check.get("last_test_at"), "last_error": check.get("last_error"),
            "status": "ready" if verified else "configured" if configured else "not_configured",
            "status_label": "已验证" if verified else "待测试" if configured else "未配置"}


def gateway_status():
    config = _config()
    routes = {route: _route_status(route) for route in ("cloud", "local")}
    active_route = str(config.get("active_route") or "cloud")
    active_route = active_route if active_route in routes else "cloud"
    active = routes[active_route]
    state = _state()
    return {
        "id": "model_connection_center", "status": active["status"],
        "status_label": "AI大脑在线" if active["verified"] else "已配置，等待验证" if active["configured"] else "需要一次配置",
        "configured": active["configured"], "active_route": active_route, "fallback_enabled": bool(config.get("fallback_enabled", True)),
        "routes": routes, "provider": active["provider"], "model": active["model"], "endpoint": active["endpoint"],
        "last_success_at": state.get("last_success_at"), "last_error": state.get("last_error"), "last_kind": state.get("last_kind"),
        "truth_rule": "云端与本地模型均只能生成经本机校验的建议或草稿；发布、账号安全和资金权限不会因模型接入而放开。密钥不会返回给网页。",
    }


def configure_gateway(payload):
    values = payload if isinstance(payload, dict) else {}
    route = "local" if values.get("route") == "local" else "cloud"
    config = _config()
    profiles = config.setdefault("profiles", {})
    previous = _profile(route)
    provider = str(values.get("provider") or previous.get("provider") or ("ollama" if route == "local" else "openai_compatible"))[:40]
    preset = LOCAL_RUNTIME_PRESETS.get(provider) if route == "local" else None
    endpoint = values.get("endpoint") or (preset or {}).get("endpoint") or previous.get("endpoint") or DEFAULT_ENDPOINT
    endpoint = _validate_endpoint(endpoint, route)
    model = str(values.get("model") or "").strip()[:80]
    if not re.fullmatch(r"[A-Za-z0-9._:/-]{2,80}", model):
        raise ValueError("请填写合法模型名称")
    protocol = str(values.get("protocol") or (preset or {}).get("protocol") or previous.get("protocol") or ("responses" if route == "cloud" else "chat_completions"))
    if protocol not in {"responses", "chat_completions"}:
        raise ValueError("不支持的模型协议")
    profile = {"provider": provider, "label": str(values.get("label") or (preset or {}).get("label") or ("云端 OpenAI 兼容模型" if route == "cloud" else "本地开源模型")),
               "endpoint": endpoint, "protocol": protocol, "model": model, "configured_at": now_iso()}
    key = str(values.get("api_key") or "").strip()
    if key:
        if len(key) > 500:
            raise ValueError("API 密钥长度不正确")
        profile["protected_api_key"] = _protect_windows(key)
    else:
        profile["protected_api_key"] = str(previous.get("protected_api_key") or "")
    if route == "cloud" and not (profile["protected_api_key"] or os.environ.get("OPENAI_API_KEY")):
        raise ValueError("云端模型需要 API 密钥；本地模型可留空")
    profiles[route] = profile
    config["schema"] = "kazuizhi-model-routing/v1"
    config["active_route"] = route if values.get("set_active", True) else config.get("active_route", "cloud")
    config["fallback_enabled"] = bool(values.get("fallback_enabled", config.get("fallback_enabled", True)))
    write_json(CONFIG_PATH, config)
    routes = _state().get("routes") if isinstance(_state().get("routes"), dict) else {}
    routes[route] = {"last_test_at": None, "last_error": None}
    _save_state(routes=routes, last_error=None)
    return gateway_status()


def clear_gateway(route="cloud"):
    route = "local" if route == "local" else "cloud"
    config = _config()
    profile = _profile(route)
    config.setdefault("profiles", {})[route] = {"provider": profile.get("provider") or ("ollama" if route == "local" else "openai_compatible"),
        "label": profile.get("label") or ("本地开源模型" if route == "local" else "云端 OpenAI 兼容模型"),
        "endpoint": profile.get("endpoint") or (LOCAL_RUNTIME_PRESETS["ollama"]["endpoint"] if route == "local" else DEFAULT_ENDPOINT),
        "protocol": profile.get("protocol") or ("chat_completions" if route == "local" else "responses"), "model": "", "protected_api_key": ""}
    write_json(CONFIG_PATH, config)
    routes = _state().get("routes") if isinstance(_state().get("routes"), dict) else {}
    routes[route] = {"last_test_at": None, "last_error": None}
    _save_state(routes=routes, last_error=None, last_success_at=None)
    return gateway_status()


def _models_endpoint(endpoint):
    """Return the OpenAI-compatible model-list route without guessing a host."""
    parsed = urllib.parse.urlsplit(str(endpoint))
    path = parsed.path.rstrip("/")
    for suffix in ("/responses", "/chat/completions", "/completions"):
        if path.endswith(suffix):
            path = path[:-len(suffix)]
            break
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path.rstrip("/") + "/models", "", ""))


def test_gateway(route=None):
    """Perform a small authenticated health check; it never creates content."""
    status = gateway_status()
    route = "local" if route == "local" else str(route or status.get("active_route") or "cloud")
    profile = _profile(route)
    route_status = _route_status(route)
    if not route_status.get("configured"):
        raise ValueError("请先完整填写该模型的地址和模型名称")
    key, _ = _api_key(route)
    endpoint = _validate_endpoint(profile.get("endpoint"), route)
    request = urllib.request.Request(_models_endpoint(endpoint), headers={"Accept": "application/json", **({"Authorization": f"Bearer {key}"} if key else {})}, method="GET")
    try:
        with urllib.request.urlopen(request, timeout=15) as response:
            # Accept a valid JSON response even when a local runtime does not
            # expose every model in a standard list shape.
            json.loads(response.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as error:
        message = f"模型服务 HTTP {error.code}，请检查地址、密钥和模型服务是否已启动"
        routes = _state().get("routes") if isinstance(_state().get("routes"), dict) else {}
        routes[route] = {"last_test_at": now_iso(), "last_error": message}
        _save_state(routes=routes, last_error=message)
        raise ValueError(message) from error
    except (urllib.error.URLError, TimeoutError, OSError, ValueError, json.JSONDecodeError) as error:
        message = "无法连接模型服务，请确认本机模型已启动或云端地址、网络和密钥正确"
        routes = _state().get("routes") if isinstance(_state().get("routes"), dict) else {}
        routes[route] = {"last_test_at": now_iso(), "last_error": message}
        _save_state(routes=routes, last_error=message)
        raise ValueError(message) from error
    routes = _state().get("routes") if isinstance(_state().get("routes"), dict) else {}
    routes[route] = {"last_test_at": now_iso(), "last_error": None}
    _save_state(routes=routes, last_error=None)
    return gateway_status()


def _extract_text(response):
    direct = response.get("output_text") if isinstance(response, dict) else None
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    texts = []
    # OpenAI-compatible local servers usually answer using the Chat
    # Completions envelope rather than the Responses envelope.
    for choice in response.get("choices", []) if isinstance(response, dict) else []:
        message = choice.get("message") if isinstance(choice, dict) else {}
        text = message.get("content") if isinstance(message, dict) else None
        if isinstance(text, str) and text.strip():
            texts.append(text.strip())
    for item in response.get("output", []) if isinstance(response, dict) else []:
        for content in item.get("content", []) if isinstance(item, dict) else []:
            if isinstance(content, dict) and content.get("type") in {"output_text", "text"}:
                text = content.get("text")
                if isinstance(text, str) and text.strip():
                    texts.append(text.strip())
    return "\n".join(texts).strip()


def _parse_json_text(text):
    value = str(text or "").strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*", "", value, flags=re.I)
        value = re.sub(r"\s*```$", "", value)
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise ValueError("ChatGPT返回的内容不是有效JSON") from error
    if not isinstance(parsed, dict):
        raise ValueError("ChatGPT结构化返回必须是JSON对象")
    return parsed


def _http_transport(payload, api_key, profile):
    protocol = str(profile.get("protocol") or "responses")
    endpoint = _validate_endpoint(profile.get("endpoint"), "local" if profile.get("route") == "local" else "cloud")
    headers = {"Content-Type": "application/json"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    if protocol == "chat_completions":
        # The task contract is retained verbatim, but sent in the broadly
        # supported Chat Completions shape used by local runtimes.
        body = {"model": payload["model"], "temperature": 0.1,
                "messages": [{"role": "system", "content": "只输出有效JSON，不执行发布、账号或资金操作。"},
                             {"role": "user", "content": payload["input"]}]}
    else:
        body = payload
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers=headers,
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:MAX_ERROR]
        raise ValueError(f"模型服务 HTTP {error.code}: {detail}") from error
    except urllib.error.URLError as error:
        raise ValueError(f"模型服务连接失败: {error.reason}") from error


def _active_profile():
    status = gateway_status()
    active = status.get("active_route") or "cloud"
    routes = status.get("routes") or {}
    selected = routes.get(active) or {}
    if selected.get("configured"):
        profile = _profile(active)
        profile["route"] = active
        return active, profile
    if status.get("fallback_enabled"):
        fallback = "local" if active == "cloud" else "cloud"
        if (routes.get(fallback) or {}).get("configured"):
            profile = _profile(fallback)
            profile["route"] = fallback
            return fallback, profile
    raise ValueError("模型接入中心尚未配置可用模型")


def _call(kind, request_item, transport=None):
    route, profile = _active_profile()
    key, _ = _api_key(route)
    if route == "cloud" and not key:
        raise ValueError("云端模型尚未配置 API 密钥")
    model = str(profile.get("model") or DEFAULT_MODEL)
    if kind == "content_production":
        contract = (
            "只返回一个JSON对象，不要Markdown。顶层必须含kind='content_production'、video_id、campaign_id、production_plan。"
            "production_plan必须符合kazuizhi-content-production/v1：schema,version,campaign_id,objective,target_platforms,topic,"
            "pain_point,titles,script,storyboard,voice,subtitle,cover,cta,output,qc,material_policy。storyboard至少1项；"
            "没有真实维修证据时不得把AI画面写成真实案例，required_real镜头可降级为info_card。老板最终审核不可绕过。"
        )
    else:
        contract = (
            "只返回一个JSON对象，不要Markdown。顶层必须含kind='content_qc'、video_id、candidate_id、decision、score、"
            "reasons、shot_feedback。decision只能是pass或rework。不得替老板执行最终发布审核。"
        )
    prompt = (
        "你是卡嘴子自治运营系统的唯一ChatGPT总决策大脑。根据下面真实Mission/R7/R8上下文完成当前任务。"
        "不得伪造平台回执、咨询、订单、维修现场或素材权利。" + contract + "\n\nREQUEST_JSON:\n" +
        json.dumps(request_item, ensure_ascii=False, separators=(",", ":"))
    )
    payload = {"model": model, "input": prompt, "max_output_tokens": 7000}
    raw = transport(payload, key) if transport else _http_transport(payload, key, profile)
    parsed = _parse_json_text(_extract_text(raw))
    if str(parsed.get("kind") or kind) != kind:
        raise ValueError("ChatGPT返回kind与当前任务不一致")
    return parsed


def _recover_retry_exhausted():
    data = cf._load()
    changed = False
    for video in data.get("videos", []):
        handoff = video.get("chatgpt_handoff") if isinstance(video.get("chatgpt_handoff"), dict) else {}
        if video.get("status") != "异常待处理" or handoff.get("phase") != "retry_exhausted":
            continue
        kind = handoff.get("kind")
        video["status"] = "等待ChatGPT质检" if kind == "content_qc" else "等待ChatGPT策划"
        video["bottleneck"] = "AI Gateway已配置，正在恢复直接ChatGPT调用"
        video["auto_action"] = "跳过已失效的无限文件桥等待，改由AI Gateway直接处理"
        handoff["phase"] = "gateway_recovering"
        handoff["updated_at"] = now_iso()
        changed = True
    if changed:
        cf._save(data)
    return changed


def run_once(limit=2, transport=None):
    status = gateway_status()
    if not status.get("configured"):
        return {"processed": 0, "status": status, "reason": "not_configured"}
    _recover_retry_exhausted()
    processed = 0
    errors = []

    planning = cf.pending_chatgpt_handoff(limit=max(1, int(limit or 1))).get("items", [])
    for item in planning:
        if processed >= limit:
            break
        try:
            result = _call("content_production", item, transport=transport)
            plan = result.get("production_plan") if isinstance(result.get("production_plan"), dict) else result
            cf.apply_chatgpt_plan({
                "video_id": item.get("video_id"),
                "campaign_id": item.get("campaign_id"),
                "production_plan": plan,
            })
            processed += 1
            _save_state(last_success_at=now_iso(), last_error=None, last_kind="content_production")
        except (OSError, ValueError, TypeError, KeyError) as error:
            message = str(error)[:MAX_ERROR]
            errors.append({"kind": "content_production", "video_id": item.get("video_id"), "error": message})
            _save_state(last_error=message, last_kind="content_production")
            try:
                cf.update_runtime_state(
                    item.get("video_id"),
                    bottleneck="AI Gateway暂时调用失败，保留同步桥作为备用通道",
                    auto_action="系统稍后自动重试；不会重复创建任务",
                    last_error=message,
                )
            except (OSError, ValueError):
                pass
            break

    if processed < limit:
        qc_reader = getattr(cf, "pending_chatgpt_qc_handoff", None)
        qc_items = qc_reader(limit=limit - processed).get("items", []) if callable(qc_reader) else []
        for item in qc_items:
            if processed >= limit:
                break
            try:
                result = _call("content_qc", item, transport=transport)
                cf.apply_chatgpt_qc({
                    "video_id": item.get("video_id"),
                    "candidate_id": item.get("candidate_id"),
                    "decision": result.get("decision"),
                    "score": result.get("score"),
                    "reasons": result.get("reasons") or [],
                    "shot_feedback": result.get("shot_feedback") or [],
                })
                processed += 1
                _save_state(last_success_at=now_iso(), last_error=None, last_kind="content_qc")
            except (OSError, ValueError, TypeError, KeyError) as error:
                message = str(error)[:MAX_ERROR]
                errors.append({"kind": "content_qc", "video_id": item.get("video_id"), "error": message})
                _save_state(last_error=message, last_kind="content_qc")
                break

    return {"processed": processed, "errors": errors, "status": gateway_status()}
