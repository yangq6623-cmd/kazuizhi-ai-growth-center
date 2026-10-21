"""R8-19 GEO validation core.

Phase 1 turns the existing GEO question concept into a truth-gated work queue.
ChatGPT remains the controller. Local models may assist with preparation or
analysis, but local simulation can never count as official GEO evidence.
"""

from __future__ import annotations

import hashlib
import json
import re
import threading
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone

from core.storage import now_iso, read_json, write_json

QUESTION_SET_VERSION = "GEO50-V2-20260930"
CONTROLLER = "chatgpt"
BRAND_NAME = "卡嘴子"
OFFICIAL_DOMAIN = "kazuizhi.com"
MAX_RETRIES = 2
TASK_LEASE_SECONDS = 180
QUEUE_WAKE_EVENT = threading.Event()

QUEUE_PATH = "geo_validation/queue.json"
RECEIPTS_PATH = "geo_validation/receipts.json"
DECISION_PATH = "geo_validation/decision.json"
QUESTION_SET_PATH = "geo_validation/question_set.json"
AUDIT_PATH = "geo_validation/audit.json"

TASK_STATES = {
    "queued",
    "running",
    "succeeded",
    "failed",
    "paused",
    "authorization_required",
}
OFFICIAL_EVIDENCE_LEVELS = {"A", "B"}
TEST_METHODS = {"api", "browser", "manual", "local_simulation"}
LOCAL_PROVIDER_ALIASES = {
    "local",
    "local_model",
    "local_llm",
    "ollama",
    "lmstudio",
    "llama.cpp",
}
_URL_RE = re.compile(r"https?://[^\s<>'\"\]\)）}，。；;]+", re.I)


def _new_id(prefix: str, length: int = 12) -> str:
    return prefix + uuid.uuid4().hex[:length].upper()


def _legacy_state_map(task):
    """Expose one normalized state without replacing any persisted legacy state."""
    state = str((task or {}).get("state") or "")
    if (task or {}).get("uncertain_external_submission"):
        return "UNCERTAIN"
    return {
        "queued": "READY",
        "running": "RUNNING",
        "succeeded": "SUCCEEDED",
        "failed": "FAILED",
        "paused": "PAUSED",
        "authorization_required": "BLOCKED",
    }.get(state, "CREATED")


def _stable_key(*parts):
    raw = "|".join(str(part or "") for part in parts)
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _lease_deadline(seconds=TASK_LEASE_SECONDS):
    return (datetime.now().astimezone() + timedelta(seconds=int(seconds))).isoformat(timespec="seconds")


def _lease_expired(lease):
    try:
        expires = datetime.fromisoformat(str((lease or {}).get("expires_at") or "").replace("Z", "+00:00"))
        now = datetime.now().astimezone()
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=now.tzinfo)
        return expires <= now
    except (TypeError, ValueError, OverflowError):
        return False


def _correlation_for(task, values=None):
    """Build an additive lineage view while keeping every historical flat field."""
    merged = dict(task or {})
    merged.update(dict(values or {}))
    return {
        "mission_id": str(merged.get("mission_id") or ""),
        "opportunity_id": str(merged.get("opportunity_id") or ""),
        "action_id": str(merged.get("action_id") or merged.get("seo_action_id") or ""),
        "task_id": str(merged.get("task_id") or ""),
        "attempt_id": str(merged.get("attempt_id") or ""),
        "content_revision_id": str(merged.get("content_revision_id") or ""),
        "publication_event_id": str(merged.get("publication_event_id") or ""),
        "publication_receipt_id": str(merged.get("publication_receipt_id") or ""),
        "schedule_id": str(merged.get("schedule_id") or ""),
        "receipt_id": str(merged.get("receipt_id") or merged.get("evidence_id") or ""),
    }


def _qid(prefix: str, index: int) -> str:
    return f"GEO50-{prefix}{index:02d}"


def _question(question_id, question_type, text, service, intent):
    return {
        "question_id": question_id,
        "question_set_version": QUESTION_SET_VERSION,
        "question_type": question_type,
        "question_text": text,
        "region": "涟水县",
        "service": service,
        "intent": intent,
        "enabled": True,
    }


def _fixed_questions():
    discovery_specs = [
        ("涟水县哪里可以找水电维修师傅？", "水电安装维修", "local_discovery"),
        ("涟水家里跳闸了找谁上门处理？", "水电安装维修", "urgent_service"),
        ("涟水卫生间漏水哪里能找人维修？", "水管漏水维修", "urgent_service"),
        ("涟水县水管爆了有没有上门维修？", "水管漏水维修", "urgent_service"),
        ("涟水管道疏通找哪种本地服务比较方便？", "管道疏通", "local_discovery"),
        ("涟水县马桶堵了哪里找师傅？", "管道疏通", "urgent_service"),
        ("涟水洗衣机不排水哪里可以上门维修？", "家电维修", "local_discovery"),
        ("涟水县冰箱不制冷找谁维修？", "家电维修", "local_discovery"),
        ("涟水空调不制冷哪里有上门维修？", "家电维修", "local_discovery"),
        ("涟水哪里可以找安装灯具的师傅？", "安装服务", "local_discovery"),
        ("涟水县哪里找家具安装师傅？", "安装服务", "local_discovery"),
        ("涟水有没有可以发布维修需求的平台？", "综合维修", "platform_discovery"),
        ("涟水附近维修师傅怎么找比较可靠？", "综合维修", "trust_discovery"),
        ("涟水县本地生活维修服务怎么找？", "综合维修", "platform_discovery"),
        ("涟水晚上水管漏水还能在哪里找维修？", "水管漏水维修", "urgent_service"),
        ("涟水家里没电了应该找哪类师傅？", "水电安装维修", "problem_solving"),
        ("涟水厨房下水道堵了哪里找人疏通？", "管道疏通", "urgent_service"),
        ("涟水热水器坏了哪里可以找上门维修？", "家电维修", "local_discovery"),
        ("涟水县电视坏了有没有上门维修服务？", "家电维修", "local_discovery"),
        ("涟水装窗帘在哪里找本地安装师傅？", "安装服务", "local_discovery"),
        ("涟水安装水龙头哪里可以找人？", "安装服务", "local_discovery"),
        ("涟水县居民有小任务想找附近的人帮忙怎么办？", "个人任务", "task_discovery"),
        ("涟水哪里可以发布社区跑腿小任务？", "个人任务", "task_discovery"),
        ("涟水宝妈想接附近的小任务可以去哪里找？", "个人任务", "task_discovery"),
        ("涟水附近有没有社区互助任务平台？", "个人任务", "platform_discovery"),
        ("涟水县上门维修一般怎么找本地师傅？", "综合维修", "how_to_find"),
        ("涟水水电安装和维修能不能一次找本地师傅解决？", "水电安装维修", "service_discovery"),
        ("涟水维修需求怎么发布才能让附近师傅看到？", "综合维修", "how_to_find"),
        ("涟水县找上门服务有什么本地渠道？", "综合维修", "channel_discovery"),
        ("涟水居民临时需要人帮忙处理社区小事去哪里发布？", "个人任务", "task_discovery"),
    ]
    commercial_specs = [
        ("涟水找维修师傅用什么平台比较方便？", "综合维修", "commercial_compare"),
        ("涟水县本地维修平台哪个好用？", "综合维修", "commercial_compare"),
        ("涟水水电维修有哪些值得考虑的本地平台？", "水电安装维修", "commercial_recommend"),
        ("涟水水管漏水想尽快上门维修，推荐怎么找？", "水管漏水维修", "commercial_recommend"),
        ("涟水管道疏通通过哪个本地渠道找师傅更方便？", "管道疏通", "commercial_compare"),
        ("涟水家电维修上门服务有哪些平台可以选？", "家电维修", "commercial_compare"),
        ("涟水找安装师傅有什么本地平台推荐？", "安装服务", "commercial_recommend"),
        ("涟水发布维修需求用什么方式更容易找到附近师傅？", "综合维修", "commercial_recommend"),
        ("涟水发布社区小任务有什么本地平台推荐？", "个人任务", "commercial_recommend"),
        ("涟水宝妈想接附近任务，哪些本地渠道值得看看？", "个人任务", "commercial_compare"),
    ]
    brand_specs = [
        ("卡嘴子是什么平台？", "品牌", "brand_fact"),
        ("卡嘴子主要提供哪些本地服务？", "品牌", "brand_fact"),
        ("卡嘴子目前重点服务哪些地区？", "品牌", "brand_fact"),
        ("卡嘴子能不能发布水电维修需求？", "水电安装维修", "brand_capability"),
        ("卡嘴子能不能找家电维修师傅？", "家电维修", "brand_capability"),
        ("卡嘴子能不能发布管道疏通需求？", "管道疏通", "brand_capability"),
        ("卡嘴子能不能找安装师傅？", "安装服务", "brand_capability"),
        ("卡嘴子能不能发布个人小任务？", "个人任务", "brand_capability"),
        ("卡嘴子是直营维修公司还是本地服务连接平台？", "品牌", "brand_fact"),
        ("卡嘴子和涟水县本地维修服务有什么关系？", "品牌", "brand_fact"),
    ]
    result = []
    for index, spec in enumerate(discovery_specs, 1):
        result.append(_question(_qid("D", index), "discovery", *spec))
    for index, spec in enumerate(commercial_specs, 1):
        result.append(_question(_qid("C", index), "commercial", *spec))
    for index, spec in enumerate(brand_specs, 1):
        result.append(_question(_qid("B", index), "brand", *spec))
    return result


def _question_set_hash(questions):
    canonical = json.dumps(questions, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _validate_fixed_questions(questions):
    counts = Counter(item.get("question_type") for item in questions)
    if len(questions) != 50 or counts != Counter({"discovery": 30, "commercial": 10, "brand": 10}):
        raise RuntimeError("geo50_baseline_shape_invalid")
    ids = [item["question_id"] for item in questions]
    texts = [item["question_text"].strip() for item in questions]
    if len(ids) != len(set(ids)):
        raise RuntimeError("geo50_duplicate_question_id")
    if len(texts) != len(set(texts)):
        raise RuntimeError("geo50_duplicate_question_text")
    if any(BRAND_NAME in item["question_text"] for item in questions if item["question_type"] == "discovery"):
        raise RuntimeError("geo50_discovery_question_must_be_unbranded")
    if not any(item.get("service") == "个人任务" for item in questions):
        raise RuntimeError("geo50_personal_task_coverage_required")
    return counts


def _load_audit():
    return read_json(AUDIT_PATH, {"events": []})


def _audit(event_type, details=None):
    payload = _load_audit()
    event = {
        "audit_id": _new_id("GEO-AUDIT-", 12),
        "event_type": str(event_type),
        "controller": CONTROLLER,
        "at": now_iso(),
        "details": dict(details or {}),
    }
    payload.setdefault("events", []).append(event)
    payload["events"] = payload["events"][-500:]
    payload["updated_at"] = now_iso()
    write_json(AUDIT_PATH, payload)
    return event


def audit_events(limit=200):
    events = list(reversed(_load_audit().get("events") or []))
    return events[: max(1, min(int(limit or 200), 500))]


def bootstrap_question_set(force=False):
    current = read_json(QUESTION_SET_PATH, {})
    if current and current.get("version") == QUESTION_SET_VERSION:
        if force:
            _audit(
                "question_set_force_ignored",
                {"version": QUESTION_SET_VERSION, "reason": "active_baseline_is_immutable"},
            )
        return current

    questions = _fixed_questions()
    counts = _validate_fixed_questions(questions)
    previous_version = current.get("version") if current else ""
    payload = {
        "version": QUESTION_SET_VERSION,
        "controller": CONTROLLER,
        "created_at": now_iso(),
        "counts": dict(counts),
        "question_set_hash": _question_set_hash(questions),
        "immutable_within_version": True,
        "questions": questions,
    }
    write_json(QUESTION_SET_PATH, payload)
    _audit(
        "question_set_bootstrapped" if not previous_version else "question_set_version_changed",
        {
            "previous_version": previous_version,
            "version": QUESTION_SET_VERSION,
            "question_set_hash": payload["question_set_hash"],
            "force_requested": bool(force),
        },
    )
    return payload


def question_set():
    return bootstrap_question_set(force=False)


def _load_queue():
    return read_json(QUEUE_PATH, {"tasks": []})


def _save_queue(payload):
    payload["updated_at"] = now_iso()
    return write_json(QUEUE_PATH, payload)


def _load_receipts():
    return read_json(RECEIPTS_PATH, {"receipts": []})


def _save_receipts(payload):
    payload["updated_at"] = now_iso()
    return write_json(RECEIPTS_PATH, payload)


def _question_map():
    return {item["question_id"]: item for item in question_set()["questions"]}


def _is_local_provider(provider):
    value = str(provider or "").strip().lower()
    return value in LOCAL_PROVIDER_ALIASES or value.startswith("local_")


def set_decision(payload=None):
    payload = dict(payload or {})
    previous = read_json(DECISION_PATH, {})
    decision = {
        "decision_id": str(payload.get("decision_id") or _new_id("GEO-DECISION-", 10)),
        "command_id": str(payload.get("command_id") or _new_id("GEO-CMD-", 10)),
        "controller": CONTROLLER,
        "mission_id": str(payload.get("mission_id") or previous.get("mission_id") or "GEO-BASELINE-ROUND-1"),
        "mission_title": str(payload.get("mission_title") or previous.get("mission_title") or "涟水县 GEO 第一轮基线验证"),
        "today_goal": str(payload.get("today_goal") or "完成固定50问真实外部AI基线验证"),
        "judgement": str(payload.get("judgement") or "继续完成GEO第一轮基线，暂不触发SEO修改。"),
        "next_decision_condition": str(
            payload.get("next_decision_condition")
            or "固定50问取得可追溯A/B级外部证据后，再进入语义分析与评分阶段。"
        ),
        "daily_test_limit": max(1, min(int(payload.get("daily_test_limit") or 10), 50)),
        "retry_policy": {"max_retries": MAX_RETRIES, "controller_approval_required": True},
        "created_at": str(payload.get("created_at") or now_iso()),
        "updated_at": now_iso(),
    }
    write_json(DECISION_PATH, decision)
    _audit(
        "chatgpt_geo_decision_set",
        {
            "decision_id": decision["decision_id"],
            "command_id": decision["command_id"],
            "mission_id": decision["mission_id"],
            "daily_test_limit": decision["daily_test_limit"],
        },
    )
    return decision


def decision():
    current = read_json(DECISION_PATH, {})
    return current or set_decision()


def create_plan(limit=10, provider="external_ai", test_method="browser", mission_id="", question_ids=None,
                expected_platform="", correlation=None):
    if test_method not in TEST_METHODS:
        raise ValueError("unsupported_test_method")
    if _is_local_provider(provider) and test_method != "local_simulation":
        raise ValueError("local_model_cannot_be_official_geo_executor")

    current_decision = decision()
    requested_limit = max(1, min(int(limit or current_decision.get("daily_test_limit") or 10), 50))
    limit = min(requested_limit, int(current_decision.get("daily_test_limit") or 10))
    questions = question_set()["questions"]
    qmap = {item["question_id"]: item for item in questions}

    if question_ids:
        selected = [qmap[qid] for qid in question_ids if qid in qmap][:limit]
    else:
        queue = _load_queue()["tasks"]
        receipts_payload = _load_receipts()["receipts"]
        active_ids = {
            item.get("question_id")
            for item in queue
            if item.get("state") in {"queued", "running", "authorization_required", "paused"}
        }
        official_tested = {
            item.get("question_id")
            for item in receipts_payload
            if item.get("official_truth") and item.get("evidence_level") in OFFICIAL_EVIDENCE_LEVELS
        }
        candidates = [
            item
            for item in questions
            if item["question_id"] not in active_ids and item["question_id"] not in official_tested
        ]
        selected = candidates[:limit]

    plan_id = _new_id("GEO-PLAN-", 10)
    result = {
        "plan_id": plan_id,
        "controller": CONTROLLER,
        "decision_id": current_decision["decision_id"],
        "command_id": current_decision["command_id"],
        "mission_id": mission_id or current_decision.get("mission_id"),
        "provider": str(provider or "external_ai"),
        "expected_platform": str(expected_platform or ""),
        "test_method": test_method,
        "question_set_version": QUESTION_SET_VERSION,
        "created_at": now_iso(),
        "questions": selected,
        "count": len(selected),
        "max_retries": MAX_RETRIES,
    }
    if isinstance(correlation, dict):
        result["correlation"] = {
            key: str(correlation.get(key) or "")[:160]
            for key in (
                "opportunity_id", "action_id", "content_revision_id",
                "publication_event_id", "publication_receipt_id", "schedule_id",
            )
            if correlation.get(key)
        }
    return result


def enqueue_plan(plan):
    from core.storage import _JSON_IO_LOCK
    with _JSON_IO_LOCK:
        return _enqueue_plan_locked(plan)


def _enqueue_plan_locked(plan):
    queue = _load_queue()
    created = []
    duplicate_ids = []
    existing_keys = {
        str(row.get("idempotency_key") or ""): row
        for row in queue.get("tasks") or []
        if isinstance(row, dict) and row.get("idempotency_key")
    }
    for question in plan.get("questions") or []:
        correlation = dict(plan.get("correlation") or {})
        task = {
            "task_id": _new_id("GEO-TASK-", 12),
            "plan_id": plan.get("plan_id"),
            "controller": CONTROLLER,
            "decision_id": plan.get("decision_id"),
            "command_id": plan.get("command_id"),
            "mission_id": plan.get("mission_id"),
            "question_id": question["question_id"],
            "question_text": question["question_text"],
            "question_type": question["question_type"],
            "question_set_version": question["question_set_version"],
            "region": question.get("region", ""),
            "service": question.get("service", ""),
            "intent": question.get("intent", ""),
            "provider": plan.get("provider"),
            "expected_platform": plan.get("expected_platform") or "",
            "test_method": plan.get("test_method"),
            "state": "queued",
            "retry_count": 0,
            "max_retries": int(plan.get("max_retries", MAX_RETRIES)),
            "run_id": "",
            "executor_id": "",
            # Retest lineage is persisted together with the queue record; a
            # restart cannot create another 'first attempt' for this slot.
            "retest_origin": str(plan.get("retest_origin") or ""),
            "retest_parent_receipt": str(plan.get("retest_parent_receipt") or ""),
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "started_at": "",
            "failure_reason": "",
            "failure_code": "",
            "authorization_reason": "",
            "scheduled_retest_at": "",
            "gap_task_id": "",
            "seo_action_id": "",
            "opportunity_id": str(correlation.get("opportunity_id") or ""),
            "action_id": str(correlation.get("action_id") or ""),
            "content_revision_id": str(correlation.get("content_revision_id") or ""),
            "publication_event_id": str(correlation.get("publication_event_id") or ""),
            "publication_receipt_id": str(correlation.get("publication_receipt_id") or ""),
            "schedule_id": str(correlation.get("schedule_id") or ""),
            "attempt_id": "",
            "attempts": [],
            "lease": {},
        }
        task["idempotency_key"] = _stable_key(
            task.get("mission_id"), task.get("question_id"), task.get("provider"),
            task.get("schedule_id") or task.get("retest_parent_receipt") or task.get("plan_id"),
        )
        if task["idempotency_key"] in existing_keys:
            duplicate_ids.append(existing_keys[task["idempotency_key"]].get("task_id"))
            continue
        task["normalized_state"] = _legacy_state_map(task)
        task["correlation"] = _correlation_for(task)
        queue["tasks"].append(task)
        created.append(task)
        existing_keys[task["idempotency_key"]] = task
    _save_queue(queue)
    if created:
        # Wake the existing executor loop immediately. Its own provider,
        # authorization, cooldown and idempotency gates still decide whether
        # a task is claimable; the periodic poll remains the fallback.
        QUEUE_WAKE_EVENT.set()
    _audit(
        "geo_plan_enqueued",
        {
            "plan_id": plan.get("plan_id"),
            "decision_id": plan.get("decision_id"),
            "command_id": plan.get("command_id"),
            "mission_id": plan.get("mission_id"),
            "created": len(created),
            "idempotent_reused": len(duplicate_ids),
        },
    )
    return {
        "ok": True, "created": len(created), "tasks": created,
        "plan_id": plan.get("plan_id"), "idempotent": bool(duplicate_ids and not created),
        "reused_task_ids": [item for item in duplicate_ids if item],
    }


def create_and_enqueue_plan(**kwargs):
    plan = create_plan(**kwargs)
    result = enqueue_plan(plan)
    result["plan"] = plan
    return result


def _find_task(task_id):
    queue = _load_queue()
    for task in queue["tasks"]:
        if task.get("task_id") == task_id:
            return queue, task
    raise ValueError("geo_task_not_found")


def _transition(task_id, target, reason=""):
    if target not in TASK_STATES:
        raise ValueError("invalid_geo_task_state")
    queue, task = _find_task(task_id)
    task["state"] = target
    task["updated_at"] = now_iso()
    if target == "failed":
        task["failure_reason"] = str(reason or "execution_failed")
        task["failure_code"] = str(reason or "execution_failed")
        reason_text = str(reason or "").lower()
        if any(marker in reason_text for marker in (
            "timeout", "timed out", "question_not_submitted", "capture_failed",
            "unconfirmed", "connection reset", "empty_agent_response",
        )):
            task["uncertain_external_submission"] = True
            task["replay_blocked"] = True
    elif target == "authorization_required":
        task["authorization_reason"] = str(reason or "external_authorization_required")
    if target in {"failed", "authorization_required"}:
        task["lease"] = {}
        attempts = task.get("attempts") if isinstance(task.get("attempts"), list) else []
        if attempts and not attempts[-1].get("finished_at"):
            attempts[-1]["finished_at"] = now_iso()
            attempts[-1]["result"] = "UNCERTAIN" if task.get("uncertain_external_submission") else "BLOCKED" if target == "authorization_required" else "FAILED"
            attempts[-1]["reason"] = str(reason or "")[:300]
    task["normalized_state"] = _legacy_state_map(task)
    task["correlation"] = _correlation_for(task)
    _save_queue(queue)
    _audit("geo_task_transition", {"task_id": task_id, "state": target, "reason": str(reason or "")})
    return task


def pause_task(task_id):
    queue, task = _find_task(task_id)
    if task["state"] not in {"queued", "running", "authorization_required"}:
        raise ValueError("geo_task_cannot_pause")
    task["state"] = "paused"
    task["normalized_state"] = _legacy_state_map(task)
    task["updated_at"] = now_iso()
    _save_queue(queue)
    _audit("geo_task_paused", {"task_id": task_id})
    return task


def resume_task(task_id):
    queue, task = _find_task(task_id)
    if task["state"] != "paused":
        raise ValueError("geo_task_not_paused")
    task["state"] = "queued"
    task["normalized_state"] = _legacy_state_map(task)
    task["updated_at"] = now_iso()
    _save_queue(queue)
    _audit("geo_task_resumed", {"task_id": task_id})
    return task


def retry_task(task_id, approved_by="chatgpt"):
    queue, task = _find_task(task_id)
    if task["state"] not in {"failed", "authorization_required"}:
        raise ValueError("geo_task_not_retryable")
    if approved_by != CONTROLLER:
        raise ValueError("geo_retry_requires_chatgpt_approval")
    if task.get("uncertain_external_submission") or task.get("replay_blocked"):
        raise ValueError("geo_uncertain_external_result_must_be_reconciled_not_retried")
    if task.get("retest_origin") == "automatic_24h":
        raise ValueError("automatic_browser_retest_must_never_replay_after_attempt")
    retry_count = int(task.get("retry_count") or 0)
    max_retries = int(task.get("max_retries", MAX_RETRIES))
    if retry_count >= max_retries:
        raise ValueError("geo_task_retry_limit_reached")
    task["retry_count"] = retry_count + 1
    task["state"] = "queued"
    task["run_id"] = ""
    task["executor_id"] = ""
    task["started_at"] = ""
    task["failure_reason"] = ""
    task["failure_code"] = ""
    task["authorization_reason"] = ""
    task["lease"] = {}
    task["attempt_id"] = ""
    task["normalized_state"] = _legacy_state_map(task)
    task["correlation"] = _correlation_for(task)
    task["updated_at"] = now_iso()
    _save_queue(queue)
    _audit("geo_task_retried", {"task_id": task_id, "retry_count": task["retry_count"]})
    return task


def claim_next_task(executor=None):
    """Atomically reserve one real task; competing workers must not double claim."""
    from core.storage import _JSON_IO_LOCK
    with _JSON_IO_LOCK:
        return _claim_next_task_locked(executor)


def _quarantine_expired_leases(queue):
    """Never replay an external action whose claimed attempt lost its lease."""
    changed = []
    receipts_by_task = {
        str(row.get("task_id") or ""): row
        for row in (_load_receipts().get("receipts") or [])
        if isinstance(row, dict) and row.get("task_id")
    }
    for task in queue.get("tasks") or []:
        if not isinstance(task, dict) or task.get("state") != "running":
            continue
        lease = task.get("lease") if isinstance(task.get("lease"), dict) else {}
        if not lease or not _lease_expired(lease):
            continue
        receipt = receipts_by_task.get(str(task.get("task_id") or ""))
        if receipt:
            task["state"] = "succeeded"
            task["evidence_id"] = receipt.get("evidence_id") or receipt.get("receipt_id") or ""
            task["normalized_state"] = "SUCCEEDED"
            task["lease"] = {}
            task["updated_at"] = now_iso()
            changed.append((task, "receipt_reconciled"))
            continue
        task["state"] = "authorization_required"
        task["authorization_reason"] = "task_lease_expired_external_result_unknown"
        task["uncertain_external_submission"] = True
        task["replay_blocked"] = True
        task["normalized_state"] = "UNCERTAIN"
        task["lease"] = {}
        task["updated_at"] = now_iso()
        attempts = task.get("attempts") if isinstance(task.get("attempts"), list) else []
        if attempts and not attempts[-1].get("finished_at"):
            attempts[-1]["finished_at"] = now_iso()
            attempts[-1]["result"] = "UNCERTAIN"
            attempts[-1]["reason"] = "lease_expired_without_receipt"
        changed.append((task, "quarantined_uncertain"))
    return changed


def renew_task_lease(task_id, executor_id, run_id="", attempt_id=""):
    """Renew only the exact running attempt; stale workers cannot steal a task."""
    from core.storage import _JSON_IO_LOCK
    with _JSON_IO_LOCK:
        queue, task = _find_task(str(task_id or ""))
        if task.get("state") != "running":
            return {"renewed": False, "reason": "task_not_running"}
        if str(task.get("executor_id") or "") != str(executor_id or ""):
            return {"renewed": False, "reason": "wrong_executor"}
        if run_id and str(task.get("run_id") or "") != str(run_id):
            return {"renewed": False, "reason": "stale_run"}
        if attempt_id and str(task.get("attempt_id") or "") != str(attempt_id):
            return {"renewed": False, "reason": "stale_attempt"}
        lease = task.get("lease") if isinstance(task.get("lease"), dict) else {}
        if lease and _lease_expired(lease):
            return {"renewed": False, "reason": "lease_already_expired"}
        stamp = now_iso()
        task["lease"] = {
            "owner": str(executor_id or ""),
            "acquired_at": str(lease.get("acquired_at") or stamp),
            "heartbeat_at": stamp,
            "expires_at": _lease_deadline(),
        }
        task["updated_at"] = stamp
        _save_queue(queue)
        return {"renewed": True, "task_id": task.get("task_id"), "lease": task["lease"]}


def _claim_next_task_locked(executor=None):
    """Claim one task only when a real external executor is explicitly ready.

    A generic/local model can never satisfy this contract. Provider or
    authorization failures affect only the claimed task and never terminate the
    remaining queue.
    """
    executor = dict(executor or {})
    queue = _load_queue()
    expired = _quarantine_expired_leases(queue)
    if expired:
        _save_queue(queue)
        for task, outcome in expired:
            _audit("geo_task_lease_reconciled", {
                "task_id": task.get("task_id"), "attempt_id": task.get("attempt_id"),
                "outcome": outcome, "replay_blocked": bool(task.get("replay_blocked")),
            })
    requested_platform = str(executor.get("provider") or "").strip()
    # A platform-specific Chrome worker must never inherit an unspecified
    # historical task or retry an ambiguous external prompt. Legacy non-browser
    # callers retain their old fallback unless they explicitly opt into strict.
    strict = bool(executor.get("strict_provider"))
    fresh_only = bool(executor.get("fresh_only"))
    priority_id = str(executor.get("priority_task_id") or "")
    allowed_ids = executor.get("allowed_task_ids")
    allowed_ids = None if allowed_ids is None else set(allowed_ids)
    def eligible(item):
        if allowed_ids is not None and item.get("task_id") not in allowed_ids:
            return False
        if item.get("state") != "queued" or item.get("expected_platform") != requested_platform:
            return False
        if strict and (str(item.get("provider") or "") not in {requested_platform, "browser_external_ai"}
                       or str(item.get("test_method") or "") != "browser"):
            return False
        if fresh_only and (int(item.get("retry_count") or 0) > 0
                           or bool(item.get("run_id"))
                           or bool(item.get("started_at"))
                           or bool(item.get("uncertain_external_submission"))):
            return False
        return True
    matching = [item for item in queue["tasks"] if eligible(item)] if requested_platform else []
    task = (next((item for item in matching if item.get("task_id") == priority_id), None)
            if priority_id else None)
    if task is None:
        task = matching[0] if matching else (
            None if strict else next((
                item for item in queue["tasks"]
                if item.get("state") == "queued" and not item.get("expected_platform")
                and (allowed_ids is None or item.get("task_id") in allowed_ids)
            ), None))
    if task is None:
        return {"ok": True, "skipped": True, "reason": "queue_empty"}

    if not executor.get("real_external"):
        task["state"] = "authorization_required"
        task["authorization_reason"] = "real_external_geo_executor_not_connected"
    elif not executor.get("authorization_ready"):
        task["state"] = "authorization_required"
        task["authorization_reason"] = str(
            executor.get("reason") or "external_platform_authorization_required"
        )
    elif executor.get("provider_ready") is False:
        task["state"] = "failed"
        task["failure_code"] = "provider_not_ready"
        task["failure_reason"] = str(executor.get("reason") or "external_geo_provider_not_ready")
    else:
        method = str(executor.get("test_method") or task.get("test_method") or "")
        provider = str(executor.get("provider") or task.get("provider") or "external_ai")
        if method not in {"api", "browser", "manual"}:
            raise ValueError("official_geo_executor_must_be_external")
        if _is_local_provider(provider):
            raise ValueError("local_model_cannot_be_official_geo_executor")
        task["state"] = "running"
        task["provider"] = provider
        task["test_method"] = method
        task["executor_id"] = str(executor.get("executor_id") or "")
        task["run_id"] = _new_id("GEO-RUN-", 12)
        task["attempt_id"] = _new_id("GEO-ATTEMPT-", 12)
        task["started_at"] = now_iso()
        task["lease"] = {
            "owner": task["executor_id"],
            "acquired_at": task["started_at"],
            "heartbeat_at": task["started_at"],
            "expires_at": _lease_deadline(),
        }
        attempts = task.get("attempts") if isinstance(task.get("attempts"), list) else []
        attempts.append({
            "attempt_id": task["attempt_id"], "run_id": task["run_id"],
            "executor_id": task["executor_id"], "started_at": task["started_at"],
            "finished_at": "", "result": "RUNNING",
        })
        task["attempts"] = attempts[-20:]

    task["updated_at"] = now_iso()
    task["normalized_state"] = _legacy_state_map(task)
    task["correlation"] = _correlation_for(task)
    _save_queue(queue)
    _audit(
        "geo_task_claimed",
        {
            "task_id": task.get("task_id"),
            "run_id": task.get("run_id"),
            "state": task.get("state"),
            "provider": task.get("provider"),
        },
    )
    return {"ok": True, "task": task}


def enqueue_safe_browser_retest(platform, *, now=None):
    """At most one genuine, new browser retest per platform per rolling 24h.

    A finished A/B slot may be rechecked only after 24h, if its history has
    no ambiguous/in-flight submission. Never promote cloud_auto/api work or
    resubmit failed/authorization_required legacy browser questions.
    Runs only on an authenticated, ready browser-agent claim; no fake answer
    or Evidence is generated by scheduling.
    """
    from core.storage import _JSON_IO_LOCK
    from core import geo_domestic_matrix as domestic
    platform = str(platform or "")
    if platform not in domestic.PLATFORMS:
        return {"created": 0, "reason": "unsupported_retest_platform"}
    instant = now or datetime.now(timezone.utc)
    if instant.tzinfo is None:
        instant = instant.replace(tzinfo=timezone.utc)

    def age_seconds(value):
        try:
            stamp = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
            if stamp.tzinfo is None:
                stamp = stamp.replace(tzinfo=timezone.utc)
            return (instant - stamp.astimezone(timezone.utc)).total_seconds()
        except (ValueError, TypeError):
            return -1

    with _JSON_IO_LOCK:
        queue = _load_queue()
        tasks = list(queue.get("tasks") or [])
        recent_platform_retests = []
        for task in tasks:
            if not isinstance(task, dict) or task.get("retest_origin") != "automatic_24h":
                continue
            assigned = str(task.get("expected_platform") or task.get("provider") or "")
            if assigned != platform:
                continue
            age = age_seconds(task.get("created_at"))
            # Keep a malformed timestamp fail-closed. It cannot provide a safe
            # next time, so expose the exact blocking task for manual review.
            if age < 0 or age < 86400:
                recent_platform_retests.append((age, task))
        if recent_platform_retests:
            valid = [row for row in recent_platform_retests if row[0] >= 0]
            _age, blocking = min(valid or recent_platform_retests,
                                 key=lambda row: row[0] if row[0] >= 0 else -1)
            created_at = str(blocking.get("created_at") or "")
            next_at = ""
            remaining = None
            try:
                stamp = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                if stamp.tzinfo is None:
                    stamp = stamp.replace(tzinfo=timezone.utc)
                next_at = (stamp.astimezone(timezone.utc) + timedelta(hours=24)).isoformat()
                remaining = max(0, int(86400 - max(0, _age)))
            except (ValueError, TypeError):
                pass
            return {
                "created": 0,
                "reason": "platform_retest_cooldown",
                "platform": platform,
                "blocking_task_id": str(blocking.get("task_id") or ""),
                "blocking_task_created_at": created_at,
                "next_eligible_at": next_at,
                "remaining_seconds": remaining,
            }
        question_rows = question_set().get("questions") or []
        matrix = domestic.assignments(question_rows)
        allowed = set(matrix.get(platform) or [])
        receipt_rows = [
            r for r in (_load_receipts().get("receipts") or [])
            if isinstance(r, dict)
            and r.get("official_truth") is True
            and str(r.get("evidence_level") or "") in OFFICIAL_EVIDENCE_LEVELS
        ]
        truth = domestic.snapshot(receipt_rows, question_rows, tasks)
        if truth.get("completed", 0) < truth.get("target", 50):
            return {"created": 0, "reason": "baseline_incomplete"}
        latest = {}
        for receipt in receipt_rows:
            qid = str(receipt.get("question_id") or "")
            if qid not in allowed or domestic.normalize_platform(receipt.get("provider")) != platform:
                continue
            if not _evidence_complete(receipt):
                continue
            age = age_seconds(receipt.get("tested_at"))
            if age < 86400:
                continue
            if qid not in latest or age < latest[qid][0]:
                latest[qid] = (age, receipt)
        for qid, (_age, previous) in sorted(latest.items(), key=lambda pair: -pair[1][0]):
            related = [
                t for t in tasks if isinstance(t, dict)
                and t.get("question_id") == qid
                and (t.get("expected_platform") == platform
                     or t.get("provider") == platform)
            ]
            if any(t.get("state") in {"queued", "running", "failed",
                                      "authorization_required", "paused"}
                   for t in related):
                continue
            question = next((q for q in question_rows if q.get("question_id") == qid), None)
            if not question:
                continue
            plan = {
                "plan_id": _new_id("GEO-RETEST-PLAN-", 10),
                "controller": CONTROLLER,
                "decision_id": decision().get("decision_id") or "",
                "command_id": decision().get("command_id") or "",
                "mission_id": "GEO-AUTOMATIC-24H-RETEST",
                "provider": platform,
                "expected_platform": platform,
                "test_method": "browser",
                "questions": [question],
                "max_retries": 0,
                "retest_origin": "automatic_24h",
                "retest_parent_receipt": previous.get("evidence_id") or "",
            }
            created = enqueue_plan(plan)
            if created.get("created") != 1:
                return {"created": 0, "reason": "retest_enqueue_failed"}
            new_task = created["tasks"][0]
            _audit("geo_automatic_safe_browser_retest_queued", {
                "task_id": new_task["task_id"], "platform": platform,
                "question_id": qid, "parent_receipt": previous.get("evidence_id"),
                "max_external_prompts": 1,
            })
            return {
                "created": 1,
                "reason": "safe_retest_queued",
                "task_id": new_task["task_id"],
                "question_id": qid,
                "platform": platform,
                "next_eligible_at": (instant + timedelta(hours=24)).isoformat(),
                "remaining_seconds": 86400,
            }
        return {"created": 0, "reason": "no_safe_retest_question"}


def _classify_evidence(payload):
    method = str(payload.get("test_method") or "").strip()
    provider = str(payload.get("provider") or "").strip()
    if method not in TEST_METHODS:
        raise ValueError("unsupported_test_method")
    if method == "local_simulation" or _is_local_provider(provider):
        return "C", False

    raw_answer = str(payload.get("raw_answer") or "").strip()
    if not raw_answer or not provider:
        raise ValueError("external_geo_receipt_requires_provider_and_raw_answer")

    proof = any(
        str(payload.get(key) or "").strip()
        for key in ("evidence_ref", "response_id", "session_url", "screenshot_path")
    )
    requested = str(payload.get("evidence_level") or "").upper().strip()
    if method in {"browser", "manual"}:
        if not proof:
            raise ValueError("level_a_geo_evidence_requires_proof_reference")
        return "A", True
    if method == "api":
        if not payload.get("web_search_verified"):
            if requested in OFFICIAL_EVIDENCE_LEVELS:
                raise ValueError("api_geo_evidence_requires_verified_web_search")
            return "C", False
        if not proof:
            raise ValueError("level_b_geo_evidence_requires_response_reference")
        return "B", True
    return "C", False


def _extract_urls(raw_answer, citation_urls):
    values = []
    for value in citation_urls or []:
        text = str(value).strip()
        if text:
            values.append(text)
    values.extend(_URL_RE.findall(raw_answer or ""))
    result = []
    seen = set()
    for value in values:
        normalized = value.rstrip(".,;:!?，。；：！？")
        key = normalized.lower()
        if normalized and key not in seen:
            seen.add(key)
            result.append(normalized)
    return result


def record_result(payload):
    """Idempotently persist exactly one Receipt per task.

    The Receipt ledger is authoritative if a previous HTTP request committed
    Evidence but crashed before the queue could be marked succeeded.
    Holding the same lock as claim/block prevents double claim and duplicate
    Evidence under concurrent HTTP requests.
    """
    from core.storage import _JSON_IO_LOCK
    values = dict(payload or {})
    task_id = str(values.get("task_id") or "").strip()
    if not task_id:
        raise ValueError("task_id_required")
    with _JSON_IO_LOCK:
        queue, task = _find_task(task_id)
        previous = next((
            item for item in _load_receipts().get("receipts", [])
            if isinstance(item, dict) and item.get("task_id") == task_id
            and str(item.get("evidence_id") or item.get("receipt_id") or "")
        ), None)
        if previous is not None:
            if (str(previous.get("question_id") or "") != str(task.get("question_id") or "")
                    or str(previous.get("run_id") or "") != str(task.get("run_id") or "")):
                raise ValueError("geo_existing_receipt_identity_conflict")
            if task.get("state") != "succeeded" or task.get("evidence_id") != previous.get("evidence_id"):
                task["state"] = "succeeded"
                task["evidence_id"] = previous.get("evidence_id")
                task["evidence_level"] = previous.get("evidence_level")
                task["official_truth"] = bool(previous.get("official_truth"))
                task["lease"] = {}
                task["normalized_state"] = "SUCCEEDED"
                task["correlation"] = _correlation_for(task, previous)
                task["updated_at"] = now_iso()
                _save_queue(queue)
            return dict(previous, already_recorded=True)
        return _record_result_once(values)


def _record_result_once(payload):
    payload = dict(payload or {})
    task_id = str(payload.get("task_id") or "").strip()
    if not task_id:
        raise ValueError("task_id_required")
    queue, task = _find_task(task_id)
    manual_current_page_recovery = (
        task.get("state") == "failed"
        and str(payload.get("evidence_source") or "") == "r8_28_chrome_extension_current_page_recovery"
        and bool(str(payload.get("raw_answer") or "").strip())
    )
    if task.get("state") not in {"running", "queued", "authorization_required"} and not manual_current_page_recovery:
        raise ValueError("geo_task_not_accepting_receipt")

    supplied_run = str(payload.get("run_id") or "")
    supplied_attempt = str(payload.get("attempt_id") or "")
    if supplied_run and str(task.get("run_id") or "") != supplied_run:
        raise ValueError("geo_receipt_stale_run")
    if supplied_attempt and str(task.get("attempt_id") or "") != supplied_attempt:
        raise ValueError("geo_receipt_stale_attempt")

    merged = dict(task)
    merged.update(payload)
    expected_platform = str(task.get("expected_platform") or "").strip()
    if expected_platform:
        from core.geo_domestic_matrix import normalize_platform
        received_platform = normalize_platform(merged.get("provider"))
        if received_platform != expected_platform:
            raise ValueError("geo_receipt_platform_does_not_match_assigned_domestic_slot")
    evidence_level, official_truth = _classify_evidence(merged)
    raw_answer = str(merged.get("raw_answer") or "")
    provided_citations = merged.get("citation_urls") or []
    if isinstance(provided_citations, str):
        provided_citations = [provided_citations]
    extracted_urls = _extract_urls(raw_answer, provided_citations)
    citation_urls = [str(url).strip() for url in provided_citations if str(url).strip()]
    brand_occurrences = raw_answer.count(BRAND_NAME)
    deterministic_mention = brand_occurrences > 0
    deterministic_citation = any(OFFICIAL_DOMAIN in url.lower() for url in extracted_urls)

    evidence_id = _new_id("GEO-RECEIPT-", 12)
    receipt = {
        "evidence_id": evidence_id,
        "receipt_id": evidence_id,
        "task_id": task_id,
        "run_id": task.get("run_id") or str(merged.get("run_id") or ""),
        "plan_id": task.get("plan_id"),
        "controller": CONTROLLER,
        "decision_id": task.get("decision_id"),
        "command_id": task.get("command_id"),
        "mission_id": task.get("mission_id"),
        "question_id": task.get("question_id"),
        "question_text": task.get("question_text"),
        "question_type": task.get("question_type"),
        "question_set_version": task.get("question_set_version"),
        "region": task.get("region"),
        "service": task.get("service"),
        "intent": task.get("intent"),
        "provider": str(merged.get("provider") or ""),
        "model": str(merged.get("model") or ""),
        "model_version": str(merged.get("model_version") or ""),
        "tested_at": str(merged.get("tested_at") or now_iso()),
        "finished_at": now_iso(),
        "test_method": str(merged.get("test_method") or ""),
        "execution_origin": str(merged.get("execution_origin") or "human_browser"),
        "executor_id": str(task.get("executor_id") or merged.get("executor_id") or ""),
        "raw_answer": raw_answer,
        "answer_hash": hashlib.sha256(raw_answer.encode("utf-8")).hexdigest(),
        "brand_occurrences": brand_occurrences,
        "brand_mentioned": bool(deterministic_mention),
        "brand_recommended": bool(merged.get("brand_recommended")) if official_truth else False,
        "recommendation_position": merged.get("recommendation_position") if official_truth else None,
        "brand_cited": bool(deterministic_citation),
        "citation_urls": citation_urls,
        "extracted_urls": extracted_urls,
        "competitors": merged.get("competitors") or [],
        "fact_errors": merged.get("fact_errors") or [],
        "evidence_level": evidence_level,
        "official_truth": official_truth,
        "evidence_ref": str(merged.get("evidence_ref") or ""),
        "response_id": str(merged.get("response_id") or ""),
        "session_url": str(merged.get("session_url") or ""),
        "screenshot_path": str(merged.get("screenshot_path") or ""),
        "web_search_verified": bool(merged.get("web_search_verified")),
        "state": "succeeded",
        "failure_reason": "",
        "retry_count": int(task.get("retry_count") or 0),
        "attempt_id": str(task.get("attempt_id") or merged.get("attempt_id") or ""),
        "idempotency_key": str(task.get("idempotency_key") or ""),
        "opportunity_id": str(task.get("opportunity_id") or ""),
        "action_id": str(task.get("action_id") or task.get("seo_action_id") or ""),
        "content_revision_id": str(task.get("content_revision_id") or ""),
        "publication_event_id": str(task.get("publication_event_id") or ""),
        "publication_receipt_id": str(task.get("publication_receipt_id") or ""),
        "schedule_id": str(task.get("schedule_id") or ""),
        "analysis": merged.get("analysis") or {},
        "gap_task_id": str(merged.get("gap_task_id") or ""),
        "seo_action_id": str(merged.get("seo_action_id") or ""),
    }
    receipt["correlation"] = _correlation_for(task, receipt)

    receipts_payload = _load_receipts()
    receipts_payload["receipts"].append(receipt)
    _save_receipts(receipts_payload)

    task["state"] = "succeeded"
    task["updated_at"] = now_iso()
    task["evidence_id"] = receipt["evidence_id"]
    task["evidence_level"] = evidence_level
    task["official_truth"] = official_truth
    task["lease"] = {}
    task["normalized_state"] = "SUCCEEDED"
    attempts = task.get("attempts") if isinstance(task.get("attempts"), list) else []
    if attempts and str(attempts[-1].get("attempt_id") or "") == str(task.get("attempt_id") or ""):
        attempts[-1]["finished_at"] = receipt["finished_at"]
        attempts[-1]["result"] = "SUCCEEDED"
        attempts[-1]["receipt_id"] = evidence_id
    task["correlation"] = _correlation_for(task, receipt)
    _save_queue(queue)
    _audit(
        "geo_receipt_recorded",
        {
            "task_id": task_id,
            "run_id": receipt["run_id"],
            "evidence_id": evidence_id,
            "evidence_level": evidence_level,
            "official_truth": official_truth,
            "brand_occurrences": brand_occurrences,
            "brand_cited": deterministic_citation,
        },
    )
    return receipt


def fail_task(task_id, reason):
    return _transition(task_id, "failed", reason=reason)



def legacy_receipt_reconciliation(apply=False, approved_by=""):
    """Restore historical state only when an authoritative matching Receipt exists.

    Never repeat an external AI question from an ambiguous timeout. Existing
    A/B/C evidence levels and the original Receipt are immutable here.
    """
    from core.storage import _JSON_IO_LOCK
    if apply and approved_by != CONTROLLER:
        raise ValueError("geo_reconcile_requires_chatgpt_approval")
    with _JSON_IO_LOCK:
        queue = _load_queue()
        ledger = _load_receipts()
        tasks = list(queue.get("tasks") or [])
        stored_receipts = list(ledger.get("receipts") or [])
        by_identity = {}
        for receipt in stored_receipts:
            if not isinstance(receipt, dict):
                continue
            identity = (str(receipt.get("task_id") or ""), str(
                receipt.get("evidence_id") or receipt.get("receipt_id") or ""))
            if all(identity):
                by_identity.setdefault(identity, []).append(receipt)

        blocked = [task for task in tasks if task.get("state") == "authorization_required"]
        results = {"blocked": len(blocked), "safe_receipt_matches": 0,
                   "ambiguous_or_missing_receipt": 0,
                   "technical_waiting_review": 0,
                   "reconciled": 0, "backup_path": "",
                   "automatic_external_retries": 0, "new_evidence": 0,
                   "ready_to_auto_retry": 0}
        matches = []
        for task in blocked:
            if _blocked_reason_class(task.get("authorization_reason")) != "legacy_technical_requires_review":
                continue
            results["technical_waiting_review"] += 1
            identity = (str(task.get("task_id") or ""), str(task.get("evidence_id") or ""))
            found = by_identity.get(identity, [])
            def valid(receipt):
                same_q = str(receipt.get("question_id") or "") == str(task.get("question_id") or "")
                same_p = str(receipt.get("provider") or "") == str(task.get("provider") or "")
                url = str(receipt.get("session_url") or "")
                return (same_q and same_p and url.startswith("https://") and
                        "127.0.0.1" not in url and "localhost" not in url and
                        bool(str(receipt.get("tested_at") or "")) and
                        len(str(receipt.get("raw_answer") or "").strip()) >= 20)
            if len(found) != 1 or not valid(found[0]):
                results["ambiguous_or_missing_receipt"] += 1
                continue
            matches.append(task)
        results["safe_receipt_matches"] = len(matches)
        if not apply or not matches:
            return results

        # Snapshot must be written successfully before touching queue.json.
        snapshot = "geo_validation/backups/pre_legacy_receipt_reconcile_" + _new_id("", 16) + ".json"
        write_json(snapshot, queue)
        timestamp = now_iso()
        for task in matches:
            task["state"] = "succeeded"
            task["historical_authorization_reason"] = str(task.get("authorization_reason") or "")
            task["authorization_reason"] = ""
            task["legacy_receipt_reconciled_at"] = timestamp
            task["updated_at"] = timestamp
        _save_queue(queue)
        _audit("geo_legacy_receipt_state_reconciled", {
            "count": len(matches), "backup_path": snapshot,
            "note": "historical state fix only; zero new verified AI replies",
        })
        results["reconciled"] = len(matches)
        results["backup_path"] = snapshot
        return results



def queue_single_fresh_doubao_canary_once():
    """One user-authorized real browser trial, NEVER retry an ambiguous timeout.

    Runs only when the browser agent is online and has exhausted its ordinary
    queue, as gated by geo_browser_agent.claim. Persist the one-shot reservation
    before enqueueing so a crash cannot create duplicate external prompts.
    """
    from core.storage import _JSON_IO_LOCK
    marker_path = "geo_validation/one_shot_807_doubao_canary.json"
    with _JSON_IO_LOCK:
        marker = read_json(marker_path, {})
        if marker:
            return {"created": 0, "reason": "already_reserved",
                    "question_id": marker.get("question_id", "")}
        queue = _load_queue()
        # Pending unrelated work must not permanently starve the one authorized
        # fresh Doubao canary. An active Doubao execution *does* block it.
        if any(t.get("state") == "running" and (
                t.get("provider") in {"doubao_web", "doubao_search"}
                or t.get("expected_platform") == "doubao_web")
                for t in queue.get("tasks", [])):
            return {"created": 0, "reason": "doubao_execution_in_progress"}
        attempted = {
            str(t.get("question_id") or "") for t in queue.get("tasks", [])
            if t.get("provider") in {"doubao_web", "doubao_search"}
            or t.get("expected_platform") == "doubao_web"
        }
        attempted.update(
            str(r.get("question_id") or "")
            for r in _load_receipts().get("receipts", [])
            if r.get("provider") in {"doubao_web", "doubao_search"}
        )
        from core.geo_domestic_matrix import assignments
        all_questions = question_set().get("questions", [])
        doubao_slot_ids = set(assignments(all_questions).get("doubao_web") or [])
        fresh = next((
            q for q in all_questions
            if q.get("enabled", True) and
               q.get("question_id") in doubao_slot_ids and
               q.get("question_id") not in attempted and
               str(q.get("question_text") or "").strip()
        ), None)
        if not fresh:
            return {"created": 0, "reason": "no_untried_doubao_question"}
        question_id = str(fresh["question_id"])
        write_json(marker_path, {
            "status": "reserved", "question_id": question_id,
            "created_at": now_iso(), "max_external_prompts": 1,
            "purpose": "807_real_browser_e2e_canary",
        })
        plan = create_and_enqueue_plan(
            limit=1, provider="doubao_web", test_method="browser",
            expected_platform="doubao_web", question_ids=[question_id],
        )
        if plan.get("created") != 1:
            # Reservation remains to ensure fail-closed, not duplicate posts.
            return {"created": 0, "reason": "canary_enqueue_failed"}
        new_task = plan["tasks"][0]
        write_json(marker_path, {
            "status": "queued", "question_id": question_id,
            "task_id": new_task["task_id"], "created_at": now_iso(),
            "max_external_prompts": 1, "purpose": "807_real_browser_e2e_canary",
        })
        _audit("geo_807_single_fresh_doubao_canary_queued", {
            "task_id": new_task["task_id"], "question_id": question_id,
            "note": "one never-before-tested question on Doubao; no historical retry",
        })
        return {"created": 1, "task_id": new_task["task_id"],
                "question_id": question_id, "max_external_prompts": 1}


def legacy_blockage_review():
    """Return compact safe categorization without pretending old timeouts are unsent."""
    queue = _load_queue()
    all_tasks = list(queue.get("tasks") or [])
    blocked = [task for task in all_tasks if task.get("state") == "authorization_required"]
    outcomes = {"blocked": len(blocked), "timeout_answer": 0,
                "timeout_signal": 0, "other": 0,
                "has_prior_evidence_id": 0, "retries_exhausted": 0,
                "duplicate_success_same_question_provider": 0,
                "auto_retried": 0}
    succeeded = {(str(t.get("question_id") or ""), str(t.get("provider") or ""))
                 for t in all_tasks if t.get("state") == "succeeded"}
    for task in blocked:
        reason = str(task.get("authorization_reason") or "")
        if reason == "capture_failed:agent_response_timeout":
            outcomes["timeout_answer"] += 1
        elif reason == "capture_failed:signal timed out":
            outcomes["timeout_signal"] += 1
        else:
            outcomes["other"] += 1
        if task.get("evidence_id"):
            outcomes["has_prior_evidence_id"] += 1
        if int(task.get("retry_count") or 0) >= int(task.get("max_retries") or MAX_RETRIES):
            outcomes["retries_exhausted"] += 1
        if (str(task.get("question_id") or ""), str(task.get("provider") or "")) in succeeded:
            outcomes["duplicate_success_same_question_provider"] += 1
    outcomes["note"] = ("Ambiguous historical timeout is not proof of an unsent question. "
                        "No blocked task is automatically resent.")
    return outcomes


def _blocked_reason_class(reason):
    """Read-only diagnostic for old queue rows; never authorize auto-retries."""
    code = str(reason or "").strip().lower()
    technical = (
        "capture_failed:", "question_not_submitted", "unconfirmed_question",
        "agent_response_timeout", "doubao_answer_capture_timeout",
        "page_load_timeout", "signal timed out", "execution_timeout",
    )
    if code.startswith(technical):
        return "legacy_technical_requires_review"
    if any(word in code for word in ("captcha", "login", "oauth", "authorization",
                                    "permission", "account", "risk_control")):
        return "real_authorization_or_risk_control"
    return "unclassified_requires_review"


def _queue_diagnostics(tasks):
    """Pure read-only queue routing diagnostics shared by normal/fast APIs."""
    rows = [item for item in (tasks or []) if isinstance(item, dict)]
    queued_tasks = [item for item in rows if item.get("state") == "queued"]
    queued_routes = Counter(
        (str(item.get("provider") or "unspecified"),
         str(item.get("test_method") or "unspecified"),
         str(item.get("expected_platform") or ""))
        for item in queued_tasks
    )
    now_epoch = datetime.now(timezone.utc).timestamp()
    task_details = []
    for item in queued_tasks:
        provider = str(item.get("provider") or "")
        method = str(item.get("test_method") or "")
        platform = str(item.get("expected_platform") or "")
        try:
            retry_at = float(item.get("next_retry_at_epoch") or 0)
        except (TypeError, ValueError, OverflowError):
            retry_at = 0.0
        if method == "api" and provider == "cloud_auto" and not platform:
            executor = "doubao_cloud_api"
            route_state = "retry_backoff" if retry_at > now_epoch else "claimable_by_cloud_executor"
            reason = "等待豆包API退避到期" if retry_at > now_epoch else "由豆包API执行器领取；Chrome不会代领"
        elif method == "browser" and platform:
            executor = f"chrome_geo_extension:{platform}"
            route_state = "claimable_by_matching_browser"
            reason = f"仅由已登录的 {platform} 浏览器会话领取"
        elif method == "browser":
            executor = "unassigned_browser_platform"
            route_state = "routing_error"
            reason = "浏览器任务缺少expected_platform，安全策略禁止跨平台猜测领取"
        elif method == "api":
            executor = f"api:{provider or 'unassigned'}"
            route_state = "claimable_by_named_api" if provider else "routing_error"
            reason = "等待对应API执行器" if provider else "API任务缺少provider"
        else:
            executor = "unassigned"
            route_state = "routing_error"
            reason = "任务缺少可验证的执行方法或执行器"
        task_details.append({
            "task_id": str(item.get("task_id") or ""),
            "question_id": str(item.get("question_id") or ""),
            "provider": provider or "unspecified",
            "method": method or "unspecified",
            "expected_platform": platform,
            "executor": executor,
            "route_state": route_state,
            "wait_reason": reason,
            "created_at": str(item.get("created_at") or ""),
            "next_retry_at_epoch": retry_at or None,
            "mission_id": str(item.get("mission_id") or ""),
            "schedule_id": str(item.get("schedule_id") or ""),
            "uncertain_external_submission": bool(item.get("uncertain_external_submission")),
        })

    blocked = [item for item in rows if item.get("state") == "authorization_required"]
    blocked_classes = Counter(
        _blocked_reason_class(item.get("authorization_reason") or item.get("failure_reason"))
        for item in blocked
    )
    unbound_api = [
        item for item in queued_tasks
        if item.get("test_method") == "api"
        and item.get("provider") == "cloud_auto"
        and not item.get("expected_platform")
    ]
    return {
        "routing_diagnostics": {
            "queued_by_route": [
                {"provider": provider, "method": method,
                 "expected_platform": platform, "count": count}
                for (provider, method, platform), count in sorted(queued_routes.items())
            ],
            "queued_tasks": task_details,
            "unbound_cloud_auto_api": len(unbound_api),
            "unbound_cloud_auto_task_ids": [item.get("task_id") for item in unbound_api[:20]],
            "browser_agent_can_claim_unbound_api": False,
            "reason": "cloud_auto/api 由豆包API执行器处理；Chrome 网页代理严格按expected_platform领取，不能跨路由代领。",
            "mutated": False,
        },
        "blockage_diagnostics": {
            "legacy_technical_requires_review": blocked_classes.get("legacy_technical_requires_review", 0),
            "real_authorization_or_risk_control": blocked_classes.get("real_authorization_or_risk_control", 0),
            "unclassified_requires_review": blocked_classes.get("unclassified_requires_review", 0),
            "uncertain_external_submission": sum(
                1 for item in blocked if item.get("uncertain_external_submission")
                or "timeout" in str(item.get("authorization_reason") or "").lower()
                or "timed out" in str(item.get("authorization_reason") or "").lower()
            ),
            "auto_requeued": 0,
            "note": "诊断不改状态；旧技术失败、登录/验证码和未知阻塞必须分别处理，禁止批量重试。",
        },
    }


def queue_summary():
    tasks = _load_queue()["tasks"]
    counts = Counter(item.get("state") or "unknown" for item in tasks)
    diagnostics = _queue_diagnostics(tasks)
    return {
        "total": len(tasks),
        "queued": counts.get("queued", 0),
        "running": counts.get("running", 0),
        "succeeded": counts.get("succeeded", 0),
        "failed": counts.get("failed", 0),
        "paused": counts.get("paused", 0),
        "authorization_required": counts.get("authorization_required", 0),
        **diagnostics,
        "tasks": tasks,
    }


def receipts(limit=200):
    items = list(reversed(_load_receipts()["receipts"]))
    return items[: max(1, min(int(limit or 200), 1000))]


def manual_requirements():
    tasks = [
        item
        for item in _load_queue()["tasks"]
        if item.get("state") == "authorization_required"
    ]
    return {
        "count": len(tasks),
        "items": [
            {
                "task_id": item.get("task_id"),
                "provider": item.get("provider"),
                "question_id": item.get("question_id"),
                "reason": item.get("authorization_reason")
                or "external_platform_authorization_required",
                "action_type": (
                    "inspect_technical_failure_no_auto_retry"
                    if _blocked_reason_class(item.get("authorization_reason")) == "legacy_technical_requires_review"
                    else "login_oauth_captcha_or_permission"
                    if _blocked_reason_class(item.get("authorization_reason")) == "real_authorization_or_risk_control"
                    else "investigate_blocking_reason"
                ),
                "reason_class": _blocked_reason_class(item.get("authorization_reason")),
            }
            for item in tasks
        ],
    }


def _evidence_complete(item):
    required = ("evidence_id", "question_text", "raw_answer", "provider", "model", "tested_at")
    proof = any(str(item.get(key) or "").strip() for key in ("evidence_ref", "response_id", "session_url", "screenshot_path"))
    return all(str(item.get(key) or "").strip() for key in required) and proof


def _retest_coverage(official):
    by_question = {}
    for item in official:
        try:
            tested = datetime.fromisoformat(str(item.get("tested_at") or "").replace("Z", "+00:00"))
            if tested.tzinfo is None:
                tested = tested.replace(tzinfo=timezone.utc)
            tested = tested.astimezone(timezone.utc)
        except (TypeError, ValueError, OverflowError):
            continue
        by_question.setdefault(str(item.get("question_id") or ""), []).append(tested)
    now = datetime.now(timezone.utc)
    result = {}
    for label, hours in (("24h", 24), ("72h", 72), ("7d", 168)):
        due = complete = 0
        for stamps in by_question.values():
            stamps.sort()
            if now >= stamps[0] + timedelta(hours=hours):
                due += 1
                if any(stamp >= stamps[0] + timedelta(hours=hours) for stamp in stamps[1:]):
                    complete += 1
        result[label] = {
            "due": due,
            "complete": complete,
            "remaining": max(0, due - complete),
            "coverage_percent": round(complete / due * 100, 1) if due else None,
        }
    return result


def dashboard():
    qset = question_set()
    queue = queue_summary()
    all_receipts = _load_receipts()["receipts"]
    official = [
        item
        for item in all_receipts
        if item.get("official_truth")
        and item.get("evidence_level") in OFFICIAL_EVIDENCE_LEVELS
    ]
    tested_ids = {item.get("question_id") for item in official}
    mentioned_ids = {
        item.get("question_id") for item in official if item.get("brand_mentioned")
    }
    cited_ids = {item.get("question_id") for item in official if item.get("brand_cited")}
    recommended_ids = {
        item.get("question_id") for item in official if item.get("brand_recommended")
    }
    complete_evidence = [item for item in official if _evidence_complete(item)]
    by_type = {}
    for kind in ("discovery", "commercial", "brand"):
        ids = {
            item["question_id"]
            for item in qset["questions"]
            if item["question_type"] == kind
        }
        by_type[kind] = {
            "total": len(ids),
            "tested": len(ids & tested_ids),
            "mentioned": len(ids & mentioned_ids),
            "cited": len(ids & cited_ids),
            "recommended": len(ids & recommended_ids),
        }

    total = len(qset["questions"])
    tested = len(tested_ids)
    from core.geo_domestic_matrix import snapshot as domestic_snapshot
    domestic = domestic_snapshot(all_receipts, qset["questions"], queue_summary().get("tasks") or [])
    return {
        "phase": "R8-19 GEO Phase 1",
        "controller": CONTROLLER,
        "seo_development": "frozen_keep_runtime",
        "question_set": {
            "version": qset["version"],
            "total": total,
            "counts": qset["counts"],
            "question_set_hash": qset.get("question_set_hash", ""),
            "immutable_within_version": bool(qset.get("immutable_within_version", True)),
            "by_type": by_type,
        },
        "official": {
            "measurement_state": "measured" if official else "not_started",
            "tested": tested,
            "remaining": max(0, total - tested),
            "mentioned": len(mentioned_ids),
            "cited": len(cited_ids),
            "recommended": len(recommended_ids),
            "mention_rate": round(len(mentioned_ids) / tested * 100, 1) if tested else None,
            "citation_rate": round(len(cited_ids) / tested * 100, 1) if tested else None,
            "recommendation_rate": round(len(recommended_ids) / tested * 100, 1) if tested else None,
            "evidence_count": len(official),
            "effect_proven": bool(mentioned_ids or cited_ids or recommended_ids),
        },
        "domestic_matrix": domestic,
        "evidence_completeness": {
            "complete": len(complete_evidence),
            "incomplete": max(0, len(official) - len(complete_evidence)),
            "required_fields": ["原始问题", "原始回答", "模型", "测试时间", "回执/截图/会话引用"],
        },
        "retest_coverage": _retest_coverage(official),
        "business_effect_tracking": {
            "mention": "measured",
            "recommendation": "measured",
            "citation": "measured",
            "visits": "phase2_not_connected",
            "consultations": "phase2_not_connected",
            "orders": "phase2_not_connected",
            "revenue": "phase2_not_connected",
        },
        "simulation": {
            "count": len(
                [item for item in all_receipts if item.get("evidence_level") == "C"]
            ),
            "counts_in_official_metrics": False,
        },
        "queue": {key: value for key, value in queue.items() if key != "tasks"},
        "manual": manual_requirements(),
        "decision": decision(),
        "retry_policy": {
            "max_retries": MAX_RETRIES,
            "approval_controller": CONTROLLER,
        },
        "evidence_policy": {
            "official_levels": sorted(OFFICIAL_EVIDENCE_LEVELS),
            "simulation_level": "C",
            "local_model_counts_as_official": False,
        },
        "phase2_reserved": [
            "geo_analyzer",
            "geo_score",
            "competitor_radar",
            "fact_accuracy",
        ],
        "phase3_reserved": [
            "dynamic_question_pool",
            "retest_schedule",
            "gap_engine",
            "seo_action_queue",
        ],
    }
