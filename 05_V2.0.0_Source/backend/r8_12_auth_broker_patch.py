"""Official authorization + environment safety bridge for durable Account Assets.

The browser opens the provider's own login/consent UI.  Passwords never pass
through Kazuizhi. OAuth callbacks validate state before token exchange; tokens
are persisted only through Windows DPAPI.
"""
from __future__ import annotations

import json
from urllib.parse import parse_qs, urlsplit

from backend import server
from integrations.account_environment import clear_risk, mark_risk, observe, snapshot as environment_snapshot
from integrations.oauth_token_broker import complete_authorization
from integrations.platform_auth_catalog import catalog, configure_provider_credentials, pending_requests, start_authorization

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
    if length < 0 or length > 64 * 1024:
        raise ValueError("请求内容过大")
    if not length:
        return {}
    return json.loads(handler.rfile.read(length) or b"{}")


def _html(handler, title: str, body: str, *, ok=True):
    color = "#16895f" if ok else "#b42318"
    html = f"""<!doctype html><html lang='zh-CN'><head><meta charset='utf-8'><meta name='viewport' content='width=device-width,initial-scale=1'><title>{title}</title></head><body style='font-family:Microsoft YaHei,Arial;background:#f4f7fb;color:#172033;padding:40px'><div style='max-width:720px;margin:auto;background:white;border:1px solid #e1e7f0;border-radius:18px;padding:28px;box-shadow:0 12px 36px rgba(23,32,51,.08)'><h2 style='color:{color}'>{title}</h2><p>{body}</p><p style='color:#6d778a'>可以关闭本窗口，返回卡嘴子 AI 的“统一账号资产中心”查看状态。</p><script>setTimeout(()=>{{try{{window.opener&&window.opener.postMessage({{type:'kz-auth-callback'}},location.origin)}}catch(e){{}}}},500);</script></div></body></html>""".encode("utf-8")
    handler.send_response(200 if ok else 400)
    handler.send_header("Content-Type", "text/html; charset=utf-8")
    handler.send_header("Content-Length", str(len(html)))
    handler.end_headers(); handler.wfile.write(html)


def install():
    global _INSTALLED
    if _INSTALLED:
        return
    original_get = server.DashboardHandler.do_GET
    original_post = server.DashboardHandler.do_POST

    def do_get(handler):
        parsed = urlsplit(handler.path); path = parsed.path
        try:
            if path == "/api/r8-12/auth/catalog":
                payload = catalog(); payload["pending"] = pending_requests(); handler._json_ok(payload); return
            if path == "/api/r8-12/account-environments":
                handler._json_ok(environment_snapshot()); return
            if path.startswith("/api/r8-12/oauth/callback/"):
                platform = path.rsplit("/", 1)[-1].strip(); query = parse_qs(parsed.query)
                state = (query.get("state") or [""])[0]
                code = (query.get("code") or [""])[0]
                error = (query.get("error") or [""])[0]
                error_description = (query.get("error_description") or query.get("error_msg") or [""])[0]
                try:
                    result = complete_authorization(platform, state=state, code=code, error=error, error_description=error_description)
                except (OSError, ValueError, RuntimeError, TypeError, KeyError) as callback_error:
                    _html(handler, "账号授权未完成", str(callback_error), ok=False); return
                if result.get("ok"):
                    _html(handler, "账号授权成功", f"{result.get('display_name') or platform} 已建立为独立账号资产。授权成功不等于内容发布成功。", ok=True)
                else:
                    _html(handler, "账号授权未完成", result.get("truth") or "平台未完成授权。", ok=False)
                return
        except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
            handler._json_error(400, error); return
        return original_get(handler)

    def do_post(handler):
        path = urlsplit(handler.path).path
        allowed = {
            "/api/r8-12/auth/start",
            "/api/r8-12/auth/configure",
            "/api/r8-12/account-environment/observe",
            "/api/r8-12/account-environment/risk",
            "/api/r8-12/account-environment/clear-risk",
        }
        if path not in allowed:
            return original_post(handler)
        if not _origin_allowed(handler):
            handler._json_error(403, "Cross-origin changes are not allowed"); return
        try:
            payload = _read_json_body(handler)
            if path == "/api/r8-12/auth/start":
                platform = str(payload.get("platform") or "").strip()
                if not platform: raise ValueError("platform 不能为空")
                result = start_authorization(
                    platform,
                    slot_label=str(payload.get("slot_label") or "").strip(),
                    redirect_uri=str(payload.get("redirect_uri") or "").strip(),
                    account_id=str(payload.get("account_id") or "").strip(),
                )
                handler._json_ok(result); return
            if path == "/api/r8-12/auth/configure":
                handler._json_ok(configure_provider_credentials(
                    str(payload.get("platform") or "").strip(),
                    client_id=str(payload.get("client_id") or "").strip(),
                    client_secret=str(payload.get("client_secret") or "").strip(),
                )); return
            account_id = str(payload.get("account_id") or "").strip()
            if not account_id: raise ValueError("account_id 不能为空")
            if path == "/api/r8-12/account-environment/observe":
                handler._json_ok(observe(account_id, device_id=payload.get("device_id"), network_profile_label=payload.get("network_profile_label"))); return
            if path == "/api/r8-12/account-environment/risk":
                handler._json_ok(mark_risk(account_id, str(payload.get("reason") or "risk_prompt"), level=str(payload.get("level") or "high"), cooldown_minutes=int(payload.get("cooldown_minutes") or 60))); return
            handler._json_ok(clear_risk(account_id, owner_confirmed=bool(payload.get("owner_confirmed")))); return
        except (OSError, ValueError, RuntimeError, TypeError, KeyError, json.JSONDecodeError) as error:
            handler._json_error(400, error)

    server.DashboardHandler.do_GET = do_get
    server.DashboardHandler.do_POST = do_post
    server.DashboardHandler._kz_r8_12_auth_broker = True
    server.DashboardHandler._kz_r8_12_safe_multi_account = True
    _INSTALLED = True


install()
