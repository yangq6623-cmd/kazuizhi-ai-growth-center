"""Match Phase-3 retests by their durable task IDs, not second-level timestamps.

The shared storage clock intentionally uses second precision. A fast offline run
can create the action and its retest within the same second, so time-only
matching is ambiguous. Production already persists retest_task_id on each
Phase-3 action; use that durable link first and fall back to evidence exclusion.
"""
from __future__ import annotations

from core import geo_analysis, geo_phase3, geo_validation


def _receipt_for_action(action, current):
    qid = str((action or {}).get("question_id") or "")
    task_id = str((action or {}).get("retest_task_id") or "")
    baseline_id = str((action or {}).get("baseline_evidence_id") or "")
    since = str((current or {}).get("execution_started_at") or (current or {}).get("baseline_at") or "")
    candidates = []
    for item in geo_validation.receipts(1000):
        if str(item.get("question_id") or "") != qid:
            continue
        if not item.get("official_truth") or item.get("evidence_level") not in geo_validation.OFFICIAL_EVIDENCE_LEVELS:
            continue
        evidence_id = str(item.get("evidence_id") or item.get("receipt_id") or "")
        if baseline_id and evidence_id == baseline_id:
            continue
        if task_id and str(item.get("task_id") or "") != task_id:
            continue
        stamp = str(item.get("tested_at") or item.get("finished_at") or "")
        if not task_id and since and stamp < since:
            continue
        candidates.append(item)
    # geo_validation.receipts() is newest-first; exact task-id matches remain
    # deterministic even when timestamps are identical to the second.
    return candidates[0] if candidates else None


def _before_after(current):
    rows = []
    for action in (current or {}).get("actions") or []:
        qid = str(action.get("question_id") or "")
        if not qid:
            continue
        receipt = _receipt_for_action(action, current)
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


geo_phase3._before_after = _before_after
