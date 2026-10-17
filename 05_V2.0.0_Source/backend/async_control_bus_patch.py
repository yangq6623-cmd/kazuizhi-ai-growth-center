"""HTTP/runtime adapter for the private asynchronous ChatGPT control bus."""
from __future__ import annotations

import ipaddress
from urllib.parse import urlsplit

from backend import server
from integrations.async_control_bus import recent_receipts, start_background_agent, status, sync_once

_INSTALLED = False


def _client_is_loopback(handler) -> bool:
    try:
        host = str((handler.client_address or ("", 0))[0] or "")
        return ipaddress.ip_address(host).is_loopback
    except (ValueError, TypeError):
        return False


def _origin_allowed(handler) -> bool:
    if not _client_is_loopback(handler):
        return False
    origin = str(handler.headers.get("Origin") or "").strip()
    return not origin or origin in {
        f"http://127.0.0.1:{handler.server.server_port}",
        f"http://localhost:{handler.server.server_port}",
    }


def install():
    global _INSTALLED
    if _INSTALLED:
        return
    original_get = server.DashboardHandler.do_GET
    original_post = server.DashboardHandler.do_POST

    def do_get(handler):
        path = urlsplit(handler.path).path
        if path.startswith("/api/async-control-bus/") and not _client_is_loopback(handler):
            handler._json_error(403, "异步控制总线状态只允许本机读取")
            return
        try:
            if path == "/api/async-control-bus/status":
                handler._json_ok(status())
                return
            if path == "/api/async-control-bus/receipts":
                handler._json_ok({"items": recent_receipts(50)})
                return
        except (OSError, ValueError, RuntimeError, TypeError) as error:
            handler._json_error(500, error)
            return
        return original_get(handler)

    def do_post(handler):
        path = urlsplit(handler.path).path
        if path != "/api/async-control-bus/sync":
            return original_post(handler)
        if not _origin_allowed(handler):
            handler._json_error(403, "异步控制总线同步只允许当前本机工作台触发")
            return
        try:
            result = sync_once()
            handler._json_ok(result, code=200 if result.get("synced") else 202)
        except (OSError, ValueError, RuntimeError, TypeError) as error:
            handler._json_error(409, error)

    server.DashboardHandler.do_GET = do_get
    server.DashboardHandler.do_POST = do_post
    server.DashboardHandler._kz_async_control_bus_patched = True
    _INSTALLED = True
    start_background_agent()


install()
