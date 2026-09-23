"""R8-10 HTTP contract for the ChatGPT control connector."""
from __future__ import annotations

import json
from urllib.parse import urlsplit

from backend import server
from backend import r8_10_idempotency_patch as _r8_10_idempotency_patch  # noqa: F401,E402
from integrations.chatgpt_control import (
    control_status,
    create_owner_command,
    primary_blocker,
    recent_commands,
    recent_receipts,
)
from integrations.chatgpt_connector_adapter import (
    adapter_status,
    process_envelope,
    recent_audit as connector_audit,
)

_INSTALLED = False


def _origin_allowed(handler):
    origin = handler.headers.get("Origin")
    return not origin or origin in {
        f"http://127.0.0.1:{handler.server.server_port}",
        f"http://localhost:{handler.server.server_port}",
    }


def _read_json(handler, *, max_bytes=16 * 1024):
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0 or length > max_bytes:
        raise ValueError("请求大小不正确")
    return json.loads(handler.rfile.read(length) or b"{}")


def _owner_primary_blocker() -> dict:
    """Realtime ChatGPT offline is advisory, not a global autonomy failure."""
    item = primary_blocker()
    if item.get("code") == "chatgpt_not_verified":
        return {
            "code": "none",
            "severity": 0,
            "blocking": False,
            "title": "无总控阻塞",
            "detail": "实时 ChatGPT 当前未验证连接，但已批准 Mission 可继续本地自治。需要新高层决策时使用异步控制总线或实时辅助通道。",
            "advisory": item,
        }
    result = dict(item)
    result.setdefault("blocking", result.get("code") != "none")
    return result


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
                handler._json_ok(_owner_primary_blocker())
                return
            if path == "/api/chatgpt-connector/status":
                handler._json_ok(adapter_status())
                return
            if path == "/api/chatgpt-connector/audit":
                handler._json_ok({"items": connector_audit(50)})
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
                handler._json_error(409, error)
            return

        if path == "/api/chatgpt-connector/envelope":
            try:
                envelope = _read_json(handler, max_bytes=64 * 1024)
                result = process_envelope(envelope)
                handler._json_ok(result, code=200)
            except json.JSONDecodeError as error:
                handler._json_error(400, error)
            except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
                handler._json_error(403, error)
            return

        return original_post(handler)

    server.DashboardHandler.do_GET = do_get
    server.DashboardHandler.do_POST = do_post
    server.DashboardHandler._kz_r8_10_control_patched = True
    _INSTALLED = True


install()
