"""Verify the autonomous R7 runtime and packaged executable.

This verifier replaces the legacy approval-first acceptance contract. R7 now
runs non-financial operating work automatically while routing financial items
to platform staff for manual handling. Audit, truth, origin and packaging
boundaries remain mandatory.
"""
import argparse
import hashlib
import json
import os
import socket
import subprocess
import sys
import tempfile
import threading
import time
import urllib.error
import urllib.request
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
NAME = "Kazuizhi_AI_Enterprise_V2.0.0_Beta"
BUILD = "KZ-ENTERPRISE-V2-BETA-20260917-R7-FINAL"


def check(condition, message):
    if not condition:
        raise AssertionError(message)


class MockAIHandler(BaseHTTPRequestHandler):
    def _send(self, payload):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        check(self.headers.get("Authorization") == "Bearer test-secret-123", "AI credential lost")
        self._send({"data": [{"id": "test-model"}]})

    def do_POST(self):
        check(self.headers.get("Authorization") == "Bearer test-secret-123", "AI command credential lost")
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length))
        check(payload.get("model") == "test-model", "AI command used wrong model")
        self._send({"choices": [{"message": {"content": "基于已验证信息的运营建议"}}]})

    def log_message(self, *args):
        pass


def inspect_source():
    manifest = json.loads((ROOT / "04_Build/v2/r3_preservation.json").read_text(encoding="utf-8"))
    for name, expected in manifest.items():
        check(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, f"R3/history changed: {name}")
    for path in (ROOT / "05_V2.0.0_Source").rglob("*"):
        if path.is_file() and path.suffix not in (".pyc", ".md", ".json"):
            text = path.read_text(encoding="utf-8")
            check(not any(x in text for x in ("1.9.5", "ENTERPRISE-R2", "ENTERPRISE-R3", "8765")), f"Stale runtime identity: {path}")
    workflow = (ROOT / ".github/workflows/build_v2_enterprise_beta.yml").read_text(encoding="utf-8")
    check("03_V1.9.5_Source" not in workflow and "kazuizhi_v1.9.5.spec" not in workflow, "Legacy build dependency")
    installer = (ROOT / "04_Build/installer/Kazuizhi_AI_V2.0.0_Beta_Setup.iss").read_text(encoding="utf-8")
    check("卡嘴子 AI 增长运营中心 V2 Beta R7 Final" in installer, "R7 shortcut identity missing")
    spec = (ROOT / "04_Build/kazuizhi_v2.0.0.spec").read_text(encoding="utf-8")
    check("console=False" in spec, "Windowed runtime is not enabled")


def exercise(command):
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    with tempfile.TemporaryDirectory() as tmp:
        public_report = Path(tmp) / "public-keywords.json"
        public_report.write_text(json.dumps({"keywords": [{"text": "涟水水电工师傅上门服务电话", "score": 73, "last_seen": "2026-09-16"}]}, ensure_ascii=False), encoding="utf-8")
        env = dict(os.environ, LOCALAPPDATA=tmp, KAZUIZHI_AI_REPORT_PATH=str(public_report))
        log_path = Path(tmp) / "runtime.log"
        with open(log_path, "w+", encoding="utf-8") as log:
            process = subprocess.Popen(command + ["--no-browser", "--port", str(port)], cwd=tmp, env=env, stdout=log, stderr=subprocess.STDOUT)
            try:
                base = f"http://127.0.0.1:{port}"
                for _ in range(100):
                    check(process.poll() is None, "Runtime exited before readiness")
                    try:
                        with urllib.request.urlopen(base + "/api/status", timeout=1) as response:
                            status = json.load(response)
                        break
                    except OSError:
                        time.sleep(.2)
                else:
                    raise AssertionError("Runtime startup timeout")

                check(status["version"] == "2.0.0" and status["stage"] == "Beta" and status["build"] == BUILD, "Wrong API identity")
                for path in ("/", "/?build=" + BUILD, "/WEB_VERSION.txt"):
                    with urllib.request.urlopen(base + path) as response:
                        text = response.read().decode("utf-8")
                        check(BUILD in text and "1.9.5" not in text, "Wrong HTTP asset identity")
                        check(response.headers["Cache-Control"] == "no-store", "Cache guard missing")

                def post(route, payload):
                    request = urllib.request.Request(base + route, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
                    with urllib.request.urlopen(request) as response:
                        return json.load(response)

                with urllib.request.urlopen(base + "/api/r7/agents") as response:
                    agents = json.load(response)
                check(len(agents["items"]) == 8, "R7 agent count incorrect")
                check(all(x.get("execution") == "autonomous_non_financial" for x in agents["items"]), "R7 agent autonomy policy misreported")

                with urllib.request.urlopen(base + "/api/r7/engine") as response:
                    engine = json.load(response)
                check(engine["migration"]["result"] == "complete" and engine["audit_integrity"] == "verified", "Migration or audit failed")
                check("非资金任务自动执行" in engine.get("autonomy_policy", ""), "Autonomy policy missing")

                operating = post("/api/r7/jobs", {"kind": "manual_task", "title": "收集并整理涟水县周边维修市场公开数据"})
                check(operating["state"] == "queued" and operating["mode"] == "local", "Non-financial job did not auto-queue")
                check(operating["execution"] == "autonomous" and operating["risk"] == "non_financial", "Non-financial classification failed")
                post("/api/r7/scheduler/tick", {})
                with urllib.request.urlopen(base + "/api/r7/jobs") as response:
                    jobs = json.load(response)["items"]
                operating = next(x for x in jobs if x["id"] == operating["id"])
                check(operating["state"] == "completed" and operating["progress"] == 100, "Autonomous operating job did not complete")
                check(operating.get("result"), "Autonomous operating result missing")

                financial = post("/api/r7/jobs", {"kind": "manual_task", "title": "审核退款并安排资金结算"})
                check(financial["state"] == "human_required", "Financial job was not routed to staff")
                check(financial["execution"] == "platform_manual" and financial["risk"] == "financial", "Financial execution policy incorrect")
                post("/api/r7/scheduler/tick", {})
                with urllib.request.urlopen(base + "/api/r7/jobs") as response:
                    jobs = json.load(response)["items"]
                financial_after = next(x for x in jobs if x["id"] == financial["id"])
                check(financial_after["state"] == "human_required" and financial_after["progress"] == 0, "Financial task was auto-executed")
                with urllib.request.urlopen(base + "/api/r7/engine") as response:
                    engine = json.load(response)
                check(any(x.get("id") == financial["id"] for x in engine.get("human_interventions", [])), "Financial handoff record missing")

                try:
                    post("/api/r7/jobs", {"kind": "auto_publish", "title": "未授权执行类型"})
                    raise AssertionError("Unauthorized job kind accepted")
                except urllib.error.HTTPError as error:
                    check(error.code == 400, "Unauthorized job returned wrong status")

                cross_origin = urllib.request.Request(base + "/api/r7/jobs", data=b"{}", headers={"Content-Type": "application/json", "Origin": "https://untrusted.example"}, method="POST")
                try:
                    urllib.request.urlopen(cross_origin)
                    raise AssertionError("Cross-origin mutation accepted")
                except urllib.error.HTTPError as error:
                    check(error.code == 403, "Cross-origin protection returned wrong status")

                with urllib.request.urlopen(base + "/api/r7/audit") as response:
                    audit = json.load(response)
                check(audit["integrity"] == "verified" and len(audit["events"]) >= 6, "R7 audit trail incomplete")

                with urllib.request.urlopen(base + "/api/integrations") as response:
                    integrations = json.load(response)
                check(not integrations["external_ai"]["configured"], "External AI falsely reported configured")
                check(any(x["id"] == "finance" and x["status"] == "blocked" for x in integrations["items"]), "Financial safety status missing")

                for route in ("tasks", "statistics", "kazuizhi"):
                    with urllib.request.urlopen(base + "/api/" + route) as response:
                        check(json.load(response)["status"] == "not_connected", "Placeholder business data misreported")

                with urllib.request.urlopen(base + "/api/promotion/keywords") as response:
                    keywords = json.load(response)
                check(any(x["keyword"] == "涟水水电工师傅上门服务电话" for x in keywords["items"]), "Public keyword signal missing")
                check("不代表搜索量" in keywords["truth_rule"], "Keyword truth boundary missing")

                mock_ai = HTTPServer(("127.0.0.1", 0), MockAIHandler)
                thread = threading.Thread(target=mock_ai.serve_forever, daemon=True)
                thread.start()
                try:
                    configured = post("/api/integrations/ai/configure", {"base_url": f"http://127.0.0.1:{mock_ai.server_port}/v1", "model": "test-model", "api_key": "test-secret-123"})
                    check(configured["external_ai"]["configured"] and "api_key" not in json.dumps(configured), "AI configuration failed or leaked")
                    tested = post("/api/integrations/ai/test", {})
                    check(tested["external_ai"]["status"] == "connected", "AI connection test failed")
                    result = post("/api/ai/command", {"prompt": "给出今日运营建议"})
                    check(result["execution"] == "proposal_only", "External AI bypassed proposal boundary")
                finally:
                    mock_ai.shutdown()
                    mock_ai.server_close()

                data_dir = Path(tmp) / "Kazuizhi_AI_Enterprise_V2.0.0_Beta" / "data"
                check((data_dir / "r7/jobs.json").exists() and (data_dir / "r7/audit.json").exists(), "R7 durable records missing")
                check((data_dir / "r7/human_interventions.json").exists(), "Human intervention store missing")
                check((data_dir / "r7/learning.json").exists(), "Autonomous learning store missing")
                check((data_dir / "plans/latest_plan.json").exists(), "Tomorrow plan missing after learning")

                duplicate = subprocess.run(command + ["--no-browser", "--port", str(port)], cwd=tmp, env=env, capture_output=True, timeout=15)
                check(duplicate.returncode != 0, "Port conflict accepted")
            finally:
                process.terminate()
                process.wait(timeout=15)
                log.seek(0)
                print(log.read())


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--source", action="store_true")
    group.add_argument("--exe", type=Path)
    args = parser.parse_args()
    inspect_source()
    if args.exe:
        exe = args.exe.resolve()
        check(exe.name == NAME + ".exe", "Wrong executable name")
        resources = exe.parent / "_internal"
        for source_dir in ("web", "version"):
            for source in (ROOT / "05_V2.0.0_Source" / source_dir).rglob("*"):
                if source.is_file():
                    packed = resources / source_dir / source.relative_to(ROOT / "05_V2.0.0_Source" / source_dir)
                    check(packed.read_bytes() == source.read_bytes(), f"Packaged asset mismatch: {packed}")
        exercise([str(exe)])
    else:
        exercise([sys.executable, str(ROOT / "05_V2.0.0_Source/run.py")])
    print("PASS: autonomous non-financial execution, financial staff handoff, audit, truth, packaging, persistence and runtime identity")
