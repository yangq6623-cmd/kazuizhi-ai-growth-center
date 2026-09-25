"""HTTP bridge for R8-16 truthful search-engine submission connectors.

Includes a Baidu ordinary-indexing compatibility shim for the verified-site
identifier emitted by Baidu Search Resource Platform. Baidu currently returns
an API endpoint whose ``site`` query value is the full verified HTTPS site
(e.g. ``https://kazuizhi.com``). That value must remain literal in the query;
percent-encoding the ``https://`` portion changes Baidu's request semantics.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from urllib.parse import urlsplit

from backend import server
from core.storage import now_iso
from integrations import search_engine_submitter as search_submitter

_INSTALLED = False


def _normalize_baidu_verified_site(value: str) -> str:
    """Return the exact HTTPS site identifier Baidu expects in the query."""
    raw = str(value or "").strip()
    if raw and "://" not in raw:
        raw = "https://" + raw.lstrip("/")
    parts = urlsplit(raw)
    if (
        parts.scheme != "https"
        or not parts.netloc
        or parts.path not in {"", "/"}
        or parts.query
        or parts.fragment
    ):
        raise ValueError("baidu_site 必须是已验证 HTTPS 站点，例如 https://kazuizhi.com")
    return f"https://{parts.netloc.lower()}"


def _submit_baidu_exact_site(urls: list[str], site: str, token: str, timeout: int = 15) -> dict:
    """Submit to Baidu while preserving the verified HTTPS site literally."""
    try:
        verified_site = _normalize_baidu_verified_site(site)
    except ValueError as error:
        return {"ok": False, "error": str(error), "at": now_iso()}

    safe_token = urllib.parse.quote(str(token or "").strip(), safe="")
    endpoint = f"http://data.zz.baidu.com/urls?site={verified_site}&token={safe_token}"
    body = "\n".join(urls).encode("utf-8")
    request = urllib.request.Request(
        endpoint,
        data=body,
        headers={"Content-Type": "text/plain", "User-Agent": "Kazuizhi-R8-16/1.0"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:  # nosec B310 - Baidu documents this HTTP endpoint
            code = int(getattr(response, "status", 200) or 200)
            raw = response.read(32 * 1024).decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"raw": raw[:2000]}
        ok = bool(200 <= code < 300 and isinstance(payload, dict) and not payload.get("error"))
        return {"ok": ok, "status": code, "response": payload, "submitted": len(urls), "at": now_iso()}
    except urllib.error.HTTPError as error:
        raw = error.read(16 * 1024).decode("utf-8", errors="replace") if getattr(error, "fp", None) else ""
        try:
            payload = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            payload = {"raw": raw[:2000]}
        return {
            "ok": False,
            "status": int(error.code),
            "response": payload,
            "error": str(error),
            "at": now_iso(),
        }
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        return {"ok": False, "error": str(error), "at": now_iso()}


def _configure(payload: dict) -> dict:
    """Accept either Baidu's HTTPS site form or the legacy host-only form."""
    normalized = dict(payload or {})
    if "baidu_site" in normalized:
        verified_site = _normalize_baidu_verified_site(normalized.get("baidu_site"))
        normalized["baidu_site"] = urlsplit(verified_site).netloc
    return search_submitter.configure(normalized)


def _install_baidu_compatibility():
    # submit_pending resolves _submit_baidu from its module globals at runtime,
    # so replacing it here fixes every R8-16 Baidu submission path without
    # exposing or migrating the token stored in the DPAPI vault.
    search_submitter._submit_baidu = _submit_baidu_exact_site


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


def install():
    global _INSTALLED
    if _INSTALLED:
        return
    _install_baidu_compatibility()
    original_get = server.DashboardHandler.do_GET
    original_post = server.DashboardHandler.do_POST

    def do_get(handler):
        path = urlsplit(handler.path).path
        if path == "/api/r8-16/search-submit/status":
            try:
                handler._json_ok(search_submitter.status())
            except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
                handler._json_error(400, error)
            return
        return original_get(handler)

    def do_post(handler):
        path = urlsplit(handler.path).path
        if path not in {
            "/api/r8-16/search-submit/config",
            "/api/r8-16/search-submit/initialize",
            "/api/r8-16/search-submit/run",
        }:
            return original_post(handler)
        if not _origin_allowed(handler):
            handler._json_error(403, "Cross-origin changes are not allowed")
            return
        try:
            payload = _read_json_body(handler)
            if path.endswith("/config"):
                handler._json_ok(_configure(payload))
            elif path.endswith("/initialize"):
                handler._json_ok(search_submitter.initialize_indexnow())
            else:
                handler._json_ok(search_submitter.submit_pending(limit=max(1, min(100, int(payload.get("limit") or 20)))))
        except (OSError, ValueError, RuntimeError, TypeError, KeyError, json.JSONDecodeError) as error:
            handler._json_error(400, error)

    server.DashboardHandler.do_GET = do_get
    server.DashboardHandler.do_POST = do_post
    server.DashboardHandler._kz_r8_16_search_submit = True
    _INSTALLED = True


install()
