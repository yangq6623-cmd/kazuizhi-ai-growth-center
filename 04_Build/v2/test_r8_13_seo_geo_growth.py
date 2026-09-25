import importlib
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))


def main():
    with tempfile.TemporaryDirectory() as temp:
        previous = os.environ.get("LOCALAPPDATA")
        os.environ["LOCALAPPDATA"] = temp
        try:
            import core.storage as storage
            import core.seo_geo_growth as growth
            import backend.r8_13_seo_geo_patch as seo_patch
            importlib.reload(storage)
            importlib.reload(growth)
            importlib.reload(seo_patch)

            seeded = growth.ensure_baseline()
            assert seeded["questions"] == 50
            first = growth.dashboard()
            assert first["summary"]["keyword_total"] >= 10
            assert first["summary"]["public_pages"] == 0
            assert first["summary"]["submitted_urls"] == 0
            assert first["summary"]["indexed_urls"] == 0
            assert first["geo"]["mention_rate"] == 0
            assert "GENERATED ≠ PUBLISHED" in first["truth_rule"]

            planned = growth.plan_today(limit=3)
            assert planned["count"] == 3
            generated = growth.generate_staging(limit=3)
            assert generated["count"] == 3
            staged = growth.dashboard()
            assert staged["funnel"]["generated"] == 3
            assert staged["funnel"]["published"] == 0
            assert staged["technical"]["staging"]["robots_generated"] is True
            assert staged["technical"]["staging"]["sitemap_generated"] is True
            assert all(Path(x["staging_path"]).is_file() for x in staged["assets"] if x.get("staging_path"))

            enriched = seo_patch._dashboard_payload()
            evidence = enriched["evidence_summary"]
            assert evidence["asset_total"] == 3
            assert evidence["staged_files"] == 3
            assert evidence["canonical_files"] == 3
            assert evidence["schema_files"] == 3
            assert evidence["title_files"] == 3
            assert evidence["description_files"] == 3
            assert evidence["today_generated"] == 3
            assert enriched["geo"]["measurement_state"] == "not_started"
            assert "只代表本地证据" in evidence["truth"]

            asset_id = staged["assets"][0]["id"]
            try:
                growth.record_asset_stage(asset_id, "PUBLISHED", {})
            except ValueError as error:
                assert "公网URL" in str(error)
            else:
                raise AssertionError("PUBLISHED accepted without real public URL")

            published = growth.record_asset_stage(asset_id, "PUBLISHED", {"public_url": "https://kazuizhi.com/seo/test/"})
            assert published["stage"] == "PUBLISHED"
            assert published["public_url"].startswith("https://")

            try:
                growth.record_asset_stage(asset_id, "SUBMITTED", {"engine": "Bing"})
            except ValueError as error:
                assert "回执" in str(error)
            else:
                raise AssertionError("SUBMITTED accepted without receipt")

            submitted = growth.record_asset_stage(asset_id, "SUBMITTED", {"engine": "Bing", "receipt": "INDEXNOW-TEST-001"})
            assert submitted["stage"] == "SUBMITTED"

            data = growth._load()
            geo_question_id = data["geo_questions"][0]["id"]
            try:
                growth.record_geo_observation({"question_id": geo_question_id, "provider": "ChatGPT", "mentioned": True})
            except ValueError as error:
                assert "证据" in str(error)
            else:
                raise AssertionError("positive GEO result accepted without evidence")
            growth.record_geo_observation({
                "question_id": geo_question_id,
                "provider": "ChatGPT",
                "mentioned": False,
                "cited": False,
                "recommended": False,
                "evidence": "联网检索未发现品牌提及",
            })
            after_geo = growth.dashboard()
            assert after_geo["geo"]["tested_questions"] == 1
            assert after_geo["geo"]["mentioned"] == 0
            measured = seo_patch._dashboard_payload()
            assert measured["geo"]["measurement_state"] == "measured"

            ui = (SOURCE / "web" / "r8_13_seo_geo.html").read_text(encoding="utf-8")
            for token in ("SEO/GEO增长中心", "关键词机会池", "索引与收录漏斗", "GEO / AI 50问验证", "技术SEO健康检查", "内容与页面工厂", "今日自动作业流水线", "转化与归因", "今日增量", "累计真值", "本周公开页面目标", "性能测速"):
                assert token in ui
            assert "[object Object]" not in ui

            bridge = (SOURCE / "web" / "r8_13_seo_geo_bridge.js").read_text(encoding="utf-8")
            assert "SEO/GEO增长" in bridge
            assert "/r8_13_seo_geo.html?embed=1" in bridge
            startup = (SOURCE / "web" / "r8_12_startup_coordinator.js").read_text(encoding="utf-8")
            assert "/r8_13_seo_geo_bridge.js" in startup
            runpy = (SOURCE / "run.py").read_text(encoding="utf-8")
            assert "r8_13_seo_geo_patch" in runpy
            assert "r8_14_seo_geo_autonomy_patch" in runpy
            assert "run_seo_geo_autonomy" in runpy

            connectors = growth.connector_status()
            assert all(item["secret_exposed"] is False for item in connectors.values())
        finally:
            if previous is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = previous

    print("PASS: R8-13 truthful SEO/GEO growth center, daily-vs-total evidence summary, staging pipeline, evidence gates and owner UI verified.")


if __name__ == "__main__":
    main()
