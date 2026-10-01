"""HTTP bridge for R8-14 SEO autonomy plus R8-19 GEO cloud autonomy."""
from __future__ import annotations

import json
from urllib.parse import urlsplit

from backend import server
from core import geo_autonomy
from core import seo_geo_autonomy as seo_core

_INSTALLED = False
_ORIGINAL_SEO_RUN_ONCE = seo_core.run_once
_ORIGINAL_SEO_STATUS = seo_core.status


def _origin_allowed(handler):
    origin = handler.headers.get("Origin")
    allowed = {
        f"http://127.0.0.1:{handler.server.server_port}",
        f"http://localhost:{handler.server.server_port}",
    }
    return not origin or origin in allowed


def _read_json_body(handler):
    length = int(handler.headers.get("Content-Length", "0") or 0)
    if length < 0 or length > 64 * 1024:
        raise ValueError("请求内容过大")
    if not length:
        return {}
    return json.loads(handler.rfile.read(length) or b"{}")


def _combined_status():
    value = _ORIGINAL_SEO_STATUS()
    value["geo_autonomy"] = geo_autonomy.status()
    return value


def _combined_run_once(force=False):
    """Keep the existing SEO cycle and add one truth-gated GEO autonomy tick.

    The dedicated GEO worker performs the fast sequential 50-question loop.
    This scheduler tick is an additional recovery path, so a desktop restart or
    sleeping worker still converges without changing evidence semantics.
    """
    seo_result = _ORIGINAL_SEO_RUN_ONCE(force=force)
    geo_result = geo_autonomy.run_once()
    if isinstance(seo_result, dict):
        result = dict(seo_result)
    else:
        result = {"seo_result": seo_result}
    result["geo_autonomy"] = geo_result
    return result


def install():
    global _INSTALLED
    if _INSTALLED:
        return

    # run.py imports this patch before importing run_once/status from the core
    # module. Replacing the attributes here makes the existing scheduler execute
    # the combined SEO + GEO controller without a second competing scheduler.
    seo_core.run_once = _combined_run_once
    seo_core.status = _combined_status

    original_get = server.DashboardHandler.do_GET
    original_post = server.DashboardHandler.do_POST

    def do_get(handler):
        path = urlsplit(handler.path).path
        if path == "/api/r8-14/seo-geo/autonomy":
            try:
                handler._json_ok(_combined_status())
            except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
                handler._json_error(400, error)
            return
        if path == "/api/r8-19/geo/autonomy":
            try:
                handler._json_ok(geo_autonomy.status())
            except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
                handler._json_error(400, error)
            return
        return original_get(handler)

    def do_post(handler):
        path = urlsplit(handler.path).path
        supported = {
            "/api/r8-14/seo-geo/autonomy/config",
            "/api/r8-14/seo-geo/autonomy/run",
            "/api/r8-19/geo/autonomy/start",
            "/api/r8-19/geo/autonomy/pause",
            "/api/r8-19/geo/autonomy/resume",
            "/api/r8-19/geo/autonomy/run",
            "/api/r8-19/geo/autonomy/retry-failed",
        }
        if path not in supported:
            return original_post(handler)
        if not _origin_allowed(handler):
            handler._json_error(403, "Cross-origin changes are not allowed")
            return
        try:
            payload = _read_json_body(handler)
            if path == "/api/r8-14/seo-geo/autonomy/config":
                result = seo_core.configure(payload)
            elif path == "/api/r8-14/seo-geo/autonomy/run":
                result = _combined_run_once(force=bool(payload.get("force")))
            elif path == "/api/r8-19/geo/autonomy/start":
                result = geo_autonomy.start(target=payload.get("target") or 50)
            elif path == "/api/r8-19/geo/autonomy/pause":
                result = geo_autonomy.pause()
            elif path == "/api/r8-19/geo/autonomy/resume":
                result = geo_autonomy.resume()
            elif path == "/api/r8-19/geo/autonomy/retry-failed":
                result = geo_autonomy.retry_failed()
            else:
                result = {"result": geo_autonomy.run_once(), "status": geo_autonomy.status()}
            handler._json_ok(result)
        except (OSError, ValueError, RuntimeError, TypeError, KeyError, json.JSONDecodeError) as error:
            handler._json_error(400, error)

    server.DashboardHandler.do_GET = do_get
    server.DashboardHandler.do_POST = do_post
    server.DashboardHandler._kz_r8_14_seo_geo_autonomy = True
    server.DashboardHandler._kz_r8_19_geo_autonomy = True
    geo_autonomy.start_worker()
    _INSTALLED = True


install()
