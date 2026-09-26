"""Local-only HTTP bridge for the R8-17 desktop Remote Agent client."""
from __future__ import annotations

import json
from urllib.parse import urlsplit

from backend import server
from integrations import remote_agent
from integrations.r8_17_remote_deployer_patch import activate_remote_mode_if_ready
from integrations import r8_17_direct_file_fallback as _r8_17_direct_file_fallback  # noqa: F401,E402

_INSTALLED = False
_BOOTSTRAP_RESULT = {}


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


def _safe_status(check_live=True):
    state = remote_agent.status(check_live=check_live)
    state.pop("shared_secret", None)
    state.pop("token", None)
    return state


def _bootstrap_remote_agent():
    result = {
        "ok": False,
        "pairing": {},
        "deploy_mode": {},
        "status": {},
        "error": "",
    }
    try:
        pairing = remote_agent.auto_import_pairing()
        result["pairing"] = pairing
    except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
        result["pairing"] = {"ok": False, "reason": str(error)}

    try:
        activation = activate_remote_mode_if_ready(check_live=True)
        result["deploy_mode"] = activation
        result["status"] = _safe_status(check_live=False)
        result["ok"] = bool(
            result["status"].get("configured")
            and result["status"].get("connected")
            and activation.get("activated")
        )
    except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
        result["error"] = str(error)
        try:
            result["status"] = _safe_status(check_live=False)
        except (OSError, ValueError, RuntimeError, TypeError, KeyError):
            result["status"] = {}
    return result


def install():
    global _INSTALLED, _BOOTSTRAP_RESULT
    if _INSTALLED:
        return
    original_get = server.DashboardHandler.do_GET
    original_post = server.DashboardHandler.do_POST

    def do_get(handler):
        path = urlsplit(handler.path).path
        if path == "/api/r8-17/remote-agent/status":
            try:
                payload = _safe_status(check_live=True)
                payload["bootstrap"] = _BOOTSTRAP_RESULT
                handler._json_ok(payload)
            except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
                handler._json_error(400, error)
            return
        return original_get(handler)

    def do_post(handler):
        path = urlsplit(handler.path).path
        if path not in {
            "/api/r8-17/remote-agent/auto-import",
            "/api/r8-17/remote-agent/test",
            "/api/r8-17/remote-agent/disconnect",
        }:
            return original_post(handler)
        if not _origin_allowed(handler):
            handler._json_error(403, "Cross-origin changes are not allowed")
            return
        try:
            _read_json_body(handler)
            if path.endswith("/auto-import"):
                result = remote_agent.auto_import_pairing()
                if result.get("ok"):
                    result["deploy_mode"] = activate_remote_mode_if_ready(check_live=True)
                result["status"] = _safe_status(check_live=False)
                handler._json_ok(result)
                return
            if path.endswith("/test"):
                health = remote_agent.health(timeout=20)
                capabilities = remote_agent.capabilities(timeout=20)
                selftest = remote_agent.selftest(timeout=25)
                activation = activate_remote_mode_if_ready(check_live=False)
                handler._json_ok({
                    "ok": bool(health.get("ok") and capabilities.get("ok") and selftest.get("ok")),
                    "health": health,
                    "capabilities": capabilities,
                    "selftest": selftest,
                    "deploy_mode": activation,
                    "status": _safe_status(check_live=False),
                    "truth": "这里只验证远程执行通道；SEO页面仍需公网验证才进入 PUBLISHED。",
                })
                return
            remote_agent.disconnect()
            handler._json_ok({"ok": True, "status": _safe_status(check_live=False)})
        except (OSError, ValueError, RuntimeError, TypeError, KeyError, json.JSONDecodeError) as error:
            handler._json_error(400, error)

    server.DashboardHandler.do_GET = do_get
    server.DashboardHandler.do_POST = do_post
    server.DashboardHandler._kz_r8_17_remote_agent = True
    _INSTALLED = True
    _BOOTSTRAP_RESULT = _bootstrap_remote_agent()
    server.DashboardHandler._kz_r8_17_bootstrap = _BOOTSTRAP_RESULT


install()

# R8-18 extends the existing local HTTP chain with truthful SEO evidence,
# PageSpeed and internal-link audit endpoints. Import after R8-17 so its
# handler captures the complete Remote Agent route set without replacing it.
from backend import r8_18_seo_quality_patch as _r8_18_seo_quality_patch  # noqa: F401,E402
