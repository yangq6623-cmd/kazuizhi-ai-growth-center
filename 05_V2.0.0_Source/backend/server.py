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
from core.version import BUILD_ID, get_version
from memory.memory_store import get_experiments, get_memory, remember
from planning.tomorrow_plan import save_manual_plan
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
        if path not in ("/api/daily-review/generate", "/api/memory", "/api/operation-summary", "/api/tomorrow-plan", "/api/business-metrics/import"):
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
        except (ValueError, json.JSONDecodeError) as error:
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
