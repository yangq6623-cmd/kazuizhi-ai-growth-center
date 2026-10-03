"""R8-23.5 cumulative field recovery.

Guarantees that the packaged browser uses the latest stable owner shell and SEO/GEO
route while retaining all later backend/runtime capabilities. Historical Candidate UI
scripts remain backend-compatible but are not allowed to re-own current navigation.
"""
from __future__ import annotations

from urllib.parse import urlsplit

from backend import server

_INSTALLED = False
RECOVERY_VERSION = "R8-23.5 Full Regression Recovery"


def _send_text(handler, text, content_type):
    data = text.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", content_type)
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Pragma", "no-cache")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def _serve_index(handler):
    """Always paint the usable shell directly; no historical blocking boot overlay."""
    source = (server.get_web_path() / "index.html").read_text(encoding="utf-8")
    source = source.replace(
        "<title>卡嘴子 AI 增长运营中心 V2.0.0 Beta R7 Final</title>",
        "<title>卡嘴子 AI 自治运营 · R8-23.5</title>",
        1,
    )
    if "autonomous-ops.js" not in source:
        source = source.replace("</body>", '<script src="/autonomous-ops.js"></script></body>', 1)
    _send_text(handler, source, "text/html; charset=utf-8")


def _serve_web_html(handler, name):
    """Serve critical embedded workspaces explicitly instead of relying on a
    historical handler chain. This prevents an older wrapper from swallowing an
    iframe route and leaving a blank SEO/GEO workspace.
    """
    source = (server.get_web_path() / name).read_text(encoding="utf-8")
    _send_text(handler, source, "text/html; charset=utf-8")


def _serve_autonomous_ops(handler):
    web = server.get_web_path()
    # Do not load r8_23_3_candidate.js in the current browser. That historical
    # Candidate UI continuously rewrites the promotion route into SEO/GEO via a
    # global MutationObserver, fighting R8-23.4/23.5 and causing the field bug
    # where the latest package showed old navigation or a non-opening SEO/GEO entry.
    # Backend Candidate compatibility remains loaded in Python.
    names = [
        "autonomous-ops.js",
        "r8_13_seo_geo_bridge.js",
        "operational-search.js",
        "geo-autonomy.js",
        "geo-phase3.js",
        "seo-geo-growth-intelligence.js",
        "seo-geo-connector-matrix.js",
        "r8_22_autonomy.js",
        "r8_23_growth_os.js",
        "r8_23_2_pilot.js",
        "r8_23_4_recovery.js",
        "r8_23_5_full_recovery.js",
    ]
    source = "\n;\n".join((web / name).read_text(encoding="utf-8") for name in names)
    _send_text(handler, source, "application/javascript; charset=utf-8")


def install():
    global _INSTALLED
    if _INSTALLED:
        return
    original_get = server.DashboardHandler.do_GET

    def do_get(handler):
        path = urlsplit(handler.path).path
        if path in {"/", "/index.html"}:
            try:
                _serve_index(handler)
            except Exception as error:
                handler._json_error(503, f"R8-23.5 owner shell recovery failed: {type(error).__name__}: {error}")
            return
        if path in {"/r8_13_seo_geo.html", "/geo.html"}:
            try:
                _serve_web_html(handler, path.lstrip("/"))
            except Exception as error:
                handler._json_error(503, f"R8-23.5 embedded growth workspace failed: {type(error).__name__}: {error}")
            return
        if path == "/autonomous-ops.js":
            try:
                _serve_autonomous_ops(handler)
            except Exception as error:
                handler._json_error(503, f"R8-23.5 browser bundle recovery failed: {type(error).__name__}: {error}")
            return
        if path == "/api/r8-23-5/recovery":
            handler._json_ok({
                "alive": True,
                "phase": RECOVERY_VERSION,
                "cumulative_runtime": ["R8-20", "R8-22", "R8-23", "R8-23.2", "R8-23.3-backend", "R8-23.4", "R8-23.5"],
                "ui_contract": {
                    "owner_cockpit": "kz-r8-23-growth-os",
                    "seo_geo_route": "r813-seo-geo",
                    "seo_geo_bridge": "KZR813SeoGeoBridge.open",
                    "seo_workspace": "/r8_13_seo_geo.html",
                    "geo_workspace": "/geo.html",
                    "historical_candidate_ui": "disabled_to_prevent_route_rewrite",
                },
                "truth_policy": "formal external Receipt/Evidence only",
            })
            return
        return original_get(handler)

    server.DashboardHandler.do_GET = do_get
    server.DashboardHandler._kz_r8_23_5_full_recovery = True
    _INSTALLED = True


install()
