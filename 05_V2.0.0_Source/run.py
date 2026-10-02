"""Kazuizhi AI Enterprise V2.2.2 Autonomous Mission Core entry point."""
import argparse
import ctypes
import json
import os
import sys
import tempfile
import threading
import time
import traceback
import webbrowser
from pathlib import Path
from core.version import BUILD_ID, PRODUCT_NAME
from ai_center.ai_engine import AIEngine
from backend.server import create_server
from backend import realtime_mirror_patch as _realtime_mirror_patch  # noqa: F401,E402
from backend import content_factory_patch as _content_factory_patch  # noqa: F401,E402
from backend import ai_production_center_patch as _ai_production_center_patch  # noqa: F401,E402
from promotion import content_factory_v2_extensions as _content_factory_v2_extensions  # noqa: F401,E402
from promotion import local_mission_qc_patch as _local_mission_qc_patch  # noqa: F401,E402
from promotion import video_worker_v2_extensions as _video_worker_v2_extensions  # noqa: F401,E402
from promotion import video_worker_cpu_patch as _video_worker_cpu_patch  # noqa: F401,E402
from backend import content_effects_patch as _content_effects_patch  # noqa: F401,E402
from backend import deep_productization_patch as _deep_productization_patch  # noqa: F401,E402
from backend import growth_chain_patch as _growth_chain_patch  # noqa: F401,E402
from core import decision_center_mission_patch as _decision_center_mission_patch  # noqa: F401,E402
from backend import autonomous_ops_patch as _autonomous_ops_patch  # noqa: F401,E402
from backend import ai_gateway_patch as _ai_gateway_patch  # noqa: F401,E402
from backend import r8_10_control_patch as _r8_10_control_patch  # noqa: F401,E402
from backend import r8_11_backbone_patch as _r8_11_backbone_patch  # noqa: F401,E402
from backend import r8_12_account_center_patch as _r8_12_account_center_patch  # noqa: F401,E402
from backend import r8_12_auth_broker_patch as _r8_12_auth_broker_patch  # noqa: F401,E402
from backend import r8_13_seo_geo_patch as _r8_13_seo_geo_patch  # noqa: F401,E402
from backend import r8_14_seo_geo_autonomy_patch as _r8_14_seo_geo_autonomy_patch  # noqa: F401,E402
# R8-17 must patch the deployer before R8-15/R8-16 capture function references.
from integrations import r8_17_remote_deployer_patch as _r8_17_remote_deployer_patch  # noqa: F401,E402
from backend import r8_15_seo_public_deploy_patch as _r8_15_seo_public_deploy_patch  # noqa: F401,E402
from backend import r8_16_search_submit_patch as _r8_16_search_submit_patch  # noqa: F401,E402
from backend import r8_17_remote_agent_patch as _r8_17_remote_agent_patch  # noqa: F401,E402
from backend import r8_18_evidence_ledger_patch as _r8_18_evidence_ledger_patch  # noqa: F401,E402
# GEO Phase 1-3 and R8-20 must be active in the real desktop entrypoint, not only CI imports.
from backend import r8_19_geo_validation_patch as _r8_19_geo_validation_patch  # noqa: F401,E402
from backend import r8_19_geo_phase3_patch as _r8_19_geo_phase3_patch  # noqa: F401,E402
from backend import r8_20_seo_geo_growth_patch as _r8_20_seo_geo_growth_patch  # noqa: F401,E402
from promotion import chatgpt_mission_patch as _chatgpt_mission_patch  # noqa: F401,E402
from core.autonomy import ensure_daily_review
from core.autonomous_ops import sync_from_runtime as sync_autonomous_ops
from core.mission_ledger import sync_backbone as sync_mission_backbone
from core.daily_workforce import ensure_daily_workforce
from core.command_execution import reconcile as reconcile_command_execution
from core.decision_bridge import export_decision_handoff
from core.decision_center import refresh_decision_center
from core.r7_engine import migrate_r6, recover_interrupted, run_due_jobs
from core.r8_migration import migrate_to_v2_2
from core.runtime_resilience import heartbeat as runtime_heartbeat
from core.runtime_resilience import record_restart_attempt as runtime_record_restart_attempt
from core.runtime_resilience import set_worker_enabled as runtime_set_worker_enabled
from core.runtime_resilience import start_process as runtime_start_process
from core.runtime_resilience import stop_process as runtime_stop_process
from core.seo_geo_autonomy import run_once as run_seo_geo_autonomy
from core.seo_geo_autonomy import status as seo_geo_autonomy_status
from core.seo_geo_growth import dashboard as seo_geo_dashboard
from core.seo_observability import run as run_seo_technical_audit, should_run_today as seo_technical_audit_due
from integrations.ai_gateway import run_once as run_ai_gateway
from integrations.bridge import sync_once as bridge_sync_once
from integrations.chatgpt_relay_agent import poll_seconds as relay_poll_seconds
from integrations.chatgpt_relay_agent import relay_config_status, safe_poll_once as relay_poll_once
from integrations.douyin_dry_run_executor import run_pending as run_pending_douyin_dry_runs
from integrations.remote_agent import auto_import_pairing
from integrations.r8_17_remote_deployer_patch import activate_remote_mode_if_ready
from promotion.chatgpt_handoff_watchdog import sync_chatgpt_handoffs
from promotion.chatgpt_orchestrator import sync_content_plans
from promotion.local_mission_qc_patch import recover_authorized_qc
from promotion.material_library import scan_material_inbox
from promotion.publish_orchestrator import run_publish_planning
from promotion.video_worker import run_pending as run_pending_videos

SCHEDULER_INTERVAL_SECONDS = 15
CONTENT_WORKER_INTERVAL_SECONDS = 60
VIDEO_WORKER_INTERVAL_SECONDS = 15
MAX_PROCESS_RESTARTS_10_MIN = 5


def _set_keep_awake(enabled):
    """Prevent Windows system sleep while the owner explicitly keeps the app running.

    The display may still turn off.  Clearing ES_SYSTEM_REQUIRED on shutdown
    restores the user's normal Windows power policy.
    """
    if os.name != "nt":
        return False
    try:
        es_continuous = 0x80000000
        es_system_required = 0x00000001
        flags = es_continuous | (es_system_required if enabled else 0)
        return bool(ctypes.windll.kernel32.SetThreadExecutionState(flags))
    except (AttributeError, OSError):
        return False


def _runtime_mark(name, *, ok=True, error=None, detail=None, force_persist=False):
    """Monitoring must never be able to stop the production worker it observes."""
    try:
        runtime_heartbeat(name, ok=ok, error=error, detail=detail, force_persist=force_persist)
    except Exception as monitor_error:
        print(f"Runtime health monitor deferred: {monitor_error}", flush=True)


def _sync_r8_17_remote_agent(*, check_live=True):
    """Import a local pairing file and optionally check the remote deploy route.

    The desktop must paint its first page from local state.  A public-network
    probe may take many seconds on an unreliable network, so startup only
    discovers local pairing data; the background scheduler performs the live
    route check after the owner shell is ready.
    """
    try:
        pairing = auto_import_pairing()
        if pairing.get("ok") or pairing.get("reason") == "already_configured":
            activation = activate_remote_mode_if_ready(check_live=check_live)
            if activation.get("activated"):
                return {"ok": True, "pairing": pairing, "activation": activation}
            return {"ok": False, "pairing": pairing, "activation": activation}
        return {"ok": False, "pairing": pairing, "activation": {}}
    except Exception as error:
        return {"ok": False, "reason": str(error)}


def start_scheduler():
    """Run the fast control/scheduling lane independently of slow AI/content I/O."""
    stop = threading.Event()
    runtime_set_worker_enabled("scheduler_core", True, "15s control lane")

    def loop():
        tick = 0
        while not stop.is_set():
            try:
                reconcile_command_execution()
                ensure_daily_workforce()
                ensure_daily_review()
                run_due_jobs()
                if tick % 20 == 0:
                    manager_report = refresh_decision_center()
                    export_decision_handoff(manager_report)
                    # R8-17: periodically discover a pairing file copied to this
                    # PC and keep the lightweight server execution channel live.
                    _sync_r8_17_remote_agent()
                    # Local SEO/GEO work remains autonomous. PUBLISHED requires
                    # public verification; SUBMITTED requires a search receipt.
                    run_seo_geo_autonomy(force=False)
                    audit_policy = seo_geo_autonomy_status()
                    if (
                        audit_policy.get("enabled")
                        and audit_policy.get("mode") == "autonomous"
                        and (audit_policy.get("policy") or {}).get("auto_technical_audit", True)
                        and seo_technical_audit_due()
                        and int((seo_geo_dashboard().get("summary") or {}).get("public_pages") or 0) > 0
                    ):
                        # Network delay is bounded by provider timeouts; this
                        # lane remains isolated from AI/video workers below.
                        run_seo_technical_audit(seo_geo_dashboard())
                _runtime_mark("scheduler_core", ok=True, detail=f"tick={tick}")
            except Exception as error:
                _runtime_mark("scheduler_core", ok=False, error=error, detail=f"tick={tick}", force_persist=True)
                print(f"R7/R8-20 scheduler check failed but will continue: {error}", flush=True)
            tick = (tick + 1) % 1_000_000
            stop.wait(SCHEDULER_INTERVAL_SECONDS)

    thread = threading.Thread(target=loop, name="r7-local-scheduler", daemon=True)
    thread.start()
    return stop


def start_content_execution_worker():
    """Isolate model/network/content work so a slow provider cannot freeze scheduler ticks."""
    stop = threading.Event()
    runtime_set_worker_enabled("content_execution", True, "60s AI/content/publish lane")

    def loop():
        cycle = 0
        while not stop.is_set():
            try:
                scan_material_inbox()
                sync_autonomous_ops(autostart=True)
                sync_content_plans()
                recover_authorized_qc(limit=10)
                run_ai_gateway(limit=2)  # optional enhancer only; provider calls are timeout-bounded
                sync_chatgpt_handoffs()
                bridge_sync_once()
                run_publish_planning(limit=10)
                run_pending_douyin_dry_runs(limit=1)
                sync_autonomous_ops(autostart=False)
                sync_mission_backbone()
                _runtime_mark("content_execution", ok=True, detail=f"cycle={cycle}")
            except Exception as error:
                _runtime_mark("content_execution", ok=False, error=error, detail=f"cycle={cycle}", force_persist=True)
                print(f"R7 AI/local-content/publish execution deferred; worker will continue: {error}", flush=True)
            cycle = (cycle + 1) % 1_000_000
            stop.wait(CONTENT_WORKER_INTERVAL_SECONDS)

    thread = threading.Thread(target=loop, name="r8-content-execution-worker", daemon=True)
    thread.start()
    return stop


def start_chatgpt_relay_worker():
    """Use outbound HTTPS only; never expose the local dashboard port publicly."""
    stop = threading.Event()
    config = relay_config_status()
    if not config.get("configured"):
        runtime_set_worker_enabled("chatgpt_relay", False, config.get("reason") or "not configured")
        return stop
    runtime_set_worker_enabled("chatgpt_relay", True, f"poll={relay_poll_seconds()}s")

    def loop():
        cycle = 0
        while not stop.is_set():
            try:
                result = relay_poll_once()
                if not result.get("ok") and not result.get("skipped"):
                    error = RuntimeError(result.get("reason") or "relay deferred")
                    _runtime_mark("chatgpt_relay", ok=False, error=error, detail=f"cycle={cycle}")
                    print(f"ChatGPT Relay deferred: {result.get('reason')}", flush=True)
                else:
                    _runtime_mark("chatgpt_relay", ok=True, detail=f"cycle={cycle}; processed={result.get('processed', 0)}")
            except Exception as error:
                _runtime_mark("chatgpt_relay", ok=False, error=error, detail=f"cycle={cycle}", force_persist=True)
                print(f"ChatGPT Relay worker recovered from error: {error}", flush=True)
            cycle = (cycle + 1) % 1_000_000
            stop.wait(relay_poll_seconds())

    thread = threading.Thread(target=loop, name="chatgpt-control-relay-worker", daemon=True)
    thread.start()
    return stop


def start_video_production_worker():
    """Keep GPU/video work isolated so a long render cannot block Mission ticks."""
    stop = threading.Event()
    runtime_set_worker_enabled("video_worker", True, "15s GPU/video lane")

    def loop():
        cycle = 0
        while not stop.is_set():
            try:
                run_pending_videos(limit=1)
                _runtime_mark("video_worker", ok=True, detail=f"cycle={cycle}")
            except Exception as error:
                _runtime_mark("video_worker", ok=False, error=error, detail=f"cycle={cycle}", force_persist=True)
                print(f"R8 video worker deferred; worker will continue: {error}", flush=True)
            cycle = (cycle + 1) % 1_000_000
            stop.wait(VIDEO_WORKER_INTERVAL_SECONDS)

    thread = threading.Thread(target=loop, name="r8-video-production-worker", daemon=True)
    thread.start()
    return stop


def _run_r8_15_server_bootstrap(args):
    from core.r8_15_server_bootstrap import execute

    report = execute(args.site_root, args.public_base_url)
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.result_file:
        destination = Path(args.result_file).expanduser()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(payload, encoding="utf-8")
    if sys.stdout is not None:
        print(payload, flush=True)
    raise SystemExit(int(report.get("exit_code", 1)))


def _run_r8_17_root_discovery_bootstrap(args):
    from core.r8_17_root_discovery_bootstrap import execute

    report = execute(args.site_root, args.public_base_url)
    payload = json.dumps(report, ensure_ascii=False, indent=2)
    if args.result_file:
        destination = Path(args.result_file).expanduser()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text(payload, encoding="utf-8")
    if sys.stdout is not None:
        print(payload, flush=True)
    raise SystemExit(int(report.get("exit_code", 1)))


def main():
    parser = argparse.ArgumentParser(description=PRODUCT_NAME)
    parser.add_argument("--port", type=int, default=8876)
    parser.add_argument("--no-browser", action="store_true")
    parser.add_argument("--r8-15-server-bootstrap", action="store_true")
    parser.add_argument("--r8-17-root-discovery-bootstrap", action="store_true")
    parser.add_argument("--site-root", default=r"C:\inetpub\kazuizhi")
    parser.add_argument("--public-base-url", default="https://kazuizhi.com/")
    parser.add_argument("--result-file", default="")
    args = parser.parse_args()
    if args.r8_15_server_bootstrap:
        _run_r8_15_server_bootstrap(args)
    if args.r8_17_root_discovery_bootstrap:
        _run_r8_17_root_discovery_bootstrap(args)

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

    keep_awake = _set_keep_awake(True)
    runtime_start_process(keep_awake=keep_awake)
    with server:
        migrate_r6()
        migrate_to_v2_2()
        recover_interrupted()
        # Recover only persisted local ChatGPT handoff state before first paint.
        # This is a filesystem operation, not an external probe; all network,
        # AI and SEO work remains on the workers below.
        try:
            sync_chatgpt_handoffs(force=True)
        except Exception as error:
            print(f"Initial handoff recovery deferred: {error}", flush=True)
        # Keep the HTTP shell responsive while slow model/network/render work is
        # isolated in its own fail-soft workers.
        scheduler_stop = start_scheduler()
        content_worker_stop = start_content_execution_worker()
        relay_stop = start_chatgpt_relay_worker()
        video_worker_stop = start_video_production_worker()
        AIEngine().start()
        url = f"http://127.0.0.1:{server.server_port}/?build={BUILD_ID}"
        print(PRODUCT_NAME, flush=True)
        print(f"Dashboard URL: {url}", flush=True)
        if not args.no_browser:
            webbrowser.open(url)
        try:
            _runtime_mark("http_server", ok=True, detail=f"port={server.server_port}", force_persist=True)
            server.serve_forever()
        except Exception as error:
            _runtime_mark("http_server", ok=False, error=error, detail=f"port={server.server_port}", force_persist=True)
            raise
        finally:
            scheduler_stop.set()
            content_worker_stop.set()
            relay_stop.set()
            video_worker_stop.set()
            runtime_stop_process()
            _set_keep_awake(False)


def _run_main_with_recovery():
    """Recover from an unexpected main-loop exception without infinite crash loops."""
    restart_times = []
    while True:
        try:
            main()
            return
        except KeyboardInterrupt:
            return
        except SystemExit:
            raise
        except Exception as error:
            now = time.monotonic()
            restart_times = [stamp for stamp in restart_times if now - stamp < 600]
            restart_times.append(now)
            attempt = len(restart_times)
            try:
                runtime_record_restart_attempt(attempt, error)
            except Exception:
                pass
            print(f"Kazuizhi runtime unexpected error; restart attempt {attempt}: {error}", flush=True)
            traceback.print_exc()
            if attempt > MAX_PROCESS_RESTARTS_10_MIN:
                print("Runtime restart circuit breaker opened after repeated crashes.", flush=True)
                raise
            time.sleep(min(5 * attempt, 30))


if __name__ == "__main__":
    _run_main_with_recovery()
