"""Regression gate for the R8-17 direct static-file IIS fallback."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    with tempfile.TemporaryDirectory(prefix="kz-r817-flat-") as temp:
        previous_local = os.environ.get("LOCALAPPDATA")
        previous_profile = os.environ.get("USERPROFILE")
        os.environ["LOCALAPPDATA"] = temp
        os.environ["USERPROFILE"] = temp
        try:
            from integrations import r8_17_remote_deployer_patch as remote_patch
            from integrations import r8_17_direct_file_fallback as fallback
            from integrations import remote_agent
            from integrations import seo_public_deployer as deployer

            old_url = "https://kazuizhi.com/seo/test-slug/"
            flat_url = "https://kazuizhi.com/seo/test-slug.html"
            source = Path(temp) / "index.html"
            source.write_text(
                '<html><head><link rel="canonical" href="' + old_url + '">'
                '<script type="application/ld+json">{"url":"' + old_url + '"}</script>'
                '</head><body><h1>测试标题</h1></body></html>',
                encoding="utf-8",
            )
            rewritten = fallback._rewrite_canonical(source, old_url, flat_url).decode("utf-8")
            require(old_url not in rewritten, "old directory canonical remained in flat fallback")
            require(rewritten.count(flat_url) == 2, "flat canonical was not rewritten everywhere")

            asset = {
                "id": "SEO-TEST",
                "slug": "test-slug",
                "staging_path": str(source),
                "canonical": old_url,
                "title": "测试标题",
                "stage": "QC_PASSED",
            }
            uploads = []
            verifies = []
            recorded = []
            receipts = []
            saved = []

            original_pending = fallback._ORIGINAL_DEPLOY_PENDING
            original_status = deployer.status
            original_dashboard = deployer.dashboard
            original_verify = deployer._verify_public_url
            original_record = deployer.record_asset_stage
            original_append = deployer._append_receipt
            original_load = deployer._load
            original_save = deployer._save
            original_upload = remote_agent.upload_bytes
            try:
                fallback._ORIGINAL_DEPLOY_PENDING = lambda limit=10: {
                    "skipped": False,
                    "attempted": 1,
                    "published": [],
                    "failed": [{
                        "asset_id": "SEO-TEST",
                        "reason": "public_http_verification_failed",
                        "public_url": old_url,
                        "verification": {"ok": False, "status": 404},
                    }],
                }
                deployer.status = lambda: {
                    "ready": True,
                    "mode": remote_patch.REMOTE_MODE,
                    "public_base_url": "https://kazuizhi.com/",
                }
                deployer.dashboard = lambda: {"assets": [asset]}
                deployer._load = lambda: {"verify_timeout_seconds": 8}
                deployer._save = lambda data: saved.append(dict(data)) or data

                def fake_upload(relative_path, content, *, job_id=""):
                    text = bytes(content).decode("utf-8")
                    uploads.append((relative_path, text, job_id))
                    return {"ok": True, "job_id": job_id, "sha256": "b" * 64}

                remote_agent.upload_bytes = fake_upload

                def fake_verify(url, expected, expected_canonical, timeout):
                    verifies.append((url, expected, expected_canonical, timeout))
                    return {
                        "ok": True,
                        "status": 200,
                        "content_match": True,
                        "canonical": expected_canonical,
                        "canonical_match": True,
                        "schema_valid": True,
                        "page_indexable": True,
                        "robots": {"allowed": True},
                    }

                deployer._verify_public_url = fake_verify
                deployer.record_asset_stage = lambda asset_id, stage, payload: recorded.append((asset_id, stage, payload)) or asset
                deployer._append_receipt = lambda receipt: receipts.append(receipt)

                result = fallback.deploy_pending(limit=10)
                require(len(result.get("published") or []) == 1, "flat fallback did not publish verified asset")
                require(not result.get("failed"), "verified flat fallback remained failed")
                require(uploads and uploads[0][0] == "seo/test-slug.html", "flat fallback path is wrong")
                require(flat_url in uploads[0][1], "flat fallback payload has wrong canonical")
                require(verifies and verifies[0][0] == flat_url, "flat fallback verified wrong public URL")
                require(verifies[0][2] == flat_url, "flat fallback expected canonical is wrong")
                require(recorded and recorded[0][1] == "PUBLISHED", "truth ledger did not advance after verified flat URL")
                require(recorded[0][2]["public_url"] == flat_url, "truth ledger stored wrong public URL")
                require(receipts and receipts[0]["strategy"] == "direct_html_file", "fallback receipt strategy missing")
                require(saved and saved[-1]["last_result"]["published"], "fallback result was not persisted")
            finally:
                fallback._ORIGINAL_DEPLOY_PENDING = original_pending
                deployer.status = original_status
                deployer.dashboard = original_dashboard
                deployer._verify_public_url = original_verify
                deployer.record_asset_stage = original_record
                deployer._append_receipt = original_append
                deployer._load = original_load
                deployer._save = original_save
                remote_agent.upload_bytes = original_upload

            print("R8-17 direct static HTML fallback regression: PASS")
        finally:
            if previous_local is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = previous_local
            if previous_profile is None:
                os.environ.pop("USERPROFILE", None)
            else:
                os.environ["USERPROFILE"] = previous_profile


if __name__ == "__main__":
    main()
