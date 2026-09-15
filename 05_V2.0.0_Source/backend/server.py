import json
import re
import socket
import sys
from functools import partial
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from urllib.parse import urlsplit
from core.version import BUILD_ID, get_version

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
                "/api/status": dict(get_version(), status="online"),
                "/api/tasks": {"status": "not_connected", "running": None, "completed": None, "failed": None},
                "/api/logs": {"latest": "V2 Beta dashboard service running"},
                "/api/statistics": {"status": "not_connected", "users": None, "orders": None, "promotion": None},
                "/api/kazuizhi": {"status": "not_connected", "users": None, "masters": None, "leaders": None},
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
