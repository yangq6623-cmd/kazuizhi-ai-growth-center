from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))

os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="kz-860-seo-")
os.environ["KZ_INDEXNOW_KEY"] = "KazuizhiIndexNow20261023"

from core import seo_geo_growth as growth  # noqa: E402
from core.storage import now_iso  # noqa: E402
from integrations import search_engine_submitter as submitter  # noqa: E402
from integrations import seo_public_deployer as deployer  # noqa: E402


TARGET_ID = "SEO-0CB250BBE457"
TARGET_REVISION = "SEO-REV-88DACE8A3C84"
TARGET_KEYWORD = "涟水县洗衣机不排水上门维修"


def _historical(index: int) -> dict:
    submitted = index < 31
    return {
        "id": f"SEO-HISTORY-{index:02d}",
        "opportunity_id": f"KW-HISTORY-{index:02d}",
        "region": "涟水县",
        "service": "水电安装维修",
        "keyword": f"历史页面{index:02d}",
        "stage": "SUBMITTED" if submitted else "PUBLISHED",
        "created_at": "2026-10-01T00:00:00+08:00",
        "updated_at": "2026-10-01T00:00:00+08:00",
        "published_at": "2026-10-01T00:00:00+08:00",
        "public_url": f"https://kazuizhi.example/seo/history-{index:02d}/",
        "canonical": f"https://kazuizhi.example/seo/history-{index:02d}/",
        "submission_receipts": (
            [{"at": "2026-10-01T00:01:00+08:00", "engine": "indexnow", "receipt": f"OLD-{index:02d}"}]
            if submitted else []
        ),
        "events": [],
    }


def main():
    data = growth._load()
    historical = [_historical(index) for index in range(32)]
    historical_ids = {row["id"] for row in historical}
    opportunity_id = growth._stable_id("KW", "涟水县", "家电维修", TARGET_KEYWORD)
    slug = growth._slug(f"涟水县-家电维修-{TARGET_KEYWORD}")
    canonical = f"https://kazuizhi.example/seo/{slug}/"
    target = {
        "id": TARGET_ID,
        "opportunity_id": opportunity_id,
        "region": "涟水县",
        "service": "家电维修",
        "keyword": TARGET_KEYWORD,
        "intent": "交易",
        "priority": "S",
        "page_type": "地区×服务页",
        "slug": slug,
        "stage": "QC_PASSED",
        "created_at": "2026-10-22T12:20:00+08:00",
        "updated_at": "2026-10-22T12:21:00+08:00",
        "content_revision_id": TARGET_REVISION,
        "public_url": "",
        "canonical": canonical,
        "submission_receipts": [],
        "events": [{
            "at": "2026-10-22T12:21:00+08:00",
            "stage": "QC_PASSED",
            "payload": {"local_qc": "R8 deterministic SEO page QC"},
        }],
    }
    # This is the production-derived #860 compatibility shape: the trusted
    # source exists on Opportunity, but the already-created Asset did not
    # inherit it.
    opportunity = {
        "id": opportunity_id,
        "region": "涟水县",
        "service": "家电维修",
        "keyword": TARGET_KEYWORD,
        "intent": "交易",
        "priority": "S",
        "status": "PLANNED",
        "source": "autonomous_verified_service_intent_pool",
        "discovered_at": "2026-10-22T12:20:00+08:00",
        "asset_id": TARGET_ID,
    }
    staging = Path(os.environ["LOCALAPPDATA"]) / "fixture" / slug / "index.html"
    staging.parent.mkdir(parents=True)
    title, description, html = growth._render_page(
        target, data["brand_facts"], canonical=canonical, related=[]
    )
    staging.write_text(html, encoding="utf-8")
    target.update({
        "title": title,
        "description": description,
        "staging_path": str(staging),
        "generated_at": target["created_at"],
    })
    data["assets"] = historical + [target]
    data["opportunities"] = [opportunity]
    growth._save(data)

    before = growth.dashboard()
    assert before["summary"]["public_pages"] == 32, before["summary"]
    assert before["summary"]["submitted_urls"] == 31, before["summary"]
    assert deployer.publication_scope_allowed(target) is False
    assert deployer.publication_scope_allowed(target, opportunity) is True

    site_root = Path(tempfile.mkdtemp(prefix="kz-860-site-")) / "kazuizhi-site"
    site_root.mkdir(parents=True)
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
        "schema_urls_valid": True,
        "page_indexable": True,
        "source_tracking_present": True,
        "visible_text_chars": 800,
        "robots": {"allowed": True},
        "checked_at": now_iso(),
    }
    try:
        deployed = deployer.deploy_pending(limit=5)
    finally:
        deployer._verify_public_url = original_verify
    assert [row["asset_id"] for row in deployed["published"]] == [TARGET_ID], deployed
    assert not deployed["failed"], deployed

    published = next(row for row in growth.dashboard()["assets"] if row["id"] == TARGET_ID)
    assert published["stage"] == "PUBLISHED", published
    assert published["public_url"].startswith("https://kazuizhi.example/seo/"), published
    assert deployer.publication_scope_allowed(published) is True

    original_key_verify = submitter._ensure_indexnow_key_file
    original_submit = submitter._submit_indexnow
    submitter._ensure_indexnow_key_file = lambda key, timeout=8: {
        "ok": True,
        "status": 200,
        "key_location": f"https://kazuizhi.example/seo/{key}.txt",
        "checked_at": now_iso(),
    }
    submitter._submit_indexnow = lambda urls, key, key_location, endpoint, timeout=15: {
        "ok": True,
        "status": 200,
        "submitted": len(urls),
        "response": "",
        "at": now_iso(),
    }
    try:
        submitted = submitter.submit_pending(limit=3)
    finally:
        submitter._ensure_indexnow_key_file = original_key_verify
        submitter._submit_indexnow = original_submit
    assert submitted["submitted_count"] == 1, submitted

    repeated_deploy = deployer.deploy_pending(limit=5)
    repeated_submit = submitter.submit_pending(limit=3)
    assert not repeated_deploy["published"], repeated_deploy
    assert repeated_submit.get("submitted_count", 0) == 0, repeated_submit

    after = growth.dashboard()
    target_after = next(row for row in after["assets"] if row["id"] == TARGET_ID)
    assert target_after["stage"] == "SUBMITTED", target_after
    assert target_after["submission_receipts"], target_after
    assert after["summary"]["public_pages"] == 33, after["summary"]
    assert after["summary"]["submitted_urls"] == 32, after["summary"]
    assert historical_ids.issubset({row["id"] for row in after["assets"]})

    unrelated = {
        "region": "涟水县",
        "service": "家电维修",
        "keyword": "未经批准的自由关键词",
        "opportunity_source": "autonomous_verified_service_intent_pool",
        "stage": "QC_PASSED",
    }
    assert deployer.publication_scope_allowed(unrelated) is False

    # The installed Windows runtime uses the R8-17 Remote Agent patch. Rewind
    # only the isolated target copy and prove the same #860 compatibility shape
    # is claimable there, while a repeated run remains idempotent.
    remote_data = growth._load()
    remote_target = next(row for row in remote_data["assets"] if row["id"] == TARGET_ID)
    remote_target["stage"] = "QC_PASSED"
    remote_target["public_url"] = ""
    remote_target["published_at"] = ""
    remote_target["submission_receipts"] = []
    remote_target["events"] = [{
        "at": "2026-10-22T12:21:00+08:00",
        "stage": "QC_PASSED",
        "payload": {"local_qc": "R8 deterministic SEO page QC"},
    }]
    growth._save(remote_data)

    from integrations import r8_17_remote_deployer_patch as remote_patch  # noqa: E402

    remote_config = deployer._load()
    remote_config.update({
        "enabled": True,
        "mode": remote_patch.REMOTE_MODE,
        "public_base_url": "https://kazuizhi.example/",
        "verify_http": True,
    })
    deployer._save(remote_config)
    remote_patch.status = lambda: {
        "ready": True,
        "mode": remote_patch.REMOTE_MODE,
        "public_base_url": "https://kazuizhi.example/",
    }
    remote_patch.remote_agent.upload_file = lambda relative, source, job_id: {
        "job_id": job_id,
        "sha256": "a" * 64,
    }
    remote_patch.remote_agent.upload_bytes = lambda relative, content, job_id: {
        "job_id": job_id,
        "sha256": "b" * 64,
    }
    remote_patch._public_text = lambda url, timeout: {
        "status": 200,
        "body": b'<link rel="canonical"><script type="application/ld+json"></script>' + b"x" * 2000,
    }
    remote_patch._ensure_root_discovery = lambda base, timeout: {"ok": True}
    deployer._verify_public_url = lambda url, expected, expected_canonical, timeout: {
        "ok": True,
        "status": 200,
        "content_match": True,
        "canonical_match": True,
        "schema_valid": True,
        "schema_urls_valid": True,
        "page_indexable": True,
        "source_tracking_present": True,
        "visible_text_chars": 800,
        "robots": {"allowed": True},
        "checked_at": now_iso(),
    }
    remote_result = remote_patch.deploy_pending(limit=5)
    assert [row["asset_id"] for row in remote_result["published"]] == [TARGET_ID], remote_result
    assert not remote_result["failed"], remote_result
    remote_published = next(row for row in growth.dashboard()["assets"] if row["id"] == TARGET_ID)
    assert remote_published["stage"] == "PUBLISHED", remote_published
    assert deployer.publication_scope_allowed(remote_published) is True
    repeated_remote = remote_patch.deploy_pending(limit=5)
    assert repeated_remote["attempted"] == 0, repeated_remote
    assert not repeated_remote["published"], repeated_remote
    print("#860 SEO publication compatibility closure passed: 32/31 -> 33/32")


if __name__ == "__main__":
    main()
