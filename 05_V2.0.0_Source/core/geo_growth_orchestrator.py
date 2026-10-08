"""R8-24 GEO autonomous growth orchestrator.

Turns C-level Doubao/API receipts into low-risk GEO growth work while keeping
formal A/B truth independent. The owner's ChatGPT Plus strategy is persisted as
local policy; no OpenAI API is required for the 7x24 execution loop.
"""
from __future__ import annotations

import hashlib
import threading
import time
from copy import deepcopy
from datetime import datetime

from core import geo_analysis
from core import geo_autonomy
from core import geo_validation as geo
from core import r7_engine
from core import seo_geo_growth
from core import geo_phase3_seo_bridge
from core.storage import now_iso, read_json, write_json
from integrations import geo_cloud_executor

STORE = "geo_validation/growth_orchestrator.json"
SCHEMA = "kz.geo-growth-os.v1"
MAX_HISTORY = 120
MAX_OPPORTUNITIES = 200
DEFAULT_RETEST_SECONDS = 72 * 60 * 60
_RUN_LOCK = threading.Lock()

DEFAULT = {
    "schema": SCHEMA,
    "enabled": True,
    "paused": False,
    "mission": "持续提高卡嘴子在涟水县本地维修相关 AI 问答中的曝光、品牌提及、推荐概率、官网引用和有效访问。",
    "policy": {
        "controller": "ChatGPT Plus 总控策略（本地持久化执行）",
        "openai_api": False,
        "new_paid_dependencies": False,
        "paid_runtime": ["doubao_api"],
        "execution_resources": ["doubao_api", "local_model", "rtx3060", "platform_capabilities"],
        "human_review_required": False,
        "formal_ab_side_channel": True,
        "truth_rule": "C级运营Signal可驱动低风险优化，但只有真实A/B Evidence可改变正式GEO成绩。",
        "retest_delay_seconds": DEFAULT_RETEST_SECONDS,
    },
    "processed_signal_ids": [],
    "opportunities": [],
    "history": [],
    "technical_blockers": [],
    "last_run_at": "",
    "last_error": "",
    "last_result": {},
}


def _load():
    value = read_json(STORE, deepcopy(DEFAULT))
    if not isinstance(value, dict) or value.get("schema") != SCHEMA:
        value = deepcopy(DEFAULT)
    for key, default in DEFAULT.items():
        value.setdefault(key, deepcopy(default))
    value.setdefault("policy", deepcopy(DEFAULT["policy"]))
    for key, default in DEFAULT["policy"].items():
        value["policy"].setdefault(key, deepcopy(default))
    value["opportunities"] = list(value.get("opportunities") or [])[-MAX_OPPORTUNITIES:]
    value["processed_signal_ids"] = list(value.get("processed_signal_ids") or [])[-2000:]
    value["history"] = list(value.get("history") or [])[-MAX_HISTORY:]
    value["technical_blockers"] = list(value.get("technical_blockers") or [])[-80:]
    return value


def _save(value):
    data = dict(value or {})
    data["schema"] = SCHEMA
    data["updated_at"] = now_iso()
    data["opportunities"] = list(data.get("opportunities") or [])[-MAX_OPPORTUNITIES:]
    data["processed_signal_ids"] = list(data.get("processed_signal_ids") or [])[-2000:]
    data["history"] = list(data.get("history") or [])[-MAX_HISTORY:]
    data["technical_blockers"] = list(data.get("technical_blockers") or [])[-80:]
    write_json(STORE, data)
    return data


def _signal_id(receipt):
    return str(receipt.get("evidence_id") or receipt.get("receipt_id") or receipt.get("response_id") or "").strip()


def _tested_at(receipt):
    return str(receipt.get("tested_at") or receipt.get("finished_at") or receipt.get("created_at") or "")


def _auxiliary_receipts():
    rows = [
        item for item in geo.receipts(2000)
        if str(item.get("evidence_level") or "") == "C"
        and not bool(item.get("official_truth"))
        and item.get("provider") == geo_cloud_executor.PROVIDER
    ]
    rows.sort(key=_tested_at)
    return rows


def _formal_count():
    return int((geo.dashboard().get("official") or {}).get("tested") or 0)


def _gap_from_signal(analysed):
    kind = str(analysed.get("question_type") or "discovery")
    if not analysed.get("brand_mentioned"):
        return {
            "code": "brand_visibility_missing",
            "label": "豆包C级运营信号未出现卡嘴子",
            "severity": "high",
            "action": "补强本地服务事实页、FAQ与品牌可发现内容",
            "suffix": "本地服务",
        }
    if kind == "commercial" and not analysed.get("brand_recommended"):
        return {
            "code": "recommendation_missing",
            "label": "豆包C级商业问题提及品牌但未形成推荐",
            "severity": "high",
            "action": "补强服务选择依据、适用场景与可信说明",
            "suffix": "怎么选",
        }
    if not analysed.get("service_match"):
        return {
            "code": "service_coverage_missing",
            "label": "豆包C级运营信号中的服务能力匹配不足",
            "severity": "medium",
            "action": "补强对应服务能力、区域与问题场景说明",
            "suffix": "服务范围",
        }
    return None


def _opportunity_score(receipt, analysed, gap):
    kind = str(analysed.get("question_type") or "discovery")
    score = 35 + {"commercial": 25, "discovery": 18, "brand": 10}.get(kind, 12)
    score += 20 if gap.get("severity") == "high" else 10
    region = str(receipt.get("region") or "涟水县")
    if "涟水" in region or "涟水" in str(receipt.get("question_text") or ""):
        score += 12
    question = str(receipt.get("question_text") or "")
    if any(token in question for token in ("爆", "漏", "跳闸", "维修", "上门", "疏通", "紧急")):
        score += 8
    if not analysed.get("brand_mentioned"):
        score += 5
    return min(100, max(0, int(score)))


def _priority(score):
    if score >= 85:
        return "S"
    if score >= 70:
        return "A"
    if score >= 55:
        return "B"
    return "C"


def _opportunity_id(signal_id, question_id, gap_code):
    raw = "|".join((signal_id, str(question_id or ""), str(gap_code or "")))
    return "GEO-GROWTH-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12].upper()


def _action_context(item):
    return {
        "region": item.get("region") or "涟水县",
        "service": item.get("service") or "综合维修",
        "keyword": item.get("keyword") or "涟水县本地维修服务",
        "audience": "涟水县有维修、安装或社区生活服务需求的本地用户",
        "evidence": (
            f"来源于豆包API C级运营Signal {item.get('signal_id') or 'unknown'}；"
            "仅用于运营优化，不属于正式A/B GEO Evidence。"
        ),
        "geo_gap_code": item.get("gap_code") or "",
        "geo_question_id": item.get("question_id") or "",
    }


def _jobs():
    return {str(row.get("id") or ""): row for row in r7_engine.list_jobs().get("items") or []}


def _growth_assets():
    dashboard = seo_geo_growth.dashboard()
    assets = {str(row.get("id") or ""): row for row in dashboard.get("assets") or []}
    opportunities = {str(row.get("id") or ""): row for row in dashboard.get("opportunities") or []}
    return dashboard, opportunities, assets


def _record_history(data, kind, detail):
    data.setdefault("history", []).append({"at": now_iso(), "kind": str(kind), "detail": deepcopy(detail)})
    data["history"] = data["history"][-MAX_HISTORY:]


def _record_blocker(data, code, detail, item_id=""):
    row = {
        "at": now_iso(),
        "code": str(code),
        "detail": str(detail)[:500],
        "item_id": str(item_id or ""),
        "blocking_scope": "subtask_only",
        "main_loop_continues": True,
    }
    existing = [
        x for x in data.get("technical_blockers") or []
        if not (x.get("code") == row["code"] and x.get("item_id") == row["item_id"])
    ]
    existing.append(row)
    data["technical_blockers"] = existing[-80:]


def _clear_blocker(data, code, item_id=""):
    code = str(code or "")
    item_id = str(item_id or "")
    data["technical_blockers"] = [
        row for row in (data.get("technical_blockers") or [])
        if not (
            str(row.get("code") or "") == code
            and (not item_id or str(row.get("item_id") or "") == item_id)
        )
    ]
    return data

def _create_from_signal(data, receipt):
    signal_id = _signal_id(receipt)
    if not signal_id or signal_id in set(data.get("processed_signal_ids") or []):
        return None
    analysed = geo_analysis.analyze_receipt(receipt)
    gap = _gap_from_signal(analysed)
    data.setdefault("processed_signal_ids", []).append(signal_id)
    if gap is None:
        _record_history(data, "signal_no_action", {
            "signal_id": signal_id,
            "question_id": receipt.get("question_id") or "",
            "reason": "当前C级信号已满足低风险运营动作的基本条件",
        })
        return None

    score = _opportunity_score(receipt, analysed, gap)
    region = str(receipt.get("region") or "涟水县")
    service = str(receipt.get("service") or "综合维修")
    keyword = f"{region}{service}{gap['suffix']}"[:120]
    item = {
        "id": _opportunity_id(signal_id, receipt.get("question_id"), gap["code"]),
        "signal_id": signal_id,
        "signal_level": "C",
        "official_truth": False,
        "question_id": str(receipt.get("question_id") or ""),
        "question_text": str(receipt.get("question_text") or ""),
        "question_type": str(receipt.get("question_type") or ""),
        "region": region,
        "service": service,
        "intent": str(receipt.get("intent") or "GEO运营优化"),
        "gap_code": gap["code"],
        "gap_label": gap["label"],
        "gap_severity": gap["severity"],
        "opportunity_score": score,
        "priority": _priority(score),
        "decision_source": "chatgpt_owner_policy_localized",
        "decision": gap["action"],
        "keyword": keyword,
        "baseline_at": _tested_at(receipt) or now_iso(),
        "baseline_signal": {
            "brand_mentioned": bool(analysed.get("brand_mentioned")),
            "brand_recommended": bool(analysed.get("brand_recommended")),
            "service_match": bool(analysed.get("service_match")),
        },
        "state": "opportunity_created",
        "seo_opportunity_id": "",
        "job_id": "",
        "job_state": "not_dispatched",
        "asset_id": "",
        "asset_stage": "",
        "public_url": "",
        "published_at": "",
        "retest_due_at_epoch": 0.0,
        "retest_task_id": "",
        "after_signal_id": "",
        "after_signal": {},
        "outcome": "pending",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "last_error": "",
    }

    seo_opportunity = geo_phase3_seo_bridge.upsert_opportunity({
        "region": region,
        "service": service,
        "keyword": keyword,
        "intent": item["intent"],
        "priority": item["priority"],
        "source": f"GEO Growth OS · C-level Signal · {gap['code']}",
        "source_ref": signal_id,
    })
    item["seo_opportunity_id"] = str(seo_opportunity.get("id") or "")
    job = r7_engine.create_job({
        "kind": "manual_task",
        "title": f"GEO 自动增长｜{gap['action']}｜{service}"[:160],
        "context": _action_context(item),
        "schedule_source": "geo_growth_orchestrator",
        "source_ref": item["id"],
    })
    item["job_id"] = str(job.get("id") or "")
    item["job_state"] = str(job.get("state") or "queued")
    item["state"] = "ai_employee_queued"
    data.setdefault("opportunities", []).append(item)
    _record_history(data, "opportunity_created", {
        "id": item["id"], "signal_id": signal_id, "score": score, "job_id": item["job_id"],
    })
    return item


def _latest_aux_for_question(question_id, after_at):
    rows = [
        row for row in _auxiliary_receipts()
        if str(row.get("question_id") or "") == str(question_id or "")
        and _tested_at(row) > str(after_at or "")
    ]
    return rows[-1] if rows else None


def _ensure_retest_task(item):
    if item.get("retest_task_id") or not item.get("question_id"):
        return
    queue = geo.queue_summary().get("tasks") or []
    existing = next((
        row for row in queue
        if row.get("provider") == geo_cloud_executor.PROVIDER
        and row.get("question_id") == item.get("question_id")
        and row.get("state") in {"queued", "running", "paused", "authorization_required"}
        and str(row.get("created_at") or "") >= str(item.get("published_at") or "")
    ), None)
    if existing:
        item["retest_task_id"] = existing.get("task_id") or ""
        return
    result = geo.create_and_enqueue_plan(
        limit=1,
        provider=geo_cloud_executor.PROVIDER,
        test_method="api",
        mission_id="GEO-GROWTH-OPERATING-RETEST",
        question_ids=[item["question_id"]],
    )
    task = (result.get("tasks") or [{}])[0]
    item["retest_task_id"] = task.get("task_id") or ""


def _signal_score(signal):
    if not isinstance(signal, dict):
        return 0
    return (
        (45 if signal.get("brand_mentioned") else 0)
        + (35 if signal.get("brand_recommended") else 0)
        + (20 if signal.get("service_match") else 0)
    )


def _sync_item(data, item, jobs, seo_opportunities, assets):
    item_id = str(item.get("id") or "")
    job = jobs.get(str(item.get("job_id") or ""), {})
    if job:
        item["job_state"] = job.get("state") or item.get("job_state")
        if job.get("state") == "failed":
            item["state"] = "failed"
            item["last_error"] = str(job.get("error") or "AI员工任务失败")[:500]
        elif job.get("state") == "completed":
            if item.get("state") in {"ai_employee_queued", "ai_employee_running", "opportunity_created", "deferred"}:
                item["state"] = "content_ready"
        elif job.get("state") in {"queued", "running"}:
            item["state"] = "ai_employee_running" if job.get("state") == "running" else "ai_employee_queued"

    seo_opportunity = seo_opportunities.get(str(item.get("seo_opportunity_id") or ""), {})
    asset_id = str(item.get("asset_id") or seo_opportunity.get("asset_id") or "")
    asset = assets.get(asset_id, {}) if asset_id else {}
    if asset:
        item["asset_id"] = asset_id
        item["asset_stage"] = asset.get("stage") or item.get("asset_stage") or ""
        item["public_url"] = asset.get("public_url") or item.get("public_url") or ""

    prepared_stages = {"GENERATED", "QC_PASSED", "PUBLISHED", "SUBMITTED", "CRAWLED", "INDEXED", "RANKED", "MENTIONED", "CITED", "CONVERTED"}
    if item.get("job_state") == "completed" and item.get("seo_opportunity_id") and str(item.get("asset_stage") or "") not in prepared_stages:
        bridge = geo_phase3_seo_bridge.prepare_phase3_assets({
            "actions": [{"action_id": item["id"], "job_state": "completed", "opportunity_id": item["seo_opportunity_id"]}]
        })
        states = bridge.get("states") or []
        if states:
            item["asset_id"] = states[0].get("asset_id") or item.get("asset_id") or ""
            item["asset_stage"] = states[0].get("stage") or item.get("asset_stage") or ""
            item["public_url"] = states[0].get("public_url") or item.get("public_url") or ""

    if item.get("asset_stage") in {"GENERATED", "QC_PASSED"}:
        item["state"] = "waiting_publish"

    if item.get("asset_stage") in {"PUBLISHED", "SUBMITTED", "CRAWLED", "INDEXED", "RANKED", "MENTIONED", "CITED", "CONVERTED"}:
        if not item.get("published_at"):
            published_asset = assets.get(str(item.get("asset_id") or ""), {})
            item["published_at"] = published_asset.get("published_at") or now_iso()
            delay = max(300, int((_load().get("policy") or {}).get("retest_delay_seconds") or DEFAULT_RETEST_SECONDS))
            item["retest_due_at_epoch"] = time.time() + delay
        item["state"] = "waiting_retest"

    if item.get("state") in {"waiting_retest", "retest_queued"}:
        fresh = _latest_aux_for_question(item.get("question_id"), item.get("published_at"))
        if fresh:
            analysed = geo_analysis.analyze_receipt(fresh)
            item["after_signal_id"] = _signal_id(fresh)
            item["after_signal"] = {
                "brand_mentioned": bool(analysed.get("brand_mentioned")),
                "brand_recommended": bool(analysed.get("brand_recommended")),
                "service_match": bool(analysed.get("service_match")),
            }
            before = _signal_score(item.get("baseline_signal"))
            after = _signal_score(item.get("after_signal"))
            item["operating_before_score"] = before
            item["operating_after_score"] = after
            item["operating_delta"] = after - before
            item["outcome"] = "improved" if after > before else "regressed" if after < before else "neutral"
            item["state"] = "completed"
            item["completed_at"] = now_iso()
            _clear_blocker(data, "operating_retest_deferred", item_id)
            _record_history(data, "before_after_completed", {
                "id": item["id"], "before": before, "after": after, "delta": after - before,
                "truth": "C-level operating signal only; formal A/B score unchanged",
            })
        elif item.get("state") == "waiting_retest" and time.time() >= float(item.get("retest_due_at_epoch") or 0):
            try:
                _ensure_retest_task(item)
                item["state"] = "retest_queued"
                _clear_blocker(data, "operating_retest_deferred", item_id)
            except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
                item["last_error"] = str(error)[:500]
                _record_blocker(data, "operating_retest_deferred", error, item_id)

    if item.get("state") != "failed":
        item["last_error"] = ""
    item["updated_at"] = now_iso()
    _clear_blocker(data, "opportunity_sync_deferred", item_id)
    return item


def _sync_all(data):
    jobs = _jobs()
    _, seo_opportunities, assets = _growth_assets()
    for item in data.get("opportunities") or []:
        try:
            _sync_item(data, item, jobs, seo_opportunities, assets)
        except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
            item["last_error"] = str(error)[:500]
            if item.get("state") not in {"completed", "failed"}:
                item["state"] = "deferred"
            _record_blocker(data, "opportunity_sync_deferred", error, item.get("id") or "")
    return data

def _state_counts(items):
    counts = {"total": len(items), "optimizing": 0, "waiting_publish": 0, "published_or_waiting_retest": 0, "completed": 0, "failed": 0}
    for item in items:
        state = str(item.get("state") or "")
        if state in {"opportunity_created", "ai_employee_queued", "ai_employee_running", "content_ready"}:
            counts["optimizing"] += 1
        if state == "waiting_publish":
            counts["waiting_publish"] += 1
        if state in {"waiting_retest", "retest_queued"}:
            counts["published_or_waiting_retest"] += 1
        if state == "completed":
            counts["completed"] += 1
        if state == "failed":
            counts["failed"] += 1
    return counts


def _pipeline(items):
    return [
        {"id": "signal", "label": "豆包运营Signal", "count": len(_auxiliary_receipts()), "state": "active"},
        {"id": "opportunity", "label": "机会识别", "count": len(items), "state": "active" if items else "waiting"},
        {"id": "decision", "label": "总控策略判断", "count": len(items), "state": "active" if items else "waiting"},
        {"id": "execute", "label": "AI员工执行", "count": sum(1 for x in items if x.get("job_id")), "state": "active" if any(x.get("job_id") for x in items) else "waiting"},
        {"id": "publish", "label": "真实发布", "count": sum(1 for x in items if x.get("public_url")), "state": "active" if any(x.get("public_url") for x in items) else "waiting"},
        {"id": "retest", "label": "自动复测", "count": sum(1 for x in items if x.get("after_signal_id")), "state": "active" if any(x.get("after_signal_id") for x in items) else "waiting"},
        {"id": "learn", "label": "Before / After", "count": sum(1 for x in items if x.get("state") == "completed"), "state": "active" if any(x.get("state") == "completed" for x in items) else "waiting"},
    ]


def _pipeline_fast(items, signal_count):
    """Pure in-memory pipeline rendering for the owner status endpoint."""
    return [
        {"id": "signal", "label": "豆包运营Signal", "count": int(signal_count or 0), "state": "active" if signal_count else "waiting"},
        {"id": "opportunity", "label": "机会识别", "count": len(items), "state": "active" if items else "waiting"},
        {"id": "decision", "label": "总控策略判断", "count": len(items), "state": "active" if items else "waiting"},
        {"id": "execute", "label": "AI员工执行", "count": sum(1 for x in items if x.get("job_id")), "state": "active" if any(x.get("job_id") for x in items) else "waiting"},
        {"id": "publish", "label": "真实发布", "count": sum(1 for x in items if x.get("public_url")), "state": "active" if any(x.get("public_url") for x in items) else "waiting"},
        {"id": "retest", "label": "自动复测", "count": sum(1 for x in items if x.get("after_signal_id")), "state": "active" if any(x.get("after_signal_id") for x in items) else "waiting"},
        {"id": "learn", "label": "Before / After", "count": sum(1 for x in items if x.get("state") == "completed"), "state": "active" if any(x.get("state") == "completed" for x in items) else "waiting"},
    ]


def fast_status():
    """#689 owner-facing snapshot that never runs analysis or orchestration.

    The #688 field failure showed the shell could paint while /api/r8-24/geo-growth
    stayed pending. The old status path entered geo_autonomy.status(), which can
    reconcile Phase-2 truth and traverse several ledgers. That work is correct
    for background execution but is not acceptable on a UI polling request.
    """
    data = _load()
    items = list(reversed(data.get("opportunities") or []))
    counts = _state_counts(items)

    try:
        receipts = geo.receipts(1000)
    except (OSError, ValueError, RuntimeError, TypeError, KeyError):
        receipts = []

    auxiliary = [
        row for row in receipts
        if str(row.get("evidence_level") or "") == "C"
        and not bool(row.get("official_truth"))
        and row.get("provider") == geo_cloud_executor.PROVIDER
    ]
    formal_ids = {
        row.get("question_id")
        for row in receipts
        if row.get("official_truth")
        and row.get("evidence_level") in geo.OFFICIAL_EVIDENCE_LEVELS
        and row.get("question_id")
    }

    cloud_data = read_json(geo_autonomy.STORE, {})
    target = max(1, min(int(cloud_data.get("target") or 1), 50))
    cycle_started_at = str(cloud_data.get("cycle_started_at") or "")
    cloud_ids = {
        row.get("question_id")
        for row in auxiliary
        if row.get("question_id")
        and (
            not cycle_started_at
            or str(row.get("tested_at") or row.get("finished_at") or row.get("created_at") or "") >= cycle_started_at
        )
    }
    completed = min(target, len(cloud_ids))
    if cloud_data.get("enabled") and cloud_data.get("paused"):
        cloud_state = "paused"
    elif cloud_data.get("enabled") and completed >= target:
        cloud_state = "monitoring"
    elif cloud_data.get("enabled"):
        cloud_state = "running"
    else:
        cloud_state = "idle"

    try:
        executor = geo_cloud_executor.status()
    except (OSError, ValueError, RuntimeError, TypeError, KeyError):
        executor = {"ready": False, "label": "豆包API"}

    return {
        "schema": SCHEMA,
        "status_mode": "fast_snapshot",
        "state": "paused" if data.get("paused") else "running" if data.get("enabled") else "stopped",
        "enabled": bool(data.get("enabled")),
        "paused": bool(data.get("paused")),
        "mission": data.get("mission") or DEFAULT["mission"],
        "policy": deepcopy(data.get("policy") or {}),
        "formal_ab_completed": len(formal_ids),
        "formal_ab_target": 50,
        "cloud": {
            "state": cloud_state,
            "completed": completed,
            "target": target,
            "provider": executor.get("label") or "豆包API",
            "ready": bool(executor.get("ready")),
        },
        "summary": {
            **counts,
            "signals": len(auxiliary),
            "technical_blockers": len(data.get("technical_blockers") or []),
        },
        "pipeline": _pipeline_fast(items, len(auxiliary)),
        "opportunities": items[:30],
        "technical_blockers": list(reversed(data.get("technical_blockers") or []))[:12],
        "last_run_at": data.get("last_run_at") or "",
        "last_error": data.get("last_error") or "",
        "last_result": deepcopy(data.get("last_result") or {}),
        "truth_rule": "豆包API C级结果用于运营Signal和自动优化；正式A/B Evidence独立计分，任何C级结果、内容生成或发布均不会冒充正式GEO提升。",
    }


def status():
    # read_only_status_no_sync: polling the dashboard must never mutate SEO/GEO ledgers.
    data = _load()
    items = list(reversed(data.get("opportunities") or []))
    counts = _state_counts(items)
    cloud = geo_autonomy.status()
    return {
        "schema": SCHEMA,
        "state": "paused" if data.get("paused") else "running" if data.get("enabled") else "stopped",
        "enabled": bool(data.get("enabled")),
        "paused": bool(data.get("paused")),
        "mission": data.get("mission") or DEFAULT["mission"],
        "policy": deepcopy(data.get("policy") or {}),
        "formal_ab_completed": _formal_count(),
        "formal_ab_target": 50,
        "cloud": {
            "state": cloud.get("state"),
            "completed": cloud.get("cloud_completed"),
            "target": cloud.get("target"),
            "provider": (cloud.get("executor") or {}).get("label") or "豆包API",
            "ready": bool((cloud.get("executor") or {}).get("ready")),
        },
        "summary": {**counts, "signals": len(_auxiliary_receipts()), "technical_blockers": len(data.get("technical_blockers") or [])},
        "pipeline": _pipeline(items),
        "opportunities": items[:30],
        "technical_blockers": list(reversed(data.get("technical_blockers") or []))[:12],
        "last_run_at": data.get("last_run_at") or "",
        "last_error": data.get("last_error") or "",
        "last_result": deepcopy(data.get("last_result") or {}),
        "truth_rule": "豆包API C级结果用于运营Signal和自动优化；正式A/B Evidence独立计分，任何C级结果、内容生成或发布均不会冒充正式GEO提升。",
    }


def arm_unattended():
    """Enable the GEO Growth OS without running heavy work on the HTTP startup path.

    #688 separates state arming from execution. The normal scheduler will pick
    up the enabled loop after the owner UI has painted, so automatic operation
    remains on while first-open API/iframe requests stay responsive.
    """
    data = _load()
    if data.get("paused"):
        return fast_status()
    data["enabled"] = True
    data["paused"] = False
    data["last_error"] = ""
    data["last_result"] = {
        "action": "arm_unattended",
        "execution": "deferred_to_scheduler",
        "at": now_iso(),
    }
    _save(data)
    return fast_status()


def start():
    data = _load()
    data["enabled"] = True
    data["paused"] = False
    data["last_error"] = ""
    cloud = geo_autonomy.status()
    try:
        if (cloud.get("executor") or {}).get("ready"):
            geo_autonomy.ensure_continuous_monitoring(target=max(1, int(cloud.get("target") or 1)))
    except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
        _record_blocker(data, "cloud_monitoring_deferred", error)
    data["last_result"] = {"action": "start", "at": now_iso()}
    _save(data)
    run_once(force=True)
    return fast_status()


def pause():
    data = _load()
    data["enabled"] = True
    data["paused"] = True
    data["last_result"] = {"action": "pause", "at": now_iso()}
    _save(data)
    return fast_status()


def resume():
    data = _load()
    data["enabled"] = True
    data["paused"] = False
    data["last_error"] = ""
    data["last_result"] = {"action": "resume", "at": now_iso()}
    _save(data)
    run_once(force=True)
    return fast_status()


def retry_failed():
    data = _load()
    retried = 0
    deferred = 0
    for item in data.get("opportunities") or []:
        if item.get("state") == "failed" and item.get("job_id"):
            try:
                job = r7_engine.command({"action": "retry", "id": item["job_id"]})
                item["job_state"] = job.get("state") or "queued"
                item["state"] = "ai_employee_queued"
                item["last_error"] = ""
                retried += 1
            except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
                item["last_error"] = str(error)[:500]
        elif item.get("state") == "deferred":
            if item.get("job_state") == "completed":
                item["state"] = "content_ready"
            elif item.get("job_state") in {"queued", "running"}:
                item["state"] = "ai_employee_queued"
            else:
                item["state"] = "opportunity_created"
            item["last_error"] = ""
            _clear_blocker(data, "opportunity_sync_deferred", item.get("id") or "")
            deferred += 1
    data["last_result"] = {"action": "retry_failed", "retried": retried, "deferred_requeued": deferred, "at": now_iso()}
    _save(data)
    r7_engine.run_due_jobs()
    return fast_status()

def run_once(force=False):
    if not _RUN_LOCK.acquire(blocking=False):
        return {"ok": True, "skipped": True, "reason": "geo_growth_orchestrator_already_running"}
    try:
        data = _load()
        if not data.get("enabled"):
            return {"ok": True, "skipped": True, "reason": "geo_growth_orchestrator_stopped"}
        if data.get("paused"):
            return {"ok": True, "skipped": True, "reason": "geo_growth_orchestrator_paused"}

        r7_engine.run_due_jobs()
        _sync_all(data)
        processed = set(data.get("processed_signal_ids") or [])
        available = [row for row in _auxiliary_receipts() if _signal_id(row) and _signal_id(row) not in processed]
        batch = 3 if force else 1
        created = []
        for receipt in available[:batch]:
            try:
                item = _create_from_signal(data, receipt)
                if item:
                    created.append(item["id"])
            except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
                signal_id = _signal_id(receipt)
                if signal_id and signal_id not in data["processed_signal_ids"]:
                    data["processed_signal_ids"].append(signal_id)
                _record_blocker(data, "signal_processing_deferred", error, signal_id)

        r7_engine.run_due_jobs()
        _sync_all(data)
        data["last_run_at"] = now_iso()
        data["last_error"] = ""
        data["last_result"] = {
            "ok": True,
            "created": created,
            "signals_seen": len(_auxiliary_receipts()),
            "formal_ab_unchanged": _formal_count(),
            "at": now_iso(),
        }
        _save(data)
        return data["last_result"]
    except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
        data = _load()
        data["last_run_at"] = now_iso()
        data["last_error"] = str(error)[:800]
        data["last_result"] = {"ok": False, "error": str(error)[:800], "at": now_iso()}
        _save(data)
        return data["last_result"]
    finally:
        _RUN_LOCK.release()
