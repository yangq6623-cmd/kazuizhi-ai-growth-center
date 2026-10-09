"""R8-19 GEO validation core.

Phase 1 turns the existing GEO question concept into a truth-gated work queue.
ChatGPT remains the controller. Local models may assist with preparation or
analysis, but local simulation can never count as official GEO evidence.
"""

from __future__ import annotations

import hashlib
import json
import re
import uuid
from collections import Counter
from datetime import datetime, timedelta, timezone

from core.storage import now_iso, read_json, write_json

QUESTION_SET_VERSION = "GEO50-V2-20260930"
CONTROLLER = "chatgpt"
BRAND_NAME = "卡嘴子"
OFFICIAL_DOMAIN = "kazuizhi.com"
MAX_RETRIES = 2

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


def create_plan(limit=10, provider="external_ai", test_method="browser", mission_id="", question_ids=None):
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
    return {
        "plan_id": plan_id,
        "controller": CONTROLLER,
        "decision_id": current_decision["decision_id"],
        "command_id": current_decision["command_id"],
        "mission_id": mission_id or current_decision.get("mission_id"),
        "provider": str(provider or "external_ai"),
        "test_method": test_method,
        "question_set_version": QUESTION_SET_VERSION,
        "created_at": now_iso(),
        "questions": selected,
        "count": len(selected),
        "max_retries": MAX_RETRIES,
    }


def enqueue_plan(plan):
    queue = _load_queue()
    created = []
    for question in plan.get("questions") or []:
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
            "test_method": plan.get("test_method"),
            "state": "queued",
            "retry_count": 0,
            "max_retries": int(plan.get("max_retries") or MAX_RETRIES),
            "run_id": "",
            "executor_id": "",
            "created_at": now_iso(),
            "updated_at": now_iso(),
            "started_at": "",
            "failure_reason": "",
            "failure_code": "",
            "authorization_reason": "",
            "scheduled_retest_at": "",
            "gap_task_id": "",
            "seo_action_id": "",
        }
        queue["tasks"].append(task)
        created.append(task)
    _save_queue(queue)
    _audit(
        "geo_plan_enqueued",
        {
            "plan_id": plan.get("plan_id"),
            "decision_id": plan.get("decision_id"),
            "command_id": plan.get("command_id"),
            "mission_id": plan.get("mission_id"),
            "created": len(created),
        },
    )
    return {"ok": True, "created": len(created), "tasks": created, "plan_id": plan.get("plan_id")}


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
    elif target == "authorization_required":
        task["authorization_reason"] = str(reason or "external_authorization_required")
    _save_queue(queue)
    _audit("geo_task_transition", {"task_id": task_id, "state": target, "reason": str(reason or "")})
    return task


def pause_task(task_id):
    queue, task = _find_task(task_id)
    if task["state"] not in {"queued", "running", "authorization_required"}:
        raise ValueError("geo_task_cannot_pause")
    task["state"] = "paused"
    task["updated_at"] = now_iso()
    _save_queue(queue)
    _audit("geo_task_paused", {"task_id": task_id})
    return task


def resume_task(task_id):
    queue, task = _find_task(task_id)
    if task["state"] != "paused":
        raise ValueError("geo_task_not_paused")
    task["state"] = "queued"
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
    retry_count = int(task.get("retry_count") or 0)
    max_retries = int(task.get("max_retries") or MAX_RETRIES)
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
    task["updated_at"] = now_iso()
    _save_queue(queue)
    _audit("geo_task_retried", {"task_id": task_id, "retry_count": task["retry_count"]})
    return task


def claim_next_task(executor=None):
    """Claim one task only when a real external executor is explicitly ready.

    A generic/local model can never satisfy this contract. Provider or
    authorization failures affect only the claimed task and never terminate the
    remaining queue.
    """
    executor = dict(executor or {})
    queue = _load_queue()
    task = next((item for item in queue["tasks"] if item.get("state") == "queued"), None)
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
        task["started_at"] = now_iso()

    task["updated_at"] = now_iso()
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
    payload = dict(payload or {})
    task_id = str(payload.get("task_id") or "").strip()
    if not task_id:
        raise ValueError("task_id_required")
    queue, task = _find_task(task_id)
    if task.get("state") not in {"running", "queued", "authorization_required"}:
        raise ValueError("geo_task_not_accepting_receipt")

    merged = dict(task)
    merged.update(payload)
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
        "analysis": merged.get("analysis") or {},
        "gap_task_id": str(merged.get("gap_task_id") or ""),
        "seo_action_id": str(merged.get("seo_action_id") or ""),
    }

    receipts_payload = _load_receipts()
    receipts_payload["receipts"].append(receipt)
    _save_receipts(receipts_payload)

    task["state"] = "succeeded"
    task["updated_at"] = now_iso()
    task["evidence_id"] = receipt["evidence_id"]
    task["evidence_level"] = evidence_level
    task["official_truth"] = official_truth
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


def queue_summary():
    tasks = _load_queue()["tasks"]
    counts = Counter(item.get("state") or "unknown" for item in tasks)
    return {
        "total": len(tasks),
        "queued": counts.get("queued", 0),
        "running": counts.get("running", 0),
        "succeeded": counts.get("succeeded", 0),
        "failed": counts.get("failed", 0),
        "paused": counts.get("paused", 0),
        "authorization_required": counts.get("authorization_required", 0),
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
                "action_type": "login_oauth_captcha_or_permission",
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
