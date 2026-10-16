"""Daily review orchestrator for summary, analysis, plan, history and memory."""

from analytics.operation_summary import build_summary
from core.storage import now_iso, read_json, write_json
from memory.memory_store import get_memory
from planning.tomorrow_plan import build_plan
from records.history_store import append_review


def verified_operational_issues():
    """Collect persisted operational exceptions without launching remote work."""
    issues = []
    try:
        from core.phase1_acceptance import status as acceptance_status
        acceptance = acceptance_status()
        checks = acceptance.get("checks") or {}
        if not checks.get("uptime_pass", True):
            issues.append(
                f"第一阶段在线率 {acceptance.get('uptime_percent')}%，低于 {acceptance.get('thresholds', {}).get('uptime_percent')}% 要求。"
            )
        if not checks.get("silent_gap_pass", True):
            issues.append(
                f"第一阶段最大静默 {int(acceptance.get('max_gap_seconds') or 0)} 秒，超过 {int(acceptance.get('thresholds', {}).get('max_silent_gap_seconds') or 900)} 秒。"
            )
        if acceptance.get("status") != "passed" and not checks.get("duration_complete", False):
            issues.append(f"第一阶段连续运行验收仍在进行，当前进度 {acceptance.get('progress_percent')}%。")
    except (OSError, ValueError, TypeError, KeyError):
        issues.append("第一阶段验收状态暂时无法读取，不能按无异常处理。")

    try:
        from promotion.ai_production_center import dashboard as content_dashboard
        tasks = content_dashboard().get("tasks") or []
        pending = [row for row in tasks if str(row.get("status") or "") in {"待本地执行器", "执行失败", "待总控确认"}]
        if pending:
            issues.append(f"AI内容中心仍有 {len(pending)} 项待执行、待确认或失败任务，需要继续恢复闭环。")
    except (OSError, ValueError, TypeError, KeyError):
        issues.append("AI内容中心积压状态暂时无法读取。")

    try:
        from promotion.search_growth import status as search_growth_status
        blockers = ((search_growth_status().get("latest_audit") or {}).get("blockers") or [])
        if blockers:
            issues.append(f"官网技术SEO仍有 {len(blockers)} 项已验证问题：{'；'.join(str(x) for x in blockers[:3])}。")
    except (OSError, ValueError, TypeError, KeyError):
        issues.append("官网技术SEO审计状态暂时无法读取。")
    return issues


def _analyse(summary):
    if summary["status"] == "not_connected":
        return (
            ["真实经营数据尚未接入，无法判断订单、用户和收入变化。"],
            ["先完成只读数据接入，再用真实转化结果选择增长重点。"],
        )
    problems = verified_operational_issues()
    opportunities = ["继续跟踪已验证指标，并为每项增长动作保留结果回执。"]
    return problems, opportunities


def generate_review(snapshot=None):
    summary = build_summary(snapshot)
    problems, opportunities = _analyse(summary)
    review = {
        "id": now_iso(),
        "generated_at": now_iso(),
        "status": "generated",
        "summary": summary,
        "problems": problems,
        "opportunities": opportunities,
        "tomorrow_plan": build_plan(summary, problems, opportunities),
        "memory_entries": len(get_memory().get("entries", [])),
        "source": "local_verified_data",
    }
    write_json("reviews/latest_review.json", review)
    write_json("plans/latest_plan.json", review["tomorrow_plan"])
    append_review(review)
    return review


def latest_review():
    return read_json("reviews/latest_review.json", {
        "status": "not_generated",
        "message": "尚未生成今日复盘。点击“生成今日复盘”开始。",
    })


def latest_plan():
    return read_json("plans/latest_plan.json", {
        "status": "not_generated",
        "message": "生成今日复盘后会得到可审核的明日计划。",
        "tasks": [],
    })

