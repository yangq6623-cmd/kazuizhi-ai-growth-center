"""Real-browser smoke gate for the R8-19 owner shell.

Static tests can pass while Chromium is trapped in a renderer loop or while an
embedded workspace is silently clipped. This gate starts either source or
packaged runtime, opens real Chrome, verifies the owner heartbeat, clicks the
main routes, explicitly stress-tests the split SEO/GEO workspace, verifies that
both embedded pages expand to their complete document height, and rejects
runaway DOM growth or uncaught page errors.
"""

from __future__ import annotations

import argparse
import os
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
        time.sleep(0.25)
    raise AssertionError(f"runtime did not become reachable: {url}: {last_error}")


def launch_runtime(exe: str | None, port: int, data_root: str) -> subprocess.Popen:
    env = os.environ.copy()
    env["LOCALAPPDATA"] = data_root
    if exe:
        cmd = [str(Path(exe).resolve()), "--no-browser", "--port", str(port)]
        cwd = str(Path(exe).resolve().parent)
    else:
        cmd = [sys.executable, str(RUN_PY), "--no-browser", "--port", str(port)]
        cwd = str(SOURCE)
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.Popen(
        cmd,
        cwd=cwd,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        creationflags=flags,
    )


def heartbeat(page, *, min_delta: int = 2, timeout_ms: int = 3000) -> int:
    before = page.evaluate(
        "() => Number(window.__KZ_R812_STARTUP_COORDINATOR__?.heartbeat || document.documentElement.dataset.kzHeartbeat || 0)"
    )
    if before <= 0:
        raise AssertionError("owner-shell heartbeat was not installed")
    try:
        page.wait_for_function(
            "before => Number(window.__KZ_R812_STARTUP_COORDINATOR__?.heartbeat || document.documentElement.dataset.kzHeartbeat || 0) >= before + 2",
            arg=before,
            timeout=timeout_ms,
        )
    except PlaywrightTimeoutError as error:
        raise AssertionError("browser main thread stopped responding; owner heartbeat did not advance") from error
    after = page.evaluate(
        "() => Number(window.__KZ_R812_STARTUP_COORDINATOR__?.heartbeat || document.documentElement.dataset.kzHeartbeat || 0)"
    )
    if after - before < min_delta:
        raise AssertionError(f"owner heartbeat advanced too slowly: {before} -> {after}")
    return after


def wait_lazy_bundle(page, target: str) -> None:
    bundle_by_target = {
        "content-studio": "content_studio",
        "r813-seo-geo": "seo_geo",
        "operational-hub": "execution",
    }
    bundle = bundle_by_target.get(target)
    if not bundle:
        return
    try:
        page.wait_for_function(
            "bundle => (window.__KZ_R812_STARTUP_COORDINATOR__?.lazy_loaded || []).includes(bundle)",
            arg=bundle,
            timeout=8000,
        )
    except PlaywrightTimeoutError as error:
        current = page.evaluate(
            "() => ({lazy: window.__KZ_R812_STARTUP_COORDINATOR__?.lazy_loaded || [], current: document.documentElement.dataset.kzStartupCurrentModule || ''})"
        )
        raise AssertionError(f"lazy owner workspace did not finish loading: target={target}, state={current}") from error


def assert_embedded_frame_expanded(page, frame_id: str, label: str, *, timeout_ms: int = 14000) -> None:
    expression = """
    frameId => {
      const f = document.getElementById(frameId);
      const d = f?.contentDocument;
      if (!f || !d?.body || !d?.documentElement) return false;
      const candidates = [d.body.scrollHeight || 0, d.documentElement.scrollHeight || 0];
      const wrap = d.querySelector('.wrap');
      const search = d.querySelector('#search');
      const direct = d.querySelector('.geo-direct-main');
      if (wrap) candidates.push(wrap.scrollHeight || 0);
      if (search) candidates.push(search.scrollHeight || 0);
      if (direct) candidates.push(direct.scrollHeight || 0);
      const expected = Math.max(...candidates);
      const actual = f.getBoundingClientRect().height;
      return expected >= 700 && actual >= expected - 90;
    }
    """
    try:
        page.wait_for_function(expression, arg=frame_id, timeout=timeout_ms)
    except PlaywrightTimeoutError as error:
        sizes = page.evaluate(
            """
            frameId => {
              const f=document.getElementById(frameId); const d=f?.contentDocument;
              if(!f||!d) return {actual:0, expected:0, missing:true};
              const expected=Math.max(d.body?.scrollHeight||0,d.documentElement?.scrollHeight||0,d.querySelector('.wrap')?.scrollHeight||0,d.querySelector('#search')?.scrollHeight||0,d.querySelector('.geo-direct-main')?.scrollHeight||0);
              return {actual:Math.round(f.getBoundingClientRect().height),expected,recorded:Number(d.documentElement?.dataset?.kzEmbeddedHeight||0)};
            }
            """,
            frame_id,
        )
        raise AssertionError(f"{label} embedded page is clipped instead of fully expanded: {sizes}") from error


def exercise_seo_geo(page) -> None:
    seo_tab = page.locator('[data-r813-workspace="seo"]').first
    geo_tab = page.locator('[data-r813-workspace="geo"]').first
    seo_tab.wait_for(state="visible", timeout=6000)
    geo_tab.wait_for(state="visible", timeout=6000)

    seo_frame_element = page.locator('#r813-seo-frame').first
    seo_frame_element.wait_for(state="visible", timeout=6000)
    seo_handle = seo_frame_element.element_handle()
    seo_frame = seo_handle.content_frame() if seo_handle else None
    if seo_frame is None:
        raise AssertionError("SEO iframe did not expose same-origin content")
    seo_frame.wait_for_selector('.head h1', state='visible', timeout=10000)
    seo_heading = seo_frame.locator('.head h1').first.inner_text().strip()
    if 'SEO' not in seo_heading:
        raise AssertionError(f"SEO heading missing after embed decoration: {seo_heading!r}")
    # The pipeline section is the stable, bottom-most SEO business block. Gate on
    # its DOM identity rather than display copy so copy-polish cannot create a
    # false build failure while still proving that the lower half rendered.
    seo_frame.wait_for_selector('#pipeline-section', state='visible', timeout=12000)
    assert_embedded_frame_expanded(page, 'r813-seo-frame', 'SEO')

    # Field reproduction: SEO -> GEO -> SEO. Scrolling happens on the owner page,
    # because embedded frames are intentionally scroll-free.
    geo_tab.click(timeout=4000)
    page.wait_for_timeout(700)
    heartbeat(page, min_delta=1, timeout_ms=3000)

    geo_frame_element = page.locator('#r813-geo-frame').first
    geo_frame_element.wait_for(state="visible", timeout=6000)
    page.wait_for_function(
        "() => { const f=document.getElementById('r813-geo-frame'); return !!f && f.src && !f.src.endsWith('about:blank'); }",
        timeout=5000,
    )
    geo_handle = geo_frame_element.element_handle()
    geo_frame = geo_handle.content_frame() if geo_handle else None
    if geo_frame is None:
        raise AssertionError("GEO iframe did not expose same-origin content")
    geo_frame.wait_for_selector('#geo-mission', state='attached', timeout=12000)
    geo_frame.wait_for_selector('.geo-browser-workbench', state='attached', timeout=12000)
    assert_embedded_frame_expanded(page, 'r813-geo-frame', 'GEO')
    heartbeat(page, min_delta=1, timeout_ms=3000)

    seo_tab.click(timeout=4000)
    page.wait_for_timeout(1600)
    assert_embedded_frame_expanded(page, 'r813-seo-frame', 'SEO after GEO -> SEO switch')
    heartbeat(page, min_delta=1, timeout_ms=3000)
    page.evaluate("() => window.scrollTo(0, document.documentElement.scrollHeight)")
    page.wait_for_timeout(1200)
    heartbeat(page, min_delta=2, timeout_ms=3500)
    page.evaluate("() => window.scrollTo(0, 0)")

    geo_tab.click(timeout=4000)
    page.wait_for_timeout(900)
    assert_embedded_frame_expanded(page, 'r813-geo-frame', 'GEO after SEO -> GEO switch')
    heartbeat(page, min_delta=1, timeout_ms=3000)
    page.evaluate("() => window.scrollTo(0, document.documentElement.scrollHeight)")
    page.wait_for_timeout(1200)
    heartbeat(page, min_delta=2, timeout_ms=3500)
    page.evaluate("() => window.scrollTo(0, 0)")

    seo_tab.click(timeout=4000)
    page.wait_for_timeout(2200)
    assert_embedded_frame_expanded(page, 'r813-seo-frame', 'SEO final switch')
    heartbeat(page, min_delta=2, timeout_ms=3500)

    seo_nodes = seo_frame.locator('*').count()
    geo_nodes = geo_frame.locator('*').count()
    if seo_nodes > 24000 or geo_nodes > 24000:
        raise AssertionError(f"SEO/GEO iframe DOM unexpectedly large: seo={seo_nodes}, geo={geo_nodes}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--exe", default="", help="Optional packaged runtime EXE; source runtime is used when omitted")
    args = parser.parse_args()

    port = free_port()
    with tempfile.TemporaryDirectory(prefix="kazuizhi-r819-browser-") as data_root:
        process = launch_runtime(args.exe or None, port, data_root)
        try:
            url = f"http://127.0.0.1:{port}/"
            wait_http(url)
            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(channel="chrome", headless=True)
                page = browser.new_page(viewport={"width": 1600, "height": 1000})
                page_errors: list[str] = []
                page.on("pageerror", lambda error: page_errors.append(str(error)))
                page.goto(url, wait_until="domcontentloaded", timeout=15000)

                try:
                    page.wait_for_function(
                        "() => ['ready','degraded'].includes(document.documentElement.dataset.kzStartupPhase || '')",
                        timeout=15000,
                    )
                except PlaywrightTimeoutError as error:
                    phase = page.evaluate("() => document.documentElement.dataset.kzStartupPhase || 'missing'")
                    current = page.evaluate("() => document.documentElement.dataset.kzStartupCurrentModule || 'none'")
                    raise AssertionError(f"owner shell did not reach ready/degraded state; phase={phase}; current_module={current}") from error

                heartbeat(page)
                baseline_nodes = page.locator("*").count()
                if baseline_nodes > 12000:
                    raise AssertionError(f"unexpectedly large initial DOM: {baseline_nodes} nodes")

                nav = page.locator(".r810-primary-nav .r810-nav-button:visible[data-target]")
                targets = nav.evaluate_all("nodes => nodes.map(node => node.dataset.target).filter(Boolean)")
                if len(targets) < 5:
                    raise AssertionError(f"owner navigation did not initialize; visible targets={targets}")

                clicked: list[str] = []
                for route_target in targets[:10]:
                    selector = f'.r810-primary-nav .r810-nav-button[data-target="{route_target}"]'
                    target = page.locator(selector).first
                    target.wait_for(state="visible", timeout=4000)
                    target.click(timeout=4000)
                    wait_lazy_bundle(page, route_target)
                    try:
                        page.wait_for_function(
                            "sel => { const el=document.querySelector(sel); return !!el && !el.disabled && el.dataset.kzLoading !== '1'; }",
                            arg=selector,
                            timeout=5000,
                        )
                    except PlaywrightTimeoutError as error:
                        raise AssertionError(f"owner route remained stuck in loading state: {route_target}") from error
                    page.wait_for_timeout(250)
                    heartbeat(page, min_delta=1, timeout_ms=3000)
                    if route_target == "r813-seo-geo":
                        exercise_seo_geo(page)
                    clicked.append(route_target)

                boss = page.locator('.r810-primary-nav .r810-nav-button[data-target="dashboard"]').first
                if boss.count():
                    boss.click(timeout=4000)
                heartbeat(page)
                page.wait_for_timeout(5000)
                heartbeat(page)

                final_nodes = page.locator("*").count()
                growth_limit = max(1800, int(baseline_nodes * 0.75))
                if final_nodes - baseline_nodes > growth_limit:
                    raise AssertionError(
                        f"runaway DOM growth detected: {baseline_nodes} -> {final_nodes} (+{final_nodes-baseline_nodes})"
                    )

                duplicates = page.evaluate(
                    """() => {
                      const counts = new Map();
                      document.querySelectorAll('[id]').forEach(n => counts.set(n.id, (counts.get(n.id)||0)+1));
                      return [...counts.entries()].filter(([id,count]) => count > 1 && /^(r8-|r810-|r811-|r812-|r813-|kz-)/.test(id));
                    }"""
                )
                if duplicates:
                    raise AssertionError(f"generated singleton IDs duplicated after navigation: {duplicates[:10]}")

                fatal_errors = [item for item in page_errors if "ResizeObserver loop" not in item and "Script error" not in item]
                if fatal_errors:
                    raise AssertionError(f"uncaught browser page errors: {fatal_errors[:8]}")

                phase = page.evaluate("() => document.documentElement.dataset.kzStartupPhase")
                failures = page.evaluate("() => Number(document.documentElement.dataset.kzStartupFailures || 0)")
                if phase == "degraded" or failures:
                    raise AssertionError(f"owner shell started degraded: phase={phase}, failed_modules={failures}")

                browser.close()
                target_name = "packaged runtime" if args.exe else "source runtime"
                print(
                    f"PASS: {target_name} stayed responsive in real Chrome; {len(clicked)} owner routes clicked; "
                    "split SEO/GEO toggled with complete embedded heights and no heartbeat loss or runaway DOM"
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
