"""R8-11 HTTP endpoints for Mission ledger, channel registry and backbone sync."""
from __future__ import annotations

from urllib.parse import urlsplit

from backend import server
from core.mission_ledger import snapshot as mission_ledger_snapshot, sync_backbone
from integrations.channel_registry import snapshot as channel_registry_snapshot

_INSTALLED = False


def install():
    global _INSTALLED
    if _INSTALLED:
        return
    original_get = server.DashboardHandler.do_GET
    original_post = server.DashboardHandler.do_POST

    def do_get(handler):
        path = urlsplit(handler.path).path
        try:
            if path == "/api/r8-11/mission-ledger":
                handler._json_ok(mission_ledger_snapshot())
                return
            if path == "/api/r8-11/channels":
                handler._json_ok(channel_registry_snapshot())
                return
            if path == "/api/r8-11/backbone":
                ledger = mission_ledger_snapshot()
                handler._json_ok({
                    "status": "available",
                    "active_mission": ledger.get("active_mission"),
                    "channel_summary": (ledger.get("channel_registry") or {}).get("summary") or {},
                    "control_bus": ledger.get("control_bus") or {},
                    "truth_rule": ledger.get("truth_rule"),
                })
                return
        except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
            handler._json_error(500, error)
            return
        return original_get(handler)

    def do_post(handler):
        path = urlsplit(handler.path).path
        if path == "/api/r8-11/backbone/sync":
            origin = handler.headers.get("Origin")
            allowed = {f"http://127.0.0.1:{handler.server.server_port}", f"http://localhost:{handler.server.server_port}"}
            if origin and origin not in allowed:
                handler._json_error(403, "Cross-origin changes are not allowed")
                return
            result = sync_backbone()
            handler._json_ok(result, code=200)
            return
        return original_post(handler)

    server.DashboardHandler.do_GET = do_get
    server.DashboardHandler.do_POST = do_post
    server.DashboardHandler._kz_r8_11_backbone_patched = True
    _INSTALLED = True


install()
