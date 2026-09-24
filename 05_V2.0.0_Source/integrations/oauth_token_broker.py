"""Provider OAuth callback/token broker for durable multi-account assets.

Security properties:
- validates state and request freshness before token exchange
- performs token exchange only against registered HTTPS official endpoints
- stores access/refresh tokens only in the Windows DPAPI credential vault
- stores only non-secret metadata in the Account Registry
- never logs authorization codes or token values
- never treats login/consent success as publish success
"""
from __future__ import annotations

import json
import os
from datetime import datetime, timedelta
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from core.storage import now_iso
from integrations.account_environment import observe
from integrations.credential_vault import put_secret
from integrations.official_account_assets import upsert_official_account
from integrations.platform_auth_catalog import PROVIDERS, request_by_state, update_request

MAX_REQUEST_AGE = timedelta(minutes=10)


def _parse_time(value: str) -> datetime:
    return datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))


def _validate_request(platform: str, state: str) -> dict:
    item = request_by_state(state)
    if not item:
        raise ValueError("授权 state 不存在或已失效")
    if item.get("platform") != platform:
        raise ValueError("授权平台与 state 不匹配")
    created = _parse_time(item.get("created_at"))
    now = datetime.now().astimezone()
    if created.tzinfo is None:
        created = created.astimezone()
    if now - created > MAX_REQUEST_AGE:
        update_request(state, status="expired", error="authorization_request_expired")
        raise ValueError("授权请求已超过10分钟，请重新发起")
    if item.get("status") not in {"waiting_owner_authorization", "callback_received"}:
        raise ValueError(f"授权请求当前状态不可回调：{item.get('status')}")
    return item


def _decode_response(raw: bytes) -> dict:
    value = json.loads(raw.decode("utf-8"))
    if not isinstance(value, dict):
        raise ValueError("平台 token 响应格式异常")
    return value


def _token_payload(platform: str, code: str, item: dict) -> tuple[str, dict, str]:
    provider = PROVIDERS[platform]
    client_id = os.environ.get(provider.get("client_id_env") or "", "")
    client_secret = os.environ.get(provider.get("client_secret_env") or "", "")
    if not client_id or not client_secret:
        raise ValueError("官方应用 Client ID/Secret 尚未配置")
    redirect_uri = str(item.get("redirect_uri") or "")
    if platform == "google_search_console":
        params = {"code": code, "client_id": client_id, "client_secret": client_secret, "redirect_uri": redirect_uri, "grant_type": "authorization_code"}
    elif platform == "bing_webmaster":
        params = {"code": code, "client_id": client_id, "client_secret": client_secret, "redirect_uri": redirect_uri, "grant_type": "authorization_code"}
    elif platform == "douyin":
        params = {"code": code, "client_key": client_id, "client_secret": client_secret, "grant_type": "authorization_code"}
    elif platform == "kuaishou":
        params = {"code": code, "app_id": client_id, "app_secret": client_secret}
    else:
        raise ValueError("该平台尚未实现 token 交换")
    return provider["token_url"], params, provider.get("token_method") or "POST_FORM"


def _exchange(platform: str, code: str, item: dict) -> dict:
    token_url, params, method = _token_payload(platform, code, item)
    if not str(token_url or "").lower().startswith("https://"):
        raise ValueError("token 交换必须使用 HTTPS 官方端点")
    encoded = urlencode(params).encode("utf-8")
    if method == "GET_QUERY":
        request = Request(f"{token_url}?{encoded.decode('ascii')}", method="GET", headers={"Accept": "application/json"})
    else:
        request = Request(token_url, data=encoded, method="POST", headers={"Content-Type": "application/x-www-form-urlencoded", "Accept": "application/json"})
    with urlopen(request, timeout=20) as response:  # nosec B310 - URL restricted to registered HTTPS provider endpoints
        result = _decode_response(response.read())
    if platform == "douyin":
        result = result.get("data") if isinstance(result.get("data"), dict) else result
        if result.get("error_code") not in {None, 0, "0"}:
            raise ValueError("抖音 token 交换失败")
    if platform == "kuaishou" and result.get("result") not in {None, 1, "1"}:
        raise ValueError("快手 token 交换失败")
    if not result.get("access_token"):
        raise ValueError("平台未返回 access_token")
    return result


def _scopes(platform: str, result: dict, item: dict) -> list[str]:
    raw = result.get("scope") or result.get("scopes") or item.get("requested_scopes") or []
    if isinstance(raw, str):
        pieces = raw.replace(",", " ").split()
    elif isinstance(raw, list):
        pieces = raw
    else:
        pieces = []
    return sorted(set(str(x).strip() for x in pieces if str(x).strip()))


def _subject(platform: str, result: dict) -> str | None:
    return str(result.get("open_id") or result.get("openId") or result.get("sub") or "").strip() or None


def _expiry(result: dict) -> str | None:
    try:
        seconds = int(result.get("expires_in") or 0)
    except (TypeError, ValueError):
        seconds = 0
    if seconds <= 0:
        return None
    return (datetime.now().astimezone() + timedelta(seconds=seconds)).isoformat(timespec="seconds")


def complete_authorization(platform: str, *, state: str, code: str, error: str = "", error_description: str = "") -> dict:
    platform = str(platform or "").strip(); state = str(state or "").strip(); code = str(code or "").strip()
    if platform not in PROVIDERS:
        raise ValueError("未登记的平台")
    item = _validate_request(platform, state)
    if error:
        update_request(state, status="denied", error=str(error)[:120], error_description=str(error_description or "")[:240])
        return {"ok": False, "status": "denied", "platform": platform, "truth": "用户或平台拒绝授权，账号不会被标记为已连接。"}
    if not code:
        raise ValueError("授权回调缺少 code")
    update_request(state, status="callback_received")
    result = _exchange(platform, code, item)
    asset = upsert_official_account(
        platform=platform,
        slot_id=str(item.get("slot_id") or ""),
        slot_label=str(item.get("slot_label") or ""),
        scopes=_scopes(platform, result, item),
        platform_subject_id=_subject(platform, result),
        expires_at=_expiry(result),
        account_id=str(item.get("account_id") or "") or None,
    )
    account_id = asset["account_id"]
    put_secret(f"oauth.{account_id}.access_token", str(result["access_token"]))
    refresh_token = str(result.get("refresh_token") or "").strip()
    if refresh_token:
        put_secret(f"oauth.{account_id}.refresh_token", refresh_token)
    observe(account_id)
    update_request(
        state,
        status="authorized",
        account_id=account_id,
        completed_at=now_iso(),
        has_refresh_token=bool(refresh_token),
        authorized_scopes=asset.get("authorized_scopes") or [],
    )
    return {
        "ok": True,
        "status": "authorized",
        "platform": platform,
        "account_id": account_id,
        "display_name": asset.get("display_name"),
        "authorized_scopes": asset.get("authorized_scopes") or [],
        "truth": "官方授权和 token 交换已成功；这只代表账号连接成功，不代表任何内容已经发布。",
    }
