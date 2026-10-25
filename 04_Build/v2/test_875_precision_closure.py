"""#875 precision-closure regression tests.

All ledgers live under a temporary LOCALAPPDATA directory.  The test performs
no browser action, external request, publication, search submission, paid API
call, credential access, or production mutation.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))
sandbox = Path(tempfile.mkdtemp(prefix="kazuizhi-875-precision-"))
previous = os.environ.get("LOCALAPPDATA")
os.environ["LOCALAPPDATA"] = str(sandbox)


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


try:
    from core import geo_domestic_matrix
    from core import geo_validation as geo
    from core import storage

    # 1. A recent-activity window may contain no formal evidence, while the
    # immutable formal ledger must still expose all 50 valid Question IDs.
    questions = geo._fixed_questions()
    qmap = {row["question_id"]: row for row in questions}
    formal = []
    for provider, question_ids in geo_domestic_matrix.assignments(questions).items():
        for question_id in question_ids:
            formal.append({
                "evidence_id": f"E-{question_id}",
                "receipt_id": f"E-{question_id}",
                "question_id": question_id,
                "question_text": qmap[question_id]["question_text"],
                "provider": provider,
                "model": "synthetic-browser",
                "raw_answer": "隔离环境中的完整回答；不代表生产证据。",
                "tested_at": "2026-10-01T10:00:00+08:00",
                "session_url": f"https://example.invalid/{question_id}",
                "official_truth": True,
                "evidence_level": "A",
            })
    auxiliary = [{
        "evidence_id": f"C-{index}",
        "receipt_id": f"C-{index}",
        "question_id": f"AUX-{index}",
        "provider": "cloud_auto",
        "model": "synthetic-api",
        "raw_answer": "隔离辅助信号",
        "tested_at": "2026-10-24T10:00:00+08:00",
        "official_truth": False,
        "evidence_level": "C",
    } for index in range(1000)]
    storage.write_json(geo.RECEIPTS_PATH, {"receipts": formal + auxiliary})
    assert len(geo.receipts(1000)) == 1000
    assert len(geo.formal_receipts()) == 50
    matrix = geo_domestic_matrix.snapshot(geo.formal_receipts(), questions)
    assert matrix["completed"] == 50, matrix
    assert matrix["target"] == 50, matrix

    # 2. Equivalent external work must reuse the existing Task even if a new
    # Controller Plan ID is generated.  A distinct scheduled retest remains a
    # distinct action, while the same schedule is still idempotent.
    storage.write_json(geo.QUEUE_PATH, {"tasks": []})
    geo.set_decision({
        "decision_id": "DECISION-875-TEST",
        "command_id": "COMMAND-875-TEST",
        "mission_id": "MISSION-875-TEST",
        "daily_test_limit": 10,
    })
    kwargs = {
        "limit": 1,
        "provider": "deepseek_web",
        "expected_platform": "deepseek_web",
        "test_method": "browser",
        "mission_id": "MISSION-875-TEST",
        "question_ids": ["GEO50-D21"],
    }
    first = geo.enqueue_plan(geo.create_plan(**kwargs))
    repeated = geo.enqueue_plan(geo.create_plan(**kwargs))
    assert first["created"] == 1
    assert repeated["created"] == 0
    assert len(repeated["reused_task_ids"]) == 1
    assert repeated["reused_task_ids"][0] == first["tasks"][0]["task_id"]

    scheduled_kwargs = dict(kwargs)
    scheduled_kwargs["correlation"] = {"schedule_id": "SCHEDULE-24H-875"}
    scheduled = geo.enqueue_plan(geo.create_plan(**scheduled_kwargs))
    scheduled_repeat = geo.enqueue_plan(geo.create_plan(**scheduled_kwargs))
    assert scheduled["created"] == 1
    assert scheduled_repeat["created"] == 0
    assert len(scheduled_repeat["reused_task_ids"]) == 1

    # 3. A queued task with an earlier external attempt and no authoritative
    # Receipt stays byte-for-byte isolated.  A new Plan cannot create the same
    # action again, while a different, fresh question can still be claimed.
    task_id = "GEO-TASK-875-UNKNOWN"
    attempted_at = now_iso()
    unknown = {
        "task_id": task_id,
        "plan_id": "PLAN-875-UNKNOWN",
        "mission_id": "MISSION-875-TEST",
        "question_id": "GEO50-D22",
        "question_text": "隔离环境中的安全问题",
        "provider": "deepseek_web",
        "expected_platform": "deepseek_web",
        "test_method": "browser",
        "state": "queued",
        "run_id": "RUN-875-UNKNOWN",
        "attempt_id": "ATTEMPT-875-UNKNOWN",
        "retry_count": 1,
        "max_retries": 2,
        "created_at": attempted_at,
        "updated_at": attempted_at,
        "attempts": [{
            "run_id": "RUN-875-UNKNOWN",
            "attempt_id": "ATTEMPT-875-UNKNOWN",
            "executor_id": "synthetic-browser",
            "started_at": attempted_at,
            "finished_at": "",
            "result": "RUNNING",
        }],
        "lease": {},
    }
    storage.write_json(geo.QUEUE_PATH, {"tasks": [unknown]})
    storage.write_json(geo.RECEIPTS_PATH, {"receipts": []})
    before = geo._load_queue()["tasks"][0]
    result = geo.targeted_receipt_reconciliation(
        [task_id], apply=True, approved_by=geo.CONTROLLER,
    )
    assert result["applicable"] == 0 and result["mutated"] is False, result
    assert result["new_external_requests"] == 0
    assert result["new_evidence"] == 0
    assert result["rows"][0]["disposition"] == "prior_attempt_without_matching_receipt_hold"
    assert geo._load_queue()["tasks"][0] == before

    same_unknown = dict(kwargs)
    same_unknown["question_ids"] = ["GEO50-D22"]
    duplicate_unknown = geo.enqueue_plan(geo.create_plan(**same_unknown))
    assert duplicate_unknown["created"] == 0
    assert duplicate_unknown["reused_task_ids"] == [task_id]

    fresh_kwargs = dict(kwargs)
    fresh_kwargs["question_ids"] = ["GEO50-D23"]
    fresh = geo.enqueue_plan(geo.create_plan(**fresh_kwargs))
    assert fresh["created"] == 1
    claimed = geo.claim_next_task({
        "executor_id": "synthetic-browser",
        "provider": "deepseek_web",
        "real_external": True,
        "strict_provider": True,
        "fresh_only": True,
    })
    assert claimed["task"]["task_id"] == fresh["tasks"][0]["task_id"], claimed
    rows = {row["task_id"]: row for row in geo._load_queue()["tasks"]}
    assert rows[task_id] == before
    assert geo._load_receipts()["receipts"] == []

    # 4. Static browser contracts: loading/error cannot masquerade as business
    # zero and a transient connector read error preserves the last verified truth.
    owner_ui = (SOURCE / "web" / "r8_23_growth_os.js").read_text(encoding="utf-8")
    connector_ui = (SOURCE / "web" / "r8_10_workbench.js").read_text(encoding="utf-8")
    r7_ui = (SOURCE / "web" / "r7.js").read_text(encoding="utf-8")
    assert "/api/r8-13/seo-geo" in owner_ui
    assert "kz:r823:owner_seo_truth:v1" in owner_ui
    assert "读取中" in owner_ui and "latestSeo = readSeoTruthCache()" in owner_ui
    assert "继续显示最后真值" in connector_ui
    assert "status:'unknown',label:'连接状态读取失败'" in connector_ui
    assert 'id="r7-today-working">—</b>' in r7_ui
    assert 'id="r7-day-progress-text">读取中</strong>' in r7_ui

    print("PASS #875: complete formal GEO ledger remains 50 after recent-window aging")
    print("PASS #875: semantic GEO action idempotency prevents duplicate task creation")
    print("PASS #875: unmatched prior attempt stays isolated while a fresh legal task can run")
    print("PASS #875: browser loading/failure preserves truth and never renders a false zero")
finally:
    if previous is None:
        os.environ.pop("LOCALAPPDATA", None)
    else:
        os.environ["LOCALAPPDATA"] = previous
    shutil.rmtree(sandbox, ignore_errors=True)
