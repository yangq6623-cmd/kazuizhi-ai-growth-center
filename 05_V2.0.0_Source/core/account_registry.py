"""R8-12 durable account and device asset registry.

The durable identity model is intentionally independent from Mission, service,
region and the phone currently used for execution.  Authorization can expire,
devices can be replaced and Missions can change without creating a new account
asset.

Secrets never enter this registry.  OAuth access/refresh tokens belong in the
local credential vault only.
"""
from __future__ import annotations

import hashlib
from copy import deepcopy

from core.storage import now_iso, read_json, write_json
from core import r8_control

REGISTRY_PATH = "r8_12/account_registry.json"
DEVICE_PATH = "r8_12/device_pool.json"
CHECKPOINT_PATH = "r8_12/account_assets_last_good.json"
AUDIT_PATH = "r8_12/account_asset_audit.json"
SCHEMA = "kz.account-registry.v2"
LEGACY_SCHEMA = "kz.account-registry.v1"
DEVICE_SCHEMA = "kz.device-pool.v2"
LEGACY_DEVICE_SCHEMA = "kz.device-pool.v1"
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


def _default_registry() -> dict:
    return {
        "schema": SCHEMA,
        "accounts": [],
        "migrations": [],
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }


def _default_devices() -> dict:
    return {
        "schema": DEVICE_SCHEMA,
        "devices": [],
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }


def _read_registry() -> dict:
    value = read_json(REGISTRY_PATH, {})
    if not isinstance(value, dict):
        return _default_registry()
    if value.get("schema") not in {SCHEMA, LEGACY_SCHEMA}:
        return _default_registry()
    value.setdefault("accounts", [])
    value.setdefault("migrations", [])
    value.setdefault("created_at", now_iso())
    value["schema"] = SCHEMA
    return value


def _read_devices() -> dict:
    value = read_json(DEVICE_PATH, {})
    if not isinstance(value, dict):
        return _default_devices()
    if value.get("schema") not in {DEVICE_SCHEMA, LEGACY_DEVICE_SCHEMA}:
        return _default_devices()
    value.setdefault("devices", [])
    value.setdefault("created_at", now_iso())
    value["schema"] = DEVICE_SCHEMA
    return value


def _append_audit(kind: str, *, account_id=None, device_id=None, detail=None) -> None:
    payload = read_json(AUDIT_PATH, {})
    payload = payload if isinstance(payload, dict) else {}
    payload.setdefault("schema", "kz.account-asset-audit.v1")
    payload.setdefault("events", [])
    payload["events"].insert(0, {
        "at": now_iso(),
        "kind": kind,
        "account_id": account_id,
        "device_id": device_id,
        "detail": detail if isinstance(detail, dict) else {},
    })
    payload["events"] = payload["events"][:500]
    payload["updated_at"] = now_iso()
    write_json(AUDIT_PATH, payload)


def _asset_quality(registry: dict, device_pool: dict) -> tuple[int, int, int, int]:
    accounts = [x for x in registry.get("accounts", []) if isinstance(x, dict) and x.get("account_id")]
    devices = [x for x in device_pool.get("devices", []) if isinstance(x, dict) and x.get("device_id")]
    identified = sum(1 for x in accounts if x.get("display_name") and x.get("platform"))
    connected = sum(1 for x in accounts if (x.get("auth") or {}).get("status") == "connected")
    return (len(accounts), identified, connected, len(devices))


def _save_checkpoint(registry: dict, device_pool: dict, reason: str) -> None:
    """Save only a non-degrading account/device checkpoint.

    A blank/partial runtime must never replace a richer last-known-good asset
    snapshot.  Connected count may legitimately fall when authorization expires,
    so account/device cardinality is the primary monotonic guard.
    """
    current_quality = _asset_quality(registry, device_pool)
    if current_quality[0] == 0 and current_quality[3] == 0:
        return
    previous = read_json(CHECKPOINT_PATH, {})
    previous_registry = previous.get("registry") if isinstance(previous, dict) else None
    previous_devices = previous.get("device_pool") if isinstance(previous, dict) else None
    previous_quality = _asset_quality(
        previous_registry if isinstance(previous_registry, dict) else {},
        previous_devices if isinstance(previous_devices, dict) else {},
    )
    # Never let a lower-cardinality transient state replace the richer snapshot.
    if previous_quality[0] > current_quality[0] or previous_quality[3] > current_quality[3]:
        return
    write_json(CHECKPOINT_PATH, {
        "schema": "kz.account-assets-checkpoint.v1",
        "saved_at": now_iso(),
        "reason": str(reason or "state_change")[:120],
        "quality": {
            "accounts": current_quality[0],
            "identified_accounts": current_quality[1],
            "connected_accounts": current_quality[2],
            "devices": current_quality[3],
        },
        "registry": deepcopy(registry),
        "device_pool": deepcopy(device_pool),
        "truth_rule": "恢复只能补回已存在账号/设备资产；不会补造平台登录、授权或发布成功。",
    })


def _merge_missing_assets(current: dict, fallback: dict, key: str) -> int:
    rows = current.setdefault(key, [])
    by_id = {
        str(x.get("account_id") or x.get("device_id") or ""): x
        for x in rows if isinstance(x, dict)
    }
    restored = 0
    for candidate in fallback.get(key, []) if isinstance(fallback, dict) else []:
        if not isinstance(candidate, dict):
            continue
        identifier = str(candidate.get("account_id") or candidate.get("device_id") or "")
        if not identifier:
            continue
        existing = by_id.get(identifier)
        if existing is None:
            rows.append(deepcopy(candidate))
            by_id[identifier] = rows[-1]
            restored += 1
            continue
        # Partial corruption recovery: only fill missing structural fields.
        for field, value in candidate.items():
            if field in {"auth", "updated_at"}:
                continue
            if existing.get(field) in {None, "", [], {}} and value not in {None, "", [], {}}:
                existing[field] = deepcopy(value)
    return restored


def recover_assets_if_degraded() -> dict:
    registry = _read_registry()
    device_pool = _read_devices()
    checkpoint = read_json(CHECKPOINT_PATH, {})
    if not isinstance(checkpoint, dict):
        return {"restored": False, "reason": "no_checkpoint"}
    fallback_registry = checkpoint.get("registry") if isinstance(checkpoint.get("registry"), dict) else {}
    fallback_devices = checkpoint.get("device_pool") if isinstance(checkpoint.get("device_pool"), dict) else {}
    current_quality = _asset_quality(registry, device_pool)
    fallback_quality = _asset_quality(fallback_registry, fallback_devices)
    degraded = current_quality[0] < fallback_quality[0] or current_quality[3] < fallback_quality[3]
    if not degraded:
        return {"restored": False, "reason": "current_not_degraded"}
    restored_accounts = _merge_missing_assets(registry, fallback_registry, "accounts")
    restored_devices = _merge_missing_assets(device_pool, fallback_devices, "devices")
    if restored_accounts or restored_devices:
        registry["schema"] = SCHEMA
        device_pool["schema"] = DEVICE_SCHEMA
        registry["updated_at"] = now_iso()
        device_pool["updated_at"] = now_iso()
        write_json(REGISTRY_PATH, registry)
        write_json(DEVICE_PATH, device_pool)
        _append_audit("asset_recovery", detail={
            "restored_accounts": restored_accounts,
            "restored_devices": restored_devices,
            "checkpoint_saved_at": checkpoint.get("saved_at"),
        })
        return {
            "restored": True,
            "accounts": restored_accounts,
            "devices": restored_devices,
            "source": "last_good_account_assets",
        }
    return {"restored": False, "reason": "nothing_missing_after_merge"}


def _account_snapshot(account: dict) -> dict:
    auth = account.get("auth") if isinstance(account.get("auth"), dict) else {}
    return {
        "account_id": account.get("account_id"),
        "platform": account.get("platform"),
        "platform_name": account.get("platform_name"),
        "display_name": account.get("display_name"),
        "auth_status": auth.get("status"),
        "auth_method": auth.get("method"),
        "platform_subject_id": auth.get("platform_subject_id"),
        "authorized_scopes": list(auth.get("scopes") or []),
        "expires_at": auth.get("expires_at"),
        "last_verified_at": auth.get("last_verified_at"),
        "reauthorization_required": bool(auth.get("reauthorization_required")),
        "service_scope": account.get("service_scope") or {},
        "region_scope": account.get("region_scope") or {},
        "preferred_device_id": account.get("preferred_device_id"),
        "legacy_account_ids": account.get("legacy_account_ids") or [],
        "source": account.get("source"),
        "created_at": account.get("created_at"),
        "updated_at": account.get("updated_at"),
    }


def _legacy_auth(existing: dict | None, legacy: dict) -> dict:
    """Import legacy truth without downgrading a previously connected asset."""
    current = deepcopy((existing or {}).get("auth") or {})
    incoming_status = _auth_state(legacy.get("login_status"))
    current_status = current.get("status")
    if current_status != "connected" or incoming_status == "connected":
        current["status"] = incoming_status
    current.setdefault("method", "legacy_real_device")
    if incoming_status == "connected":
        current["method"] = "real_device_verified"
        current["last_verified_at"] = legacy.get("login_verified_at") or current.get("last_verified_at") or now_iso()
        current["reauthorization_required"] = False
    else:
        current.setdefault("reauthorization_required", current.get("status") != "connected")
    current.setdefault("platform_subject_id", None)
    current.setdefault("scopes", [])
    current.setdefault("expires_at", None)
    return current


def migrate_legacy_assets() -> dict:
    """Idempotently import legacy R8 account/device truth into durable assets.

    Re-running migration may refresh device liveness and discover new legacy
    IDs, but it must not recreate identities or downgrade a connected durable
    account because an older legacy view temporarily says ``not_verified``.
    """
    recover_assets_if_degraded()
    state = r8_control.control_status()
    registry = _read_registry()
    device_pool = _read_devices()
    changed = False
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
            before = dict(existing)
            existing.update(row)
            changed = changed or before != existing
        else:
            device_pool["devices"].append(row)
            changed = True

    migrated = []
    for legacy in state.get("accounts", []):
        if not isinstance(legacy, dict):
            continue
        platform = str(legacy.get("platform") or "").strip()
        alias = str(legacy.get("alias") or legacy.get("label") or "").strip()
        if not platform or not alias:
            continue
        legacy_account_id = str(legacy.get("account_id") or "").strip()
        existing = next((
            x for x in registry["accounts"]
            if legacy_account_id and legacy_account_id in (x.get("legacy_account_ids") or [])
        ), None)
        if existing is None:
            existing = next((
                x for x in registry["accounts"]
                if x.get("platform") == platform and x.get("display_name") == alias
            ), None)
        account_id = (existing or {}).get("account_id") or _stable_account_id(platform, legacy_account_id or alias)
        current_service = str(legacy.get("service_category") or legacy.get("service") or "").strip()
        all_services = bool((existing or {}).get("service_scope", {}).get("all_local_services"))
        if alias == "卡嘴子本地服务维修" or current_service in {"综合服务", "本地生活服务", "全部本地服务"}:
            all_services = True
        existing_services = list((existing or {}).get("service_scope", {}).get("services") or [])
        if current_service and current_service not in existing_services and not all_services:
            existing_services.append(current_service)
        current_region = _normalize_region(legacy.get("region"))
        existing_regions = list((existing or {}).get("region_scope", {}).get("regions") or [])
        if current_region and current_region not in existing_regions:
            existing_regions.append(current_region)
        legacy_ids = sorted(set(((existing or {}).get("legacy_account_ids") or []) + ([legacy_account_id] if legacy_account_id else [])))
        row = {
            "account_id": account_id,
            "platform": platform,
            "platform_name": legacy.get("platform_name") or r8_control.PLATFORMS.get(platform, platform),
            "display_name": alias,
            "auth": _legacy_auth(existing, legacy),
            "service_scope": {
                "all_local_services": bool(all_services),
                "services": [] if all_services else existing_services[:50],
            },
            "region_scope": {
                "all_regions": bool((existing or {}).get("region_scope", {}).get("all_regions")),
                "regions": existing_regions[:50],
            },
            "preferred_device_id": (
                (existing or {}).get("preferred_device_id")
                or device_map.get(str(legacy.get("device_id") or "").strip())
            ),
            "legacy_account_ids": legacy_ids,
            "source": (existing or {}).get("source") or "r8_legacy_migration",
            "created_at": (existing or {}).get("created_at") or legacy.get("created_at") or now_iso(),
            "updated_at": now_iso(),
        }
        if existing:
            before = deepcopy(existing)
            existing.update(row)
            changed = changed or before != existing
        else:
            registry["accounts"].append(row)
            changed = True
        migrated.append(account_id)

    registry["schema"] = SCHEMA
    device_pool["schema"] = DEVICE_SCHEMA
    registry["updated_at"] = now_iso()
    device_pool["updated_at"] = now_iso()
    if changed:
        registry["migrations"].append({
            "at": now_iso(),
            "kind": "r8_legacy_account_device_import",
            "migrated_accounts": sorted(set(migrated)),
            "truth": "迁移只建立稳定身份映射；不生成平台登录、发布或授权成功。",
        })
        registry["migrations"] = registry["migrations"][-100:]
    write_json(REGISTRY_PATH, registry)
    write_json(DEVICE_PATH, device_pool)
    _save_checkpoint(registry, device_pool, "legacy_asset_migration")
    return snapshot(skip_migration=True)


def snapshot(*, skip_migration=False) -> dict:
    recover_assets_if_degraded()
    registry = _read_registry()
    device_pool = _read_devices()
    if not skip_migration and not registry.get("accounts"):
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
            "platform_limited": sum(1 for x in accounts if (x.get("auth") or {}).get("status") == "platform_limited"),
            "online_devices": sum(1 for x in devices if x.get("connection") == "connected"),
        },
        "truth_rule": "账号身份长期保留；授权可刷新，设备可替换，Mission 只引用 account_id。没有真实平台回执不得记为已发布。",
        "updated_at": max(str(registry.get("updated_at") or ""), str(device_pool.get("updated_at") or "")),
    }


def update_scope(account_id: str, *, all_services=None, services=None, all_regions=None, regions=None, preferred_device_id=None) -> dict:
    registry = _read_registry()
    device_pool = _read_devices()
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
        preferred = str(preferred_device_id or "").strip() or None
        if preferred and not any(x.get("device_id") == preferred for x in device_pool.get("devices", [])):
            raise ValueError("指定设备不在设备池中")
        account["preferred_device_id"] = preferred
    account["updated_at"] = now_iso()
    registry["updated_at"] = now_iso()
    write_json(REGISTRY_PATH, registry)
    _save_checkpoint(registry, device_pool, "account_scope_or_device_change")
    _append_audit("account_scope_updated", account_id=account_id)
    return _account_snapshot(account)


def set_auth_state(account_id: str, status: str, *, method=None, platform_subject_id=None, scopes=None, expires_at=None) -> dict:
    if status not in {"connected", "needs_authorization", "platform_limited", "disabled"}:
        raise ValueError("账号授权状态不支持")
    registry = _read_registry()
    device_pool = _read_devices()
    account = next((x for x in registry.get("accounts", []) if x.get("account_id") == account_id), None)
    if not account:
        raise ValueError("账号资产不存在")
    auth = account.setdefault("auth", {})
    previous = auth.get("status")
    auth["status"] = status
    auth["reauthorization_required"] = status == "needs_authorization"
    if method is not None:
        auth["method"] = method
    if platform_subject_id is not None:
        subject = str(platform_subject_id or "")[:200] or None
        existing_subject = auth.get("platform_subject_id")
        if existing_subject and subject and existing_subject != subject:
            raise ValueError("平台主体ID与当前永久账号不一致，禁止静默换号")
        auth["platform_subject_id"] = subject
    if scopes is not None:
        auth["scopes"] = [str(x)[:120] for x in scopes if str(x).strip()][:100]
    if expires_at is not None:
        auth["expires_at"] = expires_at
    if status == "connected":
        auth["last_verified_at"] = now_iso()
    account["updated_at"] = now_iso()
    registry["updated_at"] = now_iso()
    write_json(REGISTRY_PATH, registry)
    _save_checkpoint(registry, device_pool, "authorization_state_change")
    _append_audit("authorization_state_changed", account_id=account_id, detail={
        "from": previous,
        "to": status,
        "method": auth.get("method"),
    })
    return _account_snapshot(account)


def register_official_identity(platform: str, display_name: str, platform_subject_id: str, *, method="oauth") -> dict:
    """Create or attach an official platform subject without changing old IDs.

    If a migrated asset with the same platform/display name exists, official
    authorization enriches that same account instead of creating a duplicate.
    """
    platform = str(platform or "").strip()
    display_name = str(display_name or "").strip()
    subject = str(platform_subject_id or "").strip()
    if not platform or not display_name or not subject:
        raise ValueError("官方账号身份信息不完整")
    registry = _read_registry()
    device_pool = _read_devices()
    existing = next((
        x for x in registry.get("accounts", [])
        if x.get("platform") == platform and (x.get("auth") or {}).get("platform_subject_id") == subject
    ), None)
    if existing is None:
        existing = next((
            x for x in registry.get("accounts", [])
            if x.get("platform") == platform and x.get("display_name") == display_name
        ), None)
    if existing is None:
        existing = {
            "account_id": _stable_account_id(platform, subject),
            "platform": platform,
            "platform_name": r8_control.PLATFORMS.get(platform, platform),
            "display_name": display_name,
            "auth": {},
            "service_scope": {"all_local_services": False, "services": []},
            "region_scope": {"all_regions": False, "regions": []},
            "preferred_device_id": None,
            "legacy_account_ids": [],
            "source": "official_authorization",
            "created_at": now_iso(),
        }
        registry.setdefault("accounts", []).append(existing)
    auth = existing.setdefault("auth", {})
    old_subject = auth.get("platform_subject_id")
    if old_subject and old_subject != subject:
        raise ValueError("官方主体与现有永久账号不一致")
    auth.update({
        "platform_subject_id": subject,
        "method": method,
        "status": auth.get("status") or "needs_authorization",
        "reauthorization_required": auth.get("status") != "connected",
        "scopes": auth.get("scopes") or [],
    })
    existing["display_name"] = display_name
    existing["updated_at"] = now_iso()
    registry["updated_at"] = now_iso()
    write_json(REGISTRY_PATH, registry)
    _save_checkpoint(registry, device_pool, "official_identity_registered")
    _append_audit("official_identity_registered", account_id=existing["account_id"], detail={"platform": platform})
    return _account_snapshot(existing)
