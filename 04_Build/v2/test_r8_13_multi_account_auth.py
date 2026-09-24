from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))

os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="kz-r813-auth-")

from integrations.platform_auth_catalog import catalog, start_authorization  # noqa: E402


def main():
    data = catalog()
    providers = {x["platform"]: x for x in data["providers"]}
    required = {
        "google_search_console",
        "bing_webmaster",
        "baidu_search_resource",
        "douyin",
        "kuaishou",
        "xiaohongshu",
        "wechat_channels",
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

    baidu = start_authorization("baidu_search_resource", slot_label="百度账号1")
    assert baidu["ok"] is True
    assert baidu["requires_manual_completion"] is True
    assert baidu["authorization_url"].startswith("https://ziyuan.baidu.com/")

    # Missing official client credentials must never fabricate a successful OAuth URL.
    for key in ("KZ_GOOGLE_SEARCH_CLIENT_ID", "KZ_GOOGLE_SEARCH_CLIENT_SECRET"):
        os.environ.pop(key, None)
    google_missing = start_authorization(
        "google_search_console",
        slot_label="Google账号1",
        redirect_uri="http://127.0.0.1:8876/api/r8-12/oauth/callback/google_search_console",
    )
    assert google_missing["ok"] is False
    assert google_missing["needs_app_credentials"] is True

    os.environ["KZ_GOOGLE_SEARCH_CLIENT_ID"] = "test-client"
    os.environ["KZ_GOOGLE_SEARCH_CLIENT_SECRET"] = "test-secret"
    google = start_authorization(
        "google_search_console",
        slot_label="Google账号2",
        redirect_uri="http://127.0.0.1:8876/api/r8-12/oauth/callback/google_search_console",
    )
    assert google["ok"] is True
    assert google["authorization_url"].startswith("https://accounts.google.com/o/oauth2/v2/auth?")
    assert "prompt=select_account+consent" in google["authorization_url"]

    os.environ["KZ_DOUYIN_CLIENT_KEY"] = "test-key"
    os.environ["KZ_DOUYIN_CLIENT_SECRET"] = "test-secret"
    douyin = start_authorization(
        "douyin",
        slot_label="抖音账号2",
        redirect_uri="http://127.0.0.1:8876/api/r8-12/oauth/callback/douyin",
    )
    assert douyin["ok"] is False
    assert douyin["needs_https_callback"] is True

    ui = (SOURCE / "web" / "r8_12_multi_account_auth_ui.js").read_text(encoding="utf-8")
    for marker in ("+ 新增账号", "账号环境安全策略", "window.open", "/api/r8-12/auth/start"):
        assert marker in ui, marker
    assert "password" not in ui.lower()

    print("R8-13 multi-account auth launcher truth and safety checks passed")


if __name__ == "__main__":
    main()
