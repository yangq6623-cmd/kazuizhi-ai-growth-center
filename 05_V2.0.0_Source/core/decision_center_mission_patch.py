"""Attach shared Mission/R8 outcomes to the R7 decision-center snapshot."""
from __future__ import annotations

from core import decision_center
from core.autonomous_ops import feedback_for_r7
from core.storage import write_json

_INSTALLED = False
_ORIGINAL_REFRESH = None
_ORIGINAL_SNAPSHOT = None


def _augment(report):
    if not isinstance(report, dict):
        return report
    feedback = feedback_for_r7()
    report["mission_feedback"] = feedback
    active_id = str(feedback.get("active_mission_id") or "")
    active = next((item for item in feedback.get("items", []) if item.get("mission_id") == active_id), None)
    # This is intentionally read from the persisted shared Mission store rather
    # than derived from the daily queue.  A Mission can be active while all of
    # today's jobs are merely scheduled for later, and that must remain visible
    # to ChatGPT and the owner UI as the same operational fact.
    report["active_mission"] = active
    handoff = report.setdefault("chatgpt_handoff", {})
    handoff["mission_continuity"] = (
        "ChatGPT在同一Mission中读取R7分析与R8真实执行结果；真实发布、咨询和订单结果回流后，"
        "用于下一轮加码/保持/减少/停止判断。"
    )
    handoff["mission_decision_contract"] = {
        "schema": "kazuizhi-mission-decision/v1",
        "kind": "mission_decision",
        "allowed_actions": ["continue", "stop", "create_mission"],
        "instruction": (
            "当真实证据足够支持下一步时，可返回kind=mission_decision。continue表示在同一Mission继续下一轮；"
            "stop表示停止当前低收益非资金执行；create_mission必须提供region/service/title/evidence/goal，"
            "用于新建下一轮经营Mission。不得绕过老板成片审核、账号验证、资金和合规边界。"
        ),
    }
    questions = handoff.setdefault("questions", [])
    mission_question = "当前Mission的R8执行与真实结果是否支持继续、加码、减少或停止？"
    if mission_question not in questions:
        questions.append(mission_question)
    return report


def _refresh():
    report = _augment(_ORIGINAL_REFRESH())
    write_json(decision_center.DECISION_PATH, report)
    return report


def _snapshot():
    report = _augment(_ORIGINAL_SNAPSHOT())
    write_json(decision_center.DECISION_PATH, report)
    return report


def install():
    global _INSTALLED, _ORIGINAL_REFRESH, _ORIGINAL_SNAPSHOT
    if _INSTALLED:
        return
    _ORIGINAL_REFRESH = decision_center.refresh_decision_center
    _ORIGINAL_SNAPSHOT = decision_center.decision_snapshot
    decision_center.refresh_decision_center = _refresh
    decision_center.decision_snapshot = _snapshot
    _INSTALLED = True


install()
