"""#775: installed-server GEO must paint genuine data with all secondary requests denied.

Real Windows Chrome + the production DashboardHandler + bounded in-memory GEO
snapshot. No paid API calls and no user records are modified in this test.
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

from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait

SRC = Path(__file__).resolve().parents[2] / "05_V2.0.0_Source"
sys.path.insert(0, str(SRC))

from backend import r8_20_seo_geo_growth_patch as geo  # noqa: E402


def fixture():
    return {
        "status_ready": True, "status_mode": "fast_ui_compact",
        "snapshot_age_seconds": 11.3, "snapshot_stale": False,
        "state": "running", "enabled": True, "paused": False,
        "mission": "SYNTHETIC_CHROME_PRECHECK",
        "policy": {"execution_resources": ["doubao_api"]},
        "summary": {"signals": 156, "total": 131, "waiting_publish": 3,
                    "optimizing": 0, "completed": 131},
        "cloud": {"completed": 50, "target": 50, "ready": True},
        "today_activity": {"last_run_at": "2026-10-09T18:57:10+08:00",
                           "scheduler_fresh": True, "new_opportunities": 0,
                           "verified_publications": 2},
        "publish_connector": {"ready": False, "reason": "unverified"},
        "pipeline": [{"id": "opportunity", "label": "机会识别",
                      "count": 131, "state": "active"}],
        "opportunities": [
            {"gap_label": "UNIQUE_775_GEO_OPPORTUNITY", "question_text": "read-only testing",
             "service": "synthetic", "opportunity_score": 96,
             "state": "waiting_retest", "priority": "S",
             "asset_stage": "SUBMITTED"}
        ],
        "technical_blockers": [],
        "formal_ab_completed": 2, "formal_ab_target": 50,
        "last_run_at": "2026-10-09T18:57:10+08:00"
    }


def _open_server():
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        partial(geo.server.DashboardHandler,
                directory=str(geo.server.get_web_path())),
    )
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, f"http://127.0.0.1:{server.server_port}"


def main():
    owner = fixture()
    original = geo._geo_fast_ui_compact
    geo._geo_fast_ui_compact = lambda: owner
    srv, base = _open_server()
    options = webdriver.ChromeOptions()
    for arg in ("--headless=new", "--disable-extensions", "--disable-gpu",
                "--no-sandbox", "--disable-dev-shm-usage",
                "--disable-background-networking", "--window-size=1420,1000"):
        options.add_argument(arg)
    driver = None
    try:
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(25)
        driver.execute_cdp_cmd("Network.enable", {})
        # Force exact symptom observed at desktop: secondary core JS AND fast-ui
        # HTTP GETs never succeed, even while GET /geo.html itself still does.
        driver.execute_cdp_cmd("Network.setBlockedURLs", {"urls": [
            "*geo-growth-os.js*", "*/api/*", "*operational-search.js*",
        ]})
        for i in range(3):
            driver.get(base + f"/geo.html?embed=1&repeat={i}")
            WebDriverWait(driver, 12).until(lambda d: d.execute_script("""
              const page=document.getElementById('geo-growth-os');
              const rows=document.getElementById('geo-os-rows');
              return document.documentElement.dataset.kzGeoPriorityBoot==='ready' &&
                !!page && !!rows &&
                rows.textContent.includes('UNIQUE_775_GEO_OPPORTUNITY') &&
                document.getElementById('geo-os-kpis').textContent.includes('131');
            """))
            assert driver.execute_script("""
              const scripts=[...document.scripts];
              return scripts.filter(el => el.id === 'kz-geo-core-embedded').length===1 &&
                !scripts.some(el => el.src.includes('geo-growth-os.js') ||
                                     el.src.includes('operational-search.js'));
            """)
            assert "2 / 50" in driver.find_element(
                "id", "geo-os-kpis").text
            print(f"PASS: restart {i+1}/3 single-response GEO full workbench, secondary HTTP blocked")

        # Inspect actual installed-handler HTML and headers.
        with urlopen(base + "/geo.html?embed=1", timeout=4) as response:
            raw = response.read().decode("utf-8")
            assert response.headers.get("X-KZ-GEO-Boot") == "single-response"
            assert response.headers.get("X-KZ-GEO-Truth") == "snapshot-ready"
            assert 'id="kz-geo-core-embedded"' in raw
            assert 'UNIQUE_775_GEO_OPPORTUNITY' in raw
            assert "<!-- KZ_GEO_PRIORITY_BOOT_PAYLOAD -->" not in raw
        print("PASS: production GET /geo.html directly includes real GEO snapshot and core")

        # No made-up success or 0/50 when the backend has no verified snapshot.
        owner.clear()
        owner.update({
            "status_ready": False, "status_mode": "pending_snapshot",
            "snapshot_stale": False, "state": "unknown",
            "summary": {}, "opportunities": [], "technical_blockers": [],
            "mission": "Waiting for genuine snapshot",
            "cloud": {}, "formal_ab_completed": None, "formal_ab_target": 50,
        })
        driver.get(base + "/geo.html?embed=1&pending=1")
        WebDriverWait(driver, 10).until(lambda d: d.execute_script("""
          return document.documentElement.dataset.kzGeoPriorityBoot==='pending' &&
            !!document.getElementById('geo-growth-os');
        """))
        assert "待同步 / 50" in driver.find_element("id", "geo-os-kpis").text
        assert "真实机会明细尚未读取" in driver.find_element("id", "geo-os-rows").text
        print("PASS: pending status stays pending; no fabricated success count")

        # Hostile mission text must never break out of <script type=json>.
        owner.clear()
        owner.update(fixture())
        owner["mission"] = "</script><script>window.__KZ_GEO_HTML_BREAKOUT__=true</script>"
        driver.get(base + "/geo.html?embed=1&xss=1")
        WebDriverWait(driver, 10).until(lambda d: d.execute_script("""
          return document.documentElement.dataset.kzGeoPriorityBoot==='ready';
        """))
        assert not driver.execute_script("return !!window.__KZ_GEO_HTML_BREAKOUT__")
        assert "</script><script>" not in driver.page_source
        print("PASS: inlined dynamic mission content cannot execute HTML/script injection")

        # Legacy advanced mode must retain its own controller, without adding
        # the canonical main GEO core a second time.
        with urlopen(base + "/geo.html?embed=1&advanced=1", timeout=5) as response:
            advanced_html = response.read().decode("utf-8")
            assert response.headers.get("X-KZ-GEO-Boot") is None
            assert 'id="kz-geo-core-embedded"' not in advanced_html
        print("PASS: legacy advanced Evidence UI remains isolated")

    finally:
        if driver:
            driver.quit()
        geo._geo_fast_ui_compact = original
        srv.shutdown()
        srv.server_close()


if __name__ == "__main__":
    main()
