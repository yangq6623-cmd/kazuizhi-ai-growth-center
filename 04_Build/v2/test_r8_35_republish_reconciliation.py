"""Release gate for stale-ledger verified republish reconciliation."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))


def main():
    previous = os.environ.get("LOCALAPPDATA")
    with tempfile.TemporaryDirectory(prefix=".kz-r835-", dir=ROOT) as temp:
        os.environ["LOCALAPPDATA"] = temp
        try:
            from core import seo_geo_growth as growth
            from integrations import r8_17_remote_deployer_patch as remote_patch
            from integrations import remote_agent
            from integrations import seo_public_deployer as deployer

            source = Path(temp) / "index.html"
            source.write_text("<html><title>卡嘴子测试页</title></html>", encoding="utf-8")
            asset = {
                "id": "SEO-R835",
                "slug": "r835-test",
                "title": "卡嘴子测试页",
                "canonical": "https://kazuizhi.com/seo/r835-test/",
                "staging_path": str(source),
                "stage": "SUBMITTED",
                "republish_pending": True,
                "public_template_version": "R8-26-rich-v1",
                "growth_action_id": "GEO-GROWTH-R835",
                "content_revision_id": "GEO-GROWTH-R835",
            }
            receipts = []
            republished = []

            names = [
                (remote_patch, "_remote_mode"),
                (remote_patch, "status"),
                (remote_patch, "_public_text"),
                (remote_patch, "_ensure_root_discovery"),
                (deployer, "_load"),
                (deployer, "_save"),
                (deployer, "dashboard"),
                (deployer, "publication_scope_allowed"),
                (deployer, "_asset_attachments"),
                (deployer, "_verify_public_url"),
                (deployer, "_append_receipt"),
                (deployer, "record_asset_stage"),
                (growth, "record_asset_republished"),
                (remote_agent, "upload_file"),
                (remote_agent, "upload_bytes"),
            ]
            originals = {(id(obj), name): getattr(obj, name) for obj, name in names}
            try:
                remote_patch._remote_mode = lambda: True
                remote_patch.status = lambda: {"ready": True, "mode": remote_patch.REMOTE_MODE}
                remote_patch._public_text = lambda url, timeout: {
                    "ok": True,
                    "status": 200,
                    "body": b'<link rel="canonical"> application/ld+json ' + (b"x" * 1800),
                }
                remote_patch._ensure_root_discovery = lambda base, timeout: {"ok": True}
                deployer._load = lambda: {
                    "public_base_url": "https://kazuizhi.com/",
                    "verify_http": True,
                    "verify_timeout_seconds": 8,
                }
                deployer._save = lambda data: data
                deployer.dashboard = lambda: {"assets": [asset]}
                deployer.publication_scope_allowed = lambda row: True
                deployer._asset_attachments = lambda row, path: []

                def verify(url, expected_title, expected_canonical, timeout):
                    return {
                        "ok": True,
                        "status": 200,
                        "content_match": True,
                        "canonical": expected_canonical,
                        "canonical_match": True,
                        "schema_valid": True,
                        "schema_urls_valid": True,
                        "page_indexable": True,
                        "source_tracking_present": True,
                        "template_version": growth.PUBLIC_TEMPLATE_VERSION,
                        "mini_program_entry_present": True,
                        "mini_program_image_present": True,
                        "professional_hero_image_present": False,
                    }

                deployer._verify_public_url = verify
                deployer._append_receipt = lambda receipt: receipts.append(receipt)
                deployer.record_asset_stage = lambda *args, **kwargs: (_ for _ in ()).throw(AssertionError("republish downgraded external truth"))
                growth.record_asset_republished = lambda asset_id, evidence: republished.append((asset_id, evidence)) or asset
                remote_agent.upload_file = lambda *args, **kwargs: {"job_id": "REMOTE-R835", "sha256": "a" * 64}
                remote_agent.upload_bytes = lambda *args, **kwargs: {"job_id": "REMOTE-R835-AUX", "sha256": "b" * 64}

                result = remote_patch.deploy_pending(limit=1)
                assert result["attempted"] == 1 and len(result["published"]) == 1, result
                assert not result["failed"], result
                assert result["published"][0]["republished"] is True, result
                assert republished and republished[0][0] == asset["id"], republished
                verification = receipts[0]["verification"]
                assert verification["expected_template_version"] == growth.PUBLIC_TEMPLATE_VERSION, verification
                assert verification["conversion_contract_ok"] is True, verification
                assert receipts[0]["growth_action_id"] == "GEO-GROWTH-R835", receipts[0]
                assert republished[0][1]["content_revision_id"] == "GEO-GROWTH-R835", republished[0]
            finally:
                for obj, name in names:
                    setattr(obj, name, originals[(id(obj), name)])
        finally:
            if previous is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = previous

    print("PASS: stale template ledger reconciles through verified republish without stage downgrade")


if __name__ == "__main__":
    main()
