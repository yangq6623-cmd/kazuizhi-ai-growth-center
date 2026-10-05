"""R8-19 GEO autonomous cloud scan controller.

The controller turns the fixed GEO50 set into an unattended cloud-model queue.
It deliberately keeps two scoreboards separate:
- cloud auxiliary progress: verified cloud API answers, normally C-level;
- formal GEO progress: only A/B Evidence accepted by geo_validation.

Autonomy never upgrades an ordinary API answer into formal evidence.
"""
from __future__ import annotations

import threading
import time
from copy import deepcopy

from core import geo_analysis
from core import geo_validation as geo
from core.storage import now_iso, read_json, write_json
from integrations import geo_cloud_executor

STORE = "geo_validation/autonomy.json"
SCHEMA = "kz.geo-autonomy.v2"
ACCEPTANCE_TARGETS = (1, 3, 10, 50)
DEFAULT = {
    "schema": SCHEMA,
    "enabled": False,
    "paused": False,
    "target": 1,
    # A completed 1/3/10/50 acceptance run used to turn the controller off.
    # Production GEO monitoring must instead retain its verified API route and
    # re-check the same immutable baseline at a bounded daily cadence.
    "continuous": True,
    "recheck_interval_seconds": 24 * 60 * 60,
    "cycle_number": 0,
    "cycle_started_at": "",
    "cycle_completed_at": "",
    "next_cycle_at_epoch": 0.0,
    "started_at": "",
    "completed_at": "",
    "last_run_at": "",
    "last_error": "",
    "last_result": {},
}

_RUN_LOCK = threading.Lock()
_WORKER_LOCK = threading.Lock()
_WORKER_THREAD = None
_WORKER_STOP = None


def _load():
    value = read_json(STORE, deepcopy(DEFAULT))
    if not isinstance(value, dict) or value.get("schema") != SCHEMA:
        # Safety migration from pre-staged builds: never inherit an old
        # unattended target=50/enabled=True state. Existing queue/receipts are
        # preserved in their own ledgers, but owner acceptance restarts at 1.
        value = deepcopy(DEFAULT)
        value["last_result"] = {
            "action": "safe_stage_migration",
            "reason": "legacy autonomous state reset to staged 1-question acceptance",
            "at": now_iso(),
        }
        write_json(STORE, value)
    for key, default in DEFAULT.items():
        value.setdefault(key, deepcopy(default))
    value["target"] = max(1, min(int(value.get("target") or 1), 50))
    return value


def _save(value):
    data = dict(value or {})
    data["schema"] = SCHEMA
    data["updated_at"] = now_iso()
    write_json(STORE, data)
    return data


def _all_receipts():
    return geo.receipts(1000)


def _auto_receipts(since=""):
    return [
        item for item in _all_receipts()
        if item.get("provider") == geo_cloud_executor.PROVIDER
        and (not since or str(item.get("tested_at") or item.get("finished_at") or "") >= since)
    ]


def _formal_question_ids():
    return {
        item.get("question_id")
        for item in _all_receipts()
        if item.get("official_truth") and item.get("evidence_level") in geo.OFFICIAL_EVIDENCE_LEVELS
    }


def _auto_question_ids(since=""):
    return {item.get("question_id") for item in _auto_receipts(since) if item.get("question_id")}


def _auto_tasks():
    return [item for item in (geo.queue_summary().get("tasks") or []) if item.get("provider") == geo_cloud_executor.PROVIDER]


def _target_question_ids(target):
    questions = geo.question_set().get("questions") or []
    return {item.get("question_id") for item in questions[: max(1, min(int(target or 1), 50))] if item.get("question_id")}


def _completed_for_target(target, since=""):
    return len(_auto_question_ids(since) & _target_question_ids(target))


def _materialize(target, *, include_completed=False):
    questions = geo.question_set().get("questions") or []
    completed = set() if include_completed else _auto_question_ids()
    tasks = _auto_tasks()
    existing = {item.get("question_id") for item in tasks if item.get("question_id")}
    wanted = [item for item in questions[:target] if item.get("question_id") not in completed and item.get("question_id") not in existing]
    if not wanted:
        return 0

    decision = geo.decision()
    batch_size = max(1, min(int(decision.get("daily_test_limit") or 10), 50))
    created = 0
    for offset in range(0, len(wanted), batch_size):
        chunk = wanted[offset:offset + batch_size]
        result = geo.create_and_enqueue_plan(
            limit=len(chunk),
            provider=geo_cloud_executor.PROVIDER,
            test_method="api",
            mission_id=decision.get("mission_id") or "GEO-BASELINE-ROUND-1",
            question_ids=[item.get("question_id") for item in chunk],
        )
        created += int(result.get("created") or 0)
    return created


def _queue_counts(target):
    allowed = _target_question_ids(target)
    tasks = [item for item in _auto_tasks() if item.get("question_id") in allowed]
    states = {name: 0 for name in ("queued", "running", "succeeded", "failed", "paused", "authorization_required")}
    for item in tasks:
        state = str(item.get("state") or "")
        if state in states:
            states[state] += 1
    current = next((item for item in tasks if item.get("state") == "running"), None)
    if current is None:
        current = next((item for item in tasks if item.get("state") == "queued"), None)
    states["current"] = {
        "task_id": current.get("task_id") if current else "",
        "question_id": current.get("question_id") if current else "",
        "question_text": current.get("question_text") if current else "",
    }
    states["scope_target"] = int(target)
    states["historical_unscoped"] = max(0, len(_auto_tasks()) - len(tasks))
    return states


def _truth_snapshot():
    """Return one authoritative formal count and keep Phase-2 analysis aligned.

    Phase-1 dashboard owns the formal A/B truth. Phase-2 is a deterministic
    projection of the same receipts. If an older snapshot is stale, refresh it
    from the same receipt ledger before returning status so owner-facing cards
    cannot disagree about 0/50 versus 1/50.
    """
    dashboard = geo.dashboard()
    formal = int((dashboard.get("official") or {}).get("tested") or 0)
    analysis = geo_analysis.snapshot()
    analysed = int((analysis.get("summary") or {}).get("tested") or 0)
    if analysed != formal:
        analysis = geo_analysis.refresh(_all_receipts())
        analysed = int((analysis.get("summary") or {}).get("tested") or 0)
    return {
        "formal_ab_completed": formal,
        "phase2_analyzed": analysed,
        "consistent": formal == analysed,
    }


def status():
    data = _load()
    target = int(data.get("target") or 1)
    counts = _queue_counts(target)
    executor = geo_cloud_executor.status()
    truth = _truth_snapshot()
    completed = _completed_for_target(target, str(data.get("cycle_started_at") or ""))
    state = "idle"
    if data.get("enabled") and data.get("paused"):
        state = "paused"
    elif data.get("enabled") and completed >= target:
        state = "monitoring"
    elif data.get("enabled"):
        state = "running"
    elif completed >= target and target > 0:
        state = "completed"
    elif data.get("last_error"):
        state = "attention"
    return {
        "schema": SCHEMA,
        "state": state,
        "enabled": bool(data.get("enabled")),
        "paused": bool(data.get("paused")),
        "continuous": bool(data.get("continuous", True)),
        "recheck_interval_seconds": int(data.get("recheck_interval_seconds") or 24 * 60 * 60),
        "cycle_number": int(data.get("cycle_number") or 0),
        "next_cycle_at_epoch": float(data.get("next_cycle_at_epoch") or 0),
        "target": target,
        "acceptance_targets": list(ACCEPTANCE_TARGETS),
        "cloud_completed": completed,
        "cloud_remaining": max(0, target - completed),
        "formal_ab_completed": truth["formal_ab_completed"],
        "formal_ab_remaining": max(0, 50 - truth["formal_ab_completed"]),
        "phase2_analyzed": truth["phase2_analyzed"],
        "truth_consistent": truth["consistent"],
        "queue": counts,
        "executor": executor,
        "started_at": data.get("started_at") or "",
        "completed_at": data.get("completed_at") or "",
        "last_run_at": data.get("last_run_at") or "",
        "last_error": data.get("last_error") or "",
        "last_result": deepcopy(data.get("last_result") or {}),
        "truth_rule": "云端普通回答计入自动扫描进度但固定为C级辅助；正式GEO成绩只统计真实A/B Evidence；Phase 2 分析题数必须与正式A/B题数一致。",
    }


def start(target=1):
    data = _load()
    target = max(1, min(int(target or 1), 50))
    current = geo_cloud_executor.status()
    if not current.get("ready"):
        raise ValueError(current.get("reason") or "请先完成云端API连接验证")
    if not data.get("cycle_started_at"):
        data["cycle_started_at"] = now_iso()
        data["cycle_number"] = max(1, int(data.get("cycle_number") or 0))
    created = _materialize(target)
    data["enabled"] = True
    data["paused"] = False
    data["target"] = target
    data["completed_at"] = ""
    data["last_error"] = ""
    if not data.get("started_at") or _completed_for_target(target, data.get("cycle_started_at") or "") == 0:
        data["started_at"] = now_iso()
    data["last_result"] = {"action": "start", "target": target, "created": created, "at": now_iso()}
    _save(data)
    start_worker()
    return status()


def ensure_continuous_monitoring(target=50):
    """Re-arm a verified cloud route after an application restart or upgrade.

    Historical staged builds disabled themselves once the 50-question baseline
    had completed.  When continuous monitoring is enabled, a verified API
    route should retain the baseline and wait for its next bounded cycle rather
    than silently remaining off forever.  This never starts when credentials
    have not passed the existing connection check.
    """
    data = _load()
    current = geo_cloud_executor.status()
    if not data.get("continuous", True) or not current.get("ready"):
        return {"started": False, "reason": current.get("reason") or "continuous_monitoring_disabled", "status": status()}
    if not data.get("enabled"):
        start(target=max(1, min(int(target or data.get("target") or 1), 50)))
        return {"started": True, "reason": "verified_cloud_route_rearmed", "status": status()}
    start_worker()
    return {"started": False, "reason": "already_monitoring", "status": status()}


def pause():
    data = _load()
    data["enabled"] = True
    data["paused"] = True
    data["last_result"] = {"action": "pause", "target": int(data.get("target") or 1), "at": now_iso()}
    _save(data)
    return status()


def resume():
    data = _load()
    if not geo_cloud_executor.status().get("ready"):
        raise ValueError(geo_cloud_executor.status().get("reason") or "云端API未就绪")
    data["enabled"] = True
    data["paused"] = False
    data["last_error"] = ""
    data["last_result"] = {"action": "resume", "target": int(data.get("target") or 1), "at": now_iso()}
    _save(data)
    _materialize(int(data.get("target") or 1))
    start_worker()
    return status()


def retry_failed():
    data = _load()
    target = int(data.get("target") or 1)
    allowed = _target_question_ids(target)
    retried = 0
    errors = []
    for task in _auto_tasks():
        if task.get("question_id") not in allowed:
            continue
        if task.get("state") not in {"failed", "authorization_required"}:
            continue
        try:
            geo.retry_task(task.get("task_id"), approved_by=geo.CONTROLLER)
            retried += 1
        except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
            errors.append({"task_id": task.get("task_id"), "error": str(error)})
    if retried:
        data["enabled"] = True
        data["paused"] = False
        data["last_error"] = ""
    data["last_result"] = {"action": "retry_failed", "target": target, "retried": retried, "errors": errors[:10], "at": now_iso()}
    _save(data)
    start_worker()
    return status()


def run_once(transport=None):
    if not _RUN_LOCK.acquire(blocking=False):
        return {"ok": True, "skipped": True, "reason": "geo_autonomy_already_running"}
    try:
        data = _load()
        if not data.get("enabled"):
            return {"ok": True, "skipped": True, "reason": "geo_autonomy_disabled"}
        if data.get("paused"):
            return {"ok": True, "skipped": True, "reason": "geo_autonomy_paused"}

        target = int(data.get("target") or 1)
        cycle_started_at = str(data.get("cycle_started_at") or "")
        if not cycle_started_at:
            cycle_started_at = now_iso()
            data["cycle_started_at"] = cycle_started_at
            data["cycle_number"] = max(1, int(data.get("cycle_number") or 0))
        _materialize(target)
        completed_before = _completed_for_target(target, cycle_started_at)
        if completed_before >= target:
            if not data.get("continuous", True):
                data["enabled"] = False
                data["paused"] = False
                data["completed_at"] = data.get("completed_at") or now_iso()
                data["last_error"] = ""
                data["last_result"] = {"ok": True, "completed": completed_before, "target": target, "reason": "target_completed", "at": now_iso()}
                _save(data)
                return data["last_result"]
            now_epoch = time.time()
            next_cycle = float(data.get("next_cycle_at_epoch") or 0)
            if not next_cycle:
                next_cycle = now_epoch + max(300, int(data.get("recheck_interval_seconds") or 24 * 60 * 60))
                data["cycle_completed_at"] = now_iso()
                data["next_cycle_at_epoch"] = next_cycle
                data["last_error"] = ""
                data["last_result"] = {"ok": True, "skipped": True, "completed": completed_before, "target": target, "reason": "waiting_next_monitor_cycle", "next_cycle_at_epoch": next_cycle, "at": now_iso()}
                _save(data)
                return data["last_result"]
            if now_epoch < next_cycle:
                return {"ok": True, "skipped": True, "reason": "waiting_next_monitor_cycle", "next_cycle_at_epoch": next_cycle}
            data["cycle_number"] = int(data.get("cycle_number") or 0) + 1
            data["cycle_started_at"] = now_iso()
            data["cycle_completed_at"] = ""
            data["next_cycle_at_epoch"] = 0.0
            _materialize(target, include_completed=True)
            cycle_started_at = data["cycle_started_at"]

        result = geo_cloud_executor.run_once(transport=transport)
        data["last_run_at"] = now_iso()
        data["last_result"] = deepcopy(result)
        if result.get("ok") and result.get("receipt"):
            data["last_error"] = ""
            geo_analysis.refresh(geo.receipts(1000))
        elif not result.get("ok"):
            data["last_error"] = str(result.get("error") or "云端GEO自动任务失败")[:800]
        elif result.get("reason") == "non_cloud_geo_task_precedes_autonomous_queue":
            data["last_error"] = "队列前方存在人工/网页GEO任务；自动云端队列暂不抢占该任务。"

        completed_after = _completed_for_target(target, cycle_started_at)
        if completed_after >= target:
            if data.get("continuous", True):
                data["cycle_completed_at"] = now_iso()
                data["next_cycle_at_epoch"] = time.time() + max(300, int(data.get("recheck_interval_seconds") or 24 * 60 * 60))
            else:
                data["enabled"] = False
                data["paused"] = False
                data["completed_at"] = now_iso()
        _save(data)
        return result
    finally:
        _RUN_LOCK.release()


def _worker_loop(stop):
    while not stop.is_set():
        try:
            data = _load()
            if data.get("enabled") and not data.get("paused"):
                result = run_once()
                if result.get("receipt"):
                    stop.wait(2.0)
                    continue
                if result.get("reason") in {"geo_autonomy_already_running"}:
                    stop.wait(1.0)
                    continue
                stop.wait(5.0)
            else:
                stop.wait(2.0)
        except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
            data = _load()
            data["last_error"] = str(error)[:800]
            data["last_run_at"] = now_iso()
            _save(data)
            stop.wait(8.0)


def start_worker():
    global _WORKER_THREAD, _WORKER_STOP
    with _WORKER_LOCK:
        if _WORKER_THREAD is not None and _WORKER_THREAD.is_alive():
            return {"started": False, "reason": "already_running"}
        _WORKER_STOP = threading.Event()
        _WORKER_THREAD = threading.Thread(
            target=_worker_loop,
            args=(_WORKER_STOP,),
            name="r8-19-geo-cloud-autonomy",
            daemon=True,
        )
        _WORKER_THREAD.start()
        return {"started": True}
