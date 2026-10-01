"""Phase-2 closure patch: current metrics use the latest A/B receipt per question.

Phase 3 introduces real retests. Counting every historical retest as another
question would make Phase-2 analysed counts diverge from the 50-question truth
ledger. This additive patch keeps full receipt history but projects only the
latest official A/B receipt for each question into current visibility metrics.
"""
from __future__ import annotations

from core import geo_analysis
from core.storage import now_iso

_ORIGINAL_REFRESH = geo_analysis.refresh


def _latest_official(items):
    latest = {}
    for item in items:
        if not item.get("official_truth"):
            continue
        qid = str(item.get("question_id") or "")
        if not qid:
            continue
        stamp = str(item.get("tested_at") or item.get("finished_at") or "")
        previous = latest.get(qid)
        previous_stamp = str((previous or {}).get("tested_at") or (previous or {}).get("finished_at") or "")
        if previous is None or stamp >= previous_stamp:
            latest[qid] = item
    return list(latest.values())


def refresh(receipts):
    analysed_all = [geo_analysis.analyze_receipt(item) for item in list(receipts or [])]
    official_history = [item for item in analysed_all if item.get("official_truth")]
    current_official = _latest_official(official_history)
    auxiliary = [item for item in analysed_all if not item.get("official_truth")]
    summary = geo_analysis._aggregate(current_official + auxiliary)
    snapshot = {
        "analysis_version": geo_analysis.ANALYSIS_VERSION,
        "controller": "chatgpt",
        "source_policy": "当前指标每题只取最新A/B Evidence；历史复测保留在Receipt账本。C级本地/普通云端辅助不进入正式指标。",
        "generated_at": now_iso(),
        "summary": summary,
        "question_results": current_official,
        "auxiliary_count": len(auxiliary),
        "official_history_count": len(official_history),
        "retest_count": max(0, len(official_history) - len(current_official)),
        "chatgpt_judgement": {
            "status": "pending",
            "required": bool(current_official),
            "reason": "当前事实由每题最新真实A/B证据确定；战略解释、任务优先级和下一步行动仍由ChatGPT总脑决定。",
        },
        "next_stage_reserved": ["gap_to_task", "content_action", "retest", "before_after"],
    }
    return geo_analysis._save_snapshot(snapshot)


geo_analysis.refresh = refresh
