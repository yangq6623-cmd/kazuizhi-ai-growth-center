"""R8-12 unified Account Asset / Device Pool HTTP bridge.

The owner surface reads durable account identities.  Legacy account binding is
migration input only and no longer the normal routing source of truth.
"""
from __future__ import annotations

import json
from urllib.parse import parse_qs, urlsplit

from backend import server
from core.account_registry import (
    migrate_legacy_assets,
    recover_assets_if_degraded,
    snapshot as account_snapshot,
    update_scope,
)
from integrations.account_router import route_account
from integrations.credential_vault import status as vault_status
from integrations.oauth_adapters import all_provider_status, provider_status

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
    if length < 0 or length > 128 * 1024:
        raise ValueError("请求内容过大")
    if not length:
        return {}
    return json.loads(handler.rfile.read(length) or b"{}")


def _center_payload() -> dict:
    recovery = recover_assets_if_degraded()
    payload = account_snapshot()
    payload["oauth"] = all_provider_status()
    payload["credential_vault"] = vault_status()
    payload["recovery"] = recovery
    payload["architecture"] = {
        "identity_model": "durable_account_asset",
        "authorization_model": "replaceable_authorization",
        "device_model": "independent_device_pool",
        "mission_binding": "account_id_reference_only",
        "publication_truth": "receipt_gated",
    }
    return payload


def install():
    global _INSTALLED
    if _INSTALLED:
        return
    try:
        recover_assets_if_degraded()
        migrate_legacy_assets()
    except (OSError, ValueError, RuntimeError, TypeError, KeyError):
        pass

    original_get = server.DashboardHandler.do_GET
    original_post = server.DashboardHandler.do_POST

    def do_get(handler):
        parsed = urlsplit(handler.path)
        path = parsed.path
        try:
            if path == "/api/r8-12/account-center":
                handler._json_ok(_center_payload())
                return
            if path == "/api/r8-12/accounts":
                data = account_snapshot()
                handler._json_ok({
                    "accounts": data.get("accounts", []),
                    "summary": data.get("summary", {}),
                    "truth_rule": data.get("truth_rule"),
                })
                return
            if path == "/api/r8-12/devices":
                data = account_snapshot()
                handler._json_ok({"devices": data.get("devices", []), "summary": data.get("summary", {})})
                return
            if path == "/api/r8-12/oauth":
                query = parse_qs(parsed.query)
                platform = (query.get("platform") or [""])[0]
                handler._json_ok(provider_status(platform) if platform else all_provider_status())
                return
            if path == "/api/r8-12/route":
                query = parse_qs(parsed.query)
                result = route_account(
                    platform=(query.get("platform") or [""])[0],
                    region=(query.get("region") or [""])[0],
                    service=(query.get("service") or [""])[0],
                )
                handler._json_ok(result)
                return
            if path == "/api/r8-12/health":
                data = _center_payload()
                summary = data.get("summary") or {}
                handler._json_ok({
                    "status": "healthy" if summary.get("accounts") else "needs_account",
                    "summary": summary,
                    "recovery": data.get("recovery"),
                    "credential_vault": data.get("credential_vault"),
                    "architecture": data.get("architecture"),
                    "truth_rule": data.get("truth_rule"),
                })
                return
        except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
            handler._json_error(400, error)
            return
        return original_get(handler)

    def do_post(handler):
        path = urlsplit(handler.path).path
        allowed_paths = {
            "/api/r8-12/migrate",
            "/api/r8-12/recover-assets",
            "/api/r8-12/account/scope",
        }
        if path not in allowed_paths:
            return original_post(handler)
        if not _origin_allowed(handler):
            handler._json_error(403, "Cross-origin changes are not allowed")
            return
        try:
            if path == "/api/r8-12/migrate":
                handler._json_ok(migrate_legacy_assets())
                return
            if path == "/api/r8-12/recover-assets":
                handler._json_ok({
                    "recovery": recover_assets_if_degraded(),
                    "snapshot": account_snapshot(),
                    "truth": "只恢复已存在账号/设备资产，不补造登录、授权或发布成功。",
                })
                return
            payload = _read_json_body(handler)
            account_id = str(payload.get("account_id") or "").strip()
            result = update_scope(
                account_id,
                all_services=payload.get("all_services"),
                services=payload.get("services"),
                all_regions=payload.get("all_regions"),
                regions=payload.get("regions"),
                preferred_device_id=payload.get("preferred_device_id"),
            )
            handler._json_ok(result)
        except (OSError, ValueError, RuntimeError, TypeError, KeyError, json.JSONDecodeError) as error:
            handler._json_error(400, error)

    server.DashboardHandler.do_GET = do_get
    server.DashboardHandler.do_POST = do_post
    server.DashboardHandler._kz_r8_12_account_center = True
    server.DashboardHandler._kz_r8_12_durable_account_assets = True
    _INSTALLED = True


install()
