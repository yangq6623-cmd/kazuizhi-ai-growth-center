"""User-scoped Windows supervisor for unattended Kazuizhi recovery.

The scheduled task runs after the owner signs in and keeps the local runtime
alive.  It is deliberately labelled user-scoped: DPAPI credentials belong to
the Windows user and must not be moved to LocalSystem merely to claim a system
service.
"""
from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from core.storage import now_iso, read_json, write_json


STORE = "r8_25/runtime_supervisor.json"
INSTALL_STORE = "r8_25/service_install.json"
SCHEMA = "kz.runtime-supervisor.v1"
PROBE_INTERVAL_SECONDS = 15
MAX_BACKOFF_SECONDS = 60


def _load():
    value = read_json(STORE, {})
    if not isinstance(value, dict) or value.get("schema") != SCHEMA:
        value = {"schema": SCHEMA, "mode": "user_scheduled_task", "restart_count": 0}
    return value


def _save(**changes):
    value = _load()
    value.update(changes)
    value["schema"] = SCHEMA
    value["mode"] = "user_scheduled_task"
    value["updated_at"] = now_iso()
    write_json(STORE, value)
    return value


def status():
    value = _load()
    install = read_json(INSTALL_STORE, {})
    if isinstance(install, dict) and install.get("installed"):
        value["installed"] = True
        value["install_mode"] = install.get("mode") or "user_scheduled_task"
        value["install_detail"] = install.get("detail") or ""
        value["installed_at"] = install.get("installed_at") or value.get("installed_at")
    value.setdefault("installed", False)
    value.setdefault("running", False)
    value.setdefault("restart_count", 0)
    value["truth_rule"] = "用户级计划任务在Windows登录后守护运行；它保留当前用户DPAPI凭据，不冒充LocalSystem系统服务。"
    return value


def mark_install(*, installed, detail=""):
    return _save(installed=bool(installed), install_detail=str(detail or "")[:500], installed_at=now_iso())


def _alive(port):
    request = urllib.request.Request(
        f"http://127.0.0.1:{int(port)}/api/r8-24/geo-growth/liveness",
        headers={"User-Agent": "Kazuizhi-Phase1-Supervisor/1.0"},
    )
    try:
        with urllib.request.urlopen(request, timeout=2) as response:
            return 200 <= int(getattr(response, "status", 200) or 200) < 300
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, ValueError):
        return False


def _child_command(port):
    args = ["--supervised-child", "--no-browser", "--port", str(int(port))]
    if getattr(sys, "frozen", False):
        return [sys.executable, *args]
    return [sys.executable, str(Path(__file__).resolve().parents[1] / "run.py"), *args]


def run(*, port=8876):
    """Keep one runtime alive with bounded restart backoff."""
    started_at = now_iso()
    _save(running=True, started_at=started_at, last_heartbeat_at=started_at,
          supervisor_pid=os.getpid(), last_error="")
    backoff = 2
    child = None
    try:
        while True:
            if _alive(port):
                _save(running=True, last_heartbeat_at=now_iso(), child_pid=None,
                      state="existing_runtime_healthy")
                time.sleep(PROBE_INTERVAL_SECONDS)
                continue

            creation_flags = int(getattr(subprocess, "CREATE_NO_WINDOW", 0)) if os.name == "nt" else 0
            try:
                child = subprocess.Popen(  # noqa: S603 - fixed local executable/arguments
                    _child_command(port),
                    cwd=str(Path(sys.executable).resolve().parent if getattr(sys, "frozen", False)
                            else Path(__file__).resolve().parents[1]),
                    creationflags=creation_flags,
                )
                _save(running=True, child_pid=child.pid, last_heartbeat_at=now_iso(),
                      child_started_at=now_iso(), state="child_running", last_error="")
                while child.poll() is None:
                    healthy = _alive(port)
                    _save(
                        running=True,
                        child_pid=child.pid,
                        last_heartbeat_at=now_iso(),
                        state="child_healthy" if healthy else "child_starting_or_unresponsive",
                    )
                    if healthy:
                        backoff = 2
                    time.sleep(PROBE_INTERVAL_SECONDS)
                exit_code = child.returncode
                value = _load()
                restarts = int(value.get("restart_count") or 0) + 1
                _save(child_pid=None, last_exit_code=exit_code, last_exit_at=now_iso(),
                      restart_count=restarts, state="restart_backoff")
            except (OSError, ValueError) as error:
                value = _load()
                restarts = int(value.get("restart_count") or 0) + 1
                _save(child_pid=None, last_error=f"{type(error).__name__}: {error}"[:500],
                      last_exit_at=now_iso(), restart_count=restarts, state="restart_backoff")
            time.sleep(backoff)
            backoff = min(MAX_BACKOFF_SECONDS, backoff * 2)
            if _alive(port):
                backoff = 2
    except KeyboardInterrupt:
        return 0
    finally:
        _save(running=False, stopped_at=now_iso(), child_pid=None, state="stopped")
