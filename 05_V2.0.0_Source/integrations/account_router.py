"""R8-12 account/device routing over durable account assets."""
from __future__ import annotations

from core.account_registry import snapshot


def _service_match(scope: dict, service: str) -> bool:
    if scope.get("all_local_services"):
        return True
    wanted = str(service or "").strip()
    return not wanted or wanted in (scope.get("services") or [])


def _region_match(scope: dict, region: str) -> bool:
    if scope.get("all_regions"):
        return True
    wanted = str(region or "").strip()
    if wanted == "涟水":
        wanted = "涟水县"
    return not wanted or wanted in (scope.get("regions") or [])


def route_account(*, platform: str, region: str = "", service: str = "") -> dict:
    data = snapshot()
    devices = {x.get("device_id"): x for x in data.get("devices", []) if isinstance(x, dict)}
    candidates = []
    authorization_blocked = []
    for account in data.get("accounts", []):
        if not isinstance(account, dict) or account.get("platform") != platform:
            continue
        if not _region_match(account.get("region_scope") or {}, region):
            continue
        if not _service_match(account.get("service_scope") or {}, service):
            continue
        if account.get("auth_status") != "connected":
            authorization_blocked.append(account)
            continue
        device = devices.get(account.get("preferred_device_id"))
        ready = bool(device and device.get("connection") == "connected")
        candidates.append((ready, account, device))

    if candidates:
        candidates.sort(key=lambda row: (bool(row[0]), str(row[1].get("updated_at") or "")), reverse=True)
        ready, account, device = candidates[0]
        if ready:
            return {
                "status": "ready",
                "owner_status": "已连接",
                "account": account,
                "device": device,
                "route": "api_or_device",
                "truth": "账号身份与设备解耦；实际发布仍需平台真实回执。",
            }
        return {
            "status": "device_offline",
            "owner_status": "设备离线",
            "account": account,
            "device": device,
            "route": "wait_device",
        }

    if authorization_blocked:
        return {
            "status": "needs_authorization",
            "owner_status": "需授权",
            "account": authorization_blocked[0],
            "device": None,
            "route": "reauthorize",
        }

    return {
        "status": "no_matching_account",
        "owner_status": "未添加账号",
        "account": None,
        "device": None,
        "route": "add_account",
    }
