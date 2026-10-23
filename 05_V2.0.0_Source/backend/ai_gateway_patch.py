"""Local-only HTTP surface for the direct ChatGPT AI Gateway."""
from __future__ import annotations

import json
from urllib.parse import urlsplit

from backend import server
from integrations.ai_gateway import clear_gateway, configure_gateway, gateway_status, run_once

_INSTALLED = False


def _origin_allowed(handler):
    origin = handler.headers.get("Origin")
    return not origin or origin in {
        f"http://127.0.0.1:{handler.server.server_port}",
        f"http://localhost:{handler.server.server_port}",
    }


def _read_json(handler):
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0 or length > 32 * 1024:
        raise ValueError("请求大小不正确")
    return json.loads(handler.rfile.read(length) or b"{}")


def install():
    global _INSTALLED
    if _INSTALLED:
        return
    original_get = server.DashboardHandler.do_GET
    original_post = server.DashboardHandler.do_POST

    def do_get(handler):
        path = urlsplit(handler.path).path
        if path == "/api/ai-gateway/status":
            try:
                handler._json_ok(gateway_status())
            except (OSError, ValueError, RuntimeError, TypeError) as error:
                handler._json_error(500, error)
            return
        return original_get(handler)

    def do_post(handler):
        path = urlsplit(handler.path).path
        if path in {"/api/ai-gateway/config", "/api/ai-gateway/clear", "/api/ai-gateway/test"}:
            if not _origin_allowed(handler):
                handler._json_error(403, "Cross-origin changes are not allowed")
                return
            try:
                if path.endswith("/config"):
                    result = configure_gateway(_read_json(handler))
                elif path.endswith("/clear"):
                    result = clear_gateway()
                else:
                    result = run_once(limit=1)
                handler._json_ok(result)
            except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
                handler._json_error(400, error)
            return
        return original_post(handler)

    server.DashboardHandler.do_GET = do_get
    server.DashboardHandler.do_POST = do_post
    server.DashboardHandler._kz_ai_gateway_patched = True
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
