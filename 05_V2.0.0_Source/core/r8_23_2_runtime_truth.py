"""R8-23.2 runtime truth and closed-loop acceptance layer.

This module is deliberately conservative.  It does not replace the R7/R8
workers, SEO/GEO truth gates, public deployer, search submitters or business
metrics.  It provides the canonical identity/control/queue/evidence contract
that those subsystems report into.

Permanent policy:
- ChatGPT is the sole strategic controller and emits a bounded Decision Pack.
- The deterministic local scheduler/workers continue inside that lease even if
  the interactive chat/browser is temporarily unavailable.
- Local model + local GPU are the preferred high-volume execution route.
- Doubao is required for selected high-value SEO/GEO reasoning/QC stages and is
  otherwise an augmentation/fallback route, never formal GEO evidence.
- Configured/called/generated/published/submitted/crawled/indexed/ranked are
  different truth states.  No state may be promoted without its own receipt.
- Funds remain human-only; attribution stops at order.
"""
from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from datetime import datetime, timedelta, timezone
from pathlib import Path

from core.storage import now_iso, read_json, write_json

STATE_FILE = "ops/r8_23_2_runtime_truth.json"
SCHEMA = "kazuizhi.r8_23_2.runtime_truth.v1"
DECISION_TTL_HOURS = 24
STALE_RUNNING_MINUTES = 90
MAX_RECOVERIES = 2

DOUBAO_REQUIRED_STAGES = {
    "seo_keyword_expansion",
    "seo_search_intent",
    "seo_high_value_content",
    "seo_semantic_qc",
    "geo_question_expansion",
    "geo_gap_analysis",
    "geo_content_optimization",
    "geo_semantic_qc",
}
LOCAL_PREFERRED_STAGES = {
    "classify", "deduplicate", "summarize", "log_review", "draft",
    "seo_precheck", "geo_precheck", "receipt_summary", "batch_tagging",
}
HUMAN_ONLY_MARKERS = (
    "资金", "付款", "退款", "提现", "结算", "充值", "赔付", "改价",
    "验证码", "人脸", "实名", "oauth", "登录", "核心权限", "核心授权",
    "不可逆", "删除账号", "账号安全",
)
SYSTEM_OWNED_MARKERS = (
    "等待 chatgpt 总控下达", "等待chatgpt总控下达", "等待 seo/geo 计划",
    "等待seo/geo计划", "等待 controller plan", "等待controller plan",
)

TRUTH_STATES = (
    "CONFIGURED", "INVOKED", "GENERATED", "QC_PASSED", "PUBLISHED",
    "SUBMITTED", "CRAWLED", "INDEXED", "RANKED", "FORMAL_EVIDENCE",
    "BUSINESS_VISIT", "BUSINESS_CONSULTATION", "BUSINESS_TASK", "BUSINESS_ORDER",
)


def _default_state():
    return {
        "schema": SCHEMA,
        "decision_pack": None,
        "events": [],
        "queue": {},
        "recovery": {},
        "last_governance_at": None,
        "updated_at": now_iso(),
    }


def _load():
    data = read_json(STATE_FILE, _default_state())
    if not isinstance(data, dict):
        data = _default_state()
    for key, value in _default_state().items():
        data.setdefault(key, deepcopy(value))
    return data


def _save(data):
    data["schema"] = SCHEMA
    data["updated_at"] = now_iso()
    data["events"] = (data.get("events") or [])[-500:]
    data["queue"] = dict(list((data.get("queue") or {}).items())[-1000:])
    write_json(STATE_FILE, data)
    return data


def _event(data, kind, message, detail=None):
    payload = {
        "at": now_iso(), "kind": str(kind), "message": str(message),
        "detail": deepcopy(detail or {}),
    }
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    payload["id"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]
    data.setdefault("events", []).append(payload)
    return payload


def _dt(value):
    text = str(value or "").strip()
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.astimezone()
        return parsed
    except (TypeError, ValueError):
        return None


def _utcnow():
    return datetime.now(timezone.utc)


def _source_root():
    return Path(__file__).resolve().parents[1]


def release_identity():
    """Read one packaged release identity; no page owns a separate version."""
    path = Path(__file__).with_name("release_manifest.json")
    try:
        manifest = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError):
        manifest = {}
    candidate = manifest.get("runtime") if isinstance(manifest.get("runtime"), dict) else {}
    required = ("product_version", "release", "phase", "runtime_build")
    complete = all(str(candidate.get(key) or manifest.get(key) or "").strip() for key in required)
    return {
        "schema": manifest.get("schema") or "kz.release-manifest.v2",
        "product": manifest.get("product") or "Kazuizhi AI Enterprise",
        "product_version": candidate.get("product_version") or manifest.get("product_version"),
        "release": candidate.get("release") or manifest.get("release"),
        "phase": candidate.get("phase") or manifest.get("phase"),
        "runtime_build": candidate.get("runtime_build") or manifest.get("runtime_build"),
        "build_number": candidate.get("build_number") or manifest.get("build_number"),
        "commit": candidate.get("commit") or manifest.get("commit"),
        "built_at": candidate.get("built_at") or manifest.get("built_at"),
        "api_contract": manifest.get("api_contract") or "r8-23.2/v1",
        "db_schema": manifest.get("db_schema") or "compatible",
        "complete": bool(complete),
        "truth_rule": "所有运行页面/API/安装包必须读取同一 release_manifest；不允许模块自行声明当前版本。",
    }


def canonical_control(reconcile=False):
    """Return the one active Command/Mission/Plan chain.

    reconcile=True is used by the scheduler/controller, not normal UI reads.
    """
    from core import autonomous_ops, r8_22_autonomous_convergence as convergence

    if reconcile:
        mission = convergence.ensure_command_mission() or {}
        plan = convergence.ensure_controller_plan(mission) if mission else {}
    else:
        state = convergence._load_state()
        data = autonomous_ops._load()
        mission = autonomous_ops._find_mission(data, mission_id=state.get("active_mission_id")) or {}
        plan = state.get("plan") if isinstance(state.get("plan"), dict) else {}
        if mission and plan and str(plan.get("mission_id") or "") != str(mission.get("mission_id") or ""):
            plan = {}

    command_id = str(mission.get("command_id") or (plan or {}).get("command_id") or "")
    mission_id = str(mission.get("mission_id") or "")
    plan_id = str((plan or {}).get("plan_id") or "")
    consistent = bool(command_id and mission_id and plan_id and
                      str((plan or {}).get("command_id") or "") == command_id and
                      str((plan or {}).get("mission_id") or "") == mission_id)
    return {
        "command_id": command_id or None,
        "mission_id": mission_id or None,
        "plan_id": plan_id or None,
        "mission": deepcopy(mission),
        "plan": deepcopy(plan or {}),
        "consistent": consistent,
        "truth_rule": "全系统只有一个 active Command；旧 Command 只能作为 SUPERSEDED/FAILED/REPLACED 历史记录。",
    }


def _decision_pack_id(command_id, plan_id):
    raw = f"{command_id}|{plan_id}|r8-23.2"
    return "DP-" + hashlib.sha256(raw.encode("utf-8")).hexdigest()[:12].upper()


def ensure_decision_pack(control=None):
    control = control or canonical_control(reconcile=True)
    if not control.get("consistent"):
        return None
    data = _load()
    existing = data.get("decision_pack") if isinstance(data.get("decision_pack"), dict) else None
    pack_id = _decision_pack_id(control["command_id"], control["plan_id"])
    now = _utcnow()
    if existing and existing.get("decision_pack_id") == pack_id:
        expiry = _dt(existing.get("expires_at"))
        if expiry and expiry.astimezone(timezone.utc) > now:
            return deepcopy(existing)

    created = now_iso()
    expires = (now + timedelta(hours=DECISION_TTL_HOURS)).isoformat()
    plan = control.get("plan") or {}
    pack = {
        "schema": "kazuizhi.decision-pack.v1",
        "decision_pack_id": pack_id,
        "command_id": control["command_id"],
        "mission_id": control["mission_id"],
        "plan_id": control["plan_id"],
        "objective": str(plan.get("objective") or control.get("mission", {}).get("goal") or "")[:2000],
        "created_at": created,
        "expires_at": expires,
        "ttl_hours": DECISION_TTL_HOURS,
        "controller": "ChatGPT sole strategic controller",
        "executor": "deterministic local scheduler/workers",
        "allowed_business_engines": ["repair_services", "personal_tasks"],
        "allowed_ai_employees": [
            "market_intelligence", "seo_geo_growth", "content_operations", "social_operations",
            "video_operations", "local_growth", "conversion", "data_review",
        ],
        "model_policy": {
            "local_model": "preferred_for_high_frequency_low_risk_batch_work",
            "rtx3060": "preferred_local_compute_when_eligible",
            "doubao": "required_for_selected_high_value_seo_geo_stages_and_important_content_qc; otherwise_augmentation_or_fallback",
            "doubao_required_stages": sorted(DOUBAO_REQUIRED_STAGES),
            "formal_geo_rule": "ordinary Doubao/local model output is C-level auxiliary and never formal GEO Evidence",
        },
        "external_policy": {
            "authority": "graded_L1_L4_by_platform_account_action",
            "owned_website": "authorized_low_risk_publish_after_QC_and_real_public_verification",
            "social": "one_real_platform_closed_loop_first_then_copy",
            "funds": "permanently_human_only",
        },
        "success_contract": ["real_receipt_or_evidence_per_promoted_truth_state", "no_fabricated_external_success"],
        "fallback": "if controller transport is unavailable, continue already-authorized non-financial work until TTL; then freeze new strategic expansion and keep health/recovery/read-only monitoring",
    }
    data["decision_pack"] = pack
    _event(data, "decision_pack_issued", "ChatGPT控制租约已生成/续期", {"decision_pack_id": pack_id, "expires_at": expires})
    _save(data)
    return deepcopy(pack)


def decision_pack_status():
    data = _load()
    pack = data.get("decision_pack") if isinstance(data.get("decision_pack"), dict) else None
    if not pack:
        return {"state": "missing", "valid": False, "pack": None}
    expiry = _dt(pack.get("expires_at"))
    valid = bool(expiry and expiry.astimezone(timezone.utc) > _utcnow())
    return {"state": "active" if valid else "expired", "valid": valid, "pack": deepcopy(pack)}


def model_route_for(stage, *, importance="normal", local_ready=True, doubao_ready=True):
    """Task-type routing, never a rigid percentage split."""
    stage = str(stage or "").strip().lower()
    high = str(importance or "normal").lower() in {"high", "critical", "p0", "p1"}
    if stage in DOUBAO_REQUIRED_STAGES:
        if doubao_ready:
            return {"primary": "doubao_cloud", "secondary": "local_model" if local_ready else None,
                    "required": True, "reason": "SEO/GEO关键节点要求豆包参与"}
        return {"primary": "local_model" if local_ready else None, "secondary": None,
                "required": True, "degraded": True, "reason": "豆包关键节点暂不可用，允许本地继续预处理但不得把未复核结果升级为关键完成"}
    if stage in LOCAL_PREFERRED_STAGES or not high:
        if local_ready:
            return {"primary": "local_model", "secondary": "doubao_cloud" if doubao_ready else None,
                    "required": False, "reason": "高频低风险任务本地优先"}
    if doubao_ready:
        return {"primary": "doubao_cloud", "secondary": "local_model" if local_ready else None,
                "required": False, "reason": "复杂/高价值任务云端增强"}
    return {"primary": "local_model" if local_ready else None, "secondary": None,
            "required": False, "degraded": True, "reason": "仅剩可用模型路由"}


def _job_key(job):
    parts = [
        str(job.get("command_id") or ""), str(job.get("mission_id") or ""),
        str(job.get("task_type") or ""), str(job.get("title") or "").strip(),
        str(job.get("due_at") or ""),
    ]
    return hashlib.sha256("|".join(parts).encode("utf-8")).hexdigest()[:24]


def _wait_reason(job, now):
    state = str(job.get("state") or "")
    if state == "running":
        return "running", "正在执行"
    if state != "queued":
        return state or "unknown", "非等待状态"
    due = _dt(job.get("due_at"))
    if due and due > now:
        return "scheduled_time", f"等待计划时间 {due.astimezone().strftime('%m-%d %H:%M')}"
    auth = str(job.get("authorization_state") or "")
    if auth and auth not in {"authorized", "approved"}:
        return "authorization", "等待当前Command授权绑定"
    if int(job.get("retry_count") or 0) > 0:
        return "retry_ready", f"自动重试 {int(job.get('retry_count') or 0)}/2，已到执行时点"
    return "ready", "已到执行时点，等待调度器领取"


def govern_queue():
    """Annotate wait truth, suppress exact duplicates and recover stale local work."""
    from core import r7_engine
    from core.storage import write_json as _write_json

    control = canonical_control(reconcile=True)
    now = datetime.now().astimezone()
    data_state = _load()
    changed = False
    duplicate_suppressed = 0
    stale_recovered = 0
    seen = {}
    queue_snapshot = {}

    with r7_engine.LOCK:
        jobs_data = r7_engine._store()
        for job in jobs_data.get("items", []):
            if not isinstance(job, dict):
                continue
            if job.get("risk") == "financial":
                continue
            key = _job_key(job)
            if not job.get("idempotency_key"):
                job["idempotency_key"] = key
                changed = True

            if job.get("state") == "queued" and key in seen:
                original = seen[key]
                # Exact same command/mission/type/title/due is not useful duplicated work.
                job.update(state="cancelled", error="duplicate_suppressed",
                           duplicate_of=original, updated_at=now_iso())
                duplicate_suppressed += 1
                changed = True
                continue
            if job.get("state") == "queued":
                seen[key] = str(job.get("id") or "")

            if job.get("state") == "running" and job.get("mode") == "local":
                updated = _dt(job.get("updated_at"))
                recoveries = int(job.get("runtime_recovery_count") or 0)
                if updated and now - updated > timedelta(minutes=STALE_RUNNING_MINUTES) and recoveries < MAX_RECOVERIES:
                    job.update(
                        state="queued", error="stale_running_recovered",
                        runtime_recovery_count=recoveries + 1,
                        recovery_reason="进程/Worker长时间无状态更新，安全重入队列",
                        updated_at=now_iso(), progress=0,
                    )
                    stale_recovered += 1
                    changed = True

            reason_code, reason_label = _wait_reason(job, now)
            if job.get("wait_reason_code") != reason_code or job.get("wait_reason") != reason_label:
                job["wait_reason_code"] = reason_code
                job["wait_reason"] = reason_label
                changed = True
            queue_snapshot[str(job.get("id") or key)] = {
                "state": job.get("state"), "wait_reason_code": reason_code,
                "wait_reason": reason_label, "due_at": job.get("due_at"),
                "retry_count": int(job.get("retry_count") or 0),
                "command_id": job.get("command_id"), "mission_id": job.get("mission_id"),
            }

        if changed:
            _write_json(r7_engine.JOBS, jobs_data)

    data_state["queue"] = queue_snapshot
    data_state["last_governance_at"] = now_iso()
    if duplicate_suppressed:
        _event(data_state, "duplicates_suppressed", "重复任务已自动抑制", {"count": duplicate_suppressed})
    if stale_recovered:
        _event(data_state, "stale_jobs_recovered", "长时间无心跳任务已安全重入队列", {"count": stale_recovered})
    _save(data_state)
    return {
        "command_id": control.get("command_id"), "mission_id": control.get("mission_id"),
        "items": queue_snapshot, "duplicate_suppressed": duplicate_suppressed,
        "stale_recovered": stale_recovered, "generated_at": now_iso(),
    }


def receipt_truth(job):
    """Normalize one job without promoting local completion to external truth."""
    if not isinstance(job, dict):
        return {"state": "UNKNOWN", "formal_external": False}
    receipt = job.get("execution_receipt") if isinstance(job.get("execution_receipt"), dict) else {}
    result = job.get("result") if isinstance(job.get("result"), dict) else {}
    if job.get("state") != "completed":
        return {"state": str(job.get("state") or "UNKNOWN").upper(), "formal_external": False}
    # Public/external promotion requires explicit external identifiers/proof.
    public_url = result.get("public_url") or result.get("url") if result.get("verified_public") else None
    post_id = result.get("post_id") if result.get("platform_receipt") else None
    if public_url or post_id:
        return {"state": "PUBLISHED", "formal_external": True, "public_url": public_url, "post_id": post_id}
    if receipt:
        return {"state": "LOCAL_EXECUTED", "formal_external": False,
                "receipt_id": receipt.get("receipt_id"),
                "truth_rule": "本地执行回执不代表外部发布、抓取、收录、排名、GEO或经营成功。"}
    return {"state": "COMPLETED_UNPROVEN", "formal_external": False}


def human_pending():
    """Only owner-only gates are returned as human pending.

    Controller-plan creation and normal scheduler waiting are system-owned and
    must never be pushed back to the owner.
    """
    human = []
    system_owned = []
    deferred = []
    try:
        from core import r8_22_autonomous_convergence as convergence
        raw_human, raw_deferred = convergence._human_and_deferred()
        deferred.extend(raw_deferred or [])
        for item in raw_human or []:
            text = " ".join(str(item.get(k) or "") for k in ("title", "reason", "detail", "action")).lower()
            if any(marker in text for marker in SYSTEM_OWNED_MARKERS):
                system_owned.append(item)
            elif any(marker in text for marker in HUMAN_ONLY_MARKERS):
                human.append(item)
            else:
                # Unknown operational work stays system-owned until it proves a real human gate.
                system_owned.append(item)
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError):
        pass
    return {"human": human[:50], "system_owned": system_owned[:50], "deferred_channels": deferred[:50]}


def _model_health():
    try:
        from integrations import ai_gateway
        status = ai_gateway.gateway_status()
        routes = status.get("routes") or {}
        return {
            "local_ready": bool((routes.get("local") or {}).get("verified")),
            "doubao_ready": bool((routes.get("cloud") or {}).get("verified")),
            "local": deepcopy(routes.get("local") or {}),
            "cloud": deepcopy(routes.get("cloud") or {}),
        }
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError):
        return {"local_ready": False, "doubao_ready": False}


def readiness():
    identity = release_identity()
    control = canonical_control(reconcile=False)
    decision = decision_pack_status()
    try:
        from core import r7_engine
        audit_ok = r7_engine.audit_history().get("integrity") == "verified"
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError):
        audit_ok = False
    models = _model_health()
    blockers = []
    if not identity.get("complete"):
        blockers.append("release_identity_incomplete")
    if not control.get("consistent"):
        blockers.append("control_chain_not_consistent")
    if not decision.get("valid"):
        blockers.append("decision_pack_missing_or_expired")
    if not audit_ok:
        blockers.append("audit_integrity_failed")
    degraded = []
    if not models.get("local_ready"):
        degraded.append("local_model_not_verified")
    if not models.get("doubao_ready"):
        degraded.append("doubao_not_verified_key_seo_geo_stages_defer")
    state = "BLOCKED" if blockers else "DEGRADED" if degraded else "READY"
    return {
        "state": state, "ready": state == "READY", "blockers": blockers,
        "degraded": degraded, "identity": identity, "control": control,
        "decision_pack": decision, "models": models,
        "truth": "READY只表示自治执行前置条件满足，不代表外部SEO/GEO/社媒/经营结果已经成功。",
    }


def snapshot(reconcile=False):
    control = canonical_control(reconcile=reconcile)
    if reconcile and control.get("consistent"):
        ensure_decision_pack(control)
        queue = govern_queue()
    else:
        queue = {"items": deepcopy(_load().get("queue") or {})}
    pending = human_pending()
    ready = readiness()
    state = _load()
    return {
        "schema": SCHEMA,
        "release": release_identity(),
        "control": control,
        "decision_pack": decision_pack_status(),
        "queue": queue,
        "pending": pending,
        "readiness": ready,
        "model_routing": {
            "local_first": True,
            "doubao_required_stages": sorted(DOUBAO_REQUIRED_STAGES),
            "chatgpt_role": "sole_strategic_controller",
            "rtx3060_role": "preferred_local_compute_when_eligible",
        },
        "truth_states": list(TRUTH_STATES),
        "business_outcome_scope": ["site_visit", "mini_program_visit", "consultation", "task", "order"],
        "forbidden_business_metrics": ["money", "amount", "revenue", "profit", "ROI"],
        "events": list(reversed(state.get("events") or []))[:50],
        "field_acceptance": {
            "24h": "pending_real_field_run",
            "72h": "pending_real_fault_recovery_run",
            "7d": "pending_real_production_run",
            "note": "CI等效测试不能替代真实物理时间的24h/72h/7天验收。",
        },
    }


def controller_tick():
    """One bounded governance iteration around the existing scheduler."""
    control = canonical_control(reconcile=True)
    pack = ensure_decision_pack(control) if control.get("consistent") else None
    queue = govern_queue() if control.get("consistent") else {"items": {}}
    return {"control": control, "decision_pack": pack, "queue": queue, "readiness": readiness(), "at": now_iso()}
