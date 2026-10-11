"""Release gate for the authenticated domestic GEO browser-agent bridge."""
from __future__ import annotations

import atexit
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))
TEST_ROOT = Path(tempfile.mkdtemp(prefix=".kz-geo-agent-", dir=ROOT))
atexit.register(shutil.rmtree, TEST_ROOT, True)
os.environ["LOCALAPPDATA"] = str(TEST_ROOT)

from core import geo_domestic_matrix, geo_validation  # noqa: E402
from integrations import geo_browser_agent, geo_browser_validation  # noqa: E402


def main():
    offline = geo_browser_agent.status()
    assert offline["connected"] is False
    assert offline["automatic_after_login"] is False

    registered = geo_browser_agent.register({
        "owner_confirmed": True,
        "agent_id": "test-domestic-agent",
        "browser": "chrome",
        "profile": "test-profile",
        "sessions": [
            {"platform": platform, "state": "ready", "session_url": "https://example.com/session"}
            for platform in geo_browser_agent.DOMESTIC_PLATFORMS
        ],
    })
    token = registered["agent_token"]
    online = geo_browser_agent.status()
    assert online["connected"] is True
    assert online["automatic_after_login"] is True
    assert online["all_domestic_platforms_ready"] is True
    assert geo_browser_validation.status()["automatic_after_login"] is True

    geo_validation.bootstrap_question_set(force=True)
    prepared = geo_domestic_matrix.prepare_missing(limit=50, mission_id="MISSION-R8-27")
    assert prepared["created"] == 50
    claimed = geo_browser_agent.claim({"agent_token": token, "platform": "doubao_web"})
    task = claimed["claim"]["task"]
    assert task["state"] == "running"
    assert task["expected_platform"] == "doubao_web"
    assert claimed["contract"]["domestic_formal_slot"] is True

    receipt = geo_browser_agent.receipt({
        "agent_token": token,
        "task_id": task["task_id"],
        "platform": "doubao_web",
        "session_url": "https://www.doubao.com/chat/test",
        "raw_answer": "真实外部网页完整原始回答",
    })
    assert receipt["official_truth"] is True
    assert receipt["evidence_level"] == "A"
    assert receipt["execution_origin"] == "authenticated_browser_agent"
    matrix = geo_domestic_matrix.snapshot(
        geo_validation.receipts(1000),
        geo_validation.question_set()["questions"],
        geo_validation.queue_summary()["tasks"],
    )
    assert matrix["automatic_completed"] == 1
    assert matrix["manual_completed"] == 0

    second = geo_browser_agent.claim({"agent_token": token, "platform": "douyin_search_web"})
    second_task = second["claim"]["task"]
    blocked = geo_browser_agent.block({
        "agent_token": token,
        "platform": "douyin_search_web",
        "task_id": second_task["task_id"],
        "kind": "captcha",
        "reason": "captcha_required",
    })
    assert blocked["task"]["state"] == "authorization_required"
    platform = next(x for x in blocked["status"]["platforms"] if x["platform"] == "douyin_search_web")
    assert platform["state"] == "captcha_required"

    disconnected = geo_browser_agent.disconnect({"agent_token": token})
    assert disconnected["status"]["connected"] is False
    assert geo_browser_validation.status()["automatic_after_login"] is False

    source = (SOURCE / "backend" / "r8_19_geo_validation_patch.py").read_text(encoding="utf-8")
    for route in ("status", "register", "heartbeat", "claim", "receipt", "block", "disconnect"):
        assert f"/api/r8-27/geo-browser-agent/{route}" in source
    ui = (SOURCE / "web" / "geo-growth-os.js").read_text(encoding="utf-8")
    assert "浏览器代理：未连接或心跳过期" in ui
    assert "/api/r8-27/geo-browser-agent/status" in ui
    print("PASS: authenticated domestic GEO browser-agent bridge and truthful heartbeat gate")


if __name__ == "__main__":
    main()
