"""R8-20/R8-21 SEO/GEO growth operating-loop HTTP and scheduler bridge.

R8-24 extends the same scheduler with the GEO Growth OS. C-level Doubao/API
signals may drive low-risk operating work, while formal A/B truth remains
unchanged and independently evidence-gated.
"""
from __future__ import annotations

import json
import threading
import time
from collections import Counter
from urllib.parse import parse_qs, urlsplit

from backend import server
from backend import r8_19_geo_validation_patch as geo_validation_api
from core import runtime_resilience
from core.storage import data_root
from core import seo_geo_autonomy as seo_core
from core import seo_geo_source_tracking_patch as _seo_geo_source_tracking_patch  # noqa: F401
from core import seo_geo_growth_intelligence as growth
from core import r8_20_growth_truth_patch as _r8_20_growth_truth_patch  # noqa: F401
from core import geo_growth_orchestrator as geo_growth
from core import geo_growth_publish_bridge as _geo_growth_publish_bridge  # noqa: F401
from integrations import seo_geo_connector_router_v2 as connector_router

_INSTALLED = False
_ORIGINAL_RUN = seo_core.run_once
_ORIGINAL_STATUS = seo_core.status
_GEO_GROWTH_AUTO_START_DELAY_SECONDS = 20
_GEO_GROWTH_AUTO_START_TIMER = None

# Advanced GEO must never block the dashboard behind worker/file I/O.
# The first response exposes the immutable 50-question baseline immediately.
# Source files are read on a bounded worker and have independently truthful
# health states: "questions ready" does not claim receipts or A/B validation.
_GEO_EVIDENCE_LOCK = threading.Lock()
_GEO_EVIDENCE_CACHE = {
    "payload": None, "updated": 0.0, "started": 0.0, "refreshing": False,
    "error": "", "attempt": 0, "workers": [],
    "last_read_duration": None, "payload_bytes": 0,
}
_GEO_EVIDENCE_TTL_SECONDS = 20
_GEO_EVIDENCE_WORKER_TIMEOUT_SECONDS = 12
_GEO_EVIDENCE_MAX_WORKERS = 2
_GEO_EVIDENCE_PREWARM_TIMER = None

def _geo_evidence_seed(reason="", loading=True):
    # This deterministic, read-only function never accesses the Windows JSON
    # ledger or the shared I/O lock; it stays usable during a blocked writer.
    rows = geo_validation_api.geo_core._fixed_questions()
    totals = Counter(row.get("question_type") or "unknown" for row in rows)
    return {
        "snapshot_mode": "baseline_without_evidence",
        "snapshot_ready": False,
        "snapshot_stale": False,
        "refreshing": loading,
        "formal_ab_completed": None,
        "formal_ab_target": len(rows),
        "available_sections": 1,
        "total_sections": 4,
        "questions": rows,
        "question_set": {"version": geo_validation_api.geo_core.QUESTION_SET_VERSION,
                         "total": len(rows), "counts": dict(totals)},
        "queue": [], "receipts": [], "queue_summary": {},
        "health": {
            "dashboard": {"ok": False, "error": reason or "snapshot_pending"},
            "questions": {"ok": True, "error": ""},
            "queue": {"ok": False, "error": reason or "snapshot_pending"},
            "receipts": {"ok": False, "error": reason or "snapshot_pending"},
        },
        "retry_after_ms": 1300,
        "last_refresh_error": reason,
    }

def _geo_evidence_cached():
    now = time.monotonic()
    with _GEO_EVIDENCE_LOCK:
        state = _GEO_EVIDENCE_CACHE
        # Remove completed references; never launch an unbounded number of
        # workers when a Windows filesystem driver holds a thread indefinitely.
        state["workers"] = [t for t in state["workers"] if t.is_alive()]
        if state["refreshing"] and now - state["started"] > _GEO_EVIDENCE_WORKER_TIMEOUT_SECONDS:
            state["refreshing"] = False
            state["error"] = "后台证据文件读取超过12秒；50问基准仍可用，请检查数据文件或稍后重试"
            state["attempt"] += 1  # fence off any late result from the old worker

        payload = state["payload"]
        age = now - state["updated"] if payload else None
        refresh_needed = payload is None or age >= _GEO_EVIDENCE_TTL_SECONDS
        cooldown = now - state["started"] < 5
        can_start = len(state["workers"]) < _GEO_EVIDENCE_MAX_WORKERS
        if refresh_needed and not state["refreshing"] and can_start and not cooldown:
            state["attempt"] += 1
            token = state["attempt"]
            state["refreshing"] = True
            state["started"] = now
            worker = threading.Thread(target=_geo_evidence_update_cache, args=(token,),
                                      name="kz-geo-evidence-snapshot", daemon=True)
            state["workers"].append(worker)
            worker.start()
        if payload is not None:
            response = dict(payload)
            response.update(snapshot_ready=True, snapshot_age_seconds=round(age, 1),
                            snapshot_stale=bool(age >= 60), refreshing=bool(state["refreshing"]),
                            last_refresh_error=str(state["error"] or "")[:240])
            return response

        reason = str(state["error"] or "")[:240]
        if not can_start and not state["refreshing"]:
            reason = reason or "后台证据读取线程未返回；50问基准可查看，其他证据暂不可用"
        return _geo_evidence_seed(reason, bool(state["refreshing"]))

def _schedule_geo_evidence_prewarm():
    """Warm read-only cache after HTTP routes install; no synchronous disk I/O."""
    global _GEO_EVIDENCE_PREWARM_TIMER
    if _GEO_EVIDENCE_PREWARM_TIMER is not None:
        return
    timer = threading.Timer(3.0, _geo_evidence_cached)
    timer.daemon = True
    timer.name = "kz-geo-evidence-prewarm"
    _GEO_EVIDENCE_PREWARM_TIMER = timer
    timer.start()


def _geo_evidence_health():
    """Nonblocking cache diagnostics, without reading GEO data files or API keys.

    read_seconds is the elapsed time of an ACTIVE refresh, not the age of an
    old worker start time.  A ready cache must never show hundreds of seconds
    of supposed read time after the worker already completed.
    """
    with _GEO_EVIDENCE_LOCK:
        state = _GEO_EVIDENCE_CACHE
        now = time.monotonic()
        active = bool(state.get("refreshing"))
        ready = state.get("payload") is not None
        payload = state.get("payload") or {}
        return {
            "evidence_ready": ready,
            "refreshing": active,
            "read_seconds": round(max(0.0, now - state["started"]), 2)
                if active and state.get("started") else 0.0,
            "worker_count": sum(t.is_alive() for t in (state.get("workers") or [])),
            "last_error": str(state.get("error") or "")[:240],
            "cache_age_seconds": round(max(0.0, now - state["updated"]), 2)
                if ready and state.get("updated") else None,
            "last_read_duration_seconds": state.get("last_read_duration"),
            "payload_bytes": int(state.get("payload_bytes") or 0),
            "snapshot_mode": str(payload.get("snapshot_mode") or "") if ready else "",
            "available_sections": payload.get("available_sections") if ready else None,
            "total_sections": payload.get("total_sections") if ready else None,
            "baseline_count": 50,
            "external_ai_verification": "requires_independently_authorized_provider",
            "truth": "离线50问不等于50次正式验证；豆包C级辅助不计正式A/B",
        }


def _geo_evidence_update_cache(token):
    started = time.monotonic()
    try:
        result = _geo_evidence_snapshot()
        payload_bytes = len(json.dumps(result, ensure_ascii=False).encode("utf-8"))
        finished = time.monotonic()
        with _GEO_EVIDENCE_LOCK:
            state = _GEO_EVIDENCE_CACHE
            if state["attempt"] == token:
                state.update(
                    payload=result, updated=finished, error="", refreshing=False,
                    last_read_duration=round(finished-started, 3),
                    payload_bytes=payload_bytes,
                )
    except Exception as error:
        finished = time.monotonic()
        with _GEO_EVIDENCE_LOCK:
            state = _GEO_EVIDENCE_CACHE
            if state["attempt"] == token:
                state.update(
                    error=f"{type(error).__name__}: {str(error)[:180]}", refreshing=False,
                    last_read_duration=round(finished-started, 3),
                )


def _origin_allowed(handler):
    origin = handler.headers.get("Origin")
    return not origin or origin in {
        f"http://127.0.0.1:{handler.server.server_port}",
        f"http://localhost:{handler.server.server_port}",
    }


def _read_json(handler):
    length = int(handler.headers.get("Content-Length", "0") or 0)
    if length < 0 or length > 256 * 1024:
        raise ValueError("请求内容过大")
    return json.loads(handler.rfile.read(length) or b"{}") if length else {}


def _days(handler):
    query = parse_qs(urlsplit(handler.path).query)
    try:
        value = int((query.get("days") or [30])[0])
    except (TypeError, ValueError):
        value = 30
    return value if value in {7, 30, 90} else 30


def _serve_operational_search(handler):
    web = server.get_web_path()
    names = [
        "operational-search.js",
        "geo-autonomy.js",
        "geo-phase3.js",
        "seo-geo-growth-intelligence.js",
        "seo-geo-connector-matrix.js",
        "geo-growth-os.js",
    ]
    source = "\n;\n".join((web / name).read_text(encoding="utf-8") for name in names)
    data = source.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/javascript; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _combined_status():
    value = _ORIGINAL_STATUS()
    result = dict(value) if isinstance(value, dict) else {"seo_geo": value}
    result["r8_20_growth"] = growth.status(30)
    result["connector_routes"] = connector_router.snapshot(check_live=False)
    result["runtime_health"] = runtime_resilience.snapshot()
    result["geo_growth_os"] = geo_growth.fast_status()
    return result


def _combined_run(force=False):
    # Refresh connection/capability health first. Existing SEO/GEO loops run
    # before R8-24 so a newly completed C-level cloud receipt can be converted
    # into an operating opportunity in the same scheduler pass.
    connector_routes = connector_router.sync_growth_health(check_live=False)
    value = _ORIGINAL_RUN(force=force)
    result = dict(value) if isinstance(value, dict) else {"seo_geo": value}
    result["r8_20_growth"] = growth.run_once(force=force)
    result["geo_growth_os"] = geo_growth.run_once(force=force)
    result["connector_routes"] = connector_routes
    result["runtime_health"] = runtime_resilience.snapshot()
    return result


def _ensure_geo_growth_auto_running():
    """#688 arm unattended GEO without doing heavy synchronous work at first open."""
    current = geo_growth.fast_status()

    # An explicit owner pause is a hard stop. Auto-start never overrides it.
    if current.get("paused"):
        return {
            "started": False,
            "reason": "owner_paused",
            "state": current.get("state"),
        }

    # Only persist the enabled state here. The existing scheduler executes the
    # real operating pass later; startup must not compete with GEO iframe/API
    # reads for JSON locks, network routes or AI workers.
    state = geo_growth.arm_unattended()
    return {
        "started": not bool(current.get("enabled")),
        "reason": "growth_os_armed_scheduler_will_run",
        "state": state.get("state"),
        "execution": "deferred_to_scheduler",
    }


def _geo_snapshot_file(relative_path, default):
    """Read one atomically-replaced JSON file without waiting on the global JSON lock.

    GEO writers already use tempfile + os.replace, so a reader can safely take a
    point-in-time snapshot.  If Windows briefly denies a read during replacement,
    retry a few milliseconds instead of blocking the owner UI behind worker I/O.
    """
    path = data_root() / relative_path
    if not path.exists():
        return default, ""
    last_error = ""
    for delay in (0.0, 0.01, 0.03, 0.08):
        if delay:
            time.sleep(delay)
        try:
            return json.loads(path.read_text(encoding="utf-8")), ""
        except (OSError, ValueError) as error:
            last_error = str(error)
    return default, last_error or "snapshot_unavailable"


def _geo_evidence_snapshot():
    """Fast, lock-free advanced GEO truth snapshot owned by R8-24.

    The normal storage API serializes every JSON read/write under one process-wide
    RLock. During a busy GEO cycle that is correct for mutation paths but can make
    an owner GET wait behind retries.  This endpoint is read-only and consumes the
    same atomically-replaced files directly, so advanced Evidence never blocks the
    main GEO workbench or sits at "读取中" for 12 seconds.
    """
    started = time.perf_counter()

    qset, q_error = _geo_snapshot_file(
        geo_validation_api.geo_core.QUESTION_SET_PATH,
        {},
    )
    if not isinstance(qset, dict):
        q_error = "question_set_schema_invalid"
        qset = {}
    if not qset.get("questions"):
        fallback_questions = geo_validation_api.geo_core._fixed_questions()
        counts = Counter(item.get("question_type") or "unknown" for item in fallback_questions)
        qset = {
            "version": geo_validation_api.geo_core.QUESTION_SET_VERSION,
            "counts": dict(counts),
            "questions": fallback_questions,
            "immutable_within_version": True,
        }

    queue_payload, queue_error = _geo_snapshot_file(
        geo_validation_api.geo_core.QUEUE_PATH,
        {"tasks": []},
    )
    receipts_payload, receipts_error = _geo_snapshot_file(
        geo_validation_api.geo_core.RECEIPTS_PATH,
        {"receipts": []},
    )

    if not isinstance(qset, dict):
        q_error = "question_set_schema_invalid"
        qset = {"questions": geo_validation_api.geo_core._fixed_questions()}
    if not isinstance(queue_payload, dict):
        queue_error = "queue_schema_invalid"
        queue_payload = {"tasks": []}
    if not isinstance(receipts_payload, dict):
        receipts_error = "receipts_schema_invalid"
        receipts_payload = {"receipts": []}
    raw_questions = qset.get("questions") or []
    if not isinstance(raw_questions, list) or any(not isinstance(x, dict) for x in raw_questions):
        q_error = "question_rows_schema_invalid"
        raw_questions = geo_validation_api.geo_core._fixed_questions()
    questions = list(raw_questions)
    raw_tasks = queue_payload.get("tasks") or []
    if not isinstance(raw_tasks, list):
        queue_error = "queue_rows_schema_invalid"
        raw_tasks = []
    tasks = [row for row in raw_tasks if isinstance(row, dict)]
    raw_receipts = receipts_payload.get("receipts") or []
    if not isinstance(raw_receipts, list):
        receipts_error = "receipt_rows_schema_invalid"
        raw_receipts = []
    all_receipts = [row for row in raw_receipts if isinstance(row, dict)]
    recent_receipts = list(reversed(all_receipts))[:50]

    task_counts = Counter(str(item.get("state") or "unknown") for item in tasks)
    queue_summary = {
        "total": len(tasks),
        "queued": task_counts.get("queued", 0),
        "running": task_counts.get("running", 0),
        "succeeded": task_counts.get("succeeded", 0),
        "failed": task_counts.get("failed", 0),
        "paused": task_counts.get("paused", 0),
        "authorization_required": task_counts.get("authorization_required", 0),
        "tasks": tasks,
    }

    official = [
        item for item in all_receipts
        if item.get("official_truth")
        and item.get("evidence_level") in geo_validation_api.geo_core.OFFICIAL_EVIDENCE_LEVELS
    ]
    formal_ids = {item.get("question_id") for item in official if item.get("question_id")}
    # Formal Evidence can be human-captured or truly automated. Distinguish
    # these without counting Doubao C-level auxiliary answers as external A/B.
    manual_ids = {
        item.get("question_id") for item in official
        if item.get("question_id") and str(item.get("test_method") or "").lower() in {"manual", "browser"}
    }
    automated_ids = {
        item.get("question_id") for item in official
        if item.get("question_id") and str(item.get("test_method") or "").lower() == "api"
    }
    total = len(questions) or 50

    health = {
        "dashboard": {"ok": True, "error": ""},
        "questions": {"ok": not bool(q_error), "error": q_error},
        "queue": {"ok": not bool(queue_error), "error": queue_error},
        "receipts": {"ok": not bool(receipts_error), "error": receipts_error},
    }
    # A missing file is a valid empty state on first run; only a failed direct
    # parse/read is unhealthy. The fixed 50 baseline is available in-process.
    if not q_error:
        health["questions"]["ok"] = True
    if not queue_error:
        health["queue"]["ok"] = True
    if not receipts_error:
        health["receipts"]["ok"] = True

    dashboard = {
        "official": {
            "tested": len(formal_ids),
            "remaining": max(0, total - len(formal_ids)),
            "evidence_count": len(official),
            "manual_tested": len(manual_ids),
            "automatic_tested": len(automated_ids),
        },
        "question_set": {
            "version": (qset or {}).get("version") or geo_validation_api.geo_core.QUESTION_SET_VERSION,
            "total": total,
            "counts": (qset or {}).get("counts") or {},
        },
        "queue": {key: value for key, value in queue_summary.items() if key != "tasks"},
    }

    available = sum(1 for value in health.values() if value.get("ok"))
    return {
        "snapshot_mode": "lock_free_atomic_files",
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
        "formal_ab_completed": len(formal_ids),
        "formal_ab_target": total,
        "formal_ab_manual": len(manual_ids),
        "formal_ab_automatic": len(automated_ids),
        "dashboard": dashboard,
        "questions": questions,
        "question_set": qset or {},
        "queue": tasks,
        "queue_summary": queue_summary,
        "receipts": recent_receipts,
        "health": health,
        "available_sections": available,
        "total_sections": 4,
    }


def _schedule_geo_growth_auto_start():
    """Defer full-loop start so GEO/SEO first-open remains fast and reliable."""
    global _GEO_GROWTH_AUTO_START_TIMER
    if _GEO_GROWTH_AUTO_START_TIMER is not None and _GEO_GROWTH_AUTO_START_TIMER.is_alive():
        return {"scheduled": False, "reason": "already_scheduled"}

    def invoke():
        try:
            _ensure_geo_growth_auto_running()
        except (OSError, ValueError, RuntimeError, TypeError, KeyError):
            # Arming is deliberately lightweight. Startup must remain non-fatal
            # even if persisted state is temporarily unavailable.
            pass

    timer = threading.Timer(_GEO_GROWTH_AUTO_START_DELAY_SECONDS, invoke)
    timer.daemon = True
    timer.name = "r8-24-geo-growth-auto-start"
    _GEO_GROWTH_AUTO_START_TIMER = timer
    timer.start()
    return {
        "scheduled": True,
        "delay_seconds": _GEO_GROWTH_AUTO_START_DELAY_SECONDS,
        "reason": "protect_first_paint_then_auto_start",
    }


def install():
    global _INSTALLED
    if _INSTALLED:
        return

    seo_core.run_once = _combined_run
    seo_core.status = _combined_status

    original_get = server.DashboardHandler.do_GET
    original_post = server.DashboardHandler.do_POST

    def do_get(handler):
        path = urlsplit(handler.path).path
        try:
            if path == "/operational-search.js":
                _serve_operational_search(handler)
                return
            if path in {"/api/r8-24/geo-growth", "/api/r8-24/geo-growth/fast"}:
                handler._json_ok(geo_growth.fast_status())
                return
            if path == "/api/r8-24/geo-growth/evidence":
                handler._json_ok(_geo_evidence_cached())
                return
            if path == "/api/r8-24/geo-growth/questions-baseline":
                handler._json_ok(_geo_evidence_seed("evidence_reader_not_required", loading=False))
                return
            if path == "/api/r8-24/geo-growth/evidence-health":
                handler._json_ok(_geo_evidence_health())
                return
            if path == "/api/r8-20/runtime-health":
                handler._json_ok(runtime_resilience.snapshot())
                return
            if path in {"/api/r8-20/seo-geo/connectors", "/api/r8-21/seo-geo/connectors"}:
                handler._json_ok(connector_router.snapshot(check_live=False))
                return
            if path == "/api/r8-21/seo-geo/controller-routes":
                handler._json_ok(connector_router.route_summary_for_controller(check_live=False))
                return
            if path == "/api/r8-20/seo-geo":
                payload = growth.status(_days(handler))
                payload["connector_routes"] = connector_router.snapshot(check_live=False)
                handler._json_ok(payload)
                return
            if path == "/api/r8-20/seo-geo/trends":
                handler._json_ok(growth.trends(_days(handler)))
                return
            if path == "/api/r8-20/seo-geo/governance":
                handler._json_ok({
                    "keyword": growth.keyword_governance(),
                    "internal_links": growth.internal_link_plan(),
                    "decay": growth.content_decay(),
                    "technical": growth.technical_seo_status(),
                    "sources": growth.third_party_source_gaps(),
                    "connector_routes": connector_router.snapshot(check_live=False),
                })
                return
            if path == "/api/r8-20/seo-geo/features":
                handler._json_ok({"count": 38, "items": growth.feature_registry(), "r8_21_unified_connector_router": True})
                return
        except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
            handler._json_error(400, error)
            return
        return original_get(handler)

    def do_post(handler):
        path = urlsplit(handler.path).path
        if path in {
            "/api/r8-24/geo-growth/start",
            "/api/r8-24/geo-growth/pause",
            "/api/r8-24/geo-growth/resume",
            "/api/r8-24/geo-growth/run",
            "/api/r8-24/geo-growth/retry",
        }:
            if not _origin_allowed(handler):
                handler._json_error(403, "Cross-origin changes are not allowed")
                return
            try:
                payload = _read_json(handler)
                if path.endswith("/start"):
                    result = geo_growth.start()
                elif path.endswith("/pause"):
                    result = geo_growth.pause()
                elif path.endswith("/resume"):
                    result = geo_growth.resume()
                elif path.endswith("/retry"):
                    result = geo_growth.retry_failed()
                else:
                    result = geo_growth.run_once(force=bool(payload.get("force", True)))
                handler._json_ok({"result": result, "growth": geo_growth.fast_status()})
            except (OSError, ValueError, RuntimeError, PermissionError, TypeError, KeyError, json.JSONDecodeError) as error:
                handler._json_error(400, error)
            return

        if path in {
            "/api/r8-24/geo-growth/evidence/bootstrap",
            "/api/r8-24/geo-growth/evidence/prepare",
            "/api/r8-24/geo-growth/evidence/receipt",
        }:
            if not _origin_allowed(handler):
                handler._json_error(403, "Cross-origin changes are not allowed")
                return
            try:
                payload = _read_json(handler)
                if path.endswith("/bootstrap"):
                    result = geo_validation_api.bootstrap_question_set(force=bool(payload.get("force")))
                elif path.endswith("/prepare"):
                    result = geo_validation_api._prepare_browser_task(payload)
                else:
                    result = geo_validation_api.geo_browser_validation.record_browser_result(payload)
                    geo_validation_api._refresh_analysis()
                handler._json_ok({"result": result, "evidence": _geo_evidence_snapshot()})
            except (OSError, ValueError, RuntimeError, PermissionError, TypeError, KeyError, json.JSONDecodeError) as error:
                handler._json_error(400, error)
            return

        # The legacy SEO page still posts this route from its primary
        # "运行一次增长循环" button. In R8-20/R8-21/R8-24 it invokes the full
        # autonomous controller, unified connectors, and GEO Growth OS.
        if path == "/api/r8-13/seo-geo/run":
            if not _origin_allowed(handler):
                handler._json_error(403, "Cross-origin changes are not allowed")
                return
            try:
                payload = _read_json(handler)
                result = seo_core.run_once(force=bool(payload.get("force", True)))
                handler._json_ok({
                    "result": result,
                    "growth": growth.status(int(payload.get("days") or 30)),
                    "geo_growth_os": geo_growth.fast_status(),
                    "connector_routes": connector_router.snapshot(check_live=False),
                    "runtime_health": runtime_resilience.snapshot(),
                    # Keep the R8-21 compatibility marker visible while R8-24
                    # adds the GEO operating loop on top of the same route.
                    "mode": "r8_21_full_autonomous_loop_with_unified_connectors+r8_24_geo_growth_os",
                })
            except (OSError, ValueError, RuntimeError, PermissionError, TypeError, KeyError, json.JSONDecodeError) as error:
                handler._json_error(400, error)
            return

        supported = {
            "/api/r8-20/seo-geo/refresh",
            "/api/r8-20/seo-geo/search-observation",
            "/api/r8-20/seo-geo/attribution",
            "/api/r8-20/seo-geo/dynamic-questions",
            "/api/r8-20/seo-geo/multi-ai",
            "/api/r8-20/seo-geo/fixed50-config",
            "/api/r8-20/seo-geo/fixed50-retest",
            "/api/r8-20/seo-geo/web-vitals",
            "/api/r8-20/seo-geo/connector-health",
            "/api/r8-20/seo-geo/internal-links",
            "/api/r8-20/seo-geo/refresh-content",
            "/api/r8-20/seo-geo/backup",
            "/api/r8-20/seo-geo/restore",
            "/api/r8-21/seo-geo/connectors/sync",
        }
        if path not in supported:
            return original_post(handler)
        if not _origin_allowed(handler):
            handler._json_error(403, "Cross-origin changes are not allowed")
            return
        try:
            payload = _read_json(handler)
            if path == "/api/r8-20/seo-geo/refresh":
                connector_router.sync_growth_health(check_live=False)
                result = seo_core.run_once(force=bool(payload.get("force", True)))
            elif path == "/api/r8-21/seo-geo/connectors/sync":
                result = connector_router.sync_growth_health(check_live=bool(payload.get("check_live", False)))
            elif path == "/api/r8-20/seo-geo/search-observation":
                result = growth.record_search_observation(payload)
            elif path == "/api/r8-20/seo-geo/attribution":
                result = growth.record_attribution(payload)
            elif path == "/api/r8-20/seo-geo/dynamic-questions":
                result = growth.discover_dynamic_questions(payload.get("candidates") or [], source=payload.get("source") or "owner_or_controller", evidence=payload.get("evidence") or "")
            elif path == "/api/r8-20/seo-geo/multi-ai":
                result = growth.schedule_multi_provider_validation(payload.get("providers") or [], limit=payload.get("limit") or 3, include_dynamic=bool(payload.get("include_dynamic", True)))
            elif path == "/api/r8-20/seo-geo/fixed50-config":
                result = growth.configure_fixed50_schedule(bool(payload.get("enabled")))
            elif path == "/api/r8-20/seo-geo/fixed50-retest":
                result = growth.schedule_fixed50_retest(provider=payload.get("provider") or "browser_external_ai", limit=payload.get("limit") or 50)
            elif path == "/api/r8-20/seo-geo/web-vitals":
                result = growth.ingest_web_vitals(payload)
            elif path == "/api/r8-20/seo-geo/connector-health":
                result = growth.record_connector_health(payload.get("name"), bool(payload.get("ok")), payload.get("detail") or "")
            elif path == "/api/r8-20/seo-geo/internal-links":
                result = growth.apply_internal_links(limit=payload.get("limit") or 20)
            elif path == "/api/r8-20/seo-geo/refresh-content":
                result = growth.queue_refresh_jobs(limit=payload.get("limit") or 10)
            elif path == "/api/r8-20/seo-geo/backup":
                result = growth.create_backup(payload.get("label") or "owner")
            else:
                result = growth.restore_backup(payload.get("backup_id"), confirm=bool(payload.get("confirm")))
            handler._json_ok({
                "result": result,
                "growth": growth.status(int(payload.get("days") or 30)),
                "geo_growth_os": geo_growth.fast_status(),
                "connector_routes": connector_router.snapshot(check_live=False),
                "runtime_health": runtime_resilience.snapshot(),
            })
        except (OSError, ValueError, RuntimeError, PermissionError, TypeError, KeyError, json.JSONDecodeError) as error:
            handler._json_error(400, error)

    server.DashboardHandler.do_GET = do_get
    server.DashboardHandler.do_POST = do_post
    server.DashboardHandler._kz_r8_20_seo_geo_growth = True
    server.DashboardHandler._kz_r8_21_unified_connectors = True
    server.DashboardHandler._kz_r8_24_geo_growth_os = True

    # #687: #683 already protects the first paint and starts the Doubao scan.
    # Start the top-level GEO Growth OS a few seconds later as well, so the
    # owner never has to press "启动 GEO 自动运营" in normal operation.
    _schedule_geo_evidence_prewarm()
    _schedule_geo_growth_auto_start()
    _INSTALLED = True


install()