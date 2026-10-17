"""R8-11 HTTP endpoints for Mission ledger, channel registry and backbone sync."""
from __future__ import annotations

import json
from urllib.parse import urlsplit

from backend import server
# R8-11 makes the existing PRIVATE async Control Bus an explicit runtime
# dependency so normal ChatGPT Decision Pack/Receipt polling is always active.
from backend import async_control_bus_patch as _async_control_bus_patch  # noqa: F401,E402
# Install recovery/publish convergence before run.py imports scheduler callables.
from promotion import r8_11_runtime_convergence_patch as _r8_11_runtime_convergence_patch  # noqa: F401,E402
# R8-12 upgrades temporary bindings into durable account assets + device pool.
from backend import r8_12_account_center_patch as _r8_12_account_center_patch  # noqa: F401,E402
from core.mission_ledger import snapshot as mission_ledger_snapshot, sync_backbone
from core.command_execution import reconcile as command_execution_reconcile, status as command_execution_status
from integrations.channel_registry import snapshot as channel_registry_snapshot
from integrations.channel_router import build_routes as channel_routes_snapshot
from integrations.social_session_probe import confirm_owner_login, verify_pending_accounts

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
            if path == "/api/r8-11/mission-ledger":
                handler._json_ok(mission_ledger_snapshot())
                return
            if path == "/api/r8-11/channels":
                handler._json_ok(channel_registry_snapshot())
                return
            if path == "/api/r8-11/channel-routes":
                handler._json_ok(channel_routes_snapshot())
                return
            if path == "/api/r8-11/backbone":
                ledger = mission_ledger_snapshot()
                routes = channel_routes_snapshot(ledger.get("active_mission") or {})
                handler._json_ok({
                    "status": "available",
                    "active_mission": ledger.get("active_mission"),
                    "channel_summary": (ledger.get("channel_registry") or {}).get("summary") or {},
                    "route_summary": routes.get("summary") or {},
                    "control_bus": ledger.get("control_bus") or {},
                    "truth_rule": ledger.get("truth_rule"),
                })
                return
            if path == "/api/r8-18/control-loop":
                handler._json_ok(command_execution_status())
                return
            # Account/device pages already refresh these endpoints. Use that
            # existing cadence to run a throttled read-only ADB session probe.
            # Probe failure must never break the owner dashboard.
            if path in {"/api/r8/social", "/api/content-factory"}:
                try:
                    verify_pending_accounts(force=False)
                except (OSError, ValueError, RuntimeError, TypeError, KeyError):
                    pass
        except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
            handler._json_error(500, error)
            return
        return original_get(handler)

    def do_post(handler):
        path = urlsplit(handler.path).path
        if path == "/api/r8-11/backbone/sync":
            if not _origin_allowed(handler):
                handler._json_error(403, "Cross-origin changes are not allowed")
                return
            result = sync_backbone()
            handler._json_ok(result, code=200)
            return
        if path == "/api/r8-18/control-loop/reconcile":
            if not _origin_allowed(handler):
                handler._json_error(403, "Cross-origin changes are not allowed")
                return
            handler._json_ok(command_execution_reconcile(), code=200)
            return
        if path == "/api/r8-11/social/verify":
            if not _origin_allowed(handler):
                handler._json_error(403, "Cross-origin changes are not allowed")
                return
            try:
                result = verify_pending_accounts(force=True)
            except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
                handler._json_error(400, error)
                return
            handler._json_ok(result, code=200)
            return
        if path == "/api/r8-11/social/confirm-login":
            if not _origin_allowed(handler):
                handler._json_error(403, "Cross-origin changes are not allowed")
                return
            try:
                payload = _read_json_body(handler)
                result = confirm_owner_login(payload.get("account_id"))
            except (OSError, ValueError, RuntimeError, TypeError, KeyError, json.JSONDecodeError) as error:
                handler._json_error(400, error)
                return
            handler._json_ok(result, code=200)
            return
        return original_post(handler)

    server.DashboardHandler.do_GET = do_get
    server.DashboardHandler.do_POST = do_post
    server.DashboardHandler._kz_r8_11_backbone_patched = True
    server.DashboardHandler._kz_r8_11_social_session_probe = True
    _INSTALLED = True


install()
