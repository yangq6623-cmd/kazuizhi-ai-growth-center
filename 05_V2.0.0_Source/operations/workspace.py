"""Reviewable task, calendar, market-insight and command-center services."""

from collections import Counter
from datetime import date, timedelta

from analytics.business_metrics import build_analytics
from core.storage import now_iso, read_json, write_json
from promotion.content_center import history as promotion_history, list_keywords


TASK_STATUSES = {"pending": "待开始", "in_progress": "进行中", "completed": "已完成"}
PRIORITIES = {"low": "普通", "medium": "重要", "high": "优先"}


def _text(value, name, maximum=160, required=True):
    value = str(value or "").strip()
    if required and not value:
        raise ValueError(f"{name} is required")
    if len(value) > maximum:
        raise ValueError(f"{name} is too long")
    return value


def list_tasks():
    data = read_json("operations/tasks.json", {"items": []})
    items = data.get("items", [])
    counts = Counter(x.get("status", "pending") for x in items)
    return {"items": items, "counts": {key: counts.get(key, 0) for key in TASK_STATUSES},
            "execution": "review_required"}


def add_task(payload):
    title = _text(payload.get("title"), "title")
    priority = str(payload.get("priority", "medium"))
    if priority not in PRIORITIES:
        raise ValueError("priority must be low, medium or high")
    item = {"id": now_iso(), "title": title, "category": _text(payload.get("category") or "日常运营", "category", 60),
            "priority": priority, "priority_label": PRIORITIES[priority], "status": "pending",
            "status_label": TASK_STATUSES["pending"], "due_date": _text(payload.get("due_date"), "due_date", 10, False),
            "created_at": now_iso(), "updated_at": now_iso(), "execution": "manual"}
    data = read_json("operations/tasks.json", {"items": []})
    data.setdefault("items", []).insert(0, item)
    data["items"] = data["items"][:200]
    write_json("operations/tasks.json", data)
    return item


def update_task(payload):
    task_id = _text(payload.get("id"), "id", 80)
    status = str(payload.get("status", ""))
    if status not in TASK_STATUSES:
        raise ValueError("status must be pending, in_progress or completed")
    data = read_json("operations/tasks.json", {"items": []})
    for item in data.get("items", []):
        if item.get("id") == task_id:
            item.update(status=status, status_label=TASK_STATUSES[status], updated_at=now_iso())
            write_json("operations/tasks.json", data)
            return item
    raise ValueError("task was not found")


def generate_calendar(payload=None):
    payload = payload or {}
    region = _text(payload.get("region") or "涟水", "region", 40)
    service = _text(payload.get("service") or "本地维修与生活任务", "service", 80)
    start = date.today()
    themes = [
        ("需求洞察", f"复核{region}公开关键词信号，选择一个有证据的主题"),
        ("SEO 内容", f"围绕{region}{service}完成一篇待审核内容草稿"),
        ("本地资料", "核对品牌名称、服务区域和平台资料是否一致"),
        ("短视频准备", "完成一个真实场景脚本，检查画面授权和宣传边界"),
        ("渠道复盘", "记录发布渠道与真实咨询，不用曝光代替订单"),
        ("客户需求", "整理本周咨询问题，区分公开信号和已验证经营数据"),
        ("周复盘", "复核完成事项、问题和下周低风险计划"),
    ]
    items = [{"date": (start + timedelta(days=index)).isoformat(), "weekday": "一二三四五六日"[(start + timedelta(days=index)).weekday()],
              "theme": theme, "action": action, "status": "planned", "execution": "proposal_only"}
             for index, (theme, action) in enumerate(themes)]
    result = {"generated_at": now_iso(), "region": region, "service": service, "items": items,
              "rule": "日历只生成待审核安排，不会自动发布或执行。"}
    write_json("operations/promotion_calendar.json", result)
    return result


def get_calendar():
    return read_json("operations/promotion_calendar.json", {"items": [], "rule": "尚未生成推广日历。"})


def competition_report(payload):
    region = _text(payload.get("region"), "region", 40)
    category = _text(payload.get("category"), "category", 80)
    observations = payload.get("observations", [])
    if isinstance(observations, str):
        observations = [x.strip() for x in observations.replace("；", ";").split(";") if x.strip()]
    if not isinstance(observations, list) or not observations:
        raise ValueError("至少填写一条可核验的同行或市场观察")
    observations = [_text(x, "observation", 240) for x in observations[:20]]
    output = {"headline": f"{region}{category}市场观察报告", "evidence_count": len(observations),
              "observations": observations,
              "comparison_dimensions": ["服务范围是否写清", "需求入口是否顺畅", "价格与承诺是否可核验", "本地资料是否一致", "真实评价和服务记录是否充分"],
              "opportunities": ["优先补齐真实服务范围和常见问题", "用已核验服务记录建立信任", "围绕本地长尾需求制作可审核内容"],
              "limitations": "本报告只分析手动提供的观察，不代表完整市场份额、排名或竞争结论。",
              "execution": "proposal_only", "created_at": now_iso()}
    history = read_json("operations/competition_history.json", {"items": []})
    history.setdefault("items", []).insert(0, output)
    history["items"] = history["items"][:50]
    write_json("operations/competition_history.json", history)
    return output


def competition_history():
    return read_json("operations/competition_history.json", {"items": []})


def demand_insights():
    keywords = list_keywords().get("items", [])
    terms = [str(x.get("keyword", "")) for x in keywords if x.get("source") == "historical_public_signal"]
    regions = ["涟水", "淮安", "清江浦", "洪泽", "盱眙", "金湖", "淮阴"]
    services = ["水电维修", "家电维修", "管道疏通", "门锁维修", "马桶维修", "跑腿", "代办", "搬运"]
    region_counts = Counter({name: sum(name in term for term in terms) for name in regions})
    service_counts = Counter({name: sum(name in term for term in terms) for name in services})
    analytics = build_analytics()
    verified = analytics.get("status") == "verified"
    return {"status": "available", "generated_at": now_iso(), "public_signal_count": len(terms),
            "top_regions": [{"name": k, "signals": v} for k, v in region_counts.most_common() if v][:6],
            "top_needs": [{"name": k, "signals": v} for k, v in service_counts.most_common() if v][:6],
            "business_data_status": "已接入已验证经营数据" if verified else "真实客户与订单数据尚未接入",
            "verified_business_source": analytics.get("source") if verified else None,
            "insight": "公开关键词可用于选择调研和内容方向；是否形成真实需求，必须用咨询、订单和完成记录验证。",
            "truth_rule": "公开信号不等于客户数量、订单、收入或市场份额。"}


def command_center():
    tasks = list_tasks()
    drafts = promotion_history().get("items", [])
    analytics = build_analytics()
    demand = demand_insights()
    calendar = get_calendar()
    recommendations = []
    if analytics.get("status") != "verified":
        recommendations.append("接入只读经营汇总后，再判断订单和用户变化。")
    if not tasks["items"]:
        recommendations.append("先在任务管理中建立今天最重要的一项工作。")
    if not calendar.get("items"):
        recommendations.append("生成 7 天推广日历，把内容工作排进具体日期。")
    if not recommendations:
        recommendations.append("按任务优先级推进，并在完成后记录真实结果。")
    return {"generated_at": now_iso(), "business_status": analytics.get("status", "not_connected"),
            "business_message": analytics.get("message", "真实经营数据尚未接入"),
            "task_counts": tasks["counts"], "draft_count": len(drafts),
            "keyword_count": demand["public_signal_count"], "calendar_days": len(calendar.get("items", [])),
            "recent_tasks": tasks["items"][:5], "recent_drafts": drafts[:5],
            "recommendations": recommendations, "execution": "review_required"}
