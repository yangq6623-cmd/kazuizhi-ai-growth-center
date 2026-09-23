"""R8 V2.2.1 deep productization compatibility layer.

This patch intentionally keeps the existing R7/R8 APIs and state machines while
closing several product gaps found during real UI acceptance:
- one durable active Growth ID across pages;
- one truthful owner-action source for dashboard/sidebar badges;
- no duplicate active video job for the same campaign;
- factory publish eligibility derived from the real device/social control plane;
- no user-written "verified publish" state;
- explicit active-campaign API without changing the legacy server router.

It is imported after the V2 content-factory extensions so server import-time
aliases are repointed to the final semantics.
"""
from __future__ import annotations

import json
from urllib.parse import urlsplit

from core.storage import now_iso
from core import r8_control
from promotion import content_factory as cf


_INSTALLED = False
_ORIGINAL = {}
ACTIVE_VIDEO_STATES = {
    "等待ChatGPT策划", "等待素材路由", "等待生产", "生产中", "技术质检", "等待ChatGPT质检",
    "等待人工审核", "退回重做", "已授权发布", "等待账号", "等待最佳时间", "发布执行中", "异常待处理",
}
PLATFORM_NAME = {
    "douyin": "抖音", "xiaohongshu": "小红书", "kuaishou": "快手",
    "wechat_channels": "视频号", "weibo": "微博", "bilibili": "哔哩哔哩",
    "forum": "论坛/社区", "blog": "博客/内容站", "other": "其他平台",
}


def _active_id(data):
    campaigns = data.get("campaigns") or []
    valid = {item.get("id") for item in campaigns}
    active = str(data.get("active_campaign_id") or "").strip()
    if active in valid:
        return active
    return str(campaigns[0].get("id") or "") if campaigns else ""


def set_active_campaign(payload):
    data = cf._load()
    campaign_id = cf._clean((payload or {}).get("campaign_id"), "增长ID", 64)
    cf._by_id(data.get("campaigns", []), campaign_id, "增长任务")
    data["active_campaign_id"] = campaign_id
    data["active_campaign_updated_at"] = now_iso()
    cf._save(data)
    return {"active_campaign_id": campaign_id, "updated_at": data["active_campaign_updated_at"]}


def create_campaign(payload):
    item = _ORIGINAL["create_campaign"](payload)
    data = cf._load()
    data["active_campaign_id"] = item["id"]
    data["active_campaign_updated_at"] = now_iso()
    cf._save(data)
    return item


def create_video(payload):
    data = cf._load()
    campaign_id = cf._clean((payload or {}).get("campaign_id"), "增长ID", 64)
    cf._by_id(data.get("campaigns", []), campaign_id, "增长任务")
    existing = next(
        (item for item in data.get("videos", [])
         if item.get("campaign_id") == campaign_id and item.get("status") in ACTIVE_VIDEO_STATES),
        None,
    )
    if existing:
        raise ValueError(f"该增长战役已有生产任务 {existing.get('id')}（{existing.get('status')}），请等待当前任务完成或处理后再创建")
    result = _ORIGINAL["create_video"](payload)
    data = cf._load()
    data["active_campaign_id"] = campaign_id
    data["active_campaign_updated_at"] = now_iso()
    cf._save(data)
    return result


def save_account(payload):
    """Keep legacy account metadata route, but never accept a user-written verified state."""
    values = dict(payload or {})
    values.pop("connection_status", None)
    requested_id = str(values.get("id") or "").strip()
    data = cf._load()
    existing = next((x for x in data.get("accounts", []) if requested_id and x.get("id") == requested_id), None)
    values["connection_status"] = (
        existing.get("connection_status")
        if existing and existing.get("verification_source") in {"r8_social_control", "official_connector", "platform_probe"}
        else "待人工登录授权"
    )
    item = _ORIGINAL["save_account"](values)
    data = cf._load()
    current = cf._by_id(data.get("accounts", []), item["id"], "账号")
    if current.get("verification_source") not in {"r8_social_control", "official_connector", "platform_probe"}:
        current["connection_status"] = "待人工登录授权"
        current["verification_source"] = "metadata_only"
        current["verified_at"] = None
    cf._save(data)
    return current


def _social_snapshot():
    try:
        return r8_control.social_center_status()
    except (OSError, ValueError, RuntimeError):
        return {"accounts": [], "devices": [], "terminals": []}


def _social_connection_status(account, device_online):
    login = str(account.get("login_status") or "not_verified")
    risk = str(account.get("risk_level") or "unknown")
    paused = bool(account.get("automation_paused"))
    if login in {"needs_human", "logged_out"} or risk in {"attention", "high"}:
        return "需要人工处理"
    if login == "authorized" and device_online and not paused:
        return "已验证可发布"
    if login == "authorized" and not device_online:
        return "等待真机上线"
    if paused:
        return "已暂停"
    return "待人工登录授权"


def sync_accounts_from_control():
    """Mirror routing metadata into the content factory from the real control plane.

    The content factory never upgrades an account to verified on its own. A
    verified state requires: control-plane login_status=authorized, the bound
    ADB device online, no attention/high risk, and automation not paused.
    """
    social = _social_snapshot()
    devices = social.get("devices") or []
    online_ids = {
        item.get("device_id") for item in devices
        if item.get("connection") == "connected" and item.get("probe_source") == "adb"
    }
    data = cf._load()
    factory_accounts = data.setdefault("accounts", [])
    seen = set()
    for account in social.get("accounts") or []:
        social_id = str(account.get("account_id") or "").strip()
        if not social_id:
            continue
        seen.add(social_id)
        existing = next((x for x in factory_accounts if x.get("social_account_id") == social_id), None)
        if not existing:
            existing = next(
                (x for x in factory_accounts
                 if x.get("platform") == (account.get("platform_name") or PLATFORM_NAME.get(account.get("platform")))
                 and x.get("account_name") == (account.get("alias") or account.get("label"))
                 and x.get("device_id") == account.get("device_id")),
                None,
            )
        if not existing:
            existing = {"id": social_id}
            factory_accounts.append(existing)
        status = _social_connection_status(account, account.get("device_id") in online_ids)
        existing.update({
            "social_account_id": social_id,
            "platform_id": account.get("platform"),
            "platform": account.get("platform_name") or PLATFORM_NAME.get(account.get("platform"), account.get("platform") or "其他"),
            "account_name": account.get("alias") or account.get("label") or "未命名账号",
            "region": account.get("region") or existing.get("region") or "",
            "service": account.get("service_category") or existing.get("service") or "",
            "connection_status": status,
            "device_id": account.get("device_id") or "",
            "daily_limit": max(1, min(int(existing.get("daily_limit") or 1), 3)),
            "preferred_windows": existing.get("preferred_windows") or [],
            "verification_source": "r8_social_control",
            "login_status": account.get("login_status") or "not_verified",
            "risk_level": account.get("risk_level") or "unknown",
            "verified_at": account.get("login_verified_at") if status == "已验证可发布" else None,
            "synced_at": now_iso(),
        })
    # Legacy/manual metadata may remain visible, but can never retain a verified
    # publish state without a matching control-plane account.
    for item in factory_accounts:
        social_id = str(item.get("social_account_id") or "")
        if social_id and social_id in seen:
            continue
        if item.get("verification_source") != "official_connector":
            item["connection_status"] = "待人工登录授权"
            item["verified_at"] = None
            item.setdefault("verification_source", "metadata_only")
    cf._save(data)
    return social


def _current_mission_videos(data):
    """Return only the foreground production chain for the active Mission.

    Historic failed video attempts must remain auditable, but once the same
    Mission has a newer production task that is progressing normally they must
    not keep the owner badge in a permanent red state. The content factory now
    allows only one active video per campaign, so the newest timestamp is the
    authoritative foreground task for legacy data that predates that rule.
    """
    videos = data.get("videos") or []
    active = _active_id(data)
    if not active:
        return []
    scoped = [item for item in videos if item.get("campaign_id") == active]
    if not scoped:
        return []

    def _stamp(item):
        return str(
            item.get("runtime_updated_at")
            or item.get("plan_received_at")
            or item.get("requested_at")
            or item.get("created_at")
            or ""
        )

    return [max(scoped, key=_stamp)]


def _human_action_center(data, social):
    videos = _current_mission_videos(data)
    items = []
    waiting_review = [x for x in videos if x.get("status") == "等待人工审核"]
    if waiting_review:
        items.append({
            "id": "final_review", "kind": "human", "page": "content", "action": "去审核",
            "title": f"{len(waiting_review)} 条最终成片等待确认",
            "detail": "只有当前 Mission 的最终成片需要老板决定：通过并发布、退回重做或暂不发布。",
        })
    social_accounts = social.get("accounts") or []
    needs_human = [
        x for x in social_accounts
        if x.get("login_status") in {"needs_human", "logged_out"}
        or x.get("risk_level") in {"attention", "high"}
    ]
    if needs_human:
        items.append({
            "id": "account_human", "kind": "human", "page": "accounts", "action": "去处理",
            "title": f"{len(needs_human)} 个账号需要人工验证",
            "detail": "验证码、人脸、异常登录或平台风险必须由账号本人处理。",
        })
    abnormal = [x for x in videos if x.get("status") == "异常待处理" and int(x.get("retry_count") or 0) >= 3]
    if abnormal:
        items.append({
            "id": "production_exception", "kind": "human", "page": "content", "action": "查看异常",
            "title": f"{len(abnormal)} 个当前生产任务自动恢复失败",
            "detail": "当前 Mission 的前台生产任务已达到自动重试/降级上限，需要人工确认后续处理；历史失败不会继续占用待办红点。",
        })
    awaiting_execution = any(x.get("status") in {"已授权发布", "等待账号", "等待最佳时间", "发布执行中"} for x in videos)
    online = any(
        item.get("connection") == "connected" and item.get("probe_source") == "adb"
        for item in (social.get("devices") or [])
    )
    if awaiting_execution and not online:
        items.append({
            "id": "device_required", "kind": "human", "page": "device", "action": "检查终端",
            "title": "当前 Mission 有待发布任务，但真实手机未在线",
            "detail": "只有发布链实际需要终端时，设备离线才计入“待我处理”。",
        })
    current_video = videos[0] if videos else None
    return {
        "human_count": len(items),
        "human_items": items,
        "scope": "active_mission",
        "active_campaign_id": _active_id(data) or None,
        "current_video_id": current_video.get("id") if current_video else None,
        "updated_at": now_iso(),
    }


def dashboard():
    social = sync_accounts_from_control()
    data = cf._load()
    active = _active_id(data)
    if active and data.get("active_campaign_id") != active:
        data["active_campaign_id"] = active
        data["active_campaign_updated_at"] = now_iso()
        cf._save(data)
    value = _ORIGINAL["dashboard"]()
    value["active_campaign_id"] = active or None
    value["action_center"] = _human_action_center(data, social)
    value["social_truth"] = {
        "accounts": social.get("accounts") or [],
        "devices": social.get("devices") or [],
        "terminals": social.get("terminals") or [],
        "source": "r8_social_control",
    }
    return value


def update_account_status(payload):
    """Do not allow an arbitrary UI/API field to claim a real login verification."""
    values = dict(payload or {})
    if str(values.get("login_status") or "") == "authorized":
        source = str(values.get("verification_source") or "").strip()
        if source not in {"platform_probe", "device_probe", "official_connector"}:
            raise ValueError("账号“已验证可发布”只能由真实平台/终端验证器写入，不能人工选择")
    values.pop("verification_source", None)
    return _ORIGINAL["update_account_status"](values)


def _read_json_body(handler):
    length = int(handler.headers.get("Content-Length", "0"))
    if length > 64 * 1024:
        raise ValueError("请求内容过大")
    return json.loads(handler.rfile.read(length) or b"{}")


def _origin_allowed(handler):
    origin = handler.headers.get("Origin")
    return not origin or origin in {
        f"http://127.0.0.1:{handler.server.server_port}",
        f"http://localhost:{handler.server.server_port}",
    }


def install():
    global _INSTALLED
    if _INSTALLED:
        return
    _ORIGINAL.update({
        "create_campaign": cf.create_campaign,
        "create_video": cf.create_video,
        "save_account": cf.save_account,
        "dashboard": cf.dashboard,
        "update_account_status": r8_control.update_account_status,
    })
    cf.create_campaign = create_campaign
    cf.create_video = create_video
    cf.save_account = save_account
    cf.dashboard = dashboard
    cf.set_active_campaign = set_active_campaign
    cf.sync_accounts_from_control = sync_accounts_from_control
    r8_control.update_account_status = update_account_status

    from backend import server
    server.factory_create_campaign = create_campaign
    server.factory_create_video = create_video
    server.factory_save_account = save_account
    server.content_factory_dashboard = dashboard
    server.update_account_status = update_account_status

    # Asset intake is patched separately but its server alias was captured at
    # import time, so always repoint it to the final implementation.
    try:
        from promotion import asset_intake
        server.receive_factory_asset = asset_intake.receive
    except (ImportError, AttributeError):
        pass

    original_post = server.DashboardHandler.do_POST

    def do_post(handler):
        path = urlsplit(handler.path).path
        if path == "/api/content-factory/active-campaign":
            if not _origin_allowed(handler):
                handler.send_error(403, "Cross-origin changes are not allowed")
                return
            try:
                result = set_active_campaign(_read_json_body(handler))
            except (ValueError, json.JSONDecodeError, OSError) as error:
                handler._json_error(400, error)
                return
            handler._json_ok(result, code=200)
            return
        return original_post(handler)

    server.DashboardHandler.do_POST = do_post
    _INSTALLED = True


install()
