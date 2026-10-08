"""Field regression: GEO must display 50 real baseline questions while the
Windows Evidence file reader is blocked, and recover without fake A/B data."""
from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "05_V2.0.0_Source"
sys.path.insert(0, str(SRC))
from backend import r8_20_seo_geo_growth_patch as bridge  # noqa: E402


def run() -> None:
    original = bridge._geo_evidence_snapshot
    gate = threading.Event()
    entered = threading.Event()
    completed = {
        "snapshot_mode": "lock_free_atomic_files",
        "formal_ab_completed": 0, "formal_ab_target": 50,
        "available_sections": 4, "total_sections": 4,
        "questions": bridge._geo_evidence_seed()["questions"],
        "receipts": [], "queue": [],
        "queue_summary": {}, "health": {
            key: {"ok": True, "error": ""}
            for key in ("dashboard", "questions", "queue", "receipts")
        },
    }

    def slow_snapshot():
        entered.set()
        if not gate.wait(3):
            raise TimeoutError("synthetic blocked filesystem")
        return completed

    def reset():
        with bridge._GEO_EVIDENCE_LOCK:
            bridge._GEO_EVIDENCE_CACHE.update({
                "payload": None, "updated": 0.0, "started": 0.0,
                "refreshing": False, "error": "", "attempt": 0, "workers": [],
            })

    bridge._geo_evidence_snapshot = slow_snapshot
    try:
        reset()
        started = time.monotonic()
        baseline = bridge._geo_evidence_cached()
        assert time.monotonic() - started < 0.5, "owner request blocked behind GEO I/O"
        assert not baseline["snapshot_ready"] and len(baseline["questions"]) == 50
        assert baseline["formal_ab_completed"] is None, "invented A/B on warmup"
        assert baseline["available_sections"] == 1, "unknown receipts claimed as healthy"
        assert entered.wait(2), "worker not started"
        with bridge._GEO_EVIDENCE_LOCK:
            bridge._GEO_EVIDENCE_CACHE["started"] = (
                time.monotonic() - bridge._GEO_EVIDENCE_WORKER_TIMEOUT_SECONDS - 1
            )
        started = time.monotonic()
        stalled = bridge._geo_evidence_cached()
        assert time.monotonic() - started < 0.5
        assert not stalled["snapshot_ready"]
        assert len(stalled["questions"]) == 50
        assert "12秒" in stalled["last_refresh_error"], stalled
        # A late response from a timed-out task must not replace newer truth.
        gate.set()
        time.sleep(0.1)
        assert bridge._GEO_EVIDENCE_CACHE["payload"] is None
        with bridge._GEO_EVIDENCE_LOCK:
            bridge._GEO_EVIDENCE_CACHE["workers"] = []
            bridge._GEO_EVIDENCE_CACHE["started"] = 0
        recovered = bridge._geo_evidence_cached()
        assert not recovered["snapshot_ready"]
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            recovered = bridge._geo_evidence_cached()
            if recovered["snapshot_ready"]:
                break
            time.sleep(0.05)
        assert recovered["snapshot_ready"], "the stalled read did not recover"
        assert recovered["available_sections"] == 4
        assert recovered["formal_ab_completed"] == 0
        print("PASS: GEO 50-question fail-safe, no false A/B, 12s watchdog and recovery")
    finally:
        gate.set()
        bridge._geo_evidence_snapshot = original
        reset()


if __name__ == "__main__":
    run()
