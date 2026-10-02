"""R8-19 GEO Phase 3 additive HTTP + scheduler bridge."""
from __future__ import annotations

import json
from urllib.parse import urlsplit

from backend import server
from core import geo_phase2_latest_truth_patch as _geo_phase2_latest_truth_patch  # noqa: F401
from core import geo_phase3_job_patch as _geo_phase3_job_patch  # noqa: F401
from core import geo_phase3_seo_bridge as _geo_phase3_seo_bridge
from core import geo_phase3
from core import geo_phase3_retest_patch as _geo_phase3_retest_patch  # noqa: F401
from core import seo_geo_autonomy as seo_core

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
    if length < 0 or length > 64 * 1024:
        raise ValueError("请求内容过大")
    return json.loads(handler.rfile.read(length) or b"{}") if length else {}


def _serve_search_with_phase3(handler):
    web = server.get_web_path()
    names = ["operational-search.js", "geo-autonomy.js", "geo-phase3.js"]
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
    if not isinstance(value, dict):
        value = {"seo_geo": value}
    else:
        value = dict(value)
    value["geo_phase3"] = geo_phase3.status()
    return value


def _combined_run(force=False):
    # Converge Phase 3 first so newly completed AI-employee jobs are converted
    # into their exact SEO assets before the ordinary daily queue consumes the
    # page limit.  The bridge stops at QC_PASSED.  The existing autonomy cycle
    # then performs the real verified deployment/search submission.  A final
    # Phase-3 tick sees the new PUBLISHED receipt and queues the real A/B retest
    # in the same scheduler pass rather than waiting for another five minutes.
    phase3_before = geo_phase3.run_once(owner_approved=False)
    phase3_status = geo_phase3.status()
    prepared = _geo_phase3_seo_bridge.prepare_phase3_assets((phase3_status.get("plan") or {}))
    base = _ORIGINAL_RUN(force=force)
    phase3_after = geo_phase3.run_once(owner_approved=False)
    result = dict(base) if isinstance(base, dict) else {"seo_geo": base}
    result["geo_phase3"] = phase3_after
    result["geo_phase3_pre"] = phase3_before
    result["geo_phase3_assets"] = prepared
    return result


def install():
    global _INSTALLED
    if _INSTALLED:
        return

    # r8_14 has already combined SEO + cloud GEO autonomy. Phase 3 adds one
    # low-frequency convergence tick to the same scheduler without a competing
    # daemon or any change to A/B Evidence truth rules.
    seo_core.run_once = _combined_run
    seo_core.status = _combined_status

    original_get = server.DashboardHandler.do_GET
    original_post = server.DashboardHandler.do_POST

    def do_get(handler):
        path = urlsplit(handler.path).path
        if path == "/operational-search.js":
            try:
                _serve_search_with_phase3(handler)
            except OSError as error:
                handler._json_error(500, error)
            return
        if path == "/api/r8-19/geo/phase3":
            try:
                handler._json_ok(geo_phase3.status())
            except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
                handler._json_error(400, error)
            return
        return original_get(handler)

    def do_post(handler):
        path = urlsplit(handler.path).path
        supported = {
            "/api/r8-19/geo/phase3/plan",
            "/api/r8-19/geo/phase3/authorize",
            "/api/r8-19/geo/phase3/run",
            "/api/r8-19/geo/phase3/refresh",
            "/api/r8-19/geo/phase3/retest",
        }
        if path not in supported:
            return original_post(handler)
        if not _origin_allowed(handler):
            handler._json_error(403, "Cross-origin changes are not allowed")
            return
        try:
            payload = _read_json(handler)
            if path == "/api/r8-19/geo/phase3/plan":
                result = geo_phase3.plan(force=bool(payload.get("force")))
            elif path == "/api/r8-19/geo/phase3/authorize":
                result = geo_phase3.authorize(owner_approved=bool(payload.get("owner_approved")))
            elif path == "/api/r8-19/geo/phase3/run":
                result = geo_phase3.run_once(owner_approved=bool(payload.get("owner_approved")))
            elif path == "/api/r8-19/geo/phase3/retest":
                result = geo_phase3.sync(force_retest=bool(payload.get("force")))
            else:
                result = geo_phase3.sync()
            handler._json_ok({"result": result, "phase3": geo_phase3.status()})
        except (OSError, ValueError, RuntimeError, PermissionError, TypeError, KeyError, json.JSONDecodeError) as error:
            handler._json_error(400, error)

    server.DashboardHandler.do_GET = do_get
    server.DashboardHandler.do_POST = do_post
    server.DashboardHandler._kz_r8_19_geo_phase3 = True
    _INSTALLED = True


install()
