"""Local-only HTTP surface for the R8-18 release manifest and evidence ledger."""
from __future__ import annotations

import json
from urllib.parse import parse_qs, urlsplit

from backend import server
from core.growth_evidence import refresh_legacy_import, status as evidence_status
from core.version import release_manifest

_INSTALLED = False


def _origin_allowed(handler):
    origin = handler.headers.get("Origin")
    return not origin or origin in {f"http://127.0.0.1:{handler.server.server_port}", f"http://localhost:{handler.server.server_port}"}


def _read_json(handler):
    length = int(handler.headers.get("Content-Length", "0") or 0)
    if length < 0 or length > 16 * 1024:
        raise ValueError("请求内容过大")
    return json.loads(handler.rfile.read(length) or b"{}") if length else {}


def install():
    global _INSTALLED
    if _INSTALLED:
        return
    original_get = server.DashboardHandler.do_GET
    original_post = server.DashboardHandler.do_POST

    def do_get(handler):
        parsed = urlsplit(handler.path)
        if parsed.path == "/api/r8-18/release-manifest":
            handler._json_ok(release_manifest())
            return
        if parsed.path == "/api/r8-18/evidence-ledger":
            query = parse_qs(parsed.query)
            handler._json_ok(evidence_status(query.get("limit", [100])[0]))
            return
        return original_get(handler)

    def do_post(handler):
        path = urlsplit(handler.path).path
        if path != "/api/r8-18/evidence-ledger/refresh":
            return original_post(handler)
        if not _origin_allowed(handler):
            handler._json_error(403, "Cross-origin changes are not allowed")
            return
        try:
            _read_json(handler)
            handler._json_ok({"result": refresh_legacy_import(), "ledger": evidence_status()})
        except (OSError, ValueError, RuntimeError, TypeError, KeyError, json.JSONDecodeError) as error:
            handler._json_error(400, error)

    server.DashboardHandler.do_GET = do_get
    server.DashboardHandler.do_POST = do_post
    server.DashboardHandler._kz_r8_18_evidence_ledger = True
    _INSTALLED = True


install()
