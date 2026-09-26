"""Daily AI workforce schedule for R7.

Keeps the eight non-financial AI roles on a truthful, time-based operating plan.
The schedule creates local queued jobs only; it never performs payment/refund/
settlement actions and never claims external publication without an integration.

R7 Final also binds the regional operations strategy to the real daily workforce:
50% Lianshui core sample, 30% other Huai'an districts/counties, 15% other Jiangsu
cities and 5% Zhejiang/Shanghai strategic reserve. These are AI non-financial
work shares, not ad budgets, market share or proof that a reserve region is open.
"""

import uuid
from datetime import datetime, time

from core.storage import now_iso, read_json, write_json


SCHEDULE_STATE = "r7/workforce_schedule.json"

# Exactly 20 base jobs makes the strategic 50/30/15/5 work-share visible in the
# execution layer: S=10, A=6, B=3, C=1. Existing schedule keys are preserved
# wherever possible so an in-day R7 upgrade can reconcile queued jobs rather than
# duplicate the whole day. Reserve/prepare regions only research and prepare;
# they never claim local service is open or externally published.
DAILY_TEMPLATE = (
    ("08:00", "market-am", "市场情报员", "market", "扫描涟水县本地维修公开需求信号并整理上午重点", "lianshui"),
    ("08:20", "seo-am", "SEO/GEO 增长员", "seo", "更新涟水本地维修关键词与 SEO/GEO 上午优化草稿", "lianshui"),
    ("08:40", "content-am", "内容运营员", "content", "根据涟水真实需求信号生成上午维修知识与常见问题内容草稿", "lianshui"),
    ("09:00", "social-am", "社媒运营员", "content", "准备涟水本地论坛、社区与博客内容草稿和标题清单；没有真实发布回执不记为已发布", "lianshui"),
    ("09:20", "video-am", "短视频运营员", "video", "根据涟水用户痛点生成本地维修短视频选题与脚本草稿", "lianshui"),
    ("09:45", "local-am", "本地增长员", "local", "梳理涟水县重点区域、服务需求、师傅供给与本地增长动作", "lianshui"),
    ("10:15", "conversion-am", "用户转化员", "conversion", "分析涟水已验证用户与订单数据并检查上午转化机会", "lianshui"),
    ("10:45", "review-am", "数据复盘员", "review", "复核涟水上午执行结果并调整当天后续核心样板区优先级", "lianshui"),
    ("11:15", "market-mid", "市场情报员", "market", "二次扫描涟水本地公开需求信号并更新需求变化与高价值选题", "lianshui"),
    ("12:00", "core-midday", "数据复盘员", "review", "汇总涟水上午需求、内容与转化证据，形成下午核心样板区继续/降频建议", "lianshui"),

    ("13:30", "seo-pm", "SEO/GEO 增长员", "geo", "扫描淮安其他区县搜索与本地需求信号，生成 SEO/GEO 预热草稿", "huaian_main"),
    ("14:00", "content-pm", "内容运营员", "content", "根据淮安其他区县公开痛点生成维修知识、避坑与用户问答内容草稿", "huaian_main"),
    ("14:30", "social-pm", "社媒运营员", "content", "准备淮安其他区县论坛、社区与博客预热内容包；未开放区域不得宣称已可下单", "huaian_main"),
    ("15:00", "video-pm", "短视频运营员", "video", "生成淮安其他区县本地维修短视频选题、标题和分镜草稿", "huaian_main"),
    ("15:30", "local-pm", "本地增长员", "local", "比较淮安其他区县需求与师傅供给，整理下一批重点区县建议", "huaian_main"),
    ("16:00", "conversion-pm", "用户转化员", "conversion", "复核淮安其他区县可验证访问、维修需求与订单转化信号，避免只看曝光", "huaian_main"),

    ("16:30", "market-close", "市场情报员", "market", "扫描江苏其他城市维修需求、竞争与用户痛点公开信号，建立扩张候选清单", "jiangsu_expand"),
    ("17:00", "seo-close", "SEO/GEO 增长员", "seo", "更新江苏其他城市关键词、长尾需求与本地内容素材储备，不提前承诺服务开放", "jiangsu_expand"),
    ("17:30", "content-close", "本地增长员", "local", "整理江苏扩张准备区的师傅供给、区域机会与可复用内容战备资料", "jiangsu_expand"),

    ("17:50", "reserve-close", "市场情报员", "market", "低频扫描浙江和上海维修趋势、用户痛点与高表现内容，仅做战略储备和战备沉淀", "zhejiang_shanghai_reserve"),
)


REGION_FALLBACK = {
    "lianshui": {"name": "涟水县", "tier": "S", "role": "核心样板区", "mode": "core", "work_share_pct": 50},
    "huaian_main": {"name": "淮安其他区县", "tier": "A", "role": "淮安主战区", "mode": "main", "work_share_pct": 30},
    "jiangsu_expand": {"name": "江苏其他城市", "tier": "B", "role": "扩张准备区", "mode": "prepare", "work_share_pct": 15},
    "zhejiang_shanghai_reserve": {"name": "浙江 / 上海", "tier": "C", "role": "战略储备区", "mode": "reserve", "work_share_pct": 5},
}

# ChatGPT plans are expressed as business actions while the inherited R7 worker
# queue uses role/task types.  Keep this translation in one place so a daily
# plan cannot accidentally unlock unrelated staff work.
TASK_ACTIONS = {
    "market": {"market_scan"},
    "seo": {"seo_discovery", "seo_plan", "seo_generate", "seo_qc", "seo_monitor"},
    "geo": {"geo_baseline", "geo_observe"},
    "content": {"content_generate", "social_draft"},
    "video": {"video_generate"},
    "local": {"local_analysis"},
    "conversion": {"conversion_analysis", "attribution_review"},
    "review": {"daily_review"},
}


def _due_at(day, hhmm):
    hour, minute = (int(part) for part in hhmm.split(":", 1))
    now = datetime.now().astimezone()
    return datetime.combine(day, time(hour, minute), tzinfo=now.tzinfo).isoformat(timespec="seconds")


def _region_rows():
    """Return live region strategy rows, with a safe static fallback.

    Scheduling must not fail just because an analytics snapshot or public signal
    file is temporarily unavailable. The strategic tier itself is owner-approved;
    live scores/evidence are additional context only.
    """
    rows = {key: dict(value, id=key) for key, value in REGION_FALLBACK.items()}
    try:
        from core.region_strategy import build_region_strategy
        strategy = build_region_strategy()
        for item in strategy.get("regions", []):
            region_id = str(item.get("id") or "")
            if region_id in rows:
                rows[region_id].update(item)
    except Exception:
        pass
    return rows


def _recent_failed_types():
    learning = read_json("r7/learning.json", {"items": []})
    return {
        str(item.get("task_type") or "")
        for item in learning.get("items", [])[:30]
        if item.get("state") == "failed"
    }


def _adaptive_template(day):
    """Add a small number of recovery jobs without distorting base region shares."""
    failed = _recent_failed_types()
    extra = []
    if failed & {"seo", "geo", "content", "video"}:
        extra.append(("12:20", "adaptive-content-recovery", "SEO/GEO 增长员", "seo",
                      "检查近期内容增长失败原因并使用已验证本地关键词重新优化草稿", "lianshui"))
    if failed & {"market", "local", "conversion"}:
        extra.append(("18:00", "adaptive-growth-recheck", "数据复盘员", "review",
                      "根据近期失败记录重新评估区域与增长优先级并更新后续执行建议", "lianshui"))
    return extra[:2]


def _apply_region_metadata(job, region):
    job.update({
        "region_id": region.get("id"),
        "region_name": region.get("name"),
        "region_tier": region.get("tier"),
        "region_role": region.get("role"),
        "region_mode": region.get("mode"),
        "region_work_share_pct": region.get("work_share_pct"),
        "region_readiness_score": region.get("readiness_score"),
        "region_confidence": region.get("confidence"),
        "region_source": "regional_operations_strategy",
    })


def ensure_daily_workforce(allowed_actions=None, command_id=""):
    """Ensure today's complete, regional, time-spread workforce plan exists once.

    On upgrades during the same day, queued jobs with an existing schedule key are
    reconciled in place to the new regional assignment. Completed/running/failed
    historical jobs are never rewritten, preserving truthful execution history.
    """
    # Import here to avoid a module cycle during R7 engine startup.
    from core import r7_engine

    now = datetime.now().astimezone()
    today = now.date()
    today_key = str(today)
    allowed = {str(item or "").strip() for item in (allowed_actions or []) if str(item or "").strip()}
    base_template = list(DAILY_TEMPLATE)
    template = base_template + _adaptive_template(today)
    if allowed:
        template = [row for row in template if TASK_ACTIONS.get(row[3], set()).intersection(allowed)]
    regions = _region_rows()

    with r7_engine.LOCK:
        if r7_engine.audit_history()["integrity"] != "verified":
            raise ValueError("审计记录校验失败，已暂停自动排班")
        data = r7_engine._store()
        todays = [
            job for job in data.get("items", [])
            if job.get("schedule_date") == today_key and job.get("schedule_source") == "daily_workforce"
        ]
        existing_by_key = {
            str(job.get("schedule_key")): job
            for job in todays
            if job.get("schedule_key")
        }
        created = []
        reconciled = []

        for hhmm, key, agent, task_type, title, region_id in template:
            region = dict(regions.get(region_id) or REGION_FALLBACK[region_id], id=region_id)
            existing = existing_by_key.get(key)
            if existing:
                # Queued jobs have not executed yet, so it is truthful and safe to
                # align them with the newly approved regional strategy in place.
                if existing.get("state") == "queued":
                    changed = False
                    updates = {
                        "title": title,
                        "agent": agent,
                        "task_type": task_type,
                        "due_at": _due_at(today, hhmm),
                        "schedule_time": hhmm,
                    }
                    for field, value in updates.items():
                        if existing.get(field) != value:
                            existing[field] = value
                            changed = True
                    before_region = existing.get("region_id")
                    _apply_region_metadata(existing, region)
                    if before_region != region_id or changed:
                        existing["updated_at"] = now_iso()
                        reconciled.append(existing)
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
                "chatgpt_command_id": str(command_id or "").strip() or None,
                "result": None,
                "error": None,
                "retry_count": 0,
                "schedule_key": key,
                "schedule_date": today_key,
                "schedule_time": hhmm,
                "schedule_source": "daily_workforce",
            }
            _apply_region_metadata(job, region)
            data["items"].insert(0, job)
            created.append(job)
            existing_by_key[key] = job

        if created or reconciled:
            write_json(r7_engine.JOBS, data)
            for job in created:
                r7_engine._audit(
                    "job_auto_scheduled",
                    job["id"],
                    "daily_workforce",
                    {
                        "agent": job["agent"], "task_type": job["task_type"], "due_at": job["due_at"],
                        "region_id": job.get("region_id"), "region_tier": job.get("region_tier"),
                    },
                )
            for job in reconciled:
                r7_engine._audit(
                    "job_region_reconciled",
                    job["id"],
                    "daily_workforce",
                    {
                        "region_id": job.get("region_id"), "region_tier": job.get("region_tier"),
                        "schedule_time": job.get("schedule_time"),
                    },
                )

    # Report the plan that is actually eligible to run today.  Showing the
    # full default template after ChatGPT has approved only a subset would be
    # misleading in the control centre.
    planned_counts = {}
    for *_, region_id in template:
        planned_counts[region_id] = planned_counts.get(region_id, 0) + 1
    state = read_json(SCHEDULE_STATE, {"dates": []})
    dates = [value for value in state.get("dates", []) if value != today_key]
    dates.append(today_key)
    state.update(
        dates=dates[-31:],
        date=today_key,
        planned=len(template),
        base_planned=len(base_template),
        created=len(created),
        reconciled=len(reconciled),
        region_job_counts=planned_counts,
        region_work_share_pct={key: int(value.get("work_share_pct", 0)) for key, value in REGION_FALLBACK.items()},
        updated_at=now_iso(),
        policy=("仅执行 ChatGPT 当日计划明确授权的非资金任务；基础任务按50/30/15/5区域作战分配；资金事项不进入自动排班" if allowed else "全天分时执行；基础任务按50/30/15/5区域作战分配；非资金自动执行；资金事项不进入自动排班"),
        truth_rule="区域比例是AI非资金工作量，不是广告预算、市场份额或区域已开放证明",
    )
    write_json(SCHEDULE_STATE, state)
    return {
        "date": today_key,
        "planned": len(template),
        "base_planned": len(base_template),
        "created": len(created),
        "reconciled": len(reconciled),
        "region_job_counts": planned_counts,
        "allowed_actions": sorted(allowed),
    }
