from __future__ import annotations

import base64
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))
TEST_TEMP = ROOT / "build-temp" / "r8-32-tests"
TEST_TEMP.mkdir(parents=True, exist_ok=True)
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="kz-r832-", dir=TEST_TEMP)

from core.seo_campaign_intake import import_campaign  # noqa: E402
from core.seo_geo_autonomy import _local_qc_generated_assets  # noqa: E402
from core.seo_geo_growth import dashboard  # noqa: E402
from integrations import seo_public_deployer as deployer  # noqa: E402


PNG_1X1 = base64.b64encode(
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01\x08\x06\x00\x00\x00\x1f\x15\xc4\x89"
).decode("ascii")


def main():
    payload = {
        "campaign_id": "FIRST-LIANSHUI-REPAIR-20261015",
        "region": "涟水县",
        "service": "水电安装维修",
        "keyword": "涟水水电维修",
        "title": "涟水水电维修发布指南",
        "summary": "真实说明需求发布、报价确认与小程序入口。",
        "content": "## 服务说明\n- 先描述故障\n- 再确认报价\n\n不虚构价格、案例或排名。",
        "image_name": "repair.png",
        "image_mime": "image/png",
        "image_base64": PNG_1X1,
        "rights_confirmed": True,
    }
    created = import_campaign(payload)
    assert created["created"] is True, created
    asset = created["asset"]
    assert asset["stage"] == "GENERATED", asset
    assert len(asset["staging_attachments"]) == 1, asset
    page = Path(asset["staging_path"])
    body = page.read_text(encoding="utf-8")
    assert "data-kz-role=\"campaign-content\"" in body
    assert "./media/repair.png" in body
    assert "打开卡嘴子小程序" in body
    assert Path(asset["staging_attachments"][0]["path"]).is_file()

    repeated = import_campaign(payload)
    assert repeated["created"] is False and repeated["idempotent"] is True, repeated
    matching = [row for row in dashboard()["assets"] if row.get("campaign_id") == payload["campaign_id"]]
    assert len(matching) == 1, matching

    qc = _local_qc_generated_assets(limit=5)
    assert asset["id"] in qc["passed"], qc

    site_root = Path(tempfile.mkdtemp(prefix="kz-r832-site-", dir=TEST_TEMP)) / "site"
    site_root.mkdir(parents=True)
    deployer.configure({"enabled": True, "site_root": str(site_root), "public_base_url": "https://example.test/"})
    original_page_verify = deployer._verify_public_url
    original_media_verify = deployer._verify_public_attachment
    deployer._verify_public_url = lambda *args, **kwargs: {
        "ok": True, "status": 200, "content_match": True, "canonical_match": True,
        "schema_valid": True, "schema_urls_valid": True, "page_indexable": True,
        "source_tracking_present": True, "visible_text_chars": 800,
        "robots": {"allowed": True}, "checked_at": "test",
    }
    deployer._verify_public_attachment = lambda *args, **kwargs: {
        "ok": True, "status": 200, "content_type": "image/png", "checked_at": "test"
    }
    try:
        deployed = deployer.deploy_pending(limit=5)
    finally:
        deployer._verify_public_url = original_page_verify
        deployer._verify_public_attachment = original_media_verify
    assert len(deployed["published"]) == 1, deployed
    copied = site_root / "seo" / asset["slug"] / "media" / "repair.png"
    assert copied.is_file(), copied
    final = next(row for row in dashboard()["assets"] if row["id"] == asset["id"])
    assert final["stage"] == "PUBLISHED" and final["public_url"], final

    backend_source = (SOURCE / "backend" / "r8_13_seo_geo_patch.py").read_text(encoding="utf-8")
    ui_source = (SOURCE / "web" / "seo-campaign-intake.js").read_text(encoding="utf-8")
    assert "/api/r8-13/seo-geo/campaign/import" in backend_source
    assert "owner_approved" in backend_source and "seo_autonomy.run_once" in backend_source
    assert "导入并运行完整链路" in ui_source and "rights_confirmed" in ui_source
    print("R8-32 campaign intake -> QC -> verified public deployment wiring checks passed")


if __name__ == "__main__":
    main()
