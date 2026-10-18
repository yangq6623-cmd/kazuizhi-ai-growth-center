"""Real Chrome gate for owner-shell request budgeting and lazy workspaces."""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def wait_http(url: str, timeout: float = 35.0) -> None:
    deadline = time.time() + timeout
    last_error = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except Exception as error:  # pragma: no cover - diagnostic only
            last_error = error
        time.sleep(0.25)
    raise AssertionError(f"isolated source runtime did not start: {last_error}")


def main() -> None:
    port = free_port()
    with tempfile.TemporaryDirectory(prefix="kazuizhi-r825-cold-") as data_root:
        env = os.environ.copy()
        env["LOCALAPPDATA"] = data_root
        flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
        process = subprocess.Popen(
            [sys.executable, str(SOURCE / "run.py"), "--no-browser", "--port", str(port)],
            cwd=str(SOURCE), env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=flags,
        )
        driver = None
        try:
            base = f"http://127.0.0.1:{port}"
            wait_http(base + "/api/status")
            options = webdriver.ChromeOptions()
            for arg in (
                "--headless=new", "--disable-gpu", "--no-sandbox", "--disable-extensions",
                "--disable-background-networking", "--disable-dev-shm-usage", "--window-size=1600,1000",
            ):
                options.add_argument(arg)
            options.set_capability("goog:loggingPrefs", {"browser": "ALL"})
            driver = webdriver.Chrome(options=options)
            driver.set_page_load_timeout(30)
            wait = WebDriverWait(driver, 35)
            driver.get(base + "/?internal_test=r825-cold-start")

            wait.until(lambda d: d.execute_script(
                "return ['ready','degraded'].includes(document.documentElement.dataset.kzStartupPhase||'')"
            ))
            wait.until(lambda d: d.execute_script("return !!window.KZFetchBudget"))
            initial_src = driver.execute_script(
                "return document.getElementById('operational-frame')?.getAttribute('src')"
            )
            assert initial_src == "about:blank", f"execution iframe loaded during first paint: {initial_src}"

            driver.find_element(By.CSS_SELECTOR, '.r810-nav-button[data-target="workflow"]').click()
            wait.until(lambda d: d.execute_script("return !!document.getElementById('decision-center')"))
            wait.until(lambda d: "正在检查模型路线" not in d.find_element(By.ID, "r7-model-route").text)
            wait.until(lambda d: "正在读取任务" not in d.find_element(By.ID, "r7-jobs").text)

            driver.find_element(By.CSS_SELECTOR, '.r810-nav-button[data-target="operational-hub"]').click()
            wait.until(lambda d: d.execute_script(
                "const f=document.getElementById('operational-frame');"
                "return !!f&&f.src.includes('/operational.html?embedded=1')&&"
                "f.contentDocument?.readyState==='complete'&&f.contentDocument.body.innerText.length>100"
            ))

            driver.find_element(By.CSS_SELECTOR, '.r810-nav-button[data-target="r813-seo-geo"]').click()
            wait.until(lambda d: d.execute_script(
                "return (window.__KZ_R812_STARTUP_COORDINATOR__?.lazy_loaded||[]).includes('seo_geo')"
            ))
            wait.until(lambda d: d.execute_script(
                "const f=document.getElementById('r813-seo-frame');return !!f&&f.src&&!f.src.endsWith('about:blank')"
            ))

            driver.find_element(By.CSS_SELECTOR, '.r810-nav-button[data-target="connections"]').click()
            wait.until(lambda d: d.execute_script(
                "return (window.__KZ_R812_STARTUP_COORDINATOR__?.lazy_loaded||[]).includes('connections')"
            ))
            wait.until(lambda d: d.execute_script(
                "return document.querySelectorAll('script[data-kz-local-direct-ui],script[data-kz-async-control-ui]').length===2"
            ))

            time.sleep(6)
            state = driver.execute_script("return ({"
                "phase:document.documentElement.dataset.kzStartupPhase||'',"
                "failures:window.__KZ_R812_STARTUP_COORDINATOR__?.failed_modules||[],"
                "budget:window.KZFetchBudget.snapshot(),"
                "heartbeat:Number(window.__KZ_R812_STARTUP_COORDINATOR__?.heartbeat||0)"
                "})")
            assert state["phase"] == "ready", state
            assert state["failures"] == [], state
            assert state["budget"]["peak_active"] <= 2, state
            assert state["heartbeat"] > 2, state

            severe = [
                row for row in driver.get_log("browser")
                if row.get("level") == "SEVERE" and "favicon" not in row.get("message", "").lower()
            ]
            assert not severe, severe[:8]
            print(
                "PASS: real Chrome cold start kept API concurrency <=2; decision, execution, "
                "SEO/GEO and connection workspaces loaded with zero failed modules"
            )
        finally:
            if driver:
                driver.quit()
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=8)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)


if __name__ == "__main__":
    main()
