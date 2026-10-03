"""Durable official account slots layered onto the R8-12 Account Registry.

Each successful official authorization creates or refreshes one permanent
Account Asset.  Authorization can change without changing account_id.
No token or platform password is written into this registry.
"""
from __future__ import annotations

import hashlib
from copy import deepcopy

from core.storage import now_iso, read_json, write_json

REGISTRY_PATH = "r8_12/account_registry.json"
CHECKPOINT_PATH = "r8_12/account_assets_last_good.json"
AUDIT_PATH = "r8_12/account_asset_audit.json"
SCHEMA = "kz.account-registry.v2"

PLATFORM_CODE = {
    "google_search_console": "GSC",
    "bing_webmaster": "BING",
    "baidu_search_resource": "BAIDU",
    "douyin": "DY",
    "kuaishou": "KS",
    "xiaohongshu": "XHS",
    "wechat_channels": "WXSPH",
}
PLATFORM_NAME = {
    "google_search_console": "Google Search Console",
    "bing_webmaster": "Bing Webmaster",
    "baidu_search_resource": "百度搜索资源平台",
    "douyin": "抖音",
    "kuaishou": "快手",
    "xiaohongshu": "小红书",
    "wechat_channels": "微信 / 视频号",
}


def _registry() -> dict:
    data = read_json(REGISTRY_PATH, {})
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        data = {"schema": SCHEMA, "accounts": [], "migrations": [], "created_at": now_iso(), "updated_at": now_iso()}
    data.setdefault("accounts", [])
    data.setdefault("migrations", [])
    data.setdefault("created_at", now_iso())
    return data


def _account_id(platform: str, slot_id: str) -> str:
    code = PLATFORM_CODE.get(platform, "OTHER")
    digest = hashlib.sha256(f"official|{platform}|{slot_id}".encode("utf-8")).hexdigest()[:12].upper()
    return f"ACC-{code}-{digest}"


def _audit(kind: str, account_id: str, detail: dict) -> None:
    data = read_json(AUDIT_PATH, {})
    if not isinstance(data, dict): data = {}
    data.setdefault("schema", "kz.account-asset-audit.v1")
    data.setdefault("events", [])
    data["events"].insert(0, {"at": now_iso(), "kind": kind, "account_id": account_id, "device_id": None, "detail": detail})
    data["events"] = data["events"][:500]
    data["updated_at"] = now_iso()
    write_json(AUDIT_PATH, data)


def _checkpoint(registry: dict, reason: str) -> None:
    previous = read_json(CHECKPOINT_PATH, {})
    device_pool = previous.get("device_pool") if isinstance(previous, dict) and isinstance(previous.get("device_pool"), dict) else {"schema": "kz.device-pool.v2", "devices": []}
    accounts = [x for x in registry.get("accounts", []) if isinstance(x, dict) and x.get("account_id")]
    write_json(CHECKPOINT_PATH, {
        "schema": "kz.account-assets-checkpoint.v1",
        "saved_at": now_iso(),
        "reason": reason,
        "quality": {
            "accounts": len(accounts),
            "identified_accounts": sum(1 for x in accounts if x.get("display_name") and x.get("platform")),
            "connected_accounts": sum(1 for x in accounts if (x.get("auth") or {}).get("status") == "connected"),
            "devices": len(device_pool.get("devices") or []),
        },
        "registry": deepcopy(registry),
        "device_pool": device_pool,
        "truth_rule": "只恢复已存在账号/设备资产；不会补造登录、授权或发布成功。",
    })


def upsert_official_account(*, platform: str, slot_id: str, slot_label: str, scopes=None,
                            platform_subject_id=None, expires_at=None, account_id=None) -> dict:
    platform = str(platform or "").strip(); slot_id = str(slot_id or "").strip()
    if not platform or not slot_id:
        raise ValueError("platform/slot_id 不能为空")
    registry = _registry()
    wanted = str(account_id or "").strip() or _account_id(platform, slot_id)
    existing = next((x for x in registry["accounts"] if isinstance(x, dict) and x.get("account_id") == wanted), None)
    if existing is None:
        existing = next((x for x in registry["accounts"] if isinstance(x, dict) and (x.get("auth") or {}).get("platform_slot_id") == slot_id and x.get("platform") == platform), None)
    created = existing is None
    row = existing if existing is not None else {}
    account_id_final = row.get("account_id") or wanted
    row.update({
        "account_id": account_id_final,
        "platform": platform,
        "platform_name": PLATFORM_NAME.get(platform, platform),
        "display_name": str(slot_label or "").strip()[:80] or PLATFORM_NAME.get(platform, platform),
        "auth": {
            "status": "connected",
            "method": "official_authorization",
            "platform_slot_id": slot_id,
            "platform_subject_id": str(platform_subject_id or "").strip() or None,
            "scopes": sorted(set(str(x).strip() for x in (scopes or []) if str(x).strip())),
            "expires_at": expires_at,
            "last_verified_at": now_iso(),
            "reauthorization_required": False,
        },
        "service_scope": row.get("service_scope") or {"all_local_services": True, "services": []},
        "region_scope": row.get("region_scope") or {"all_regions": True, "regions": []},
        "preferred_device_id": row.get("preferred_device_id"),
        "legacy_account_ids": row.get("legacy_account_ids") or [],
        "source": "official_platform_authorization",
        "created_at": row.get("created_at") or now_iso(),
        "updated_at": now_iso(),
    })
    if created: registry["accounts"].append(row)
    registry["updated_at"] = now_iso()
    write_json(REGISTRY_PATH, registry)
    _checkpoint(registry, "official_account_authorized")
    _audit("official_account_created" if created else "official_account_reauthorized", account_id_final, {
        "platform": platform, "slot_id": slot_id, "slot_label": row["display_name"],
        "platform_subject_id_present": bool(platform_subject_id), "scope_count": len(row["auth"]["scopes"]),
    })
    return {
        "created": created,
        "account_id": account_id_final,
        "platform": platform,
        "display_name": row["display_name"],
        "auth_status": "connected",
        "authorized_scopes": list(row["auth"]["scopes"]),
        "truth": "账号资产仅在真实官方授权/token 交换成功后建立；registry 不保存 token 或密码。",
    }


def mark_reauthorization_required(account_id: str, reason: str) -> dict:
    registry = _registry(); wanted = str(account_id or "").strip()
    row = next((x for x in registry["accounts"] if isinstance(x, dict) and x.get("account_id") == wanted), None)
    if row is None: raise ValueError("账号不存在")
    auth = row.setdefault("auth", {})
    auth["status"] = "needs_authorization"; auth["reauthorization_required"] = True
    auth["last_error"] = str(reason or "reauthorization_required")[:240]
    row["updated_at"] = now_iso(); registry["updated_at"] = now_iso(); write_json(REGISTRY_PATH, registry)
    _audit("official_account_reauthorization_required", wanted, {"reason": auth["last_error"]})
    return {"account_id": wanted, "auth_status": "needs_authorization", "reason": auth["last_error"]}
