"""#872 isolated regression for exact GEO reconciliation at browser claim.

All ledgers are synthetic under a temporary LOCALAPPDATA.  No browser, paid
API, production ledger, external prompt, publication or search submission is
used by this test.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))

sandbox = Path(tempfile.mkdtemp(prefix="kazuizhi-872-geo-reconcile-"))
previous = os.environ.get("LOCALAPPDATA")
os.environ["LOCALAPPDATA"] = str(sandbox)


def task(task_id: str, suffix: str) -> dict:
    return {
        "task_id": task_id,
        "question_id": f"GEO50-D{suffix}",
        "state": "queued",
        "provider": "deepseek_web",
        "test_method": "browser",
        "expected_platform": "deepseek_web",
        "run_id": f"RUN-{suffix}",
        "attempt_id": f"ATTEMPT-{suffix}",
        "started_at": "2026-10-23T10:00:00+08:00",
        "attempts": [{
            "run_id": f"RUN-{suffix}",
            "attempt_id": f"ATTEMPT-{suffix}",
            "result": "RUNNING",
        }],
    }


def receipt(task_id: str, suffix: str, receipt_id: str) -> dict:
    return {
        "task_id": task_id,
        "question_id": f"GEO50-D{suffix}",
        "provider": "deepseek_web",
        "run_id": f"RUN-{suffix}",
        "attempt_id": f"ATTEMPT-{suffix}",
        "evidence_id": receipt_id,
        "receipt_id": receipt_id,
        "tested_at": "2026-10-23T10:02:00+08:00",
        "finished_at": "2026-10-23T10:02:30+08:00",
        "session_url": f"https://chat.deepseek.com/a/{suffix}",
        "raw_answer": "这是隔离账本中已经存在的真实回答结构；测试只做本地关联，不再次发送外部问题。",
        "evidence_level": "A",
        "official_truth": True,
    }


try:
    from core import geo_validation as geo
    from core.storage import write_json

    exact = "GEO-TASK-872-EXACT"
    ambiguous = "GEO-TASK-872-AMBIGUOUS"
    missing = "GEO-TASK-872-MISSING"
    tasks = [task(exact, "01"), task(ambiguous, "02"), task(missing, "03")]
    receipts = [
        receipt(exact, "01", "GEO-RECEIPT-872-EXACT"),
        receipt(ambiguous, "02", "GEO-RECEIPT-872-A"),
        receipt(ambiguous, "02", "GEO-RECEIPT-872-B"),
    ]
    write_json(geo.QUEUE_PATH, {"tasks": tasks})
    write_json(geo.RECEIPTS_PATH, {"receipts": receipts})

    before = geo.queue_summary()
    details = {
        row["task_id"]: row
        for row in before["routing_diagnostics"]["queued_tasks"]
    }
    assert details[exact]["run_id"] == "RUN-01"
    assert details[exact]["attempt_id"] == "ATTEMPT-01"
    assert details[exact]["reconciliation_disposition"] == "unique_authoritative_receipt"
    assert details[exact]["matching_receipt_count"] == 1
    assert details[ambiguous]["reconciliation_disposition"] == "ambiguous_multiple_receipts_hold"
    assert details[ambiguous]["matching_receipt_count"] == 2
    assert details[missing]["reconciliation_disposition"] == "prior_attempt_without_matching_receipt_hold"
    assert before["reconciliation_preview"]["applicable"] == 1
    assert before["reconciliation_preview"]["mutated"] is False

    original_receipt_count = len(geo._load_receipts()["receipts"])
    claim = geo.claim_next_task({
        "real_external": True,
        "authorization_ready": True,
        "provider_ready": True,
        "provider": "deepseek_web",
        "test_method": "browser",
        "executor_id": "chrome_geo_extension:deepseek_web",
        "strict_provider": True,
        "fresh_only": True,
    })
    assert claim["skipped"] is True and claim["reason"] == "queue_blocked", claim
    after = {row["task_id"]: row for row in geo._load_queue()["tasks"]}
    assert after[exact]["state"] == "succeeded"
    assert after[exact]["evidence_id"] == "GEO-RECEIPT-872-EXACT"
    assert after[ambiguous]["state"] == "queued"
    assert after[missing]["state"] == "queued"
    assert len(geo._load_receipts()["receipts"]) == original_receipt_count
    assert len(after[ambiguous]["attempts"]) == 1
    assert len(after[missing]["attempts"]) == 1

    geo_ui = (SOURCE / "web" / "geo-growth-os.js").read_text(encoding="utf-8")
    seo_ui = (SOURCE / "web" / "r8_13_seo_geo.html").read_text(encoding="utf-8")
    endpoint = (SOURCE / "backend" / "r8_19_geo_validation_patch.py").read_text(encoding="utf-8")
    assert "Run ${x.run_id||'—'}" in geo_ui
    assert "对账 ${x.reconciliation_disposition||'未检查'}" in geo_ui
    assert "GEO机会发布事件URL（去重）" in geo_ui
    assert "今日Asset首次公开" in seo_ui
    assert '"error": "task_id_required"' in endpoint

    print(
        "PASS #872: exact Receipt auto-links before browser claim; ambiguous/missing "
        "attempts remain blocked; no external send or new Evidence"
    )
finally:
    if previous is None:
        os.environ.pop("LOCALAPPDATA", None)
    else:
        os.environ["LOCALAPPDATA"] = previous
    shutil.rmtree(sandbox, ignore_errors=True)
