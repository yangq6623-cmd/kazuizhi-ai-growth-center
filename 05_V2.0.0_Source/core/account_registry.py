"""R8-12 unified account asset registry.

Accounts are durable business assets. Mission, service scope and device routing
reference a stable ``account_id`` instead of re-binding platform identity every
run. Secrets/tokens are intentionally excluded from this registry.
"""
from __future__ import annotations

import hashlib

from core.storage import now_iso, read_json, write_json
from core import r8_control

REGISTRY_PATH = "r8_12/account_registry.json"
DEVICE_PATH = "r8_12/device_pool.json"
SCHEMA = "kz.account-registry.v1"
DEVICE_SCHEMA = "kz.device-pool.v1"
PLATFORM_CODE = {
    "douyin": "DY",
    "kuaishou": "KS",
    "xiaohongshu": "XHS",
    "wechat_channels": "WXSPH",
    "weibo": "WB",
    "bilibili": "BL",
    "forum": "FORUM",
    "blog": "BLOG",
    "other": "OTHER",
}


def _stable_account_id(platform: str, seed: str) -> str:
    code = PLATFORM_CODE.get(platform, "OTHER")
    digest = hashlib.sha256(f"{platform}|{seed}".encode("utf-8")).hexdigest()[:10].upper()
    return f"ACC-{code}-{digest}"


def _stable_device_id(device_id: str) -> str:
    safe = "".join(ch if ch.isalnum() else "-" for ch in str(device_id or "").upper()).strip("-")
    return f"DEV-{safe or 'UNKNOWN'}"


def _normalize_region(value: str) -> str:
    text = str(value or "").strip()
    return "涟水县" if text in {"涟水", "涟水县"} else text


def _auth_state(login_status: str) -> str:
    return {
        "authorized": "connected",
        "needs_human": "needs_authorization",
        "logged_out": "needs_authorization",
        "not_verified": "needs_authorization",
    }.get(str(login_status or ""), "needs_authorization")


def _account_snapshot(account: dict) -> dict:
    return {
        "account_id": account.get("account_id"),
        "platform": account.get("platform"),
        "platform_name": account.get("platform_name"),
        "display_name": account.get("display_name"),
        "auth_status": (account.get("auth") or {}).get("status"),
        "auth_method": (account.get("auth") or {}).get("method"),
        "service_scope": account.get("service_scope") or {},
        "region_scope": account.get("region_scope") or {},
        "preferred_device_id": account.get("preferred_device_id"),
        "legacy_account_ids": account.get("legacy_account_ids") or [],
        "updated_at": account.get("updated_at"),
    }


def migrate_legacy_assets() -> dict:
    """Import legacy R8 accounts/devices without changing their platform truth."""
    state = r8_control.control_status()
    registry = read_json(REGISTRY_PATH, {})
    registry = registry if isinstance(registry, dict) else {}
    registry.setdefault("schema", SCHEMA)
    registry.setdefault("accounts", [])
    registry.setdefault("migrations", [])

    device_pool = read_json(DEVICE_PATH, {})
    device_pool = device_pool if isinstance(device_pool, dict) else {}
    device_pool.setdefault("schema", DEVICE_SCHEMA)
    device_pool.setdefault("devices", [])

    device_map = {}
    for legacy in state.get("devices", []):
        if not isinstance(legacy, dict):
            continue
        legacy_id = str(legacy.get("device_id") or "").strip()
        if not legacy_id:
            continue
        stable_id = _stable_device_id(legacy_id)
        device_map[legacy_id] = stable_id
        existing = next((x for x in device_pool["devices"] if x.get("device_id") == stable_id), None)
        row = {
            "device_id": stable_id,
            "legacy_device_id": legacy_id,
            "label": legacy.get("label") or legacy_id,
            "device_type": "real_android",
            "connection": legacy.get("connection") or "unknown",
            "health": legacy.get("health") or "unknown",
            "probe_source": legacy.get("probe_source"),
            "last_seen_at": legacy.get("last_seen_at"),
            "created_at": (existing or {}).get("created_at") or legacy.get("created_at") or now_iso(),
            "updated_at": now_iso(),
        }
        if existing:
            existing.update(row)
        else:
            device_pool["devices"].append(row)

    migrated = []
    for legacy in state.get("accounts", []):
        if not isinstance(legacy, dict):
            continue
        platform = str(legacy.get("platform") or "").strip()
        alias = str(legacy.get("alias") or legacy.get("label") or "").strip()
        if not platform or not alias:
            continue
        legacy_account_id = str(legacy.get("account_id") or "").strip()
        existing = next(
            (
                x for x in registry["accounts"]
                if legacy_account_id and legacy_account_id in (x.get("legacy_account_ids") or [])
            ),
            None,
        )
        if existing is None:
            existing = next(
                (x for x in registry["accounts"] if x.get("platform") == platform and x.get("display_name") == alias),
                None,
            )
        account_id = (existing or {}).get("account_id") or _stable_account_id(platform, alias)
        current_service = str(legacy.get("service_category") or "").strip()
        all_services = alias == "卡嘴子本地服务维修" or current_service in {"综合服务", "本地生活服务", "全部本地服务"}
        current_region = _normalize_region(legacy.get("region"))
        auth = {
            "status": _auth_state(legacy.get("login_status")),
            "method": "real_device_verified" if legacy.get("login_status") == "authorized" else "legacy_real_device",
            "platform_subject_id": (existing or {}).get("auth", {}).get("platform_subject_id"),
            "scopes": (existing or {}).get("auth", {}).get("scopes") or [],
            "expires_at": (existing or {}).get("auth", {}).get("expires_at"),
            "last_verified_at": legacy.get("login_verified_at"),
            "reauthorization_required": legacy.get("login_status") != "authorized",
        }
        row = {
            "account_id": account_id,
            "platform": platform,
            "platform_name": legacy.get("platform_name") or r8_control.PLATFORMS.get(platform, platform),
            "display_name": alias,
            "auth": auth,
            "service_scope": {
                "all_local_services": bool(all_services),
                "services": [] if all_services else ([current_service] if current_service else []),
            },
            "region_scope": {
                "all_regions": False,
                "regions": [current_region] if current_region else [],
            },
            "preferred_device_id": device_map.get(str(legacy.get("device_id") or "").strip()),
            "legacy_account_ids": sorted(set(((existing or {}).get("legacy_account_ids") or []) + ([legacy_account_id] if legacy_account_id else []))),
            "source": (existing or {}).get("source") or "r8_legacy_migration",
            "created_at": (existing or {}).get("created_at") or legacy.get("created_at") or now_iso(),
            "updated_at": now_iso(),
        }
        if existing:
            existing.update(row)
        else:
            registry["accounts"].append(row)
        migrated.append(account_id)

    registry["migrations"].append({
        "at": now_iso(),
        "kind": "r8_legacy_account_device_import",
        "migrated_accounts": migrated,
        "truth": "迁移只建立稳定身份映射；不生成平台登录、发布或授权成功。",
    })
    registry["updated_at"] = now_iso()
    device_pool["updated_at"] = now_iso()
    write_json(REGISTRY_PATH, registry)
    write_json(DEVICE_PATH, device_pool)
    return snapshot()


def snapshot() -> dict:
    registry = read_json(REGISTRY_PATH, {})
    if not isinstance(registry, dict) or registry.get("schema") != SCHEMA:
        return migrate_legacy_assets()
    device_pool = read_json(DEVICE_PATH, {})
    if not isinstance(device_pool, dict) or device_pool.get("schema") != DEVICE_SCHEMA:
        return migrate_legacy_assets()
    accounts = [x for x in registry.get("accounts", []) if isinstance(x, dict)]
    devices = [x for x in device_pool.get("devices", []) if isinstance(x, dict)]
    return {
        "schema": SCHEMA,
        "accounts": [_account_snapshot(x) for x in accounts],
        "devices": devices,
        "summary": {
            "accounts": len(accounts),
            "connected_accounts": sum(1 for x in accounts if (x.get("auth") or {}).get("status") == "connected"),
            "needs_authorization": sum(1 for x in accounts if (x.get("auth") or {}).get("status") == "needs_authorization"),
            "online_devices": sum(1 for x in devices if x.get("connection") == "connected"),
        },
        "truth_rule": "账号身份长期保留；授权可刷新，设备可替换，Mission 只引用 account_id。没有真实平台回执不得记为已发布。",
        "updated_at": max(str(registry.get("updated_at") or ""), str(device_pool.get("updated_at") or "")),
    }


def update_scope(account_id: str, *, all_services=None, services=None, all_regions=None, regions=None, preferred_device_id=None) -> dict:
    registry = read_json(REGISTRY_PATH, {})
    if not isinstance(registry, dict) or registry.get("schema") != SCHEMA:
        migrate_legacy_assets()
        registry = read_json(REGISTRY_PATH, {})
    account = next((x for x in registry.get("accounts", []) if x.get("account_id") == account_id), None)
    if not account:
        raise ValueError("账号资产不存在")
    if all_services is not None:
        account.setdefault("service_scope", {})["all_local_services"] = bool(all_services)
    if services is not None:
        account.setdefault("service_scope", {})["services"] = [str(x).strip() for x in services if str(x).strip()][:50]
    if all_regions is not None:
        account.setdefault("region_scope", {})["all_regions"] = bool(all_regions)
    if regions is not None:
        account.setdefault("region_scope", {})["regions"] = [_normalize_region(x) for x in regions if str(x).strip()][:50]
    if preferred_device_id is not None:
        account["preferred_device_id"] = str(preferred_device_id or "").strip() or None
    account["updated_at"] = now_iso()
    registry["updated_at"] = now_iso()
    write_json(REGISTRY_PATH, registry)
    return _account_snapshot(account)


def set_auth_state(account_id: str, status: str, *, method=None, platform_subject_id=None, scopes=None, expires_at=None) -> dict:
    if status not in {"connected", "needs_authorization", "platform_limited", "disabled"}:
        raise ValueError("账号授权状态不支持")
    registry = read_json(REGISTRY_PATH, {})
    if not isinstance(registry, dict) or registry.get("schema") != SCHEMA:
        migrate_legacy_assets()
        registry = read_json(REGISTRY_PATH, {})
    account = next((x for x in registry.get("accounts", []) if x.get("account_id") == account_id), None)
    if not account:
        raise ValueError("账号资产不存在")
    auth = account.setdefault("auth", {})
    auth["status"] = status
    auth["reauthorization_required"] = status == "needs_authorization"
    if method is not None:
        auth["method"] = method
    if platform_subject_id is not None:
        auth["platform_subject_id"] = str(platform_subject_id or "")[:200] or None
    if scopes is not None:
        auth["scopes"] = [str(x)[:120] for x in scopes][:100]
    if expires_at is not None:
        auth["expires_at"] = expires_at
    if status == "connected":
        auth["last_verified_at"] = now_iso()
    account["updated_at"] = now_iso()
    registry["updated_at"] = now_iso()
    write_json(REGISTRY_PATH, registry)
    return _account_snapshot(account)
