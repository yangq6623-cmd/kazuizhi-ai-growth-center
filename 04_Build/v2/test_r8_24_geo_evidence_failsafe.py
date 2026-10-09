"""Field regression: GEO must display 50 real baseline questions while the
Windows Evidence file reader is blocked, and recover without fake A/B data."""
from __future__ import annotations

import json
import sys
import threading
import time
from http.server import ThreadingHTTPServer
from urllib.request import urlopen
from unittest.mock import patch
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "05_V2.0.0_Source"
sys.path.insert(0, str(SRC))
from backend import r8_20_seo_geo_growth_patch as bridge  # noqa: E402


def run() -> None:
    # The refresh must keep cycling without a browser request, and it must
    # delegate file reads to the existing bounded cache worker.
    with patch.object(bridge, "_geo_evidence_cached", return_value={}) as refresh, \
            patch.object(bridge.threading, "Timer") as timer_cls:
        bridge._geo_evidence_periodic_refresh()
        refresh.assert_called_once_with()
        timer_cls.assert_called_once_with(
            bridge._GEO_EVIDENCE_REFRESH_INTERVAL_SECONDS,
            bridge._geo_evidence_periodic_refresh,
        )
        timer_cls.return_value.start.assert_called_once_with()
        assert timer_cls.return_value.daemon is True
    print("PASS: GEO Evidence refresh independently rearms every 30 seconds")
    original = bridge._geo_evidence_snapshot
    original_cached = bridge._geo_evidence_cached
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
                "last_read_duration": None, "payload_bytes": 0,
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
        # Genuine loopback HTTP integration: a blocked Evidence filesystem
        # reader must not monopolize the user-facing threaded web server.
        http = ThreadingHTTPServer(("127.0.0.1", 0), bridge.server.DashboardHandler)
        http.daemon_threads = True
        served = threading.Thread(target=http.serve_forever, daemon=True)
        served.start()
        try:
            root = f"http://127.0.0.1:{http.server_address[1]}"
            for endpoint in ("liveness", "evidence-health", "evidence-compact"):
                t0 = time.monotonic()
                with urlopen(root + "/api/r8-24/geo-growth/" + endpoint, timeout=2) as resp:
                    payload = json.load(resp)
                assert time.monotonic() - t0 < 1.5, endpoint
                if endpoint == "liveness":
                    assert payload["server_ready"] is True
                if endpoint == "evidence-compact":
                    assert payload["snapshot_ready"] is False
                    assert len(payload["questions"]) == 50
        finally:
            http.shutdown()
            http.server_close()
        print("PASS: loopback GEO HTTP endpoints respond while Evidence reader is blocked")
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
        # The timed-out generation is fenced by its token. A replacement worker
        # may already be running; releasing the fixture permits true recovery.
        gate.set()
        time.sleep(0.1)
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            recovered = bridge._geo_evidence_cached()
            if recovered["snapshot_ready"]:
                break
            time.sleep(0.05)
        assert recovered["snapshot_ready"], "the stalled read did not recover"
        assert recovered["available_sections"] == 4
        assert recovered["formal_ab_completed"] == 0
        diagnostics = bridge._geo_evidence_health()
        assert diagnostics["evidence_ready"] is True and diagnostics["worker_count"] == 0, diagnostics
        assert diagnostics["payload_bytes"] > 0
        assert diagnostics["available_sections"] == 4
        assert isinstance(diagnostics["last_read_duration_seconds"], (float, int))
        with bridge._GEO_EVIDENCE_LOCK:
            bridge._GEO_EVIDENCE_CACHE["started"] = time.monotonic() - 826.81
            bridge._GEO_EVIDENCE_CACHE["refreshing"] = False
        idle = bridge._geo_evidence_health()
        assert idle["read_seconds"] == 0.0, idle
        assert idle["cache_age_seconds"] is not None, idle
        print("PASS: idle GEO Evidence cache does not report 826 seconds of active read")
        print("PASS: GEO 50-question fail-safe, no false A/B, 12s watchdog and recovery")
        bridge._geo_evidence_snapshot = original
        original_file = bridge._geo_snapshot_file
        questions = bridge._geo_evidence_seed()["questions"]
        names = bridge.geo_validation_api.geo_core
        data = {
            names.QUESTION_SET_PATH: {"version": names.QUESTION_SET_VERSION, "questions": questions},
            names.QUEUE_PATH: {"tasks": []},
            names.RECEIPTS_PATH: {"receipts": [
                {"question_id": questions[0]["question_id"], "official_truth": True, "evidence_level": "A", "test_method": "browser"},
                {"question_id": questions[1]["question_id"], "official_truth": True, "evidence_level": "A", "test_method": "manual"},
                {"question_id": questions[2]["question_id"], "official_truth": False, "evidence_level": "C", "test_method": "api"},
            ]},
        }
        try:
            bridge._geo_snapshot_file = lambda path, default: (data.get(path,default), "")
            proof = bridge._geo_evidence_snapshot()
            assert proof["formal_ab_completed"] == 2, proof
            assert proof["formal_ab_manual"] == 2 and proof["formal_ab_automatic"] == 0, proof
            assert proof["available_sections"] == 4 and len(proof["questions"]) == 50
            # Compact owner endpoint includes real official results, not the
            # full ledger or a generated/fabricated formal test count.
            bridge._geo_evidence_cached = lambda: proof
            compact = bridge._geo_evidence_compact()
            assert len(compact["questions"]) == 50
            assert compact["formal_ab_completed"] == 2
            assert compact["formal_ab_manual"] == 2
            assert compact["formal_ab_automatic"] == 0
            assert compact["available_sections"] == 4
            assert "tasks" not in compact["queue_summary"]
            assert "questions" not in compact["question_set"]
            assert len(compact["receipts"]) == 3
            assert compact["dashboard"]["official"]["tested"] == 2

            # Corrupt one legacy section: the rest remain readable and no
            # fake zero is allowed to replace prior official receipts.
            data[names.QUEUE_PATH] = {"tasks": "legacy_bad_shape"}
            partial = bridge._geo_evidence_snapshot()
            assert partial["available_sections"] == 3
            assert len(partial["questions"]) == 50
            assert partial["formal_ab_completed"] == 2
        finally:
            bridge._geo_snapshot_file = original_file
            bridge._geo_evidence_cached = original_cached
        print("PASS: GEO manual 2/50 != automatic 0/50; legacy queue corruption isolated")
    finally:
        gate.set()
        bridge._geo_evidence_snapshot = original
        reset()




def test_fast_snapshot_does_not_block_http():
    """Both GEO panes must remain responsive while global JSON access stalls."""
    original_status = bridge.geo_growth.fast_status
    saved = dict(bridge._GEO_FAST_CACHE)
    entered = threading.Event()
    release = threading.Event()

    def blocked_status():
        entered.set()
        if not release.wait(3):
            raise TimeoutError("synthetic slow GEO ledger")
        return {"status_mode": "fast_snapshot", "state": "running",
                "formal_ab_completed": 2, "formal_ab_target": 50,
                "summary": {"total": 9}, "pipeline": [], "opportunities": []}

    bridge.geo_growth.fast_status = blocked_status
    try:
        with bridge._GEO_FAST_LOCK:
            bridge._GEO_FAST_CACHE.update({
                "payload": None, "updated": 0.0, "started": 0.0,
                "refreshing": False, "error": "", "attempt": 0, "workers": [],
            })
        started = time.monotonic()
        pending = bridge._geo_fast_cached()
        assert time.monotonic() - started < 0.5
        assert pending["status_ready"] is False
        assert pending["formal_ab_completed"] is None
        assert entered.wait(2), "worker was not started"
        http = ThreadingHTTPServer(("127.0.0.1", 0), bridge.server.DashboardHandler)
        http.daemon_threads = True
        served = threading.Thread(target=http.serve_forever, daemon=True)
        served.start()
        try:
            root = f"http://127.0.0.1:{http.server_address[1]}"
            for endpoint in ("fast", "fast-health", "evidence-health"):
                start = time.monotonic()
                with urlopen(root + "/api/r8-24/geo-growth/" + endpoint, timeout=2) as resp:
                    payload = json.load(resp)
                assert time.monotonic() - start < 1.5, endpoint
                if endpoint == "fast":
                    assert payload["status_ready"] is False
                    assert payload["formal_ab_completed"] is None
        finally:
            http.shutdown()
            http.server_close()
        release.set()
        deadline = time.monotonic() + 3
        while time.monotonic() < deadline:
            ready = bridge._geo_fast_cached()
            if ready["status_ready"]:
                break
            time.sleep(0.05)
        assert ready["status_ready"] is True and ready["formal_ab_completed"] == 2
        assert ready["snapshot_stale"] is False
        with bridge._GEO_FAST_LOCK:
            bridge._GEO_FAST_CACHE["updated"] = time.monotonic() - 100
        stale = bridge._geo_fast_cached()
        assert stale["status_ready"] is True and stale["snapshot_stale"] is True
        print("PASS: fast GEO UI nonblocking, 2/50 truth, stale state and recovery")
    finally:
        release.set()
        bridge.geo_growth.fast_status = original_status
        with bridge._GEO_FAST_LOCK:
            bridge._GEO_FAST_CACHE.clear()
            bridge._GEO_FAST_CACHE.update(saved)


if __name__ == "__main__":
    run()
    test_fast_snapshot_does_not_block_http()
