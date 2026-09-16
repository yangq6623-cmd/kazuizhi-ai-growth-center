"""Exercise source/frozen HTTP runtime; reject mixed assets and legacy regressions."""
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
BUILD = "KZ-ENTERPRISE-V2-BETA-20260916-R7-UX1"

class MockAIHandler(BaseHTTPRequestHandler):
    def _send(self, payload):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(data)))
        self.end_headers()
        self.wfile.write(data)

    def do_GET(self):
        check(self.headers.get("Authorization") == "Bearer test-secret-123", "AI test leaked or lost credential")
        self._send({"data": [{"id": "test-model"}]})

    def do_POST(self):
        check(self.headers.get("Authorization") == "Bearer test-secret-123", "AI command lost credential")
        length = int(self.headers.get("Content-Length", "0"))
        payload = json.loads(self.rfile.read(length))
        check(payload.get("model") == "test-model", "AI command used wrong model")
        self._send({"choices": [{"message": {"content": "基于已验证信息的待审核建议"}}]})

    def log_message(self, *args):
        pass

def check(condition, message):
    if not condition:
        raise AssertionError(message)

def inspect_source():
    manifest = json.loads((ROOT / "04_Build/v2/r3_preservation.json").read_text(encoding="utf-8"))
    for name, expected in manifest.items():
        check(hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == expected, f"R3/history changed: {name}")
    for base in (ROOT / "05_V2.0.0_Source",):
        for p in base.rglob("*"):
            if p.is_file() and p.suffix not in (".pyc",):
                text = p.read_text(encoding="utf-8")
                if p.suffix not in (".md", ".json"):
                    check(not any(x in text for x in ("1.9.5", "ENTERPRISE-R2", "ENTERPRISE-R3", "8765")), f"Stale runtime identity: {p}")
    workflow = (ROOT / ".github/workflows/build_v2_enterprise_beta.yml").read_text(encoding="utf-8")
    check("03_V1.9.5_Source" not in workflow and "kazuizhi_v1.9.5.spec" not in workflow, "Legacy build dependency")
    check("installer_output_v2/" in workflow, "Setup upload missing")
    installer = (ROOT / "04_Build/installer/Kazuizhi_AI_V2.0.0_Beta_Setup.iss").read_text(encoding="utf-8")
    check("Kazuizhi_AI_V1.9.5_Enterprise.exe" in installer, "Legacy runtime shutdown missing")
    check("Kazuizhi AI Enterprise V2.0.0 Beta.lnk" in installer, "Stale V2 shortcut cleanup missing")
    check("卡嘴子 AI 增长运营中心 V2 Beta R7.1" in installer, "R7 shortcut identity missing")
    check("卡嘴子 AI 增长运营中心 V2 Beta R2.lnk" in installer, "R2 shortcut cleanup missing")
    check("卡嘴子 AI 增长运营中心 V2 Beta R4.lnk" in installer, "R4 shortcut cleanup missing")
    check("卡嘴子 AI 增长运营中心 V2 Beta R5.lnk" in installer, "R5 shortcut cleanup missing")
    check("卡嘴子 AI 增长运营中心 V2 Beta R6.lnk" in installer, "R6 shortcut cleanup missing")
    spec = (ROOT / "04_Build/kazuizhi_v2.0.0.spec").read_text(encoding="utf-8")
    check("console=False" in spec, "Windowed runtime is not enabled")

def exercise(command):
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    with tempfile.TemporaryDirectory() as tmp:
        report = Path(tmp) / "public-keywords.json"
        report.write_text(json.dumps({"keywords": [{"text": "涟水水电工师傅上门服务电话", "score": 73, "last_seen": "2026-09-16"}]}, ensure_ascii=False), encoding="utf-8")
        runtime_env = dict(os.environ, LOCALAPPDATA=tmp, KAZUIZHI_AI_REPORT_PATH=str(report))
        with open(Path(tmp) / "runtime.log", "w+", encoding="utf-8") as log:
            p = subprocess.Popen(command + ["--no-browser", "--port", str(port)], cwd=tmp, env=runtime_env, stdout=log, stderr=subprocess.STDOUT)
            try:
                base = f"http://127.0.0.1:{port}"
                for attempt in range(100):
                    check(p.poll() is None, "Runtime exited before readiness")
                    try:
                        with urllib.request.urlopen(base + "/api/status", timeout=1) as response:
                            status = json.load(response)
                        break
                    except OSError:
                        time.sleep(.2)
                else:
                    raise AssertionError("Runtime startup timeout")
                check(status["version"] == "2.0.0" and status["stage"] == "Beta" and status["build"] == BUILD, "Wrong API version")
                expected_capabilities = {"daily_review", "operation_summary", "problem_analysis", "growth_opportunities", "tomorrow_plan", "review_history", "ai_memory", "user_growth_analysis", "order_conversion_analysis", "technician_supply_analysis", "leader_promotion_analysis", "channel_effect_analysis", "local_keyword_library", "seo_content_generation", "geo_local_optimization", "ad_copy_generation", "short_video_script", "ai_task_management", "promotion_calendar", "competition_analysis", "customer_demand_analysis", "operations_command_center", "integration_status_center", "external_ai_connection_test", "ai_operations_assistant", "system_self_diagnostics", "approved_job_engine", "truthful_progress", "agent_role_registry", "scheduler_and_audit"}
                check(expected_capabilities.issubset(status["capabilities"]), "V2 capabilities missing")
                for path in ("/", "/?build=" + BUILD, "/WEB_VERSION.txt"):
                    with urllib.request.urlopen(base + path) as response:
                        text = response.read().decode("utf-8")
                        check(BUILD in text and "1.9.5" not in text, "Wrong HTTP asset identity")
                        check(response.headers["Cache-Control"] == "no-store", "Cache guard missing")
                        if path == "/":
                            for label in ("AI 指挥中心", "连接与体检", "任务与员工", "创建待审批任务", "审计日志", "异常中心", "AI 统一对接中心", "四类 AI 协作状态", "外部大模型", "系统体检", "今日复盘", "用户增长分析", "订单转化分析", "师傅资源分析", "团长推广分析", "渠道效果分析", "本地推广 AI 工作台", "选择本地关键词", "生成 SEO 内容", "生成 GEO 方案", "生成广告文案", "生成短视频脚本", "AI 任务管理", "AI 推广日历", "AI 竞争分析", "AI 客户需求分析", "今日运营总结", "明日计划", "历史复盘记录", "AI Memory"):
                                check(label in text, f"Dashboard module missing: {label}")
                def post(route, payload):
                    request = urllib.request.Request(base + route, data=json.dumps(payload, ensure_ascii=False).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
                    with urllib.request.urlopen(request) as response:
                        return json.load(response)
                with urllib.request.urlopen(base + "/api/r7/agents") as response:
                    agents = json.load(response)
                check(len(agents["items"]) == 8 and all(x["execution"] == "requires_approved_job" for x in agents["items"]), "R7 agent roles misreported")
                with urllib.request.urlopen(base + "/api/r7/engine") as response:
                    engine = json.load(response)
                check(engine["migration"]["result"] == "complete" and engine["audit_integrity"] == "verified", "R7 migration or audit failed")
                with urllib.request.urlopen(base + "/api/r7/model-routes") as response:
                    routes = json.load(response)
                check(len(routes["routes"]) == 1 and routes["default"] == "local_rules", "Unverified external route appeared")
                manual = post("/api/r7/jobs", {"kind": "manual_task", "title": "核查本地草稿"})
                check(manual["state"] == "awaiting_approval" and manual["progress"] == 0, "Job bypassed approval")
                try:
                    post("/api/r7/jobs", {"kind": "auto_publish", "title": "对外发布"})
                    raise AssertionError("Unauthorized job kind accepted")
                except urllib.error.HTTPError as error:
                    check(error.code == 400, "Unauthorized job returned wrong status")
                cross_origin = urllib.request.Request(base + "/api/r7/jobs", data=b'{}', headers={"Content-Type": "application/json", "Origin": "https://untrusted.example"}, method="POST")
                try:
                    urllib.request.urlopen(cross_origin)
                    raise AssertionError("Cross-origin mutation accepted")
                except urllib.error.HTTPError as error:
                    check(error.code == 403, "Cross-origin protection returned wrong status")
                manual = post("/api/r7/jobs/command", {"id": manual["id"], "action": "approve", "actor": "owner"})
                check(manual["state"] == "queued" and manual["progress"] == 0, "Approval progress is fabricated")
                manual = post("/api/r7/jobs/command", {"id": manual["id"], "action": "start"})
                check(manual["state"] == "running", "Manual task did not start")
                manual = post("/api/r7/jobs/command", {"id": manual["id"], "action": "complete", "outcome": "已人工核查"})
                check(manual["state"] == "completed" and manual["progress"] == 100, "Manual task result not recorded")
                local = post("/api/r7/jobs", {"kind": "diagnostics", "title": "本机体检"})
                post("/api/r7/jobs/command", {"id": local["id"], "action": "approve", "actor": "owner"})
                post("/api/r7/scheduler/tick", {})
                with urllib.request.urlopen(base + "/api/r7/jobs") as response:
                    jobs = json.load(response)
                local = next(x for x in jobs["items"] if x["id"] == local["id"])
                check(local["state"] == "completed" and local["progress"] == 100, "Approved local task did not execute")
                with urllib.request.urlopen(base + "/api/r7/audit") as response:
                    audit = json.load(response)
                check(audit["integrity"] == "verified" and len(audit["events"]) >= 8, "R7 audit trail incomplete")
                with urllib.request.urlopen(base + "/api/integrations") as response:
                    integrations = json.load(response)
                check(not integrations["external_ai"]["configured"], "External AI falsely reported configured")
                check(any(x["id"] == "local_engine" and x["status"] == "ready" for x in integrations["items"]), "Local engine status missing")
                check(any(x["id"] == "finance" and x["status"] == "blocked" for x in integrations["items"]), "Financial safety status missing")
                with urllib.request.urlopen(base + "/api/control-center") as response:
                    control = json.load(response)
                check(len(control["roles"]) == 4 and len(control["loop"]) == 7, "AI command-center model incomplete")
                diagnostic_request = urllib.request.Request(base + "/api/system/diagnostics", data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(diagnostic_request) as response:
                    diagnostics = json.load(response)
                check(diagnostics["status"] == "healthy" and diagnostics["summary"]["failed"] == 0, "System diagnostics failed")
                mock_ai = HTTPServer(("127.0.0.1", 0), MockAIHandler)
                mock_thread = threading.Thread(target=mock_ai.serve_forever, daemon=True)
                mock_thread.start()
                try:
                    config_request = urllib.request.Request(
                        base + "/api/integrations/ai/configure",
                        data=json.dumps({"base_url": f"http://127.0.0.1:{mock_ai.server_port}/v1", "model": "test-model", "api_key": "test-secret-123"}).encode("utf-8"),
                        headers={"Content-Type": "application/json"}, method="POST")
                    with urllib.request.urlopen(config_request) as response:
                        configured = json.load(response)
                    check(configured["external_ai"]["configured"] and "api_key" not in json.dumps(configured), "AI credential configuration failed or leaked")
                    test_request = urllib.request.Request(base + "/api/integrations/ai/test", data=b"{}", headers={"Content-Type": "application/json"}, method="POST")
                    with urllib.request.urlopen(test_request) as response:
                        tested = json.load(response)
                    check(tested["external_ai"]["status"] == "connected", "AI connection test failed")
                    with urllib.request.urlopen(base + "/api/r7/model-routes") as response:
                        routes = json.load(response)
                    check(len(routes["routes"]) == 2, "Verified external model route missing")
                    command_request = urllib.request.Request(
                        base + "/api/ai/command", data=json.dumps({"prompt": "给出今日待审核建议"}).encode("utf-8"),
                        headers={"Content-Type": "application/json"}, method="POST")
                    with urllib.request.urlopen(command_request) as response:
                        ai_result = json.load(response)
                    check(ai_result["execution"] == "proposal_only" and "待审核" in ai_result["content"], "AI command boundary failed")
                finally:
                    mock_ai.shutdown()
                    mock_ai.server_close()
                with urllib.request.urlopen(base + "/api/promotion/keywords") as response:
                    keywords = json.load(response)
                check(any(x["keyword"] == "涟水水电工师傅上门服务电话" for x in keywords["items"]), "Historical public keyword signal missing")
                check("不代表搜索量" in keywords["truth_rule"], "Keyword truth boundary missing")
                keyword_request = urllib.request.Request(
                    base + "/api/promotion/keywords",
                    data=json.dumps({"keyword": "涟水空调清洗服务", "region": "涟水", "category": "家电清洗"}).encode("utf-8"),
                    headers={"Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(keyword_request) as response:
                    check(json.load(response)["source"] == "owner_input", "Owner keyword was not labelled")
                promotion_payload = {"region": "涟水", "service": "水电维修", "keyword": "涟水水电维修", "audience": "本地家庭用户", "evidence": ""}
                for route, kind in (("seo-content", "SEO内容草稿"), ("geo-plan", "GEO本地优化建议"), ("ad-copy", "广告文案草稿"), ("video-script", "短视频脚本草稿")):
                    promotion_request = urllib.request.Request(
                        base + "/api/promotion/" + route,
                        data=json.dumps(promotion_payload).encode("utf-8"),
                        headers={"Content-Type": "application/json"}, method="POST")
                    with urllib.request.urlopen(promotion_request) as response:
                        draft = json.load(response)
                    check(draft["kind"] == kind and draft["execution"] == "proposal_only", "Promotion draft bypassed review")
                    rendered = json.dumps(draft, ensure_ascii=False)
                    check(not any(claim in rendered for claim in ("人人都能接单", "无需审核即可接单", "所有任务都能发布")), "Forbidden promotion claim generated")
                unsafe_promotion = urllib.request.Request(
                    base + "/api/promotion/ad-copy",
                    data=json.dumps(dict(promotion_payload, service="人人都能接单")).encode("utf-8"),
                    headers={"Content-Type": "application/json"}, method="POST")
                try:
                    urllib.request.urlopen(unsafe_promotion)
                    raise AssertionError("Forbidden promotion claim accepted")
                except urllib.error.HTTPError as error:
                    check(error.code == 400, "Forbidden promotion claim returned wrong status")
                with urllib.request.urlopen(base + "/api/promotion/history") as response:
                    promotion_history = json.load(response)
                check(len(promotion_history["items"]) == 4 and promotion_history["execution"] == "proposal_only", "Promotion history was not persisted")
                task_request = urllib.request.Request(
                    base + "/api/operations/tasks",
                    data=json.dumps({"title": "审核本地推广草稿", "priority": "high", "due_date": "2026-09-17"}).encode("utf-8"),
                    headers={"Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(task_request) as response:
                    task = json.load(response)
                check(task["status"] == "pending" and task["execution"] == "manual", "AI task creation failed")
                update_task_request = urllib.request.Request(
                    base + "/api/operations/tasks/update",
                    data=json.dumps({"id": task["id"], "status": "completed"}).encode("utf-8"),
                    headers={"Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(update_task_request) as response:
                    task = json.load(response)
                check(task["status"] == "completed", "AI task status update failed")
                calendar_request = urllib.request.Request(
                    base + "/api/operations/calendar/generate",
                    data=json.dumps({"region": "涟水", "service": "本地维修"}).encode("utf-8"),
                    headers={"Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(calendar_request) as response:
                    calendar = json.load(response)
                check(len(calendar["items"]) == 7 and all(x["execution"] == "proposal_only" for x in calendar["items"]), "Promotion calendar failed")
                competition_request = urllib.request.Request(
                    base + "/api/insights/competition",
                    data=json.dumps({"region": "涟水", "category": "本地维修", "observations": ["同行页面写明服务区域", "常见问题内容较完整"]}).encode("utf-8"),
                    headers={"Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(competition_request) as response:
                    competition = json.load(response)
                check(competition["evidence_count"] == 2 and competition["execution"] == "proposal_only", "Competition analysis failed")
                with urllib.request.urlopen(base + "/api/insights/demand") as response:
                    demand = json.load(response)
                check(demand["public_signal_count"] == 1 and "不等于" in demand["truth_rule"], "Customer demand truth boundary failed")
                with urllib.request.urlopen(base + "/api/command-center") as response:
                    command_center = json.load(response)
                check(command_center["task_counts"]["completed"] == 1 and command_center["calendar_days"] == 7, "Command center aggregation failed")
                for route in ("tasks", "statistics", "kazuizhi"):
                    with urllib.request.urlopen(base + "/api/" + route) as response:
                        check(json.load(response)["status"] == "not_connected", "Placeholder data misreported")
                with urllib.request.urlopen(base + "/api/operation-summary/today") as response:
                    summary = json.load(response)
                check(summary["status"] == "not_connected" and not summary["verified_metrics"], "Unverified business data reported")
                request = urllib.request.Request(
                    base + "/api/daily-review/generate",
                    data=b"{}",
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(request) as response:
                    review = json.load(response)
                check(response.status == 201 and review["status"] == "generated", "Daily review generation failed")
                check(review["summary"]["status"] == "not_connected", "Review invented business data")
                check(review["problems"] and review["opportunities"], "Problem or opportunity analysis missing")
                check(review["tomorrow_plan"]["tasks"], "Tomorrow plan missing")
                check(all(item["execution"] == "proposal_only" for item in review["tomorrow_plan"]["tasks"]), "Plan bypassed review")
                check("退款" in review["tomorrow_plan"]["blocked_financial_actions"], "Financial safety boundary missing")
                with urllib.request.urlopen(base + "/api/business-analytics") as response:
                    analytics = json.load(response)
                check(analytics["status"] == "not_connected", "Disconnected business data was reported as verified")
                unsafe_request = urllib.request.Request(
                    base + "/api/business-metrics/import",
                    data=json.dumps({"source": "test", "as_of": "2026-09-16", "phone": "13800000000"}).encode("utf-8"),
                    headers={"Content-Type": "application/json"}, method="POST")
                try:
                    urllib.request.urlopen(unsafe_request)
                    raise AssertionError("Sensitive business field accepted")
                except urllib.error.HTTPError as error:
                    check(error.code == 400, "Sensitive field rejection returned wrong status")
                verified_snapshot = {
                    "source": "automated-readonly-test", "as_of": "2026-09-16 08:00:00", "window": "today",
                    "mini_program_visits": 100, "repair_requests": 20, "new_users": 30, "leads": 10,
                    "new_orders": 8, "completed_orders": 6, "cancelled_orders": 1,
                    "new_technicians": 4, "approved_technicians": 3, "active_technicians": 12, "technician_inquiries": 5,
                    "new_leaders": 2, "active_leaders": 7, "leader_referrals": 5, "leader_orders": 2,
                    "published_content": 4, "channel_visits": {"SEO": 40, "品牌小程序码": 60},
                    "channel_orders": {"SEO": 5, "品牌小程序码": 3}, "by_region": {"涟水": 8}, "by_skill": {"水电维修": 5},
                }
                import_request = urllib.request.Request(
                    base + "/api/business-metrics/import", data=json.dumps(verified_snapshot).encode("utf-8"),
                    headers={"Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(import_request) as response:
                    analytics = json.load(response)
                check(response.status == 201 and analytics["status"] == "verified", "Verified business snapshot import failed")
                check(analytics["modules"]["order_conversion"]["rates"]["request_to_order_pct"] == 40.0, "Order conversion is wrong")
                check(len(analytics["modules"]["channel_effect"]["breakdown"]["channels"]) == 2, "Channel analysis missing")
                check(analytics["modules"]["leader_promotion"]["status"] == "verified", "Leader analysis missing")
                with urllib.request.urlopen(base + "/api/operation-summary/today") as response:
                    connected_summary = json.load(response)
                check(connected_summary["verified_metrics"]["orders"] == 8 and connected_summary["verified_metrics"]["users"] == 30, "Business metrics did not feed operation summary")
                summary_request = urllib.request.Request(
                    base + "/api/operation-summary",
                    data=json.dumps({"completed_items": ["verified completed item"]}).encode("utf-8"),
                    headers={"Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(summary_request) as response:
                    saved_summary = json.load(response)
                check(saved_summary["completed_items"] == ["verified completed item"], "Manual daily summary failed")
                plan_request = urllib.request.Request(
                    base + "/api/tomorrow-plan",
                    data=json.dumps({"tasks": ["review local growth signals"]}).encode("utf-8"),
                    headers={"Content-Type": "application/json"}, method="POST")
                with urllib.request.urlopen(plan_request) as response:
                    saved_plan = json.load(response)
                check(saved_plan["tasks"][0]["execution"] == "proposal_only", "Manual plan bypassed review")
                for route in ("daily-review/latest", "tomorrow-plan/latest", "history", "memory", "experiments"):
                    with urllib.request.urlopen(base + "/api/" + route) as response:
                        payload = json.load(response)
                    check(isinstance(payload, dict), f"Invalid module response: {route}")
                with urllib.request.urlopen(base + "/api/history") as response:
                    history = json.load(response)
                check(len(history["items"]) == 3, "Review, summary and plan history were not persisted")
                memory_request = urllib.request.Request(
                    base + "/api/memory",
                    data=json.dumps({"category": "test", "statement": "verified fact", "evidence": "automated test"}).encode("utf-8"),
                    headers={"Content-Type": "application/json"},
                    method="POST",
                )
                with urllib.request.urlopen(memory_request) as response:
                    memory = json.load(response)
                check(memory["entries"][-1]["statement"] == "verified fact", "AI Memory write failed")
                data_dir = Path(tmp) / "Kazuizhi_AI_Enterprise_V2.0.0_Beta" / "data"
                check((data_dir / "reviews/latest_review.json").exists(), "Latest review file missing")
                check((data_dir / "reviews/history.json").exists(), "Review history file missing")
                check((data_dir / "plans/latest_plan.json").exists(), "Latest plan file missing")
                check((data_dir / "summaries/today.json").exists(), "Daily summary file missing")
                check((data_dir / "memory/learning_memory.json").exists(), "AI Memory file missing")
                check((data_dir / "business/verified_snapshot.json").exists(), "Verified business snapshot missing")
                check((data_dir / "promotion/keywords.json").exists(), "Keyword library missing")
                check((data_dir / "promotion/history.json").exists(), "Promotion history missing")
                check((data_dir / "operations/tasks.json").exists(), "Operations task store missing")
                check((data_dir / "operations/promotion_calendar.json").exists(), "Promotion calendar store missing")
                check((data_dir / "operations/competition_history.json").exists(), "Competition history missing")
                check((data_dir / "integrations/config.json").exists(), "Integration configuration missing")
                check((data_dir / "integrations/ai_key.bin").exists(), "Encrypted AI credential missing")
                check((data_dir / "r7/jobs.json").exists() and (data_dir / "r7/audit.json").exists(), "R7 durable records missing")
                check((data_dir / "r7/migration.json").exists(), "R7 migration record missing")
                # A second process must fail, not open a browser to the occupied port.
                duplicate = subprocess.run(command + ["--no-browser", "--port", str(port)], cwd=tmp, env=runtime_env, capture_output=True, timeout=15)
                check(duplicate.returncode != 0, "Port conflict accepted")
                duplicate_output = (duplicate.stdout + duplicate.stderr).decode("utf-8", errors="replace")
                if not str(command[0]).lower().endswith(".exe"):
                    check(str(port) in duplicate_output and "Traceback" not in duplicate_output, "Port conflict message is unclear")
            finally:
                p.terminate()
                p.wait(timeout=15)
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
    print("PASS: V2 identity, all 20 recovery capabilities, R7 UX and integration truth, windowed runtime, truth policy, persistence, HTTP routes, resources, port conflict and R3/history preservation")


