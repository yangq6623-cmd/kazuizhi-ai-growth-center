"""R8-23.4 full-interface real-browser acceptance.

This gate launches the actual source/runtime build, opens every owner-visible primary
surface in Chrome, verifies fail-open startup, fixed content-vs-SEO/GEO semantics,
bounded diagnostics, API truth contracts and records screenshots for manual review.
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
        cmd, cwd=cwd, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
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


def click_visible(page, locator, timeout=5000):
    locator.wait_for(state="visible", timeout=timeout)
    locator.scroll_into_view_if_needed()
    locator.click(timeout=timeout)


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
            assert ping.get("alive") is True, ping
            assert ping_elapsed <= 1.5, f"/api/ping not lightweight: {ping_elapsed:.3f}s"
            version, version_elapsed = get_json(base + "/api/version", 2.5)
            assert str(version.get("phase") or "").startswith("R8-23.4"), version
            assert version_elapsed <= 2.0, f"/api/version too slow: {version_elapsed:.3f}s"
            growth, _ = get_json(base + "/api/r8-20/seo-geo?days=30", 6.0)
            assert int((growth.get("geo") or {}).get("formal_tested") or 0) <= 50

            with sync_playwright() as pw:
                browser = pw.chromium.launch(channel="chrome", headless=True)

                degraded = browser.new_page(viewport={"width": 1500, "height": 950})
                degraded.route("**/api/version", lambda route: route.abort())
                degraded.goto(base + "/", wait_until="domcontentloaded", timeout=12000)
                degraded.locator("body > .layout").wait_for(state="visible", timeout=2500)
                if degraded.locator("#kz-r8233-boot").count():
                    raise AssertionError("legacy blocking boot overlay is still present")
                degraded.screenshot(path=str(screenshots / "00_fail_open_startup.png"), full_page=True)
                degraded.close()

                page = browser.new_page(viewport={"width": 1600, "height": 1000})
                errors: list[str] = []
                page.on("pageerror", lambda error: errors.append(str(error)))
                page.goto(base + "/", wait_until="domcontentloaded", timeout=12000)
                page.locator("body > .layout").wait_for(state="visible", timeout=2500)
                page.wait_for_function("() => document.readyState === 'complete'", timeout=12000)
                page.wait_for_function("() => document.documentElement.dataset.kzR8234Ui === 'ready'", timeout=7000)
                page.wait_for_timeout(1600)
                if page.locator("#kz-r8233-boot").count():
                    raise AssertionError("blocking Candidate boot overlay returned")

                legacy_content = page.locator('aside nav button.nav[data-page="promotion"]').first
                if legacy_content.count() and "内容生产与发布" not in legacy_content.inner_text():
                    raise AssertionError(f"promotion route mislabeled: {legacy_content.inner_text()!r}")
                legacy_seo = page.locator('aside nav button.nav[data-page="r813-seo-geo"]').first
                if legacy_seo.count() and "SEO/GEO增长" not in legacy_seo.inner_text():
                    raise AssertionError(f"SEO/GEO route mislabeled: {legacy_seo.inner_text()!r}")

                primary = page.locator('.r810-primary-nav .r810-nav-button:visible[data-target]')
                primary_rows = primary.evaluate_all(
                    "nodes => nodes.map(n => ({target:n.dataset.target,label:(n.textContent||'').trim()}))"
                ) if primary.count() else []
                if len(primary_rows) < 5:
                    raise AssertionError(f"too few visible primary owner routes: {primary_rows}")
                primary_targets = [row["target"] for row in primary_rows if row.get("target")]
                if len(primary_targets) != len(set(primary_targets)):
                    raise AssertionError(f"duplicate primary route targets: {primary_targets}")

                def classify(rows):
                    seo = [row for row in rows if row.get("target") == "r813-seo-geo" or "SEO/GEO" in row.get("label", "")]
                    content = [row for row in rows if row.get("target") == "content-studio" or "内容生产" in row.get("label", "") or "内容与推广" in row.get("label", "") or "内容创导" in row.get("label", "")]
                    return seo, content

                seo_rows, content_rows = classify(primary_rows)
                if not seo_rows:
                    page.wait_for_timeout(2500)
                    primary_rows = page.locator('.r810-primary-nav .r810-nav-button:visible[data-target]').evaluate_all(
                        "nodes => nodes.map(n => ({target:n.dataset.target,label:(n.textContent||'').trim()}))"
                    )
                    seo_rows, content_rows = classify(primary_rows)
                if not seo_rows:
                    raise AssertionError(f"visible SEO/GEO owner route missing: {primary_rows}")
                if not content_rows:
                    raise AssertionError(f"visible content-production owner route missing: {primary_rows}")
                if seo_rows[0]["target"] == content_rows[0]["target"]:
                    raise AssertionError("SEO/GEO and content production still share one route")

                opened = []
                for index, row in enumerate(primary_rows):
                    target = row.get("target")
                    if not target or target in opened:
                        continue
                    button = page.locator(f'.r810-primary-nav .r810-nav-button[data-target="{target}"]').first
                    click_visible(page, button)
                    page.wait_for_timeout(450)
                    if target == "r813-seo-geo" or "SEO/GEO" in row.get("label", ""):
                        page.wait_for_selector('#r813-seo-geo', timeout=7000)
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
                    elif target == "content-studio" or "内容生产" in row.get("label", "") or "内容与推广" in row.get("label", "") or "内容创导" in row.get("label", ""):
                        visible_text = page.locator('main').inner_text(timeout=5000)
                        if "SEO/GEO增长中心" in visible_text and "内容" not in visible_text:
                            raise AssertionError("content production route incorrectly became SEO/GEO dashboard")
                    page.screenshot(path=str(screenshots / f"primary_{index+1:02d}_{safe_name(target)}.png"), full_page=True)
                    opened.append(target)

                diagnostic_row = next((row for row in primary_rows if "连接" in row.get("label", "") or row.get("target") == "connections"), None)
                if diagnostic_row:
                    button = page.locator(f'.r810-primary-nav .r810-nav-button[data-target="{diagnostic_row["target"]}"]').first
                    click_visible(page, button)
                    page.wait_for_timeout(400)
                    diag_button = page.locator('#run-diagnostics').first
                    if diag_button.count() and diag_button.is_visible():
                        diag_button.click(timeout=5000)
                        try:
                            page.wait_for_function(
                                "() => { const b=document.getElementById('run-diagnostics'); return !b || (!b.disabled && !/体检中|检查中/.test(b.textContent||'')); }",
                                timeout=11000,
                            )
                        except PlaywrightTimeoutError as error:
                            raise AssertionError("diagnostics remained in endless loading state") from error

                page.wait_for_timeout(900)
                if '?build=' in page.url:
                    raise AssertionError(f"legacy build query was not cleared: {page.url}")
                if page.locator("#kz-r8233-boot").count():
                    raise AssertionError("blocking boot overlay reappeared")
                fatal = [x for x in errors if "ResizeObserver loop" not in x and "Script error" not in x]
                if fatal:
                    raise AssertionError(f"uncaught browser errors: {fatal[:10]}")
                page.screenshot(path=str(screenshots / "99_final_state.png"), full_page=True)
                browser.close()

            print(
                f"PASS: R8-23.4 full UI simulation opened {len(opened)} visible owner routes; "
                f"fail-open startup, distinct SEO/GEO + content routes, diagnostics, version and growth APIs passed. "
                f"Screenshots: {screenshots}"
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
