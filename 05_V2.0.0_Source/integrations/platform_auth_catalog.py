"""Official platform authorization catalog + safe multi-account entry points.

Design rules:
- Never collect or persist platform plaintext passwords.
- Open the platform's own login/consent page in the system browser/new window.
- Keep one durable Kazuizhi account slot per real platform identity.
- Multiple accounts on one platform are supported as independent account assets.
- Tokens/secrets never enter GitHub, Mission JSON, normal logs, or browser storage.
- No proxy rotation, fingerprint spoofing, CAPTCHA bypass, SMS interception or risk-control evasion.
- Prefer a stable device/browser/network environment per account and pause on risk prompts.
"""
from __future__ import annotations

import os
import secrets
from copy import deepcopy
from urllib.parse import urlencode

from core.storage import now_iso, read_json, write_json

AUTH_REQUESTS_PATH = "r8_12/auth_requests.json"
AUTH_SCHEMA = "kz.auth-request.v1"

PROVIDERS = {
    "google_search_console": {
        "name": "Google Search Console",
        "category": "search",
        "auth_mode": "oauth2_authorization_code",
        "authorization_url": "https://accounts.google.com/o/oauth2/v2/auth",
        "token_url": "https://oauth2.googleapis.com/token",
        "token_method": "POST_FORM",
        "api_base": "https://www.googleapis.com/webmasters/v3/",
        "console_url": "https://search.google.com/search-console",
        "client_id_env": "KZ_GOOGLE_SEARCH_CLIENT_ID",
        "client_secret_env": "KZ_GOOGLE_SEARCH_CLIENT_SECRET",
        "default_scopes": ["https://www.googleapis.com/auth/webmasters"],
        "browser_mode": "system_external",
        "multi_account": True,
        "notes": "Search Console private data uses OAuth 2.0. Use account chooser/consent in the system browser; do not embed Google login in an app-controlled WebView.",
    },
    "bing_webmaster": {
        "name": "Bing Webmaster",
        "category": "search",
        "auth_mode": "oauth2_authorization_code",
        "authorization_url": "https://www.bing.com/webmasters/OAuth/authorize",
        "token_url": "https://www.bing.com/webmasters/OAuth/token",
        "token_method": "POST_FORM",
        "api_base": "https://www.bing.com/webmaster/api.svc/json/",
        "console_url": "https://www.bing.com/webmasters",
        "client_id_env": "KZ_BING_WEBMASTER_CLIENT_ID",
        "client_secret_env": "KZ_BING_WEBMASTER_CLIENT_SECRET",
        "default_scopes": ["webmaster.manage"],
        "browser_mode": "system_external",
        "multi_account": True,
        "notes": "Bing Webmaster supports delegated OAuth 2.0 with access and refresh tokens.",
    },
    "baidu_search_resource": {
        "name": "百度搜索资源平台",
        "category": "search",
        "auth_mode": "official_portal_site_token",
        "authorization_url": "https://ziyuan.baidu.com/site/index",
        "token_url": None,
        "token_method": None,
        "api_base": "http://data.zz.baidu.com/urls",
        "console_url": "https://ziyuan.baidu.com/",
        "client_id_env": None,
        "client_secret_env": None,
        "default_scopes": [],
        "browser_mode": "system_external",
        "multi_account": True,
        "notes": "普通收录使用已验证站点对应 token/API 提交；不把通用百度 OAuth 冒充为搜索资源平台授权。",
    },
    "douyin": {
        "name": "抖音",
        "category": "content",
        "auth_mode": "oauth2_authorization_code",
        "authorization_url": "https://open.douyin.com/platform/oauth/connect",
        "token_url": "https://open.douyin.com/oauth/access_token/",
        "token_method": "POST_FORM",
        "api_base": "https://open.douyin.com/",
        "console_url": "https://developer.open-douyin.com/",
        "client_id_env": "KZ_DOUYIN_CLIENT_KEY",
        "client_secret_env": "KZ_DOUYIN_CLIENT_SECRET",
        "default_scopes": ["user_info"],
        "browser_mode": "system_external",
        "multi_account": True,
        "requires_https_callback": True,
        "notes": "网站应用可走官方扫码授权。发布 scope 仍以开放平台实际审批结果为准。",
    },
    "kuaishou": {
        "name": "快手",
        "category": "content",
        "auth_mode": "oauth2_authorization_code",
        "authorization_url": "https://open.kuaishou.com/oauth2/authorize",
        "token_url": "https://open.kuaishou.com/oauth2/access_token",
        "token_method": "GET_QUERY",
        "api_base": "https://open.kuaishou.com/",
        "console_url": "https://open.kuaishou.com/platform/console",
        "client_id_env": "KZ_KUAISHOU_CLIENT_ID",
        "client_secret_env": "KZ_KUAISHOU_CLIENT_SECRET",
        "default_scopes": ["user_info"],
        "browser_mode": "system_external",
        "multi_account": True,
        "notes": "网站应用支持网页授权和官方扫码登录。发布能力需申请相应 scope。",
    },
    "xiaohongshu": {
        "name": "小红书",
        "category": "content",
        "auth_mode": "official_portal_manual_authorization",
        "authorization_url": "https://miniapp.xiaohongshu.com/",
        "token_url": None,
        "token_method": None,
        "api_base": "https://miniapp.xiaohongshu.com/",
        "console_url": "https://miniapp.xiaohongshu.com/",
        "client_id_env": None,
        "client_secret_env": None,
        "default_scopes": [],
        "browser_mode": "system_external",
        "multi_account": True,
        "notes": "只登记官方开放平台入口；没有公开确认到普通笔记账号的一键 OAuth 发布流程时，不伪造接口能力。",
    },
    "wechat_channels": {
        "name": "微信 / 视频号",
        "category": "content",
        "auth_mode": "official_portal_manual_authorization",
        "authorization_url": "https://open.weixin.qq.com/",
        "token_url": None,
        "token_method": None,
        "api_base": "https://open.weixin.qq.com/",
        "console_url": "https://open.weixin.qq.com/",
        "client_id_env": None,
        "client_secret_env": None,
        "default_scopes": [],
        "browser_mode": "system_external",
        "multi_account": True,
        "notes": "开放能力依应用类型、主体和审核权限而定；扫码/管理员确认交给官方页面完成。",
    },
}

DEFAULT_ENVIRONMENT_POLICY = {
    "stable_environment_per_account": True,
    "stable_device_preferred": True,
    "stable_network_preferred": True,
    "proxy_rotation": False,
    "fingerprint_spoofing": False,
    "credential_capture": False,
    "captcha_bypass": False,
    "sms_interception": False,
    "max_parallel_authorizations_per_account": 1,
    "max_parallel_mutating_jobs_per_account": 1,
    "risk_prompt_action": "pause_for_human",
    "network_change_action": "warn_and_reduce_rate",
    "reauth_on_suspicious_session_change": True,
    "truth": "安全策略用于降低误触发风控，不用于规避或绕过平台安全机制。",
}


def _public_provider(key: str, raw: dict) -> dict:
    row = deepcopy(raw)
    cid_env = row.pop("client_id_env", None)
    secret_env = row.pop("client_secret_env", None)
    row["platform"] = key
    row["client_id_configured"] = bool(cid_env and os.environ.get(cid_env)) if cid_env else row["auth_mode"].startswith("official_portal")
    row["client_secret_configured"] = bool(secret_env and os.environ.get(secret_env)) if secret_env else row["auth_mode"].startswith("official_portal")
    row["configured"] = bool(row["client_id_configured"] and row["client_secret_configured"])
    row["credential_names"] = [name for name in (cid_env, secret_env) if name]
    return row


def catalog() -> dict:
    return {
        "providers": [_public_provider(key, value) for key, value in PROVIDERS.items()],
        "environment_policy": deepcopy(DEFAULT_ENVIRONMENT_POLICY),
        "truth": "官方登录在平台自己的页面完成；卡嘴子不保存账号密码。一个平台可登记多个独立账号资产。",
    }


def _load_requests() -> dict:
    data = read_json(AUTH_REQUESTS_PATH, {})
    if not isinstance(data, dict) or data.get("schema") != AUTH_SCHEMA:
        data = {"schema": AUTH_SCHEMA, "pending": [], "updated_at": now_iso()}
    data.setdefault("pending", [])
    return data


def _write_requests(data: dict) -> None:
    data["updated_at"] = now_iso()
    write_json(AUTH_REQUESTS_PATH, data)


def _save_request(item: dict) -> None:
    data = _load_requests()
    data["pending"] = [x for x in data["pending"] if x.get("state") != item.get("state")]
    data["pending"].insert(0, item)
    data["pending"] = data["pending"][:100]
    _write_requests(data)


def request_by_state(state: str) -> dict | None:
    wanted = str(state or "").strip()
    for item in _load_requests().get("pending", []):
        if isinstance(item, dict) and item.get("state") == wanted:
            return dict(item)
    return None


def update_request(state: str, **changes) -> dict:
    data = _load_requests(); wanted = str(state or "").strip(); found = None
    for item in data.get("pending", []):
        if isinstance(item, dict) and item.get("state") == wanted:
            item.update(changes); item["updated_at"] = now_iso(); found = dict(item); break
    if found is None:
        raise ValueError("授权请求不存在或已失效")
    _write_requests(data)
    return found


def start_authorization(platform: str, *, slot_label: str = "", redirect_uri: str = "", account_id: str = "") -> dict:
    platform = str(platform or "").strip()
    provider = PROVIDERS.get(platform)
    if not provider:
        raise ValueError("未登记的平台授权适配器")
    public = _public_provider(platform, provider)
    state = secrets.token_urlsafe(24)
    slot_id = secrets.token_hex(12)
    item = {
        "state": state,
        "slot_id": slot_id,
        "account_id": str(account_id or "").strip() or None,
        "platform": platform,
        "slot_label": str(slot_label or "").strip()[:80] or f"{provider['name']}账号",
        "created_at": now_iso(),
        "status": "waiting_owner_authorization",
        "browser_mode": provider.get("browser_mode", "system_external"),
    }

    mode = provider["auth_mode"]
    if mode.startswith("official_portal"):
        item["authorization_url"] = provider["authorization_url"]
        item["status"] = "waiting_owner_portal_login"
        _save_request(item)
        return {
            "ok": True, "platform": platform, "mode": mode,
            "authorization_url": provider["authorization_url"],
            "browser_mode": provider.get("browser_mode"), "state": state,
            "slot_id": slot_id, "slot_label": item["slot_label"],
            "requires_manual_completion": True,
            "truth": "只打开官方平台入口；完成登录/站点验证/API token 配置后仍需真实验证，未自动标记为已连接。",
        }

    if not public.get("configured"):
        item["status"] = "needs_app_credentials"; _save_request(item)
        return {
            "ok": False, "platform": platform, "mode": mode,
            "authorization_url": provider["console_url"],
            "browser_mode": provider.get("browser_mode"), "state": state,
            "slot_id": slot_id, "slot_label": item["slot_label"],
            "needs_app_credentials": True,
            "missing": public.get("credential_names") or [],
            "truth": "官方应用 Client ID/Secret 未配置时，先进入官方控制台申请；不会生成假的 OAuth 登录。",
        }

    client_id = os.environ.get(provider["client_id_env"], "")
    scopes = provider.get("default_scopes") or []
    if provider.get("requires_https_callback") and redirect_uri and not redirect_uri.lower().startswith("https://"):
        item["status"] = "needs_https_callback"; _save_request(item)
        return {
            "ok": False, "platform": platform, "mode": mode,
            "authorization_url": provider["console_url"],
            "browser_mode": provider.get("browser_mode"), "state": state,
            "slot_id": slot_id, "slot_label": item["slot_label"],
            "needs_https_callback": True,
            "truth": "该平台官方要求 HTTPS 回调；本地 127.0.0.1 不能冒充已满足条件。",
        }
    if not redirect_uri:
        raise ValueError("OAuth 平台需要 redirect_uri")

    if platform == "google_search_console":
        params = {"client_id": client_id, "redirect_uri": redirect_uri, "response_type": "code", "scope": " ".join(scopes), "access_type": "offline", "include_granted_scopes": "true", "prompt": "select_account consent", "state": state}
    elif platform == "bing_webmaster":
        params = {"client_id": client_id, "response_type": "code", "redirect_uri": redirect_uri, "scope": " ".join(scopes), "state": state}
    elif platform == "douyin":
        params = {"client_key": client_id, "response_type": "code", "scope": ",".join(scopes), "redirect_uri": redirect_uri, "state": state}
    elif platform == "kuaishou":
        params = {"app_id": client_id, "response_type": "code", "scope": ",".join(scopes), "redirect_uri": redirect_uri, "state": state, "ua": "pc"}
    else:
        raise ValueError("该平台尚未实现 OAuth URL 组装")

    authorization_url = f"{provider['authorization_url']}?{urlencode(params)}"
    item["authorization_url"] = authorization_url
    item["redirect_uri"] = redirect_uri
    item["requested_scopes"] = list(scopes)
    _save_request(item)
    return {
        "ok": True, "platform": platform, "mode": mode,
        "authorization_url": authorization_url,
        "browser_mode": provider.get("browser_mode"), "state": state,
        "slot_id": slot_id, "slot_label": item["slot_label"],
        "requires_manual_completion": False,
        "truth": "仅启动官方授权。只有 state 校验、token 交换和账号身份读取成功后才允许建立/更新账号资产。",
    }


def pending_requests() -> list[dict]:
    return _load_requests().get("pending", [])[:50]
