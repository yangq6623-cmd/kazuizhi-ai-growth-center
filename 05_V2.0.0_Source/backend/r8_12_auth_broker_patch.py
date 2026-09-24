"""Official authorization launcher for the R8-12 durable account center.

This bridge never receives platform passwords. It returns official provider URLs
for the owner UI to open in the system browser/new window. OAuth callback/token
exchange remains provider-specific and must pass truthful identity verification
before an Account Asset can be marked connected.
"""
from __future__ import annotations

import json
from urllib.parse import urlsplit

from backend import server
from integrations.platform_auth_catalog import catalog, pending_requests, start_authorization

_INSTALLED = False


def _origin_allowed(handler):
    origin = handler.headers.get("Origin")
    allowed = {
        f"http://127.0.0.1:{handler.server.server_port}",
        f"http://localhost:{handler.server.server_port}",
    }
    return not origin or origin in allowed


def _read_json_body(handler):
    length = int(handler.headers.get("Content-Length", "0") or 0)
    if length < 0 or length > 64 * 1024:
        raise ValueError("请求内容过大")
    if not length:
        return {}
    return json.loads(handler.rfile.read(length) or b"{}")


def install():
    global _INSTALLED
    if _INSTALLED:
        return

    original_get = server.DashboardHandler.do_GET
    original_post = server.DashboardHandler.do_POST

    def do_get(handler):
        path = urlsplit(handler.path).path
        try:
            if path == "/api/r8-12/auth/catalog":
                payload = catalog()
                payload["pending"] = pending_requests()
                handler._json_ok(payload)
                return
        except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
            handler._json_error(400, error)
            return
        return original_get(handler)

    def do_post(handler):
        path = urlsplit(handler.path).path
        if path != "/api/r8-12/auth/start":
            return original_post(handler)
        if not _origin_allowed(handler):
            handler._json_error(403, "Cross-origin changes are not allowed")
            return
        try:
            payload = _read_json_body(handler)
            platform = str(payload.get("platform") or "").strip()
            slot_label = str(payload.get("slot_label") or "").strip()
            redirect_uri = str(payload.get("redirect_uri") or "").strip()
            if not platform:
                raise ValueError("platform 不能为空")
            result = start_authorization(platform, slot_label=slot_label, redirect_uri=redirect_uri)
            handler._json_ok(result)
        except (OSError, ValueError, RuntimeError, TypeError, KeyError, json.JSONDecodeError) as error:
            handler._json_error(400, error)

    server.DashboardHandler.do_GET = do_get
    server.DashboardHandler.do_POST = do_post
    server.DashboardHandler._kz_r8_12_auth_broker = True
    _INSTALLED = True


install()
