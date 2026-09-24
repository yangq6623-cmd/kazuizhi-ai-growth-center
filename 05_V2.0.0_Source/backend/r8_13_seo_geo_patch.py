"""R8-13 SEO/GEO growth HTTP bridge."""
from __future__ import annotations

import json
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

_INSTALLED = False


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
                handler._json_ok(dashboard())
                return
            if path == "/api/r8-13/seo-geo/technical":
                handler._json_ok(technical_snapshot())
                return
        except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
            handler._json_error(400, error)
            return
        return original_get(handler)

    def do_post(handler):
        path = urlsplit(handler.path).path
        allowed = {
            "/api/r8-13/seo-geo/config",
            "/api/r8-13/seo-geo/plan",
            "/api/r8-13/seo-geo/generate",
            "/api/r8-13/seo-geo/run",
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
                handler._json_ok({"config": configure(payload), "dashboard": dashboard()})
                return
            if path == "/api/r8-13/seo-geo/plan":
                handler._json_ok({"result": plan_today(payload.get("limit")), "dashboard": dashboard()})
                return
            if path == "/api/r8-13/seo-geo/generate":
                handler._json_ok({"result": generate_staging(payload.get("limit") or 6), "dashboard": dashboard()})
                return
            if path == "/api/r8-13/seo-geo/run":
                handler._json_ok({"result": run_daily_cycle(force=bool(payload.get("force"))), "dashboard": dashboard()})
                return
            if path == "/api/r8-13/seo-geo/asset-stage":
                asset_id = str(payload.get("asset_id") or "").strip()
                stage = str(payload.get("stage") or "").strip()
                if not asset_id or not stage:
                    raise ValueError("asset_id 和 stage 不能为空")
                evidence = payload.get("evidence") if isinstance(payload.get("evidence"), dict) else {}
                handler._json_ok({"asset": record_asset_stage(asset_id, stage, evidence), "dashboard": dashboard()})
                return
            if path == "/api/r8-13/seo-geo/geo-observation":
                handler._json_ok({"observation": record_geo_observation(payload), "dashboard": dashboard()})
                return
        except (OSError, ValueError, RuntimeError, TypeError, KeyError, json.JSONDecodeError) as error:
            handler._json_error(400, error)

    server.DashboardHandler.do_GET = do_get
    server.DashboardHandler.do_POST = do_post
    server.DashboardHandler._kz_r8_13_seo_geo = True
    _INSTALLED = True


install()
