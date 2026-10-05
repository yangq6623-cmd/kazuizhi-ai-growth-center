"""R8-20/R8-21 SEO/GEO growth operating-loop HTTP and scheduler bridge.

R8-24 extends the same scheduler with the GEO Growth OS. C-level Doubao/API
signals may drive low-risk operating work, while formal A/B truth remains
unchanged and independently evidence-gated.
"""
from __future__ import annotations

import json
from urllib.parse import parse_qs, urlsplit

from backend import server
from core import runtime_resilience
from core import seo_geo_autonomy as seo_core
from core import seo_geo_source_tracking_patch as _seo_geo_source_tracking_patch  # noqa: F401
from core import seo_geo_growth_intelligence as growth
from core import r8_20_growth_truth_patch as _r8_20_growth_truth_patch  # noqa: F401
from core import geo_growth_orchestrator as geo_growth
from integrations import seo_geo_connector_router_v2 as connector_router

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
    names = [
        "operational-search.js",
        "geo-autonomy.js",
        "geo-phase3.js",
        "seo-geo-growth-intelligence.js",
        "seo-geo-connector-matrix.js",
        "geo-growth-os.js",
    ]
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
    result["connector_routes"] = connector_router.snapshot(check_live=False)
    result["runtime_health"] = runtime_resilience.snapshot()
    result["geo_growth_os"] = geo_growth.status()
    return result


def _combined_run(force=False):
    # Refresh connection/capability health first. Existing SEO/GEO loops run
    # before R8-24 so a newly completed C-level cloud receipt can be converted
    # into an operating opportunity in the same scheduler pass.
    connector_routes = connector_router.sync_growth_health(check_live=False)
    value = _ORIGINAL_RUN(force=force)
    result = dict(value) if isinstance(value, dict) else {"seo_geo": value}
    result["r8_20_growth"] = growth.run_once(force=force)
    result["geo_growth_os"] = geo_growth.run_once(force=force)
    result["connector_routes"] = connector_routes
    result["runtime_health"] = runtime_resilience.snapshot()
    return result


def install():
    global _INSTALLED
    if _INSTALLED:
        return

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
            if path == "/api/r8-24/geo-growth":
                handler._json_ok(geo_growth.status())
                return
            if path == "/api/r8-20/runtime-health":
                handler._json_ok(runtime_resilience.snapshot())
                return
            if path in {"/api/r8-20/seo-geo/connectors", "/api/r8-21/seo-geo/connectors"}:
                handler._json_ok(connector_router.snapshot(check_live=False))
                return
            if path == "/api/r8-21/seo-geo/controller-routes":
                handler._json_ok(connector_router.route_summary_for_controller(check_live=False))
                return
            if path == "/api/r8-20/seo-geo":
                payload = growth.status(_days(handler))
                payload["connector_routes"] = connector_router.snapshot(check_live=False)
                handler._json_ok(payload)
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
                    "connector_routes": connector_router.snapshot(check_live=False),
                })
                return
            if path == "/api/r8-20/seo-geo/features":
                handler._json_ok({"count": 38, "items": growth.feature_registry(), "r8_21_unified_connector_router": True})
                return
        except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
            handler._json_error(400, error)
            return
        return original_get(handler)

    def do_post(handler):
        path = urlsplit(handler.path).path
        if path in {
            "/api/r8-24/geo-growth/start",
            "/api/r8-24/geo-growth/pause",
            "/api/r8-24/geo-growth/resume",
            "/api/r8-24/geo-growth/run",
            "/api/r8-24/geo-growth/retry",
        }:
            if not _origin_allowed(handler):
                handler._json_error(403, "Cross-origin changes are not allowed")
                return
            try:
                payload = _read_json(handler)
                if path.endswith("/start"):
                    result = geo_growth.start()
                elif path.endswith("/pause"):
                    result = geo_growth.pause()
                elif path.endswith("/resume"):
                    result = geo_growth.resume()
                elif path.endswith("/retry"):
                    result = geo_growth.retry_failed()
                else:
                    result = geo_growth.run_once(force=bool(payload.get("force", True)))
                handler._json_ok({"result": result, "growth": geo_growth.status()})
            except (OSError, ValueError, RuntimeError, PermissionError, TypeError, KeyError, json.JSONDecodeError) as error:
                handler._json_error(400, error)
            return

        # The legacy SEO page still posts this route from its primary
        # "运行一次增长循环" button. In R8-20/R8-21/R8-24 it invokes the full
        # autonomous controller, unified connectors, and GEO Growth OS.
        if path == "/api/r8-13/seo-geo/run":
            if not _origin_allowed(handler):
                handler._json_error(403, "Cross-origin changes are not allowed")
                return
            try:
                payload = _read_json(handler)
                result = seo_core.run_once(force=bool(payload.get("force", True)))
                handler._json_ok({
                    "result": result,
                    "growth": growth.status(int(payload.get("days") or 30)),
                    "geo_growth_os": geo_growth.status(),
                    "connector_routes": connector_router.snapshot(check_live=False),
                    "runtime_health": runtime_resilience.snapshot(),
                    "mode": "r8_24_full_autonomous_loop_with_geo_growth_os",
                })
            except (OSError, ValueError, RuntimeError, PermissionError, TypeError, KeyError, json.JSONDecodeError) as error:
                handler._json_error(400, error)
            return

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
            "/api/r8-21/seo-geo/connectors/sync",
        }
        if path not in supported:
            return original_post(handler)
        if not _origin_allowed(handler):
            handler._json_error(403, "Cross-origin changes are not allowed")
            return
        try:
            payload = _read_json(handler)
            if path == "/api/r8-20/seo-geo/refresh":
                connector_router.sync_growth_health(check_live=False)
                result = seo_core.run_once(force=bool(payload.get("force", True)))
            elif path == "/api/r8-21/seo-geo/connectors/sync":
                result = connector_router.sync_growth_health(check_live=bool(payload.get("check_live", False)))
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
            handler._json_ok({
                "result": result,
                "growth": growth.status(int(payload.get("days") or 30)),
                "geo_growth_os": geo_growth.status(),
                "connector_routes": connector_router.snapshot(check_live=False),
                "runtime_health": runtime_resilience.snapshot(),
            })
        except (OSError, ValueError, RuntimeError, PermissionError, TypeError, KeyError, json.JSONDecodeError) as error:
            handler._json_error(400, error)

    server.DashboardHandler.do_GET = do_get
    server.DashboardHandler.do_POST = do_post
    server.DashboardHandler._kz_r8_20_seo_geo_growth = True
    server.DashboardHandler._kz_r8_21_unified_connectors = True
    server.DashboardHandler._kz_r8_24_geo_growth_os = True
    _INSTALLED = True


install()
