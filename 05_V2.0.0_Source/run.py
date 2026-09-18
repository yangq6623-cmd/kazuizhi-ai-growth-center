"""Kazuizhi AI Enterprise V2.0.0 Beta entry point."""
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
from core.autonomy import ensure_daily_review
from core.daily_workforce import ensure_daily_workforce
from core.decision_bridge import export_decision_handoff
from core.decision_center import refresh_decision_center
from core.r7_engine import migrate_r6, recover_interrupted, run_due_jobs
from integrations.bridge import sync_once as bridge_sync_once


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
                # R7 acts as the manager: every 5 minutes it rebuilds the employee
                # reports and, when the existing Google Drive bridge is healthy,
                # exports the latest report for the ChatGPT strategy layer.
                if tick % 20 == 0:
                    manager_report = refresh_decision_center()
                    export_decision_handoff(manager_report)
            except (OSError, ValueError) as error:
                print(f"R7 scheduler check failed: {error}", flush=True)
            if tick % 4 == 0:
                try:
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
            "Close the old Enterprise R2/R3/R4/R5/R6 runtime and start V2.0.0 Beta R7 Final again."
        )
        message = (
            f"\u7aef\u53e3 {args.port} \u6b63\u88ab\u65e7\u7248\u5361\u5634\u5b50\u7a0b\u5e8f\u5360\u7528\u3002\n\n"
            "\u8bf7\u5173\u95ed\u65e7\u7248 Enterprise R2/R3/R4/R5/R6 \u7a0b\u5e8f\uff0c\u518d\u91cd\u65b0\u542f\u52a8 V2.0.0 Beta R7 Final\u3002"
        )
        print(console_message, flush=True)
        if not args.no_browser and os.name == "nt":
            ctypes.windll.user32.MessageBoxW(0, message, "Kazuizhi AI V2 Beta R7 Final", 0x30)
        raise SystemExit(2)
    with server:
        migrate_r6()
        recover_interrupted()
        scheduler_stop = start_scheduler()
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
