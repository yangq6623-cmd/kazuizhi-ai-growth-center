"""Daily AI workforce schedule for R7.

Keeps the eight non-financial AI roles on a truthful, time-based operating plan.
The schedule creates local queued jobs only; it never performs payment/refund/
settlement actions and never claims external publication without an integration.
"""

import uuid
from datetime import datetime, time

from core.storage import now_iso, read_json, write_json


SCHEDULE_STATE = "r7/workforce_schedule.json"

# A full but purposeful day: research -> content -> distribution prep -> conversion
# analysis -> review. External-facing roles prepare drafts/evidence only until a real
# publishing connector is available.
DAILY_TEMPLATE = (
    ("08:00", "market-am", "市场情报员", "market", "扫描涟水县本地维修公开需求信号并整理上午重点"),
    ("08:20", "seo-am", "SEO/GEO 增长员", "seo", "更新涟水本地维修关键词与 SEO/GEO 上午优化草稿"),
    ("08:40", "content-am", "内容运营员", "content", "生成上午维修知识与常见问题内容草稿"),
    ("09:00", "social-am", "社媒运营员", "content", "准备上午论坛、社区与博客发布草稿和标题清单"),
    ("09:20", "video-am", "短视频运营员", "video", "生成上午本地维修短视频选题与脚本草稿"),
    ("09:45", "local-am", "本地增长员", "local", "梳理涟水县重点区域、服务需求与本地增长动作"),
    ("10:15", "conversion-am", "用户转化员", "conversion", "分析已验证用户与订单数据并检查上午转化机会"),
    ("10:45", "review-am", "数据复盘员", "review", "复核上午执行结果并调整当天后续工作优先级"),
    ("11:15", "market-mid", "市场情报员", "market", "二次扫描本地公开需求信号并更新需求变化"),
    ("13:30", "seo-pm", "SEO/GEO 增长员", "geo", "生成下午 GEO 本地服务覆盖与搜索优化草稿"),
    ("14:00", "content-pm", "内容运营员", "content", "生成下午维修案例结构与用户问答内容草稿"),
    ("14:30", "social-pm", "社媒运营员", "content", "准备下午论坛、社区与博客内容包并记录待发布清单"),
    ("15:00", "video-pm", "短视频运营员", "video", "生成下午短视频脚本、标题与封面文案草稿"),
    ("15:30", "local-pm", "本地增长员", "local", "复核本地服务区域与推广机会并整理下一步动作"),
    ("16:00", "conversion-pm", "用户转化员", "conversion", "复核今日用户增长、维修需求与订单转化数据"),
    ("16:30", "market-close", "市场情报员", "market", "第三次扫描本地需求信号并形成日终市场摘要"),
    ("17:00", "seo-close", "SEO/GEO 增长员", "seo", "根据今日需求信号优化下一轮 SEO/GEO 关键词与内容方向"),
    ("17:30", "content-close", "内容运营员", "content", "整理明日可继续使用的内容素材、标题与草稿清单"),
)


def _due_at(day, hhmm):
    hour, minute = (int(part) for part in hhmm.split(":", 1))
    now = datetime.now().astimezone()
    return datetime.combine(day, time(hour, minute), tzinfo=now.tzinfo).isoformat(timespec="seconds")


def _recent_failed_types():
    learning = read_json("r7/learning.json", {"items": []})
    return {
        str(item.get("task_type") or "")
        for item in learning.get("items", [])[:30]
        if item.get("state") == "failed"
    }


def _adaptive_template(day):
    """Add a small number of recovery/optimization jobs based on recent outcomes."""
    failed = _recent_failed_types()
    extra = []
    if failed & {"seo", "geo", "content", "video"}:
        extra.append(("12:00", "adaptive-content-recovery", "SEO/GEO 增长员", "seo",
                      "检查近期内容增长失败原因并使用已验证本地关键词重新优化草稿"))
    if failed & {"market", "local", "conversion"}:
        extra.append(("17:15", "adaptive-growth-recheck", "数据复盘员", "review",
                      "根据近期失败记录重新评估增长优先级并更新后续执行建议"))
    return extra[:2]


def ensure_daily_workforce():
    """Ensure today's complete, time-spread workforce plan exists exactly once."""
    # Import here to avoid a module cycle during R7 engine startup.
    from core import r7_engine

    now = datetime.now().astimezone()
    today = now.date()
    today_key = str(today)
    template = list(DAILY_TEMPLATE) + _adaptive_template(today)

    with r7_engine.LOCK:
        if r7_engine.audit_history()["integrity"] != "verified":
            raise ValueError("审计记录校验失败，已暂停自动排班")
        data = r7_engine._store()
        existing = {
            str(job.get("schedule_key"))
            for job in data.get("items", [])
            if job.get("schedule_date") == today_key and job.get("schedule_key")
        }
        created = []
        for hhmm, key, agent, task_type, title in template:
            if key in existing:
                continue
            stamp = now_iso()
            job = {
                "id": uuid.uuid4().hex,
                "kind": "manual_task",
                "title": title,
                "mode": "local",
                "agent": agent,
                "task_type": task_type,
                "risk": "non_financial",
                "execution": "autonomous",
                "state": "queued",
                "progress": 0,
                "completed_steps": 0,
                "total_steps": 1,
                "due_at": _due_at(today, hhmm),
                "created_at": stamp,
                "updated_at": stamp,
                "approved_by": "autonomy_policy",
                "result": None,
                "error": None,
                "retry_count": 0,
                "schedule_key": key,
                "schedule_date": today_key,
                "schedule_time": hhmm,
                "schedule_source": "daily_workforce",
            }
            data["items"].insert(0, job)
            created.append(job)
            existing.add(key)
        if created:
            write_json(r7_engine.JOBS, data)
            for job in created:
                r7_engine._audit(
                    "job_auto_scheduled",
                    job["id"],
                    "daily_workforce",
                    {"agent": job["agent"], "task_type": job["task_type"], "due_at": job["due_at"]},
                )

    state = read_json(SCHEDULE_STATE, {"dates": []})
    dates = [value for value in state.get("dates", []) if value != today_key]
    dates.append(today_key)
    state.update(
        dates=dates[-31:],
        date=today_key,
        planned=len(template),
        created=len(created),
        updated_at=now_iso(),
        policy="全天分时执行；非资金自动执行；资金事项不进入自动排班",
    )
    write_json(SCHEDULE_STATE, state)
    return {"date": today_key, "planned": len(template), "created": len(created)}
