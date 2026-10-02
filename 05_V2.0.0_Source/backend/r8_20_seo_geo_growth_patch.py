"""R8-20 SEO/GEO growth operating-loop HTTP and scheduler bridge."""
from __future__ import annotations

import json
from urllib.parse import parse_qs, urlsplit

from backend import server
from core import seo_geo_autonomy as seo_core
from core import seo_geo_source_tracking_patch as _seo_geo_source_tracking_patch  # noqa: F401
from core import seo_geo_growth_intelligence as growth

_INSTALLED = False
_ORIGINAL_RUN = seo_core.run_once
_ORIGINAL_STATUS = seo_core.status


def _origin_allowed(handler):
    origin = handler.headers.get("Origin")
    return not origin or origin in {
        f"http://127.0.0.1:{handler.server.server_port}",
        f"http://localhost:{handler.server.server_port}",
    }


def _read_json(handler):
    length = int(handler.headers.get("Content-Length", "0") or 0)
    if length < 0 or length > 256 * 1024:
        raise ValueError("请求内容过大")
    return json.loads(handler.rfile.read(length) or b"{}") if length else {}


def _days(handler):
    query = parse_qs(urlsplit(handler.path).query)
    try:
        value = int((query.get("days") or [30])[0])
    except (TypeError, ValueError):
        value = 30
    return value if value in {7, 30, 90} else 30


def _serve_operational_search(handler):
    web = server.get_web_path()
    names = ["operational-search.js", "geo-autonomy.js", "geo-phase3.js", "seo-geo-growth-intelligence.js"]
    source = "\n;\n".join((web / name).read_text(encoding="utf-8") for name in names)
    data = source.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/javascript; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _combined_status():
    value = _ORIGINAL_STATUS()
    result = dict(value) if isinstance(value, dict) else {"seo_geo": value}
    result["r8_20_growth"] = growth.status(30)
    return result


def _combined_run(force=False):
    value = _ORIGINAL_RUN(force=force)
    result = dict(value) if isinstance(value, dict) else {"seo_geo": value}
    result["r8_20_growth"] = growth.run_once(force=force)
    return result


def install():
    global _INSTALLED
    if _INSTALLED:
        return

    # Wrap the current R8-19 combined scheduler instead of creating a competing daemon.
    seo_core.run_once = _combined_run
    seo_core.status = _combined_status

    original_get = server.DashboardHandler.do_GET
    original_post = server.DashboardHandler.do_POST

    def do_get(handler):
        path = urlsplit(handler.path).path
        try:
            if path == "/operational-search.js":
                _serve_operational_search(handler)
                return
            if path == "/api/r8-20/seo-geo":
                handler._json_ok(growth.status(_days(handler)))
                return
            if path == "/api/r8-20/seo-geo/trends":
                handler._json_ok(growth.trends(_days(handler)))
                return
            if path == "/api/r8-20/seo-geo/governance":
                handler._json_ok({
                    "keyword": growth.keyword_governance(),
                    "internal_links": growth.internal_link_plan(),
                    "decay": growth.content_decay(),
                    "technical": growth.technical_seo_status(),
                    "sources": growth.third_party_source_gaps(),
                })
                return
            if path == "/api/r8-20/seo-geo/features":
                handler._json_ok({"count": 38, "items": growth.feature_registry()})
                return
        except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
            handler._json_error(400, error)
            return
        return original_get(handler)

    def do_post(handler):
        path = urlsplit(handler.path).path
        supported = {
            "/api/r8-20/seo-geo/refresh",
            "/api/r8-20/seo-geo/search-observation",
            "/api/r8-20/seo-geo/attribution",
            "/api/r8-20/seo-geo/dynamic-questions",
            "/api/r8-20/seo-geo/multi-ai",
            "/api/r8-20/seo-geo/fixed50-config",
            "/api/r8-20/seo-geo/fixed50-retest",
            "/api/r8-20/seo-geo/web-vitals",
            "/api/r8-20/seo-geo/connector-health",
            "/api/r8-20/seo-geo/internal-links",
            "/api/r8-20/seo-geo/refresh-content",
            "/api/r8-20/seo-geo/backup",
            "/api/r8-20/seo-geo/restore",
        }
        if path not in supported:
            return original_post(handler)
        if not _origin_allowed(handler):
            handler._json_error(403, "Cross-origin changes are not allowed")
            return
        try:
            payload = _read_json(handler)
            if path == "/api/r8-20/seo-geo/refresh":
                result = growth.run_once(force=bool(payload.get("force", True)))
            elif path == "/api/r8-20/seo-geo/search-observation":
                result = growth.record_search_observation(payload)
            elif path == "/api/r8-20/seo-geo/attribution":
                result = growth.record_attribution(payload)
            elif path == "/api/r8-20/seo-geo/dynamic-questions":
                result = growth.discover_dynamic_questions(payload.get("candidates") or [], source=payload.get("source") or "owner_or_controller", evidence=payload.get("evidence") or "")
            elif path == "/api/r8-20/seo-geo/multi-ai":
                result = growth.schedule_multi_provider_validation(payload.get("providers") or [], limit=payload.get("limit") or 3, include_dynamic=bool(payload.get("include_dynamic", True)))
            elif path == "/api/r8-20/seo-geo/fixed50-config":
                result = growth.configure_fixed50_schedule(bool(payload.get("enabled")))
            elif path == "/api/r8-20/seo-geo/fixed50-retest":
                result = growth.schedule_fixed50_retest(provider=payload.get("provider") or "browser_external_ai", limit=payload.get("limit") or 50)
            elif path == "/api/r8-20/seo-geo/web-vitals":
                result = growth.ingest_web_vitals(payload)
            elif path == "/api/r8-20/seo-geo/connector-health":
                result = growth.record_connector_health(payload.get("name"), bool(payload.get("ok")), payload.get("detail") or "")
            elif path == "/api/r8-20/seo-geo/internal-links":
                result = growth.apply_internal_links(limit=payload.get("limit") or 20)
            elif path == "/api/r8-20/seo-geo/refresh-content":
                result = growth.queue_refresh_jobs(limit=payload.get("limit") or 10)
            elif path == "/api/r8-20/seo-geo/backup":
                result = growth.create_backup(payload.get("label") or "owner")
            else:
                result = growth.restore_backup(payload.get("backup_id"), confirm=bool(payload.get("confirm")))
            handler._json_ok({"result": result, "growth": growth.status(int(payload.get("days") or 30))})
        except (OSError, ValueError, RuntimeError, PermissionError, TypeError, KeyError, json.JSONDecodeError) as error:
            handler._json_error(400, error)

    server.DashboardHandler.do_GET = do_get
    server.DashboardHandler.do_POST = do_post
    server.DashboardHandler._kz_r8_20_seo_geo_growth = True
    _INSTALLED = True


install()
