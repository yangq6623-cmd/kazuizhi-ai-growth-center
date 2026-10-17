"""R8-23.2 Pilot: runtime truth, model routing, queue explainability and readiness.

This module does not weaken any earlier truth gate. It converges the owner-facing
runtime around one current Command/Mission/Plan view and makes model/tool use
explicit:
- ChatGPT is the strategic controller.
- Local model / RTX 3060 are the default high-frequency execution path.
- Doubao is mandatory on SEO/GEO critical semantic work, and an enhancer/fallback
  elsewhere. Ordinary model output remains C-level auxiliary evidence.
- External success still requires real URL/Post ID/Search Receipt/formal GEO A/B
  Evidence/business evidence.
- Funds remain human-only.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta

from core.storage import now_iso

PILOT_VERSION = "R8-23.2 Pilot"
CONTRACT_VERSION = "kazuizhi.runtime-truth.v1"
DECISION_PACK_TTL_HOURS = 24

RECEIPT_STAGES = (
    "configured", "invoked", "generated", "qc_passed", "published",
    "submitted", "crawled", "indexed", "external_verified",
)

HUMAN_ONLY_MARKERS = (
    "验证码", "人脸", "实名", "付款", "退款", "提现", "结算", "充值", "赔付",
    "资金", "改价", "账号安全", "核心权限", "不可逆", "删除账号",
)
OPTIONAL_EXTERNAL_MARKERS = (
    "抖音", "视频号", "小红书", "快手", "b站", "微博", "社媒", "手机离线",
)

SEO_GEO_DOUABO_REQUIRED = {
    "seo_keyword_intent", "seo_high_value_content", "seo_semantic_qc",
    "seo_refresh", "geo_question_expansion", "geo_gap_analysis",
    "geo_content_enhancement", "geo_semantic_qc",
}


def _parse_time(value):
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def release_manifest() -> dict:
    """One owner-facing runtime identity contract.

    The legacy R8 runtime identity is intentionally preserved for compatibility;
    the phase label is R8-23.2 Pilot.
    """
    return {
        "contract": CONTRACT_VERSION,
        "product": "Kazuizhi AI Enterprise",
        "runtime_identity": "KZ-ENTERPRISE-V2.2.2-R8-AUTONOMOUS-20260922",
        "phase": PILOT_VERSION,
        "frontend_compatibility": "R8-17",
        "truth_policy": "configured != invoked != external_success",
        "outcome_scope": "site_visit -> mini_program_visit -> consultation -> task -> order",
        "funds_policy": "human_only",
        "generated_at": now_iso(),
    }


def _convergence_state() -> dict:
    try:
        from core import r8_22_autonomous_convergence as convergence
        state = convergence._load_state()
        return deepcopy(state) if isinstance(state, dict) else {}
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError, AttributeError):
        return {}


def _active_command_link() -> dict:
    try:
        from core import command_execution
        link = command_execution.active_authorization()
        return deepcopy(link) if isinstance(link, dict) else {}
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError, AttributeError):
        return {}


def _active_mission() -> dict:
    try:
        from core import autonomous_ops
        snap = autonomous_ops.snapshot(sync=False)
        row = snap.get("active_mission") if isinstance(snap, dict) else {}
        return deepcopy(row) if isinstance(row, dict) else {}
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError, AttributeError):
        return {}


def single_truth() -> dict:
    """Canonical current Command -> Mission -> Plan view used by all new UI/API."""
    state = _convergence_state()
    link = _active_command_link()
    mission = _active_mission()
    command_id = str(state.get("active_command_id") or link.get("command_id") or mission.get("command_id") or "") or None
    mission_id = str(state.get("active_mission_id") or mission.get("mission_id") or link.get("mission_id") or "") or None
    plan = deepcopy(state.get("plan") or {})
    conflicts = []
    for label, value in (
        ("link.command_id", link.get("command_id")),
        ("mission.command_id", mission.get("command_id")),
    ):
        if command_id and value and str(value) != str(command_id):
            conflicts.append({"field": label, "expected": command_id, "actual": value})
    if mission_id and link.get("mission_id") and str(link.get("mission_id")) != str(mission_id):
        conflicts.append({"field": "link.mission_id", "expected": mission_id, "actual": link.get("mission_id")})
    return {
        "contract": CONTRACT_VERSION,
        "command_id": command_id,
        "mission_id": mission_id,
        "command_status": link.get("status") or mission.get("command_status"),
        "objective": link.get("objective") or mission.get("command_objective") or mission.get("objective"),
        "plan": plan,
        "conflicts": conflicts,
        "consistent": not conflicts,
        "generated_at": now_iso(),
    }


def decision_pack() -> dict:
    truth = single_truth()
    link = _active_command_link()
    created_at = link.get("created_at") or now_iso()
    created = _parse_time(created_at)
    expires = created + timedelta(hours=DECISION_PACK_TTL_HOURS) if created else None
    now = datetime.now().astimezone()
    if expires is not None and expires.tzinfo is None:
        expires = expires.astimezone()
    valid = bool(truth.get("command_id") and truth.get("mission_id") and truth.get("consistent"))
    if expires is not None and now > expires:
        valid = False
    return {
        "decision_pack_id": f"DP-{truth.get('command_id') or 'UNBOUND'}",
        "command_id": truth.get("command_id"),
        "mission_id": truth.get("mission_id"),
        "objective": truth.get("objective"),
        "issued_at": created_at,
        "expires_at": expires.isoformat() if expires else None,
        "ttl_hours": DECISION_PACK_TTL_HOURS,
        "valid": valid,
        "allowed": [
            "local_model", "rtx3060", "doubao_cloud", "seo_website",
            "search_submission", "formal_geo_browser", "authorized_remote_agent",
            "graded_social_distribution", "read_only_business_data",
        ],
        "prohibited": ["payment", "refund", "withdrawal", "settlement", "price_change", "funds"],
        "fallback": "continue_last_valid_non_financial_plan_and_defer_unavailable_capability",
        "required_return": ["task_receipt", "external_receipt_when_applicable", "evidence_when_applicable"],
        "generated_at": now_iso(),
    }


def model_route(task_kind: str = "general", *, local_quality: float | None = None) -> dict:
    """Task-type routing; no fixed model percentage is imposed."""
    kind = str(task_kind or "general").strip().lower()
    critical = kind in SEO_GEO_DOUABO_REQUIRED or kind.startswith("seo_critical") or kind.startswith("geo_critical")
    if critical:
        route = ["local_model", "doubao_cloud"]
        reason = "SEO/GEO关键语义节点：本地先处理，豆包必须参与增强/复核。"
        doubao_required = True
    elif local_quality is not None and float(local_quality) < 70:
        route = ["local_model", "doubao_cloud"]
        reason = "本地质量低于70分，升级豆包增强。"
        doubao_required = True
    elif local_quality is not None and float(local_quality) < 85:
        route = ["local_model", "local_model_retry", "doubao_cloud_if_still_below_threshold"]
        reason = "本地质量70-84分，先本地重试，仍不足再升级豆包。"
        doubao_required = False
    else:
        route = ["local_model"]
        reason = "高频低风险任务默认本地模型/RTX3060优先。"
        doubao_required = False
    return {
        "task_kind": kind,
        "route": route,
        "doubao_required": doubao_required,
        "chatgpt_role": "strategic_controller_only",
        "formal_evidence_rule": "local/doubao outputs are C-level auxiliary unless independently verified by the formal truth gate",
        "reason": reason,
    }


def queue_diagnostics() -> dict:
    items = []
    try:
        from core import r7_engine
        jobs = r7_engine.list_jobs().get("items", [])
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError, AttributeError):
        jobs = []
    now = datetime.now().astimezone()
    for job in jobs:
        if not isinstance(job, dict) or job.get("state") != "queued":
            continue
        due = _parse_time(job.get("due_at"))
        if due is not None and due.tzinfo is None:
            due = due.astimezone()
        if job.get("authorization_state") == "waiting_for_chatgpt":
            reason = "等待有效Decision Pack/Command绑定"
        elif due and due > now:
            reason = "等待计划时间"
        elif job.get("dependency_state") in {"waiting", "blocked"}:
            reason = "等待依赖"
        else:
            reason = "已到期，等待Worker领取"
        overdue_minutes = 0
        if due and due < now:
            overdue_minutes = max(0, int((now - due).total_seconds() // 60))
        items.append({
            "id": job.get("id"), "title": job.get("title"), "reason": reason,
            "due_at": job.get("due_at"), "overdue_minutes": overdue_minutes,
            "retry_count": int(job.get("retry_count") or 0),
            "command_id": job.get("command_id"), "mission_id": job.get("mission_id"),
            "priority_class": job.get("priority_class"),
            "timed_out": overdue_minutes >= 30 and reason == "已到期，等待Worker领取",
        })
    items.sort(key=lambda x: (not x.get("timed_out"), str(x.get("due_at") or "")))
    return {
        "waiting": len(items),
        "timed_out": sum(bool(x.get("timed_out")) for x in items),
        "items": items[:100],
        "generated_at": now_iso(),
    }


def attention_policy(items: list[dict] | None = None) -> dict:
    human, deferred, auto_resolvable = [], [], []
    for item in items or []:
        if not isinstance(item, dict):
            continue
        text = " ".join(str(item.get(k) or "") for k in ("title", "reason", "detail", "action")).lower()
        if any(marker in text for marker in HUMAN_ONLY_MARKERS):
            human.append(item)
        elif any(marker in text for marker in OPTIONAL_EXTERNAL_MARKERS):
            deferred.append({**item, "policy": "defer_optional_channel_continue_core"})
        else:
            auto_resolvable.append({**item, "policy": "controller_or_worker_should_resolve"})
    return {"human": human, "deferred": deferred, "auto_resolvable": auto_resolvable}


def receipt_state(record: dict | None = None) -> dict:
    record = record if isinstance(record, dict) else {}
    reached = []
    for stage in RECEIPT_STAGES:
        if record.get(stage) or record.get(f"{stage}_at") or str(record.get("state") or "") == stage:
            reached.append(stage)
    external = bool(record.get("public_url") or record.get("post_id") or record.get("external_receipt_id") or record.get("formal_evidence_id"))
    if external and "external_verified" not in reached and record.get("external_verified"):
        reached.append("external_verified")
    return {
        "stages": list(RECEIPT_STAGES),
        "reached": reached,
        "highest_stage": reached[-1] if reached else None,
        "external_proof_present": external,
        "truth": "调用成功不是外部成功；外部结果必须有真实URL/Post ID/Search Receipt/Formal GEO Evidence/经营证据。",
    }


def readiness() -> dict:
    truth = single_truth()
    pack = decision_pack()
    queue = queue_diagnostics()
    blockers = []
    warnings = []
    if not truth.get("consistent"):
        blockers.append("command_mission_truth_conflict")
    if not pack.get("valid"):
        blockers.append("decision_pack_invalid_or_expired")
    if queue.get("timed_out"):
        warnings.append("queued_jobs_overdue")
    state = "READY"
    if blockers:
        state = "BLOCKED"
    elif warnings:
        state = "DEGRADED"
    return {
        "state": state,
        "blockers": blockers,
        "warnings": warnings,
        "single_truth": truth,
        "decision_pack": pack,
        "queue": {"waiting": queue.get("waiting"), "timed_out": queue.get("timed_out")},
        "model_policy": {
            "chatgpt": "strategic_controller",
            "local_model": "preferred_high_frequency_executor",
            "rtx3060": "preferred_local_compute",
            "doubao": "mandatory_for_seo_geo_critical_semantic_steps_and_quality_escalation",
        },
        "field_acceptance_remaining": ["24h_unattended", "72h_fault_recovery", "7d_production_soak"],
        "generated_at": now_iso(),
    }


def snapshot() -> dict:
    return {
        "release": release_manifest(),
        "truth": single_truth(),
        "decision_pack": decision_pack(),
        "queue": queue_diagnostics(),
        "readiness": readiness(),
        "model_routes": {
            "general": model_route("general"),
            "seo_keyword_intent": model_route("seo_keyword_intent"),
            "geo_gap_analysis": model_route("geo_gap_analysis"),
            "seo_semantic_qc": model_route("seo_semantic_qc"),
        },
        "generated_at": now_iso(),
    }
