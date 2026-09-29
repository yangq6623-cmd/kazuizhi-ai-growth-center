"""Local-only HTTP surface for the direct ChatGPT AI Gateway.

This patch also exposes a same-origin bridge for owner-facing content studio
browser modules. Browser code must not call the model router on :17777
directly: that router intentionally has no browser CORS/OPTIONS surface. The
dashboard on :8876 owns the browser request and forwards it locally instead.

RTX 3060 12 GB policy:
- serialize local text-model calls;
- cap oversized text generations;
- retry one transient 503 after releasing stale Ollama allocations;
- unload the text model after every owner-facing AI call so image/video models
  can use the GPU next without competing with an idle Qwen model.
"""
from __future__ import annotations

import json
import socket
import threading
import time
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from backend import server
from integrations.ai_gateway import clear_gateway, configure_gateway, gateway_status, run_once, test_gateway

_INSTALLED = False
_LOCAL_ROUTER_URL = "http://127.0.0.1:17777/v1/chat/completions"
_LOCAL_OLLAMA_BASE = "http://127.0.0.1:11434"
_LOCAL_OLLAMA_HOST = ("127.0.0.1", 11434)
_LOCAL_ROUTER_HOST = ("127.0.0.1", 17777)
_LOCAL_PROXY_PATH = "/api/local-ai/chat/completions"
_LOCAL_HEALTH_PATH = "/api/local-ai/health"
_LOCAL_RELEASE_PATH = "/api/local-ai/release"
_DIRECT_ROUTER_JS = "http://127.0.0.1:17777/v1/chat/completions"
_SAME_ORIGIN_ROUTER_JS = _LOCAL_PROXY_PATH
_LOCAL_AI_BROWSER_SCRIPTS = {
    "/content-studio-simple.js": "content-studio-simple.js",
    "/content-reference-center.js": "content-reference-center.js",
}
_LOCAL_AI_LOCK = threading.Lock()
_LOCAL_AI_TIMEOUT_SECONDS = 150
_LOCAL_AI_MAX_TOKENS = 1200


def _origin_allowed(handler):
    origin = handler.headers.get("Origin")
    return not origin or origin in {
        f"http://127.0.0.1:{handler.server.server_port}",
        f"http://localhost:{handler.server.server_port}",
    }


def _read_json(handler):
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0 or length > 64 * 1024:
        raise ValueError("请求大小不正确")
    return json.loads(handler.rfile.read(length) or b"{}")


def _port_ready(host_port, timeout=1.0):
    try:
        with socket.create_connection(host_port, timeout=timeout):
            return True
    except OSError:
        return False


def _ollama_json(path, payload=None, timeout=10):
    url = f"{_LOCAL_OLLAMA_BASE}{path}"
    if payload is None:
        request = Request(url, headers={"Accept": "application/json"}, method="GET")
    else:
        request = Request(
            url,
            data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
            headers={"Content-Type": "application/json", "Accept": "application/json"},
            method="POST",
        )
    with urlopen(request, timeout=timeout) as response:
        raw = response.read()
    if not raw:
        return {}
    return json.loads(raw.decode("utf-8"))


def _loaded_ollama_models():
    try:
        data = _ollama_json("/api/ps", timeout=3)
    except (HTTPError, URLError, socket.timeout, TimeoutError, OSError, ValueError, json.JSONDecodeError):
        return []
    models = data.get("models") if isinstance(data, dict) else []
    result = []
    for item in models or []:
        if not isinstance(item, dict):
            continue
        name = item.get("name") or item.get("model") or ""
        if name:
            result.append(name)
    return result


def _release_ollama_model(model_name=""):
    """Unload resident Ollama text models to return VRAM to video generation."""
    names = [model_name] if model_name else _loaded_ollama_models()
    released = []
    seen = set()
    for name in names:
        if not name or name in seen:
            continue
        seen.add(name)
        try:
            _ollama_json(
                "/api/generate",
                {"model": name, "prompt": "", "stream": False, "keep_alive": 0},
                timeout=20,
            )
            released.append(name)
        except (HTTPError, URLError, socket.timeout, TimeoutError, OSError, ValueError, json.JSONDecodeError):
            continue
    return released


def _compact_chat_payload(payload):
    """Keep local text work bounded for a 12 GB RTX 3060 without changing intent."""
    request_payload = dict(payload)
    messages = request_payload.get("messages")
    if not isinstance(messages, list) or not messages:
        raise ValueError("请先填写需要 AI 处理的内容")
    normalized = []
    for message in messages:
        if not isinstance(message, dict):
            continue
        item = dict(message)
        content = str(item.get("content") or "")
        # Prevent accidental huge pasted pages from exhausting context/VRAM.
        if len(content) > 12000:
            content = content[:12000] + "\n[内容过长，已截取前12000字进行本次分析]"
        item["content"] = content
        normalized.append(item)
    if not normalized:
        raise ValueError("请先填写需要 AI 处理的内容")
    request_payload["messages"] = normalized
    request_payload["stream"] = False
    try:
        current_max = int(request_payload.get("max_tokens") or _LOCAL_AI_MAX_TOKENS)
    except (TypeError, ValueError):
        current_max = _LOCAL_AI_MAX_TOKENS
    request_payload["max_tokens"] = max(256, min(current_max, _LOCAL_AI_MAX_TOKENS))
    try:
        temperature = float(request_payload.get("temperature", 0.3))
    except (TypeError, ValueError):
        temperature = 0.3
    request_payload["temperature"] = max(0.0, min(temperature, 0.35))
    return request_payload


def _router_request(payload):
    request = Request(
        _LOCAL_ROUTER_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    with urlopen(request, timeout=_LOCAL_AI_TIMEOUT_SECONDS) as response:
        return response.read()


def _local_ai_health():
    router_ok = _port_ready(_LOCAL_ROUTER_HOST)
    ollama_ok = _port_ready(_LOCAL_OLLAMA_HOST)
    loaded = _loaded_ollama_models() if ollama_ok else []
    return {
        "ok": bool(router_ok and ollama_ok),
        "router": "ready" if router_ok else "starting",
        "model_runtime": "ready" if ollama_ok else "starting",
        "loaded_models": loaded,
        "resource_policy": "serial_text_then_release",
        "message": "本地 AI 已就绪" if router_ok and ollama_ok else "AI 服务正在启动，请稍后重试",
    }


def _proxy_local_chat(payload):
    request_payload = _compact_chat_payload(payload)
    data = None
    actual_model = ""
    with _LOCAL_AI_LOCK:
        try:
            for attempt in range(2):
                try:
                    raw = _router_request(request_payload)
                    break
                except HTTPError as error:
                    if error.code == 503 and attempt == 0:
                        _release_ollama_model()
                        time.sleep(1.2)
                        continue
                    try:
                        detail = json.loads(error.read().decode("utf-8", errors="replace") or "{}")
                        message = detail.get("detail") or detail.get("error") or detail.get("message") or ""
                    except (ValueError, TypeError, AttributeError, json.JSONDecodeError):
                        message = ""
                    raise RuntimeError(message or "AI 服务暂时繁忙，请稍后重试") from error
                except (URLError, socket.timeout, TimeoutError, OSError) as error:
                    raise RuntimeError("AI 服务响应较慢，请稍后重试") from error
            else:
                raise RuntimeError("AI 服务暂时繁忙，请稍后重试")

            try:
                data = json.loads(raw.decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError) as error:
                raise RuntimeError("AI 服务返回异常，请稍后重试") from error
            if not isinstance(data, dict) or not isinstance(data.get("choices"), list):
                raise RuntimeError("AI 服务暂时没有返回可用结果，请稍后重试")
            actual_model = str(data.get("model") or "")
            return data
        finally:
            # Qwen3:8b can occupy almost the whole 12 GB card while idle. The
            # owner workflow now releases it after each text step so subsequent
            # ComfyUI/video work starts with free VRAM. On failures, release any
            # resident Ollama model to recover the card before the next retry.
            _release_ollama_model(actual_model)
            if not actual_model:
                _release_ollama_model()


def _rewrite_browser_script(source):
    """Keep every content-studio browser hop on the dashboard origin."""
    return (
        source.replace(_DIRECT_ROUTER_JS, _SAME_ORIGIN_ROUTER_JS)
        .replace("可检查 17777 服务后重试。", "请确认本地 AI 服务已经启动后重试。")
        .replace(
            "if(!response.ok)throw new Error(`本地 Router 返回 ${response.status}`);",
            "if(!response.ok){let detail={};try{detail=await response.json();}catch(_){}throw new Error(detail.detail||detail.error||detail.message||'AI 服务暂时繁忙，请稍后重试');}",
        )
        .replace(
            "},45000,400);\n      showAnalysis(analyzed);",
            "},180000,400);\n      showAnalysis(analyzed);",
        )
        .replace(
            "},135000,400);\n      showAnalysis(analyzed);",
            "},180000,400);\n      showAnalysis(analyzed);",
        )
        .replace(
            "后台正在分析参考、原创改写、导演分镜并建立候选任务。",
            "后台正在分析参考、原创改写、导演分镜并建立候选任务。首次调用本地模型可能需要 1–2 分钟，请保持页面打开。",
        )
    )


def _serve_browser_script_with_same_origin_router(handler, filename):
    path = server.get_web_path() / filename
    source = _rewrite_browser_script(path.read_text(encoding="utf-8"))
    data = source.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/javascript; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def install():
    global _INSTALLED
    if _INSTALLED:
        return
    original_get = server.DashboardHandler.do_GET
    original_post = server.DashboardHandler.do_POST

    def do_get(handler):
        path = urlsplit(handler.path).path
        if path in _LOCAL_AI_BROWSER_SCRIPTS:
            try:
                _serve_browser_script_with_same_origin_router(handler, _LOCAL_AI_BROWSER_SCRIPTS[path])
            except OSError as error:
                handler._json_error(500, error)
            return
        if path == _LOCAL_HEALTH_PATH:
            handler._json_ok(_local_ai_health())
            return
        if path == "/api/ai-gateway/status":
            try:
                handler._json_ok(gateway_status())
            except (OSError, ValueError, RuntimeError, TypeError) as error:
                handler._json_error(500, error)
            return
        return original_get(handler)

    def do_post(handler):
        path = urlsplit(handler.path).path
        if path == _LOCAL_PROXY_PATH:
            if not _origin_allowed(handler):
                handler._json_error(403, "仅允许本机工作台使用此功能")
                return
            try:
                result = _proxy_local_chat(_read_json(handler))
                handler._json_ok(result)
            except (ValueError, json.JSONDecodeError) as error:
                handler._json_error(400, error)
            except RuntimeError as error:
                handler._json_error(503, error)
            return
        if path == _LOCAL_RELEASE_PATH:
            if not _origin_allowed(handler):
                handler._json_error(403, "仅允许本机工作台使用此功能")
                return
            released = _release_ollama_model()
            handler._json_ok({"ok": True, "released": released, "message": "文本模型显存已释放"})
            return
        if path in {"/api/ai-gateway/config", "/api/ai-gateway/clear", "/api/ai-gateway/test"}:
            if not _origin_allowed(handler):
                handler._json_error(403, "Cross-origin changes are not allowed")
                return
            try:
                if path.endswith("/config"):
                    result = configure_gateway(_read_json(handler))
                elif path.endswith("/clear"):
                    result = clear_gateway(_read_json(handler).get("route"))
                else:
                    result = test_gateway(_read_json(handler).get("route"))
                handler._json_ok(result)
            except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
                handler._json_error(400, error)
            return
        return original_post(handler)

    server.DashboardHandler.do_GET = do_get
    server.DashboardHandler.do_POST = do_post
    server.DashboardHandler._kz_ai_gateway_patched = True
    server.DashboardHandler._kz_local_ai_proxy_patched = True
    server.DashboardHandler._kz_local_ai_resource_scheduled = True
    _INSTALLED = True


install()

# R8-10 installs after the legacy API gateway so the owner UI gets a separate,
# truthful ChatGPT-subscription control status. The legacy OpenAI API gateway
# remains an optional advanced fallback and cannot set this state to verified.
from backend import r8_10_control_patch as _r8_10_control_patch  # noqa: E402,F401
# Optional same-PC real-time helper: ChatGPT desktop Site Tools/WebMCP may call
# this localhost runtime directly. It is no longer required for normal autonomy.
from backend import kz_local_control_patch as _kz_local_control_patch  # noqa: E402,F401
# Primary day-to-day owner channel: normal ChatGPT writes Decision Packs to a
# dedicated PRIVATE GitHub control-bus repository. The local agent keeps Mission
# execution running without Work/Codex or a permanent Site Tools session.
from backend import async_control_bus_patch as _async_control_bus_patch  # noqa: E402,F401
