"""
Kazuizhi AI V1.9.5 local web dashboard.
"""

import threading
import webbrowser
import datetime
from http.server import BaseHTTPRequestHandler, HTTPServer
import json

HOST = "127.0.0.1"
PORT = 8765

START_TIME = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

PAGE = """
<!doctype html>
<html>
<head>
<meta charset='utf-8'>
<title>卡嘴智 AI运营中心 V1.9.5</title>
<style>
body{font-family:Microsoft YaHei;background:#f3f7fb;margin:0;padding:30px;color:#1f2937}
h1{color:#0f172a}
.grid{display:grid;grid-template-columns:repeat(3,1fr);gap:20px}
.card{background:white;border-radius:14px;padding:20px;box-shadow:0 4px 15px #dbe4ef}
.title{font-size:18px;color:#475569}.num{font-size:28px;margin-top:12px;color:#2563eb}
.ok{color:#16a34a}
</style>
</head>
<body>
<h1>卡嘴智 AI 自动化运营中心 V1.9.5</h1>
<div class='grid'>
<div class='card'><div class='title'>系统状态</div><div class='num ok'>在线运行</div></div>
<div class='card'><div class='title'>AI引擎</div><div class='num'>Running</div></div>
<div class='card'><div class='title'>启动时间</div><div class='num' style='font-size:18px'>START_TIME</div></div>
<div class='card'><div class='title'>任务中心</div><div class='num'>准备接入</div></div>
<div class='card'><div class='title'>数据中心</div><div class='num'>准备接入</div></div>
<div class='card'><div class='title'>SEO/GEO中心</div><div class='num'>准备接入</div></div>
<div class='card'><div class='title'>日志中心</div><div class='num'>正常</div></div>
<div class='card'><div class='title'>卡嘴子业务接口</div><div class='num'>待连接</div></div>
<div class='card'><div class='title'>自动化任务</div><div class='num'>待连接</div></div>
</div>
</body>
</html>
""".replace("START_TIME", START_TIME)

class Handler(BaseHTTPRequestHandler):
    def do_GET(self):
        if self.path == "/api/status":
            data = {"status":"online","version":"V1.9.5","start_time":START_TIME}
            self.send_response(200)
            self.send_header("Content-Type","application/json; charset=utf-8")
            self.end_headers()
            self.wfile.write(json.dumps(data,ensure_ascii=False).encode("utf-8"))
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
