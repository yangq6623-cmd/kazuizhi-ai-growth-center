"""Localhost-only HTTP adapter for Kazuizhi Site Tools/WebMCP control."""
from __future__ import annotations

import ipaddress
import json
from urllib.parse import urlsplit

from backend import server
from integrations.kz_local_control import (
    execute_tool,
    pair_webmcp,
    recent_audit,
    status,
    tool_catalog,
)

_INSTALLED = False
SITE_TOOLS_MARKER = "webmcp-local"


def _client_is_loopback(handler) -> bool:
    try:
        host = str((handler.client_address or ("", 0))[0] or "")
        return ipaddress.ip_address(host).is_loopback
    except (ValueError, TypeError):
        return False


def _origin_allowed(handler) -> bool:
    if not _client_is_loopback(handler):
        return False
    if str(handler.headers.get("X-KZ-Site-Tools") or "").strip() != SITE_TOOLS_MARKER:
        return False
    origin = str(handler.headers.get("Origin") or "").strip()
    if not origin:
        # Non-browser/local automation clients are not accepted on the preferred
        # WebMCP path. Remote/unattended automation must use the signed Relay.
        return False
    return origin in {
        f"http://127.0.0.1:{handler.server.server_port}",
        f"http://localhost:{handler.server.server_port}",
    }


def _read_json(handler, *, max_bytes=64 * 1024):
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0 or length > max_bytes:
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
        if path.startswith("/api/kz-local-control/") and not _client_is_loopback(handler):
            handler._json_error(403, "KZ Local Control 只允许本机访问")
            return
        try:
            if path == "/api/kz-local-control/status":
                handler._json_ok(status())
                return
            if path == "/api/kz-local-control/tools":
                handler._json_ok({"items": tool_catalog()})
                return
            if path == "/api/kz-local-control/audit":
                handler._json_ok({"items": recent_audit(50)})
                return
        except (OSError, ValueError, RuntimeError, TypeError) as error:
            handler._json_error(500, error)
            return
        return original_get(handler)

    def do_post(handler):
        path = urlsplit(handler.path).path
        if path not in {"/api/kz-local-control/pair", "/api/kz-local-control/tool"}:
            return original_post(handler)
        if not _origin_allowed(handler):
            handler._json_error(403, "KZ Local Control 只接受当前本机工作台的 Site Tools 调用")
            return
        try:
            payload = _read_json(handler)
            if path.endswith("/pair"):
                result = pair_webmcp(payload)
                handler._json_ok(result, code=200)
                return
            result = execute_tool(
                payload.get("tool"),
                payload.get("args") if isinstance(payload.get("args"), dict) else {},
                request_id=payload.get("request_id"),
            )
            handler._json_ok(result, code=200)
        except json.JSONDecodeError as error:
            handler._json_error(400, error)
        except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
            handler._json_error(409, error)

    server.DashboardHandler.do_GET = do_get
    server.DashboardHandler.do_POST = do_post
    server.DashboardHandler._kz_local_control_patched = True
    _INSTALLED = True


install()
