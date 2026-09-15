"""Daily review orchestrator for summary, analysis, plan, history and memory."""

from analytics.operation_summary import build_summary
from core.storage import now_iso, read_json, write_json
from memory.memory_store import get_memory
from planning.tomorrow_plan import build_plan
from records.history_store import append_review


def _analyse(summary):
    if summary["status"] == "not_connected":
        return (
            ["真实经营数据尚未接入，无法判断订单、用户和收入变化。"],
            ["先完成只读数据接入，再用真实转化结果选择增长重点。"],
        )
    problems = []
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

