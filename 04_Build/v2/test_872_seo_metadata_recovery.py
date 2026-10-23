"""#872 regression: recover exact SEO semantics without falsifying publication.

Uses only synthetic JSON ledgers under a temporary LOCALAPPDATA.  It does not
touch the production site, browser, search engines, or any external account.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))

sandbox = Path(tempfile.mkdtemp(prefix="kazuizhi-872-seo-metadata-"))
previous = os.environ.get("LOCALAPPDATA")
os.environ["LOCALAPPDATA"] = str(sandbox)


try:
    from core import seo_geo_growth as growth
    from core.storage import now_iso, write_json
    from integrations import seo_public_deployer as deployer

    region = "涟水县"
    service = "家电维修"
    keyword = "涟水县家电维修本地服务"
    asset_id = growth._stable_id("SEO", region, service, keyword)
    assert asset_id == "SEO-BDBB6D3893E0"
    slug = "bc999910286a647c"
    public_url = f"https://kazuizhi.com/seo/{slug}/"
    action_id = "GEO-GROWTH-D4BBF14879F4"
    receipt_id = "REMOTE-DEPLOY-SEO-BDBB6D3893E0-TEST"

    state = growth._empty_state()
    state["assets"] = [{
        "id": asset_id,
        "opportunity_id": "",
        "region": "",
        "service": "",
        "keyword": slug,
        "intent": "",
        "priority": "",
        "page_type": "已恢复公开页",
        "slug": slug,
        "stage": "SUBMITTED",
        "created_at": "",
        "updated_at": now_iso(),
        "published_at": "2026-10-23T13:38:02+08:00",
        "public_url": public_url,
        "canonical": public_url,
        "staging_path": "",
        "title": "涟水县本地服务需求发布与办理指南｜卡嘴子本地服务",
        "description": "",
        "content_revision_id": action_id,
        "public_template_version": growth.PUBLIC_TEMPLATE_VERSION,
        "submission_receipts": [{"at": now_iso(), "engine": "IndexNow", "receipt": "SUBMIT-OLD"}],
        "events": [],
    }]
    growth._save(state)
    write_json("geo_validation/growth_orchestrator.json", {
        "schema": "kz.geo-growth-os.v1",
        "opportunities": [{
            "id": action_id,
            "seo_opportunity_id": growth._stable_id("KW", region, service, keyword),
            "asset_id": asset_id,
            "content_revision_id": action_id,
            "region": region,
            "service": service,
            "keyword": keyword,
            "intent": "GEO运营优化",
            "priority": "A",
        }],
    })
    receipt = {
        "receipt_id": receipt_id,
        "asset_id": asset_id,
        "public_url": public_url,
        "growth_action_id": action_id,
        "content_revision_id": action_id,
        "created_at": "2026-10-23T13:38:02+08:00",
        "verification": {"ok": True, "canonical": public_url},
    }

    result = growth.rehydrate_verified_publications([receipt])
    assert result["restored"] == []
    assert result["metadata_repaired"] == [asset_id], result
    repaired = next(row for row in growth._load()["assets"] if row["id"] == asset_id)
    assert repaired["region"] == region
    assert repaired["service"] == service
    assert repaired["keyword"] == keyword
    assert repaired["stage"] == "SUBMITTED"
    assert repaired["public_url"] == public_url
    assert repaired["submission_receipts"][0]["receipt"] == "SUBMIT-OLD"
    assert repaired["metadata_repair_pending"] is True

    refresh = growth.refresh_legacy_staging(limit=10)
    assert refresh["refreshed"] == [asset_id], refresh
    staged = next(row for row in growth._load()["assets"] if row["id"] == asset_id)
    html = Path(staged["staging_path"]).read_text(encoding="utf-8")
    assert keyword in staged["title"] and keyword in html
    assert f"服务类别</strong><br>{service}" in html
    assert staged["stage"] == "SUBMITTED"
    assert staged["republish_pending"] is True
    assert staged["content_revision_id"].startswith("SEO-META-")

    completed = growth.record_asset_republished(asset_id, {
        "public_url": public_url,
        "deploy_receipt": "REMOTE-DEPLOY-METADATA-REPAIR-TEST",
        "content_revision_id": staged["content_revision_id"],
    })
    assert completed["stage"] == "SUBMITTED"
    assert completed["metadata_repair_pending"] is False
    assert completed["public_url"] == public_url

    snapshot = deployer.asset_receipt_snapshot(staged)
    assert snapshot["region"] == region and snapshot["service"] == service
    assert snapshot["keyword"] == keyword
    assert "site_root" not in snapshot and "token" not in snapshot and "password" not in snapshot

    print(
        "PASS #872: exact GEO identity repairs degraded SEO metadata, stages a distinct "
        "revision, and preserves URL, submission Receipt, and external stage"
    )
finally:
    if previous is None:
        os.environ.pop("LOCALAPPDATA", None)
    else:
        os.environ["LOCALAPPDATA"] = previous
    shutil.rmtree(sandbox, ignore_errors=True)
