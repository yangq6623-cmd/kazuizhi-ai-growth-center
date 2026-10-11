"""Truthful control bridge for an authenticated domestic GEO browser agent.

This module does not pretend that a saved login is an automation worker.  A
browser process must register, prove fresh heartbeats, advertise the platform
sessions it can use, and return the real external page URL and unmodified
answer for every task.  CAPTCHA, login expiry and risk-control challenges pause
only the affected platform and are surfaced to the owner.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime

from core import geo_validation as geo
from core.storage import now_iso, read_json, write_json

STATE_PATH = "r8_27/geo_browser_agent.json"
SCHEMA = "kz.geo-browser-agent.v1"
# Manifest V3 workers are intentionally suspended by Chromium between events.
# The extension wakes every 30 seconds, while this three-minute tolerance avoids
# false disconnects during browser scheduling jitter without masking a stopped
# executor for long.
HEARTBEAT_TTL_SECONDS = 180
DOMESTIC_PLATFORMS = (
    "doubao_web",
    "douyin_search_web",
    "deepseek_web",
    "qwen_web",
    "so360_ai_search",
)


def _default_state():
    return {
        "schema": SCHEMA,
        "agent_id": "",
        "token_hash": "",
        "registered_at": "",
        "last_heartbeat_at": "",
        "disconnected_at": "",
        "browser": "",
        "profile": "",
        "sessions": {},
        "last_task_id": "",
        "last_result_at": "",
        "last_error": "",
    }


def _load():
    try:
        value = read_json(STATE_PATH, _default_state())
    except OSError:
        # A status read must stay fail-closed and must not make the owner page
        # unavailable when Windows temporarily denies the data directory.
        return _default_state()
    return value if isinstance(value, dict) else _default_state()


def _parse_time(value):
    try:
        return datetime.fromisoformat(str(value or ""))
    except (TypeError, ValueError):
        return None


def _age_seconds(value):
    stamp = _parse_time(value)
    if stamp is None:
        return None
    now = datetime.now().astimezone()
    if stamp.tzinfo is None:
        stamp = stamp.replace(tzinfo=now.tzinfo)
    return max(0, int((now - stamp.astimezone(now.tzinfo)).total_seconds()))


def _token_hash(token):
    return hashlib.sha256(str(token or "").encode("utf-8")).hexdigest()


def _authorize(state, token):
    supplied = _token_hash(token)
    expected = str(state.get("token_hash") or "")
    if not expected or not secrets.compare_digest(supplied, expected):
        raise PermissionError("geo_browser_agent_token_invalid")


def _normalize_sessions(rows):
    if isinstance(rows, dict):
        rows = [dict(value or {}, platform=key) for key, value in rows.items()]
    result = {}
    for row in rows or []:
        if not isinstance(row, dict):
            continue
        platform = str(row.get("platform") or "").strip()
        if platform not in DOMESTIC_PLATFORMS:
            continue
        state = str(row.get("state") or "authorization_required").strip()
        if state not in {"ready", "authorization_required", "captcha_required", "blocked", "offline"}:
            state = "authorization_required"
        result[platform] = {
            "platform": platform,
            "state": state,
            "session_url": str(row.get("session_url") or "").strip(),
            "reason": str(row.get("reason") or "").strip(),
            "verified_at": str(row.get("verified_at") or now_iso()),
        }
    return result


def status():
    state = _load()
    age = _age_seconds(state.get("last_heartbeat_at"))
    connected = bool(state.get("agent_id")) and age is not None and age <= HEARTBEAT_TTL_SECONDS
    sessions = state.get("sessions") if isinstance(state.get("sessions"), dict) else {}
    platforms = []
    ready_count = 0
    for platform in DOMESTIC_PLATFORMS:
        row = dict(sessions.get(platform) or {})
        session_state = str(row.get("state") or "not_registered")
        ready = connected and session_state == "ready"
        ready_count += int(ready)
        platforms.append({
            "platform": platform,
            "state": session_state if connected else ("agent_offline" if row else "not_registered"),
            "ready": ready,
            "reason": str(row.get("reason") or ""),
            "verified_at": str(row.get("verified_at") or ""),
        })
    return {
        "schema": SCHEMA,
        "connected": connected,
        "automatic_after_login": connected and ready_count > 0,
        "all_domestic_platforms_ready": connected and ready_count == len(DOMESTIC_PLATFORMS),
        "ready_platforms": ready_count,
        "target_platforms": len(DOMESTIC_PLATFORMS),
        "heartbeat_age_seconds": age,
        "heartbeat_ttl_seconds": HEARTBEAT_TTL_SECONDS,
        "agent_id": str(state.get("agent_id") or ""),
        "browser": str(state.get("browser") or ""),
        "profile": str(state.get("profile") or ""),
        "last_task_id": str(state.get("last_task_id") or ""),
        "last_result_at": str(state.get("last_result_at") or ""),
        "last_error": str(state.get("last_error") or ""),
        "platforms": platforms,
        "requires_pc_awake": True,
        "captcha_policy": "pause_platform_and_require_owner",
        "truth_rule": "只接受代理从真实外部页面返回的原始回答、会话URL与引用；心跳过期即停止自动领取任务。",
    }


def register(payload):
    values = dict(payload or {})
    if not values.get("owner_confirmed"):
        raise ValueError("geo_browser_agent_owner_confirmation_required")
    agent_id = str(values.get("agent_id") or ("geo-agent-" + secrets.token_hex(6))).strip()
    token = secrets.token_urlsafe(32)
    state = _default_state()
    state.update({
        "agent_id": agent_id,
        "token_hash": _token_hash(token),
        "registered_at": now_iso(),
        "last_heartbeat_at": now_iso(),
        "browser": str(values.get("browser") or "chrome").strip(),
        "profile": str(values.get("profile") or "dedicated-kazuizhi-geo").strip(),
        "sessions": _normalize_sessions(values.get("sessions") or []),
    })
    write_json(STATE_PATH, state)
    return {"ok": True, "agent_token": token, "status": status()}


def heartbeat(payload):
    values = dict(payload or {})
    state = _load()
    _authorize(state, values.get("agent_token"))
    supplied = _normalize_sessions(values.get("sessions") or [])
    if supplied:
        sessions = dict(state.get("sessions") or {})
        sessions.update(supplied)
        state["sessions"] = sessions
    state["last_heartbeat_at"] = now_iso()
    state["last_error"] = str(values.get("last_error") or "")
    write_json(STATE_PATH, state)
    return {"ok": True, "status": status()}


def claim(payload):
    values = dict(payload or {})
    state = _load()
    _authorize(state, values.get("agent_token"))
    current = status()
    if not current.get("connected"):
        raise RuntimeError("geo_browser_agent_heartbeat_stale")
    platform = str(values.get("platform") or "").strip()
    sessions = state.get("sessions") if isinstance(state.get("sessions"), dict) else {}
    session = dict(sessions.get(platform) or {})
    if platform not in DOMESTIC_PLATFORMS:
        raise ValueError("unsupported_domestic_geo_platform")
    if session.get("state") != "ready":
        raise RuntimeError("geo_browser_platform_authorization_required")
    result = geo.claim_next_task({
        "real_external": True,
        "authorization_ready": True,
        "provider_ready": True,
        "provider": platform,
        "test_method": "browser",
        "executor_id": state.get("agent_id"),
    })
    task = result.get("task") or {}
    if task:
        state["last_task_id"] = str(task.get("task_id") or "")
        state["last_heartbeat_at"] = now_iso()
        write_json(STATE_PATH, state)
    from integrations import geo_browser_validation
    return {"claim": result, "contract": geo_browser_validation.contract(task, platform=platform)}


def receipt(payload):
    values = dict(payload or {})
    state = _load()
    _authorize(state, values.pop("agent_token", None))
    values["execution_origin"] = "authenticated_browser_agent"
    values["executor_id"] = str(state.get("agent_id") or "")
    from integrations import geo_browser_validation
    result = geo_browser_validation.record_browser_result(values)
    state["last_task_id"] = str(values.get("task_id") or "")
    state["last_result_at"] = now_iso()
    state["last_heartbeat_at"] = now_iso()
    state["last_error"] = ""
    write_json(STATE_PATH, state)
    return result


def block(payload):
    values = dict(payload or {})
    state = _load()
    _authorize(state, values.get("agent_token"))
    platform = str(values.get("platform") or "").strip()
    if platform not in DOMESTIC_PLATFORMS:
        raise ValueError("unsupported_domestic_geo_platform")
    reason = str(values.get("reason") or "external_platform_authorization_required").strip()
    kind = str(values.get("kind") or "authorization_required").strip()
    sessions = dict(state.get("sessions") or {})
    row = dict(sessions.get(platform) or {})
    row.update({
        "platform": platform,
        "state": "captcha_required" if kind == "captcha" else "authorization_required",
        "reason": reason,
        "verified_at": now_iso(),
    })
    sessions[platform] = row
    state["sessions"] = sessions
    state["last_heartbeat_at"] = now_iso()
    state["last_error"] = reason
    task_id = str(values.get("task_id") or "").strip()
    task = geo._transition(task_id, "authorization_required", reason) if task_id else None
    write_json(STATE_PATH, state)
    return {"ok": True, "task": task, "status": status()}


def disconnect(payload):
    values = dict(payload or {})
    state = _load()
    _authorize(state, values.get("agent_token"))
    state["disconnected_at"] = now_iso()
    state["last_heartbeat_at"] = ""
    state["last_error"] = str(values.get("reason") or "agent_disconnected")
    write_json(STATE_PATH, state)
    return {"ok": True, "status": status()}
