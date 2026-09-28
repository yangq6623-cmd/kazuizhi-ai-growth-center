"""Local-only HTTP surface for the direct ChatGPT AI Gateway.

This patch also exposes a same-origin bridge for the owner-facing simple content
studio. Browser code must not call the model router on :17777 directly: that
router intentionally has no browser CORS/OPTIONS surface. The dashboard on
:8876 owns the browser request and forwards it locally instead.
"""
from __future__ import annotations

import json
import socket
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from backend import server
from integrations.ai_gateway import clear_gateway, configure_gateway, gateway_status, run_once, test_gateway

_INSTALLED = False
_LOCAL_ROUTER_URL = "http://127.0.0.1:17777/v1/chat/completions"
_LOCAL_OLLAMA_HOST = ("127.0.0.1", 11434)
_LOCAL_ROUTER_HOST = ("127.0.0.1", 17777)
_LOCAL_PROXY_PATH = "/api/local-ai/chat/completions"
_LOCAL_HEALTH_PATH = "/api/local-ai/health"
_DIRECT_ROUTER_JS = "http://127.0.0.1:17777/v1/chat/completions"
_SAME_ORIGIN_ROUTER_JS = _LOCAL_PROXY_PATH


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


def _local_ai_health():
    router_ok = _port_ready(_LOCAL_ROUTER_HOST)
    ollama_ok = _port_ready(_LOCAL_OLLAMA_HOST)
    return {
        "ok": bool(router_ok and ollama_ok),
        "router": "ready" if router_ok else "starting",
        "model_runtime": "ready" if ollama_ok else "starting",
        "message": "本地 AI 已就绪" if router_ok and ollama_ok else "AI 服务正在启动，请稍后重试",
    }


def _proxy_local_chat(payload):
    if not isinstance(payload, dict):
        raise ValueError("请求内容不正确")
    messages = payload.get("messages")
    if not isinstance(messages, list) or not messages:
        raise ValueError("请先填写需要 AI 处理的内容")
    request = Request(
        _LOCAL_ROUTER_URL,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=120) as response:
            raw = response.read()
    except HTTPError as error:
        # The simple owner UI should never expose router implementation details.
        try:
            detail = json.loads(error.read().decode("utf-8", errors="replace") or "{}")
            message = detail.get("detail") or detail.get("error") or ""
        except (ValueError, TypeError, AttributeError):
            message = ""
        raise RuntimeError(message or "AI 服务暂时不可用，请稍后重试") from error
    except (URLError, socket.timeout, TimeoutError, OSError) as error:
        raise RuntimeError("AI 服务正在启动或响应较慢，请稍后重试") from error
    try:
        data = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError("AI 服务返回异常，请稍后重试") from error
    if not isinstance(data, dict) or not isinstance(data.get("choices"), list):
        raise RuntimeError("AI 服务暂时没有返回可用结果，请稍后重试")
    return data


def _serve_simple_studio_with_same_origin_router(handler):
    """Serve the simple-studio script with its router URL rewritten locally.

    Keeping the rewrite in this compatibility patch avoids a browser CORS hop
    while preserving the source module's existing production flow. Future
    source consolidation can replace the literal directly; packaged runtime is
    already same-origin from this build onward.
    """
    path = server.get_web_path() / "content-studio-simple.js"
    source = path.read_text(encoding="utf-8")
    source = source.replace(_DIRECT_ROUTER_JS, _SAME_ORIGIN_ROUTER_JS)
    data = source.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/javascript; charset=utf-8")
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
        if path == "/content-studio-simple.js":
            try:
                _serve_simple_studio_with_same_origin_router(handler)
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
