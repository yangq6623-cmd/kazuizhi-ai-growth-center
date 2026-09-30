"""Real-browser smoke gate for the R8-19 owner shell.

This test exists because static/source tests and a process launch gate can all pass
while Chromium's renderer is trapped in a DOM/mutation loop.  It starts either
the source runtime or a packaged EXE, opens the real owner page in Chrome via
Playwright, waits for the R8 coordinator, verifies the 250 ms heartbeat keeps
advancing, clicks the main owner navigation, and rejects runaway DOM growth or
uncaught page errors.
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
        except Exception as error:  # noqa: BLE001 - report final startup cause
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
                # windows-latest already provides Google Chrome. Using the real
                # installed channel avoids a separate browser download and is
                # closer to the user's field environment.
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
                    raise AssertionError(f"owner shell did not reach ready/degraded state; phase={phase}") from error

                heartbeat(page)
                baseline_nodes = page.locator("*").count()
                if baseline_nodes > 12000:
                    raise AssertionError(f"unexpectedly large initial DOM: {baseline_nodes} nodes")

                # Exercise every visible primary owner navigation button. This
                # catches click handlers, iframe setup and route patches that a
                # plain HTTP or process-launch test cannot validate.
                nav = page.locator(".r810-primary-nav .r810-nav-button:visible")
                labels = [value.strip() for value in nav.all_text_contents()]
                if len(labels) < 5:
                    raise AssertionError(f"owner navigation did not initialize; visible labels={labels}")

                for label in labels[:10]:
                    target = page.locator(".r810-primary-nav .r810-nav-button:visible", has_text=label).first
                    target.click(timeout=4000)
                    page.wait_for_timeout(250)
                    heartbeat(page, min_delta=1, timeout_ms=2500)

                # Return to the boss dashboard and leave the app running long
                # enough to catch delayed observer/timer feedback loops.
                boss = page.locator(".r810-primary-nav .r810-nav-button:visible", has_text="老板总控").first
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

                fatal_errors = [
                    item for item in page_errors
                    if "ResizeObserver loop" not in item and "Script error" not in item
                ]
                if fatal_errors:
                    raise AssertionError(f"uncaught browser page errors: {fatal_errors[:8]}")

                phase = page.evaluate("() => document.documentElement.dataset.kzStartupPhase")
                failures = page.evaluate("() => Number(document.documentElement.dataset.kzStartupFailures || 0)")
                if phase == "degraded" or failures:
                    raise AssertionError(f"owner shell started degraded: phase={phase}, failed_modules={failures}")

                browser.close()
                target = "packaged runtime" if args.exe else "source runtime"
                print(
                    f"PASS: {target} stayed responsive in real Chrome; {len(labels)} owner routes clicked; "
                    f"DOM {baseline_nodes}->{final_nodes}; no startup degradation or uncaught page errors"
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
