"""Kazuizhi AI Enterprise V2.2.0 R8 Operational entry point."""
import argparse
import ctypes
import os
import tempfile
import threading
import traceback
import webbrowser
from pathlib import Path
from core.version import BUILD_ID, PRODUCT_NAME
from ai_center.ai_engine import AIEngine
from backend.server import create_server
from backend import realtime_mirror_patch as _realtime_mirror_patch  # noqa: F401,E402
from backend import content_factory_patch as _content_factory_patch  # noqa: F401,E402
from core.autonomy import ensure_daily_review
from core.daily_workforce import ensure_daily_workforce
from core.decision_bridge import export_decision_handoff
from core.decision_center import refresh_decision_center
from core.r7_engine import migrate_r6, recover_interrupted, run_due_jobs
from core.r8_migration import migrate_to_v2_2
from integrations.bridge import sync_once as bridge_sync_once
from promotion.chatgpt_orchestrator import sync_content_plans
from promotion.video_worker import run_pending as run_pending_videos


def start_scheduler():
    stop = threading.Event()
    def loop():
        tick = 0
        while not stop.is_set():
            try:
                # Keep all eight AI roles on a purposeful time-based workday.
                # Missed slots execute when the app next starts; future slots stay queued.
                ensure_daily_workforce()
                ensure_daily_review()
                run_due_jobs()
                # R7 acts as manager. Every five minutes it exports the latest
                # decision context plus pending content requests to ChatGPT.
                if tick % 20 == 0:
                    manager_report = refresh_decision_center()
                    export_decision_handoff(manager_report)
            except (OSError, ValueError) as error:
                print(f"R7 scheduler check failed: {error}", flush=True)
            if tick % 4 == 0:
                try:
                    # Content-production contracts are consumed first so the
                    # generic R7 bridge never rejects this dedicated command kind.
                    sync_content_plans()
                    bridge_sync_once()
                except (OSError, ValueError) as error:
                    # Bridge failures never stop autonomous local work. They are surfaced
                    # through bridge status/diagnostics and retried on the next cycle.
                    print(f"R7 bridge sync deferred: {error}", flush=True)
            tick += 1
            stop.wait(15)
    thread = threading.Thread(target=loop, name="r7-local-scheduler", daemon=True)
    thread.start()
    return stop


def start_video_production_worker():
    """Keep GPU/video work isolated so a long render cannot block R7/bridge ticks."""
    stop = threading.Event()
    def loop():
        while not stop.is_set():
            try:
                run_pending_videos(limit=1)
            except (OSError, ValueError, RuntimeError) as error:
                print(f"R8 video worker deferred: {error}", flush=True)
            stop.wait(15)
    thread = threading.Thread(target=loop, name="r8-video-production-worker", daemon=True)
    thread.start()
    return stop


def main():
    parser = argparse.ArgumentParser(description=PRODUCT_NAME)
    parser.add_argument("--port", type=int, default=8876)
    parser.add_argument("--no-browser", action="store_true")
    args = parser.parse_args()
    try:
        server = create_server(args.port)
    except OSError:
        console_message = (
            f"Port {args.port} is occupied by another Kazuizhi runtime. "
            "Close the old Enterprise runtime and start V2.2.0 R8 Operational again."
        )
        message = (
            f"端口 {args.port} 正被旧版卡嘴子程序占用。\n\n"
            "请关闭旧版 Enterprise R2/R3/R4/R5/R6 程序，再重新启动 V2.2.0 R8 Operational。"
        )
        print(console_message, flush=True)
        if not args.no_browser and os.name == "nt":
            ctypes.windll.user32.MessageBoxW(0, message, "Kazuizhi AI V2.2 R8 Operational", 0x30)
        raise SystemExit(2)
    with server:
        migrate_r6()
        migrate_to_v2_2()
        recover_interrupted()
        scheduler_stop = start_scheduler()
        video_worker_stop = start_video_production_worker()
        AIEngine().start()
        url = f"http://127.0.0.1:{server.server_port}/?build={BUILD_ID}"
        print(PRODUCT_NAME, flush=True)
        print(f"Dashboard URL: {url}", flush=True)
        if not args.no_browser:
            webbrowser.open(url)
        try:
            server.serve_forever()
        finally:
            scheduler_stop.set()
            video_worker_stop.set()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except Exception:
        error = traceback.format_exc()
        print(error, flush=True)
        logs = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "Kazuizhi_AI_Enterprise_V2.0.0_Beta" / "logs"
        logs.mkdir(parents=True, exist_ok=True)
        (logs / "startup-error.log").write_text(error, encoding="utf-8")
        raise