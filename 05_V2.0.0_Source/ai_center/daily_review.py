"""Daily autonomous review: summary, learning memory and next-day scheduling."""

from analytics.operation_summary import build_summary
from core.storage import now_iso, read_json, write_json
from memory.memory_store import get_memory, remember
from planning.tomorrow_plan import build_plan
from records.history_store import append_review


def _analyse(summary):
    if summary["status"] == "not_connected":
        return (
            ["真实经营数据尚未接入，无法判断订单、用户和收入变化。"],
            ["继续整理公开需求信号，同时推进只读经营数据接入；不得用推测数字代替真实订单。"],
        )
    problems = []
    opportunities = ["继续跟踪已验证指标，并让下一日任务优先处理有真实结果回执的增长动作。"]
    return problems, opportunities


def _enqueue_plan(plan):
    """Schedule tomorrow's non-financial tasks once; create_job enforces finance policy."""
    from core.r7_engine import create_job, list_jobs

    existing = {(item.get("title"), str(item.get("due_at") or "")[:10]) for item in list_jobs().get("items", [])}
    scheduled = []
    due_day = str(plan.get("date") or "")
    due_at = f"{due_day}T08:00:00" if due_day else ""
    for task in plan.get("tasks", []):
        title = str(task.get("title") or "").strip()
        if not title or (title, due_day) in existing:
            continue
        job = create_job({"kind": "manual_task", "title": title, "due_at": due_at})
        scheduled.append(job["id"])
    return scheduled


def generate_review(snapshot=None):
    summary = build_summary(snapshot)
    problems, opportunities = _analyse(summary)
    plan = build_plan(summary, problems, opportunities)
    review = {
        "id": now_iso(),
        "generated_at": now_iso(),
        "status": "generated",
        "summary": summary,
        "problems": problems,
        "opportunities": opportunities,
        "tomorrow_plan": plan,
        "memory_entries": len(get_memory().get("entries", [])),
        "source": "local_verified_data",
        "learning_mode": "audited_memory_and_plan_optimization",
    }
    write_json("reviews/latest_review.json", review)
    write_json("plans/latest_plan.json", plan)
    append_review(review)

    evidence = f"review_id={review['id']}; business_status={summary.get('status')}"
    remember("每日自动复盘", opportunities[0] if opportunities else "今日无新增增长机会，保持当前已验证策略。", evidence)
    review["scheduled_job_ids"] = _enqueue_plan(plan)
    write_json("reviews/latest_review.json", review)
    return review


def latest_review():
    return read_json("reviews/latest_review.json", {
        "status": "not_generated",
        "message": "尚未生成今日复盘；自主运行模式会在每日复盘窗口自动生成。",
    })


def latest_plan():
    return read_json("plans/latest_plan.json", {
        "status": "not_generated",
        "message": "每日自动复盘后会生成并排入次日非资金任务。",
        "tasks": [],
    })

