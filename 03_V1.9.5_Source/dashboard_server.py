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
    def log_message(self, format, *args):
        pass


def start_dashboard_server(host="127.0.0.1", port=8765):
    web_path = get_web_path()
    os.chdir(web_path)
    server = ThreadingHTTPServer((host, port), DashboardHandler)
    server.serve_forever()
