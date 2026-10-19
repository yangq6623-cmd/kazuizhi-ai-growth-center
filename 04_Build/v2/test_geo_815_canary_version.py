"""#815 version gate safety regression; no external AI questions or real state."""
import atexit
import os
from pathlib import Path
import shutil
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "05_V2.0.0_Source"))
TEMP = Path(tempfile.mkdtemp(prefix=".kz-815-version-", dir=ROOT))
atexit.register(shutil.rmtree, TEMP, True)
os.environ["LOCALAPPDATA"] = str(TEMP)
from integrations import geo_browser_agent as agent
from core import geo_validation as geo


def main():
    sessions = [
        {"platform": name, "state": "ready", "session_url": "https://example.org/test"}
        for name in agent.DOMESTIC_PLATFORMS
    ]
    identity = agent.register({
        "owner_confirmed": True, "agent_id": "kz-r8-28-version-test-815",
        "browser": "chrome", "sessions": sessions
    })
    token = identity["agent_token"]
    auth = {"agent_token": token, "platform": "doubao_web"}
    with patch.object(geo, "claim_next_task", return_value={"skipped": True, "reason": "queue_empty"}) as claim_task, \
         patch.object(geo, "enqueue_safe_browser_retest", return_value={"created": 0, "reason": "global_retest_cooldown"}) as retest, \
         patch.object(geo, "queue_single_fresh_doubao_canary_once", return_value={"created": 0, "reason": "no_untried_doubao_question"}) as canary:
        for version in ("2.2.2.808", "2.2.2.814", "2.2.2.828", "2.2.2.805"):
            agent.heartbeat({**auth, "version": version, "sessions": sessions})
            before = canary.call_count
            result = agent.claim(auth)
            assert result["claim"]["reason"] == "queue_empty", result
            assert claim_task.call_count >= 1
            assert retest.call_count >= 1
            reason = agent.status()["last_canary_reason"]
            if version in ("2.2.2.808", "2.2.2.814", "2.2.2.828"):
                assert canary.call_count == before + 1, (version, reason)
                assert reason == "no_untried_doubao_question", (version, reason)
            else:
                assert canary.call_count == before, "unverified old extension must not run canary"
                assert reason == "extension_version_not_supported", (version, reason)
        assert canary.call_count == 3
    print("PASS #815: Chrome 808, 814 and lease-aware 828 can enter one-shot canary eligibility; 805 fails closed; no tasks posted")


if __name__ == "__main__":
    main()
