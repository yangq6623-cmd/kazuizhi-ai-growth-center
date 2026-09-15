"""Kazuizhi AI V1.9.5 dashboard server #28."""

import threading
import webbrowser
import datetime
import json
from http.server import BaseHTTPRequestHandler, HTTPServer

HOST = "127.0.0.1"
PORT = 8765
START_TIME = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

PAGE = """
<!doctype html>
<html><head><meta charset='utf-8'><title>卡嘴智 AI运营中心 V1.9.5</title>
<style>
body{font-family:Microsoft YaHei;background:#f3f7fb;padding:30px;color:#1f2937}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}
.card{background:#fff;padding:22px;border-radius:14px;box-shadow:0 4px 15px #dbe4ef}
.num{font-size:24px;color:#2563eb;margin-top:10px}.ok{color:#16a34a}
</style></head>
<body>
<h1>卡嘴智 AI 自动化运营中心 V1.9.5</h1>
<div class='grid'>
<div class='card'>系统状态<div class='num ok'>在线运行</div></div>
<div class='card'>AI引擎<div class='num'>Running</div></div>
<div class='card'>启动时间<div class='num'>START_TIME</div></div>
<div class='card'>AI任务中心<div class='num'>数据接口已连接</div></div>
<div class='card'>数据中心<div class='num'>统计接口已连接</div></div>
<div class='card'>SEO/GEO中心<div class='num'>增长分析模块</div></div>
<div class='card'>日志中心<div class='num'>运行正常</div></div>
<div class='card'>卡嘴子业务<div class='num'>接口预留</div></div>
<div class='card'>自动化中心<div class='num'>准备运行</div></div>
</div>
</body></html>
""".replace("START_TIME", START_TIME)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        routes = {
            "/api/status": {"status":"online","version":"V1.9.5","start_time":START_TIME},
            "/api/tasks": {"running":0,"completed":0,"failed":0},
            "/api/logs": {"latest":"Dashboard service running"},
            "/api/statistics": {"users":0,"orders":0,"promotion":0},
            "/api/kazuizhi": {"users":0,"masters":0,"leaders":0}
        }
        if self.path in routes:
            self.send_response(200)
            self.send_header("Content-Type","application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(routes[self.path],ensure_ascii=False).encode("utf-8"))
            return
        self.send_response(200)
        self.send_header("Content-Type","text/html; charset=utf-8")
        self.end_headers()
        self.wfile.write(PAGE.encode("utf-8"))

    def log_message(self, format, *args):
        return

def start_web():
    server = HTTPServer((HOST, PORT), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    webbrowser.open(f"http://{HOST}:{PORT}")
    return f"http://{HOST}:{PORT}"
