"""
Kazuizhi AI V1.9.5 local web server bootstrap.
"""

import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

HOST = "127.0.0.1"
PORT = 8765


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(b"<html><body><h1>Kazuizhi AI V1.9.5</h1><p>Service running.</p></body></html>")

    def log_message(self, format, *args):
        return


def start_web():
    server = HTTPServer((HOST, PORT), Handler)

    def run():
        server.serve_forever()

    threading.Thread(target=run, daemon=True).start()
    webbrowser.open(f"http://{HOST}:{PORT}")
    return f"http://{HOST}:{PORT}"
