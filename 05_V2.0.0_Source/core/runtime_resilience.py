"""24/7 runtime resilience state for the Kazuizhi desktop controller.

This module is deliberately small and dependency-free.  It records bounded
worker heartbeats outside the install directory, so a long-running owner PC can
prove that the scheduler is still alive without letting monitoring failures stop
real work.  It does not fabricate business success: these are process-health
signals only.
"""
from __future__ import annotations

import os
import threading
import time
from copy import deepcopy
from datetime import datetime

from core.storage import now_iso, read_json, write_json

STORE = "r8_20/runtime_health.json"
SCHEMA = "kz.runtime-health.v1"
PERSIST_INTERVAL_SECONDS = 60
STALE_AFTER_SECONDS = 180
_LOCK = threading.RLock()
_STATE = None
_LAST_PERSIST_MONOTONIC = 0.0
_PROCESS_STARTED_MONOTONIC = time.monotonic()


def _default_state():
    stamp = now_iso()
    return {
        "schema": SCHEMA,
        "process": {
            "pid": os.getpid(),
            "running": False,
            "started_at": stamp,
            "last_heartbeat_at": stamp,
            "uptime_seconds": 0,
            "keep_awake": False,
            "restart_attempts": 0,
        },
        "workers": {},
        "previous_process": {},
        "monitor_error": None,
        "updated_at": stamp,
    }


def _ensure_state():
    global _STATE
    if _STATE is None:
        loaded = read_json(STORE, {})
        if not isinstance(loaded, dict) or loaded.get("schema") != SCHEMA:
            loaded = _default_state()
        loaded.setdefault("process", {})
        loaded.setdefault("workers", {})
        loaded.setdefault("previous_process", {})
        loaded.setdefault("monitor_error", None)
        _STATE = loaded
    return _STATE


def _persist(force=False):
    """Best-effort persistence; health monitoring must never stop real work."""
    global _LAST_PERSIST_MONOTONIC
    data = _ensure_state()
    now_mono = time.monotonic()
    if not force and now_mono - _LAST_PERSIST_MONOTONIC < PERSIST_INTERVAL_SECONDS:
        return
    data["updated_at"] = now_iso()
    try:
        write_json(STORE, data)
        data["monitor_error"] = None
        _LAST_PERSIST_MONOTONIC = now_mono
    except Exception as error:  # monitoring is fail-soft by design
        data["monitor_error"] = f"{type(error).__name__}: {error}"[:500]


def _touch_process(data):
    process = data.setdefault("process", {})
    process["pid"] = os.getpid()
    process["last_heartbeat_at"] = now_iso()
    process["uptime_seconds"] = max(0, int(time.monotonic() - _PROCESS_STARTED_MONOTONIC))


def start_process(*, keep_awake=False, restart_attempts=0):
    global _PROCESS_STARTED_MONOTONIC
    with _LOCK:
        data = _ensure_state()
        previous = deepcopy(data.get("process") or {})
        if previous:
            data["previous_process"] = previous
        _PROCESS_STARTED_MONOTONIC = time.monotonic()
        stamp = now_iso()
        data["process"] = {
            "pid": os.getpid(),
            "running": True,
            "started_at": stamp,
            "last_heartbeat_at": stamp,
            "uptime_seconds": 0,
            "keep_awake": bool(keep_awake),
            "restart_attempts": int(restart_attempts or 0),
        }
        data["workers"] = {}
        _persist(force=True)
        return snapshot()


def set_worker_enabled(name, enabled, detail=""):
    worker_name = str(name or "worker")[:80]
    with _LOCK:
        data = _ensure_state()
        worker = data.setdefault("workers", {}).setdefault(worker_name, {})
        worker.setdefault("cycles", 0)
        worker.setdefault("failures", 0)
        worker.setdefault("consecutive_failures", 0)
        worker["enabled"] = bool(enabled)
        worker["detail"] = str(detail or "")[:500]
        worker["last_heartbeat_at"] = now_iso()
        _touch_process(data)
        _persist(force=not enabled)
        return deepcopy(worker)


def heartbeat(name, *, ok=True, error=None, detail=None, force_persist=False):
    worker_name = str(name or "worker")[:80]
    with _LOCK:
        data = _ensure_state()
        worker = data.setdefault("workers", {}).setdefault(worker_name, {})
        worker["enabled"] = True
        worker["cycles"] = int(worker.get("cycles") or 0) + 1
        worker["failures"] = int(worker.get("failures") or 0)
        worker["consecutive_failures"] = int(worker.get("consecutive_failures") or 0)
        stamp = now_iso()
        worker["last_heartbeat_at"] = stamp
        if detail is not None:
            worker["detail"] = str(detail)[:500]
        if ok:
            worker["last_ok_at"] = stamp
            worker["consecutive_failures"] = 0
        else:
            worker["failures"] += 1
            worker["consecutive_failures"] += 1
            worker["last_error_at"] = stamp
            worker["last_error"] = f"{type(error).__name__}: {error}"[:500] if error is not None else "unknown_error"
        _touch_process(data)
        _persist(force=force_persist or not ok)
        return deepcopy(worker)


def record_restart_attempt(attempt, error):
    with _LOCK:
        data = _ensure_state()
        process = data.setdefault("process", {})
        process["restart_attempts"] = int(attempt or 0)
        process["last_restart_error_at"] = now_iso()
        process["last_restart_error"] = f"{type(error).__name__}: {error}"[:500]
        _touch_process(data)
        _persist(force=True)


def stop_process():
    with _LOCK:
        data = _ensure_state()
        process = data.setdefault("process", {})
        _touch_process(data)
        process["running"] = False
        process["stopped_at"] = now_iso()
        _persist(force=True)
        return snapshot()


def _age_seconds(stamp):
    if not stamp:
        return None
    try:
        value = datetime.fromisoformat(str(stamp))
        now = datetime.now().astimezone()
        if value.tzinfo is None:
            value = value.astimezone()
        return max(0, int((now - value).total_seconds()))
    except (TypeError, ValueError, OverflowError):
        return None


def snapshot(stale_after_seconds=STALE_AFTER_SECONDS):
    with _LOCK:
        data = deepcopy(_ensure_state())
        process = data.setdefault("process", {})
        if process.get("running"):
            process["uptime_seconds"] = max(0, int(time.monotonic() - _PROCESS_STARTED_MONOTONIC))
        unhealthy = []
        for name, worker in (data.get("workers") or {}).items():
            if not isinstance(worker, dict):
                continue
            enabled = bool(worker.get("enabled", True))
            age = _age_seconds(worker.get("last_heartbeat_at"))
            worker["heartbeat_age_seconds"] = age
            if not enabled:
                worker["state"] = "disabled"
            elif int(worker.get("consecutive_failures") or 0) >= 3:
                worker["state"] = "degraded"
                unhealthy.append(name)
            elif age is not None and age > int(stale_after_seconds):
                worker["state"] = "stale"
                unhealthy.append(name)
            else:
                worker["state"] = "healthy"
        data["health"] = "degraded" if unhealthy else "healthy"
        data["unhealthy_workers"] = unhealthy
        data["truth_rule"] = "运行健康只表示进程/线程仍在工作，不代表SEO收录、GEO命中或公网发布成功；业务结果仍需真实Evidence/Receipt。"
        return data
