"""R8-23.5 cumulative field recovery.

Guarantees that the packaged browser bundle contains the full R8-23 chain plus
an explicit regression guard for SEO/GEO navigation and latest owner cockpit.
"""
from __future__ import annotations

from urllib.parse import urlsplit

from backend import server

_INSTALLED = False
RECOVERY_VERSION = "R8-23.5 Full Regression Recovery"


def _serve_autonomous_ops(handler):
    web = server.get_web_path()
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
        "r8_23_3_candidate.js",
        "r8_23_4_recovery.js",
        "r8_23_5_full_recovery.js",
    ]
    source = "\n;\n".join((web / name).read_text(encoding="utf-8") for name in names)
    data = source.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/javascript; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Pragma", "no-cache")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def install():
    global _INSTALLED
    if _INSTALLED:
        return
    original_get = server.DashboardHandler.do_GET

    def do_get(handler):
        path = urlsplit(handler.path).path
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
                "cumulative_runtime": ["R8-20", "R8-22", "R8-23", "R8-23.2", "R8-23.3", "R8-23.4", "R8-23.5"],
                "ui_contract": {
                    "owner_cockpit": "kz-r8-23-growth-os",
                    "seo_geo_route": "r813-seo-geo",
                    "seo_geo_bridge": "KZR813SeoGeoBridge.open",
                },
                "truth_policy": "formal external Receipt/Evidence only",
            })
            return
        return original_get(handler)

    server.DashboardHandler.do_GET = do_get
    server.DashboardHandler._kz_r8_23_5_full_recovery = True
    _INSTALLED = True


install()
