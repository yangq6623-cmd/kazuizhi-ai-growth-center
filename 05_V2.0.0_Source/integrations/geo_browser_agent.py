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
from core.storage import now_iso, read_json, read_json_snapshot, write_json

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
        "last_claim_at": "",
        "last_claim_platform": "",
        "last_claim_reason": "",
        "last_claim_task_id": "",
        "last_canary_reason": "",
        "last_retest_reason": "",
        "last_retest_blocking_task_id": "",
        "last_retest_next_eligible_at": "",
        "extension_version": "",
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
    # The 127.0.0.1 owner/status GET and post-write status response must stay
    # available even if another JSON ledger is waiting on a Windows file lock.
    # Existing-but-unreadable state raises rather than inventing a ready agent.
    state = read_json_snapshot(STATE_PATH, _default_state())
    if not isinstance(state, dict) or state.get("schema") != SCHEMA:
        state = _default_state()
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
        "last_claim_at": str(state.get("last_claim_at") or ""),
        "last_claim_platform": str(state.get("last_claim_platform") or ""),
        "last_claim_reason": str(state.get("last_claim_reason") or ""),
        "last_claim_task_id": str(state.get("last_claim_task_id") or ""),
        "last_canary_reason": str(state.get("last_canary_reason") or ""),
        "last_retest_reason": str(state.get("last_retest_reason") or ""),
        "last_retest_blocking_task_id": str(state.get("last_retest_blocking_task_id") or ""),
        "last_retest_next_eligible_at": str(state.get("last_retest_next_eligible_at") or ""),
        "extension_version": str(state.get("extension_version") or ""),
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
    if "version" in values:
        state["extension_version"] = str(values.get("version") or "")[:40]
    # A successful heartbeat proves connectivity, not that the preceding
    # browser-capture error was resolved. Keep the last failure visible until
    # a real Receipt succeeds or an explicit new error value is supplied.
    if "last_error" in values:
        state["last_error"] = str(values.get("last_error") or "")
    lease = None
    active_task_id = str(values.get("active_task_id") or "")
    if active_task_id:
        if str(state.get("extension_version") or "") in {"2.2.2.828", "2.2.2.854", "2.2.2.891"} and not all(
            str(values.get(key) or "") for key in ("run_id", "attempt_id")
        ):
            raise ValueError("geo_browser_828_heartbeat_requires_exact_attempt")
        lease = geo.renew_task_lease(
            active_task_id,
            str(state.get("agent_id") or ""),
            run_id=str(values.get("run_id") or ""),
            attempt_id=str(values.get("attempt_id") or ""),
        )
    write_json(STATE_PATH, state)
    return {"ok": True, "status": status(), "task_lease": lease}


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
    contract = {
        "real_external": True,
        "authorization_ready": True,
        "provider_ready": True,
        "provider": platform,
        "test_method": "browser",
        "executor_id": state.get("agent_id"),
        # Never give a logged-in browser a generic/old cross-platform task
        # or re-send a task with an earlier external attempt.
        "strict_provider": True,
        "fresh_only": True,
    }
    canary_reason = "not_doubao"
    if platform == "doubao_web":
        # #815: this limited one-shot is supported by the original 808 and
        # the regression-tested 814 executor. Future extension revisions must
        # be explicitly verified before enabling external canary sends.
        if state.get("extension_version") not in {"2.2.2.808", "2.2.2.814", "2.2.2.828", "2.2.2.854", "2.2.2.891"}:
            canary_reason = "extension_version_not_supported"
        elif not str(state.get("agent_id") or "").startswith("kz-r8-28-"):
            canary_reason = "agent_not_r8_28"
        else:
            # Reserve the single genuinely untried question *before* looking
            # at the ordinary queue. Otherwise fresh unrelated background work
            # could starve this one authorized browser end-to-end test forever.
            canary = geo.queue_single_fresh_doubao_canary_once()
            canary_reason = str(canary.get("reason") or (
                "queued" if canary.get("created") == 1 else "not_created"))
            if canary.get("created") == 1:
                contract["priority_task_id"] = str(canary["task_id"])
    result = geo.claim_next_task(contract)
    retest_reason = "ordinary_queued_task"
    retest = {}
    if result.get("skipped"):
        # Browser baseline 50/50 is not an infinite source of fresh questions.
        # Schedule at most one authentic 24h follow-up from an already verified
        # successful slot. Never replay historical failed/ambiguous tasks.
        retest = geo.enqueue_safe_browser_retest(platform)
        retest_reason = str(retest.get("reason") or "not_eligible")
        if retest.get("created") == 1:
            contract["priority_task_id"] = str(retest["task_id"])
            result = geo.claim_next_task(contract)
    task = result.get("task") or {}
    state["last_retest_reason"] = retest_reason
    state["last_retest_blocking_task_id"] = str(retest.get("blocking_task_id") or "")
    state["last_retest_next_eligible_at"] = str(retest.get("next_eligible_at") or "")
    state["last_claim_at"] = now_iso()
    state["last_claim_platform"] = platform
    if task:
        claim_reason = "claimed"
    else:
        claim_reason = str(result.get("reason") or "queue_empty")
        blocked = result.get("blocked") if isinstance(result.get("blocked"), list) else []
        if blocked:
            claim_reason += ":" + str(blocked[0].get("reason") or "safety_gate")
    state["last_claim_reason"] = claim_reason
    state["last_claim_task_id"] = str(task.get("task_id") or "")
    if platform == "doubao_web":
        state["last_canary_reason"] = canary_reason
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
    task_id = str(values.get("task_id") or "")
    if not task_id:
        raise ValueError("task_id_required")
    from core.storage import _JSON_IO_LOCK
    with _JSON_IO_LOCK:
        _queue, task = geo._find_task(task_id)
        legacy_current_page = (
            str(values.get("evidence_source") or "") ==
            "r8_28_chrome_extension_current_page_recovery"
            and task.get("state") == "failed"
        )
        if not legacy_current_page and task.get("state") not in {"running", "succeeded"}:
            raise ValueError("geo_browser_receipt_requires_claimed_task")
        if not legacy_current_page and str(task.get("executor_id") or "") != str(state.get("agent_id") or ""):
            raise PermissionError("geo_browser_receipt_wrong_executor")
        if str(state.get("extension_version") or "") in {"2.2.2.828", "2.2.2.854", "2.2.2.891"} and not all(
            str(values.get(key) or "") for key in ("run_id", "attempt_id")
        ):
            raise ValueError("geo_browser_828_receipt_requires_exact_attempt")
        if values.get("run_id") and str(task.get("run_id") or "") != str(values.get("run_id") or ""):
            raise ValueError("geo_browser_receipt_stale_run")
        if values.get("attempt_id") and str(task.get("attempt_id") or "") != str(values.get("attempt_id") or ""):
            raise ValueError("geo_browser_receipt_stale_attempt")
        assigned = str(task.get("expected_platform") or "")
        if assigned and assigned != str(values.get("platform") or ""):
            raise ValueError("geo_browser_receipt_platform_mismatch")
    from integrations import geo_browser_validation
    result = geo_browser_validation.record_browser_result(values)
    state["last_task_id"] = str(values.get("task_id") or "")
    state["last_result_at"] = now_iso()
    state["last_heartbeat_at"] = now_iso()
    state["last_error"] = ""
    write_json(STATE_PATH, state)
    return result


def block(payload):
    """Distinguish execution failure from real browser authorization barriers.

    A timeout, DOM change or missing reply does not invalidate an existing
    account login. Do not turn the entire platform into "authorization
    required" on capture failures. Historical tasks are never rewritten here.
    """
    values = dict(payload or {})
    state = _load()
    _authorize(state, values.get("agent_token"))
    platform = str(values.get("platform") or "").strip()
    if platform not in DOMESTIC_PLATFORMS:
        raise ValueError("unsupported_domestic_geo_platform")
    reason = str(values.get("reason") or "external_platform_authorization_required").strip()
    kind = str(values.get("kind") or "authorization_required").strip()
    technical = kind in {"execution_error", "capture_error", "runtime_error", "timeout"}
    target = "failed" if technical else "authorization_required"
    task_id = str(values.get("task_id") or "").strip()

    # Receipt can beat the late failure callback; never downgrade a completed
    # task or overwrite the evidence associated with a successful result.
    task = None
    if task_id:
        from core.storage import _JSON_IO_LOCK
        with _JSON_IO_LOCK:
            _queue, previous = geo._find_task(task_id)
            if str(state.get("extension_version") or "") in {"2.2.2.828", "2.2.2.854", "2.2.2.891"} and not all(
                str(values.get(key) or "") for key in ("run_id", "attempt_id")
            ):
                raise ValueError("geo_browser_828_block_requires_exact_attempt")
            same_attempt = (
                (not values.get("run_id") or str(previous.get("run_id") or "") == str(values.get("run_id") or ""))
                and (not values.get("attempt_id") or str(previous.get("attempt_id") or "") == str(values.get("attempt_id") or ""))
            )
            if (previous.get("state") == "running"
                    and str(previous.get("executor_id") or "") == str(state.get("agent_id") or "")
                    and same_attempt):
                task = geo._transition(task_id, target, reason)
            else:
                # A late timeout must never undo a successfully persisted Receipt.
                return {
                    "ok": True, "task": previous, "ignored_stale": True,
                    "block_category": "stale_callback",
                    "requires_manual_login": False, "status": status(),
                }

    if not technical:
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
    # For a technical problem, keep the last verified platform session state:
    # a ready login remains ready; further tasks are subject to queue gates.
    state["last_heartbeat_at"] = now_iso()
    state["last_error"] = reason
    write_json(STATE_PATH, state)
    return {
        "ok": True,
        "task": task,
        "block_category": "technical" if technical else "authorization",
        "requires_manual_login": not technical,
        "status": status(),
    }


def disconnect(payload):
    values = dict(payload or {})
    state = _load()
    _authorize(state, values.get("agent_token"))
    state["disconnected_at"] = now_iso()
    state["last_heartbeat_at"] = ""
    state["last_error"] = str(values.get("reason") or "agent_disconnected")
    write_json(STATE_PATH, state)
    return {"ok": True, "status": status()}
