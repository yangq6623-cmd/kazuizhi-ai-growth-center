"""R8-23.3 Candidate: runtime execution recovery and owner-facing truth convergence.

This release fixes field-observed Pilot issues without adding product scope:
- the current authorized Command is distinguished from a newer pending owner Command;
- Decision Pack authority is a rolling control lease refreshed by real controller receipts,
  instead of expiring forever 24 hours after the original Command was created;
- due queued work is explained and overdue execution stalls are surfaced as blockers;
- human attention is separated from auto-resolvable/deferred external work;
- all existing formal GEO, external Receipt and finance boundaries remain unchanged.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta

from core.storage import now_iso
from core import r8_23_2_runtime_truth as pilot

CANDIDATE_VERSION = "R8-23.3 Candidate"
CONTRACT_VERSION = "kazuizhi.runtime-truth.v1.1"
CONTROL_LEASE_HOURS = 24
EXECUTION_STALL_MINUTES = 10

_AUTHORIZED_STATUSES = {"accepted", "completed", "running", "acknowledged"}
_PENDING_STATUSES = {"queued_for_verified_connector", "queued", "pending", "received"}


def _parse_time(value):
    text = str(value or "").strip()
    if not text:
        return None
    try:
        value = datetime.fromisoformat(text.replace("Z", "+00:00"))
        return value.astimezone() if value.tzinfo else value.astimezone()
    except ValueError:
        return None


def _latest_time(*values):
    parsed = [value for value in (_parse_time(x) for x in values) if value is not None]
    return max(parsed) if parsed else None


def release_manifest():
    manifest = dict(pilot.release_manifest())
    manifest.update({
        "contract": CONTRACT_VERSION,
        "phase": CANDIDATE_VERSION,
        "candidate_scope": "runtime_execution_and_ui_convergence",
        "runtime_identity": "KZ-ENTERPRISE-V2.2.2-R8-AUTONOMOUS-20260922",
        "truth_policy": "configured != invoked != published != crawled != indexed != formal_external_evidence",
        "funds_policy": "human_only",
        "generated_at": now_iso(),
    })
    return manifest


def _links():
    try:
        from core import command_execution
        rows = command_execution.command_links(200)
        return [deepcopy(x) for x in rows if isinstance(x, dict)]
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError, AttributeError):
        return []


def _authorized(link):
    if str(link.get("status") or "") not in _AUTHORIZED_STATUSES or not link.get("command_id"):
        return False
    try:
        from core import command_execution
        return bool(command_execution._control_state().get("verified"))
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError, AttributeError):
        return False


def _active_link():
    for link in _links():
        if _authorized(link):
            return link
    return {}


def _pending_link(active_command_id=None):
    active = str(active_command_id or "")
    for link in _links():
        command_id = str(link.get("command_id") or "")
        if not command_id or command_id == active:
            continue
        if str(link.get("status") or "") in _PENDING_STATUSES:
            return link
    return {}


def _state():
    try:
        from core import r8_22_autonomous_convergence as convergence
        row = convergence._load_state()
        return deepcopy(row) if isinstance(row, dict) else {}
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError, AttributeError):
        return {}


def _mission():
    try:
        from core import autonomous_ops
        snap = autonomous_ops.snapshot(sync=False)
        row = snap.get("active_mission") if isinstance(snap, dict) else {}
        return deepcopy(row) if isinstance(row, dict) else {}
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError, AttributeError):
        return {}


def single_truth():
    state = _state()
    active = _active_link()
    mission = _mission()
    state_command = str(state.get("active_command_id") or "")
    link_command = str(active.get("command_id") or "")
    mission_command = str(mission.get("command_id") or "")
    command_id = state_command or link_command or mission_command or None
    mission_id = str(state.get("active_mission_id") or mission.get("mission_id") or active.get("mission_id") or "") or None
    plan = deepcopy(state.get("plan") or {})
    conflicts = []
    for label, value in (("authorization.command_id", link_command), ("mission.command_id", mission_command)):
        if command_id and value and value != command_id:
            conflicts.append({"field": label, "expected": command_id, "actual": value})
    if mission_id and active.get("mission_id") and str(active.get("mission_id")) != mission_id:
        conflicts.append({"field": "authorization.mission_id", "expected": mission_id, "actual": active.get("mission_id")})
    if plan:
        if command_id and plan.get("command_id") and str(plan.get("command_id")) != command_id:
            conflicts.append({"field": "plan.command_id", "expected": command_id, "actual": plan.get("command_id")})
        if mission_id and plan.get("mission_id") and str(plan.get("mission_id")) != mission_id:
            conflicts.append({"field": "plan.mission_id", "expected": mission_id, "actual": plan.get("mission_id")})
    pending = _pending_link(command_id)
    return {
        "contract": CONTRACT_VERSION,
        "command_id": command_id,
        "active_command_id": command_id,
        "active_command_status": active.get("status") or mission.get("command_status"),
        "active_command_receipt_id": active.get("control_receipt_id"),
        "pending_command_id": pending.get("command_id"),
        "pending_command_status": pending.get("status"),
        "pending_command_created_at": pending.get("created_at"),
        "pending_explanation": "等待ChatGPT控制通道确认后才会接管当前Mission" if pending else None,
        "mission_id": mission_id,
        "plan": plan,
        "objective": active.get("objective") or mission.get("command_objective") or mission.get("goal"),
        "conflicts": conflicts,
        "consistent": bool(command_id and mission_id and not conflicts),
        "truth_note": "执行中的Command与待确认新Command分开显示；待确认Command不能冒充当前执行权。",
        "generated_at": now_iso(),
    }


def controller_lease():
    truth = single_truth()
    state = _state()
    active = _active_link()
    refreshed = _latest_time(
        state.get("last_phase_receipt_at"),
        state.get("updated_at"),
        active.get("created_at"),
    )
    expires = refreshed + timedelta(hours=CONTROL_LEASE_HOURS) if refreshed else None
    now = datetime.now().astimezone()
    valid = bool(truth.get("consistent") and active and refreshed and expires and now <= expires)
    return {
        "lease_id": f"LEASE-{truth.get('active_command_id') or 'UNBOUND'}",
        "command_id": truth.get("active_command_id"),
        "mission_id": truth.get("mission_id"),
        "refreshed_at": refreshed.isoformat() if refreshed else None,
        "expires_at": expires.isoformat() if expires else None,
        "ttl_hours": CONTROL_LEASE_HOURS,
        "remaining_minutes": max(0, int((expires - now).total_seconds() // 60)) if expires else 0,
        "valid": valid,
        "refresh_source": "controller_phase_receipt_or_convergence_state",
        "policy": "持续运行且真实控制回执正常时滚动续租；离线超过24小时或Command/Mission冲突则阻断。",
    }


def decision_pack():
    truth = single_truth()
    lease = controller_lease()
    return {
        "decision_pack_id": f"DP-{truth.get('active_command_id') or 'UNBOUND'}",
        "command_id": truth.get("active_command_id"),
        "mission_id": truth.get("mission_id"),
        "plan_id": (truth.get("plan") or {}).get("plan_id"),
        "objective": truth.get("objective"),
        "issued_at": (_active_link() or {}).get("created_at"),
        "lease_refreshed_at": lease.get("refreshed_at"),
        "expires_at": lease.get("expires_at"),
        "ttl_hours": CONTROL_LEASE_HOURS,
        "valid": bool(lease.get("valid")),
        "allowed": [
            "local_model", "rtx3060", "doubao_cloud", "seo_website", "search_submission",
            "formal_geo_browser", "authorized_remote_agent", "graded_social_distribution", "read_only_business_data",
        ],
        "prohibited": ["payment", "refund", "withdrawal", "settlement", "price_change", "funds"],
        "model_policy": {
            "local": "preferred_high_frequency_executor",
            "doubao": "required_on_seo_geo_critical_semantic_steps",
            "chatgpt": "strategy_priority_review_and_replanning",
        },
        "formal_evidence_rule": "本地模型和豆包普通调用均为C级辅助；正式GEO只认真实外部A/B Evidence。",
        "required_return": ["task_receipt", "external_receipt_when_applicable", "evidence_when_applicable"],
        "generated_at": now_iso(),
    }


def queue_diagnostics():
    try:
        from core import r7_engine
        jobs = r7_engine.list_jobs().get("items", [])
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError, AttributeError):
        jobs = []
    truth = single_truth()
    current_command = str(truth.get("active_command_id") or "")
    current_mission = str(truth.get("mission_id") or "")
    now = datetime.now().astimezone()
    waiting = []
    running = []
    current_completed = 0
    historical_backlog = 0
    for job in jobs:
        if not isinstance(job, dict):
            continue
        belongs = bool(
            (current_command and str(job.get("command_id") or "") == current_command)
            or (current_mission and str(job.get("mission_id") or "") == current_mission)
        )
        state = str(job.get("state") or "")
        if not belongs:
            if state == "queued":
                historical_backlog += 1
            continue
        if state == "completed":
            current_completed += 1
            continue
        if state == "running":
            running.append({"id": job.get("id"), "title": job.get("title"), "updated_at": job.get("updated_at")})
            continue
        if state != "queued":
            continue
        due = _parse_time(job.get("due_at"))
        if job.get("authorization_state") == "waiting_for_chatgpt":
            reason = "等待有效控制租约/Command绑定"
        elif due and due > now:
            reason = "等待计划时间"
        elif job.get("dependency_state") in {"waiting", "blocked"}:
            reason = "等待依赖"
        else:
            reason = "已到期，等待Worker领取"
        overdue_minutes = max(0, int((now - due).total_seconds() // 60)) if due and due < now else 0
        timed_out = bool(overdue_minutes >= EXECUTION_STALL_MINUTES and reason == "已到期，等待Worker领取")
        waiting.append({
            "id": job.get("id"), "title": job.get("title"), "reason": reason,
            "due_at": job.get("due_at"), "overdue_minutes": overdue_minutes,
            "timed_out": timed_out, "authorization_state": job.get("authorization_state"),
            "task_type": job.get("task_type"), "priority_class": job.get("priority_class"),
            "retry_count": int(job.get("retry_count") or 0),
            "next_action": "Worker自动领取" if reason == "已到期，等待Worker领取" else reason,
        })
    waiting.sort(key=lambda x: (not x.get("timed_out"), str(x.get("due_at") or "")))
    timed_out = sum(bool(x.get("timed_out")) for x in waiting)
    return {
        "waiting": len(waiting),
        "running": len(running),
        "completed_current_mission": current_completed,
        "timed_out": timed_out,
        "execution_stalled": bool(timed_out and not running),
        "historical_backlog": historical_backlog,
        "items": waiting[:100],
        "running_items": running[:50],
        "scope": "current_mission_only",
        "generated_at": now_iso(),
    }


def attention_summary():
    raw = []
    try:
        from core.autonomy import human_interventions
        value = human_interventions()
        raw.extend(value.get("items", []) if isinstance(value, dict) else [])
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError, AttributeError):
        pass
    human, deferred, auto = [], [], []
    policy = pilot.attention_policy(raw)
    human.extend(policy.get("human") or [])
    deferred.extend(policy.get("deferred") or [])
    auto.extend(policy.get("auto_resolvable") or [])
    try:
        from core import r8_22_autonomous_convergence as convergence
        conv_human, conv_deferred = convergence._human_and_deferred()
        for item in conv_human:
            if item not in human:
                human.append(item)
        for item in conv_deferred:
            if item not in deferred:
                deferred.append(item)
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError, AttributeError):
        pass
    return {
        "human_required": human[:50],
        "human_count": len(human),
        "deferred_external": deferred[:50],
        "deferred_count": len(deferred),
        "auto_resolvable": auto[:50],
        "auto_count": len(auto),
        "owner_badge_count": len(human),
        "rule": "老板入口只显示真人必须处理事项；计划生成、普通SEO/GEO推进由控制器和Worker自行解决。",
        "generated_at": now_iso(),
    }


def readiness():
    truth = single_truth()
    lease = controller_lease()
    queue = queue_diagnostics()
    blockers = []
    warnings = []
    if not truth.get("consistent"):
        blockers.append({"code": "COMMAND_MISSION_TRUTH_CONFLICT", "label": "当前Command/Mission/Plan不一致"})
    if not lease.get("valid"):
        blockers.append({"code": "CONTROL_LEASE_INVALID", "label": "Decision Pack控制租约无效或已过期"})
    if queue.get("execution_stalled"):
        blockers.append({"code": "DUE_JOB_EXECUTION_STALL", "label": f"{queue.get('timed_out')}个当前Mission到期任务未被Worker领取"})
    elif queue.get("timed_out"):
        warnings.append({"code": "OVERDUE_QUEUE", "label": f"{queue.get('timed_out')}个到期任务等待处理"})
    attention = attention_summary()
    if attention.get("deferred_count"):
        warnings.append({"code": "OPTIONAL_EXTERNAL_DEFERRED", "label": f"{attention.get('deferred_count')}个可选外部渠道等待验证，不阻断核心SEO/GEO"})
    state = "BLOCKED" if blockers else ("DEGRADED" if warnings else "READY")
    return {
        "state": state,
        "blockers": blockers,
        "warnings": warnings,
        "single_truth": truth,
        "control_lease": lease,
        "queue": {
            "waiting": queue.get("waiting"), "running": queue.get("running"),
            "timed_out": queue.get("timed_out"), "historical_backlog": queue.get("historical_backlog"),
        },
        "attention": {"human": attention.get("human_count"), "deferred": attention.get("deferred_count"), "auto": attention.get("auto_count")},
        "model_policy": {
            "chatgpt": "strategic_controller",
            "local_model": "preferred_high_frequency_executor",
            "rtx3060": "preferred_local_compute",
            "doubao": "mandatory_for_seo_geo_critical_semantic_steps_and_quality_escalation",
        },
        "field_acceptance_remaining": ["2h_candidate_smoke", "24h_unattended", "72h_fault_recovery", "7d_production_soak"],
        "generated_at": now_iso(),
    }


def snapshot():
    return {
        "release": release_manifest(),
        "truth": single_truth(),
        "decision_pack": decision_pack(),
        "control_lease": controller_lease(),
        "queue": queue_diagnostics(),
        "attention": attention_summary(),
        "readiness": readiness(),
        "model_routes": {
            "general": pilot.model_route("general"),
            "seo_keyword_intent": pilot.model_route("seo_keyword_intent"),
            "seo_semantic_qc": pilot.model_route("seo_semantic_qc"),
            "geo_gap_analysis": pilot.model_route("geo_gap_analysis"),
            "geo_content_enhancement": pilot.model_route("geo_content_enhancement"),
        },
        "formal_geo_rule": "正式GEO成绩只认真实外部AI/浏览器A/B Evidence；豆包与本地模型不抬分。",
        "generated_at": now_iso(),
    }
