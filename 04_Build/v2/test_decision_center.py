import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SRC))

sandbox = Path(tempfile.mkdtemp(prefix="kazuizhi-decision-center-"))
os.environ["LOCALAPPDATA"] = str(sandbox)

try:
    from core.daily_workforce import ensure_daily_workforce
    from core.decision_bridge import export_decision_handoff
    from core.decision_center import EMPLOYEES, decision_snapshot, refresh_decision_center
    from integrations.bridge import configure_bridge

    workforce = ensure_daily_workforce()
    report = refresh_decision_center()
    cached = decision_snapshot()

    if report.get("schema") != "kazuizhi-autonomous-decision/v1":
        raise AssertionError(f"Unexpected decision schema: {report.get('schema')}")
    if len(report.get("employee_reports", [])) != 8:
        raise AssertionError("Decision center must contain all eight AI employee reports")
    actual_agents = {item.get("agent") for item in report["employee_reports"]}
    if actual_agents != set(EMPLOYEES):
        raise AssertionError(f"Employee report mismatch: {actual_agents}")

    summary = report.get("manager_summary", {})
    if summary.get("planned", 0) < workforce.get("planned", 0):
        raise AssertionError(f"Manager summary lost scheduled work: {summary} vs {workforce}")
    if not report.get("manager_decisions"):
        raise AssertionError("Manager report must contain at least one evidence-based decision")
    if report.get("chatgpt_handoff", {}).get("status") != "ready_for_strategy_review":
        raise AssertionError("ChatGPT strategy handoff is not ready")
    if "资金" not in report.get("guardrails", {}).get("financial", ""):
        raise AssertionError("Financial manual-only boundary missing")
    if "回执" not in report.get("guardrails", {}).get("external_publish", ""):
        raise AssertionError("External publication truth boundary missing")
    if cached.get("date") != report.get("date"):
        raise AssertionError("Decision snapshot did not persist today's report")

    bridge_base = sandbox / "drive"
    bridge = configure_bridge({"root": str(bridge_base)})
    if bridge.get("status") != "connected":
        raise AssertionError(f"Test bridge did not connect: {bridge}")
    exported = export_decision_handoff(report)
    if not exported.get("exported"):
        raise AssertionError(f"Decision handoff did not export: {exported}")
    handoff_path = Path(exported["path"])
    payload = json.loads(handoff_path.read_text(encoding="utf-8"))
    if payload.get("schema") != "kazuizhi-chatgpt-strategy-handoff/v1":
        raise AssertionError("ChatGPT bridge handoff schema mismatch")
    if payload.get("decision_center", {}).get("date") != report.get("date"):
        raise AssertionError("Exported handoff does not contain the current manager report")

    ui = (SRC / "web" / "decision_center.js").read_text(encoding="utf-8")
    required_ui = (
        "AI 自主决策中心 V1", "8 个员工日报", "经理判断",
        "ChatGPT 战略交接", "/api/r7/decision-center", "每 5 分钟",
        "decisionOpenWorkflow", "decisionActivate", "data-agent-name",
        "decision-evidence-open", "decision-reports-open", "decision-bridge-open",
        "团队协作", "decision-shared-context", "data-team-page",
        "查看这个员工今天的任务", "查看任务依据", "查看全部任务",
    )
    for token in required_ui:
        if token not in ui:
            raise AssertionError(f"Decision center UI missing contract token: {token}")

    if "decision-planned':'today'" not in ui or "decision-queued':'queued'" not in ui or "decision-failed':'failed'" not in ui:
        raise AssertionError("Decision KPI cards are not wired to real workflow filters")
    if "addEventListener('click'" not in ui or "decision-refresh" not in ui:
        raise AssertionError("Decision center refresh/control click handlers missing")

    server = (SRC / "backend" / "server.py").read_text(encoding="utf-8")
    # R7 GET routes are intentionally lazy now so a normal R7 page cannot
    # trigger the R8 ADB adapter. Accept the legacy route-dict form only for
    # backward source compatibility, but require the decision endpoint itself.
    legacy_get = '"/api/r7/decision-center": decision_snapshot()' in server
    lazy_get = 'if path == "/api/r7/decision-center":' in server and 'return decision_snapshot()' in server
    if not (legacy_get or lazy_get):
        raise AssertionError("Decision center GET API route missing")
    if '"/api/r7/decision-center/refresh"' not in server:
        raise AssertionError("Decision center refresh API route missing")

    run = (SRC / "run.py").read_text(encoding="utf-8")
    for token in ("tick % 20 == 0", "refresh_decision_center()", "export_decision_handoff(manager_report)"):
        if token not in run:
            raise AssertionError(f"Manager refresh/bridge loop missing: {token}")

    print("PASS: autonomous decision center, eight employee reports, manager decisions, interactive drill-down controls, team collaboration view, ChatGPT bridge handoff and guardrails")
finally:
    shutil.rmtree(sandbox, ignore_errors=True)
