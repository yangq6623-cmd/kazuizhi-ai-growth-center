from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))

os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="kz-r816-")
os.environ["KZ_INDEXNOW_KEY"] = "KazuizhiIndexNow20260925"

from core.seo_geo_growth import dashboard, ensure_baseline, generate_staging, plan_today, record_asset_stage  # noqa: E402
from integrations import search_engine_submitter as submitter  # noqa: E402
from integrations import seo_public_deployer as deployer  # noqa: E402


def publish_one(site_root: Path):
    plan_today(limit=1)
    generated = generate_staging(limit=1)
    assert generated["count"] == 1, generated
    asset = next(x for x in dashboard()["assets"] if x["stage"] == "GENERATED")
    record_asset_stage(asset["id"], "QC_PASSED", {"local_qc": "R8-16 test"})
    deployer.configure({
        "enabled": True,
        "site_root": str(site_root),
        "public_base_url": "https://kazuizhi.example/",
    })
    original_verify = deployer._verify_public_url
    deployer._verify_public_url = lambda url, expected, expected_canonical, timeout: {
        "ok": True,
        "status": 200,
        "content_match": True,
        "canonical_match": True,
        "schema_valid": True,
        "page_indexable": True,
        "robots": {"allowed": True},
        "checked_at": "test",
    }
    try:
        result = deployer.deploy_pending(limit=5)
    finally:
        deployer._verify_public_url = original_verify
    assert len(result["published"]) == 1, result
    return next(x for x in dashboard()["assets"] if x["id"] == asset["id"])


def main():
    ensure_baseline()
    site_root = Path(tempfile.mkdtemp(prefix="kz-r816-site-")) / "kazuizhi-site"
    site_root.mkdir(parents=True)

    # IndexNow must initialize itself after the public deploy connector is
    # available.  This is only key-file verification, not a claimed search
    # submission receipt.
    memory = {}
    original_vault_get = submitter._vault_get
    original_vault_put = submitter._vault_put
    original_public_status = deployer.status
    original_key_verify = submitter._ensure_indexnow_key_file
    submitter._vault_get = lambda key, env_name="": memory.get(key, "")
    submitter._vault_put = lambda key, value: memory.__setitem__(key, value)
    deployer.status = lambda: {"ready": True, "site_root": str(site_root), "public_base_url": "https://kazuizhi.example/"}
    submitter._ensure_indexnow_key_file = lambda key, timeout=8: {"ok": True, "status": 200, "key_location": f"https://kazuizhi.example/seo/{key}.txt", "checked_at": "test"}
    try:
        initialized = submitter.initialize_indexnow()
    finally:
        submitter._vault_get = original_vault_get
        submitter._vault_put = original_vault_put
        deployer.status = original_public_status
        submitter._ensure_indexnow_key_file = original_key_verify
    assert initialized["ok"] is True and initialized["key_created"] is True, initialized
    assert initialized["key_location"].startswith("https://kazuizhi.example/seo/"), initialized
    # The submitter must read the deployment module dynamically.  R8-17
    # replaces that module's status function for Remote Agent mode, so a stale
    # imported function would incorrectly expose IndexNow initialization.
    assert "from integrations import seo_public_deployer" in (SOURCE / "integrations" / "search_engine_submitter.py").read_text(encoding="utf-8")

    first = publish_one(site_root)
    assert first["stage"] == "PUBLISHED", first

    # A search submission receipt is required before advancing to SUBMITTED.
    original_key_verify = submitter._ensure_indexnow_key_file
    original_submit = submitter._submit_indexnow
    submitter._ensure_indexnow_key_file = lambda key, timeout=8: {
        "ok": True,
        "status": 200,
        "key_location": "https://kazuizhi.example/seo/key.txt",
        "checked_at": "test",
    }
    submitter._submit_indexnow = lambda urls, key, key_location, endpoint, timeout=15: {
        "ok": True,
        "status": 200,
        "submitted": len(urls),
        "response": "",
        "at": "test",
    }
    try:
        result = submitter.submit_pending(limit=10)
    finally:
        submitter._ensure_indexnow_key_file = original_key_verify
        submitter._submit_indexnow = original_submit

    assert result["submitted_count"] >= 1, result
    first_after = next(x for x in dashboard()["assets"] if x["id"] == first["id"])
    assert first_after["stage"] == "SUBMITTED", first_after
    assert any(x.get("engine") == "indexnow" and x.get("receipt") for x in first_after.get("submission_receipts") or []), first_after

    # A rejected external response must not fake SUBMITTED.
    second = publish_one(site_root)
    assert second["stage"] == "PUBLISHED", second
    submitter._ensure_indexnow_key_file = lambda key, timeout=8: {
        "ok": True,
        "status": 200,
        "key_location": "https://kazuizhi.example/seo/key.txt",
        "checked_at": "test",
    }
    submitter._submit_indexnow = lambda urls, key, key_location, endpoint, timeout=15: {
        "ok": False,
        "status": 403,
        "submitted": 0,
        "response": "key rejected",
        "at": "test",
    }
    try:
        failed = submitter.submit_pending(limit=10)
    finally:
        submitter._ensure_indexnow_key_file = original_key_verify
        submitter._submit_indexnow = original_submit

    assert failed["failed"], failed
    second_after = next(x for x in dashboard()["assets"] if x["id"] == second["id"])
    assert second_after["stage"] == "PUBLISHED", second_after

    # A Baidu quota rejection proves the connector reached Baidu; it must be
    # represented distinctly and must not re-attempt the same page versions
    # again on the same natural day.
    original_baidu_token = submitter._baidu_token
    original_baidu_submit = submitter._submit_baidu
    submitter._baidu_token = lambda: "test-token"
    submitter._submit_baidu = lambda urls, site, token, timeout=15: {
        "ok": False,
        "status": 400,
        "response": {"error": 400, "message": "over quota"},
        "submitted": len(urls),
        "at": "test",
    }
    try:
        submitter.configure({"allow_baidu_http_submission": True, "baidu_site": "kazuizhi.example"})
        quota = submitter.submit_pending(limit=100)
        retry = submitter.submit_pending(limit=3)
    finally:
        submitter._baidu_token = original_baidu_token
        submitter._submit_baidu = original_baidu_submit

    baidu_failure = next(row for row in quota["failed"] if row["engine"] == "baidu")
    assert quota["batch_limit"] == 3, quota
    assert quota["eligible_by_engine"]["baidu"] <= 3, quota
    assert baidu_failure["reason"] == "baidu_quota_exhausted", quota
    assert retry["eligible_by_engine"]["baidu"] == 0, retry
    legacy_quota = {
        "last_run_at": submitter.now_iso(),
        "last_result": {"failed": [{"engine": "baidu", "reason": "api_submit_failed", "result": {"message": "over quota"}}]},
    }
    submitter._normalize_baidu_quota_failure(legacy_quota)
    assert submitter._baidu_quota_held_today(legacy_quota) is True, legacy_quota

    connector = submitter.status()
    assert connector["connectors"]["bing"]["configured"] is True, connector
    assert connector["connectors"]["so360"]["monitoring_only"] is True, connector
    assert connector["connectors"]["doubao_search"]["monitoring_only"] is True, connector
    assert connector["connectors"]["douyin_search"]["monitoring_only"] is True, connector
    assert connector["connectors"]["so360"]["submit_capable"] is False, connector
    assert connector["automation_summary"]["auto_submit_enabled"] is True, connector
    assert connector["truth"].find("SUBMITTED") >= 0
    # Failed submissions are de-duplicated while their exponential backoff is
    # active, then become eligible again; successful receipts remain permanent.
    retry_data = {**submitter.DEFAULT, "submission_attempts": {}}
    retry_asset = {"id": "SEO-RETRY", "published_at": "2026-10-07T10:00:00+08:00", "submission_receipts": []}
    submitter._record_attempt(retry_data, "indexnow", [retry_asset])
    submitter._record_failure(retry_data, "indexnow", [retry_asset], "endpoint_rejected")
    assert submitter._retry_blocked(retry_data, "indexnow", retry_asset) is True
    retry_entry = retry_data["submission_attempts"]["indexnow"]["SEO-RETRY"]
    assert retry_entry["failure_count"] == 1 and retry_entry["next_retry_at"], retry_entry

    # Owner-facing controls must invoke a real initialization endpoint.  The
    # Search Console control must also be able to start official authorization
    # directly: the optional account-center bridge cannot be a single point of
    # failure for the visible button.
    page = (SOURCE / "web" / "r8_13_seo_geo.html").read_text(encoding="utf-8")
    bridge = (SOURCE / "web" / "r8_13_seo_geo_bridge.js").read_text(encoding="utf-8")
    assert "/api/r8-16/search-submit/initialize" in page
    assert "/api/r8-12/auth/start" in page
    assert "beginSearchAuthorization" in page
    assert "KZAuthUI" in bridge
    assert "已连接·额度用尽" in page
    assert "baidu_quota_exhausted" in page
    assert "baidu_quota_hold" in page
    for marker in ("360搜索站长平台", "豆包搜索 / 豆包浏览器", "抖音搜索 / 抖音浏览器", "自动重试", "不计SUBMITTED"):
        assert marker in page, marker

    # Repeated OAuth callbacks create a history of account assets.  The
    # submitter must use the newest usable credential instead of silently
    # retrying an old, expired access token.
    original_read_json = submitter.read_json
    original_vault_get = submitter._vault_get
    registry = {
        "accounts": [
            {"account_id": "ACC-GSC-OLD", "platform": "google_search_console", "updated_at": "2026-09-27T10:00:00+08:00", "auth": {"status": "connected", "last_verified_at": "2026-09-27T10:00:00+08:00"}},
            {"account_id": "ACC-GSC-NEW", "platform": "google_search_console", "updated_at": "2026-09-27T16:00:00+08:00", "auth": {"status": "connected", "last_verified_at": "2026-09-27T16:00:00+08:00"}},
        ]
    }
    submitter.read_json = lambda path, default: registry if path == submitter.REGISTRY else original_read_json(path, default)
    submitter._vault_get = lambda key, env_name="": "fresh-token" if key == "oauth.ACC-GSC-NEW.access_token" else ""
    try:
        selected = submitter._connected_account("google_search_console")
    finally:
        submitter.read_json = original_read_json
        submitter._vault_get = original_vault_get
    assert selected and selected["account_id"] == "ACC-GSC-NEW", selected

    # A stored token that has actually received a Google 401 must not be
    # rendered as a ready connector.  The owner needs a clear reauthorization
    # action rather than a misleading green state and repeated failed jobs.
    original_load = submitter._load
    original_connected = submitter._connected_account
    original_google_token = submitter._google_access_token
    submitter._load = lambda: {
        **submitter.DEFAULT,
        "last_result": {"failed": [{"engine": "google_search_console", "reason": "sitemap_submit_failed", "result": {"status": 401, "response": "UNAUTHENTICATED"}}]},
    }
    submitter._connected_account = lambda platform: {"account_id": "ACC-GSC-NEW"} if platform == "google_search_console" else None
    submitter._google_access_token = lambda account: "stale-token"
    try:
        google_status = submitter.status()["connectors"]["google"]
    finally:
        submitter._load = original_load
        submitter._connected_account = original_connected
        submitter._google_access_token = original_google_token
    assert google_status["configured"] is True and google_status["ready"] is False, google_status
    assert google_status["reauthorization_required"] is True, google_status
    assert "401" in google_status["reason"], google_status

    # An upgrade can restore a page from an immutable public deployment
    # receipt.  It may have no local revision timestamp, but it should receive
    # one capped initial submission rather than remaining PUBLISHED forever.
    recovered = {
        "id": "SEO-RECOVERED", "public_url": "https://kazuizhi.example/seo/recovered/",
        "submission_receipts": [],
        "events": [{"payload": {"recovered_from_verified_receipt": True}}],
    }
    ordinary_legacy = {"id": "SEO-LEGACY", "public_url": "https://kazuizhi.example/seo/legacy/", "submission_receipts": [], "events": []}
    eligible, legacy_count = submitter._eligible_assets({**submitter.DEFAULT, "submission_attempts": {}}, "indexnow", [recovered, ordinary_legacy], 3)
    assert [row["id"] for row in eligible] == ["SEO-RECOVERED"], eligible
    assert legacy_count == 1, legacy_count

    print("R8-16 truthful IndexNow/search submission receipt gates passed")


if __name__ == "__main__":
    main()
