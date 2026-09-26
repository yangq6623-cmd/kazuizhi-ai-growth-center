"""R8-13/R8-16 SEO/GEO growth HTTP bridge."""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from urllib.parse import urlsplit

from backend import server
from core.seo_geo_growth import (
    configure,
    dashboard,
    ensure_baseline,
    generate_staging,
    plan_today,
    record_asset_stage,
    record_geo_observation,
    run_daily_cycle,
    technical_snapshot,
)
from integrations.search_engine_submitter import status as search_submit_status
from integrations import seo_public_deployer
from promotion.search_growth import audit as audit_search_site, status as search_growth_status

_INSTALLED = False


def _optional_status(label, reader, fallback):
    """Read a non-essential connector without taking the SEO screen offline.

    The desktop dashboard must still be usable when a locally stored account,
    a deployment path, or an optional connector cannot be read during startup.
    A connector's transient failure is shown as its own pending state rather
    than aborting the single dashboard request and making the browser report
    the unhelpful ``Failed to fetch`` message.
    """
    try:
        result = reader()
        return result if isinstance(result, dict) else dict(fallback)
    except Exception as error:  # HTTP boundary: optional status must not break the page.
        result = dict(fallback)
        result["status"] = "unavailable"
        result["reason"] = f"{label}暂时不可用：{type(error).__name__}"
        return result


def _connector_fallback():
    return {
        "connectors": {
            "baidu": {
                "label": "百度搜索资源平台", "configured": False, "ready": False,
                "mode": "普通收录 API", "requires_owner": True,
                "reason": "连接状态正在重新读取，请稍后刷新。",
            },
            "bing": {
                "label": "Bing / IndexNow", "configured": False, "ready": False,
                "mode": "IndexNow", "requires_owner": False,
                "reason": "连接状态正在重新读取，请稍后刷新。",
            },
            "google": {
                "label": "Google Search Console", "configured": False, "ready": False,
                "mode": "Search Console Sitemap API", "requires_owner": True,
                "reason": "连接状态正在重新读取，请稍后刷新。",
            },
        },
        "ready_engines": [],
        "truth": "连接器状态暂不可用；不会影响本地 SEO/GEO 数据和页面查看。",
    }


def _origin_allowed(handler):
    origin = handler.headers.get("Origin")
    allowed = {
        f"http://127.0.0.1:{handler.server.server_port}",
        f"http://localhost:{handler.server.server_port}",
    }
    return not origin or origin in allowed


def _read_json_body(handler):
    length = int(handler.headers.get("Content-Length", "0") or 0)
    if length < 0 or length > 512 * 1024:
        raise ValueError("请求内容过大")
    if not length:
        return {}
    return json.loads(handler.rfile.read(length) or b"{}")


def _staging_evidence(payload):
    """Derive owner-facing local evidence without claiming public success."""
    assets = list(payload.get("assets") or [])
    today = datetime.now().astimezone().date().isoformat()
    generated_today = 0
    qc_today = 0
    published_today = 0
    staged_files = 0
    canonical_files = 0
    schema_files = 0
    title_files = 0
    description_files = 0

    for asset in assets:
        if str(asset.get("generated_at") or "").startswith(today):
            generated_today += 1
        if str(asset.get("qc_passed_at") or "").startswith(today):
            qc_today += 1
        if str(asset.get("published_at") or "").startswith(today):
            published_today += 1
        path = Path(str(asset.get("staging_path") or ""))
        if not path.is_file():
            continue
        staged_files += 1
        try:
            html = path.read_text(encoding="utf-8", errors="replace")[:1024 * 1024]
        except OSError:
            continue
        lower = html.lower()
        if "rel=\"canonical\"" in lower or "rel='canonical'" in lower:
            canonical_files += 1
        if "application/ld+json" in lower:
            schema_files += 1
        if "<title>" in lower and "</title>" in lower:
            title_files += 1
        if "name=\"description\"" in lower or "name='description'" in lower:
            description_files += 1

    qc_total = sum(1 for asset in assets if str(asset.get("stage") or "") in {
        "QC_PASSED", "PUBLISHED", "SUBMITTED", "CRAWLED", "INDEXED", "RANKED", "MENTIONED", "CITED", "CONVERTED"
    })
    return {
        "today_generated": generated_today,
        "today_qc_passed": qc_today,
        "today_published": published_today,
        "asset_total": len(assets),
        "qc_passed_total": qc_total,
        "staged_files": staged_files,
        "canonical_files": canonical_files,
        "schema_files": schema_files,
        "title_files": title_files,
        "description_files": description_files,
        "truth": "本地文件、Title、Description、Canonical、Schema 只代表本地证据；公网状态仍必须由真实URL验证。",
    }


def _dashboard_payload():
    payload = dashboard()
    technical = payload.setdefault("technical", {})
    # Keep the independent website audit and the deployment connector separate.
    # The former is a current homepage/robots/sitemap observation; the latter
    # owns the historical per-page verification receipt required for PUBLISHED.
    technical["public_site"] = _optional_status(
        "官网探测状态", search_growth_status,
        {"status": "unavailable", "latest_audit": None, "packs": []},
    )
    technical["public_deploy"] = _optional_status(
        "公网部署状态", seo_public_deployer.status,
        {"configured": False, "enabled": False, "ready": False,
         "reason": "公网部署状态正在重新读取。"},
    )
    search = _optional_status("搜索连接器状态", search_submit_status, _connector_fallback())
    technical["connectors"] = deepcopy_connectors = search.get("connectors") or {}
    payload["search_submit"] = search
    payload["evidence_summary"] = _staging_evidence(payload)
    geo = payload.setdefault("geo", {})
    geo["measurement_state"] = "measured" if int(geo.get("observations") or 0) > 0 else "not_started"
    return payload


def install():
    global _INSTALLED
    if _INSTALLED:
        return
    ensure_baseline()
    original_get = server.DashboardHandler.do_GET
    original_post = server.DashboardHandler.do_POST

    def do_get(handler):
        path = urlsplit(handler.path).path
        try:
            if path == "/api/r8-13/seo-geo":
                handler._json_ok(_dashboard_payload())
                return
            if path == "/api/r8-13/seo-geo/technical":
                result = technical_snapshot()
                result["public_site"] = search_growth_status()
                result["public_deploy"] = seo_public_deployer.status()
                result["connectors"] = (search_submit_status().get("connectors") or {})
                handler._json_ok(result)
                return
        except Exception as error:  # Never close the local HTTP connection without JSON.
            handler._json_error(503, f"SEO/GEO 状态暂时不可用：{type(error).__name__}")
            return
        return original_get(handler)

    def do_post(handler):
        path = urlsplit(handler.path).path
        allowed = {
            "/api/r8-13/seo-geo/config",
            "/api/r8-13/seo-geo/plan",
            "/api/r8-13/seo-geo/generate",
            "/api/r8-13/seo-geo/run",
            "/api/r8-13/seo-geo/audit-site",
            "/api/r8-13/seo-geo/asset-stage",
            "/api/r8-13/seo-geo/geo-observation",
        }
        if path not in allowed:
            return original_post(handler)
        if not _origin_allowed(handler):
            handler._json_error(403, "Cross-origin changes are not allowed")
            return
        try:
            payload = _read_json_body(handler)
            if path == "/api/r8-13/seo-geo/config":
                handler._json_ok({"config": configure(payload), "dashboard": _dashboard_payload()})
                return
            if path == "/api/r8-13/seo-geo/plan":
                handler._json_ok({"result": plan_today(payload.get("limit")), "dashboard": _dashboard_payload()})
                return
            if path == "/api/r8-13/seo-geo/generate":
                handler._json_ok({"result": generate_staging(payload.get("limit") or 6), "dashboard": _dashboard_payload()})
                return
            if path == "/api/r8-13/seo-geo/run":
                handler._json_ok({"result": run_daily_cycle(force=bool(payload.get("force"))), "dashboard": _dashboard_payload()})
                return
            if path == "/api/r8-13/seo-geo/audit-site":
                site = str(payload.get("site") or dashboard().get("config", {}).get("site_base_url") or "").strip()
                result = audit_search_site({"site": site})
                handler._json_ok({"audit": result, "dashboard": _dashboard_payload()})
                return
            if path == "/api/r8-13/seo-geo/asset-stage":
                asset_id = str(payload.get("asset_id") or "").strip()
                stage = str(payload.get("stage") or "").strip()
                if not asset_id or not stage:
                    raise ValueError("asset_id 和 stage 不能为空")
                evidence = payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {}
                handler._json_ok({"asset": record_asset_stage(asset_id, stage, evidence), "dashboard": _dashboard_payload()})
                return
            if path == "/api/r8-13/seo-geo/geo-observation":
                handler._json_ok({"observation": record_geo_observation(payload), "dashboard": _dashboard_payload()})
                return
        except (OSError, ValueError, RuntimeError, TypeError, KeyError, json.JSONDecodeError) as error:
            handler._json_error(400, error)

    server.DashboardHandler.do_GET = do_get
    server.DashboardHandler.do_POST = do_post
    server.DashboardHandler._kz_r8_13_seo_geo = True
    _INSTALLED = True


install()
