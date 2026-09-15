"""
Kazuizhi AI V1.9.5 local web console.
"""

import threading
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime

HOST = "127.0.0.1"
PORT = 8765
START_TIME = datetime.now()

HTML = """
<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>卡嘴智AI控制中心</title>
<style>
body{margin:0;background:#0f172a;color:#e5e7eb;font-family:Arial,"Microsoft YaHei"}
.header{padding:25px;background:#111827;font-size:28px}
.status{color:#22c55e}
.container{display:grid;grid-template-columns:repeat(3,1fr);gap:20px;padding:25px}
.card{background:#1e293b;border-radius:12px;padding:20px;box-shadow:0 4px 15px #0005}
.title{font-size:18px;margin-bottom:15px}
.value{font-size:24px}
</style>
</head>
<body>
<div class="header">卡嘴智 AI Growth Center V1.9.5</div>
<div class="container">
<div class="card"><div class="title">系统状态</div><div class="value status">● 在线运行</div></div>
<div class="card"><div class="title">AI引擎</div><div class="value">Running</div></div>
<div class="card"><div class="title">启动时间</div><div class="value">%s</div></div>
<div class="card"><div class="title">任务中心</div><div class="value">准备接入</div></div>
<div class="card"><div class="title">数据中心</div><div class="value">准备接入</div></div>
<div class="card"><div class="title">日志中心</div><div class="value">正常</div></div>
</div>
</body>
</html>
"""


class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        page = HTML % START_TIME.strftime("%Y-%m-%d %H:%M:%S")
        self.send_response(200)
        self.send_header("Content-Type", "text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(page.encode("utf-8"))

    def log_message(self, format, *args):
        return


def start_web():
    server = HTTPServer((HOST, PORT), Handler)

    def run():
        server.serve_forever()

    threading.Thread(target=run, daemon=True).start()
    webbrowser.open(f"http://{HOST}:{PORT}")
    return f"http://{HOST}:{PORT}"
