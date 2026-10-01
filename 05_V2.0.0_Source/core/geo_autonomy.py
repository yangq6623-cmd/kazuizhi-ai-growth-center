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
SCHEMA = "kz.geo-autonomy.v1"
ACCEPTANCE_TARGETS = (1, 3, 10, 50)
DEFAULT = {
    "schema": SCHEMA,
    "enabled": False,
    "paused": False,
    "target": 50,
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
        value = deepcopy(DEFAULT)
    for key, default in DEFAULT.items():
        value.setdefault(key, deepcopy(default))
    value["target"] = max(1, min(int(value.get("target") or 50), 50))
    return value


def _save(value):
    data = dict(value or {})
    data["schema"] = SCHEMA
    data["updated_at"] = now_iso()
    write_json(STORE, data)
    return data


def _all_receipts():
    return geo.receipts(1000)


def _auto_receipts():
    return [item for item in _all_receipts() if item.get("provider") == geo_cloud_executor.PROVIDER]


def _formal_question_ids():
    return {
        item.get("question_id")
        for item in _all_receipts()
        if item.get("official_truth") and item.get("evidence_level") in geo.OFFICIAL_EVIDENCE_LEVELS
    }


def _auto_question_ids():
    return {item.get("question_id") for item in _auto_receipts() if item.get("question_id")}


def _auto_tasks():
    return [item for item in (geo.queue_summary().get("tasks") or []) if item.get("provider") == geo_cloud_executor.PROVIDER]


def _materialize(target):
    questions = geo.question_set().get("questions") or []
    completed = _auto_question_ids()
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


def _queue_counts():
    tasks = _auto_tasks()
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
    target = int(data.get("target") or 50)
    auxiliary_ids = _auto_question_ids()
    counts = _queue_counts()
    executor = geo_cloud_executor.status()
    truth = _truth_snapshot()
    completed = len(auxiliary_ids & {item.get("question_id") for item in (geo.question_set().get("questions") or [])[:target]})
    state = "idle"
    if data.get("enabled") and data.get("paused"):
        state = "paused"
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


def start(target=50):
    data = _load()
    target = max(1, min(int(target or 50), 50))
    current = geo_cloud_executor.status()
    if not current.get("ready"):
        raise ValueError(current.get("reason") or "请先完成云端API连接验证")
    created = _materialize(target)
    data["enabled"] = True
    data["paused"] = False
    data["target"] = target
    data["completed_at"] = ""
    data["last_error"] = ""
    if not data.get("started_at") or len(_auto_question_ids()) == 0:
        data["started_at"] = now_iso()
    data["last_result"] = {"action": "start", "target": target, "created": created, "at": now_iso()}
    _save(data)
    start_worker()
    return status()


def pause():
    data = _load()
    data["enabled"] = True
    data["paused"] = True
    data["last_result"] = {"action": "pause", "at": now_iso()}
    _save(data)
    return status()


def resume():
    data = _load()
    if not geo_cloud_executor.status().get("ready"):
        raise ValueError(geo_cloud_executor.status().get("reason") or "云端API未就绪")
    data["enabled"] = True
    data["paused"] = False
    data["last_error"] = ""
    data["last_result"] = {"action": "resume", "target": int(data.get("target") or 50), "at": now_iso()}
    _save(data)
    _materialize(int(data.get("target") or 50))
    start_worker()
    return status()


def retry_failed():
    retried = 0
    errors = []
    for task in _auto_tasks():
        if task.get("state") not in {"failed", "authorization_required"}:
            continue
        try:
            geo.retry_task(task.get("task_id"), approved_by=geo.CONTROLLER)
            retried += 1
        except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
            errors.append({"task_id": task.get("task_id"), "error": str(error)})
    data = _load()
    if retried:
        data["enabled"] = True
        data["paused"] = False
        data["last_error"] = ""
    data["last_result"] = {"action": "retry_failed", "retried": retried, "errors": errors[:10], "at": now_iso()}
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

        target = int(data.get("target") or 50)
        _materialize(target)
        completed_before = len(_auto_question_ids())
        if completed_before >= target:
            data["enabled"] = False
            data["paused"] = False
            data["completed_at"] = data.get("completed_at") or now_iso()
            data["last_error"] = ""
            data["last_result"] = {"ok": True, "completed": completed_before, "reason": "target_completed", "at": now_iso()}
            _save(data)
            return data["last_result"]

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

        completed_after = len(_auto_question_ids())
        if completed_after >= target:
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
