"""R8-18 SEO evidence/performance/internal-link HTTP bridge."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit

from backend import server
from integrations.seo_quality_evidence import (
    configure,
    run_all,
    run_internal_links,
    run_performance,
    run_result_verification,
    status,
)

_INSTALLED = False
_WEB = Path(__file__).resolve().parents[1] / "web"


def _origin_allowed(handler):
    origin = handler.headers.get("Origin")
    allowed = {
        f"http://127.0.0.1:{handler.server.server_port}",
        f"http://localhost:{handler.server.server_port}",
    }
    return not origin or origin in allowed


def _read_json_body(handler):
    length = int(handler.headers.get("Content-Length", "0") or 0)
    if length < 0 or length > 128 * 1024:
        raise ValueError("请求内容过大")
    if not length:
        return {}
    return json.loads(handler.rfile.read(length) or b"{}")


def _serve_seo_page(handler):
    source = _WEB / "r8_13_seo_geo.html"
    text = source.read_text(encoding="utf-8")
    marker = '<script src="/r8_18_seo_quality_ui.js"></script>'
    if marker not in text:
        text = text.replace("</body>", marker + "\n</body>")
    body = text.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(body)))
    handler.end_headers()
    handler.wfile.write(body)


def install():
    global _INSTALLED
    if _INSTALLED:
        return
    original_get = server.DashboardHandler.do_GET
    original_post = server.DashboardHandler.do_POST

    def do_get(handler):
        path = urlsplit(handler.path).path
        try:
            if path == "/r8_13_seo_geo.html":
                _serve_seo_page(handler)
                return
            if path == "/api/r8-18/seo-quality/status":
                handler._json_ok(status())
                return
        except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
            handler._json_error(400, error)
            return
        return original_get(handler)

    def do_post(handler):
        path = urlsplit(handler.path).path
        allowed = {
            "/api/r8-18/seo-quality/config",
            "/api/r8-18/seo-quality/run",
            "/api/r8-18/seo-quality/verify-results",
            "/api/r8-18/seo-quality/performance",
            "/api/r8-18/seo-quality/internal-links",
        }
        if path not in allowed:
            return original_post(handler)
        if not _origin_allowed(handler):
            handler._json_error(403, "Cross-origin changes are not allowed")
            return
        try:
            payload = _read_json_body(handler)
            limit = max(1, min(50, int(payload.get("limit") or 10)))
            if path == "/api/r8-18/seo-quality/config":
                handler._json_ok(configure(payload))
                return
            if path == "/api/r8-18/seo-quality/verify-results":
                handler._json_ok(run_result_verification(limit=limit))
                return
            if path == "/api/r8-18/seo-quality/performance":
                handler._json_ok(run_performance(limit=min(5, limit)))
                return
            if path == "/api/r8-18/seo-quality/internal-links":
                handler._json_ok(run_internal_links(limit=limit))
                return
            handler._json_ok(run_all(limit=limit))
        except (OSError, ValueError, RuntimeError, TypeError, KeyError, json.JSONDecodeError) as error:
            handler._json_error(400, error)

    server.DashboardHandler.do_GET = do_get
    server.DashboardHandler.do_POST = do_post
    server.DashboardHandler._kz_r8_18_seo_quality = True
    _INSTALLED = True


install()

