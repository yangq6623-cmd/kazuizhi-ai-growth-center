"""Release gate for account-scoped automatic publishing."""
from __future__ import annotations

import importlib
import os
import sys
import tempfile
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[2] / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))


with tempfile.TemporaryDirectory() as temporary:
    os.environ["LOCALAPPDATA"] = temporary
    from core import account_registry as registry
    from integrations import desktop_browser_session as browser
    from core import r8_growth_ops as growth

    importlib.reload(registry)
    importlib.reload(browser)
    importlib.reload(growth)

    account = registry.register_official_identity("douyin", "auto-publish-test", "auto-publish-subject", method="desktop_browser_qr")
    registry.set_auth_state(account["account_id"], "connected", method="desktop_browser_qr")
    registry.update_scope(account["account_id"], services=["家电维修"], regions=["涟水县"])
    state = browser._state()
    state["sessions"].append({"account_id": account["account_id"], "platform": "douyin", "status": "owner_confirmed"})
    browser._save(state)

    signal = growth.ingest_signal({
        "platform": "douyin", "source_id": "auto-policy-test", "summary": "用户询问冰箱上门维修",
        "region": "涟水县", "service_category": "家电维修", "intent_level": "high", "recommended_action": "reply",
    })["item"]
    growth.route_signal({"signal_id": signal["signal_id"]})
    case = growth.create_growth_case({"signal_id": signal["signal_id"]})["item"]
    content = growth.create_content_brief({"growth_id": case["growth_id"]})["item"]
    reviewed = growth.review_content({"content_id": content["content_id"], "action": "approve", "reviewer": "owner"})

    queued = reviewed["automatic_publish_job"]
    assert queued and queued["status"] == "queued"
    assert queued["account_id"] == account["account_id"]
    assert queued["authorization_mode"] == "automatic_policy_after_qc"
    assert queued["receipt"] is None
    assert growth.dashboard()["publication_policy"]["enabled"] is True
    assert growth.configure_publication_policy({"enabled": True})["policy"]["requires_real_receipt"] is True

    from integrations.manager import integration_status
    publishing = next(row for row in integration_status()["items"] if row["id"] == "publishing")
    assert publishing["status"] == "configured"
    assert publishing["status_label"] == "质检后自动入队"
    assert "PC 扫码授权" in publishing["message"]
    assert "Receipt" in publishing["message"]

print("PASS: approved content is auto-queued only for its authorized PC-browser account and never fakes a publication receipt")
