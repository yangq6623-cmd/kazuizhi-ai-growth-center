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

    connector = submitter.status()
    assert connector["connectors"]["bing"]["configured"] is True, connector
    assert connector["truth"].find("SUBMITTED") >= 0

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

    print("R8-16 truthful IndexNow/search submission receipt gates passed")


if __name__ == "__main__":
    main()
