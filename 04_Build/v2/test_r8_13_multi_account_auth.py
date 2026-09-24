from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))

os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="kz-r813-auth-")

from core.storage import read_json, write_json  # noqa: E402
from integrations.account_environment import (  # noqa: E402
    clear_risk,
    get_profile,
    mark_risk,
    observe,
    routing_allowed,
)
from integrations.account_router import route_account  # noqa: E402
from integrations.official_account_assets import upsert_official_account  # noqa: E402
from integrations.oauth_token_broker import _validate_request  # noqa: E402
from integrations.platform_auth_catalog import catalog, start_authorization  # noqa: E402


def main():
    data = catalog()
    providers = {x["platform"]: x for x in data["providers"]}
    required = {
        "google_search_console", "bing_webmaster", "baidu_search_resource",
        "douyin", "kuaishou", "xiaohongshu", "wechat_channels",
    }
    assert required.issubset(providers), sorted(required - set(providers))

    policy = data["environment_policy"]
    assert policy["stable_environment_per_account"] is True
    assert policy["proxy_rotation"] is False
    assert policy["fingerprint_spoofing"] is False
    assert policy["credential_capture"] is False
    assert policy["captcha_bypass"] is False
    assert policy["sms_interception"] is False
    assert policy["max_parallel_authorizations_per_account"] == 1
    assert policy["max_parallel_mutating_jobs_per_account"] == 1

    # Baidu is an official portal/site-token flow, not fabricated generic OAuth.
    baidu = start_authorization("baidu_search_resource", slot_label="百度账号1")
    assert baidu["ok"] is True
    assert baidu["requires_manual_completion"] is True
    assert baidu["authorization_url"].startswith("https://ziyuan.baidu.com/")
    assert baidu["slot_id"]

    # Missing official client credentials must never fabricate a successful OAuth URL.
    for key in ("KZ_GOOGLE_SEARCH_CLIENT_ID", "KZ_GOOGLE_SEARCH_CLIENT_SECRET"):
        os.environ.pop(key, None)
    google_missing = start_authorization(
        "google_search_console", slot_label="Google账号1",
        redirect_uri="http://127.0.0.1:8876/api/r8-12/oauth/callback/google_search_console",
    )
    assert google_missing["ok"] is False
    assert google_missing["needs_app_credentials"] is True

    os.environ["KZ_GOOGLE_SEARCH_CLIENT_ID"] = "test-client"
    os.environ["KZ_GOOGLE_SEARCH_CLIENT_SECRET"] = "test-secret"
    google = start_authorization(
        "google_search_console", slot_label="Google账号2",
        redirect_uri="http://127.0.0.1:8876/api/r8-12/oauth/callback/google_search_console",
    )
    google2 = start_authorization(
        "google_search_console", slot_label="Google账号3",
        redirect_uri="http://127.0.0.1:8876/api/r8-12/oauth/callback/google_search_console",
    )
    assert google["ok"] is True
    assert google2["ok"] is True
    assert google["slot_id"] != google2["slot_id"]
    assert google["authorization_url"].startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "prompt=select_account+consent" in google["authorization_url"]

    os.environ["KZ_DOUYIN_CLIENT_KEY"] = "test-key"
    os.environ["KZ_DOUYIN_CLIENT_SECRET"] = "test-secret"
    douyin = start_authorization(
        "douyin", slot_label="抖音账号2",
        redirect_uri="http://127.0.0.1:8876/api/r8-12/oauth/callback/douyin",
    )
    assert douyin["ok"] is False
    assert douyin["needs_https_callback"] is True

    # Durable identity: reauthorizing the same slot/account preserves account_id.
    first = upsert_official_account(
        platform="google_search_console", slot_id=google["slot_id"], slot_label="Google账号2",
        scopes=["https://www.googleapis.com/auth/webmasters"], platform_subject_id="subject-A",
    )
    second = upsert_official_account(
        platform="google_search_console", slot_id=google["slot_id"], slot_label="Google账号2-重授权",
        scopes=["https://www.googleapis.com/auth/webmasters"], platform_subject_id="subject-A",
        account_id=first["account_id"],
    )
    assert first["account_id"] == second["account_id"]
    assert first["created"] is True and second["created"] is False

    # Environment continuity: no raw IP, no evasion, risk pauses require explicit human clear.
    account_id = first["account_id"]
    initial = get_profile(account_id)
    assert initial["policy"]["proxy_rotation"] is False
    assert initial["policy"]["fingerprint_spoofing"] is False
    assert initial["policy"]["auto_failover_on_risk"] is False
    stable = observe(account_id, network_profile_label="home-network", device_id="DEV-TEST")
    assert stable["risk_level"] == "low"
    changed = observe(account_id, network_profile_label="office-network", device_id="DEV-TEST")
    assert changed["risk_level"] == "medium"
    risky = mark_risk(account_id, "platform_security_prompt", level="high")
    assert risky["risk_level"] == "high"
    assert routing_allowed(account_id)["allowed"] is False
    try:
        clear_risk(account_id, owner_confirmed=False)
        raise AssertionError("risk clear must require owner confirmation")
    except ValueError:
        pass
    cleared = clear_risk(account_id, owner_confirmed=True)
    assert cleared["risk_level"] == "low"

    # Explicitly bound task must pause on risk; it must not fail over to another account.
    third = upsert_official_account(
        platform="google_search_console", slot_id=google2["slot_id"], slot_label="Google账号3",
        scopes=["https://www.googleapis.com/auth/webmasters"], platform_subject_id="subject-B",
    )
    observe(third["account_id"], network_profile_label="home-network")
    mark_risk(account_id, "security_verification", level="high")
    routed = route_account(
        platform="google_search_console", preferred_account_id=account_id,
        task_key="SEO-SUBMIT-001", refresh_devices=False,
    )
    assert routed["status"] == "risk_pause"
    assert routed["account_id"] == account_id
    assert routed["account_id"] != third["account_id"]
    assert routed["route_kind"] == "wait_owner"

    # Authorization state is short-lived; stale callbacks are rejected before token exchange.
    requests = read_json("r8_12/auth_requests.json", {})
    for item in requests.get("pending", []):
        if item.get("state") == google["state"]:
            item["created_at"] = (datetime.now().astimezone() - timedelta(minutes=30)).isoformat(timespec="seconds")
    write_json("r8_12/auth_requests.json", requests)
    try:
        _validate_request("google_search_console", google["state"])
        raise AssertionError("stale authorization state must be rejected")
    except ValueError as error:
        assert "超过10分钟" in str(error)

    ui = (SOURCE / "web" / "r8_12_multi_account_auth_ui.js").read_text(encoding="utf-8")
    center = (SOURCE / "web" / "r8_12_account_center.html").read_text(encoding="utf-8")
    for marker in ("+ 新增账号", "账号环境安全策略", "window.open", "/api/r8-12/auth/start", "重新授权账号"):
        assert marker in ui, marker
    for marker in ("环境稳定", "风控暂停", "重新授权", "设备：不要求/未指定"):
        assert marker in center, marker
    assert "password" not in ui.lower()

    print("R8-13 multi-account identity, official auth and environment safety checks passed")


if __name__ == "__main__":
    main()
