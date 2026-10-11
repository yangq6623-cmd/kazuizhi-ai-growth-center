"""Truth-gated domestic GEO validation matrix.

The first formal domestic baseline is 50 independent platform/question slots:
10 each for Doubao, Douyin, DeepSeek, Qwen and 360 AI Search. Foreign AI
results remain useful auxiliary observations but never advance this baseline.
"""
from __future__ import annotations

from collections import OrderedDict
from datetime import datetime, timedelta, timezone


SCHEMA = "kz.geo-domestic-matrix.v1"
VERSION = "CN-GEO50-V1-20261011"
TARGET_PER_PLATFORM = 10

PLATFORMS = OrderedDict([
    ("doubao_web", {
        "label": "豆包", "aliases": {"doubao_web", "doubao_search"},
        "access": "网页端真实检索；API可选", "authorization": "登录/验证码出现时需人工处理",
    }),
    ("douyin_search_web", {
        "label": "抖音", "aliases": {"douyin_search_web", "douyin_search", "douyin_web"},
        "access": "浏览器真实搜索；发布能力另行授权", "authorization": "需要抖音账号登录及平台发布授权",
    }),
    ("deepseek_web", {
        "label": "DeepSeek", "aliases": {"deepseek_web", "deepseek_search"},
        "access": "网页端真实检索；API可选", "authorization": "登录/验证码出现时需人工处理",
    }),
    ("qwen_web", {
        "label": "通义千问", "aliases": {"qwen_web", "qwen_search", "tongyi_web"},
        "access": "网页端真实检索；API可选", "authorization": "登录/验证码出现时需人工处理",
    }),
    ("so360_ai_search", {
        "label": "360 AI搜索", "aliases": {"so360_ai_search", "360_ai_search", "so360_web"},
        "access": "浏览器真实搜索；站点提交另走站长平台", "authorization": "登录/验证码或站点验证时需人工处理",
    }),
])

ALIAS_TO_PLATFORM = {
    alias.lower(): platform
    for platform, config in PLATFORMS.items()
    for alias in config["aliases"]
}


def normalize_platform(value):
    return ALIAS_TO_PLATFORM.get(str(value or "").strip().lower(), "")


def assignments(questions):
    rows = list(questions or [])[:50]
    result = {}
    for index, platform in enumerate(PLATFORMS):
        result[platform] = [
            str(item.get("question_id") or "")
            for item in rows[index * TARGET_PER_PLATFORM:(index + 1) * TARGET_PER_PLATFORM]
            if item.get("question_id")
        ]
    return result


def _complete(item):
    required = ("evidence_id", "question_text", "raw_answer", "provider", "model", "tested_at")
    proof = any(str(item.get(key) or "").strip() for key in
                ("evidence_ref", "response_id", "session_url", "screenshot_path"))
    return all(str(item.get(key) or "").strip() for key in required) and proof


def snapshot(receipts, questions, tasks=None):
    allocation = assignments(questions)
    official = [
        row for row in (receipts or [])
        if isinstance(row, dict) and row.get("official_truth")
        and str(row.get("evidence_level") or "").upper() in {"A", "B"}
    ]
    completed_slots = set()
    incomplete_slots = set()
    evidence_by_slot = {}
    receipts_by_slot = {}
    auxiliary = 0
    mismatched = 0
    for receipt in official:
        platform = normalize_platform(receipt.get("provider"))
        question_id = str(receipt.get("question_id") or "")
        if not platform:
            auxiliary += 1
            continue
        if question_id not in allocation.get(platform, []):
            mismatched += 1
            continue
        slot = (platform, question_id)
        if _complete(receipt):
            completed_slots.add(slot)
            evidence_by_slot[slot] = receipt.get("evidence_id") or receipt.get("receipt_id")
            receipts_by_slot.setdefault(slot, []).append(receipt)
        else:
            incomplete_slots.add(slot)

    active_states = {"queued", "running", "authorization_required", "paused"}
    active_slots = set()
    authorization_slots = set()
    for task in tasks or []:
        if not isinstance(task, dict) or task.get("state") not in active_states:
            continue
        platform = normalize_platform(task.get("expected_platform"))
        question_id = str(task.get("question_id") or "")
        if platform and question_id in allocation.get(platform, []):
            active_slots.add((platform, question_id))
            if task.get("state") == "authorization_required":
                authorization_slots.add((platform, question_id))

    platform_rows = []
    for platform, config in PLATFORMS.items():
        question_ids = allocation.get(platform, [])
        completed = sum((platform, qid) in completed_slots for qid in question_ids)
        active = sum((platform, qid) in active_slots for qid in question_ids)
        waiting_auth = sum((platform, qid) in authorization_slots for qid in question_ids)
        missing = [qid for qid in question_ids if (platform, qid) not in completed_slots]
        platform_rows.append({
            "platform": platform,
            "label": config["label"],
            "target": len(question_ids),
            "completed": completed,
            "remaining": max(0, len(question_ids) - completed),
            "active": active,
            "authorization_required": waiting_auth,
            "question_ids": question_ids,
            "missing_question_ids": missing,
            "access": config["access"],
            "authorization": config["authorization"],
            "api_required": False,
            "state": "complete" if question_ids and completed == len(question_ids)
                     else "authorization_required" if waiting_auth
                     else "in_progress" if active or completed
                     else "not_started",
        })

    completed = len(completed_slots)
    activated = bool(
        any(normalize_platform(row.get("provider")) for row in official)
        or any(normalize_platform(row.get("expected_platform")) for row in (tasks or []) if isinstance(row, dict))
    )
    mentioned = {slot for slot, rows in receipts_by_slot.items() if any(row.get("brand_mentioned") for row in rows)}
    recommended = {slot for slot, rows in receipts_by_slot.items() if any(row.get("brand_recommended") for row in rows)}
    cited = {slot for slot, rows in receipts_by_slot.items() if any(row.get("brand_cited") for row in rows)}
    automatic = {
        slot for slot, rows in receipts_by_slot.items()
        if any(
            str(row.get("test_method") or "").lower() == "api"
            or str(row.get("execution_origin") or "") == "authenticated_browser_agent"
            for row in rows
        )
    }
    manual = {
        slot for slot, rows in receipts_by_slot.items()
        if slot not in automatic and any(
            str(row.get("test_method") or "").lower() in {"manual", "browser"}
            for row in rows
        )
    }
    retest = {}
    now = datetime.now(timezone.utc)
    for label, hours in (("24h", 24), ("72h", 72), ("7d", 168)):
        due = done = 0
        for rows in receipts_by_slot.values():
            stamps = []
            for row in rows:
                try:
                    stamp = datetime.fromisoformat(str(row.get("tested_at") or "").replace("Z", "+00:00"))
                    if stamp.tzinfo is None:
                        stamp = stamp.replace(tzinfo=timezone.utc)
                    stamps.append(stamp.astimezone(timezone.utc))
                except (TypeError, ValueError, OverflowError):
                    continue
            stamps.sort()
            if stamps and now >= stamps[0] + timedelta(hours=hours):
                due += 1
                if any(stamp >= stamps[0] + timedelta(hours=hours) for stamp in stamps[1:]):
                    done += 1
        retest[label] = {"due": due, "complete": done, "remaining": max(0, due - done)}
    return {
        "schema": SCHEMA,
        "version": VERSION,
        "scope": "china_domestic_primary",
        "activated": activated,
        "completed": completed,
        "target": sum(len(value) for value in allocation.values()),
        "remaining": max(0, 50 - completed),
        "evidence_complete": len(completed_slots),
        "evidence_incomplete": len(incomplete_slots - completed_slots),
        "mentioned": len(mentioned),
        "recommended": len(recommended),
        "cited": len(cited),
        "mention_rate": round(len(mentioned) / completed * 100, 1) if completed else None,
        "recommendation_rate": round(len(recommended) / completed * 100, 1) if completed else None,
        "citation_rate": round(len(cited) / completed * 100, 1) if completed else None,
        "manual_completed": len(manual),
        "automatic_completed": len(automatic),
        "retest_coverage": retest,
        "foreign_or_other_auxiliary_evidence": auxiliary,
        "platform_mismatch_evidence": mismatched,
        "platforms": platform_rows,
        "truth_rule": "仅五个国内平台各自指定问题的真实完整A/B级外部证据计入50条；API不是必需项。",
        "excluded_from_score": ["ChatGPT", "Google", "Bing", "本地模型", "C级回答", "queued/running/SUBMITTED"],
    }


def prepare_missing(limit=50, platform="", mission_id=""):
    """Create missing domestic slots without claiming external success."""
    from core import geo_validation as geo

    questions = geo.question_set().get("questions") or []
    existing_receipts = geo.receipts(1000)
    existing_tasks = geo.queue_summary().get("tasks") or []
    current = snapshot(existing_receipts, questions, existing_tasks)
    requested_platform = normalize_platform(platform)
    candidates = []
    for row in current["platforms"]:
        if requested_platform and row["platform"] != requested_platform:
            continue
        for question_id in row["missing_question_ids"]:
            if any(normalize_platform(task.get("expected_platform")) == row["platform"]
                   and task.get("question_id") == question_id
                   and task.get("state") in {"queued", "running", "authorization_required", "paused"}
                   for task in existing_tasks):
                continue
            candidates.append((row["platform"], question_id))

    requested = max(1, min(int(limit or 50), 50))
    created = []
    for expected_platform, question_id in candidates[:requested]:
        result = geo.create_and_enqueue_plan(
            limit=1,
            provider="browser_external_ai",
            test_method="browser",
            mission_id=mission_id,
            question_ids=[question_id],
            expected_platform=expected_platform,
        )
        created.extend(result.get("tasks") or [])
    return {
        "ok": True, "created": len(created), "tasks": created,
        "matrix": snapshot(existing_receipts, questions, existing_tasks + created),
        "truth_rule": "只准备任务；未获得真实外部回执前不计完成。",
    }
