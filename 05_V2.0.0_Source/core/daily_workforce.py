"""Daily AI workforce schedule for R7.

Keeps the eight non-financial AI roles on a truthful, time-based operating plan.
The schedule creates local queued jobs only; it never performs payment/refund/
settlement actions and never claims external publication without an integration.

R7 Final also binds the regional operations strategy to the real daily workforce:
50% Lianshui core sample, 30% other Huai'an districts/counties, 15% other Jiangsu
cities and 5% Zhejiang/Shanghai strategic reserve. These are AI non-financial
work shares, not ad budgets, market share or proof that a reserve region is open.
"""

import hashlib
import json
import time as time_module
import uuid
from datetime import datetime, time

from core.storage import now_iso, read_json, write_json


SCHEDULE_STATE = "r7/workforce_schedule.json"
BASE_BATCH_NUMBER = 1
TERMINAL_STATES = {"completed", "failed", "cancelled", "human_required"}

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


def _fingerprint(prefix, rows):
    canonical = json.dumps(rows, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return f"{prefix}:" + hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:20]


def _continuation_candidates(today_key):
    """Return only existing, evidence-backed work that can actually advance.

    This is deliberately not another fixed task template.  It observes the
    current SEO asset ledger and GEO Opportunity schedules and materializes a
    small continuation batch only when those ledgers contain actionable work.
    Repeating the same unchanged condition yields the same idempotency key and
    therefore cannot create an endless stream of cosmetic tasks.
    """
    candidates = []
    next_wake_epoch = None

    seo = read_json("r8_13/seo_geo_growth.json", {})
    seo_assets = seo.get("assets") if isinstance(seo, dict) else []
    if not isinstance(seo_assets, list):
        seo_assets = []
    pending_seo = [
        {
            "asset_id": str(row.get("id") or ""),
            "stage": str(row.get("stage") or ""),
            "revision": str(row.get("content_revision_id") or row.get("revision_id")
                            or row.get("generated_at") or row.get("created_at") or ""),
        }
        for row in seo_assets if isinstance(row, dict)
        and str(row.get("stage") or "") in {"PLANNED", "GENERATED", "QC_PASSED", "PUBLISHED"}
        and row.get("id")
    ]
    if pending_seo:
        pending_seo.sort(key=lambda row: (row["asset_id"], row["stage"], row["revision"]))
        key = _fingerprint("seo_existing_assets", pending_seo)
        candidates.append({
            "key": key,
            "agent": "SEO/GEO 增长员",
            "task_type": "seo_pipeline",
            "title": f"推进 {len(pending_seo)} 条既有 SEO Asset 的生成、QC、发布或提交闭环",
            "evidence_refs": [row["asset_id"] for row in pending_seo[:20]],
            "reason": "existing_seo_assets_pending_next_stage",
        })

    geo = read_json("geo_validation/growth_orchestrator.json", {})
    opportunities = geo.get("opportunities") if isinstance(geo, dict) else []
    if not isinstance(opportunities, list):
        opportunities = []
    now_epoch = time_module.time()
    due_slots = []
    for opportunity in opportunities:
        if not isinstance(opportunity, dict) or str(opportunity.get("state") or "") == "superseded":
            continue
        for slot in opportunity.get("retest_schedule") or []:
            if not isinstance(slot, dict) or slot.get("signal_id"):
                continue
            try:
                due_epoch = float(slot.get("due_at_epoch") or 0)
            except (TypeError, ValueError, OverflowError):
                due_epoch = 0.0
            if due_epoch > now_epoch:
                next_wake_epoch = due_epoch if next_wake_epoch is None else min(next_wake_epoch, due_epoch)
                continue
            if due_epoch:
                due_slots.append({
                    "opportunity_id": str(opportunity.get("id") or ""),
                    "schedule_id": str(slot.get("schedule_id") or ""),
                    "window": str(slot.get("window") or ""),
                    "task_id": str(slot.get("task_id") or ""),
                    "due_at_epoch": int(due_epoch),
                })
    if due_slots:
        due_slots.sort(key=lambda row: (row["due_at_epoch"], row["schedule_id"], row["opportunity_id"]))
        key = _fingerprint("geo_due_retests", due_slots)
        candidates.append({
            "key": key,
            "agent": "SEO/GEO 增长员",
            "task_type": "geo_growth_cycle",
            "title": f"推进 {len(due_slots)} 条已到期 GEO 复测的原队列执行与回执核查",
            "evidence_refs": [row["schedule_id"] or row["opportunity_id"] for row in due_slots[:20]],
            "reason": "geo_retest_schedule_due",
        })

    return candidates, next_wake_epoch


def _continuation_batch(data, today_key, now):
    """Create one idempotent in-day batch after the preceding batch finishes."""
    jobs = [row for row in data.get("items", []) if isinstance(row, dict)]
    todays = [row for row in jobs if row.get("schedule_date") == today_key]
    base = [row for row in todays if row.get("schedule_source") == "daily_workforce"]
    if not base or any(row.get("state") not in TERMINAL_STATES for row in base):
        return {
            "created": [], "reason": "base_batch_incomplete", "next_wake_epoch": None,
            "batch_id": f"R7-{today_key.replace('-', '')}-B01",
            "batch_number": BASE_BATCH_NUMBER,
            "batch_state": "running_or_waiting_due",
        }

    continuation = [row for row in todays if row.get("schedule_source") == "daily_workforce_continuation"]
    batch_numbers = [BASE_BATCH_NUMBER]
    batch_numbers.extend(int(row.get("batch_number") or 0) for row in continuation)
    latest_number = max(batch_numbers)
    latest_rows = [row for row in continuation if int(row.get("batch_number") or 0) == latest_number]
    latest_batch_id = (
        str((latest_rows[0] if latest_rows else {}).get("batch_id") or "")
        or f"R7-{today_key.replace('-', '')}-B{latest_number:02d}"
    )
    if latest_rows and any(row.get("state") not in TERMINAL_STATES for row in latest_rows):
        return {
            "created": [], "reason": "continuation_batch_incomplete", "next_wake_epoch": None,
            "batch_id": latest_batch_id, "batch_number": latest_number,
            "batch_state": "running_or_waiting_due",
        }

    candidates, next_wake_epoch = _continuation_candidates(today_key)
    used = {
        str(row.get("idempotency_key") or "") for row in jobs
        if row.get("idempotency_key")
    }
    candidates = [row for row in candidates if f"daily_continuation:{today_key}:{row['key']}" not in used]
    if not candidates:
        # Never fall back to B01 after B02/B03 has already completed.  The old
        # fallback made a healthy waiting state look as if continuation had
        # never happened, even though the immutable jobs/receipts proved it.
        return {
            "created": [], "reason": "no_new_eligible_work", "next_wake_epoch": next_wake_epoch,
            "batch_id": latest_batch_id, "batch_number": latest_number,
            "batch_state": "completed_waiting_eligibility",
        }

    batch_number = latest_number + 1
    batch_id = f"R7-{today_key.replace('-', '')}-B{batch_number:02d}"
    authority = next((row for row in jobs if row.get("mission_id") and row.get("command_id")), {})
    created = []
    for candidate in candidates[:4]:
        stamp = now_iso()
        job = {
            "id": uuid.uuid4().hex,
            "kind": "manual_task",
            "title": candidate["title"][:160],
            "mode": "local",
            "agent": candidate["agent"],
            "task_type": candidate["task_type"],
            "risk": "non_financial",
            "execution": "autonomous",
            "state": "queued",
            "progress": 0,
            "completed_steps": 0,
            "total_steps": 1,
            "due_at": now.isoformat(timespec="seconds"),
            "created_at": stamp,
            "updated_at": stamp,
            "approved_by": "autonomy_policy",
            "result": None,
            "error": None,
            "retry_count": 0,
            "schedule_key": candidate["key"],
            "schedule_date": today_key,
            "schedule_time": now.strftime("%H:%M"),
            "schedule_source": "daily_workforce_continuation",
            "batch_id": batch_id,
            "batch_number": batch_number,
            "batch_kind": "eligible_continuation",
            "idempotency_key": f"daily_continuation:{today_key}:{candidate['key']}",
            "continuation_reason": candidate["reason"],
            "evidence_refs": list(candidate.get("evidence_refs") or []),
            "mission_id": authority.get("mission_id"),
            "command_id": authority.get("command_id"),
            "command_receipt_id": authority.get("command_receipt_id"),
            "authorization_state": "authorized" if authority.get("command_id") else "waiting_for_chatgpt",
            "authorization_note": (
                "沿用当前 Mission/Command 的非资金自治授权。"
                if authority.get("command_id") else "等待现有 ChatGPT Command 自动绑定。"
            ),
            "priority_class": authority.get("priority_class") or "P1_closed_loop",
        }
        data["items"].insert(0, job)
        created.append(job)
    return {
        "created": created,
        "reason": "eligible_work_materialized",
        "batch_id": batch_id,
        "batch_number": batch_number,
        "batch_state": "queued",
        "next_wake_epoch": next_wake_epoch,
    }


def ensure_daily_workforce():
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
    base_template = list(DAILY_TEMPLATE)
    template = base_template + _adaptive_template(today)
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
        continuation_result = {"created": [], "reason": "not_evaluated", "next_wake_epoch": None}

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
                        "batch_id": f"R7-{today_key.replace('-', '')}-B01",
                        "batch_number": BASE_BATCH_NUMBER,
                        "batch_kind": "daily_base",
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
                "result": None,
                "error": None,
                "retry_count": 0,
                "schedule_key": key,
                "schedule_date": today_key,
                "schedule_time": hhmm,
                "schedule_source": "daily_workforce",
                "batch_id": f"R7-{today_key.replace('-', '')}-B01",
                "batch_number": BASE_BATCH_NUMBER,
                "batch_kind": "daily_base",
            }
            _apply_region_metadata(job, region)
            data["items"].insert(0, job)
            created.append(job)
            existing_by_key[key] = job

        # Evaluate continuation against the same point-in-time task ledger.
        # Newly created base jobs keep this at base_batch_incomplete. Once the
        # base (or prior continuation) is terminal, only evidence-backed work
        # can produce the next batch.
        continuation_result = _continuation_batch(data, today_key, now)
        continuation_created = continuation_result.get("created") or []

        if created or reconciled or continuation_created:
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
            for job in continuation_created:
                r7_engine._audit(
                    "job_continuation_scheduled",
                    job["id"],
                    "daily_workforce",
                    {
                        "batch_id": job.get("batch_id"),
                        "batch_number": job.get("batch_number"),
                        "task_type": job.get("task_type"),
                        "reason": job.get("continuation_reason"),
                        "idempotency_key": job.get("idempotency_key"),
                    },
                )

    base_counts = {}
    for *_, region_id in base_template:
        base_counts[region_id] = base_counts.get(region_id, 0) + 1
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
        region_job_counts=base_counts,
        region_work_share_pct={key: int(value.get("work_share_pct", 0)) for key, value in REGION_FALLBACK.items()},
        updated_at=now_iso(),
        active_batch_id=(continuation_result.get("batch_id")
                         or f"R7-{today_key.replace('-', '')}-B01"),
        latest_batch_number=int(continuation_result.get("batch_number") or BASE_BATCH_NUMBER),
        active_batch_state=str(continuation_result.get("batch_state") or "unknown"),
        continuation_created=len(continuation_result.get("created") or []),
        continuation_reason=continuation_result.get("reason"),
        next_eligible_wake_at=(
            datetime.fromtimestamp(continuation_result["next_wake_epoch"], tz=now.tzinfo).isoformat(timespec="seconds")
            if continuation_result.get("next_wake_epoch") else ""
        ),
        policy="全天分时执行；基础任务按50/30/15/5区域作战分配；非资金自动执行；资金事项不进入自动排班",
        truth_rule="区域比例是AI非资金工作量，不是广告预算、市场份额或区域已开放证明",
    )
    write_json(SCHEDULE_STATE, state)
    return {
        "date": today_key,
        "planned": len(template),
        "base_planned": len(base_template),
        "created": len(created),
        "reconciled": len(reconciled),
        "continuation_created": len(continuation_result.get("created") or []),
        "continuation_reason": continuation_result.get("reason"),
        "batch_id": continuation_result.get("batch_id") or f"R7-{today_key.replace('-', '')}-B01",
        "batch_number": int(continuation_result.get("batch_number") or BASE_BATCH_NUMBER),
        "batch_state": str(continuation_result.get("batch_state") or "unknown"),
        "region_job_counts": base_counts,
    }
