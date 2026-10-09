"""Browser smoke for the *actual* SEO HTML and GEO JS in static preview mode."""
from __future__ import annotations
import functools
import threading
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait

ROOT = Path(__file__).resolve().parents[1]


class SilentHandler(SimpleHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass


def run():
    handler = functools.partial(SilentHandler, directory=str(ROOT))
    httpd = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    worker = threading.Thread(target=httpd.serve_forever, daemon=True)
    worker.start()
    opts = webdriver.ChromeOptions()
    opts.add_argument("--headless=new")
    opts.add_argument("--disable-gpu")
    opts.add_argument("--window-size=1440,980")
    opts.add_argument("--no-sandbox")
    opts.add_argument("--disable-extensions")
    opts.add_argument("--disable-dev-shm-usage")
    driver = None
    try:
        driver = webdriver.Chrome(options=opts)
        driver.set_page_load_timeout(35)
        url = f"http://127.0.0.1:{httpd.server_port}/preview/index.html"
        driver.get(url)
        wait = WebDriverWait(driver, 28)
        wait.until(lambda d: d.find_elements(By.CSS_SELECTOR, "#seo-frame:not([hidden])"))
        wait.until(lambda d: d.execute_script("""
          const doc=document.querySelector('#seo-frame')?.contentDocument;
          return doc && doc.querySelectorAll('#kpis .kpi').length >= 6;
        """))
        seo_count = driver.execute_script("""
           return document.querySelector('#seo-frame')
             .contentDocument.querySelectorAll('#kpis .kpi').length;
        """)
        assert seo_count >= 6, f"SEO KPIs absent: {seo_count}"
        assert driver.execute_script("""
          return !!document.querySelector('#seo-frame')
            .contentDocument.body.textContent.includes('演示样例数据');
        """), "SEO preview is not clearly labelled as mock data"
        print("PASS: real SEO HTML renders with mock-data badge and KPIs")

        driver.find_element(By.CSS_SELECTOR, '.tabs [data-preview-route="geo"]').click()
        wait.until(lambda d: d.find_elements(By.ID, "geo-growth-os"))
        wait.until(lambda d: d.execute_script("""
          const badge=document.getElementById('geo-os-state');
          return badge && badge.textContent.includes('自动运营中');
        """))
        assert driver.find_elements(By.CSS_SELECTOR, "#geo-os-kpis .geo-os-kpi")
        print("PASS: real GEO script renders current-state mock and 7 KPI cards")

        driver.find_element(By.CSS_SELECTOR, "#geo-growth-advanced > summary").click()
        wait.until(lambda d: d.execute_script("""
          return document.querySelectorAll('#geo-adv-questions tr').length===50;
        """))
        wait.until(lambda d: d.execute_script("""
          return document.documentElement.dataset.kzGeoAdvancedSections === '4';
        """))
        print("PASS: real GEO advanced Evidence UI renders fixed 50 baseline and mock 4/4")

        driver.find_element(By.ID, "geo-os-pause").click()
        wait.until(lambda d: d.execute_script("""
          const s=document.getElementById('geo-os-state');
          return s && s.textContent.includes('已暂停');
        """))
        driver.find_element(By.ID, "geo-os-resume").click()
        wait.until(lambda d: d.execute_script("""
          const s=document.getElementById('geo-os-state');
          return s && s.textContent.includes('自动运营中');
        """))
        print("PASS: preview controls respond locally without live POSTs")
        path = ROOT / "preview" / "browser-preview.png"
        driver.save_screenshot(str(path))
        print("SCREENSHOT:", path.name)
    except Exception:
        if driver:
            print("PREVIEW DEBUG:", driver.execute_script("""
              const f=document.querySelector('#seo-frame');
              const d=f?.contentDocument;
              return {
                outer_text:document.body.innerText.slice(0,550),
                frame_url:f?.contentWindow?.location?.href,
                frame_ready:d?.readyState,
                frame_body_text:d?.body?.innerText.slice(0,850),
                frame_html: d?.body?.innerHTML.slice(-700),
                frame_scripts:[...(d?.scripts||[])].map(s=>s.src||'inline').slice(-7),
                kpi_count: d?.querySelectorAll('#kpis .kpi').length,
                service_message: d?.querySelector('#service-message')?.textContent
              }
            """), flush=True)
            driver.save_screenshot(str(ROOT / "preview" / "browser-preview.png"))
        raise
    finally:
        if driver:
            driver.quit()
        httpd.shutdown()
        httpd.server_close()


if __name__ == "__main__":
    run()
