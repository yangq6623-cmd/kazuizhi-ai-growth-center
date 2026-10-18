"""#811 real HTTP thread regression with synthetic ledgers only.

Windows CI: python 04_Build/v2/test_geo_811_http_concurrency.py
No production data, browser submissions, task claims, or external HTTP calls.
"""
from __future__ import annotations

import json
import sys
import tempfile
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from http.server import ThreadingHTTPServer
from pathlib import Path
from urllib.request import urlopen
from unittest.mock import patch

SOURCE = Path(__file__).resolve().parents[2] / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))
from backend import r8_20_seo_geo_growth_patch as bridge  # noqa: E402
from core import storage  # noqa: E402


def run():
    with tempfile.TemporaryDirectory(prefix="kz811-api-") as directory:
        root = Path(directory)
        entered, release = threading.Event(), threading.Event()

        def slow_evidence_reader():
            entered.set()
            release.wait(20)
            raise TimeoutError("synthetic stalled Evidence snapshot")

        with patch.object(storage, "data_root", return_value=root), \
                patch.object(bridge, "data_root", return_value=root), \
                patch.object(bridge, "_geo_evidence_snapshot", side_effect=slow_evidence_reader):
            with bridge._GEO_EVIDENCE_LOCK:
                bridge._GEO_EVIDENCE_CACHE.update({
                    "payload": None, "updated": 0.0, "started": 0.0,
                    "refreshing": False, "error": "", "attempt": 0, "workers": [],
                    "last_read_duration": None, "payload_bytes": 0,
                })
            http = ThreadingHTTPServer(("127.0.0.1", 0), bridge.server.DashboardHandler)
            http.daemon_threads = True
            served = threading.Thread(target=http.serve_forever, daemon=True)
            served.start()
            base = f"http://127.0.0.1:{http.server_address[1]}"
            routes = ["/api/r8-25/phase1-acceptance",
                      "/api/r8-24/geo-growth/evidence-compact"]
            try:
                def request_one(route):
                    started = time.monotonic()
                    with urlopen(base + route, timeout=3.5) as response:
                        assert response.status == 200
                        payload = json.load(response)
                    duration = time.monotonic() - started
                    assert duration < 3.5, (route, duration)
                    if route.endswith("/phase1-acceptance"):
                        assert "acceptance" in payload and "supervisor" in payload
                    else:
                        assert "snapshot_ready" in payload and "questions" in payload
                        if payload["snapshot_ready"] is False:
                            assert payload["formal_ab_completed"] is None
                    return duration

                # If these two supposedly lock-free owner routes queue behind
                # a writer, the test exhausts its per-request budget and fails.
                with storage._JSON_IO_LOCK:
                    with ThreadPoolExecutor(max_workers=8) as executor:
                        futures = [executor.submit(request_one, routes[i % 2])
                                   for i in range(200)]
                        durations = [future.result() for future in as_completed(futures)]
                assert entered.wait(3), "Evidence snapshot worker did not start"
                assert len(durations) == 200
                print("PASS #811: 200 threaded HTTP requests while JSON writer and Evidence reader are blocked")
                print("max={:.3f}s, mean={:.3f}s".format(max(durations),
                      sum(durations) / len(durations)))
            finally:
                release.set()
                http.shutdown()
                http.server_close()


if __name__ == "__main__":
    run()
