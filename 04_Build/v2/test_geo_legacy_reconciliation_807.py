"""Guard old GEO data without ever repeating an external platform question."""
from __future__ import annotations

import atexit
import copy
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "05_V2.0.0_Source"))
TEMP = Path(tempfile.mkdtemp(prefix=".kz-geo-legacy-807-", dir=ROOT))
atexit.register(shutil.rmtree, TEMP, True)
os.environ["LOCALAPPDATA"] = str(TEMP)

from core import geo_validation as geo  # noqa: E402
from core.storage import read_json  # noqa: E402


def task(tid, state, evidence="", reason="capture_failed:agent_response_timeout",
         provider="doubao_web", qid="GEO50-D01"):
    return {
        "task_id": tid, "state": state, "evidence_id": evidence,
        "authorization_reason": reason, "question_id": qid,
        "question_text": "涟水县哪里可以找水电维修师傅？",
        "provider": provider, "retry_count": 0, "max_retries": 2,
    }


def receipt(tid, eid, provider="doubao_web", qid="GEO50-D01", valid=True):
    return {
        "task_id": tid, "evidence_id": eid, "question_id": qid,
        "provider": provider,
        "session_url": "https://www.doubao.com/chat/real" if valid else "http://127.0.0.1:8876/",
        "tested_at": "2026-10-17T13:45:00+08:00",
        "raw_answer": "这是外部网页保存的完整历史回答，用于账本状态回归测试，不构成新增外部曝光。",
        "evidence_level": "C", "official_truth": False,
    }


def main():
    original = [
        task("T1", "authorization_required", "E1"),
        task("T2", "authorization_required", "E2"),
        task("T3", "authorization_required"),
        task("T4", "authorization_required", "E4"),
        task("T5", "authorization_required", "", "captcha_required"),
        task("T6", "authorization_required", "", "capture_failed:signal timed out"),
        task("T7", "succeeded", "E7", "", qid="GEO50-D22"),
        task("T8", "authorization_required", "", qid="GEO50-D22"),
        task("T9", "authorization_required", "E9"),
    ]
    original_receipts = [
        receipt("T1", "E1"),
        receipt("T4", "E4", provider="qwen_web"),  # provider mismatch
        receipt("T9", "E9", valid=False),  # localhost is NOT an external receipt
    ]
    geo._save_queue({"tasks": copy.deepcopy(original)})
    geo._save_receipts({"receipts": copy.deepcopy(original_receipts)})

    preview = geo.legacy_receipt_reconciliation()
    assert preview["blocked"] == 8
    assert preview["safe_receipt_matches"] == 1
    assert preview["ambiguous_or_missing_receipt"] == 6
    assert preview["technical_waiting_review"] == 7
    assert preview["reconciled"] == 0
    assert geo._load_queue()["tasks"] == original, "read-only preview must not mutate queue"
    try:
        geo.legacy_receipt_reconciliation(apply=True, approved_by="")
    except ValueError as err:
        assert "geo_reconcile_requires_chatgpt_approval" in str(err)
    else:
        raise AssertionError("unapproved apply accepted")

    result = geo.legacy_receipt_reconciliation(apply=True, approved_by="chatgpt")
    assert result["reconciled"] == 1
    assert result["new_evidence"] == 0 and result["automatic_external_retries"] == 0
    previous = read_json(result["backup_path"], {})
    assert previous["tasks"] == original, "backup must preserve complete pre-change ledger"
    rows = {x["task_id"]: x for x in geo._load_queue()["tasks"]}
    assert rows["T1"]["state"] == "succeeded"
    assert rows["T1"]["historical_authorization_reason"] == "capture_failed:agent_response_timeout"
    assert rows["T1"]["evidence_id"] == "E1"
    for tid in ["T2","T3","T4","T5","T6","T8","T9"]:
        assert rows[tid]["state"] == "authorization_required", tid
    assert geo._load_receipts()["receipts"] == original_receipts, "never mutate original receipts"
    assert any(x["event_type"] == "geo_legacy_receipt_state_reconciled" for x in geo.audit_events())
    again = geo.legacy_receipt_reconciliation(apply=True, approved_by="chatgpt")
    assert again["reconciled"] == 0 and again["backup_path"] == "", "second apply must be idempotent"

    report = geo.legacy_blockage_review()
    assert report["blocked"] == 7
    assert report["timeout_answer"] == 5
    assert report["timeout_signal"] == 1
    assert report["other"] == 1
    assert report["has_prior_evidence_id"] == 3
    assert report["duplicate_success_same_question_provider"] >= 1
    assert report["auto_retried"] == 0

    # A never-attempted Doubao question is selected once, rather than
    # replaying any of the old 99 ambiguous timeout tasks.
    from integrations import geo_browser_agent as agent
    sessions = [{"platform": platform, "state": "ready",
                 "session_url": "https://example.com/"} for platform in agent.DOMESTIC_PLATFORMS]
    reg = agent.register({
        "owner_confirmed": True, "agent_id": "kz-r8-28-genuine-sample",
        "browser": "chrome", "sessions": sessions,
    })
    token = reg["agent_token"]
    agent.heartbeat({"agent_token": token, "version": "2.2.2.808", "sessions": sessions})
    before_len = len(geo._load_queue()["tasks"])
    claimed = agent.claim({"agent_token": token, "platform": "doubao_web"})["claim"]["task"]
    assert claimed["expected_platform"] == "doubao_web"
    assert claimed["provider"] == "doubao_web"
    assert claimed["state"] == "running"
    prior_doubao = {
        t["question_id"] for t in original
        if t["provider"] in {"doubao_web", "doubao_search"}
    }
    assert claimed["question_id"] not in prior_doubao, "old prompt must never be replayed"
    assert len(geo._load_queue()["tasks"]) == before_len + 1
    again_claim = agent.claim({"agent_token": token, "platform": "doubao_web"})["claim"]
    assert again_claim.get("skipped") is True
    assert len(geo._load_queue()["tasks"]) == before_len + 1, "second canary forbidden"
    marker = geo.queue_single_fresh_doubao_canary_once()
    assert marker["reason"] == "already_reserved"
    # No fake successful Evidence was produced when this task was only claimed.
    assert geo._load_receipts()["receipts"] == original_receipts

    print("PASS 807: backup before reconciled Receipt, no fabricated Evidence, "
          "C-grade stays C, no mass retry, idempotent and foreign/local replies rejected")


if __name__ == "__main__":
    main()
