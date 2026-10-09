"""#774 field regression: GEO standalone remains usable when core JS is unavailable.

Runs against a real local ThreadingHTTPServer + headless Windows Chrome.
Synthetic data only: no user ledgers, publication, paid model, or external AI.
"""
from __future__ import annotations

import sys
import threading
import time
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.support.ui import WebDriverWait

SRC = Path(__file__).resolve().parents[2] / "05_V2.0.0_Source"
sys.path.insert(0, str(SRC))
from backend import r8_20_seo_geo_growth_patch as geo  # noqa: E402


def main():
    owner = {
        "status_ready": True, "status_mode": "fast_ui_compact",
        "snapshot_age_seconds": 17.1, "snapshot_stale": False,
        "state": "running", "mission": "Preflight only",
        "summary": {"signals": 156, "total": 131, "waiting_publish": 3},
        "cloud": {"completed": 50, "target": 50, "ready": True},
        "today_activity": {"scheduler_fresh": True, "last_run_at": "test-only"},
        "policy": {"execution_resources": ["doubao_api"]},
        "publish_connector": {"ready": False, "reason": "no verified connector"},
        "opportunities": [
            {"gap_label": "Test genuine read-only opportunity",
             "asset_stage": "SUBMITTED", "opportunity_score": 96,
             "state": "waiting_retest", "priority": "S"}
        ],
        "pipeline": [], "technical_blockers": [],
        "formal_ab_completed": 2, "formal_ab_target": 50,
    }
    original = geo._geo_fast_ui_compact
    original_document = geo._geo_priority_document
    geo._geo_fast_ui_compact = lambda: owner
    # #775 retains the #774 honest JS-less fallback for a static/legacy HTML
    # response, while test_geo_775_single_response_chrome covers the stronger
    # bundled HTML+core+snapshot served by the real installed handler.
    def serve_static_html(handler):
        data = (SRC / "web" / "geo.html").read_bytes()
        handler.send_response(200)
        handler.send_header("Content-Type", "text/html; charset=utf-8")
        handler.send_header("Content-Length", str(len(data)))
        handler.end_headers()
        handler.wfile.write(data)

    geo._geo_priority_document = serve_static_html
    server = ThreadingHTTPServer(
        ("127.0.0.1", 0),
        partial(geo.server.DashboardHandler, directory=str(geo.server.get_web_path())),
    )
    server.daemon_threads = True
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    opts = webdriver.ChromeOptions()
    for arg in ("--headless=new", "--disable-gpu", "--no-sandbox",
                "--disable-extensions", "--disable-background-networking",
                "--disable-dev-shm-usage", "--window-size=1460,1000"):
        opts.add_argument(arg)
    driver = None
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        driver = webdriver.Chrome(options=opts)
        driver.set_page_load_timeout(25)
        driver.execute_cdp_cmd("Network.enable", {})
        # On field desktop this asset may hang/abort while fast-ui returns
        # immediately. Explicitly block it so the fallback must stand alone.
        driver.execute_cdp_cmd("Network.setBlockedURLs",
                               {"urls": ["*geo-growth-os.js*"]})
        driver.get(base + "/geo.html?embed=1&scenario=core-blocked")
        wait = WebDriverWait(driver, 18)
        wait.until(lambda d: d.execute_script("""
          const box=document.getElementById('geo-direct-standalone-health');
          return document.documentElement.dataset.kzGeoStandAloneStatus==='snapshot'
            && box && box.textContent.includes('131')
            && box.textContent.includes('156')
            && box.textContent.includes('2 / 50');
        """))
        assert driver.execute_script("return document.readyState") == "complete"
        assert driver.execute_script(
            "return document.getElementById('geo-growth-os') === null")
        assert driver.execute_script("""
          return ![...document.scripts].some(
            s=>s.src.includes('operational-search.js'));
        """)
        print("PASS: direct GEO fallback shows authentic 156 signals / 131 opportunities / 2/50 with core JS blocked")

        # Restore core. A full GEO workbench must replace the fallback without
        # the legacy operational-search.js rebuilding the same host element.
        driver.execute_cdp_cmd("Network.setBlockedURLs", {"urls": []})
        driver.get(base + "/geo.html?embed=1&scenario=core-restored")
        wait.until(lambda d: d.execute_script("""
          const core=document.getElementById('geo-growth-os');
          const rows=document.getElementById('geo-os-rows');
          return !!core && !!rows && rows.textContent.includes('Test genuine read-only opportunity');
        """))
        assert driver.execute_script("""
          return !document.getElementById('geo-direct-standalone-health');
        """)
        assert driver.execute_script("""
          return ![...document.scripts].some(
            s=>s.src.includes('operational-search.js'));
        """)
        print("PASS: direct GEO core fully mounts and receives data after core JS recovers; legacy scripts absent")

        # An independent test of an actual backend fault, not invented zeros.
        driver.execute_cdp_cmd("Network.setBlockedURLs",
                               {"urls": ["*geo-growth-os.js*", "*fast-ui*"]})
        driver.get(base + "/geo.html?embed=1&scenario=all-blocked")
        wait.until(lambda d: d.execute_script("""
          return document.documentElement.dataset.kzGeoStandAloneStatus==='degraded';
        """))
        fallback = driver.execute_script("""
          return document.getElementById('geo-direct-standalone-health').textContent;
        """)
        assert "2 / 50" not in fallback and "131" not in fallback
        assert "直接打开后台接口" in fallback
        print("PASS: simultaneous core/API failure remains readable without fabricated data")

    finally:
        if driver:
            driver.quit()
        geo._geo_fast_ui_compact = original
        geo._geo_priority_document = original_document
        server.shutdown()
        server.server_close()


if __name__ == "__main__":
    main()
