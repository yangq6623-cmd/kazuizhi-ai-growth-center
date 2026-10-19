"""Regression gate for #827-compatible task lineage and safe external leases.

Synthetic temporary ledgers only. No network calls and no production mutation.
"""
import atexit
from copy import deepcopy
from datetime import datetime, timedelta, timezone
import os
from pathlib import Path
import shutil
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "05_V2.0.0_Source"))
TEMP = Path(tempfile.mkdtemp(prefix=".kz-r8-37-", dir=ROOT))
atexit.register(shutil.rmtree, TEMP, True)
os.environ["LOCALAPPDATA"] = str(TEMP)

from core import geo_growth_orchestrator as growth  # noqa: E402
from core import geo_validation as geo  # noqa: E402


QUESTION = {
    "question_id": "GEO50-C04",
    "question_text": "涟水本地维修平台如何选择？",
    "question_type": "commercial",
    "question_set_version": geo.QUESTION_SET_VERSION,
    "region": "涟水县",
    "service": "综合维修",
    "intent": "commercial_compare",
}


def enqueue(suffix="COMPAT"):
    result = geo.enqueue_plan({
        "plan_id": f"GEO-PLAN-{suffix}",
        "decision_id": "DECISION-COMPAT",
        "command_id": "COMMAND-COMPAT",
        "mission_id": "MISSION-COMPAT",
        "provider": "doubao_web",
        "expected_platform": "doubao_web",
        "test_method": "browser",
        "questions": [QUESTION],
        "max_retries": 2,
        "correlation": {
            "opportunity_id": "GEO-GROWTH-1F0329CF1616",
            "action_id": "GEO-GROWTH-1F0329CF1616",
            "content_revision_id": "REV-COMPAT",
            "publication_event_id": "PUBLICATION-COMPAT",
            "publication_receipt_id": "DEPLOY-COMPAT",
            "schedule_id": f"GEO-SCHEDULE-{suffix}",
        },
    })
    assert result["created"] == 1
    return result["tasks"][0]


def contract(executor="agent-compat"):
    return {
        "real_external": True,
        "authorization_ready": True,
        "provider_ready": True,
        "provider": "doubao_web",
        "test_method": "browser",
        "executor_id": executor,
        "strict_provider": True,
        "fresh_only": True,
    }


def main():
    r7_ui = (ROOT / "05_V2.0.0_Source" / "web" / "r7.js").read_text(encoding="utf-8")
    assert "feedback.classList.contains('error')" in r7_ui
    assert r"/读取\/api\/r7\/[^\s]*超时/" in r7_ui
    assert "feedback.hidden=true" in r7_ui

    schedule_item = {
        "id": "GEO-GROWTH-1F0329CF1616",
        "content_revision_id": "REV-COMPAT",
        "publication_receipt_id": "DEPLOY-COMPAT",
        "published_at": "2026-10-18T17:04:07+08:00",
    }
    first_schedule = growth._ensure_retest_schedule(schedule_item)
    second_schedule = growth._ensure_retest_schedule(schedule_item)
    assert [row["schedule_id"] for row in first_schedule] == [row["schedule_id"] for row in second_schedule]
    assert len({row["schedule_id"] for row in first_schedule}) == 3
    revised_item = deepcopy(schedule_item)
    revised_item.update(content_revision_id="REV-COMPAT-2", publication_receipt_id="DEPLOY-COMPAT-2",
                        publication_event_id="PUBLICATION-COMPAT-2")
    revised_schedule = growth._ensure_retest_schedule(revised_item)
    assert [row["schedule_id"] for row in revised_schedule] != [row["schedule_id"] for row in first_schedule]
    assert len(revised_item["retest_schedule_history"]) == 1
    assert revised_item["retest_schedule_history"][0]["schedule"] == first_schedule

    task = enqueue()
    assert task["normalized_state"] == "READY"
    assert task["correlation"]["schedule_id"] == "GEO-SCHEDULE-COMPAT"
    assert task["idempotency_key"]

    duplicate = geo.enqueue_plan({
        "plan_id": "GEO-PLAN-COMPAT-DUPLICATE-CALL",
        "decision_id": "DECISION-COMPAT",
        "command_id": "COMMAND-COMPAT",
        "mission_id": "MISSION-COMPAT",
        "provider": "doubao_web",
        "expected_platform": "doubao_web",
        "test_method": "browser",
        "questions": [QUESTION],
        "max_retries": 2,
        "correlation": {
            "opportunity_id": "GEO-GROWTH-1F0329CF1616",
            "action_id": "GEO-GROWTH-1F0329CF1616",
            "content_revision_id": "REV-COMPAT",
            "publication_event_id": "PUBLICATION-COMPAT",
            "publication_receipt_id": "DEPLOY-COMPAT",
            "schedule_id": "GEO-SCHEDULE-COMPAT",
        },
    })
    assert duplicate["created"] == 0 and duplicate["idempotent"] is True
    assert duplicate["reused_task_ids"] == [task["task_id"]]

    claimed = geo.claim_next_task(contract())["task"]
    assert claimed["state"] == "running" and claimed["normalized_state"] == "RUNNING"
    assert claimed["attempt_id"].startswith("GEO-ATTEMPT-")
    assert claimed["lease"]["owner"] == "agent-compat"
    assert len(claimed["attempts"]) == 1
    assert geo.claim_next_task(contract()).get("skipped") is True, "same task was double-claimed"

    renewed = geo.renew_task_lease(
        claimed["task_id"], "agent-compat", claimed["run_id"], claimed["attempt_id"])
    assert renewed["renewed"] is True
    wrong = geo.renew_task_lease(
        claimed["task_id"], "other-agent", claimed["run_id"], claimed["attempt_id"])
    assert wrong == {"renewed": False, "reason": "wrong_executor"}

    receipt = geo.record_result({
        "task_id": claimed["task_id"],
        "run_id": claimed["run_id"],
        "attempt_id": claimed["attempt_id"],
        "provider": "doubao_web",
        "test_method": "browser",
        "session_url": "https://www.doubao.com/chat/synthetic-compat",
        "raw_answer": "这是隔离测试生成的完整外部回答样本，仅用于验证任务关联和回执幂等逻辑。",
        "tested_at": datetime.now(timezone.utc).isoformat(),
    })
    saved = geo._find_task(claimed["task_id"])[1]
    assert saved["state"] == "succeeded" and saved["lease"] == {}
    assert saved["attempts"][-1]["receipt_id"] == receipt["receipt_id"]
    assert receipt["correlation"]["publication_event_id"] == "PUBLICATION-COMPAT"

    # A second synthetic task loses its lease without a Receipt. It must be
    # quarantined as uncertain and must never be silently requeued/replayed.
    second = enqueue("EXPIRE")
    second_claim = geo.claim_next_task(contract("agent-expire"))["task"]
    queue = geo._load_queue()
    expiring = next(row for row in queue["tasks"] if row["task_id"] == second_claim["task_id"])
    expiring["lease"]["expires_at"] = (
        datetime.now(timezone.utc) - timedelta(seconds=1)
    ).isoformat()
    geo._save_queue(queue)
    after_expiry = geo.claim_next_task(contract("agent-new"))
    assert after_expiry.get("skipped") is True
    quarantined = geo._find_task(second_claim["task_id"])[1]
    assert quarantined["state"] == "authorization_required"
    assert quarantined["normalized_state"] == "UNCERTAIN"
    assert quarantined["replay_blocked"] is True
    try:
        geo.retry_task(quarantined["task_id"], approved_by="chatgpt")
        raise AssertionError("uncertain external task was allowed to retry")
    except ValueError as error:
        assert "must_be_reconciled_not_retried" in str(error)

    # Preserve the exact historical safety classes called out by the field
    # ledger: 73 timeouts and 81 uncertain sends remain immutable and cannot
    # re-enter the automatic claim path.
    queue = geo._load_queue()
    for index in range(73):
        queue["tasks"].append({
            "task_id": f"HIST-TIMEOUT-{index:03d}", "state": "authorization_required",
            "authorization_reason": "legacy_timeout_requires_manual_receipt_review",
            "provider": "doubao_web", "expected_platform": "doubao_web",
            "test_method": "browser", "replay_blocked": True,
        })
    for index in range(81):
        queue["tasks"].append({
            "task_id": f"HIST-UNCERTAIN-{index:03d}", "state": "failed",
            "failure_reason": "historical_send_result_unknown",
            "provider": "doubao_web", "expected_platform": "doubao_web",
            "test_method": "browser", "uncertain_external_submission": True,
            "replay_blocked": True,
        })
    geo._save_queue(queue)
    protected_before = {
        row["task_id"]: deepcopy(row) for row in geo._load_queue()["tasks"]
        if str(row.get("task_id") or "").startswith("HIST-")
    }
    assert len(protected_before) == 154
    assert geo.claim_next_task(contract("agent-history-guard")).get("skipped") is True
    protected_after = {
        row["task_id"]: row for row in geo._load_queue()["tasks"]
        if str(row.get("task_id") or "").startswith("HIST-")
    }
    assert protected_after == protected_before

    print("PASS #827 compatibility hardening: additive lineage, task lease, exact-attempt Receipt, "
          "double-claim prevention, uncertain-result quarantine and 73+81 historical no-replay protection")


if __name__ == "__main__":
    main()
