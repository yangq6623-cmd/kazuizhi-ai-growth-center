"""Kazuizhi AI Dashboard local server."""

import os
import sys
from pathlib import Path
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler


def get_web_path():
    if getattr(sys, "frozen", False):
        return Path(sys._MEIPASS) / "web"
    return Path(__file__).resolve().parent / "web"


class DashboardHandler(SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    def log_message(self, format, *args):
        pass


def start_dashboard_server(host="127.0.0.1", port=8876):
    web_path = get_web_path()
    print(f"Dashboard resource path: {web_path}")
    print(f"Dashboard listen: http://{host}:{port}")

    version_file = web_path / "WEB_VERSION.txt"
    if version_file.exists():
        print(version_file.read_text(encoding="utf-8"))

    os.chdir(web_path)
    server = ThreadingHTTPServer((host, port), DashboardHandler)
    server.serve_forever()
