"""#812 isolated end-to-end safety: claim -> browser Receipt -> deduplicate -> recover.

Only synthetic data in temporary LOCALAPPDATA. No external AI questions sent.
Run: python 04_Build/v2/test_geo_812_claim_execute_receipt.py
"""
import atexit
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import shutil
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "05_V2.0.0_Source"))
TEMP = Path(tempfile.mkdtemp(prefix=".kz-geo-812-", dir=ROOT))
atexit.register(shutil.rmtree, TEMP, True)
os.environ["LOCALAPPDATA"] = str(TEMP)

from core import geo_validation as geo, geo_domestic_matrix as domestic
from integrations import geo_browser_agent as agent

OLD = (datetime.now(timezone.utc) - timedelta(days=3)).isoformat()


def make_receipts():
    questions = geo.question_set()["questions"]
    allocation = domestic.assignments(questions)
    by_id = {q["question_id"]: q for q in questions}
    rows = []
    for platform, ids in allocation.items():
        for qid in ids:
            q = by_id[qid]
            rows.append({
                "task_id": "FORMAL-" + qid,
                "run_id": "BASELINE-RUN-" + qid,
                "evidence_id": "BASELINE-RECEIPT-" + qid,
                "receipt_id": "BASELINE-RECEIPT-" + qid,
                "question_id": qid,
                "question_text": q["question_text"],
                "provider": platform, "model": platform,
                "tested_at": OLD,
                "raw_answer": "合成测试样本：该问题曾在独立网页上获得完整回答。",
                "session_url": "https://example.com/synthetic/",
                "evidence_level": "A", "official_truth": True,
                "test_method": "browser",
            })
    assert len(rows) == 50
    return rows


def main():
    geo.bootstrap_question_set(force=True)
    geo._save_receipts({"receipts": make_receipts()})
    before = [
        {"task_id": "AMBIGUOUS-DOUBAO-D01", "question_id": "GEO50-D01",
         "provider": "doubao_web", "expected_platform": "doubao_web",
         "test_method": "browser", "state": "authorization_required",
         "run_id": "UNKNOWN-EXTERNAL-ATTEMPT", "authorization_reason": "legacy_timeout"},
        {"task_id": "CLOUD-ONLY", "question_id": "GEO50-D11",
         "provider": "cloud_auto", "expected_platform": "", "test_method": "api",
         "state": "queued", "run_id": "", "started_at": "", "retry_count": 0},
    ]
    geo._save_queue({"tasks": before.copy()})
    sessions = [{"platform": p, "state": "ready", "session_url": "https://example.com/session"}
                for p in agent.DOMESTIC_PLATFORMS]
    identity = agent.register({
        "owner_confirmed": True, "agent_id": "kz-r8-28-test-812",
        "sessions": sessions, "browser": "chrome",
    })
    token = identity["agent_token"]
    auth = {"agent_token": token}
    agent.heartbeat({**auth, "sessions": sessions, "version": "2.2.2.808"})

    claim = agent.claim({**auth, "platform": "doubao_web"})
    task = claim["claim"].get("task") or {}
    assert task.get("state") == "running", claim
    assert task["question_id"] in domestic.assignments(geo.question_set()["questions"])["doubao_web"]
    assert task["question_id"] != "GEO50-D01", "ambiguous old answer was resent"
    assert task.get("retest_origin") == "automatic_24h", task
    assert task.get("max_retries") == 0, task
    assert agent.status()["last_retest_reason"] == "safe_retest_queued"
    current = geo._load_queue()["tasks"]
    assert current[0] == before[0] and current[1] == before[1], "legacy queue modified"
    assert len(current) == 3

    # A platform's daily retest blocks only that platform. Concurrent polls
    # on another platform may reserve exactly one independent safe retest.
    with ThreadPoolExecutor(max_workers=5) as pool:
        outcomes = list(pool.map(
            lambda _: agent.claim({**auth, "platform": "deepseek_web"}), range(5)))
    assert sum(bool(x["claim"].get("task")) for x in outcomes) == 1, outcomes
    assert len(geo._load_queue()["tasks"]) == 4
    assert agent.status()["last_retest_reason"] in {
        "safe_retest_queued", "platform_retest_cooldown"
    }

    blocked = geo.enqueue_safe_browser_retest("doubao_web")
    assert blocked["reason"] == "platform_retest_cooldown", blocked
    assert blocked["blocking_task_id"] == task["task_id"], blocked
    assert blocked["next_eligible_at"], blocked
    assert 0 <= blocked["remaining_seconds"] <= 86400, blocked

    receipt_args = {
        **auth, "task_id": task["task_id"], "platform": "doubao_web",
        "session_url": "https://www.doubao.com/chat/synthetic-812",
        "raw_answer": "合成测试回答，长度足够验证真实回执的状态转换和去重处理。",
        "tested_at": datetime.now(timezone.utc).isoformat(),
    }
    first = agent.receipt(receipt_args)
    second = agent.receipt(receipt_args)
    assert first["evidence_id"] == second["evidence_id"]
    assert second["already_recorded"] is True
    assert len(geo._load_receipts()["receipts"]) == 51
    after = next(x for x in geo._load_queue()["tasks"] if x["task_id"] == task["task_id"])
    assert after["state"] == "succeeded"
    ignored = agent.block({**auth, "task_id": task["task_id"], "platform": "doubao_web",
                           "kind": "timeout", "reason": "late_capture_timeout"})
    assert ignored["ignored_stale"] is True
    assert geo._find_task(task["task_id"])[1]["state"] == "succeeded"

    # Simulate crash AFTER Evidence ledger commits but BEFORE queue status
    # succeeds. Reposting the same Receipt reconciles without duplicating it.
    q = geo.question_set()["questions"][31]
    broken = {
        "task_id": "CRASH-PARTIAL-812", "question_id": q["question_id"],
        "question_text": q["question_text"], "question_type": q["question_type"],
        "question_set_version": q["question_set_version"],
        "provider": "qwen_web", "expected_platform": "qwen_web",
        "test_method": "browser", "state": "running", "run_id": "CRASH-RUN",
        "executor_id": "kz-r8-28-test-812", "retry_count": 0,
    }
    qdata = geo._load_queue()
    qdata["tasks"].append(broken)
    geo._save_queue(qdata)
    payload = {
        **auth, "task_id": "CRASH-PARTIAL-812", "platform": "qwen_web",
        "session_url": "https://www.qianwen.com/synthetic-812",
        "raw_answer": "合成测试：模拟回执账本已写而队列还没更新的真实宕机情况。",
    }
    prior = geo._save_queue
    def broken_save(value):
        if any(t.get("task_id") == "CRASH-PARTIAL-812" and t.get("state") == "succeeded"
               for t in value.get("tasks", [])):
            raise OSError("synthetic_queue_write_interruption")
        return prior(value)
    with patch.object(geo, "_save_queue", side_effect=broken_save):
        try:
            agent.receipt(payload)
        except OSError as error:
            assert "synthetic_queue_write_interruption" in str(error)
        else:
            raise AssertionError("synthetic crash did not occur")
    assert len(geo._load_receipts()["receipts"]) == 52
    restored = agent.receipt(payload)
    assert restored["already_recorded"]
    assert len(geo._load_receipts()["receipts"]) == 52
    assert geo._find_task("CRASH-PARTIAL-812")[1]["state"] == "succeeded"
    assert domestic.snapshot(geo._load_receipts()["receipts"],
                             geo.question_set()["questions"])["completed"] == 50
    print("PASS #812: safe 24h real-browser retest, concurrent claim, idempotent Receipt, "
          "crash recovery, late-timeout fencing, no old replay, baseline 50/50 intact")


if __name__ == "__main__":
    main()
