"""Regression: owner GEO read-only APIs must not block behind the JSON write lock."""
from __future__ import annotations

import json
import sys
import tempfile
import threading
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[2] / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))
from core import storage, phase1_acceptance, runtime_supervisor  # noqa: E402
from integrations import geo_browser_agent  # noqa: E402


def put(root, relative, payload):
    path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
    return path


def main():
    with tempfile.TemporaryDirectory(prefix="kz-geo-readonly-") as directory:
        root = Path(directory)
        started = datetime.now().astimezone().isoformat()
        put(root, phase1_acceptance.STORE, {
            "schema": phase1_acceptance.SCHEMA, "started_at": started,
            "samples": 77, "worker_cycles": 8, "worker_failures": 1,
            "geo_snapshot": {"formal_ab_completed": 0, "formal_ab_target": 50,
                             "incomplete_evidence": 50},
        })
        put(root, runtime_supervisor.STORE, {
            "schema": runtime_supervisor.SCHEMA, "running": True, "restart_count": 2,
        })
        put(root, runtime_supervisor.INSTALL_STORE, {"installed": True, "mode": "user_scheduled_task"})
        put(root, geo_browser_agent.STATE_PATH, {
            "schema": geo_browser_agent.SCHEMA, "agent_id": "test-registered-agent",
            "last_heartbeat_at": started, "sessions": {"doubao_web": {"state": "ready"}},
            "token_hash": "never-display-this",
        })

        with patch.object(storage, "data_root", lambda: root):
            acquired = threading.Event()
            release = threading.Event()
            def hold_writer_lock():
                with storage._JSON_IO_LOCK:
                    acquired.set()
                    release.wait(8)
            holder = threading.Thread(target=hold_writer_lock, daemon=True)
            holder.start()
            assert acquired.wait(2), "failed to arrange simulated blocked JSON writer"
            try:
                before = time.monotonic()
                acceptance = phase1_acceptance.status()
                supervisor = runtime_supervisor.status()
                browser = geo_browser_agent.status()
                elapsed = time.monotonic() - before
                assert elapsed < 1.2, f"read-only owner status waited on global lock: {elapsed:.2f}s"
                assert acceptance["samples"] == 77, "historical acceptance samples were lost"
                assert acceptance["geo_snapshot"]["formal_ab_completed"] == 0, "formal evidence must not be fabricated"
                assert supervisor["installed"] and supervisor["restart_count"] == 2
                assert browser["connected"] and browser["ready_platforms"] == 1
                assert "token_hash" not in browser
            finally:
                release.set()
                holder.join(3)

            evidence_path = root / phase1_acceptance.STORE
            evidence_path.write_text("{BROKEN", encoding="utf-8")
            try:
                phase1_acceptance.status()
            except OSError:
                pass  # corrupt authoritative data must fail closed
            else:
                raise AssertionError("corrupt ledger silently converted to empty or passed evidence")

    print("PASS: #802 acceptance/supervisor/browser state reads stay nonblocking, fail closed, preserve truth")


if __name__ == "__main__":
    main()
