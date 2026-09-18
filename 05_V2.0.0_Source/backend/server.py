import json
import re
import socket
import sys
import tempfile
from functools import partial
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import parse_qs, quote, urlsplit
from ai_center.daily_review import generate_review, latest_plan, latest_review
from analytics.business_metrics import build_analytics, import_snapshot, import_template
from analytics.operation_summary import build_summary, save_summary
from core.decision_center import decision_snapshot, refresh_decision_center
from core.storage import now_iso
from core.r7_engine import (
    agent_registry, audit_history, command as job_command, create_job,
    engine_status, list_jobs, run_due_jobs,
)
from core.r8_control import (
    control_status, register_account, remove_account, social_center_status,
    update_account_status,
)
from core.version import BUILD_ID, get_version
from memory.memory_store import get_experiments, get_memory, remember
from integrations.android_device import (
    device_audit, execute_action as device_execute_action,
    list_transfer_files as device_list_transfer_files,
    pull_file_bytes as device_pull_file_bytes,
    push_file as device_push_file,
    scan_and_sync as device_scan_and_sync, screenshot_bytes as device_screenshot_bytes,
    set_takeover as device_set_takeover,
)
from integrations.bridge import (
    bridge_status, configure_bridge, disable_bridge, export_report,
    list_bridge_commands, self_test as bridge_self_test, sync_once as bridge_sync_once,
)
from integrations.business_data import (
    business_source_status, configure_business_source, refresh_business_source,
    refresh_if_due as refresh_business_if_due, test_business_source,
)
from integrations.manager import (
    ask_ai, control_center, integration_status, model_routes, save_ai_config,
    system_diagnostics, test_ai_connection,
)
from planning.tomorrow_plan import save_manual_plan
from operations.workspace import (
    add_task, command_center, competition_history, competition_report,
    demand_insights, generate_calendar, get_calendar, list_tasks, update_task,
)
from promotion.content_center import (
    add_keyword, generate_ad, generate_geo, generate_seo, generate_video,
    history as promotion_history, list_keywords,
)
from records.history_store import append_event, list_reviews


def get_web_path():
    root = Path(sys._MEIPASS) if getattr(sys, "frozen", False) else Path(__file__).resolve().parents[1]
    return root / "web"


def validate_resources():
    web = get_web_path()
    for name in ("index.html", "WEB_VERSION.txt"):
        text = (web / name).read_text(encoding="utf-8")
        if BUILD_ID not in text or re.search(r"1[.]9[.]5|ENTERPRISE-R[23]", text):
            raise RuntimeError(f"V2 dashboard identity mismatch: {name}")
    return web


class DashboardHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def _json_error(self, code, message):
        data = json.dumps({"error": str(message)}, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _json_ok(self, payload, code=200):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def _status_payload(self):
        return dict(
            get_version(),
            status="online",
            capabilities=[
                "daily_review", "operation_summary", "problem_analysis",
                "growth_opportunities", "tomorrow_plan", "review_history",
                "ai_memory", "user_growth_analysis", "order_conversion_analysis",
                "technician_supply_analysis", "leader_promotion_analysis",
                "channel_effect_analysis", "local_keyword_library",
                "seo_content_generation", "geo_local_optimization",
                "ad_copy_generation", "short_video_script", "ai_task_management",
                "promotion_calendar", "competition_analysis",
                "customer_demand_analysis", "operations_command_center",
                "integration_status_center", "external_ai_connection_test",
                "ai_operations_assistant", "system_self_diagnostics",
                "approved_job_engine", "truthful_progress", "agent_role_registry",
                "scheduler_and_audit", "bidirectional_operations_bridge",
                "offline_autonomous_mode", "bridge_command_receipts",
                "bridge_closed_loop_self_test", "verified_readonly_business_source",
                "autonomous_decision_center", "r8_single_android_device_center",
                "r8_adb_truthful_probe", "r8_device_screenshot",
                "r8_manual_takeover", "r8_device_action_audit",
                "r8_device_file_transfer", "r8_social_media_center",
                "r8_platform_device_account_binding",
            ],
        )

    def _api_get_payload(self, path):
        """Resolve only the requested endpoint.

        This deliberately avoids the old eager route dictionary, which executed
        every R7/R8 provider for every GET. In particular an ordinary R7 page
        must never launch an ADB scan or fail because a phone is unplugged.
        """
        if path == "/api/status":
            return self._status_payload()
        if path == "/api/tasks":
            return {"status": "not_connected", "running": None, "completed": None, "failed": None}
        if path == "/api/logs":
            return {"latest": "V2 Beta dashboard service running"}
        if path == "/api/statistics":
            return {"status": "not_connected", "users": None, "orders": None, "promotion": None}
        if path == "/api/kazuizhi":
            return {"status": "not_connected", "users": None, "masters": None, "leaders": None}
        if path == "/api/daily-review/latest":
            return latest_review()
        if path == "/api/operation-summary/today":
            return build_summary()
        if path == "/api/tomorrow-plan/latest":
            return latest_plan()
        if path == "/api/history":
            return list_reviews()
        if path == "/api/memory":
            return get_memory()
        if path == "/api/experiments":
            return get_experiments()
        if path == "/api/business-analytics":
            return build_analytics()
        if path == "/api/business-metrics/template":
            return import_template()
        if path == "/api/business-source/status":
            return business_source_status(build_analytics())
        if path == "/api/promotion/keywords":
            return list_keywords()
        if path == "/api/promotion/history":
            return promotion_history()
        if path == "/api/operations/tasks":
            return list_tasks()
        if path == "/api/operations/calendar":
            return get_calendar()
        if path == "/api/insights/competition":
            return competition_history()
        if path == "/api/insights/demand":
            return demand_insights()
        if path == "/api/command-center":
            return command_center()
        if path == "/api/control-center":
            return control_center()
        if path == "/api/integrations":
            return integration_status()
        if path == "/api/system/diagnostics":
            return system_diagnostics()
        if path == "/api/bridge/status":
            return bridge_status()
        if path == "/api/bridge/commands":
            return list_bridge_commands()
        if path == "/api/r7/jobs":
            return list_jobs()
        if path == "/api/r7/agents":
            return agent_registry()
        if path == "/api/r7/engine":
            return engine_status()
        if path == "/api/r7/audit":
            return audit_history()
        if path == "/api/r7/model-routes":
            return model_routes()
        if path == "/api/r7/decision-center":
            return decision_snapshot()
        if path == "/api/r8/control":
            return control_status()
        if path == "/api/r8/device/status":
            return device_scan_and_sync()
        if path == "/api/r8/device/audit":
            return device_audit()
        if path == "/api/r8/social":
            return social_center_status()
        raise KeyError(path)

    def do_GET(self):
        parsed = urlsplit(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        if path == "/api/r8/device/screenshot":
            device_id = str((query.get("device_id") or [""])[0]).strip()
            if not device_id:
                self._json_error(400, "device_id 不能为空")
                return
            try:
                data = device_screenshot_bytes(device_id)
            except (ValueError, RuntimeError, OSError) as error:
                self._json_error(400, error)
                return
            self.send_response(200)
            self.send_header("Content-Type", "image/png")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if path == "/api/r8/device/files":
            device_id = str((query.get("device_id") or [""])[0]).strip()
            if not device_id:
                self._json_error(400, "device_id 不能为空")
                return
            try:
                self._json_ok(device_list_transfer_files(device_id))
            except (ValueError, RuntimeError, OSError) as error:
                self._json_error(400, error)
            return
        if path == "/api/r8/device/file":
            device_id = str((query.get("device_id") or [""])[0]).strip()
            name = str((query.get("name") or [""])[0]).strip()
            if not device_id or not name:
                self._json_error(400, "device_id 和 name 不能为空")
                return
            try:
                safe_name, data = device_pull_file_bytes(device_id, name)
            except (ValueError, RuntimeError, OSError) as error:
                self._json_error(400, error)
                return
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Disposition", "attachment; filename*=UTF-8''" + quote(safe_name))
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        if path.startswith("/api/"):
            if not path.startswith("/api/r8/"):
                try:
                    refresh_business_if_due()
                except Exception:
                    pass
            try:
                payload = self._api_get_payload(path)
            except KeyError:
                self.send_error(404)
                return
            except Exception as error:
                # Always return a structured response instead of dropping the
                # local HTTP connection and surfacing an opaque "Failed to fetch".
                self._json_error(500, error)
                return
            self._json_ok(payload)
            return
        super().do_GET()

    def do_POST(self):
        path = urlsplit(self.path).path
        origin = self.headers.get("Origin")
        if origin and origin not in {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}:
            self.send_error(403, "Cross-origin changes are not allowed")
            return
        if path == "/api/r8/device/file-push":
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 20 * 1024 * 1024:
                self._json_error(413 if length > 20 * 1024 * 1024 else 400, "文件必须为 1 字节到 20MB")
                return
            device_id = str(self.headers.get("X-Device-ID") or "").strip()
            filename = str(self.headers.get("X-Filename") or "").strip()
            if not device_id or not filename:
                self._json_error(400, "X-Device-ID 和 X-Filename 不能为空")
                return
            temp_path = None
            try:
                data = self.rfile.read(length)
                if len(data) != length:
                    raise ValueError("文件上传数据不完整")
                handle = tempfile.NamedTemporaryFile(prefix="kazuizhi-r8-upload-", delete=False)
                temp_path = Path(handle.name)
                try:
                    handle.write(data)
                finally:
                    handle.close()
                result = device_push_file(device_id, temp_path, filename)
                self._json_ok(result, code=201)
            except (ValueError, RuntimeError, OSError) as error:
                self._json_error(400, error)
            finally:
                if temp_path:
                    try:
                        temp_path.unlink(missing_ok=True)
                    except OSError:
                        pass
            return

        allowed_posts = (
            "/api/daily-review/generate", "/api/memory", "/api/operation-summary",
            "/api/tomorrow-plan", "/api/business-metrics/import", "/api/promotion/keywords",
            "/api/business-source/configure", "/api/business-source/test", "/api/business-source/refresh",
            "/api/promotion/seo-content", "/api/promotion/geo-plan",
            "/api/promotion/ad-copy", "/api/promotion/video-script",
            "/api/operations/tasks", "/api/operations/tasks/update",
            "/api/operations/calendar/generate", "/api/insights/competition",
            "/api/integrations/ai/configure", "/api/integrations/ai/test",
            "/api/ai/command", "/api/system/diagnostics",
            "/api/bridge/configure", "/api/bridge/disable", "/api/bridge/sync", "/api/bridge/report",
            "/api/bridge/self-test", "/api/r7/jobs", "/api/r7/jobs/command",
            "/api/r7/scheduler/tick", "/api/r7/decision-center/refresh",
            "/api/r8/device/action", "/api/r8/device/takeover",
            "/api/r8/social/account", "/api/r8/social/account/status", "/api/r8/social/account/remove",
        )
        if path not in allowed_posts:
            self.send_error(404)
            return
        length = int(self.headers.get("Content-Length", "0"))
        if length > 64 * 1024:
            self.send_error(413)
            return
        try:
            payload = json.loads(self.rfile.read(length) or b"{}")
            if path == "/api/business-metrics/import":
                result = import_snapshot(payload)
            elif path == "/api/business-source/configure":
                result = configure_business_source(payload)
            elif path == "/api/business-source/test":
                result = test_business_source()
            elif path == "/api/business-source/refresh":
                result = refresh_business_source(force=True)
            elif path == "/api/promotion/keywords":
                result = add_keyword(payload)
            elif path == "/api/promotion/seo-content":
                result = generate_seo(payload)
            elif path == "/api/promotion/geo-plan":
                result = generate_geo(payload)
            elif path == "/api/promotion/ad-copy":
                result = generate_ad(payload)
            elif path == "/api/promotion/video-script":
                result = generate_video(payload)
            elif path == "/api/operations/tasks":
                result = add_task(payload)
            elif path == "/api/operations/tasks/update":
                result = update_task(payload)
            elif path == "/api/operations/calendar/generate":
                result = generate_calendar(payload)
            elif path == "/api/insights/competition":
                result = competition_report(payload)
            elif path == "/api/integrations/ai/configure":
                result = save_ai_config(payload)
            elif path == "/api/integrations/ai/test":
                result = test_ai_connection()
            elif path == "/api/ai/command":
                result = ask_ai(payload)
            elif path == "/api/system/diagnostics":
                result = system_diagnostics()
            elif path == "/api/bridge/configure":
                result = configure_bridge(payload)
            elif path == "/api/bridge/disable":
                result = disable_bridge()
            elif path == "/api/bridge/sync":
                result = bridge_sync_once()
            elif path == "/api/bridge/report":
                result = export_report()
            elif path == "/api/bridge/self-test":
                result = bridge_self_test()
            elif path == "/api/r7/jobs":
                result = create_job(payload)
            elif path == "/api/r7/jobs/command":
                result = job_command(payload)
            elif path == "/api/r7/scheduler/tick":
                result = run_due_jobs()
            elif path == "/api/r7/decision-center/refresh":
                result = refresh_decision_center()
            elif path == "/api/r8/device/action":
                result = device_execute_action(payload)
            elif path == "/api/r8/device/takeover":
                result = device_set_takeover(payload)
            elif path == "/api/r8/social/account":
                register_account(payload)
                result = social_center_status()
            elif path == "/api/r8/social/account/status":
                update_account_status(payload)
                result = social_center_status()
            elif path == "/api/r8/social/account/remove":
                remove_account(payload)
                result = social_center_status()
            elif path == "/api/daily-review/generate":
                snapshot = payload.get("snapshot")
                if snapshot is not None and not isinstance(snapshot, dict):
                    raise ValueError("snapshot must be an object")
                result = generate_review(snapshot)
            elif path == "/api/memory":
                statement = str(payload.get("statement", "")).strip()
                if not statement or len(statement) > 500:
                    raise ValueError("statement must contain 1-500 characters")
                result = remember(
                    str(payload.get("category", "老板确认"))[:50],
                    statement,
                    str(payload.get("evidence", "老板手动录入"))[:500],
                )
            elif path == "/api/operation-summary":
                items = payload.get("completed_items", [])
                if not isinstance(items, list):
                    raise ValueError("completed_items must be an array")
                result = save_summary(items)
                append_event({
                    "id": now_iso(), "generated_at": now_iso(), "kind": "今日运营总结",
                    "summary": result, "problems": [], "opportunities": [],
                })
            else:
                items = payload.get("tasks", [])
                if not isinstance(items, list):
                    raise ValueError("tasks must be an array")
                result = save_manual_plan(items)
                append_event({
                    "id": now_iso(), "generated_at": now_iso(), "kind": "明日计划",
                    "summary": {"headline": f"已保存 {len(result['tasks'])} 项明日计划。"},
                    "problems": [], "opportunities": [], "tomorrow_plan": result,
                })
        except (ValueError, json.JSONDecodeError, OSError, RuntimeError) as error:
            self._json_error(400, error)
            return
        self._json_ok(result, code=201)

    def list_directory(self, path):
        self.send_error(404)
        return None

    def log_message(self, *args):
        pass


class DashboardServer(ThreadingHTTPServer):
    allow_reuse_address = False

    def server_bind(self):
        if hasattr(socket, "SO_EXCLUSIVEADDRUSE"):
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_EXCLUSIVEADDRUSE, 1)
        super().server_bind()


def create_server(port=8876):
    web = validate_resources()
    server = DashboardServer(("127.0.0.1", port), partial(DashboardHandler, directory=str(web)))
    print((web / "WEB_VERSION.txt").read_text(encoding="utf-8"), flush=True)
    return server
