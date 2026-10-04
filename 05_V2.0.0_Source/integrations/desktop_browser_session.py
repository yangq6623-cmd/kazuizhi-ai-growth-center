"""PC browser QR-login sessions for social-platform workspaces.

The platform never controls a phone or stores a platform password.  Login takes
place in the user's normal Windows browser profile; this registry only records
which platform page was opened and the owner's confirmation that the QR login
has completed.  A confirmation is *not* a publication receipt.
"""
from __future__ import annotations

import webbrowser

from core.storage import now_iso, read_json, write_json

STATE_PATH = "r8_12/desktop_browser_sessions.json"
PLATFORM_URLS = {
    "douyin": "https://creator.douyin.com/",
    "kuaishou": "https://cp.kuaishou.com/",
    "xiaohongshu": "https://creator.xiaohongshu.com/",
    "wechat_channels": "https://channels.weixin.qq.com/",
    "weibo": "https://weibo.com/",
    "bilibili": "https://member.bilibili.com/platform/home",
    "forum": "https://www.baidu.com/",
    "blog": "https://www.baidu.com/",
}


def _state():
    value = read_json(STATE_PATH, {})
    if not isinstance(value, dict): value = {}
    value.setdefault("schema", "kz.desktop-browser-session.v1")
    value.setdefault("sessions", [])
    return value


def _save(value):
    value["updated_at"] = now_iso()
    write_json(STATE_PATH, value)
    return value


def _normalise(value):
    return str(value or "").strip().lower()


def sessions():
    return list(_state().get("sessions") or [])


def for_account(account_id):
    account_id = str(account_id or "").strip()
    return next((item for item in sessions() if item.get("account_id") == account_id), None)


def is_ready(account_id):
    item = for_account(account_id)
    return bool(item and item.get("status") == "owner_confirmed")


def begin_qr_login(*, platform, account_id, account_alias=""):
    platform, account_id = _normalise(platform), str(account_id or "").strip()
    if not platform or not account_id: raise ValueError("缺少平台或账号资产")
    url = PLATFORM_URLS.get(platform)
    if not url: raise ValueError("该平台暂未配置 PC 网页扫码入口")
    value = _state(); rows = value["sessions"]
    item = next((row for row in rows if row.get("account_id") == account_id), None)
    if item is None:
        item = {"account_id": account_id, "platform": platform, "created_at": now_iso()}
        rows.append(item)
    item.update({
        "platform": platform, "account_alias": str(account_alias or "").strip()[:120],
        "browser_url": url, "status": "awaiting_qr_scan", "opened_at": now_iso(),
        "last_action": "已在 Windows 默认浏览器打开平台官网，请在电脑页面扫码登录",
        "updated_at": now_iso(),
    })
    _save(value)
    opened = bool(webbrowser.open(url, new=2))
    return {"session": item, "opened": opened, "truth": "已打开 PC 网页登录入口；只有老板确认完成扫码后才会作为浏览器会话路由，仍不代表发布成功。"}


def confirm_qr_login(*, account_id):
    account_id = str(account_id or "").strip()
    value = _state(); item = next((row for row in value["sessions"] if row.get("account_id") == account_id), None)
    if item is None: raise ValueError("请先打开该平台的 PC 扫码登录页")
    item.update({"status": "owner_confirmed", "confirmed_at": now_iso(), "updated_at": now_iso(), "last_action": "老板确认 Windows 浏览器扫码登录完成"})
    _save(value)
    return {"session": item, "truth": "这是老板确认的 PC 浏览器会话；发布成功仍必须取得平台 URL / Post ID / Receipt。"}


def clear_sessions():
    value = _state(); count = len(value.get("sessions") or [])
    value["sessions"] = []; _save(value)
    return {"cleared": count}
