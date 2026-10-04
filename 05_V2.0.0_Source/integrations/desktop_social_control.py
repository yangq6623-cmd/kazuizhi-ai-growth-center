"""Read-only social control view backed by PC browser QR sessions.

This is the compatibility boundary for legacy R8 surfaces.  It exposes familiar
account fields but never creates a phone, ADB probe, or device binding.
"""
from __future__ import annotations

from core.account_registry import snapshot as account_snapshot
from core.storage import now_iso
from integrations.desktop_browser_session import is_ready


def social_center_status():
    value = account_snapshot()
    accounts = []
    for raw in value.get("accounts") or []:
        account_id = str(raw.get("account_id") or "")
        auth_status = str(raw.get("auth_status") or "needs_authorization")
        ready = is_ready(account_id)
        accounts.append({
            "account_id": account_id, "platform": raw.get("platform"),
            "platform_name": raw.get("platform_name"), "alias": raw.get("display_name"),
            "label": raw.get("display_name"),
            "region": ((raw.get("region_scope") or {}).get("regions") or [""])[0],
            "service_category": ((raw.get("service_scope") or {}).get("services") or [""])[0],
            "login_status": "authorized" if auth_status == "connected" else "needs_human",
            "auth_status": auth_status, "auth_method": raw.get("auth_method"),
            "login_verified_at": raw.get("last_verified_at"), "browser_session_ready": ready,
            "automation_paused": auth_status in {"disabled", "platform_limited"},
            "risk_level": "normal" if auth_status == "connected" else "attention",
        })
    return {"schema": "kz.desktop-browser-social-control.v1", "accounts": accounts,
            "devices": [], "terminals": [], "platforms": [],
            "summary": {"accounts": len(accounts), "authorized": sum(1 for row in accounts if row["login_status"] == "authorized"), "browser_ready": sum(1 for row in accounts if row["browser_session_ready"])},
            "mode": "desktop_browser_qr_only", "updated_at": now_iso()}
