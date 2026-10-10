"""Release gate for #782 crawlability, migration and truthful GEO publishing."""
from __future__ import annotations

import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))


def main():
    temp = tempfile.mkdtemp(prefix=".kz-r825-web-", dir=ROOT)
    try:
        previous = os.environ.get("LOCALAPPDATA")
        os.environ["LOCALAPPDATA"] = temp
        try:
            from core import seo_geo_growth as growth
            from integrations import seo_public_deployer as deployer
            from integrations import r8_17_remote_deployer_patch as remote
            from integrations import search_engine_submitter as submitter
            from promotion import search_growth

            seo_ui = (SOURCE / "web" / "r8_13_seo_geo.html").read_text(encoding="utf-8")
            seo_backend = (SOURCE / "backend" / "r8_13_seo_geo_patch.py").read_text(encoding="utf-8")
            for marker in (
                "官网可抓取质量", "主站点地图", "SEO子站点地图", "公开页面样本",
                "检查官网与公开页", "/api/r8-13/seo-geo/audit-site",
            ):
                assert marker in seo_ui, marker
            assert 'technical = seo_observability.run(_dashboard_payload())' in seo_backend
            assert '"technical_audit": technical' in seo_backend

            growth.ensure_baseline()
            growth.plan_today(limit=2)
            result = growth.generate_staging(limit=2)
            assert result["count"] == 2, result
            assets = [row for row in growth.dashboard()["assets"] if row.get("staging_path")]
            assert len(assets) == 2

            for asset in assets:
                page = Path(asset["staging_path"]).read_text(encoding="utf-8")
                assert "{{" not in page, page[:500]
                assert 'name="robots" content="index,follow' in page
                assert 'property="og:title"' in page and 'property="og:url"' in page
                assert f'name="kazuizhi-template-version" content="{growth.PUBLIC_TEMPLATE_VERSION}"' in page
                assert "KZSEO-" in page and "kz_source=KZSEO-" in page
                assert "价格原则" in page and "服务与售后流程" in page and "来源编号" in page
                inspected = deployer._inspect_public_html(page, asset["title"], asset["canonical"])
                assert inspected["canonical_match"] is True, inspected
                assert inspected["schema_valid"] is True, inspected
                assert inspected["schema_urls_valid"] is True, inspected
                assert inspected["source_tracking_present"] is True, inspected
                assert inspected["visible_text_chars"] >= 500, inspected

                block = page.split('<script type="application/ld+json">', 1)[1].split("</script>", 1)[0]
                schema = json.loads(block)
                organization = next(row for row in schema["@graph"] if row.get("@type") == "Organization")
                service = next(row for row in schema["@graph"] if row.get("@type") == "Service")
                assert organization["url"] == "https://kazuizhi.com/", organization
                assert service["url"] == asset["canonical"], service

            # An upgrade must rebuild legacy public HTML without downgrading
            # SUBMITTED/CRAWLED/etc. evidence states.  Republish is tracked by
            # a separate flag and cleared only after live verification.
            legacy_id = assets[0]["id"]
            state = growth._load()
            legacy = next(row for row in state["assets"] if row.get("id") == legacy_id)
            legacy["stage"] = "SUBMITTED"
            legacy["public_template_version"] = "legacy"
            legacy["public_url"] = legacy["canonical"]
            growth._save(state)
            refreshed = growth.refresh_legacy_staging(limit=1)
            assert refreshed["refreshed"] == [legacy_id], refreshed
            migrated = next(row for row in growth.dashboard()["assets"] if row.get("id") == legacy_id)
            assert migrated["stage"] == "SUBMITTED", migrated
            assert migrated["republish_pending"] is True, migrated
            migrated_page = Path(migrated["staging_path"]).read_text(encoding="utf-8")
            assert growth.PUBLIC_TEMPLATE_VERSION in migrated_page
            growth.record_asset_republished(legacy_id, {"public_url": migrated["canonical"], "verification": {"ok": True}})
            republished = next(row for row in growth.dashboard()["assets"] if row.get("id") == legacy_id)
            assert republished["stage"] == "SUBMITTED", republished
            assert republished["republish_pending"] is False, republished
            assert republished["last_republished_at"], republished
            old_receipt = {
                **republished,
                "submission_receipts": [{"engine": "indexnow", "at": "2026-01-01T00:00:00+08:00", "receipt": "old"}],
            }
            assert submitter._existing_engine_receipt(old_receipt, "indexnow") is False
            current_receipt = {
                **old_receipt,
                "submission_receipts": [{"engine": "indexnow", "at": "2099-01-01T00:00:00+08:00", "receipt": "new"}],
            }
            assert submitter._existing_engine_receipt(current_receipt, "indexnow") is True

            sitemap = (Path(result["staging_root"]) / "sitemap.xml").read_text(encoding="utf-8")
            assert sitemap.count("<lastmod>") == 2, sitemap
            discovery = remote._root_discovery_files("https://kazuizhi.com/")
            root_map = discovery["sitemap.xml"].decode("utf-8")
            assert "<sitemapindex" in root_map and "<urlset" not in root_map, root_map
            legacy_map = b'<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://kazuizhi.com/</loc></url><url><loc>https://kazuizhi.com/seo/sitemap.xml</loc></url></urlset>'
            assert remote._legacy_root_sitemap(legacy_map, "https://kazuizhi.com/") is True
            assert remote._legacy_root_sitemap(discovery["sitemap.xml"], "https://kazuizhi.com/") is False

            original_status = remote._public_status
            original_text = remote._public_text
            original_upload = remote.remote_agent.upload_bytes
            repaired_state = {"done": False}
            remote._public_status = lambda url, timeout: {"ok": True, "status": 200, "url": url}
            remote._public_text = lambda url, timeout: {
                "ok": True, "status": 200, "url": url,
                "body": discovery["sitemap.xml"] if repaired_state["done"] else legacy_map,
                "sha256": "after" if repaired_state["done"] else "before",
            }
            def fake_upload(relative, content, job_id=""):
                repaired_state["done"] = True
                return {"ok": True, "job_id": job_id, "destination": relative}
            remote.remote_agent.upload_bytes = fake_upload
            try:
                repaired = remote._ensure_root_discovery("https://kazuizhi.com/", 2)
            finally:
                remote._public_status = original_status
                remote._public_text = original_text
                remote.remote_agent.upload_bytes = original_upload
            sitemap_repair = repaired["files"]["sitemap.xml"]
            assert sitemap_repair["repaired"] is True and sitemap_repair["repair_verified"] is True, sitemap_repair
            assert sitemap_repair["previous_sha256"] == "before" and "<urlset" in sitemap_repair["previous_body"]

            home = '<html><head><title>卡嘴子</title><meta name="description" content="本地服务"></head><body><div id="app"></div><script src="app.js"></script></body></html>'
            root_sitemap = '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://kazuizhi.com/</loc></url><url><loc>https://kazuizhi.com/seo/sitemap.xml</loc></url></urlset>'
            child_sitemap = '<?xml version="1.0"?><urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9"><url><loc>https://kazuizhi.com/seo/sample/</loc></url></urlset>'
            thin = '<html><head><script type="application/ld+json">{"@context":"https://schema.org","@type":"Organization","url":"{{https://kazuizhi.com/seo/sample/}}"}</script></head><body><h1>样本</h1></body></html>'
            bodies = {
                "https://kazuizhi.com/": (200, home),
                "https://kazuizhi.com/robots.txt": (200, "User-agent: *\nAllow: /"),
                "https://kazuizhi.com/sitemap.xml": (200, root_sitemap),
                "https://kazuizhi.com/seo/sitemap.xml": (200, child_sitemap),
                "https://kazuizhi.com/seo/sample/": (200, thin),
            }
            original_fetch = search_growth._fetch
            search_growth._fetch = lambda url: {"url": url, "status": bodies[url][0], "content_type": "text/html", "body": bodies[url][1]}
            try:
                audit = search_growth.audit({"site": "https://kazuizhi.com/"})
            finally:
                search_growth._fetch = original_fetch
            joined = "；".join(audit["blockers"])
            for marker in (
                "首页缺少 canonical", "首页缺少 Open Graph", "前端JS壳", "普通内部链接",
                "应改为 sitemapindex", "缺少逐页 lastmod", "未替换的网址模板", "正文偏薄",
            ):
                assert marker in joined, (marker, joined)
            assert audit["result"] == "needs_work"
        finally:
            if previous is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = previous
    finally:
        shutil.rmtree(temp, ignore_errors=True)

    print("PASS: #782 crawlable pages, legacy migration, resubmission revisions and live audit blockers verified")


if __name__ == "__main__":
    main()
