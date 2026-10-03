from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))

os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="kz-r815-")

from core.seo_geo_growth import dashboard, ensure_baseline, generate_staging, plan_today, record_asset_stage  # noqa: E402
from integrations import seo_public_deployer as deployer  # noqa: E402


def main():
    ensure_baseline()
    plan_today(limit=1)
    generated = generate_staging(limit=1)
    assert generated["count"] == 1, generated
    asset = next(x for x in dashboard()["assets"] if x["stage"] == "GENERATED")

    # The generated public page itself must already contain the technical SEO
    # elements R8-15 later verifies on the real public URL.
    staged_html = Path(asset["staging_path"]).read_text(encoding="utf-8")
    inspected = deployer._inspect_public_html(staged_html, asset["title"], asset["canonical"])
    assert inspected["content_match"] is True, inspected
    assert inspected["canonical_match"] is True, inspected
    assert inspected["schema_valid"] is True, inspected
    assert inspected["page_indexable"] is True, inspected

    broken_canonical = staged_html.replace(asset["canonical"], "https://wrong.example/", 1)
    broken = deployer._inspect_public_html(broken_canonical, asset["title"], asset["canonical"])
    assert broken["canonical_match"] is False, broken

    noindex_html = staged_html.replace("</head>", '<meta name="robots" content="noindex"></head>')
    noindex = deployer._inspect_public_html(noindex_html, asset["title"], asset["canonical"])
    assert noindex["page_indexable"] is False, noindex

    record_asset_stage(asset["id"], "QC_PASSED", {"local_qc": "test"})

    site_root = Path(tempfile.mkdtemp(prefix="kz-r815-site-")) / "kazuizhi-site"
    site_root.mkdir(parents=True)
    protected = site_root / "Web.config"
    protected.write_text("DO-NOT-TOUCH", encoding="utf-8")
    app_data = site_root / "App_Data"
    app_data.mkdir()
    marker = app_data / "db-marker.txt"
    marker.write_text("KEEP", encoding="utf-8")

    state = deployer.configure({
        "enabled": True,
        "site_root": str(site_root),
        "public_base_url": "https://kazuizhi.example/",
    })
    assert state["ready"] is True, state
    assert state["safety"]["writes_only_below"] == "<site_root>/seo/"
    assert state["safety"]["touches_web_config"] is False
    assert state["safety"]["touches_database"] is False
    assert state["safety"]["canonical_verification_required"] is True
    assert state["safety"]["schema_verification_required"] is True
    assert state["safety"]["robots_verification_required"] is True

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
    public = result["published"][0]
    assert public["public_url"].startswith("https://kazuizhi.example/seo/")
    deployed = list((site_root / "seo").glob("*/index.html"))
    assert len(deployed) == 1, deployed
    assert (site_root / "seo" / "sitemap.xml").is_file()
    assert protected.read_text(encoding="utf-8") == "DO-NOT-TOUCH"
    assert marker.read_text(encoding="utf-8") == "KEEP"

    published_asset = next(x for x in dashboard()["assets"] if x["id"] == asset["id"])
    assert published_asset["stage"] == "PUBLISHED"
    assert published_asset["public_url"] == public["public_url"]

    # Truth gate: a failed public verification must not mark the next page PUBLISHED.
    plan_today(limit=1)
    generate_staging(limit=1)
    second = next(x for x in dashboard()["assets"] if x["stage"] == "GENERATED")
    record_asset_stage(second["id"], "QC_PASSED", {"local_qc": "test"})
    deployer._verify_public_url = lambda url, expected, expected_canonical, timeout: {
        "ok": False,
        "status": 200,
        "content_match": True,
        "canonical_match": False,
        "schema_valid": True,
        "page_indexable": True,
        "robots": {"allowed": True},
        "checked_at": "test",
    }
    try:
        failed = deployer.deploy_pending(limit=5)
    finally:
        deployer._verify_public_url = original_verify
    assert failed["failed"], failed
    second_after = next(x for x in dashboard()["assets"] if x["id"] == second["id"])
    assert second_after["stage"] == "QC_PASSED", second_after

    print("R8-15 guarded public deployment truth/safety/SEO verification checks passed")


if __name__ == "__main__":
    main()
