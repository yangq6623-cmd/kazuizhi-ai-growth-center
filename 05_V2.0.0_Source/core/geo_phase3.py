"""R8-19 GEO Phase 3: gap -> action -> execution -> retest -> before/after.

This controller never changes GEO evidence semantics. Phase-2 A/B Evidence is
read-only input. Optimization work is non-financial and must be authorized by a
verified ChatGPT Command or an explicit owner action. Publication keeps using
the existing truthful SEO/GEO deployment pipeline, and a Phase-3 retest remains
pending until a real external A/B receipt is recorded.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy

from core import geo_analysis, geo_validation, seo_geo_growth
from core.command_execution import active_authorization
from core.r7_engine import create_job, list_jobs, run_due_jobs
from core.storage import now_iso, read_json, write_json
from integrations import geo_chatgpt_analyzer

STORE = "geo_validation/phase3.json"
SCHEMA = "kz.geo-phase3.v1"
MAX_ACTIONS = 5

DEFAULT = {
    "schema": SCHEMA,
    "enabled": True,
    "plan": {},
    "history": [],
    "updated_at": "",
}

GAP_ACTIONS = {
    "brand_visibility_missing": {
        "title": "补强 GEO 品牌可见性与本地服务事实页",
        "task_type": "geo",
        "keyword_suffix": "本地服务",
        "reason": "真实外部AI回答未出现卡嘴子，需要增加可抓取、可引用的品牌与服务事实。",
    },
    "recommendation_missing": {
        "title": "补强商业推荐题的服务选择与可信说明",
        "task_type": "geo",
        "keyword_suffix": "怎么选",
        "reason": "商业推荐题没有形成明确推荐，需要补充真实服务能力、适用场景和选择依据。",
    },
    "official_citation_missing": {
        "title": "补强官网可引用结构与品牌一致性",
        "task_type": "seo",
        "keyword_suffix": "官方服务信息",
        "reason": "回答提及品牌但没有引用官网，需要增强官网FAQ、服务区域和结构化信息。",
    },
    "source_support_missing": {
        "title": "补充可追溯官网来源与FAQ证据页",
        "task_type": "seo",
        "keyword_suffix": "服务说明",
        "reason": "回答缺少可追溯来源URL，需要补充公开可访问、事实一致的来源页面。",
    },
    "brand_fact_depth_missing": {
        "title": "完善品牌能力与服务范围FAQ",
        "task_type": "geo",
        "keyword_suffix": "平台服务范围",
        "reason": "品牌题对真实服务能力覆盖不足，需要完善品牌事实与能力说明。",
    },
}


def _load():
    data = read_json(STORE, deepcopy(DEFAULT))
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        data = deepcopy(DEFAULT)
    data.setdefault("enabled", True)
    data.setdefault("plan", {})
    data.setdefault("history", [])
    return data


def _save(data):
    data = dict(data or {})
    data["schema"] = SCHEMA
    data["updated_at"] = now_iso()
    data["history"] = list(data.get("history") or [])[:30]
    write_json(STORE, data)
    return data


def _analysis():
    snap = geo_analysis.snapshot()
    formal = int((snap.get("summary") or {}).get("tested") or 0)
    if formal != int((geo_validation.dashboard().get("official") or {}).get("tested") or 0):
        snap = geo_analysis.refresh(geo_validation.receipts(1000))
    return snap


def _fingerprint(snapshot):
    ids = [str(item.get("evidence_id") or "") for item in snapshot.get("question_results") or []]
    raw = "|".join([str(snapshot.get("analysis_version") or ""), *sorted(ids)])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()[:20]


def _question_for_gap(snapshot, code):
    for item in snapshot.get("question_results") or []:
        if any(str(gap.get("code") or "") == code for gap in item.get("gaps") or []):
            return item
    return {}


def _advisory(snapshot):
    saved = geo_chatgpt_analyzer.snapshot()
    if not isinstance(saved, dict) or not isinstance(saved.get("analysis"), dict):
        return {}
    if int(saved.get("official_evidence_count") or 0) != len(snapshot.get("question_results") or []):
        return {}
    return saved


def _action_rows(snapshot):
    summary = snapshot.get("summary") or {}
    advisory = _advisory(snapshot)
    advisory_actions = list(((advisory.get("analysis") or {}).get("candidate_actions") or []))
    rows = []
    for index, gap in enumerate((summary.get("gaps") or [])[:MAX_ACTIONS]):
        code = str(gap.get("code") or "")
        template = GAP_ACTIONS.get(code, {
            "title": "处理 GEO 可见度缺口",
            "task_type": "geo",
            "keyword_suffix": "本地服务信息",
            "reason": str(gap.get("label") or code or "GEO缺口"),
        })
        question = _question_for_gap(snapshot, code)
        service = str(question.get("service") or "综合维修")
        region = str(question.get("region") or "涟水县")
        keyword = f"{region}{service}{template['keyword_suffix']}"
        advisory_row = advisory_actions[index] if index < len(advisory_actions) and isinstance(advisory_actions[index], dict) else {}
        action_title = str(advisory_row.get("action") or template["title"])
        why = str(advisory_row.get("why") or template["reason"])
        rows.append({
            "action_id": f"GEO3-A{index+1:02d}-{code or 'gap'}",
            "gap_code": code,
            "gap_label": str(gap.get("label") or code),
            "severity": str(gap.get("severity") or "medium"),
            "count": int(gap.get("count") or 0),
            "title": action_title[:160],
            "why": why[:500],
            "task_type": template["task_type"],
            "question_id": str(question.get("question_id") or ""),
            "question_text": str(question.get("question_text") or gap.get("example_question") or ""),
            "region": region,
            "service": service,
            "intent": str(question.get("intent") or ""),
            "keyword": keyword[:120],
            "baseline_score": int(question.get("visibility_score") or 0),
            "baseline_evidence_id": str(question.get("evidence_id") or ""),
            "job_id": "",
            "opportunity_id": "",
            "job_state": "not_dispatched",
            "retest_task_id": "",
            "retest_evidence_id": "",
            "after_score": None,
            "delta": None,
        })
    return rows, advisory


def plan(force=False):
    data = _load()
    snapshot = _analysis()
    tested = int((snapshot.get("summary") or {}).get("tested") or 0)
    if tested <= 0:
        raise ValueError("Phase 3 需要至少 1 条真实 A/B GEO Evidence")
    fingerprint = _fingerprint(snapshot)
    current = data.get("plan") or {}
    if current and current.get("source_fingerprint") == fingerprint and not force:
        return current
    actions, advisory = _action_rows(snapshot)
    if not actions:
        raise ValueError("当前真实A/B证据没有可执行GEO缺口")
    authorization = active_authorization()
    plan_value = {
        "plan_id": f"GEO3-{fingerprint.upper()}",
        "source_fingerprint": fingerprint,
        "source_analysis_version": snapshot.get("analysis_version"),
        "baseline_at": now_iso(),
        "baseline_formal_count": tested,
        "baseline_summary": deepcopy(snapshot.get("summary") or {}),
        "controller": "chatgpt",
        "decision_source": "chatgpt_advisory" if advisory else "deterministic_gap_candidates_waiting_controller",
        "chatgpt_advisory_response_id": str(advisory.get("response_id") or ""),
        "authorization": deepcopy(authorization or {}),
        "authorization_mode": "chatgpt_command" if authorization else "waiting",
        "status": "authorized" if authorization else "waiting_authorization",
        "actions": actions,
        "created_at": now_iso(),
        "execution_started_at": "",
        "execution_completed_at": "",
        "retest_queued_at": "",
        "completed_at": "",
        "seo_cycle": {},
        "before_after": [],
        "outcome": "pending",
    }
    if current:
        data["history"].insert(0, current)
    data["plan"] = plan_value
    _save(data)
    return plan_value


def authorize(owner_approved=False):
    data = _load()
    current = data.get("plan") or plan()
    authorization = active_authorization()
    if authorization:
        current["authorization"] = deepcopy(authorization)
        current["authorization_mode"] = "chatgpt_command"
        current["status"] = "authorized"
    elif owner_approved:
        current["authorization"] = {"source": "owner_explicit", "approved_at": now_iso()}
        current["authorization_mode"] = "owner_explicit"
        current["status"] = "authorized"
    else:
        raise PermissionError("等待已验证 ChatGPT Command；也可由老板在界面明确批准本轮非资金 GEO 优化")
    data["plan"] = current
    _save(data)
    return current


def _job_map():
    return {str(item.get("id") or ""): item for item in list_jobs().get("items") or []}


def _action_context(action):
    return {
        "region": action.get("region") or "涟水县",
        "service": action.get("service") or "综合维修",
        "keyword": action.get("keyword") or "涟水县本地维修服务",
        "audience": "涟水县有维修、安装或社区生活服务需求的本地用户",
        "evidence": f"来源于真实GEO Evidence {action.get('baseline_evidence_id') or '未知'}；缺口：{action.get('gap_label') or action.get('gap_code')}",
        "geo_gap_code": action.get("gap_code") or "",
        "geo_question_id": action.get("question_id") or "",
    }


def dispatch(owner_approved=False):
    data = _load()
    current = data.get("plan") or plan()
    if current.get("status") == "waiting_authorization":
        current = authorize(owner_approved=owner_approved)
        data = _load()
    auth = current.get("authorization") or {}
    mode = str(current.get("authorization_mode") or "")
    mission_id = str(auth.get("mission_id") or "")
    command_id = str(auth.get("command_id") or "")
    schedule_source = "geo_phase3" if mode == "chatgpt_command" else "geo_phase3_owner"
    created = []
    for action in current.get("actions") or []:
        if action.get("job_id"):
            continue
        opportunity = seo_geo_growth.upsert_opportunity({
            "region": action.get("region"),
            "service": action.get("service"),
            "keyword": action.get("keyword"),
            "intent": action.get("intent") or "GEO缺口修复",
            "priority": "S",
            "source": f"GEO Phase 3 · {action.get('gap_code')}",
            "source_ref": action.get("baseline_evidence_id"),
        })
        title = f"GEO Phase 3｜{action.get('title')}｜{action.get('service')}"
        job = create_job({
            "kind": "manual_task",
            "title": title[:160],
            "context": _action_context(action),
            "schedule_source": schedule_source,
            "source_ref": current.get("plan_id"),
            "mission_id": mission_id,
            "command_id": command_id,
        })
        action["job_id"] = job.get("id") or ""
        action["opportunity_id"] = opportunity.get("id") or ""
        action["job_state"] = job.get("state") or "queued"
        created.append(job.get("id"))
    current["execution_started_at"] = current.get("execution_started_at") or now_iso()
    current["status"] = "executing"
    current["dispatched_job_ids"] = [x for x in created if x]
    data["plan"] = current
    _save(data)
    run_due_jobs()
    return sync()


def _stage_rank(stage):
    order = {name: index for index, name in enumerate(seo_geo_growth.STAGES)}
    return order.get(str(stage or "DISCOVERED"), 0)


def _publish_state(current):
    snap = seo_geo_growth.dashboard()
    opportunities = {str(x.get("id") or ""): x for x in snap.get("opportunities") or []}
    assets = {str(x.get("id") or ""): x for x in snap.get("assets") or []}
    rows = []
    for action in current.get("actions") or []:
        opp = opportunities.get(str(action.get("opportunity_id") or ""), {})
        asset = assets.get(str(opp.get("asset_id") or ""), {}) if opp else {}
        rows.append({
            "action_id": action.get("action_id"),
            "opportunity_id": action.get("opportunity_id"),
            "asset_id": asset.get("id") or "",
            "stage": asset.get("stage") or opp.get("status") or "DISCOVERED",
            "public_url": asset.get("public_url") or "",
        })
    return rows


def _eligible_retest_questions(current):
    return [x.get("question_id") for x in current.get("actions") or [] if x.get("question_id")]


def _queue_retest(current, force=False):
    if current.get("retest_queued_at"):
        return current
    publish_rows = _publish_state(current)
    if not force and (not publish_rows or not all(_stage_rank(x.get("stage")) >= _stage_rank("PUBLISHED") for x in publish_rows)):
        current["publish_state"] = publish_rows
        current["status"] = "waiting_publish"
        return current
    qids = list(dict.fromkeys(_eligible_retest_questions(current)))[:MAX_ACTIONS]
    queue = geo_validation.queue_summary().get("tasks") or []
    reused = []
    missing = []
    for qid in qids:
        candidate = next((x for x in queue if x.get("question_id") == qid and x.get("test_method") == "browser" and x.get("state") in {"queued", "paused", "authorization_required"}), None)
        if candidate:
            reused.append(candidate)
        else:
            missing.append(qid)
    created = []
    if missing:
        result = geo_validation.create_and_enqueue_plan(
            limit=len(missing),
            provider="browser_external_ai",
            test_method="browser",
            question_ids=missing,
        )
        created = list(result.get("tasks") or [])
    task_by_qid = {x.get("question_id"): x for x in reused + created}
    for action in current.get("actions") or []:
        task = task_by_qid.get(action.get("question_id"))
        if task:
            action["retest_task_id"] = task.get("task_id") or ""
    current["retest_queued_at"] = now_iso()
    current["publish_state"] = publish_rows
    current["status"] = "waiting_retest"
    return current


def _latest_retest_receipt(qid, since):
    rows = [
        item for item in geo_validation.receipts(1000)
        if item.get("question_id") == qid
        and item.get("official_truth")
        and item.get("evidence_level") in geo_validation.OFFICIAL_EVIDENCE_LEVELS
        and str(item.get("tested_at") or item.get("finished_at") or "") > str(since or "")
    ]
    rows.sort(key=lambda x: str(x.get("tested_at") or x.get("finished_at") or ""), reverse=True)
    return rows[0] if rows else None


def _before_after(current):
    rows = []
    for action in current.get("actions") or []:
        qid = action.get("question_id")
        if not qid:
            continue
        receipt = _latest_retest_receipt(qid, current.get("execution_started_at") or current.get("baseline_at"))
        if not receipt:
            continue
        analysed = geo_analysis.analyze_receipt(receipt)
        before = int(action.get("baseline_score") or 0)
        after = int(analysed.get("visibility_score") or 0)
        action["retest_evidence_id"] = receipt.get("evidence_id") or receipt.get("receipt_id") or ""
        action["after_score"] = after
        action["delta"] = after - before
        rows.append({
            "question_id": qid,
            "action_id": action.get("action_id"),
            "before": before,
            "after": after,
            "delta": after - before,
            "before_evidence_id": action.get("baseline_evidence_id"),
            "after_evidence_id": action.get("retest_evidence_id"),
            "brand_before": before > 0,
            "brand_after": bool(analysed.get("brand_mentioned")),
        })
    return rows


def sync(force_retest=False):
    data = _load()
    current = data.get("plan") or {}
    if not current:
        return status()
    jobs = _job_map()
    job_states = []
    for action in current.get("actions") or []:
        job = jobs.get(str(action.get("job_id") or ""), {})
        if job:
            action["job_state"] = job.get("state") or action.get("job_state")
            action["job_result"] = deepcopy(job.get("result") or {})
        job_states.append(action.get("job_state"))
    if job_states and all(state == "completed" for state in job_states):
        current["execution_completed_at"] = current.get("execution_completed_at") or now_iso()
        current = _queue_retest(current, force=force_retest)
    rows = _before_after(current)
    current["before_after"] = rows
    expected = len([x for x in current.get("actions") or [] if x.get("question_id")])
    if expected and len(rows) >= expected:
        deltas = [int(x.get("delta") or 0) for x in rows]
        total = sum(deltas)
        current["outcome"] = "improved" if total > 0 else "regressed" if total < 0 else "neutral"
        current["status"] = "completed"
        current["completed_at"] = current.get("completed_at") or now_iso()
    data["plan"] = current
    _save(data)
    return status()


def run_once(owner_approved=False):
    data = _load()
    if not data.get("enabled"):
        return {"skipped": True, "reason": "phase3_disabled", "status": status()}
    current = data.get("plan") or {}
    if not current:
        try:
            current = plan()
        except ValueError as error:
            return {"skipped": True, "reason": str(error), "status": status()}
    if current.get("status") == "waiting_authorization":
        if active_authorization() or owner_approved:
            return {"skipped": False, "result": dispatch(owner_approved=owner_approved), "status": status()}
        return {"skipped": True, "reason": "waiting_chatgpt_or_owner_authorization", "status": status()}
    if current.get("status") == "authorized":
        return {"skipped": False, "result": dispatch(owner_approved=owner_approved), "status": status()}
    run_due_jobs()
    return {"skipped": False, "result": sync(), "status": status()}


def status():
    data = _load()
    current = deepcopy(data.get("plan") or {})
    analysis = _analysis()
    formal = int((analysis.get("summary") or {}).get("tested") or 0)
    current_jobs = _job_map()
    if current:
        for action in current.get("actions") or []:
            job = current_jobs.get(str(action.get("job_id") or ""), {})
            if job:
                action["job_state"] = job.get("state") or action.get("job_state")
    return {
        "schema": SCHEMA,
        "enabled": bool(data.get("enabled")),
        "phase2": {
            "formal_evidence": formal,
            "analysis_ready": formal > 0,
            "software_remaining": ["live_cloud_1_3_10_50_field_acceptance"],
            "code_state": "closed_candidate",
        },
        "plan": current,
        "authorization": active_authorization(),
        "truth_rule": "Phase 3 只优化内容与公开页面；正式成效必须等待新的真实A/B GEO Evidence，再做 Before/After。普通豆包API C级回答永不升级为正式成绩。",
        "history_count": len(data.get("history") or []),
        "updated_at": data.get("updated_at") or "",
    }
