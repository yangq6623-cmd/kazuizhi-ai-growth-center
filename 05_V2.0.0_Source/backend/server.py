import json
import re
import socket
import sys
from functools import partial
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlsplit
from ai_center.daily_review import generate_review, latest_plan, latest_review
from analytics.business_metrics import build_analytics, import_snapshot, import_template
from analytics.operation_summary import build_summary, save_summary
from core.storage import now_iso
from core.r7_engine import (
    agent_registry, audit_history, command as job_command, create_job,
    engine_status, list_jobs, run_due_jobs,
)
from core.version import BUILD_ID, get_version
from memory.memory_store import get_experiments, get_memory, remember
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

    def do_GET(self):
        path = urlsplit(self.path).path
        if path.startswith("/api/"):
            try:
                refresh_business_if_due()
            except Exception:
                # Live business data must never prevent the local R7 control plane from loading.
                pass
            routes = {
                "/api/status": dict(
                    get_version(),
                    status="online",
                    capabilities=[
                        "daily_review",
                        "operation_summary",
                        "problem_analysis",
                        "growth_opportunities",
                        "tomorrow_plan",
                        "review_history",
                        "ai_memory",
                        "user_growth_analysis",
                        "order_conversion_analysis",
                        "technician_supply_analysis",
                        "leader_promotion_analysis",
                        "channel_effect_analysis",
                        "local_keyword_library",
                        "seo_content_generation",
                        "geo_local_optimization",
                        "ad_copy_generation",
                        "short_video_script",
                        "ai_task_management",
                        "promotion_calendar",
                        "competition_analysis",
                        "customer_demand_analysis",
                        "operations_command_center",
                        "integration_status_center",
                        "external_ai_connection_test",
                        "ai_operations_assistant",
                        "system_self_diagnostics",
                        "approved_job_engine",
                        "truthful_progress",
                        "agent_role_registry",
                        "scheduler_and_audit",
                        "bidirectional_operations_bridge",
                        "offline_autonomous_mode",
                        "bridge_command_receipts",
                        "bridge_closed_loop_self_test",
                        "verified_readonly_business_source",
                    ],
                ),
                "/api/tasks": {"status": "not_connected", "running": None, "completed": None, "failed": None},
                "/api/logs": {"latest": "V2 Beta dashboard service running"},
                "/api/statistics": {"status": "not_connected", "users": None, "orders": None, "promotion": None},
                "/api/kazuizhi": {"status": "not_connected", "users": None, "masters": None, "leaders": None},
                "/api/daily-review/latest": latest_review(),
                "/api/operation-summary/today": build_summary(),
                "/api/tomorrow-plan/latest": latest_plan(),
                "/api/history": list_reviews(),
                "/api/memory": get_memory(),
                "/api/experiments": get_experiments(),
                "/api/business-analytics": build_analytics(),
                "/api/business-metrics/template": import_template(),
                "/api/business-source/status": business_source_status(build_analytics()),
                "/api/promotion/keywords": list_keywords(),
                "/api/promotion/history": promotion_history(),
                "/api/operations/tasks": list_tasks(),
                "/api/operations/calendar": get_calendar(),
                "/api/insights/competition": competition_history(),
                "/api/insights/demand": demand_insights(),
                "/api/command-center": command_center(),
                "/api/control-center": control_center(),
                "/api/integrations": integration_status(),
                "/api/system/diagnostics": system_diagnostics(),
                "/api/bridge/status": bridge_status(),
                "/api/bridge/commands": list_bridge_commands(),
                "/api/r7/jobs": list_jobs(),
                "/api/r7/agents": agent_registry(),
                "/api/r7/engine": engine_status(),
                "/api/r7/audit": audit_history(),
                "/api/r7/model-routes": model_routes(),
            }
            if path not in routes:
                self.send_error(404)
                return
            data = json.dumps(routes[path], ensure_ascii=False).encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        super().do_GET()

    def do_POST(self):
        path = urlsplit(self.path).path
        origin = self.headers.get("Origin")
        if origin and origin not in {f"http://127.0.0.1:{self.server.server_port}", f"http://localhost:{self.server.server_port}"}:
            self.send_error(403, "Cross-origin changes are not allowed")
            return
        if path not in (
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
            "/api/bridge/self-test",
            "/api/r7/jobs", "/api/r7/jobs/command", "/api/r7/scheduler/tick",
        ):
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
        except (ValueError, json.JSONDecodeError, OSError) as error:
            data = json.dumps({"error": str(error)}, ensure_ascii=False).encode("utf-8")
            self.send_response(400)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(data)))
            self.end_headers()
            self.wfile.write(data)
            return
        data = json.dumps(result, ensure_ascii=False).encode("utf-8")
        self.send_response(201)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

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
    # Bind synchronously: an occupied R3 port must fail before opening a browser.
    server = DashboardServer(("127.0.0.1", port), partial(DashboardHandler, directory=str(web)))
    print((web / "WEB_VERSION.txt").read_text(encoding="utf-8"), flush=True)
    return server
