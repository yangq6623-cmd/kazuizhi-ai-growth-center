"""R8-23.4 full-interface real-browser acceptance.

Field screenshots exposed regressions that route-smoke tests missed: a hard boot gate,
wrong SEO/GEO navigation, cross-page stale copy and never-ending loading indicators.
This gate opens the real owner shell in Chrome, simulates every visible navigation
surface, verifies route meaning, API contracts and fail-open startup, and saves one
screenshot per route for CI review.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request
from pathlib import Path

from playwright.sync_api import TimeoutError as PlaywrightTimeoutError
from playwright.sync_api import sync_playwright

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
RUN_PY = SOURCE / "run.py"


def free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def launch_runtime(exe: str | None, port: int, data_root: str) -> subprocess.Popen:
    env = os.environ.copy()
    env["LOCALAPPDATA"] = data_root
    if exe:
        cmd = [str(Path(exe).resolve()), "--no-browser", "--port", str(port)]
        cwd = str(Path(exe).resolve().parent)
    else:
        cmd = [sys.executable, str(RUN_PY), "--no-browser", "--port", str(port)]
        cwd = str(SOURCE)
    return subprocess.Popen(
        cmd,
        cwd=cwd,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def wait_http(url: str, timeout: float = 30.0) -> None:
    deadline = time.time() + timeout
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=1.5) as response:
                if response.status < 500:
                    return
        except Exception as error:
            last_error = error
        time.sleep(0.2)
    raise AssertionError(f"runtime did not become reachable: {url}: {last_error}")


def get_json(url: str, timeout: float = 3.0) -> tuple[dict, float]:
    started = time.perf_counter()
    with urllib.request.urlopen(url, timeout=timeout) as response:
        body = json.loads(response.read().decode("utf-8"))
        status = response.status
    elapsed = time.perf_counter() - started
    if status != 200:
        raise AssertionError(f"expected HTTP 200: {url}; got {status}")
    return body, elapsed


def safe_name(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9._-]+", "-", value).strip("-")
    return value[:80] or "page"


def assert_not_stuck(page, label: str) -> None:
    # Do not reject legitimate empty states; reject controls that are still actively loading.
    stuck = page.evaluate(
        """() => [...document.querySelectorAll('button:visible')]
        .filter(el => !el.hidden && /体检中|加载中|正在检查/.test((el.textContent||'').trim()))
        .map(el => (el.textContent||'').trim())""".replace("button:visible", "button")
    )
    if stuck:
        raise AssertionError(f"{label} retained active loading controls: {stuck[:8]}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", default="")
    parser.add_argument("--screens", default=os.environ.get("KZ_UI_SCREENSHOT_DIR", ""))
    args = parser.parse_args()

    port = free_port()
    screenshots = Path(args.screens) if args.screens else Path(tempfile.mkdtemp(prefix="kz-r8234-ui-shots-"))
    screenshots.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(prefix="kz-r8234-runtime-") as data_root:
        process = launch_runtime(args.exe or None, port, data_root)
        base = f"http://127.0.0.1:{port}"
        try:
            wait_http(base + "/api/ping")

            ping, ping_elapsed = get_json(base + "/api/ping", 2.0)
            if not ping.get("alive") or ping_elapsed > 1.5:
                raise AssertionError(f"/api/ping not lightweight: {ping_elapsed:.3f}s {ping}")
            version, version_elapsed = get_json(base + "/api/version", 2.5)
            if not str(version.get("phase") or "").startswith("R8-23.4"):
                raise AssertionError(f"unexpected version phase: {version}")
            if version_elapsed > 2.0:
                raise AssertionError(f"/api/version too slow: {version_elapsed:.3f}s")
            growth, _ = get_json(base + "/api/r8-20/seo-geo?days=30", 6.0)
            if int((growth.get("geo") or {}).get("formal_tested") or 0) > 50:
                raise AssertionError("formal GEO truth exceeded immutable 50-question set")

            with sync_playwright() as pw:
                browser = pw.chromium.launch(channel="chrome", headless=True)

                # Fail-open startup: even a failed /api/version must not lock the UI.
                degraded = browser.new_page(viewport={"width": 1500, "height": 950})
                degraded.route("**/api/version", lambda route: route.abort())
                degraded.goto(base + "/", wait_until="domcontentloaded", timeout=12000)
                degraded.locator("body > .layout").wait_for(state="visible", timeout=2500)
                if degraded.locator("#kz-r8233-boot").count():
                    raise AssertionError("legacy R8-23.3 blocking boot overlay is still present")
                degraded.screenshot(path=str(screenshots / "00_fail_open_startup.png"), full_page=True)
                degraded.close()

                page = browser.new_page(viewport={"width": 1600, "height": 1000})
                errors: list[str] = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(base + "/", wait_until="domcontentloaded", timeout=12000)
                page.locator("body > .layout").wait_for(state="visible", timeout=2500)
                try:
                    page.wait_for_function("() => document.readyState === 'complete'", timeout=12000)
                except PlaywrightTimeoutError as error:
                    state = page.evaluate("() => document.readyState")
                    raise AssertionError(f"root document never completed; Chrome tab would keep loading: {state}") from error

                page.wait_for_function("() => document.documentElement.dataset.kzR8234Ui === 'ready'", timeout=6000)
                page.wait_for_timeout(1200)
                if page.locator("#kz-r8233-boot").count():
                    raise AssertionError("blocking Candidate boot overlay returned on normal startup")

                # Route contract must remain semantic, not text-based DOM guessing.
                content = page.locator('aside nav button.nav[data-page="promotion"]').first
                content.wait_for(state="visible", timeout=5000)
                if "内容生产与发布" not in content.inner_text():
                    raise AssertionError(f"promotion route mislabeled: {content.inner_text()!r}")
                seo = page.locator('aside nav button.nav[data-page="r813-seo-geo"]').first
                seo.wait_for(state="visible", timeout=5000)
                if "SEO/GEO增长" not in seo.inner_text():
                    raise AssertionError(f"SEO/GEO route mislabeled: {seo.inner_text()!r}")

                duplicates = page.evaluate(
                    """() => {
                      const routes=[...document.querySelectorAll('aside nav button.nav[data-page]')].map(x=>x.dataset.page);
                      return routes.filter((x,i)=>routes.indexOf(x)!==i);
                    }"""
                )
                if duplicates:
                    raise AssertionError(f"duplicate sidebar routes: {duplicates}")

                # Open every visible legacy sidebar route and record a screenshot.
                routes = page.locator('aside nav button.nav:visible[data-page]').evaluate_all(
                    "nodes => nodes.map(n => ({route:n.dataset.page,label:(n.textContent||'').trim()}))"
                )
                if len(routes) < 8:
                    raise AssertionError(f"too few visible owner routes: {routes}")

                seen = set()
                for index, item in enumerate(routes):
                    route = item["route"]
                    if route in seen:
                        continue
                    seen.add(route)
                    button = page.locator(f'aside nav button.nav[data-page="{route}"]').first
                    button.scroll_into_view_if_needed()
                    button.click(timeout=5000)
                    page.wait_for_timeout(450)
                    if route == "r813-seo-geo":
                        page.wait_for_selector('#r813-seo-geo.page.active, #r813-seo-geo', timeout=7000)
                        page.locator('[data-r813-workspace="seo"]').first.wait_for(state="visible", timeout=7000)
                        seo_frame = page.locator('#r813-seo-frame').first
                        seo_frame.wait_for(state="visible", timeout=7000)
                        handle = seo_frame.element_handle()
                        frame = handle.content_frame() if handle else None
                        if frame is None:
                            raise AssertionError("SEO iframe unavailable")
                        frame.wait_for_selector('.head h1', timeout=10000)
                        heading = frame.locator('.head h1').first.inner_text()
                        if "SEO/GEO增长中心" not in heading:
                            raise AssertionError(f"wrong SEO/GEO workspace heading: {heading!r}")
                        if page.get_by_text("从一个关键词，完成四类内容准备", exact=False).count():
                            raise AssertionError("SEO/GEO route opened content production workbench")
                    elif route == "promotion":
                        active_text = page.locator('.page.active').inner_text(timeout=5000)
                        if "SEO/GEO增长中心" in active_text and "内容" not in active_text:
                            raise AssertionError("content production route incorrectly became SEO/GEO dashboard")
                    shot = screenshots / f"{index+1:02d}_{safe_name(route)}.png"
                    page.screenshot(path=str(shot), full_page=True)

                # New primary navigation is also an owner surface; click every visible target.
                primary = page.locator('.r810-primary-nav .r810-nav-button:visible[data-target]')
                primary_targets = primary.evaluate_all("nodes => nodes.map(n => n.dataset.target).filter(Boolean)") if primary.count() else []
                for target in dict.fromkeys(primary_targets):
                    button = page.locator(f'.r810-primary-nav .r810-nav-button[data-target="{target}"]').first
                    button.click(timeout=5000)
                    page.wait_for_timeout(350)
                    page.screenshot(path=str(screenshots / f"primary_{safe_name(target)}.png"), full_page=True)

                # Diagnostics must settle or explicitly time out; never spin forever.
                diag = page.locator('aside nav button.nav[data-page="connections"]').first
                if diag.count():
                    diag.click(timeout=5000)
                    page.wait_for_timeout(350)
                    button = page.locator('#run-diagnostics').first
                    if button.count() and button.is_visible():
                        button.click(timeout=5000)
                        try:
                            page.wait_for_function(
                                "() => { const b=document.getElementById('run-diagnostics'); return !b || (!b.disabled && !/体检中|检查中/.test(b.textContent||'')); }",
                                timeout=11000,
                            )
                        except PlaywrightTimeoutError as error:
                            raise AssertionError("diagnostics remained in endless loading state") from error

                page.wait_for_timeout(900)
                if page.locator('#kz-r8233-boot').count():
                    raise AssertionError("blocking boot overlay reappeared")
                if '?build=' in page.url:
                    raise AssertionError(f"legacy build query was not cleared: {page.url}")

                fatal = [x for x in errors if "ResizeObserver loop" not in x and "Script error" not in x]
                if fatal:
                    raise AssertionError(f"uncaught browser errors: {fatal[:10]}")

                page.screenshot(path=str(screenshots / "99_final_state.png"), full_page=True)
                browser.close()

            print(
                f"PASS: R8-23.4 full UI simulation opened {len(seen)} sidebar routes and "
                f"{len(set(primary_targets))} primary routes; fail-open startup, SEO/GEO route, "
                f"content route, diagnostics, version and growth APIs passed. Screenshots: {screenshots}"
            )
        finally:
            if process.poll() is None:
                process.terminate()
                try:
                    process.wait(timeout=6)
                except subprocess.TimeoutExpired:
                    process.kill()
                    process.wait(timeout=3)


if __name__ == "__main__":
    main()
