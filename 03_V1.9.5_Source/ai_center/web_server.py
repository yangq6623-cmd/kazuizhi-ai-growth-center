"""
Kazuizhi AI V1.9.5 local web console.
"""

import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer

HOST = "127.0.0.1"
PORT = 8765

PAGE = """
<!doctype html>
<html><head><meta charset='utf-8'><title>卡嘴智 AI 运营中心</title></head>
<body>
<h1>卡嘴智 AI 运营中心 V1.9.5</h1>
<div>● 服务在线</div>
<hr>
<div>AI引擎　Running</div>
<div>任务中心　准备接入</div>
<div>数据中心　准备接入</div>
<div>SEO/GEO中心　准备接入</div>
<div>日志中心　准备接入</div>
</body></html>
"""

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(PAGE.encode("utf-8"))

    def log_message(self, format, *args):
        return


def start_web():
    server = HTTPServer((HOST, PORT), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    webbrowser.open(f"http://{HOST}:{PORT}")
    return f"http://{HOST}:{PORT}"
