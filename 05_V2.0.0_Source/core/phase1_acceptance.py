"""Durable seven-day Phase-1 acceptance ledger.

The ledger measures process continuity, worker health, connector truth and GEO
evidence completeness.  It never turns configuration, submissions or ordinary
model answers into external business proof.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta

from core.storage import now_iso, read_json, write_json


STORE = "r8_25/phase1_acceptance.json"
HISTORY_STORE = "r8_25/phase1_acceptance_history.json"
SCHEMA = "kz.phase1-acceptance.v1"
HISTORY_SCHEMA = "kz.phase1-acceptance-history.v1"
TARGET_DAYS = 7
SAMPLE_INTERVAL_SECONDS = 60
SILENT_GAP_SECONDS = 15 * 60
TARGET_UPTIME_RATIO = 0.995
TARGET_WORKER_SUCCESS_RATIO = 0.95


def _parse(value):
    try:
        stamp = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        return stamp if stamp.tzinfo else stamp.astimezone()
    except (TypeError, ValueError, OverflowError):
        return None


def _default(*, candidate_id="", start_reason=""):
    stamp = now_iso()
    return {
        "schema": SCHEMA,
        "started_at": stamp,
        "target_days": TARGET_DAYS,
        "target_end_at": (datetime.now().astimezone() + timedelta(days=TARGET_DAYS)).isoformat(timespec="seconds"),
        "last_sample_at": "",
        "samples": 0,
        "healthy_samples": 0,
        "degraded_samples": 0,
        "observed_downtime_seconds": 0,
        "max_gap_seconds": 0,
        "process_pid": None,
        "process_restarts_observed": 0,
        "worker_cycles": 0,
        "worker_failures": 0,
        "last_worker_cycles_raw": 0,
        "last_worker_failures_raw": 0,
        "channel_snapshot": {},
        "geo_snapshot": {},
        "events": [],
        "status": "in_progress",
        "updated_at": stamp,
        "candidate_id": str(candidate_id or "").strip(),
        "start_reason": str(start_reason or "").strip(),
        "run_id": "PHASE1-" + datetime.now().astimezone().strftime("%Y%m%dT%H%M%S%z"),
    }


def _load():
    value = read_json(STORE, {})
    if not isinstance(value, dict) or value.get("schema") != SCHEMA:
        value = _default()
    for key, default in _default().items():
        value.setdefault(key, deepcopy(default))
    return value


def _save(value):
    value["schema"] = SCHEMA
    value["updated_at"] = now_iso()
    write_json(STORE, value)
    return value


def _archive(value):
    if not isinstance(value, dict) or not int(value.get("samples") or 0):
        return 0
    history = read_json(HISTORY_STORE, {})
    if not isinstance(history, dict) or history.get("schema") != HISTORY_SCHEMA:
        history = {"schema": HISTORY_SCHEMA, "runs": []}
    archived = status(value)
    archived["archived_at"] = now_iso()
    archived["final_status"] = archived.get("status")
    runs = [archived, *list(history.get("runs") or [])][:50]
    write_json(HISTORY_STORE, {"schema": HISTORY_SCHEMA, "runs": runs, "updated_at": now_iso()})
    return len(runs)


def history():
    value = read_json(HISTORY_STORE, {})
    if not isinstance(value, dict) or value.get("schema") != HISTORY_SCHEMA:
        value = {"schema": HISTORY_SCHEMA, "runs": []}
    rows = []
    for run in value.get("runs") or []:
        if not isinstance(run, dict):
            continue
        rows.append({key: run.get(key) for key in (
            "run_id", "candidate_id", "start_reason", "started_at", "target_end_at",
            "last_sample_at", "samples", "max_gap_seconds", "process_restarts_observed",
            "uptime_percent", "worker_success_percent", "progress_percent", "final_status",
        )})
    return {"schema": HISTORY_SCHEMA, "count": len(rows), "runs": rows}


def start(*, reset=False, candidate_id="", start_reason=""):
    archived_count = 0
    if reset:
        archived_count = _archive(_load())
        value = _default(candidate_id=candidate_id, start_reason=start_reason)
        value["previous_runs_archived"] = archived_count
    else:
        value = _load()
    return status(_save(value))


def _connector_public(connectors):
    rows = {}
    for key, item in (connectors or {}).items():
        if not isinstance(item, dict):
            continue
        rows[str(key)] = {
            "label": item.get("label") or key,
            "ready": bool(item.get("ready")),
            "configured": bool(item.get("configured")),
            "monitoring_only": bool(item.get("monitoring_only")),
            "authorization_state": item.get("authorization_state") or "",
            "automation_state": item.get("automation_state") or "",
            "last_success_at": item.get("last_success_at") or "",
            "last_failure_at": item.get("last_failure_at") or "",
            "last_failure_reason": item.get("last_failure_reason") or "",
        }
    return rows


def observe(*, runtime=None, search=None, geo=None, supervisor=None):
    value = _load()
    now = datetime.now().astimezone()
    previous = _parse(value.get("last_sample_at"))
    gap = max(0, int((now - previous).total_seconds())) if previous else 0
    if gap:
        value["max_gap_seconds"] = max(int(value.get("max_gap_seconds") or 0), gap)
        value["observed_downtime_seconds"] = int(value.get("observed_downtime_seconds") or 0) + max(
            0, gap - (SAMPLE_INTERVAL_SECONDS * 2)
        )

    runtime = runtime if isinstance(runtime, dict) else {}
    process = runtime.get("process") if isinstance(runtime.get("process"), dict) else {}
    pid = process.get("pid")
    if value.get("process_pid") and pid and value.get("process_pid") != pid:
        value["process_restarts_observed"] = int(value.get("process_restarts_observed") or 0) + 1
        value.setdefault("events", []).insert(0, {
            "at": now_iso(), "kind": "process_restart_observed",
            "previous_pid": value.get("process_pid"), "pid": pid,
        })
    if pid:
        value["process_pid"] = pid

    workers = runtime.get("workers") if isinstance(runtime.get("workers"), dict) else {}
    cycle_total = sum(int(row.get("cycles") or 0) for row in workers.values() if isinstance(row, dict))
    failure_total = sum(int(row.get("failures") or 0) for row in workers.values() if isinstance(row, dict))
    previous_cycles = int(value.get("last_worker_cycles_raw") or 0)
    previous_failures = int(value.get("last_worker_failures_raw") or 0)
    cycle_delta = cycle_total if cycle_total < previous_cycles else max(0, cycle_total - previous_cycles)
    failure_delta = failure_total if failure_total < previous_failures else max(0, failure_total - previous_failures)
    value["worker_cycles"] = int(value.get("worker_cycles") or 0) + cycle_delta
    value["worker_failures"] = int(value.get("worker_failures") or 0) + failure_delta
    value["last_worker_cycles_raw"] = cycle_total
    value["last_worker_failures_raw"] = failure_total

    healthy = bool(process.get("running")) and runtime.get("health") == "healthy"
    value["samples"] = int(value.get("samples") or 0) + 1
    if healthy:
        value["healthy_samples"] = int(value.get("healthy_samples") or 0) + 1
    else:
        value["degraded_samples"] = int(value.get("degraded_samples") or 0) + 1

    search = search if isinstance(search, dict) else {}
    value["channel_snapshot"] = {
        "observed_at": now_iso(),
        "connectors": _connector_public(search.get("connectors") or {}),
        "last_run_at": search.get("last_run_at") or "",
        "last_result_failed": len((search.get("last_result") or {}).get("failed") or []),
    }

    geo = geo if isinstance(geo, dict) else {}
    official = geo.get("official") if isinstance(geo.get("official"), dict) else {}
    completeness = geo.get("evidence_completeness") if isinstance(geo.get("evidence_completeness"), dict) else {}
    value["geo_snapshot"] = {
        "observed_at": now_iso(),
        "formal_ab_completed": int(official.get("tested") or 0),
        "formal_ab_target": int((geo.get("question_set") or {}).get("total") or 50),
        "mentioned": int(official.get("mentioned") or 0),
        "recommended": int(official.get("recommended") or 0),
        "cited": int(official.get("cited") or 0),
        "complete_evidence": int(completeness.get("complete") or 0),
        "incomplete_evidence": int(completeness.get("incomplete") or 0),
    }
    if isinstance(supervisor, dict):
        value["supervisor_snapshot"] = {
            key: supervisor.get(key) for key in (
                "mode", "installed", "running", "started_at", "last_heartbeat_at",
                "child_pid", "restart_count", "last_exit_code", "last_error",
            )
        }
    value["last_sample_at"] = now_iso()
    value["events"] = list(value.get("events") or [])[:100]
    _save(value)
    return status(value)


def status(value=None):
    value = deepcopy(value if isinstance(value, dict) else _load())
    started = _parse(value.get("started_at")) or datetime.now().astimezone()
    elapsed = max(0, int((datetime.now().astimezone() - started).total_seconds()))
    target_seconds = int(value.get("target_days") or TARGET_DAYS) * 86400
    downtime = min(elapsed, int(value.get("observed_downtime_seconds") or 0))
    uptime_ratio = 1.0 if elapsed <= 0 else max(0.0, (elapsed - downtime) / elapsed)
    cycles = int(value.get("worker_cycles") or 0)
    failures = int(value.get("worker_failures") or 0)
    worker_success_ratio = 1.0 if cycles <= 0 else max(0.0, (cycles - failures) / cycles)
    geo = value.get("geo_snapshot") or {}
    formal_completed = int(geo.get("formal_ab_completed") or 0)
    formal_target = int(geo.get("formal_ab_target") or 50)
    checks = {
        "duration_complete": elapsed >= target_seconds,
        "uptime_pass": uptime_ratio >= TARGET_UPTIME_RATIO,
        "worker_success_pass": worker_success_ratio >= TARGET_WORKER_SUCCESS_RATIO,
        "silent_gap_pass": int(value.get("max_gap_seconds") or 0) <= SILENT_GAP_SECONDS,
        "geo_formal_50_complete": formal_completed >= formal_target,
        "geo_evidence_complete": int(geo.get("incomplete_evidence") or 0) == 0,
    }
    if not checks["duration_complete"]:
        state = "in_progress"
    elif all(checks.values()):
        state = "passed"
    else:
        state = "needs_review"
    value.update({
        "status": state,
        "elapsed_seconds": elapsed,
        "remaining_seconds": max(0, target_seconds - elapsed),
        "progress_percent": round(min(100.0, elapsed / max(1, target_seconds) * 100), 2),
        "uptime_percent": round(uptime_ratio * 100, 3),
        "worker_success_percent": round(worker_success_ratio * 100, 2),
        "checks": checks,
        "thresholds": {
            "target_days": int(value.get("target_days") or TARGET_DAYS),
            "uptime_percent": TARGET_UPTIME_RATIO * 100,
            "worker_success_percent": TARGET_WORKER_SUCCESS_RATIO * 100,
            "max_silent_gap_seconds": SILENT_GAP_SECONDS,
            "formal_geo_target": formal_target,
        },
        "truth_rule": "验收通过必须同时满足连续运行、工作线程成功率、静默中断上限和真实GEO Evidence；配置、提交或C级回答不能替代验收证据。",
    })
    return value
