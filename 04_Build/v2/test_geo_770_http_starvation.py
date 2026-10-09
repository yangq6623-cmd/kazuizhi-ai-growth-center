"""Read-only concurrent localhost probe: report request starvation, not fake GEO zeros.

Uses a temporary random loopback port, never the actual owner's 8876 service,
and never reads or writes the user's business data.
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
from urllib.request import urlopen

SRC = Path(__file__).resolve().parents[2] / "05_V2.0.0_Source"
sys.path.insert(0, str(SRC))
from backend import r8_20_seo_geo_growth_patch as bridge  # noqa: E402


def read_json(url, timeout=3):
    with urlopen(url, timeout=timeout) as response:
        assert response.status == 200, (url, response.status)
        return json.load(response)


def main():
    existing_fn = bridge._geo_fast_ui_compact
    old_threshold = bridge._HTTP_DIAG_SLOW_SECONDS
    bridge._HTTP_DIAG_SLOW_SECONDS = 0.08
    blocked = threading.Event()
    release = threading.Event()
    entered = [0]
    entered_lock = threading.Lock()

    def artificial_slow():
        with entered_lock:
            entered[0] += 1
            if entered[0] >= 5:
                blocked.set()
        assert release.wait(3), "test release event not set"
        return {"status_ready": True, "formal_ab_completed": 2, "formal_ab_target": 50}

    bridge._geo_fast_ui_compact = artificial_slow
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        partial(bridge.server.DashboardHandler, directory=str(bridge.server.get_web_path())),
    )
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            pending = [
                pool.submit(read_json, base + "/api/r8-24/geo-growth/fast-ui", 5)
                for _ in range(5)
            ]
            assert blocked.wait(2), "five test slow handlers never started"
            time.sleep(0.12)
            started = time.perf_counter()
            health = read_json(base + "/api/r8-24/geo-growth/http-health")
            elapsed = (time.perf_counter()-started)*1000
            assert elapsed < 600, f"health GET blocked {elapsed:.0f}ms by five slow requests"
            assert health["inflight_requests"] >= 5, health
            assert sum(x["kind"].endswith("/fast-ui") for x in health["active_slow_requests"]) >= 5, health
            assert all("?" not in x["kind"] for x in health["active_slow_requests"]), health
            with urlopen(base + "/kz_site_tools.js", timeout=3) as resp:
                script=resp.read()
                assert resp.status == 200 and b"KazuizhiSiteTools" in script
            with urlopen(base + "/api/r8-24/geo-growth/liveness", timeout=3) as resp:
                assert json.load(resp)["server_ready"] is True
            release.set()
            for task in pending:
                assert task.result(timeout=5)["formal_ab_completed"] == 2
        health = read_json(base + "/api/r8-24/geo-growth/http-health")
        assert sum(x["kind"].endswith("/fast-ui") for x in health["recent_slow_requests"]) >= 5, health
        print("PASS: 5 blocked GEO API requests do not block local HTTP health, tiny JS or liveness")
        print("PASS: read-only HTTP diagnostics show true in-flight/slow requests with no query strings")
    finally:
        release.set()
        bridge._geo_fast_ui_compact = existing_fn
        bridge._HTTP_DIAG_SLOW_SECONDS = old_threshold
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
