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
    # Frontend owner status polling must be request-deduplicated and keep its
    # real data on transient HTTP errors. The existing fast health probe only
    # diagnoses readiness and must not manufacture KPI statistics.
    page=(SRC / "web" / "geo-growth-os.js").read_text(encoding="utf-8")
    for marker in ("statusLoading", "statusFailures", "geo-os-refresh",
                   "if(!ensureStructure() || statusLoading)",
                   "geo-growth/fast-health", "timeoutMs:5000"):
        assert marker in page, marker
    print("PASS: GEO frontend serial polling, manual refresh, real-snapshot recovery")
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




def test_geo_truth_unknown_and_stalled_threads():
    class Blocked:
        def is_alive(self):
            return True
    old=dict(bridge._GEO_FAST_CACHE)
    try:
        with bridge._GEO_FAST_LOCK:
            bridge._GEO_FAST_CACHE.update(payload=None, updated=0,
                started=time.monotonic()-32, refreshing=False,
                workers=[Blocked(), Blocked()], error="blocked file read", attempt=12)
        pending=bridge._geo_fast_cached()
        assert pending["status_ready"] is False
        assert pending["pending_reason"] == "blocked_reader_workers"
        health=bridge._geo_fast_health()
        assert health["worker_count"] == 2
        assert health["worker_limit_reached"] is True
        assert "blocked file read" in health["last_error"]
        frontend=(SRC/"web"/"geo-growth-os.js").read_text(encoding="utf-8")
        for text in ("技术阻塞：状态待核查", "后台数据尚未核实",
                     "worker_limit_reached", "真实机会明细尚未读取"):
            assert text in frontend, text
        print("PASS: exhausted snapshot workers show UNKNOWN rather than false zeros")
    finally:
        with bridge._GEO_FAST_LOCK:
            bridge._GEO_FAST_CACHE.clear()
            bridge._GEO_FAST_CACHE.update(old)


def test_late_lazy_module_retry_registration():
    source=(SRC/"web"/"r8_12_startup_coordinator.js").read_text(encoding="utf-8")
    assert "scheduleFailedModuleRecovery();" in source
    assert "failureRecoveryTimer" in source
    assert "failureRecoveryAttempts" in source
    assert "network_restored" in source
    assert "visibilitychange" in source
    assert "...Object.values(LAZY_SEQUENCE).flat()" in source
    assert "setTimeout(() => retryFailedModules(`auto_retry_" not in source
    print("PASS: late lazy module failures register bounded scheduled recovery")


def test_evidence_health_fallback_count():
    """Fallback may surface only truthful cached A/B, never baseline as completion."""
    saved = dict(bridge._GEO_EVIDENCE_CACHE)
    snapshot = {
        "snapshot_ready": True, "formal_ab_completed": 2, "formal_ab_target": 50,
        "formal_ab_manual": 2, "formal_ab_automatic": 0,
        "available_sections": 4, "total_sections": 4,
        "dashboard": {"official": {"evidence_count": 2}},
        "queue_summary": {"queued": 3, "running": 1, "authorization_required": 0},
    }
    try:
        with bridge._GEO_EVIDENCE_LOCK:
            bridge._GEO_EVIDENCE_CACHE.update(
                payload=snapshot, updated=time.monotonic()-12, refreshing=False,
                started=0.0, error="", workers=[], payload_bytes=200,
            )
        health = bridge._geo_evidence_health()
        assert health["evidence_ready"] is True
        summary=health["owner_summary"]
        assert summary["formal_ab_completed"]==2
        assert summary["formal_ab_manual"]==2
        assert summary["formal_ab_automatic"]==0
        assert summary["queue_summary"]["queued"]==3
        http=ThreadingHTTPServer(("127.0.0.1",0),bridge.server.DashboardHandler)
        http.daemon_threads=True
        thread=threading.Thread(target=http.serve_forever,daemon=True)
        thread.start()
        try:
            with urlopen(f"http://127.0.0.1:{http.server_address[1]}/api/r8-24/geo-growth/evidence-health", timeout=2) as response:
                actual=json.load(response)
            assert actual["owner_summary"]["formal_ab_completed"]==2
            assert actual["owner_summary"]["formal_ab_automatic"]==0
        finally:
            http.shutdown()
            http.server_close()
        with bridge._GEO_EVIDENCE_LOCK:
            bridge._GEO_EVIDENCE_CACHE["payload"]=None
        assert bridge._geo_evidence_health()["owner_summary"] is None
        print("PASS: evidence-health fallback exposes true 2/50 and never manufactures evidence")
    finally:
        with bridge._GEO_EVIDENCE_LOCK:
            bridge._GEO_EVIDENCE_CACHE.clear()
            bridge._GEO_EVIDENCE_CACHE.update(saved)


def test_lazy_module_recovery_registry():
    text=(SRC/"web"/"r8_12_startup_coordinator.js").read_text(encoding="utf-8")
    ui=(SRC/"web"/"geo-growth-os.js").read_text(encoding="utf-8")
    for marker in ("...Object.values(LAZY_SEQUENCE).flat()", "knownRecoveryModules",
                   "kz_site_tools.js", "kz_local_direct_ui.js",
                   "kz_async_control_ui.js"):
        assert marker in text, marker
    for marker in ("kzGeoEvidenceFallback", "/api/r8-24/geo-growth/evidence-health",
                   "Evidence 概览已恢复", "明细待同步"):
        assert marker in ui, marker
    print("PASS: all three connection lazy modules now have a registered retry route")


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



def test_seo_cached_dashboard_is_lock_free():
    """Cached SEO GET must not reopen the official GEO ledger per browser poll."""
    from backend import r8_13_seo_geo_patch as seo_bridge
    with patch.object(seo_bridge, "_load_last_good_payload", return_value={
        "_snapshot_saved_at": bridge.geo_validation_api.geo_core.now_iso(),
        "summary": {"public_pages": 20, "submitted_urls": 20, "indexed_urls": 0},
        "geo": {"truth_source": "r8-19-official-evidence", "tested_questions": 2},
        "service_health": {},
    }), patch.object(seo_bridge, "_overlay_formal_geo_truth",
                    side_effect=RuntimeError("GET must not read GEO ledger")), \
            patch.object(seo_bridge, "_kick_snapshot_refresh") as schedule:
        started = time.monotonic()
        payload = seo_bridge._fast_dashboard_response()
        assert time.monotonic() - started < 0.5
        assert payload["geo"]["tested_questions"] == 2
        assert payload["summary"]["submitted_urls"] == 20
        assert payload["summary"]["indexed_urls"] == 0
        schedule.assert_not_called()
    print("PASS: SEO cached HTTP view never enters global GEO ledger lock")
    ui = (SRC / "web" / "geo-growth-os.js").read_text(encoding="utf-8")
    for marker in ("status_ready:false", "formal_ab_completed:null", "unknownAware",
                   "Emergency pause remains available", "fast-health"):
        assert marker in ui, marker
    print("PASS: first-paint GEO unknowns do not masquerade as zeros; pause remains available")



def test_compact_owner_http_recovery():
    """Large real ledgers must not block or inflate the owner UI transport."""
    from unittest.mock import patch
    fixture = {
        "status_ready": True,
        "status_mode": "fast_snapshot",
        "state": "running",
        "mission": "live owner mission",
        "enabled": True,
        "paused": False,
        "snapshot_age_seconds": 12,
        "summary": {"signals": 90, "total": 250, "waiting_publish": 10},
        "cloud": {"state": "running", "completed": 3, "target": 50, "ready": True},
        "formal_ab_completed": 2,
        "formal_ab_target": 50,
        "opportunities": [{
            "id": str(i), "gap_label": "local repair "+str(i),
            "state": "waiting_publish", "score": 93,
            "large_internal_record": "SENSITIVE-EXCLUDED-"+"x"*200000,
            "question_text": "repair question "*100
        } for i in range(350)],
        "last_result": {"never_send": "x"*1000000},
    }
    with patch.object(bridge, "_geo_fast_cached", return_value=fixture):
        compact = bridge._geo_fast_ui_compact()
        assert compact["status_ready"] and compact["formal_ab_completed"] == 2
        assert compact["summary"]["total"] == 250
        assert len(compact["opportunities"]) <= 15
        output = json.dumps(compact, ensure_ascii=False)
        assert len(output.encode("utf-8")) < 25000, len(output)
        assert "SENSITIVE-EXCLUDED" not in output
        assert "never_send" not in output
        with patch.object(bridge, "_geo_fast_health", return_value={
            "status_ready": True, "snapshot_age_seconds": 15,
            "snapshot_stale": False, "refreshing": False
        }):
            with bridge._GEO_FAST_LOCK:
                old=dict(bridge._GEO_FAST_CACHE)
                bridge._GEO_FAST_CACHE["payload"]=fixture
            try:
                health = bridge._geo_fast_health_overview()
                assert health["owner_overview"]["formal_ab_completed"] == 2
                assert health["owner_overview"]["summary"]["total"] == 250
                assert "opportunities" not in health["owner_overview"]
            finally:
                with bridge._GEO_FAST_LOCK:
                    bridge._GEO_FAST_CACHE.clear()
                    bridge._GEO_FAST_CACHE.update(old)
        http = ThreadingHTTPServer(("127.0.0.1", 0), bridge.server.DashboardHandler)
        http.daemon_threads = True
        served = threading.Thread(target=http.serve_forever, daemon=True)
        served.start()
        try:
            root=f"http://127.0.0.1:{http.server_address[1]}"
            with urlopen(root+"/api/r8-24/geo-growth/fast-ui",timeout=2) as response:
                payload=json.load(response)
            assert payload["summary"]["total"]==250
            assert payload["formal_ab_completed"]==2
            assert len(payload["opportunities"])==15
        finally:
            http.shutdown()
            http.server_close()
    print("PASS: bounded GEO fast-ui transport, truthful health fallback, large-ledger HTTP")

if __name__ == "__main__":
    run()
    test_fast_snapshot_does_not_block_http()
    test_seo_cached_dashboard_is_lock_free()
    test_compact_owner_http_recovery()
    test_evidence_health_fallback_count()
    test_lazy_module_recovery_registry()
    test_geo_truth_unknown_and_stalled_threads()
    test_late_lazy_module_retry_registration()
