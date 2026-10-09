"""Regression: a 20-second remote business connector cannot freeze ordinary GETs.

A live local HTTP server handles simultaneous owner requests while the mock
read-only remote business refresh is deliberately held. No user data/network.
"""
from __future__ import annotations

import concurrent.futures
import json
import sys
import threading
import time
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from unittest.mock import patch
from urllib.request import urlopen

SRC = Path(__file__).resolve().parents[2] / "05_V2.0.0_Source"
sys.path.insert(0, str(SRC))

from backend import server  # noqa: E402
from integrations import business_data  # noqa: E402


def get(url):
    started = time.perf_counter()
    with urlopen(url, timeout=4.0) as response:
        payload = response.read()
        code = response.status
    return code, payload, time.perf_counter() - started


def test_20_second_remote_refresh_never_blocks_regular_api():
    remote_entered = threading.Event()
    remote_release = threading.Event()
    calls = []

    def blocked_remote(*args, **kwargs):
        calls.append(time.perf_counter())
        remote_entered.set()
        assert remote_release.wait(8), "mock remote was not released by test"
        return {"status": "simulated_refresh"}

    # This patch deliberately exposes the legacy GET hook too: #770 called it
    # on almost every /api/ request, reproducing the actual field failure.
    with (
        patch.object(business_data, "_read_key", return_value="fake-test-key"),
        patch.object(business_data, "_status_config", return_value={"last_refresh": None}),
        patch.object(business_data, "refresh_business_source", side_effect=blocked_remote),
        patch.object(server, "refresh_business_if_due", blocked_remote, create=True),
    ):
        stop = business_data.start_background_refresh(
            initial_delay_seconds=0.0, check_interval_seconds=60
        )
        assert remote_entered.wait(2), "background refresh did not start"
        srv = ThreadingHTTPServer(
            ("127.0.0.1", 0),
            partial(server.DashboardHandler, directory=str(server.get_web_path())),
        )
        srv.daemon_threads = True
        thread = threading.Thread(target=srv.serve_forever, daemon=True)
        thread.start()
        try:
            base = f"http://127.0.0.1:{srv.server_port}"
            urls = [
                base + "/api/status",
                base + "/api/r7/agents",
                base + "/kz_local_direct_ui.js",
            ] * 4
            with concurrent.futures.ThreadPoolExecutor(max_workers=12) as pool:
                results = list(pool.map(get, urls))
            assert all(code == 200 for code, _, _ in results), results
            assert all(seconds < 1.2 for _, _, seconds in results), results
            assert len(calls) == 1, "owner GETs accidentally triggered extra remote refresh"
            assert b"Kazuizhi" in results[2][1], "static JS was not served"
            print("PASS: 12 concurrent GETs (API + JS) remain responsive during 20s remote sync")
        finally:
            remote_release.set()
            stop.set()
            srv.shutdown()
            srv.server_close()


def test_explicit_and_background_refresh_share_one_execution_lock():
    active = [0]
    peak = [0]
    lock = threading.Lock()
    entered = threading.Event()
    release = threading.Event()

    def slow_refresh(force=True):
        with lock:
            active[0] += 1
            peak[0] = max(peak[0], active[0])
        entered.set()
        assert release.wait(3), "mock did not resume"
        with lock:
            active[0] -= 1
        return {"ok": True}

    with patch.object(business_data, "_refresh_business_source_serial",
                      side_effect=slow_refresh):
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
            a = pool.submit(business_data.refresh_business_source, True)
            assert entered.wait(1), "first refresh not running"
            b = pool.submit(business_data.refresh_business_source, False)
            time.sleep(0.1)
            assert peak[0] == 1, "remote refresh operations overlapped"
            release.set()
            assert a.result(timeout=3)["ok"] and b.result(timeout=3)["ok"]
    assert peak[0] == 1
    print("PASS: explicit POST and background refresh do not overlap")


def test_route_categories_hide_dynamic_identifiers():
    from backend import r8_20_seo_geo_growth_patch as bridge
    assert bridge._http_request_category("/api/r8-22/autonomy") == "/api/r8-22/autonomy"
    assert bridge._http_request_category("/api/r8-23/growth-os") == "/api/r8-23/growth-os"
    assert bridge._http_request_category("/api/r7/engine") == "/api/r7/engine"
    assert bridge._http_request_category("/api/r8-22/sensitive-owner-secret") == "api:r8_other"
    assert bridge._http_request_category("/api/random-private-key-123") == "api:other"
    assert bridge._http_request_category("/kz_local_direct_ui.js") == "static_js"
    run = (SRC / "run.py").read_text(encoding="utf-8")
    assert "start_business_refresh_worker()," in run
    base = (SRC / "backend" / "server.py").read_text(encoding="utf-8")
    assert "refresh_business_if_due()" not in base
    print("PASS: background worker registered and route categories do not leak secrets")


if __name__ == "__main__":
    test_20_second_remote_refresh_never_blocks_regular_api()
    test_explicit_and_background_refresh_share_one_execution_lock()
    test_route_categories_hide_dynamic_identifiers()
