"""Per-account environment safety profiles for official multi-account operation.

This module is deliberately conservative:
- no proxy rotation
- no fingerprint spoofing
- no CAPTCHA/SMS/human-verification bypass
- no raw password storage
- no raw public IP persistence

It records only coarse environment continuity and task locks so automation can
pause on suspicious changes instead of pushing through platform risk controls.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from core.storage import now_iso, read_json, write_json

PATH = "r8_12/account_environment_profiles.json"
SCHEMA = "kz.account-environment.v1"


def _store() -> dict:
    data = read_json(PATH, {})
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        data = {"schema": SCHEMA, "profiles": {}, "updated_at": now_iso()}
    data.setdefault("profiles", {})
    return data


def _profile(account_id: str) -> dict:
    account_id = str(account_id or "").strip()
    if not account_id:
        raise ValueError("account_id 不能为空")
    data = _store()
    profile = data["profiles"].get(account_id)
    if not isinstance(profile, dict):
        profile = {
            "account_id": account_id,
            "environment_status": "unobserved",
            "risk_level": "unknown",
            "preferred_device_id": None,
            "network_profile_label": None,
            "last_network_profile_label": None,
            "authorization_lock": False,
            "mutation_lock": False,
            "consecutive_failures": 0,
            "last_error_code": None,
            "last_risk_reason": None,
            "cooldown_until": None,
            "last_authorized_at": None,
            "last_mutation_at": None,
            "updated_at": now_iso(),
            "policy": {
                "stable_device_preferred": True,
                "stable_network_preferred": True,
                "proxy_rotation": False,
                "fingerprint_spoofing": False,
                "captcha_bypass": False,
                "sms_interception": False,
                "auto_failover_on_risk": False,
            },
        }
        data["profiles"][account_id] = profile
        data["updated_at"] = now_iso()
        write_json(PATH, data)
    return dict(profile)


def get_profile(account_id: str) -> dict:
    return _profile(account_id)


def snapshot() -> dict:
    data = _store()
    rows = []
    for account_id in sorted(data.get("profiles", {})):
        profile = data["profiles"].get(account_id)
        if isinstance(profile, dict):
            rows.append(dict(profile))
    return {
        "profiles": rows,
        "summary": {
            "profiles": len(rows),
            "normal": sum(1 for x in rows if x.get("risk_level") == "low"),
            "warning": sum(1 for x in rows if x.get("risk_level") in {"medium", "unknown"}),
            "paused": sum(1 for x in rows if x.get("risk_level") in {"high", "blocked"}),
        },
        "truth": "环境档案用于保持账号环境连续性和安全停机；不做代理轮换、指纹伪装或验证码绕过。",
    }


def observe(account_id: str, *, device_id=None, network_profile_label=None) -> dict:
    data = _store()
    profile = _profile(account_id)
    current_network = str(network_profile_label or "").strip() or None
    current_device = str(device_id or "").strip() or None

    previous_network = profile.get("network_profile_label")
    previous_device = profile.get("preferred_device_id")
    changed = []
    if previous_network and current_network and previous_network != current_network:
        changed.append("network_profile_changed")
    if previous_device and current_device and previous_device != current_device:
        changed.append("device_changed")

    if current_network:
        profile["last_network_profile_label"] = previous_network
        profile["network_profile_label"] = current_network
    if current_device:
        profile["preferred_device_id"] = current_device

    if changed:
        profile["environment_status"] = "changed"
        profile["risk_level"] = "medium"
        profile["last_risk_reason"] = ",".join(changed)
    else:
        profile["environment_status"] = "stable" if (current_network or current_device or previous_network or previous_device) else "unobserved"
        if profile.get("risk_level") not in {"high", "blocked"}:
            profile["risk_level"] = "low" if profile["environment_status"] == "stable" else "unknown"
            profile["last_risk_reason"] = None
    profile["updated_at"] = now_iso()
    data["profiles"][account_id] = profile
    data["updated_at"] = now_iso()
    write_json(PATH, data)
    return dict(profile)


def mark_risk(account_id: str, reason: str, *, level="high", cooldown_minutes=60) -> dict:
    level = str(level or "high").lower()
    if level not in {"low", "medium", "high", "blocked"}:
        raise ValueError("risk level 无效")
    data = _store(); profile = _profile(account_id)
    profile["risk_level"] = level
    profile["environment_status"] = "paused" if level in {"high", "blocked"} else "changed"
    profile["last_risk_reason"] = str(reason or "risk_prompt")[:240]
    profile["consecutive_failures"] = int(profile.get("consecutive_failures") or 0) + 1
    if cooldown_minutes and level in {"high", "blocked"}:
        profile["cooldown_until"] = (datetime.now().astimezone() + timedelta(minutes=int(cooldown_minutes))).isoformat(timespec="seconds")
    profile["authorization_lock"] = False
    profile["mutation_lock"] = False
    profile["updated_at"] = now_iso()
    data["profiles"][account_id] = profile; data["updated_at"] = now_iso(); write_json(PATH, data)
    return dict(profile)


def clear_risk(account_id: str, *, owner_confirmed=False) -> dict:
    if not owner_confirmed:
        raise ValueError("高风险状态只能由明确人工确认解除")
    data = _store(); profile = _profile(account_id)
    profile["risk_level"] = "low"
    profile["environment_status"] = "stable"
    profile["last_risk_reason"] = None
    profile["cooldown_until"] = None
    profile["consecutive_failures"] = 0
    profile["updated_at"] = now_iso()
    data["profiles"][account_id] = profile; data["updated_at"] = now_iso(); write_json(PATH, data)
    return dict(profile)


def acquire_lock(account_id: str, kind: str) -> dict:
    kind = str(kind or "").strip()
    if kind not in {"authorization", "mutation"}:
        raise ValueError("lock kind 无效")
    data = _store(); profile = _profile(account_id)
    if profile.get("risk_level") in {"high", "blocked"}:
        return {"ok": False, "reason": "account_paused_for_risk", "profile": profile}
    key = "authorization_lock" if kind == "authorization" else "mutation_lock"
    if profile.get(key):
        return {"ok": False, "reason": f"{kind}_already_running", "profile": profile}
    profile[key] = True; profile["updated_at"] = now_iso()
    data["profiles"][account_id] = profile; data["updated_at"] = now_iso(); write_json(PATH, data)
    return {"ok": True, "profile": dict(profile)}


def release_lock(account_id: str, kind: str, *, success=True, error_code=None) -> dict:
    kind = str(kind or "").strip()
    if kind not in {"authorization", "mutation"}:
        raise ValueError("lock kind 无效")
    data = _store(); profile = _profile(account_id)
    key = "authorization_lock" if kind == "authorization" else "mutation_lock"
    profile[key] = False
    if success:
        profile["consecutive_failures"] = 0
        profile["last_error_code"] = None
        if kind == "authorization": profile["last_authorized_at"] = now_iso()
        if kind == "mutation": profile["last_mutation_at"] = now_iso()
    else:
        profile["consecutive_failures"] = int(profile.get("consecutive_failures") or 0) + 1
        profile["last_error_code"] = str(error_code or "unknown")[:120]
    profile["updated_at"] = now_iso()
    data["profiles"][account_id] = profile; data["updated_at"] = now_iso(); write_json(PATH, data)
    return dict(profile)


def routing_allowed(account_id: str) -> dict:
    profile = _profile(account_id)
    blocked = profile.get("risk_level") in {"high", "blocked"}
    busy = bool(profile.get("mutation_lock"))
    return {
        "allowed": not blocked and not busy,
        "risk_level": profile.get("risk_level"),
        "environment_status": profile.get("environment_status"),
        "reason": "risk_pause" if blocked else ("mutation_busy" if busy else "ok"),
        "profile": profile,
    }
