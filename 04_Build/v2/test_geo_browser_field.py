import argparse
import json
import sys
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--port", type=int, required=True)
    args = parser.parse_args()

    url = f"http://127.0.0.1:{args.port}/geo.html?embed=1&field-smoke=694"
    options = Options()
    options.add_argument("--headless=new")
    options.add_argument("--disable-gpu")
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-background-networking")
    options.add_argument("--disable-extensions")
    options.add_argument("--no-first-run")
    options.add_argument("--window-size=1600,1200")

    driver = webdriver.Chrome(options=options)
    try:
        driver.set_page_load_timeout(20)
        driver.get(url)
        wait = WebDriverWait(driver, 12)
        wait.until(lambda d: d.find_elements(By.ID, "search-growth-switch"))
        wait.until(lambda d: d.find_elements(By.ID, "geo-growth-pane"))
        wait.until(lambda d: d.find_elements(By.ID, "geo-growth-os"))
        wait.until(lambda d: d.find_elements(By.ID, "geo-os-state"))

        growth = driver.find_element(By.ID, "geo-growth-os")
        state = driver.find_element(By.ID, "geo-os-state").text.strip()
        fallback = driver.find_element(By.ID, "geo-direct-fallback")
        fallback_display = driver.execute_script("return getComputedStyle(arguments[0]).display", fallback)
        growth_display = driver.execute_script("return getComputedStyle(arguments[0]).display", growth)

        if growth_display == "none":
            raise AssertionError("GEO Growth OS exists but is not visible")
        if fallback_display != "none":
            raise AssertionError("GEO page is still showing fallback shell instead of the full workbench")
        if not state:
            raise AssertionError("GEO Growth OS state badge is empty")

        text = driver.find_element(By.ID, "geo-growth-pane").text
        required = ["GEO 自动增长工作台", "当前 Mission", "运营 Signal", "正式 A/B"]
        missing = [marker for marker in required if marker not in text]
        if missing:
            raise AssertionError(f"GEO workbench missing visible markers: {missing}")

        result = {
            "ok": True,
            "url": url,
            "state": state,
            "fallback_display": fallback_display,
            "growth_display": growth_display,
            "required_markers": required,
        }
        print("PASS: real Chrome mounted visible GEO Growth OS")
        print(json.dumps(result, ensure_ascii=True))

        # Real browser failure injection: block only the owner data endpoint.
        # /fast-health must recover the last truthful summary, not leave the
        # owner stuck at "syncing" with made-up zeroes.
        WebDriverWait(driver, 25).until(lambda d: d.execute_script("""
          const badge=document.getElementById('geo-os-state');
          return badge && badge.textContent &&
            !badge.textContent.includes('正在同步真实状态');
        """))
        driver.execute_script("""
          window.__geo_original_fetch = window.fetch;
          window.fetch = function(input,options) {
            const url=typeof input==='string'?input:(input?.url||'');
            if(String(url).includes('/api/r8-24/geo-growth/fast-ui'))
              return Promise.reject(new Error('simulated owner transport failure'));
            return window.__geo_original_fetch.call(window,input,options);
          };
        """)
        driver.find_element(By.ID, "geo-os-refresh").click()
        WebDriverWait(driver, 15).until(lambda d: d.execute_script("""
          const badge=document.getElementById('geo-os-state');
          const rows=document.getElementById('geo-os-rows');
          return !!(badge && badge.textContent.includes('概览已恢复') &&
            rows && rows.textContent.includes('机会明细暂不可用'));
        """))
        driver.execute_script("window.fetch = window.__geo_original_fetch;")
        driver.find_element(By.ID, "geo-os-refresh").click()
        WebDriverWait(driver, 15).until(lambda d: d.execute_script("""
          const badge=document.getElementById('geo-os-state');
          return !!(badge && !badge.textContent.includes('概览已恢复') &&
            !badge.textContent.includes('正在同步真实状态'));
        """))
        print("PASS: installed GEO browser degrades to genuine health overview and recovers")
        # Advanced browser E2E (not just existence of the section). Force a
        # compact Evidence GET rejection; verified cache data must still
        # appear in the UI with a clear "detail unknown" warning.
        driver.execute_script("""
          window.__geo_original_fetch = window.fetch;
          window.fetch = function(input,options) {
            const url=typeof input==='string'?input:(input?.url||'');
            if(String(url).includes('/api/r8-24/geo-growth/evidence-compact'))
              return Promise.reject(new Error('synthetic Evidence GET failure'));
            return window.__geo_original_fetch.call(window,input,options);
          };
        """)
        driver.find_element(By.CSS_SELECTOR, "#geo-growth-advanced > summary").click()
        WebDriverWait(driver, 12).until(lambda d: d.execute_script("""
          return document.querySelectorAll('#geo-adv-questions tr').length===50;
        """))
        WebDriverWait(driver, 15).until(lambda d: d.execute_script("""
          return document.documentElement.dataset.kzGeoEvidenceFallback==='1' &&
                 document.getElementById('geo-adv-state').textContent.includes('概览');
        """))
        assert "明细待同步" in driver.find_element(By.ID,"geo-adv-message").text
        driver.execute_script("window.fetch = window.__geo_original_fetch;")
        driver.find_element(By.ID, "geo-adv-refresh").click()
        WebDriverWait(driver, 15).until(lambda d: d.execute_script("""
          return document.documentElement.dataset.kzGeoAdvancedSections==='4'
            && document.documentElement.dataset.kzGeoEvidenceFallback==='0';
        """))
        print("PASS: installed advanced GEO Evidence failure -> truthful health overview -> 4/4 recovery")
    finally:
        driver.quit()


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"FAIL: real Chrome GEO field smoke: {exc}", file=sys.stderr)
        raise
