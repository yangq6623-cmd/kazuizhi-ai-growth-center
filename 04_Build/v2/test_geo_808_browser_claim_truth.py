"""#808 GEO safe browser claim: preserve scoped unattempted jobs, never replay ambiguous attempts."""
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
TEMP = Path(tempfile.mkdtemp(prefix=".kz-geo-808-", dir=ROOT))
atexit.register(shutil.rmtree, TEMP, True)
os.environ["LOCALAPPDATA"] = str(TEMP)

from core import geo_validation as geo  # noqa: E402
from integrations import geo_browser_agent as agent  # noqa: E402

def make(tid, provider, expected, *, state="queued", retry_count=0, run_id="", started_at="", question_id="GEO50-D01"):
    return {
        "task_id": tid, "question_id": question_id,
        "question_text": "涟水县哪里可以找到正规维修师傅？",
        "provider": provider, "expected_platform": expected,
        "test_method": "browser", "state": state,
        "retry_count": retry_count, "max_retries": 2,
        "run_id": run_id, "started_at": started_at, "authorization_reason": "",
    }

def main():
    geo.bootstrap_question_set(force=True)
    original = [
        make("OLD-UNKNOWN", "browser_external_ai", ""),              # no destination
        make("OLD-CLOUD", "cloud_auto", "doubao_web"),                # wrong executor
        make("OLD-RETRY", "browser_external_ai", "doubao_web", retry_count=21),
        make("OLD-SENT", "doubao_web", "doubao_web", run_id="GEO-RUN-ALREADY"),
        make("OTHER-PLATFORM", "browser_external_ai", "qwen_web"),
        make("OTHER-RUNNING", "cloud_auto", "qwen_web", state="running"),
        make("NEW-DOUBAO", "browser_external_ai", "doubao_web", question_id="GEO50-D04"),
    ]
    geo._save_queue({"tasks": copy.deepcopy(original)})
    geo._save_receipts({"receipts": []})

    sessions = [{"platform": p, "state": "ready", "session_url": "https://example.com/"}
                for p in agent.DOMESTIC_PLATFORMS]
    reg = agent.register({
        "owner_confirmed": True, "agent_id": "kz-r8-28-live-test-808",
        "browser": "chrome", "sessions": sessions,
    })
    token = reg["agent_token"]
    agent.heartbeat({"agent_token": token, "version": "2.2.2.808", "sessions": sessions})
    first = agent.claim({"agent_token": token, "platform": "doubao_web"})
    claimed = first["claim"]["task"]
    assert claimed["question_id"] == "GEO50-D02", "one fresh canary must precede unrelated pending work"
    assert claimed["state"] == "running"
    assert claimed["provider"] == "doubao_web"
    assert claimed["task_id"] != "NEW-DOUBAO"
    assert agent.status()["last_canary_reason"] == "queued"
    assert agent.status()["last_claim_task_id"] == claimed["task_id"]
    assert agent.status()["extension_version"] == "2.2.2.808"

    after = {t["task_id"]: t for t in geo._load_queue()["tasks"]}
    for t in original:
        assert after[t["task_id"]] == t, "existing task changed: " + t["task_id"]
    assert len(after) == len(original) + 1
    assert geo._load_receipts()["receipts"] == []
    audit = geo.audit_events()
    assert sum(x["event_type"] == "geo_807_single_fresh_doubao_canary_queued" for x in audit) == 1

    # Another claim may take an independently unattempted and explicitly
    # addressed ordinary task, but must NEVER run the old ambiguous tasks.
    second = agent.claim({"agent_token": token, "platform": "doubao_web"})
    assert second["claim"]["task"]["task_id"] == "NEW-DOUBAO"
    third = agent.claim({"agent_token": token, "platform": "doubao_web"})
    assert third["claim"].get("skipped") is True
    assert agent.status()["last_claim_reason"] == "queue_empty"
    assert agent.status()["last_canary_reason"] == "already_reserved"
    assert len(geo._load_queue()["tasks"]) == len(original) + 1
    assert geo._load_receipts()["receipts"] == []

    # A technical failure should be observable, but must not invalidate login
    # or send the task again. The browser call only affects this claimed task.
    blocked = agent.block({
        "agent_token": token, "platform": "doubao_web",
        "task_id": claimed["task_id"], "kind": "timeout",
        "reason": "capture_failed:agent_response_timeout",
    })
    assert blocked["block_category"] == "technical"
    assert blocked["task"]["state"] == "failed"
    assert agent.status()["last_error"] == "capture_failed:agent_response_timeout"
    assert any(x["platform"] == "doubao_web" and x["ready"] for x in agent.status()["platforms"])
    again = agent.claim({"agent_token": token, "platform": "doubao_web"})
    assert again["claim"].get("skipped") is True
    assert geo._load_receipts()["receipts"] == []
    assert len(geo._load_queue()["tasks"]) == len(original) + 1

    # A normal older R8-27 browser-agent without 808 heartbeat still claims a
    # first-attempt assigned task; generic unaddressed work is not misrouted.
    old = agent.register({
        "owner_confirmed": True, "agent_id": "test-original-agent",
        "browser": "chrome", "sessions": sessions,
    })
    old_token = old["agent_token"]
    candidate = agent.claim({"agent_token": old_token, "platform": "qwen_web"})
    assert candidate["claim"]["task"]["task_id"] == "OTHER-PLATFORM"
    assert agent.status()["last_canary_reason"] == "already_reserved", "other platform must not erase Doubao canary audit"
    print("PASS 808: one prioritized Doubao canary; no old prompt replay, "
          "strict platform claims, legible status, real Receipt unchanged")

if __name__ == "__main__":
    main()
