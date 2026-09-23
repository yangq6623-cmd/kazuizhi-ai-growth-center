"""R8-10 local HTTP contract for the ChatGPT control connector.

Owner-facing UI can read the canonical connector state, Command/Receipt audit
trail and the single primary blocker. There is intentionally no normal local UI
endpoint that can mark ChatGPT verified or fabricate receipts. Only an
authorized connector adapter may call the internal integration hooks after a
real external round trip.
"""
from __future__ import annotations

import json
from urllib.parse import urlsplit

from backend import server
from integrations.chatgpt_control import (
    control_status,
    create_owner_command,
    primary_blocker,
    recent_commands,
    recent_receipts,
)

_INSTALLED = False


def _origin_allowed(handler):
    origin = handler.headers.get("Origin")
    return not origin or origin in {
        f"http://127.0.0.1:{handler.server.server_port}",
        f"http://localhost:{handler.server.server_port}",
    }


def _read_json(handler):
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0 or length > 16 * 1024:
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
        try:
            if path == "/api/chatgpt-control/status":
                handler._json_ok(control_status())
                return
            if path == "/api/chatgpt-control/commands":
                handler._json_ok({"items": recent_commands(50)})
                return
            if path == "/api/chatgpt-control/receipts":
                handler._json_ok({"items": recent_receipts(50)})
                return
            if path == "/api/chatgpt-control/blocker":
                handler._json_ok(primary_blocker())
                return
        except (OSError, ValueError, RuntimeError, TypeError) as error:
            handler._json_error(500, error)
            return
        return original_get(handler)

    def do_post(handler):
        path = urlsplit(handler.path).path
        if path == "/api/chatgpt-control/commands":
            if not _origin_allowed(handler):
                handler._json_error(403, "Cross-origin changes are not allowed")
                return
            try:
                result = create_owner_command(_read_json(handler))
                handler._json_ok(result, code=202)
            except (OSError, ValueError, RuntimeError, json.JSONDecodeError) as error:
                # A non-verified connector is a business precondition failure,
                # not a pretend success or an internal server failure.
                handler._json_error(409, error)
            return
        return original_post(handler)

    server.DashboardHandler.do_GET = do_get
    server.DashboardHandler.do_POST = do_post
    server.DashboardHandler._kz_r8_10_control_patched = True
    _INSTALLED = True


install()
