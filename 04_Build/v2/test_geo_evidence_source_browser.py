"""Pre-installer Windows Chrome E2E: real GEO page + synthetic verified cache.

No real business data, no posting, no Windows installation.
"""
from __future__ import annotations

import json
import sys
import threading
import time
from functools import partial
from http.server import ThreadingHTTPServer
from pathlib import Path
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

SRC = Path(__file__).resolve().parents[2] / "05_V2.0.0_Source"
sys.path.insert(0, str(SRC))
from backend import r8_20_seo_geo_growth_patch as bridge  # noqa: E402


def main():
    questions = bridge._geo_evidence_seed()["questions"]
    receipts = [
        {"question_id": questions[0]["question_id"], "official_truth": True,
         "evidence_level": "A", "test_method": "browser", "evidence_id": "TEST-A-01"},
        {"question_id": questions[1]["question_id"], "official_truth": True,
         "evidence_level": "B", "test_method": "manual", "evidence_id": "TEST-B-02"},
        {"question_id": questions[2]["question_id"], "official_truth": False,
         "evidence_level": "C", "test_method": "api", "evidence_id": "TEST-C-03"},
    ]
    evidence = {
        "snapshot_ready": True, "snapshot_mode": "lock_free_atomic_files",
        "available_sections": 4, "total_sections": 4,
        "formal_ab_completed": 2, "formal_ab_target": 50,
        "formal_ab_manual": 2, "formal_ab_automatic": 0,
        "questions": questions, "queue": [], "receipts": receipts,
        "queue_summary": {"queued": 0, "running": 0, "authorization_required": 0},
        "dashboard": {"official": {"tested": 2, "evidence_count": 2,
                                    "manual_tested": 2, "automatic_tested": 0}},
        "question_set": {"version": "GEO50-V2-20260930", "total": 50},
        "health": {name: {"ok": True, "error": ""} for name in
                   ("dashboard", "questions", "queue", "receipts")},
    }
    owner = {
        "status_ready": True, "status_mode": "fast_snapshot",
        "snapshot_stale": False, "snapshot_age_seconds": 1,
        "state": "running", "enabled": True, "paused": False,
        "mission": "Synthetic GEO internal browser preflight",
        "policy": {"execution_resources": ["doubao_api"]},
        "today_activity": {"scheduler_fresh": True, "last_run_at": ""},
        "summary": {"signals": 3, "total": 3, "waiting_publish": 1},
        "cloud": {"ready": False, "completed": 3, "target": 50, "state": "running"},
        "formal_ab_completed": 2, "formal_ab_target": 50,
        "opportunities": [], "pipeline": [], "technical_blockers": [],
        "publish_connector": {"ready": False},
    }
    orig = bridge._geo_evidence_cached
    orig_fast = bridge._geo_fast_cached
    bridge._geo_evidence_cached = lambda: evidence
    bridge._geo_fast_cached = lambda: owner
    with bridge._GEO_EVIDENCE_LOCK:
        old_e = dict(bridge._GEO_EVIDENCE_CACHE)
        bridge._GEO_EVIDENCE_CACHE.update(payload=evidence, updated=time.monotonic(),
                                          refreshing=False, last_read_duration=0.01,
                                          payload_bytes=12500, workers=[], error="")
    with bridge._GEO_FAST_LOCK:
        old_f = dict(bridge._GEO_FAST_CACHE)
        bridge._GEO_FAST_CACHE.update(payload=owner, updated=time.monotonic(),
                                      refreshing=False, workers=[], error="")
    server = ThreadingHTTPServer(("127.0.0.1", 0), partial(bridge.server.DashboardHandler, directory=str(bridge.server.get_web_path())))
    server.daemon_threads = True
    task = threading.Thread(target=server.serve_forever, daemon=True)
    task.start()
    options = webdriver.ChromeOptions()
    for argument in ("--headless=new", "--disable-gpu", "--no-sandbox",
                     "--disable-extensions", "--disable-dev-shm-usage",
                     "--window-size=1560,1100"):
        options.add_argument(argument)
    driver = None
    try:
        driver = webdriver.Chrome(options=options)
        driver.set_page_load_timeout(30)
        driver.get(f"http://127.0.0.1:{server.server_port}/geo.html?embed=1")
        wait = WebDriverWait(driver, 30)
        from urllib.request import urlopen
        with urlopen(f"http://127.0.0.1:{server.server_port}/geo.html?embed=1", timeout=4) as check:
            print("SOURCE GEO HTTP status:", check.status, "bytes:", len(check.read()), flush=True)
        print("SOURCE GEO browser:", json.dumps(driver.execute_script("""
          return {title:document.title, ready:document.readyState,
            body:document.body?.innerText.slice(0,450),
            scripts:[...document.scripts].map(s=>s.src||'inline').slice(-12),
            growth:!!document.getElementById('geo-growth-os'),
            advanced:!!document.getElementById('geo-growth-advanced'),
            fallback:document.getElementById('geo-direct-fallback')?.innerText.slice(0,190)};
        """),ensure_ascii=True),flush=True)
        wait.until(lambda d: d.find_elements(By.ID, "geo-growth-advanced"))
        wait.until(lambda d: d.find_elements(By.ID, "geo-os-state"))
        # Real browser / actual JS: force the heavy evidence request to fail.
        driver.execute_script("""
          window.__oldFetch = window.fetch;
          window.fetch = function(input, options){
            const url=typeof input==='string'?input:(input?.url||'');
            if(String(url).includes('/geo-growth/evidence-compact'))
              return Promise.reject(new Error('source-level simulated Evidence failure'));
            return window.__oldFetch.call(this,input,options);
          };
        """)
        advanced = driver.find_element(By.ID, "geo-growth-advanced")
        if not advanced.get_attribute("open"):
            advanced.find_element(By.TAG_NAME, "summary").click()
        driver.find_element(By.ID, "geo-adv-refresh").click()
        wait.until(lambda d: d.execute_script("""
          return document.documentElement.dataset.kzGeoEvidenceFallback==='1'
            && document.querySelectorAll('#geo-adv-questions tr').length===50;
        """))
        msg = driver.find_element(By.ID, "geo-adv-message").text
        assert "2/50" in msg and "明细" in msg, msg
        assert "2 / 50" in driver.find_element(By.ID, "geo-adv-kpis").text
        print("PASS: real Chrome GEO page shows truthful 2/50 fallback under failed full Evidence GET")
        driver.execute_script("window.fetch = window.__oldFetch")
        driver.find_element(By.ID, "geo-adv-refresh").click()
        wait.until(lambda d: d.execute_script("""
          return document.documentElement.dataset.kzGeoEvidenceFallback==='0'
            && document.documentElement.dataset.kzGeoAdvancedSections==='4';
        """))
        cards = driver.find_element(By.ID,"geo-adv-kpis").text
        assert "2 / 50" in cards, cards
        assert driver.find_element(By.ID, "geo-adv-questions").find_elements(By.TAG_NAME,"tr").__len__() == 50
        print("PASS: Evidence recovers 4/4 details, 50 canonical questions, 2 formal, 0 automatic")
    finally:
        if driver:
            driver.quit()
        server.shutdown()
        server.server_close()
        bridge._geo_evidence_cached = orig
        bridge._geo_fast_cached = orig_fast
        with bridge._GEO_EVIDENCE_LOCK:
            bridge._GEO_EVIDENCE_CACHE.clear()
            bridge._GEO_EVIDENCE_CACHE.update(old_e)
        with bridge._GEO_FAST_LOCK:
            bridge._GEO_FAST_CACHE.clear()
            bridge._GEO_FAST_CACHE.update(old_f)


if __name__ == "__main__":
    main()
