"""Unified acquisition-channel registry for R8-11.

The registry is a truthful routing/catalog layer, not a claim that every external
platform has already been authenticated.  It deliberately requires no paid
third-party token service.  Social execution uses the existing real-Android
control plane; owned/search channels use local or already-configured Kazuizhi
capabilities.  Human login/verification remains a hard boundary.
"""
from __future__ import annotations

from core.storage import now_iso


CHANNELS = (
    # Social / short video
    {"id": "douyin", "name": "抖音", "group": "short_video", "mode": "real_android_app", "auth": "human_login"},
    {"id": "wechat_channels", "name": "视频号", "group": "short_video", "mode": "real_android_app", "auth": "human_login"},
    {"id": "kuaishou", "name": "快手", "group": "short_video", "mode": "real_android_app", "auth": "human_login"},
    {"id": "xiaohongshu", "name": "小红书", "group": "social_content", "mode": "real_android_app", "auth": "human_login"},
    {"id": "bilibili", "name": "B站", "group": "short_video", "mode": "real_android_app", "auth": "human_login"},
    {"id": "weibo", "name": "微博", "group": "social_content", "mode": "real_android_app", "auth": "human_login"},
    # Search / GEO
    {"id": "baidu_search", "name": "百度搜索 / GEO", "group": "search", "mode": "content_and_indexing", "auth": "public_or_owned"},
    {"id": "wechat_search", "name": "微信搜一搜", "group": "search", "mode": "content_and_indexing", "auth": "public_or_owned"},
    {"id": "sogou_search", "name": "搜狗搜索", "group": "search", "mode": "content_and_indexing", "auth": "public"},
    {"id": "360_search", "name": "360搜索", "group": "search", "mode": "content_and_indexing", "auth": "public"},
    # Local exposure
    {"id": "maps_local", "name": "地图 / 本地信息", "group": "local_discovery", "mode": "manual_or_browser_assisted", "auth": "human_login_if_needed"},
    {"id": "local_life", "name": "本地生活平台", "group": "local_discovery", "mode": "manual_or_browser_assisted", "auth": "human_login"},
    # Community / Q&A
    {"id": "qa", "name": "问答渠道", "group": "community", "mode": "content_routing", "auth": "human_login_if_needed"},
    {"id": "forum", "name": "论坛 / 本地社区", "group": "community", "mode": "content_routing", "auth": "human_login_if_needed"},
    # Owned properties
    {"id": "website", "name": "官网 / 落地页", "group": "owned", "mode": "owned_web", "auth": "owned"},
    {"id": "mini_program", "name": "微信小程序", "group": "owned", "mode": "owned_mini_program", "auth": "owned"},
)

SOCIAL_IDS = {"douyin", "wechat_channels", "kuaishou", "xiaohongshu", "bilibili", "weibo"}
SEARCH_IDS = {"baidu_search", "wechat_search", "sogou_search", "360_search"}


def _social_state() -> dict:
    try:
        from core.r8_control import social_center_status
        return social_center_status()
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError):
        return {"platforms": [], "devices": [], "accounts": []}


def _search_state() -> dict:
    try:
        from promotion.search_growth import status
        value = status()
        return value if isinstance(value, dict) else {}
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError):
        return {}


def _business_state() -> dict:
    try:
        from integrations.business_data import business_source_status
        from analytics.business_metrics import build_analytics
        value = business_source_status(build_analytics())
        return value if isinstance(value, dict) else {}
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError):
        return {}


def _social_row(channel: dict, social: dict) -> dict:
    platform = next((x for x in social.get("platforms", []) if x.get("id") == channel["id"]), {})
    accounts = [x for x in social.get("accounts", []) if x.get("platform") == channel["id"]]
    devices = {x.get("device_id"): x for x in social.get("devices", [])}
    authorized = [x for x in accounts if x.get("login_status") == "authorized"]
    online_authorized = [
        x for x in authorized
        if (devices.get(x.get("device_id")) or {}).get("connection") == "connected"
        and (devices.get(x.get("device_id")) or {}).get("probe_source") == "adb"
    ]
    external_verified = bool(online_authorized)
    if external_verified:
        state = "ready_for_dry_run"
    elif accounts:
        state = "needs_login_or_device_validation"
    else:
        state = "not_bound"
    return {
        **channel,
        "software_route_ready": True,
        "external_verified": external_verified,
        "state": state,
        "accounts": len(accounts),
        "authorized_accounts": len(authorized),
        "online_authorized_accounts": len(online_authorized),
        "platform_attention": int(platform.get("attention") or 0),
        "execution": "ADB real-device serial execution",
        "human_gates": ["login", "captcha", "sms", "face_verification", "final_publish_approval"],
        "paid_token_required": False,
        "token_policy": "不购买第三方平台 Token；使用真实账号人工登录 + 本机真实 Android 执行。",
    }


def _non_social_row(channel: dict, search: dict, business: dict) -> dict:
    cid = channel["id"]
    external_verified = False
    evidence = ""
    if cid in SEARCH_IDS:
        audit = search.get("latest_audit") or {}
        external_verified = bool(audit)
        evidence = "已有搜索增长审计" if external_verified else "等待真实抓取/收录证据"
    elif cid == "website":
        audit = search.get("latest_audit") or {}
        external_verified = bool(audit)
        evidence = "官网技术状态已有本地审计" if external_verified else "等待官网真实部署/抓取审计"
    elif cid == "mini_program":
        status = str(business.get("status") or business.get("connection_status") or "").lower()
        external_verified = status in {"verified", "connected", "ready", "ok"}
        evidence = "经营数据源已验证" if external_verified else "等待小程序/经营数据真实验证"
    else:
        evidence = "已纳入统一路由；外部账号/页面尚未现场验证"
    return {
        **channel,
        "software_route_ready": True,
        "external_verified": external_verified,
        "state": "verified_read_or_owned" if external_verified else "registered_pending_field_validation",
        "execution": channel["mode"],
        "human_gates": ["login_or_verification"] if "human" in channel["auth"] else [],
        "paid_token_required": False,
        "token_policy": "核心路由不依赖付费第三方 Token；需要登录的平台由真人登录/验证。",
        "evidence": evidence,
    }


def snapshot() -> dict:
    social = _social_state()
    search = _search_state()
    business = _business_state()
    rows = []
    for channel in CHANNELS:
        rows.append(_social_row(channel, social) if channel["id"] in SOCIAL_IDS else _non_social_row(channel, search, business))
    return {
        "schema": "kz.channel-registry.v1",
        "generated_at": now_iso(),
        "channels": rows,
        "summary": {
            "registered": len(rows),
            "software_route_ready": sum(1 for x in rows if x.get("software_route_ready")),
            "externally_verified": sum(1 for x in rows if x.get("external_verified")),
            "paid_token_required": 0,
        },
        "policy": {
            "no_paid_third_party_token_required": True,
            "social_execution": "真实安卓 + 真实账号；验证码/短信/人脸由真人完成",
            "external_truth": "纳入软件路由不等于平台已登录/已发布；只有真实账号验证和真实平台回执才能升级状态。",
            "finance": "资金操作永久人工处理",
        },
    }
