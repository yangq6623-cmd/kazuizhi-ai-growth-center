"""R8-25 GEO: never convert capture failure into browser authorization blockage."""
from __future__ import annotations
import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "05_V2.0.0_Source"))
TEMP = Path(tempfile.mkdtemp(prefix=".kz-geo-block-safe-", dir=ROOT))
atexit.register(shutil.rmtree, TEMP, True)
os.environ["LOCALAPPDATA"] = str(TEMP)

from core import geo_domestic_matrix, geo_validation as geo  # noqa: E402
from integrations import geo_browser_agent as agent  # noqa: E402


def main():
    registered = agent.register({
        "owner_confirmed": True,
        "sessions": [
            {"platform": platform, "state": "ready", "session_url": "https://example.com/test"}
            for platform in agent.DOMESTIC_PLATFORMS
        ],
    })
    token = registered["agent_token"]
    geo.bootstrap_question_set(force=True)
    assert geo_domestic_matrix.prepare_missing(limit=50, mission_id="GEO-805-REGRESSION")["created"] == 50

    first = agent.claim({"agent_token": token, "platform": "doubao_web"})["claim"]["task"]
    failed = agent.block({
        "agent_token": token, "platform": "doubao_web",
        "task_id": first["task_id"], "kind": "execution_error",
        "reason": "capture_failed:question_not_submitted",
    })
    assert failed["task"]["state"] == "failed", "technical failure must be failed, not awaiting login"
    assert failed["block_category"] == "technical"
    assert failed["requires_manual_login"] is False
    assert next(row for row in failed["status"]["platforms"] if row["platform"] == "doubao_web")["ready"]
    assert geo.queue_summary()["authorization_required"] == 0
    assert geo.queue_summary()["failed"] == 1
    assert agent.heartbeat({"agent_token": token})["status"]["last_error"].startswith("capture_failed:"), (
        "successful heartbeat must not hide unresolved capture error"
    )

    second = agent.claim({"agent_token": token, "platform": "deepseek_web"})["claim"]["task"]
    evidence = agent.receipt({
        "agent_token": token, "task_id": second["task_id"],
        "platform": "deepseek_web", "session_url": "https://chat.deepseek.com/a",
        "raw_answer": "这是来自真实外部AI页面的完整测试回复内容",
    })
    assert evidence["official_truth"] is True
    assert agent.status()["last_error"] == "", "verified success clears last capture error"
    late = agent.block({
        "agent_token": token, "platform": "deepseek_web",
        "task_id": second["task_id"], "kind": "execution_error",
        "reason": "capture_failed:agent_response_timeout",
    })
    assert late["task"]["state"] == "succeeded", "late failure callback must not change successful Receipt"
    assert next(row for row in late["status"]["platforms"] if row["platform"] == "deepseek_web")["ready"]
    assert sum(item["task_id"] == second["task_id"] for item in geo.receipts(1000)) == 1

    third = agent.claim({"agent_token": token, "platform": "douyin_search_web"})["claim"]["task"]
    captcha = agent.block({
        "agent_token": token, "platform": "douyin_search_web",
        "task_id": third["task_id"], "kind": "captcha", "reason": "captcha_required",
    })
    assert captcha["task"]["state"] == "authorization_required"
    assert captcha["requires_manual_login"] is True
    assert next(row for row in captcha["status"]["platforms"] if row["platform"] == "douyin_search_web")["state"] == "captcha_required"

    # Historical #804 rows mislabeled as auth must only be classified for
    # review. Never bulk reset their retry count, old claims, or evidence.
    queue = geo._load_queue()
    legacy = next(item for item in queue["tasks"] if item["task_id"] == first["task_id"])
    legacy["state"] = "authorization_required"
    legacy["authorization_reason"] = "capture_failed:question_not_submitted"
    legacy_retry = legacy.get("retry_count")
    geo._save_queue(queue)
    summary = geo.queue_summary()
    assert summary["blockage_diagnostics"]["legacy_technical_requires_review"] == 1
    assert summary["blockage_diagnostics"]["real_authorization_or_risk_control"] == 1
    assert summary["blockage_diagnostics"]["auto_requeued"] == 0
    assert summary["queued"] == 47
    assert geo._find_task(first["task_id"])[1]["retry_count"] == legacy_retry
    manual = geo.manual_requirements()
    by_id = {item["task_id"]: item for item in manual["items"]}
    assert by_id[first["task_id"]]["action_type"] == "inspect_technical_failure_no_auto_retry"
    assert by_id[third["task_id"]]["action_type"] == "login_oauth_captcha_or_permission"
    print("PASS: 805 GEO technical/auth separated, no evidence downgrade, no auto-retry, legacy diagnostics honest")


if __name__ == "__main__":
    main()
