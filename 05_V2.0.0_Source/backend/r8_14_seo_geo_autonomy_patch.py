"""HTTP bridge for R8-14 SEO autonomy plus R8-19 GEO cloud autonomy.

#645 fixes two field failures found on the staged GEO acceptance screen:
- a historical cloud task must never prevent a fresh 1 -> 3 -> 10 -> 50 cycle;
- a stale browser_external_ai RUNNING task must be recovered so it cannot block
  the browser queue or interfere with the independent Doubao cloud queue.
"""
from __future__ import annotations

import json
import threading
import time
from datetime import datetime, timezone
from urllib.parse import urlsplit

from backend import server
from core import geo_autonomy
from core import geo_validation as geo
from core import seo_geo_autonomy as seo_core
from core.storage import now_iso

_INSTALLED = False
_ORIGINAL_SEO_RUN_ONCE = seo_core.run_once
_ORIGINAL_SEO_STATUS = seo_core.status
_ORIGINAL_GEO_RUN_ONCE = geo_autonomy.run_once
_ORIGINAL_GEO_MATERIALIZE = geo_autonomy._materialize

# Browser tasks are human/browser-session work and therefore get a slightly
# longer stale window than one API request. Five minutes is long enough for a
# normal page round-trip while still preventing an abandoned task from holding
# the queue indefinitely.
STALE_BROWSER_SECONDS = 5 * 60
STALE_CLOUD_SECONDS = 5 * 60
CLOUD_PROVIDER = geo_autonomy.geo_cloud_executor.PROVIDER
_ACTIVE_OR_TERMINAL_BLOCKING_STATES = {
    "queued",
    "running",
    "failed",
    "paused",
    "authorization_required",
}
_LAST_RECOVERY = {
    "at": "",
    "requeued": 0,
    "failed": 0,
    "items": [],
}


def _iso_epoch(value):
    text = str(value or "").strip()
    if not text:
        return 0.0
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except (TypeError, ValueError, OverflowError):
        return 0.0


def _is_browser_task(task):
    method = str(task.get("test_method") or "").strip().lower()
    provider = str(task.get("provider") or "").strip().lower()
    return method == "browser" or provider in {
        "browser_external_ai",
        "chatgpt_web",
    }


def _recover_stale_running_tasks():
    """Recover abandoned browser/cloud RUNNING tasks without bypassing auth.

    A stale browser task is only returned to the queue (or failed after its
    retry limit). This does not bypass login, CAPTCHA, 2FA or any provider risk
    control. It simply releases a dead RUNNING lease so another valid executor
    can claim work later.
    """
    global _LAST_RECOVERY
    payload = geo._load_queue()
    tasks = payload.get("tasks") or []
    now_epoch = time.time()
    changed = False
    requeued = 0
    failed = 0
    items = []

    for task in tasks:
        if task.get("state") != "running":
            continue
        provider = str(task.get("provider") or "")
        is_cloud = provider == CLOUD_PROVIDER
        is_browser = _is_browser_task(task)
        if not is_cloud and not is_browser:
            continue

        reference = (
            _iso_epoch(task.get("heartbeat_at"))
            or _iso_epoch(task.get("started_at"))
            or _iso_epoch(task.get("updated_at"))
        )
        if not reference:
            continue
        stale_after = STALE_CLOUD_SECONDS if is_cloud else STALE_BROWSER_SECONDS
        age = max(0.0, now_epoch - reference)
        if age < stale_after:
            continue

        retry_count = int(task.get("retry_count") or 0)
        configured_max = int(task.get("max_retries") or (3 if is_cloud else 2))
        max_retries = max(configured_max, 3) if is_cloud else max(1, configured_max)
        task["max_retries"] = max_retries
        event = {
            "event": "STALE_LEASE_RECOVERED",
            "at": now_iso(),
            "provider": provider,
            "age_seconds": int(age),
            "retry_count": retry_count,
        }

        if retry_count < max_retries:
            task["retry_count"] = retry_count + 1
            task["state"] = "queued"
            task["run_id"] = ""
            task["executor_id"] = ""
            task["started_at"] = ""
            task["heartbeat_at"] = ""
            task["authorization_reason"] = ""
            task["failure_reason"] = ""
            task["failure_code"] = ""
            task["last_error"] = "stale_running_lease_requeued"
            task["stale_recovered_at"] = now_iso()
            task["updated_at"] = now_iso()
            event["action"] = "requeued"
            event["retry_count"] = task["retry_count"]
            requeued += 1
        else:
            task["state"] = "failed"
            task["failure_reason"] = "stale_running_retry_limit_reached"
            task["failure_code"] = "STALE_RUNNING"
            task["finished_at"] = now_iso()
            task["updated_at"] = now_iso()
            event["action"] = "failed"
            failed += 1

        events = list(task.get("execution_events") or [])
        events.append(event)
        task["execution_events"] = events[-50:]
        items.append(
            {
                "task_id": task.get("task_id") or "",
                "question_id": task.get("question_id") or "",
                "provider": provider,
                "action": event["action"],
                "age_seconds": int(age),
                "retry_count": int(task.get("retry_count") or 0),
            }
        )
        changed = True

    if changed:
        geo._save_queue(payload)
        for item in items:
            geo._audit("geo_stale_task_recovered", item)

    _LAST_RECOVERY = {
        "at": now_iso(),
        "requeued": requeued,
        "failed": failed,
        "items": items[-20:],
    }
    return dict(_LAST_RECOVERY)


def _materialize_current_cycle(target, *, include_completed=False):
    """Create only missing tasks for the current cycle.

    #644 inherited a subtle bug from the earlier staged controller: every
    historical cloud task was treated as an active duplicate. A new cycle could
    therefore report 0/1 while also showing queue=0 because a terminal task from
    an older cycle silently blocked creation of the new run.
    """
    target = max(1, min(int(target or 1), 50))
    questions = geo.question_set().get("questions") or []
    data = geo_autonomy._load()
    cycle_started_at = str(data.get("cycle_started_at") or "")
    cycle_epoch = _iso_epoch(cycle_started_at)

    if include_completed:
        completed = set()
    else:
        completed = geo_autonomy._auto_question_ids(cycle_started_at)

    current_cycle_existing = set()
    for task in geo_autonomy._auto_tasks():
        question_id = task.get("question_id")
        if not question_id:
            continue
        created_epoch = _iso_epoch(task.get("created_at"))
        belongs_to_cycle = not cycle_epoch or (created_epoch and created_epoch >= cycle_epoch)
        if not belongs_to_cycle:
            continue
        if task.get("state") in _ACTIVE_OR_TERMINAL_BLOCKING_STATES:
            current_cycle_existing.add(question_id)

    wanted = [
        item
        for item in questions[:target]
        if item.get("question_id") not in completed
        and item.get("question_id") not in current_cycle_existing
    ]
    if not wanted:
        return 0

    decision = geo.decision()
    batch_size = max(1, min(int(decision.get("daily_test_limit") or 10), 50))
    created = 0
    for offset in range(0, len(wanted), batch_size):
        chunk = wanted[offset : offset + batch_size]
        result = geo.create_and_enqueue_plan(
            limit=len(chunk),
            provider=CLOUD_PROVIDER,
            test_method="api",
            mission_id=decision.get("mission_id") or "GEO-BASELINE-ROUND-1",
            question_ids=[item.get("question_id") for item in chunk],
        )
        created += int(result.get("created") or 0)
    return created


def _geo_run_once_guarded(transport=None):
    _recover_stale_running_tasks()
    return _ORIGINAL_GEO_RUN_ONCE(transport=transport)


def _geo_status_with_recovery():
    _recover_stale_running_tasks()
    value = geo_autonomy.status()
    if isinstance(value, dict):
        value = dict(value)
        value["stale_recovery"] = dict(_LAST_RECOVERY)
    return value


def _origin_allowed(handler):
    origin = handler.headers.get("Origin")
    allowed = {
        f"http://127.0.0.1:{handler.server.server_port}",
        f"http://localhost:{handler.server.server_port}",
    }
    return not origin or origin in allowed


def _read_json_body(handler):
    length = int(handler.headers.get("Content-Length", "0") or 0)
    if length < 0 or length > 64 * 1024:
        raise ValueError("请求内容过大")
    if not length:
        return {}
    return json.loads(handler.rfile.read(length) or b"{}")


def _serve_search_with_geo_autonomy(handler):
    """Append the autonomy UI to the already-loaded search workspace."""
    web = server.get_web_path()
    source = (web / "operational-search.js").read_text(encoding="utf-8")
    autonomy = (web / "geo-autonomy.js").read_text(encoding="utf-8")
    data = (source + "\n;\n" + autonomy).encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/javascript; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _combined_status():
    value = _ORIGINAL_SEO_STATUS()
    value["geo_autonomy"] = _geo_status_with_recovery()
    return value


def _combined_run_once(force=False):
    """Keep the SEO cycle and add one recovered, truth-gated GEO tick."""
    seo_result = _ORIGINAL_SEO_RUN_ONCE(force=force)
    geo_result = geo_autonomy.run_once()
    if isinstance(seo_result, dict):
        result = dict(seo_result)
    else:
        result = {"seo_result": seo_result}
    result["geo_autonomy"] = geo_result
    return result


_UNATTENDED_CLOUD_TARGET = 50
_UNATTENDED_CLOUD_STARTUP_DELAY_SECONDS = 12
_AUTO_ARM_TIMER = None


def _arm_unattended_cloud_scan():
    """#682 automatically arm the verified Doubao/cloud GEO scan.

    The cloud scan is C-level auxiliary evidence and therefore may run without
    the manual external-browser Evidence gate. A user pause is always respected.
    Once the saved cloud route is verified, an idle or partially staged install
    is promoted to the full 50-question unattended target and continues daily.
    """
    _recover_stale_running_tasks()
    current = geo_autonomy.geo_cloud_executor.status()
    data = geo_autonomy._load()

    # Preserve an explicit owner pause. The worker remains alive so Resume can
    # continue immediately, but #682 never silently overrides Pause.
    if data.get("paused"):
        geo_autonomy.start_worker()
        return {
            "armed": False,
            "reason": "owner_paused",
            "target": int(data.get("target") or 1),
            "executor_ready": bool(current.get("ready")),
        }

    if not current.get("ready"):
        geo_autonomy.start_worker()
        return {
            "armed": False,
            "reason": current.get("reason") or "verified_cloud_route_required",
            "target": int(data.get("target") or 1),
            "executor_ready": False,
        }

    changed = False
    if not data.get("continuous", True):
        data["continuous"] = True
        changed = True
    if int(data.get("recheck_interval_seconds") or 0) <= 0:
        data["recheck_interval_seconds"] = 24 * 60 * 60
        changed = True
    if changed:
        geo_autonomy._save(data)

    current_target = int(data.get("target") or 1)
    if not data.get("enabled") or current_target < _UNATTENDED_CLOUD_TARGET:
        status = geo_autonomy.start(target=_UNATTENDED_CLOUD_TARGET)
        return {
            "armed": True,
            "reason": "verified_cloud_route_auto_started",
            "target": int(status.get("target") or _UNATTENDED_CLOUD_TARGET),
            "executor_ready": True,
        }

    geo_autonomy.start_worker()
    return {
        "armed": False,
        "reason": "already_running_or_monitoring",
        "target": current_target,
        "executor_ready": True,
    }


def _schedule_unattended_cloud_scan():
    """Defer first paint, then keep retrying the saved Doubao route until ready."""
    global _AUTO_ARM_TIMER
    if _AUTO_ARM_TIMER is not None and _AUTO_ARM_TIMER.is_alive():
        return {"scheduled": False, "reason": "already_scheduled"}

    attempts = {"count": 0, "max": 40}

    def invoke():
        global _AUTO_ARM_TIMER
        attempts["count"] += 1
        retry = False
        try:
            result = _arm_unattended_cloud_scan()
            retry = (
                not result.get("executor_ready")
                and result.get("reason") != "owner_paused"
                and attempts["count"] < attempts["max"]
            )
        except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
            retry = attempts["count"] < attempts["max"]
            try:
                data = geo_autonomy._load()
                data["last_error"] = f"自动GEO延迟启动失败: {str(error)[:720]}"
                data["last_run_at"] = now_iso()
                geo_autonomy._save(data)
            except (OSError, ValueError, RuntimeError, TypeError, KeyError):
                pass

        if retry:
            timer = threading.Timer(15, invoke)
            timer.daemon = True
            timer.name = "r8-19-geo-auto-arm-retry"
            _AUTO_ARM_TIMER = timer
            timer.start()

    timer = threading.Timer(_UNATTENDED_CLOUD_STARTUP_DELAY_SECONDS, invoke)
    timer.daemon = True
    timer.name = "r8-19-geo-auto-arm-after-ui"
    _AUTO_ARM_TIMER = timer
    timer.start()
    return {
        "scheduled": True,
        "delay_seconds": _UNATTENDED_CLOUD_STARTUP_DELAY_SECONDS,
        "retry_seconds": 15,
        "max_attempts": attempts["max"],
        "reason": "protect_first_paint_then_retry_until_verified_route_ready",
    }


def install():
    global _INSTALLED
    if _INSTALLED:
        return

    # Patch the GEO controller before starting its worker. The worker resolves
    # these module globals on every iteration, so both startup recovery and all
    # later cycles use the #645 behavior.
    geo_autonomy._materialize = _materialize_current_cycle
    geo_autonomy.run_once = _geo_run_once_guarded

    # run.py imports this patch before importing run_once/status from the SEO
    # core module. Keep the existing scheduler as an additional recovery tick.
    seo_core.run_once = _combined_run_once
    seo_core.status = _combined_status

    original_get = server.DashboardHandler.do_GET
    original_post = server.DashboardHandler.do_POST

    def do_get(handler):
        path = urlsplit(handler.path).path
        if path == "/operational-search.js":
            try:
                _serve_search_with_geo_autonomy(handler)
            except OSError as error:
                handler._json_error(500, error)
            return
        if path == "/api/r8-14/seo-geo/autonomy":
            try:
                handler._json_ok(_combined_status())
            except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
                handler._json_error(400, error)
            return
        if path == "/api/r8-19/geo/autonomy":
            try:
                handler._json_ok(_geo_status_with_recovery())
            except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
                handler._json_error(400, error)
            return
        return original_get(handler)

    def do_post(handler):
        path = urlsplit(handler.path).path
        supported = {
            "/api/r8-14/seo-geo/autonomy/config",
            "/api/r8-14/seo-geo/autonomy/run",
            "/api/r8-19/geo/autonomy/start",
            "/api/r8-19/geo/autonomy/pause",
            "/api/r8-19/geo/autonomy/resume",
            "/api/r8-19/geo/autonomy/run",
            "/api/r8-19/geo/autonomy/retry-failed",
        }
        if path not in supported:
            return original_post(handler)
        if not _origin_allowed(handler):
            handler._json_error(403, "Cross-origin changes are not allowed")
            return
        try:
            payload = _read_json_body(handler)
            _recover_stale_running_tasks()
            if path == "/api/r8-14/seo-geo/autonomy/config":
                result = seo_core.configure(payload)
            elif path == "/api/r8-14/seo-geo/autonomy/run":
                result = _combined_run_once(force=bool(payload.get("force")))
            elif path == "/api/r8-19/geo/autonomy/start":
                # Missing target means the staged first gate, never an implicit
                # jump to 50. Explicit 3/10/50 buttons still work normally.
                result = geo_autonomy.start(target=payload.get("target") or 1)
            elif path == "/api/r8-19/geo/autonomy/pause":
                result = geo_autonomy.pause()
            elif path == "/api/r8-19/geo/autonomy/resume":
                result = geo_autonomy.resume()
            elif path == "/api/r8-19/geo/autonomy/retry-failed":
                result = geo_autonomy.retry_failed()
            else:
                result = {"result": geo_autonomy.run_once(), "status": _geo_status_with_recovery()}
            handler._json_ok(result)
        except (OSError, ValueError, RuntimeError, TypeError, KeyError, json.JSONDecodeError) as error:
            handler._json_error(400, error)

    server.DashboardHandler.do_GET = do_get
    server.DashboardHandler.do_POST = do_post
    server.DashboardHandler._kz_r8_14_seo_geo_autonomy = True
    server.DashboardHandler._kz_r8_19_geo_autonomy = True

    # #683: preserve #682 unattended behavior, but never start the cloud
    # network worker during module/server bootstrap. Give the owner shell and
    # GEO iframe a clean first-paint window, then auto-arm the verified route.
    _recover_stale_running_tasks()
    _schedule_unattended_cloud_scan()
    _INSTALLED = True


install()
