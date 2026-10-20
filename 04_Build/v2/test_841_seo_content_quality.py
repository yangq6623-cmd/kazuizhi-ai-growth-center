"""#841 isolated QA: 3 real SEO assets, intent copy and republish safety.

This test cannot write to the actual public website, emit search submissions,
create customer data or modify the user's persistent local ledgers.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "05_V2.0.0_Source"


def main():
    original = os.environ.get("LOCALAPPDATA")
    with tempfile.TemporaryDirectory(prefix="kz-841-seo-qc-") as tmp:
        os.environ["LOCALAPPDATA"] = tmp
        sys.path.insert(0, str(SRC))
        try:
            from core import seo_geo_growth as growth, seo_content_quality as quality
            from core import seo_geo_autonomy
            from integrations import seo_public_deployer

            fixtures = [
                ("9c7e309e8d0ebd77", "SEO-31E04B858348", "涟水县水电维修上门", "水电安装维修"),
                ("077ab037e185be7b", "SEO-A0D69FA9F671", "涟水漏水电路故障维修", "水电安装维修"),
                ("adadb41b67cec9e3", "SEO-61AA21F956B0", "涟水家政保洁上门", "家政保洁"),
            ]
            facts = growth.DEFAULT_BRAND_FACTS
            assets = []
            rendered = {}
            for slug, asset_id, keyword, service in fixtures:
                url = f"https://kazuizhi.com/seo/{slug}/"
                asset = {
                    "id": asset_id, "slug": slug, "region": "涟水县",
                    "keyword": keyword, "service": service,
                    "canonical": url, "public_url": url,
                    "stage": "SUBMITTED", "published_at": "2026-10-16T12:00:00+08:00",
                    "public_template_version": growth.PUBLIC_TEMPLATE_VERSION,
                    "submission_receipts": [{"at": "2026-10-17", "engine": "indexnow", "receipt": "historical"}],
                }
                title, description, html = growth._render_page(asset, facts, canonical=url)
                assert keyword in title and description and len(html) > 1500
                assert quality.validate_staged_content(asset, html)["ok"], (keyword, quality.validate_staged_content(asset, html))
                assert url in html and "kz_source=" in html and "asset_id=" in html
                rendered[slug] = html
                assets.append(asset)

            assert rendered[fixtures[0][0]] != rendered[fixtures[1][0]], "水电通用页与漏水电路页不能完全重复"
            assert "漏水附近出现跳闸" in rendered["077ab037e185be7b"]
            assert "预约时怎样避免服务范围不清" in rendered["adadb41b67cec9e3"]
            cleaning = rendered["adadb41b67cec9e3"]
            for banned in ("维修类项目应先检测", "现场检测后明细报价", "故障现象、发生时间、设备型号", "在线报修"):
                assert banned not in cleaning, banned
            bad = cleaning.replace("保洁范围", "维修类项目应先检测", 1)
            assert not quality.validate_staged_content(assets[2], bad)["ok"]

            # A fourth historic page must not get mass-republished just because
            # #841 improves future page copy.
            other = {
                "id": "SEO-UNCHANGED", "slug": "not-in-surgical-scope",
                "keyword": "涟水热水器上门维修", "service": "家电维修",
                "region": "涟水县", "stage": "SUBMITTED",
                "canonical": "https://kazuizhi.com/seo/not-in-surgical-scope/",
                "public_url": "https://kazuizhi.com/seo/not-in-surgical-scope/",
                "public_template_version": growth.PUBLIC_TEMPLATE_VERSION,
                "published_at": "2026-10-17T12:00:00+08:00",
            }
            state = growth._load()
            state["assets"] = assets + [other]
            growth._save(state)
            result = growth.refresh_legacy_staging(limit=10)
            assert set(result["refreshed"]) == {a["id"] for a in assets}, result
            after = growth._load()["assets"]
            assert len(after) == 4
            for row in after[:3]:
                assert row["stage"] == "SUBMITTED", row
                assert row["republish_pending"], row
                assert row["content_quality_revision"] == quality.CONTENT_QUALITY_REVISION
                assert str(row.get("content_revision_id") or "").startswith("QUALITY-")
                assert row["submission_receipts"] == [{"at": "2026-10-17", "engine": "indexnow", "receipt": "historical"}]
                stage_file = Path(row["staging_path"])
                assert stage_file.is_file()
                assert seo_public_deployer.validate_public_content(row, stage_file)["ok"]

            assert "republish_pending" not in after[3] and not after[3].get("staging_path")
            # Existing re-rendering is idempotent; do not create a second
            # publication or content revision for the same durable Asset.
            retry = growth.refresh_legacy_staging(limit=10)
            assert retry["count"] == 0, retry
            assert len(growth._load()["assets"]) == 4
            assert all(row["stage"] == "SUBMITTED" for row in growth._load()["assets"])
            assert len(growth._load()["submission_events"]) == 0

            # The existing Generated -> QC_PASSED gate must reject a bad
            # cleaning page before it gets any permission to deploy.
            invalid = dict(after[2])
            invalid["id"] = "SEO-BAD-CLEANING"
            invalid["slug"] = "bad-cleaning-staging"
            invalid["stage"] = "GENERATED"
            invalid["republish_pending"] = False
            invalid_path = Path(tmp) / "bad-cleaning.html"
            invalid_path.write_text(bad, encoding="utf-8")
            invalid["staging_path"] = str(invalid_path)
            newer = growth._load()
            newer["assets"].append(invalid)
            growth._save(newer)
            verdict = seo_geo_autonomy._local_qc_generated_assets(limit=20)
            assert any(x["asset_id"] == invalid["id"] and "家政保洁页混入维修模板话术" in x["reasons"]
                       for x in verdict["failed"]), verdict
            assert growth._load()["assets"][-1]["stage"] == "GENERATED"
            print("#841 SEO content quality, surgical republish, and QC gates: PASS")
        finally:
            if original is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = original
            if str(SRC) in sys.path:
                sys.path.remove(str(SRC))


if __name__ == "__main__":
    main()
