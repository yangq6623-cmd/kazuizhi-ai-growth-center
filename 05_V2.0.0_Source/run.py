"""Kazuizhi AI Enterprise V2.2.2 Autonomous Mission Core entry point."""
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
# Completion extensions deliberately install after the base server/compatibility
# patches so all import-time aliases point at the final R8 content semantics.
from promotion import content_factory_v2_extensions as _content_factory_v2_extensions  # noqa: F401,E402
# Validated ChatGPT Missions use local autonomous post-render QC so routine
# production never depends on a permanently-open chat window or OpenAI API.
from promotion import local_mission_qc_patch as _local_mission_qc_patch  # noqa: F401,E402
from promotion import video_worker_v2_extensions as _video_worker_v2_extensions  # noqa: F401,E402
from promotion import video_worker_cpu_patch as _video_worker_cpu_patch  # noqa: F401,E402
from backend import content_effects_patch as _content_effects_patch  # noqa: F401,E402
# Productization truth/state patches install last so UI-facing aliases use one
# Growth ID, one owner-action source and the durable R8 conversion ledger.
from backend import deep_productization_patch as _deep_productization_patch  # noqa: F401,E402
from backend import growth_chain_patch as _growth_chain_patch  # noqa: F401,E402
# R7/R8 are two views over one Mission loop. The decision patch feeds verified
# R8 outcomes back into R7; the backend patch injects R7/Mission context into
# ChatGPT production handoffs and exposes the shared world-state API.
from core import decision_center_mission_patch as _decision_center_mission_patch  # noqa: F401,E402
from backend import autonomous_ops_patch as _autonomous_ops_patch  # noqa: F401,E402
# Direct OpenAI API remains optional/advanced. The normal ChatGPT control path
# uses the signed Connector contract and canonical Command/Receipt state.
from backend import ai_gateway_patch as _ai_gateway_patch  # noqa: F401,E402
from backend import r8_10_control_patch as _r8_10_control_patch  # noqa: F401,E402
# R8-11 joins Command -> Mission -> execution -> platform Receipt -> business
# context into one ledger and exposes a unified no-paid-token channel registry.
from backend import r8_11_backbone_patch as _r8_11_backbone_patch  # noqa: F401,E402
# Extend the fallback bridge with a narrow mission_decision contract.
from promotion import chatgpt_mission_patch as _chatgpt_mission_patch  # noqa: F401,E402
from core.autonomy import ensure_daily_review
from core.autonomous_ops import sync_from_runtime as sync_autonomous_ops
from core.mission_ledger import sync_backbone as sync_mission_backbone
from core.daily_workforce import ensure_daily_workforce
from core.decision_bridge import export_decision_handoff
from core.decision_center import refresh_decision_center
from core.r7_engine import migrate_r6, recover_interrupted, run_due_jobs
from core.r8_migration import migrate_to_v2_2
from integrations.ai_gateway import run_once as run_ai_gateway
from integrations.bridge import sync_once as bridge_sync_once
from integrations.chatgpt_relay_agent import poll_seconds as relay_poll_seconds
from integrations.chatgpt_relay_agent import relay_config_status, safe_poll_once as relay_poll_once
from promotion.chatgpt_handoff_watchdog import sync_chatgpt_handoffs
from promotion.chatgpt_orchestrator import sync_content_plans
from promotion.local_mission_qc_patch import recover_authorized_qc
from promotion.material_library import scan_material_inbox
from promotion.publish_orchestrator import run_publish_planning
from promotion.video_worker import run_pending as run_pending_videos


def start_scheduler():
    stop = threading.Event()
    def loop():
        tick = 0
        while not stop.is_set():
            try:
                ensure_daily_workforce()
                ensure_daily_review()
                run_due_jobs()
                if tick % 20 == 0:
                    manager_report = refresh_decision_center()
                    export_decision_handoff(manager_report)
            except (OSError, ValueError) as error:
                print(f"R7 scheduler check failed: {error}", flush=True)
            if tick % 4 == 0:
                try:
                    scan_material_inbox()
                    # One Mission joins R7 analysis, ChatGPT strategy and R8
                    # execution. A ready campaign may enter its first production
                    # task automatically; owner review/publish truth gates remain.
                    sync_autonomous_ops(autostart=True)
                    # Accept returned plans first. Then recover routine QC for
                    # already-authorized ChatGPT Missions locally before optional
                    # API/realtime ChatGPT paths are considered.
                    sync_content_plans()
                    recover_authorized_qc(limit=10)
                    run_ai_gateway(limit=2)
                    sync_chatgpt_handoffs()
                    bridge_sync_once()
                    # Owner-approved content is automatically routed to every
                    # matching verified target-platform account. This creates
                    # publication plans only; real platform execution still needs
                    # a verified connector/device receipt.
                    run_publish_planning(limit=10)
                    sync_autonomous_ops(autostart=False)
                    # Publish one truthful R8-11 Mission ledger + channel registry
                    # snapshot to the existing PRIVATE Control Bus. This is the
                    # reverse path that lets normal ChatGPT inspect execution
                    # progress without any paid third-party token service.
                    sync_mission_backbone()
                except (OSError, ValueError) as error:
                    print(f"R7 AI/bridge/material/publish planning deferred: {error}", flush=True)
            tick += 1
            stop.wait(15)
    thread = threading.Thread(target=loop, name="r7-local-scheduler", daemon=True)
    thread.start()
    return stop


def start_chatgpt_relay_worker():
    """Use outbound HTTPS only; never expose the local dashboard port publicly."""
    stop = threading.Event()
    config = relay_config_status()
    if not config.get("configured"):
        return stop

    def loop():
        while not stop.is_set():
            result = relay_poll_once()
            if not result.get("ok") and not result.get("skipped"):
                print(f"ChatGPT Relay deferred: {result.get('reason')}", flush=True)
            stop.wait(relay_poll_seconds())

    thread = threading.Thread(target=loop, name="chatgpt-control-relay-worker", daemon=True)
    thread.start()
    return stop


def start_video_production_worker():
    """Keep GPU/video work isolated so a long render cannot block R7/AI ticks."""
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
            "Close the old Enterprise runtime and start V2.2.2 Autonomous Mission Core again."
        )
        message = (
            f"端口 {args.port} 正被旧版卡嘴子程序占用。\n\n"
            "请关闭旧版 Enterprise 程序，再重新启动 V2.2.2 自治运营核心。"
        )
        print(console_message, flush=True)
        if not args.no_browser and os.name == "nt":
            ctypes.windll.user32.MessageBoxW(0, message, "Kazuizhi AI V2.2.2 自治运营核心", 0x30)
        raise SystemExit(2)
    with server:
        migrate_r6()
        migrate_to_v2_2()
        recover_interrupted()
        try:
            scan_material_inbox()
            sync_autonomous_ops(autostart=True)
            sync_content_plans()
            recover_authorized_qc(limit=10)
            run_ai_gateway(limit=2)
            sync_chatgpt_handoffs(force=True)
            run_publish_planning(limit=10)
            sync_autonomous_ops(autostart=False)
            sync_mission_backbone()
        except (OSError, ValueError):
            pass
        scheduler_stop = start_scheduler()
        relay_stop = start_chatgpt_relay_worker()
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
            relay_stop.set()
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
