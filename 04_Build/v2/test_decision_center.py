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
    from core.decision_center import EMPLOYEES, decision_snapshot, refresh_decision_center

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

    ui = (SRC / "web" / "decision_center.js").read_text(encoding="utf-8")
    for token in (
        "AI 自主决策中心 V1", "8 个员工日报", "经理判断",
        "ChatGPT 战略交接", "/api/r7/decision-center", "每 5 分钟自动汇总",
    ):
        if token not in ui:
            raise AssertionError(f"Decision center UI missing contract token: {token}")

    server = (SRC / "backend" / "server.py").read_text(encoding="utf-8")
    if '"/api/r7/decision-center": decision_snapshot()' not in server:
        raise AssertionError("Decision center GET API route missing")
    if '"/api/r7/decision-center/refresh"' not in server:
        raise AssertionError("Decision center refresh API route missing")

    run = (SRC / "run.py").read_text(encoding="utf-8")
    if "tick % 20 == 0" not in run or "refresh_decision_center()" not in run:
        raise AssertionError("Five-minute manager refresh loop missing")

    print("PASS: 8 employee reports, R7 manager decisions, ChatGPT strategy handoff, finance/publishing guardrails and five-minute refresh")
finally:
    shutil.rmtree(sandbox, ignore_errors=True)
