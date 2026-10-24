"""#874 first-breakpoint regression.

Synthetic temporary ledgers only: no browser action, external AI request,
publication, search submission, production mutation, credential or paid API.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import threading
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))
sandbox = Path(tempfile.mkdtemp(prefix="kazuizhi-874-first-breakpoint-"))
previous = os.environ.get("LOCALAPPDATA")
os.environ["LOCALAPPDATA"] = str(sandbox)


def iso(delta_seconds: int) -> str:
    return (datetime.now(timezone.utc) + timedelta(seconds=delta_seconds)).isoformat()


def browser_task(task_id: str, *, expires: int, suffix: str) -> dict:
    started = iso(-700)
    return {
        "task_id": task_id,
        "question_id": f"GEO50-D{suffix}",
        "question_text": "隔离环境中的安全复测问题",
        "state": "running",
        "provider": "deepseek_web",
        "expected_platform": "deepseek_web",
        "test_method": "browser",
        "run_id": f"RUN-{suffix}",
        "attempt_id": f"ATTEMPT-{suffix}",
        "executor_id": "synthetic-browser",
        "started_at": started,
        "updated_at": started,
        "retry_count": 0,
        "max_retries": 2,
        "lease": {
            "owner": "synthetic-browser",
            "acquired_at": started,
            "heartbeat_at": iso(-5 if expires > 0 else -400),
            "expires_at": iso(expires),
        },
        "attempts": [{
            "run_id": f"RUN-{suffix}", "attempt_id": f"ATTEMPT-{suffix}",
            "executor_id": "synthetic-browser", "started_at": started,
            "finished_at": "", "result": "RUNNING",
        }],
    }


try:
    from core import storage
    from core import r7_engine
    from core import geo_domestic_matrix
    from core import geo_growth_orchestrator
    from core import geo_validation as geo
    from backend import r8_14_seo_geo_autonomy_patch as recovery

    # R7 owner reads must not join a process-wide writer lock.
    jobs = [{
        "id": f"J-{index}", "title": f"synthetic-{index}",
        "state": "completed" if index < 1000 else "queued", "mode": "local",
    } for index in range(1200)]
    storage.write_json(r7_engine.JOBS, {"schema": 1, "items": jobs})
    storage.write_json(r7_engine.MIGRATION, {"result": "complete", "copied": []})
    storage.write_json("r7/human_interventions.json", {"items": []})
    storage.write_json("r7/learning.json", {"items": [], "policy_version": 1})
    result = {}
    finished = threading.Event()

    def read_r7() -> None:
        try:
            result["snapshot"] = r7_engine.ui_snapshot()
        except Exception as error:
            result["error"] = repr(error)
        finally:
            finished.set()

    with storage._JSON_IO_LOCK:
        worker = threading.Thread(target=read_r7, daemon=True)
        worker.start()
        assert finished.wait(1.5), "R7 owner snapshot waited for the global JSON writer lock"
    assert "error" not in result, result
    assert result["snapshot"]["jobs"]["ledger_count"] == 1200
    assert result["snapshot"]["snapshot_state"] == "fresh"

    # Corrupt snapshot reads keep the last truth instead of showing zeros.
    (storage.data_root() / r7_engine.JOBS).write_text("{broken", encoding="utf-8")
    cached = r7_engine.ui_snapshot()
    assert cached["snapshot_state"] == "cached"
    assert cached["jobs"]["ledger_count"] == 1200
    assert cached["snapshot_error"]

    # Full GEO50 truth cannot be truncated by 1000 newer auxiliary receipts.
    questions = geo._fixed_questions()
    allocation = geo_domestic_matrix.assignments(questions)
    qmap = {row["question_id"]: row for row in questions}
    formal = []
    for platform, ids in allocation.items():
        for qid in ids:
            formal.append({
                "evidence_id": f"E-{qid}", "receipt_id": f"E-{qid}",
                "question_id": qid, "question_text": qmap[qid]["question_text"],
                "raw_answer": "隔离环境中的完整外部回答结构，不代表真实生产结果。",
                "provider": platform, "model": "synthetic-browser",
                "tested_at": "2026-10-01T10:00:00+08:00",
                "session_url": f"https://example.invalid/session/{qid}",
                "official_truth": True, "evidence_level": "A",
            })
    auxiliary = [{
        "evidence_id": f"C-{index}", "question_id": f"AUX-{index}",
        "question_text": "辅助信号", "raw_answer": "隔离辅助回答",
        "provider": "cloud_auto", "model": "synthetic-api",
        "tested_at": "2026-10-24T10:00:00+08:00",
        "response_id": f"R-{index}", "official_truth": False,
        "evidence_level": "C",
    } for index in range(1000)]
    storage.write_json(geo.RECEIPTS_PATH, {"receipts": formal + auxiliary})
    storage.write_json(geo_growth_orchestrator.STORE, dict(geo_growth_orchestrator.DEFAULT))
    fast = geo_growth_orchestrator.fast_status()
    assert fast["formal_ab_completed"] == 50, fast["formal_ab_completed"]
    assert fast["formal_ab_target"] == 50

    # A live nested browser lease must remain running. An expired browser
    # attempt without a Receipt is quarantined, never reset to queued.
    live = browser_task("GEO-TASK-874-LIVE", expires=600, suffix="01")
    unknown = browser_task("GEO-TASK-874-UNKNOWN", expires=-60, suffix="02")
    exact = browser_task("GEO-TASK-874-EXACT", expires=-60, suffix="03")
    cloud = {
        "task_id": "GEO-TASK-874-CLOUD", "question_id": "GEO50-D04",
        "state": "running", "provider": recovery.CLOUD_PROVIDER,
        "test_method": "api", "started_at": iso(-700), "updated_at": iso(-700),
        "retry_count": 0, "max_retries": 3,
    }
    storage.write_json(geo.QUEUE_PATH, {"tasks": [live, unknown, exact, cloud]})
    exact_receipt = {
        "task_id": exact["task_id"], "question_id": exact["question_id"],
        "provider": exact["provider"], "run_id": exact["run_id"],
        "attempt_id": exact["attempt_id"], "evidence_id": "E-EXACT",
        "receipt_id": "E-EXACT", "tested_at": iso(-50),
        "session_url": "https://chat.deepseek.com/a/synthetic",
        "raw_answer": "隔离账本中已经存在的完整回答，仅用于验证本地精准关联。",
        "evidence_level": "A", "official_truth": True,
    }
    storage.write_json(geo.RECEIPTS_PATH, {"receipts": [exact_receipt]})
    recovery._recover_stale_running_tasks()
    rows = {row["task_id"]: row for row in geo._load_queue()["tasks"]}
    assert rows[live["task_id"]]["state"] == "running"
    assert rows[unknown["task_id"]]["state"] == "authorization_required"
    assert rows[unknown["task_id"]]["authorization_reason"] == "task_lease_expired_external_result_unknown"
    assert rows[unknown["task_id"]]["uncertain_external_submission"] is True
    assert rows[unknown["task_id"]]["retry_count"] == 0
    assert rows[unknown["task_id"]]["run_id"] == unknown["run_id"]
    assert rows[exact["task_id"]]["state"] == "succeeded"
    assert rows[exact["task_id"]]["evidence_id"] == "E-EXACT"
    assert rows[cloud["task_id"]]["state"] == "queued"
    assert rows[cloud["task_id"]]["retry_count"] == 1

    ui = (SOURCE / "web" / "r7.js").read_text(encoding="utf-8")
    assert "r7LastSnapshot" in ui
    assert "继续显示" in ui and "最后成功快照" in ui

    print("PASS #874: R7 snapshot bypasses writer lock and preserves labeled last truth")
    print("PASS #874: GEO50 uses full Receipt ledger; old formal evidence is not truncated")
    print("PASS #874: live browser lease stays live; expired unknown result is quarantined, not replayed")
finally:
    if previous is None:
        os.environ.pop("LOCALAPPDATA", None)
    else:
        os.environ["LOCALAPPDATA"] = previous
    shutil.rmtree(sandbox, ignore_errors=True)
