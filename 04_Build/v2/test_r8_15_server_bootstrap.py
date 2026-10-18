from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))

from core import r8_15_server_bootstrap as bootstrap  # noqa: E402


def main():
    original_public = bootstrap.configure_public_deploy
    original_autonomy_config = bootstrap.configure_autonomy
    original_run = bootstrap.run_seo_geo_autonomy

    calls = {"run": 0}

    try:
        bootstrap.configure_public_deploy = lambda payload: {
            "ready": True,
            "enabled": True,
            "site_root": payload["site_root"],
            "public_base_url": payload["public_base_url"],
            "safety": {"writes_only_below": "<site_root>/seo/"},
        }
        bootstrap.configure_autonomy = lambda payload: {
            "enabled": payload["enabled"],
            "mode": payload["mode"],
        }

        def successful_cycle(force=False):
            calls["run"] += 1
            assert force is True
            return {
                "public_deploy": {
                    "skipped": False,
                    "published": [
                        {
                            "asset_id": "SEO-TEST-1",
                            "public_url": "https://kazuizhi.com/seo/lianshui-water-repair/",
                            "receipt": "DEPLOY-SEO-TEST-1",
                        }
                    ],
                    "failed": [],
                    "managed_sitemap": r"C:\inetpub\kazuizhi\seo\sitemap.xml",
                }
            }

        bootstrap.run_seo_geo_autonomy = successful_cycle
        ok = bootstrap.execute()
        assert ok["exit_code"] == 0, ok
        assert ok["published_count"] == 1, ok
        assert ok["failed_count"] == 0, ok
        assert ok["published"][0]["public_url"].startswith("https://kazuizhi.com/seo/"), ok
        assert ok["site_root"] == bootstrap.DEFAULT_SITE_ROOT
        assert calls["run"] == 1

        bootstrap.configure_public_deploy = lambda payload: {
            "ready": False,
            "enabled": True,
            "reason": "site_root_not_writable",
        }
        before = calls["run"]
        not_ready = bootstrap.execute()
        assert not_ready["exit_code"] == 3, not_ready
        assert calls["run"] == before, "autonomy must not run when connector is not ready"

        bootstrap.configure_public_deploy = lambda payload: {"ready": True, "enabled": True}
        bootstrap.run_seo_geo_autonomy = lambda force=False: {
            "public_deploy": {
                "skipped": False,
                "published": [],
                "failed": [
                    {
                        "asset_id": "SEO-TEST-2",
                        "reason": "public_http_verification_failed",
                        "public_url": "https://kazuizhi.com/seo/failure-test/",
                    }
                ],
            }
        }
        failed = bootstrap.execute()
        assert failed["exit_code"] == 4, failed
        assert failed["failed_count"] == 1, failed

        bootstrap.run_seo_geo_autonomy = lambda force=False: {
            "public_deploy": {"skipped": True, "reason": "connector_not_ready", "published": [], "failed": []}
        }
        skipped = bootstrap.execute()
        assert skipped["exit_code"] == 5, skipped

        print("R8-15 server bootstrap field-bridge checks passed")
    finally:
        bootstrap.configure_public_deploy = original_public
        bootstrap.configure_autonomy = original_autonomy_config
        bootstrap.run_seo_geo_autonomy = original_run


if __name__ == "__main__":
    main()
