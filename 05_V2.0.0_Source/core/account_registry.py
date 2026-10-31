"""R8-12 durable Account Asset + Device Pool registry.

Account identity is permanent. Authorization and devices are replaceable.
Mission/service/region changes never create a new account identity. Secrets are
stored only by the local credential vault, never in this registry.
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
DEVICE_SCHEMA = "kz.device-pool.v2"
LEGACY_SCHEMAS = {"kz.account-registry.v1", SCHEMA}
LEGACY_DEVICE_SCHEMAS = {"kz.device-pool.v1", DEVICE_SCHEMA}
PLATFORM_CODE = {
    "douyin": "DY", "kuaishou": "KS", "xiaohongshu": "XHS",
    "wechat_channels": "WXSPH", "weibo": "WB", "bilibili": "BL",
    "forum": "FORUM", "blog": "BLOG", "other": "OTHER",
}
PLATFORM_ALIASES = {
    "抖音": "douyin", "douyin": "douyin", "快手": "kuaishou", "kuaishou": "kuaishou",
    "小红书": "xiaohongshu", "xiaohongshu": "xiaohongshu", "视频号": "wechat_channels",
    "微信视频号": "wechat_channels", "wechat_channels": "wechat_channels", "微博": "weibo", "weibo": "weibo",
    "B站": "bilibili", "哔哩哔哩": "bilibili", "bilibili": "bilibili",
}


def _missing(value):
    return value is None or value == "" or value == [] or value == {}


def _platform(value):
    text = str(value or "").strip()
    return PLATFORM_ALIASES.get(text, text)


def _stable_account_id(platform, seed):
    code = PLATFORM_CODE.get(platform, "OTHER")
    digest = hashlib.sha256(f"{platform}|{seed}".encode("utf-8")).hexdigest()[:10].upper()
    return f"ACC-{code}-{digest}"


def _stable_device_id(device_id):
    safe = "".join(ch if ch.isalnum() else "-" for ch in str(device_id or "").upper()).strip("-")
    return f"DEV-{safe or 'UNKNOWN'}"


def _normalize_region(value):
    text = str(value or "").strip()
    return "涟水县" if text in {"涟水", "涟水县"} else text


def _auth_state(login_status):
    return {"authorized": "connected", "needs_human": "needs_authorization", "logged_out": "needs_authorization", "not_verified": "needs_authorization"}.get(str(login_status or ""), "needs_authorization")


def _default_registry():
    return {"schema": SCHEMA, "accounts": [], "migrations": [], "created_at": now_iso(), "updated_at": now_iso()}


def _default_devices():
    return {"schema": DEVICE_SCHEMA, "devices": [], "created_at": now_iso(), "updated_at": now_iso()}


def _read_registry():
    value = read_json(REGISTRY_PATH, {})
    if not isinstance(value, dict) or value.get("schema") not in LEGACY_SCHEMAS: return _default_registry()
    value.setdefault("accounts", []); value.setdefault("migrations", []); value.setdefault("created_at", now_iso()); value["schema"] = SCHEMA
    return value


def _read_devices():
    value = read_json(DEVICE_PATH, {})
    if not isinstance(value, dict) or value.get("schema") not in LEGACY_DEVICE_SCHEMAS: return _default_devices()
    value.setdefault("devices", []); value.setdefault("created_at", now_iso()); value["schema"] = DEVICE_SCHEMA
    return value


def _append_audit(kind, *, account_id=None, device_id=None, detail=None):
    payload = read_json(AUDIT_PATH, {}); payload = payload if isinstance(payload, dict) else {}
    payload.setdefault("schema", "kz.account-asset-audit.v1"); payload.setdefault("events", [])
    payload["events"].insert(0, {"at": now_iso(), "kind": kind, "account_id": account_id, "device_id": device_id, "detail": detail if isinstance(detail, dict) else {}})
    payload["events"] = payload["events"][:500]; payload["updated_at"] = now_iso(); write_json(AUDIT_PATH, payload)


def _asset_quality(registry, device_pool):
    accounts = [x for x in registry.get("accounts", []) if isinstance(x, dict) and x.get("account_id")]
    devices = [x for x in device_pool.get("devices", []) if isinstance(x, dict) and x.get("device_id")]
    return (len(accounts), sum(1 for x in accounts if x.get("display_name") and x.get("platform")), sum(1 for x in accounts if (x.get("auth") or {}).get("status") == "connected"), len(devices))


def _save_checkpoint(registry, device_pool, reason):
    quality = _asset_quality(registry, device_pool)
    if quality[0] == 0 and quality[3] == 0: return
    previous = read_json(CHECKPOINT_PATH, {})
    preg = previous.get("registry") if isinstance(previous, dict) and isinstance(previous.get("registry"), dict) else {}
    pdev = previous.get("device_pool") if isinstance(previous, dict) and isinstance(previous.get("device_pool"), dict) else {}
    pquality = _asset_quality(preg, pdev)
    if pquality[0] > quality[0] or pquality[3] > quality[3]: return
    write_json(CHECKPOINT_PATH, {
        "schema": "kz.account-assets-checkpoint.v1", "saved_at": now_iso(), "reason": str(reason or "state_change")[:120],
        "quality": {"accounts": quality[0], "identified_accounts": quality[1], "connected_accounts": quality[2], "devices": quality[3]},
        "registry": deepcopy(registry), "device_pool": deepcopy(device_pool),
        "truth_rule": "只恢复已存在账号/设备资产；不会补造登录、授权或发布成功。",
    })


def _merge_missing(current, fallback, key):
    rows = current.setdefault(key, []); id_key = "account_id" if key == "accounts" else "device_id"
    by_id = {str(x.get(id_key) or ""): x for x in rows if isinstance(x, dict)}; restored = 0
    for candidate in fallback.get(key, []) if isinstance(fallback, dict) else []:
        if not isinstance(candidate, dict): continue
        identifier = str(candidate.get(id_key) or "")
        if not identifier: continue
        existing = by_id.get(identifier)
        if existing is None:
            rows.append(deepcopy(candidate)); by_id[identifier] = rows[-1]; restored += 1; continue
        for field, value in candidate.items():
            if field in {"auth", "updated_at"}: continue
            if _missing(existing.get(field)) and not _missing(value): existing[field] = deepcopy(value)
    return restored


def recover_assets_if_degraded():
    registry, devices = _read_registry(), _read_devices(); checkpoint = read_json(CHECKPOINT_PATH, {})
    if not isinstance(checkpoint, dict): return {"restored": False, "reason": "no_checkpoint"}
    preg = checkpoint.get("registry") if isinstance(checkpoint.get("registry"), dict) else {}; pdev = checkpoint.get("device_pool") if isinstance(checkpoint.get("device_pool"), dict) else {}
    q, pq = _asset_quality(registry, devices), _asset_quality(preg, pdev)
    if q[0] >= pq[0] and q[3] >= pq[3]: return {"restored": False, "reason": "current_not_degraded"}
    ra, rd = _merge_missing(registry, preg, "accounts"), _merge_missing(devices, pdev, "devices")
    if not (ra or rd): return {"restored": False, "reason": "nothing_missing_after_merge"}
    registry["schema"], devices["schema"], registry["updated_at"], devices["updated_at"] = SCHEMA, DEVICE_SCHEMA, now_iso(), now_iso()
    write_json(REGISTRY_PATH, registry); write_json(DEVICE_PATH, devices)
    _append_audit("asset_recovery", detail={"restored_accounts": ra, "restored_devices": rd, "checkpoint_saved_at": checkpoint.get("saved_at")})
    return {"restored": True, "accounts": ra, "devices": rd, "source": "last_good_account_assets"}


def _account_snapshot(account):
    auth = account.get("auth") if isinstance(account.get("auth"), dict) else {}
    return {
        "account_id": account.get("account_id"), "platform": account.get("platform"), "platform_name": account.get("platform_name"), "display_name": account.get("display_name"),
        "auth_status": auth.get("status"), "auth_method": auth.get("method"), "platform_subject_id": auth.get("platform_subject_id"), "authorized_scopes": list(auth.get("scopes") or []),
        "expires_at": auth.get("expires_at"), "last_verified_at": auth.get("last_verified_at"), "reauthorization_required": bool(auth.get("reauthorization_required")),
        "service_scope": account.get("service_scope") or {}, "region_scope": account.get("region_scope") or {}, "preferred_device_id": account.get("preferred_device_id"),
        "legacy_account_ids": account.get("legacy_account_ids") or [], "source": account.get("source"), "created_at": account.get("created_at"), "updated_at": account.get("updated_at"),
    }


def _legacy_auth(existing, legacy):
    auth = deepcopy((existing or {}).get("auth") or {}); incoming = _auth_state(legacy.get("login_status"))
    if auth.get("status") != "connected" or incoming == "connected": auth["status"] = incoming
    auth.setdefault("method", "legacy_real_device")
    if incoming == "connected": auth.update({"method": "real_device_verified", "last_verified_at": legacy.get("login_verified_at") or auth.get("last_verified_at") or now_iso(), "reauthorization_required": False})
    else: auth.setdefault("reauthorization_required", auth.get("status") != "connected")
    auth.setdefault("platform_subject_id", None); auth.setdefault("scopes", []); auth.setdefault("expires_at", None)
    return auth


def _legacy_inputs(state):
    """Read both old social-control and old content-factory account stores."""
    accounts = [deepcopy(x) for x in state.get("accounts", []) if isinstance(x, dict)]
    factory = read_json("r8/content_factory.json", {})
    for old in factory.get("accounts", []) if isinstance(factory, dict) else []:
        if not isinstance(old, dict): continue
        accounts.append({
            "account_id": old.get("id") or old.get("account_id"), "platform": _platform(old.get("platform")),
            "platform_name": old.get("platform"), "device_id": old.get("device_id"),
            "alias": old.get("account_name") or old.get("alias") or old.get("label"),
            "label": old.get("account_name") or old.get("alias") or old.get("label"),
            "login_status": "authorized" if old.get("connection_status") == "已验证可发布" else "not_verified",
            "region": old.get("region"), "service_category": old.get("service"),
            "migrated_from": "r8/content_factory.json",
        })
    return accounts


def _ensure_device(devices, legacy_id, *, connection="unknown", health="unknown", label=None, probe_source=None, last_seen_at=None):
    legacy_id = str(legacy_id or "").strip()
    if not legacy_id: return None
    stable = _stable_device_id(legacy_id)
    existing = next((x for x in devices["devices"] if x.get("device_id") == stable), None)
    row = {
        "device_id": stable, "legacy_device_id": legacy_id, "label": label or legacy_id, "device_type": "real_android",
        "connection": connection or "unknown", "health": health or "unknown", "probe_source": probe_source,
        "last_seen_at": last_seen_at, "created_at": (existing or {}).get("created_at") or now_iso(), "updated_at": now_iso(),
    }
    if existing: existing.update(row)
    else: devices["devices"].append(row)
    return stable


def migrate_legacy_assets():
    recover_assets_if_degraded(); state = r8_control.control_status(); registry, devices = _read_registry(), _read_devices(); changed, device_map, migrated = False, {}, []
    for legacy in state.get("devices", []):
        if not isinstance(legacy, dict): continue
        legacy_id = str(legacy.get("device_id") or "").strip()
        if not legacy_id: continue
        stable = _ensure_device(devices, legacy_id, connection=legacy.get("connection"), health=legacy.get("health"), label=legacy.get("label"), probe_source=legacy.get("probe_source"), last_seen_at=legacy.get("last_seen_at"))
        device_map[legacy_id] = stable; changed = True

    for legacy in _legacy_inputs(state):
        platform, alias = _platform(legacy.get("platform")), str(legacy.get("alias") or legacy.get("label") or "").strip()
        if not platform or not alias: continue
        legacy_id = str(legacy.get("account_id") or "").strip(); raw_device = str(legacy.get("device_id") or "").strip()
        if raw_device and raw_device not in device_map: device_map[raw_device] = _ensure_device(devices, raw_device)
        existing = next((x for x in registry["accounts"] if legacy_id and legacy_id in (x.get("legacy_account_ids") or [])), None)
        if existing is None: existing = next((x for x in registry["accounts"] if x.get("platform") == platform and x.get("display_name") == alias), None)
        account_id = (existing or {}).get("account_id") or _stable_account_id(platform, legacy_id or alias)
        service = str(legacy.get("service_category") or legacy.get("service") or "").strip()
        all_services = bool((existing or {}).get("service_scope", {}).get("all_local_services")) or alias == "卡嘴子本地服务维修" or service in {"综合服务", "本地生活服务", "全部本地服务"}
        services = list((existing or {}).get("service_scope", {}).get("services") or [])
        if service and service not in services and not all_services: services.append(service)
        region = _normalize_region(legacy.get("region")); regions = list((existing or {}).get("region_scope", {}).get("regions") or [])
        if region and region not in regions: regions.append(region)
        legacy_ids = sorted(set(((existing or {}).get("legacy_account_ids") or []) + ([legacy_id] if legacy_id else [])))
        row = {
            "account_id": account_id, "platform": platform, "platform_name": legacy.get("platform_name") or r8_control.PLATFORMS.get(platform, platform), "display_name": alias,
            "auth": _legacy_auth(existing, legacy), "service_scope": {"all_local_services": bool(all_services), "services": [] if all_services else services[:50]},
            "region_scope": {"all_regions": bool((existing or {}).get("region_scope", {}).get("all_regions")), "regions": regions[:50]},
            "preferred_device_id": (existing or {}).get("preferred_device_id") or device_map.get(raw_device), "legacy_account_ids": legacy_ids,
            "source": (existing or {}).get("source") or legacy.get("migrated_from") or "r8_legacy_migration", "created_at": (existing or {}).get("created_at") or legacy.get("created_at") or now_iso(), "updated_at": now_iso(),
        }
        if existing: existing.update(row)
        else: registry["accounts"].append(row)
        changed = True; migrated.append(account_id)

    registry["schema"], devices["schema"], registry["updated_at"], devices["updated_at"] = SCHEMA, DEVICE_SCHEMA, now_iso(), now_iso()
    if changed:
        registry["migrations"].append({"at": now_iso(), "kind": "legacy_account_device_import", "migrated_accounts": sorted(set(migrated)), "truth": "迁移只建立稳定身份映射；不生成平台登录、发布或授权成功。"}); registry["migrations"] = registry["migrations"][-100:]
    write_json(REGISTRY_PATH, registry); write_json(DEVICE_PATH, devices); _save_checkpoint(registry, devices, "legacy_asset_migration")
    return snapshot(skip_migration=True)


def sync_device_health(scan_snapshot):
    """Refresh Device Pool from real ADB observations without touching accounts."""
    devices = _read_devices(); changed = 0
    for observed in (scan_snapshot or {}).get("devices", []):
        if not isinstance(observed, dict): continue
        legacy_id = str(observed.get("device_id") or "").strip()
        if not legacy_id: continue
        stable = _stable_device_id(legacy_id); existing = next((x for x in devices["devices"] if x.get("device_id") == stable), None)
        connection = "connected" if observed.get("connected") else "offline"
        before = deepcopy(existing) if existing else None
        _ensure_device(devices, legacy_id, connection=connection, health=observed.get("health") or "normal", label=observed.get("model") or legacy_id, probe_source="adb", last_seen_at=now_iso() if observed.get("connected") else (existing or {}).get("last_seen_at"))
        after = next((x for x in devices["devices"] if x.get("device_id") == stable), None)
        if before != after: changed += 1
    if changed:
        devices["updated_at"] = now_iso(); write_json(DEVICE_PATH, devices); _save_checkpoint(_read_registry(), devices, "adb_device_health_sync")
    return {"updated": changed, "devices": devices.get("devices", [])}


def snapshot(*, skip_migration=False):
    recover_assets_if_degraded(); registry, devices = _read_registry(), _read_devices()
    if not skip_migration and not registry.get("accounts"): return migrate_legacy_assets()
    accounts, drows = [x for x in registry.get("accounts", []) if isinstance(x, dict)], [x for x in devices.get("devices", []) if isinstance(x, dict)]
    return {
        "schema": SCHEMA, "accounts": [_account_snapshot(x) for x in accounts], "devices": drows,
        "summary": {"accounts": len(accounts), "connected_accounts": sum(1 for x in accounts if (x.get("auth") or {}).get("status") == "connected"), "needs_authorization": sum(1 for x in accounts if (x.get("auth") or {}).get("status") == "needs_authorization"), "platform_limited": sum(1 for x in accounts if (x.get("auth") or {}).get("status") == "platform_limited"), "online_devices": sum(1 for x in drows if x.get("connection") == "connected")},
        "truth_rule": "账号身份长期保留；授权可刷新，设备可替换，Mission 只引用 account_id。没有真实平台回执不得记为已发布。",
        "updated_at": max(str(registry.get("updated_at") or ""), str(devices.get("updated_at") or "")),
    }


def update_scope(account_id, *, all_services=None, services=None, all_regions=None, regions=None, preferred_device_id=None):
    registry, devices = _read_registry(), _read_devices(); account = next((x for x in registry.get("accounts", []) if x.get("account_id") == account_id), None)
    if not account: raise ValueError("账号资产不存在")
    if all_services is not None: account.setdefault("service_scope", {})["all_local_services"] = bool(all_services)
    if services is not None: account.setdefault("service_scope", {})["services"] = [str(x).strip() for x in services if str(x).strip()][:50]
    if all_regions is not None: account.setdefault("region_scope", {})["all_regions"] = bool(all_regions)
    if regions is not None: account.setdefault("region_scope", {})["regions"] = [_normalize_region(x) for x in regions if str(x).strip()][:50]
    if preferred_device_id is not None:
        preferred = str(preferred_device_id or "").strip() or None
        if preferred and not any(x.get("device_id") == preferred for x in devices.get("devices", [])): raise ValueError("指定设备不在设备池中")
        account["preferred_device_id"] = preferred
    account["updated_at"], registry["updated_at"] = now_iso(), now_iso(); write_json(REGISTRY_PATH, registry); _save_checkpoint(registry, devices, "account_scope_or_device_change"); _append_audit("account_scope_updated", account_id=account_id)
    return _account_snapshot(account)


def set_auth_state(account_id, status, *, method=None, platform_subject_id=None, scopes=None, expires_at=None):
    if status not in {"connected", "needs_authorization", "platform_limited", "disabled"}: raise ValueError("账号授权状态不支持")
    registry, devices = _read_registry(), _read_devices(); account = next((x for x in registry.get("accounts", []) if x.get("account_id") == account_id), None)
    if not account: raise ValueError("账号资产不存在")
    auth = account.setdefault("auth", {}); previous = auth.get("status"); auth["status"], auth["reauthorization_required"] = status, status == "needs_authorization"
    if method is not None: auth["method"] = method
    if platform_subject_id is not None:
        subject = str(platform_subject_id or "")[:200] or None
        if auth.get("platform_subject_id") and subject and auth.get("platform_subject_id") != subject: raise ValueError("平台主体ID与当前永久账号不一致，禁止静默换号")
        auth["platform_subject_id"] = subject
    if scopes is not None: auth["scopes"] = [str(x)[:120] for x in scopes if str(x).strip()][:100]
    if expires_at is not None: auth["expires_at"] = expires_at
    if status == "connected": auth["last_verified_at"] = now_iso()
    account["updated_at"], registry["updated_at"] = now_iso(), now_iso(); write_json(REGISTRY_PATH, registry); _save_checkpoint(registry, devices, "authorization_state_change"); _append_audit("authorization_state_changed", account_id=account_id, detail={"from": previous, "to": status, "method": auth.get("method")})
    return _account_snapshot(account)


def register_official_identity(platform, display_name, platform_subject_id, *, method="oauth"):
    platform, display_name, subject = _platform(platform), str(display_name or "").strip(), str(platform_subject_id or "").strip()
    if not platform or not display_name or not subject: raise ValueError("官方账号身份信息不完整")
    registry, devices = _read_registry(), _read_devices(); existing = next((x for x in registry.get("accounts", []) if x.get("platform") == platform and (x.get("auth") or {}).get("platform_subject_id") == subject), None)
    if existing is None: existing = next((x for x in registry.get("accounts", []) if x.get("platform") == platform and x.get("display_name") == display_name), None)
    if existing is None:
        existing = {"account_id": _stable_account_id(platform, subject), "platform": platform, "platform_name": r8_control.PLATFORMS.get(platform, platform), "display_name": display_name, "auth": {}, "service_scope": {"all_local_services": False, "services": []}, "region_scope": {"all_regions": False, "regions": []}, "preferred_device_id": None, "legacy_account_ids": [], "source": "official_authorization", "created_at": now_iso()}; registry.setdefault("accounts", []).append(existing)
    auth = existing.setdefault("auth", {})
    if auth.get("platform_subject_id") and auth.get("platform_subject_id") != subject: raise ValueError("官方主体与现有永久账号不一致")
    auth.update({"platform_subject_id": subject, "method": method, "status": auth.get("status") or "needs_authorization", "reauthorization_required": auth.get("status") != "connected", "scopes": auth.get("scopes") or []})
    existing["display_name"], existing["updated_at"], registry["updated_at"] = display_name, now_iso(), now_iso(); write_json(REGISTRY_PATH, registry); _save_checkpoint(registry, devices, "official_identity_registered"); _append_audit("official_identity_registered", account_id=existing["account_id"], detail={"platform": platform})
    return _account_snapshot(existing)
