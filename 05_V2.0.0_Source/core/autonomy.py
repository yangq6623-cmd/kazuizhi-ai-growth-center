"""Autonomous operations policy for R7.

Non-financial operating tasks run automatically. Financial or settlement related
items are recorded for platform staff and never executed by R7.
"""

from datetime import date, datetime, timedelta

from analytics.business_metrics import build_analytics
from core.storage import now_iso, read_json, write_json

FINANCIAL_TERMS = (
    "支付", "付款", "收款", "退款", "退费", "返款", "提现", "结算", "改价", "调价",
    "余额", "充值", "资金", "打款", "转账", "划转", "佣金", "赔付", "补贴", "发票付款",
)

AGENT_RULES = (
    (("市场", "需求", "维修数据", "公开数据", "同行", "竞品", "涟水"), "市场情报员", "market"),
    (("SEO", "seo", "关键词", "搜索"), "SEO/GEO 增长员", "seo"),
    (("GEO", "geo", "本地优化"), "SEO/GEO 增长员", "geo"),
    (("短视频", "视频", "脚本"), "短视频运营员", "video"),
    (("内容", "文案", "广告"), "内容运营员", "content"),
    (("本地", "区域", "服务范围"), "本地增长员", "local"),
    (("转化", "咨询", "用户"), "用户转化员", "conversion"),
    (("复盘", "总结", "日报", "明日计划"), "数据复盘员", "review"),
    (("体检", "诊断", "系统"), "系统巡检员", "diagnostics"),
)


def is_financial(text):
    lowered = str(text or "").lower()
    for phrase in ("非资金", "不涉及资金", "无需资金", "无资金操作", "不含资金"):
        lowered = lowered.replace(phrase.lower(), "")
    return any(term.lower() in lowered for term in FINANCIAL_TERMS)


def classify(title):
    title = str(title or "").strip()
    if is_financial(title):
        return {
            "risk": "financial",
            "execution": "platform_manual",
            "agent": "平台人工客服",
            "task_type": "financial",
            "auto_approve": False,
        }
    for keywords, agent, task_type in AGENT_RULES:
        if any(word.lower() in title.lower() for word in keywords):
            return {
                "risk": "non_financial",
                "execution": "autonomous",
                "agent": agent,
                "task_type": task_type,
                "auto_approve": True,
            }
    return {
        "risk": "non_financial",
        "execution": "autonomous",
        "agent": "运营协调员",
        "task_type": "general",
        "auto_approve": True,
    }


def record_human_intervention(job):
    data = read_json("r7/human_interventions.json", {"items": []})
    item = {
        "id": job["id"],
        "created_at": now_iso(),
        "title": job["title"],
        "reason": "涉及资金或结算，R7 仅记录，不执行。请到小程序/平台后台由人工处理。",
        "status": "待平台人工处理",
        "source": "R7 自动识别",
    }
    data.setdefault("items", []).insert(0, item)
    data["items"] = data["items"][:200]
    write_json("r7/human_interventions.json", data)
    return item


def human_interventions():
    return read_json("r7/human_interventions.json", {"items": []})


def execute_autonomous(job):
    """Execute a truthful local task using only capabilities already available locally."""
    task_type = job.get("task_type") or classify(job.get("title"))["task_type"]
    title = job.get("title", "")

    if task_type == "diagnostics":
        from integrations.manager import system_diagnostics
        return {"task_type": task_type, "summary": system_diagnostics()["summary"]}

    if task_type == "review":
        from ai_center.daily_review import generate_review
        review = generate_review(None)
        return {"task_type": task_type, "headline": review.get("summary", {}).get("headline", "复盘已完成")}

    if task_type == "market":
        from operations.workspace import demand_insights, generate_calendar
        insight = demand_insights()
        calendar = generate_calendar({"region": "涟水", "service": "本地维修与生活任务"})
        return {
            "task_type": task_type,
            "scope": "涟水县及淮安市本地维修公开信号",
            "public_signal_count": insight.get("public_signal_count", 0),
            "top_needs": insight.get("top_needs", []),
            "top_regions": insight.get("top_regions", []),
            "calendar_days": len(calendar.get("items", [])),
            "limitation": "仅基于本机已接入/历史公开信号整理；未接入实时外部数据源时不虚构实时市场量。",
        }

    if task_type in {"seo", "geo", "content", "video"}:
        from promotion.content_center import generate_ad, generate_geo, generate_seo, generate_video
        payload = {
            "region": "涟水",
            "service": "本地维修服务",
            "keyword": "涟水本地维修服务",
            "audience": "涟水县有维修与生活服务需求的本地用户",
            "evidence": "",
        }
        if task_type == "seo":
            record = generate_seo(payload)
        elif task_type == "geo":
            record = generate_geo(payload)
        elif task_type == "video":
            record = generate_video(payload)
        else:
            record = generate_ad(payload)
        return {"task_type": task_type, "draft_id": record.get("id"), "kind": record.get("kind"), "status": "草稿已自动生成"}

    if task_type in {"local", "conversion", "general"}:
        from operations.workspace import command_center, demand_insights
        center = command_center()
        insight = demand_insights()
        return {
            "task_type": task_type,
            "headline": title,
            "business_status": center.get("business_status"),
            "recommendations": center.get("recommendations", [])[:5],
            "public_signal_count": insight.get("public_signal_count", 0),
            "note": "已完成本机可验证范围内的自动分析；需要实时经营数据的结论将在只读数据接入后增强。",
        }

    return {"task_type": task_type, "headline": title, "status": "自动任务已处理"}


def learn_from_job(job):
    """Persist execution lessons without allowing self-modifying code."""
    data = read_json("r7/learning.json", {"items": [], "policy_version": 1})
    item = {
        "at": now_iso(),
        "job_id": job["id"],
        "title": job["title"],
        "task_type": job.get("task_type"),
        "state": job.get("state"),
        "agent": job.get("agent"),
        "result": job.get("result"),
        "error": job.get("error"),
        "lesson": "成功任务保留策略；失败任务降低相同动作优先级并记录原因，下一轮优先选择可验证、低风险动作。" if job.get("state") == "completed" else "记录失败原因，后续计划优先使用替代低风险动作。",
        "guardrail": "仅优化策略、计划、模板和优先级；禁止自行修改程序代码或资金安全边界。",
    }
    data.setdefault("items", []).insert(0, item)
    data["items"] = data["items"][:300]
    write_json("r7/learning.json", data)
    refresh_tomorrow_plan(data)
    return item


def learning_status():
    data = read_json("r7/learning.json", {"items": [], "policy_version": 1})
    items = data.get("items", [])
    completed = sum(1 for x in items[:50] if x.get("state") == "completed")
    failed = sum(1 for x in items[:50] if x.get("state") == "failed")
    return {
        "policy_version": data.get("policy_version", 1),
        "recent_samples": min(len(items), 50),
        "recent_completed": completed,
        "recent_failed": failed,
        "latest": items[0] if items else None,
        "mode": "strategy_learning_only",
    }


def refresh_tomorrow_plan(learning=None):
    learning = learning or read_json("r7/learning.json", {"items": []})
    recent = learning.get("items", [])[:20]
    failed_types = {x.get("task_type") for x in recent if x.get("state") == "failed"}
    business = build_analytics()
    tasks = [
        {"title": "扫描涟水县本地维修公开需求信号", "agent": "市场情报员", "execution": "autonomous", "risk": "non_financial"},
        {"title": "生成涟水本地维修 SEO/GEO 内容草稿", "agent": "SEO/GEO 增长员", "execution": "autonomous", "risk": "non_financial"},
        {"title": "复盘今日执行结果并更新运营记忆", "agent": "数据复盘员", "execution": "autonomous", "risk": "non_financial"},
    ]
    if business.get("status") == "verified":
        tasks.insert(1, {"title": "分析已验证订单与用户变化并调整增长优先级", "agent": "用户转化员", "execution": "autonomous", "risk": "non_financial"})
    if "seo" in failed_types:
        tasks.append({"title": "检查 SEO 自动草稿失败原因并使用本地关键词模板重试", "agent": "SEO/GEO 增长员", "execution": "autonomous", "risk": "non_financial"})
    plan = {
        "date": str(date.today() + timedelta(days=1)),
        "saved_at": now_iso(),
        "status": "auto_ready",
        "tasks": tasks,
        "execution_policy": "非资金任务自动执行；资金事项仅记录并交平台人工处理。",
        "learning_policy": "根据历史结果调整任务优先级与模板，不自行修改程序代码。",
    }
    write_json("plans/latest_plan.json", plan)
    return plan


def dispatch_due_plan():
    """Turn an auto-ready learned plan into real R7 jobs once its date arrives."""
    plan = read_json("plans/latest_plan.json", {})
    plan_date = str(plan.get("date") or "")
    if plan.get("status") != "auto_ready" or not plan_date or plan_date > str(date.today()):
        return {"dispatched": 0, "date": plan_date or None}
    state = read_json("r7/plan_dispatch.json", {"dates": []})
    if plan_date in state.get("dates", []):
        return {"dispatched": 0, "date": plan_date, "already_dispatched": True}

    from core.r7_engine import create_job
    created = []
    for task in plan.get("tasks", [])[:20]:
        title = str(task.get("title") or "").strip()
        if not title or task.get("risk") == "financial" or is_financial(title):
            continue
        job = create_job({"kind": "manual_task", "title": title, "due_at": ""})
        created.append(job["id"])

    dates = list(state.get("dates", []))
    dates.append(plan_date)
    state.update(dates=dates[-90:], last_dispatched_at=now_iso(), last_job_ids=created)
    write_json("r7/plan_dispatch.json", state)
    return {"dispatched": len(created), "date": plan_date, "job_ids": created}


def ensure_daily_review(review_hour=18):
    """Create one automatic daily review job after the configured local hour."""
    now = datetime.now().astimezone()
    today = str(now.date())
    if now.hour < review_hour:
        return {"created": False, "reason": "not_due", "date": today}
    state = read_json("r7/daily_cycle.json", {})
    if state.get("last_review_date") == today:
        return {"created": False, "reason": "already_created", "date": today}

    from core.r7_engine import create_job
    job = create_job({"kind": "daily_review", "title": "每日自动复盘、学习并生成明日计划", "due_at": ""})
    state.update(last_review_date=today, last_review_job_id=job["id"], updated_at=now_iso())
    write_json("r7/daily_cycle.json", state)
    return {"created": True, "date": today, "job_id": job["id"]}
