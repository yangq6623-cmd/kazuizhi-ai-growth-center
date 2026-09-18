"""Manager-level autonomous analysis for the R7 AI workforce.

The decision center turns truthful local execution records into eight employee
reports, a manager summary and low-risk strategy proposals. It never fabricates
external publication/results and never executes financial actions.
"""

from datetime import datetime

from analytics.business_metrics import build_analytics
from core.storage import now_iso, read_json, write_json


DECISION_PATH = "r7/decision_center.json"
EMPLOYEES = (
    "市场情报员", "SEO/GEO 增长员", "内容运营员", "社媒运营员",
    "短视频运营员", "本地增长员", "用户转化员", "数据复盘员",
)


def _date_key(value):
    if not value:
        return ""
    try:
        return str(datetime.fromisoformat(str(value)).astimezone().date())
    except (ValueError, TypeError):
        return str(value)[:10]


def _today_relevant(job, today):
    return any(_date_key(job.get(key)) == today for key in ("created_at", "due_at", "updated_at"))


def _job_time(job):
    return job.get("updated_at") or job.get("created_at") or job.get("due_at")


def _unique(values, limit=6):
    result = []
    seen = set()
    for value in values:
        text = str(value or "").strip()
        if not text or text in seen:
            continue
        seen.add(text)
        result.append(text[:240])
        if len(result) >= limit:
            break
    return result


def _result_evidence(job):
    result = job.get("result") if isinstance(job.get("result"), dict) else {}
    values = []
    for key in ("summary", "outcome", "headline", "scope", "source_note"):
        if result.get(key):
            values.append(result.get(key))
    for key in ("key_findings", "top_needs", "top_regions", "recommendations", "next_actions"):
        raw = result.get(key)
        if isinstance(raw, list):
            for item in raw:
                if isinstance(item, str):
                    values.append(item)
                elif isinstance(item, dict):
                    values.append(item.get("title") or item.get("keyword") or item.get("name") or item.get("region"))
    return _unique(values, 5)


def _agent_recommendation(agent, planned, completed, queued, running, failed, evidence):
    if failed:
        return f"先处理 {failed} 项失败记录，确认原因后再扩大同类工作量。"
    if running:
        return "继续当前执行，完成后依据真实结果决定是否加码下一轮。"
    if queued:
        return f"按计划继续消化 {queued} 项待执行工作，不需要老板逐项干预。"
    if planned and completed >= planned:
        return "今日计划已完成；保留有效做法，明日根据结果继续优化，不机械重复。"
    if evidence:
        return "已有可核验结果，下一轮优先沿着已验证发现继续测试和优化。"
    return "当前没有足够新证据，不扩大结论；等待下一轮真实数据和执行结果。"


def _employee_report(agent, jobs, today):
    items = [job for job in jobs if job.get("agent") == agent and _today_relevant(job, today)]
    items.sort(key=lambda item: str(_job_time(item) or ""), reverse=True)
    planned = len([job for job in items if job.get("state") != "cancelled"])
    completed_items = [job for job in items if job.get("state") == "completed"]
    queued = len([job for job in items if job.get("state") == "queued"])
    running = len([job for job in items if job.get("state") == "running"])
    failed = len([job for job in items if job.get("state") == "failed"])
    evidence = []
    for job in completed_items[:5]:
        evidence.extend(_result_evidence(job))
    evidence = _unique(evidence, 6)
    if failed:
        status = "异常"
    elif running:
        status = "工作中"
    elif queued:
        status = "待执行"
    elif planned and len(completed_items) >= planned:
        status = "今日已完成"
    else:
        status = "空闲"
    latest = items[0] if items else None
    return {
        "agent": agent,
        "status": status,
        "planned": planned,
        "completed": len(completed_items),
        "queued": queued,
        "running": running,
        "failed": failed,
        "completion_rate": round(len(completed_items) * 100 / planned) if planned else 0,
        "latest_task": latest.get("title") if latest else None,
        "latest_at": _job_time(latest) if latest else None,
        "evidence": evidence,
        "judgement": _agent_recommendation(agent, planned, len(completed_items), queued, running, failed, evidence),
    }


def _public_signal_count(jobs):
    total = 0
    for job in jobs:
        result = job.get("result") if isinstance(job.get("result"), dict) else {}
        value = result.get("public_signal_count")
        if isinstance(value, (int, float)) and value > 0:
            total += int(value)
    return total


def _manager_decisions(reports, jobs, business_status):
    total_planned = sum(item["planned"] for item in reports)
    total_completed = sum(item["completed"] for item in reports)
    total_failed = sum(item["failed"] for item in reports)
    total_queued = sum(item["queued"] for item in reports)
    ratio = round(total_completed * 100 / total_planned) if total_planned else 0
    signals = _public_signal_count(jobs)
    decisions = []

    if total_failed:
        decisions.append({
            "level": "high", "action": "先恢复失败任务，再扩大同类工作量",
            "reason": f"今日员工报告中仍有 {total_failed} 项失败记录，需要先确认失败原因。",
            "execution": "automatic_recovery_with_guardrails",
        })
    if signals:
        decisions.append({
            "level": "medium", "action": "保持市场情报 → SEO/GEO → 内容的联动",
            "reason": f"今日已记录 {signals} 条可核验公开需求信号，可继续用于下一轮关键词和内容方向校准。",
            "execution": "autonomous_non_financial",
        })
    if business_status == "verified":
        decisions.append({
            "level": "high", "action": "继续用真实经营数据校准增长优先级",
            "reason": "生产经营聚合数据处于已验证状态，用户增长与订单转化判断应优先使用真实数据。",
            "execution": "autonomous_read_only_analysis",
        })
    if total_planned and ratio >= 70:
        decisions.append({
            "level": "normal", "action": "保留当前有效节奏，并把更多资源给表现更好的方向",
            "reason": f"今日计划完成度为 {ratio}%，可以在不增加资金风险的前提下继续优化分配。",
            "execution": "autonomous_non_financial",
        })
    elif total_planned and total_queued:
        decisions.append({
            "level": "normal", "action": "优先消化当前待执行任务，不盲目增加任务量",
            "reason": f"今日仍有 {total_queued} 项待执行，先完成现有验证闭环再决定是否加码。",
            "execution": "autonomous_non_financial",
        })
    if not decisions:
        decisions.append({
            "level": "normal", "action": "维持基础排班并等待更多真实结果",
            "reason": "当前证据不足以支持明显加码或缩减，避免为了显得忙而制造无效任务。",
            "execution": "autonomous_non_financial",
        })
    return decisions[:5]


def refresh_decision_center():
    """Build and persist one current manager report from truthful local evidence."""
    from core.r7_engine import engine_status, list_jobs

    now = datetime.now().astimezone()
    today = str(now.date())
    jobs = list_jobs().get("items", [])
    today_jobs = [job for job in jobs if _today_relevant(job, today)]
    reports = [_employee_report(agent, jobs, today) for agent in EMPLOYEES]
    engine = engine_status()
    analytics = build_analytics()
    business_status = analytics.get("status")
    planned = sum(item["planned"] for item in reports)
    completed = sum(item["completed"] for item in reports)
    queued = sum(item["queued"] for item in reports)
    running = sum(item["running"] for item in reports)
    failed = sum(item["failed"] for item in reports)
    completion_rate = round(completed * 100 / planned) if planned else 0
    decisions = _manager_decisions(reports, today_jobs, business_status)
    proposals = [
        {"agent": item["agent"], "proposal": item["judgement"], "evidence": item["evidence"][:3]}
        for item in reports if item["planned"] or item["evidence"] or item["failed"]
    ]
    report = {
        "schema": "kazuizhi-autonomous-decision/v1",
        "generated_at": now_iso(),
        "date": today,
        "status": "ready",
        "manager_summary": {
            "headline": f"8 个 AI 员工今日计划 {planned} 项，已完成 {completed} 项，完成度 {completion_rate}%",
            "planned": planned,
            "completed": completed,
            "queued": queued,
            "running": running,
            "failed": failed,
            "human_required": int(engine.get("jobs", {}).get("human_required", 0)),
            "completion_rate": completion_rate,
            "business_data_status": business_status,
        },
        "employee_reports": reports,
        "manager_decisions": decisions,
        "employee_proposals": proposals,
        "chatgpt_handoff": {
            "status": "ready_for_strategy_review",
            "purpose": "供 ChatGPT 总控制大脑做跨员工复盘、解释原因并形成下一阶段策略。",
            "questions": [
                "哪些方向应该加码、保持、减少或停止？",
                "员工之间的发现是否互相印证或存在冲突？",
                "下一工作日的资源和任务优先级应如何调整？",
            ],
        },
        "guardrails": {
            "financial": "退款、提现、结算、改价、付款、转账等资金事项永远交平台人工处理。",
            "external_publish": "没有真实平台连接、发布回执或链接时，只能记为草稿/待发布，不能记为已发布。",
            "self_modification": "只允许调整策略、计划、模板和优先级；不得自行修改程序代码或安全边界。",
        },
    }
    write_json(DECISION_PATH, report)
    return report


def decision_snapshot():
    data = read_json(DECISION_PATH, {})
    if not data or data.get("date") != str(datetime.now().astimezone().date()):
        return refresh_decision_center()
    return data
