"""R8-15 one-click Windows Server bootstrap for guarded SEO/GEO public deployment.

This module is intentionally server-local. It never accepts or stores a server
password. It enables the existing guarded IIS filesystem connector, drives the
R8-14/R8-15 SEO autonomy loop once, and returns a machine-readable field report.
"""
from __future__ import annotations

from copy import deepcopy

from core.seo_geo_autonomy import configure as configure_autonomy
from core.seo_geo_autonomy import run_once as run_seo_geo_autonomy
from integrations.seo_public_deployer import configure as configure_public_deploy

SCHEMA = "kz.r8-15-server-bootstrap.v1"
DEFAULT_SITE_ROOT = r"C:\inetpub\kazuizhi"
DEFAULT_PUBLIC_BASE_URL = "https://kazuizhi.com/"


def _report(exit_code: int, **payload) -> dict:
    report = {
        "schema": SCHEMA,
        "exit_code": int(exit_code),
        "truth": (
            "服务器文件写入不等于发布成功；只有真实公网URL通过HTTP、内容、canonical、"
            "Schema与robots/indexability验证后才允许记录PUBLISHED。"
        ),
    }
    report.update(deepcopy(payload))
    return report


def execute(
    site_root: str = DEFAULT_SITE_ROOT,
    public_base_url: str = DEFAULT_PUBLIC_BASE_URL,
) -> dict:
    """Run one guarded server-local SEO deployment cycle and return a field report.

    Exit codes:
    0 = connector ready and cycle completed without publish verification failures
    2 = invalid/bootstrap configuration error
    3 = connector not ready on this server
    4 = at least one real public URL failed verification
    5 = autonomous cycle did not reach the public deployment stage
    """
    try:
        connector = configure_public_deploy({
            "enabled": True,
            "site_root": site_root,
            "public_base_url": public_base_url,
            "verify_http": True,
        })
        autonomy = configure_autonomy({"enabled": True, "mode": "autonomous"})
    except (OSError, ValueError, RuntimeError) as error:
        return _report(
            2,
            site_root=str(site_root),
            public_base_url=str(public_base_url),
            error=str(error),
        )

    if not connector.get("ready"):
        return _report(
            3,
            site_root=str(site_root),
            public_base_url=str(public_base_url),
            connector=connector,
            autonomy=autonomy,
            reason=connector.get("reason") or "deploy_connector_not_ready",
        )

    try:
        cycle = run_seo_geo_autonomy(force=True)
    except (OSError, ValueError, RuntimeError) as error:
        return _report(
            5,
            site_root=str(site_root),
            public_base_url=str(public_base_url),
            connector=connector,
            autonomy=autonomy,
            error=str(error),
        )

    public_deploy = deepcopy(cycle.get("public_deploy") or {})
    published = deepcopy(public_deploy.get("published") or [])
    failed = deepcopy(public_deploy.get("failed") or [])

    if public_deploy.get("skipped"):
        return _report(
            5,
            site_root=str(site_root),
            public_base_url=str(public_base_url),
            connector=connector,
            autonomy=autonomy,
            public_deploy=public_deploy,
            published=published,
            failed=failed,
            reason=public_deploy.get("reason") or "public_deploy_skipped",
        )

    exit_code = 4 if failed else 0
    return _report(
        exit_code,
        site_root=str(site_root),
        public_base_url=str(public_base_url),
        connector=connector,
        autonomy=autonomy,
        public_deploy=public_deploy,
        published=published,
        published_count=len(published),
        failed=failed,
        failed_count=len(failed),
        managed_sitemap=public_deploy.get("managed_sitemap") or "",
        note=(
            "R8-15 server bootstrap only manages <site_root>/seo/. Root Web.config, App_Data, "
            "SQL, APK and uploads are outside its write scope."
        ),
    )
