"""R8-12 durable account/authorization/device route planner.

Mission routing never re-binds an account. It selects a stable Account Asset and
then chooses the safest available execution channel. Official API is used only
when a real publish scope is recorded; otherwise a verified real device is the
fallback. No branch here claims publication success.
"""
from __future__ import annotations

from core.account_registry import migrate_legacy_assets, snapshot, sync_device_health
from integrations.oauth_adapters import provider_status

PLATFORM_ALIASES = {
    "抖音": "douyin", "douyin": "douyin", "快手": "kuaishou", "kuaishou": "kuaishou",
    "小红书": "xiaohongshu", "xiaohongshu": "xiaohongshu", "视频号": "wechat_channels",
    "微信视频号": "wechat_channels", "wechat_channels": "wechat_channels", "微博": "weibo", "weibo": "weibo",
    "B站": "bilibili", "哔哩哔哩": "bilibili", "bilibili": "bilibili",
}
PUBLISH_SCOPE_HINTS = {"publish", "video_publish", "video.publish", "content_publish", "content.publish", "user_video_publish"}


def normalize_platform(value):
    text = str(value or "").strip()
    return PLATFORM_ALIASES.get(text, text)


def _service_match(scope, service):
    if scope.get("all_local_services"): return True
    wanted = str(service or "").strip()
    return not wanted or wanted in (scope.get("services") or [])


def _region_match(scope, region):
    if scope.get("all_regions"): return True
    wanted = str(region or "").strip()
    if wanted == "涟水": wanted = "涟水县"
    return not wanted or wanted in (scope.get("regions") or [])


def _has_publish_scope(account):
    scopes = {str(x or "").strip().lower() for x in (account.get("authorized_scopes") or [])}
    return bool(scopes & PUBLISH_SCOPE_HINTS)


def _device_ready(device):
    return isinstance(device, dict) and device.get("connection") == "connected" and str(device.get("health") or "").lower() not in {"blocked", "high_risk", "failed"}


def _refresh_live_assets():
    """Best-effort legacy migration + real ADB liveness refresh.

    Failing to scan a phone never destroys the last durable identity/device
    record. It only means this routing attempt uses the current stored health.
    """
    try:
        migrate_legacy_assets()
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError):
        pass
    try:
        from integrations import android_device
        sync_device_health(android_device.scan_and_sync())
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError):
        pass


def route_account(*, platform, region="", service="", require_publish=True, refresh_devices=True):
    if refresh_devices:
        _refresh_live_assets()
    platform_code = normalize_platform(platform)
    data = snapshot()
    devices = {x.get("device_id"): x for x in data.get("devices", []) if isinstance(x, dict)}
    eligible, auth_blocked, limited = [], [], []

    for account in data.get("accounts", []):
        if not isinstance(account, dict) or normalize_platform(account.get("platform")) != platform_code: continue
        if not _region_match(account.get("region_scope") or {}, region): continue
        if not _service_match(account.get("service_scope") or {}, service): continue
        if account.get("auth_status") == "platform_limited": limited.append(account); continue
        if account.get("auth_status") != "connected": auth_blocked.append(account); continue
        device = devices.get(account.get("preferred_device_id"))
        official = provider_status(platform_code)
        eligible.append({
            "account": account, "device": device, "official": official,
            "api_ready": bool(require_publish and official.get("configured") and _has_publish_scope(account)),
            "device_ready": _device_ready(device),
        })

    if eligible:
        eligible.sort(key=lambda row: (bool(row["api_ready"]), bool(row["device_ready"]), str(row["account"].get("updated_at") or "")), reverse=True)
        choice = eligible[0]; account, device = choice["account"], choice["device"]
        if choice["api_ready"]:
            return {
                "status": "ready", "owner_status": "已连接", "account": account, "account_id": account.get("account_id"),
                "device": device, "device_id": device.get("device_id") if isinstance(device, dict) else None,
                "route_kind": "official_api", "route": "official_api", "platform": platform_code,
                "truth": "官方应用已配置且账号记录真实发布 scope；最终成功仍必须回收平台 Content/Post ID + URL / Receipt。",
            }
        if choice["device_ready"]:
            return {
                "status": "ready", "owner_status": "已连接", "account": account, "account_id": account.get("account_id"),
                "device": device, "device_id": device.get("device_id"), "route_kind": "real_device", "route": "real_device", "platform": platform_code,
                "truth": "账号身份与设备解耦；当前由在线真实设备执行，最终成功仍必须有真实平台回执。",
            }
        return {
            "status": "device_offline", "owner_status": "设备离线", "account": account, "account_id": account.get("account_id"),
            "device": device, "device_id": device.get("device_id") if isinstance(device, dict) else account.get("preferred_device_id"),
            "route_kind": "wait_device", "route": "wait_device", "platform": platform_code,
            "reason": "账号身份有效，但当前没有已批准的官方发布 API 路径，且首选真实设备不在线。",
        }

    if auth_blocked:
        account = auth_blocked[0]
        return {
            "status": "needs_authorization", "owner_status": "需授权", "account": account, "account_id": account.get("account_id"),
            "device": None, "device_id": account.get("preferred_device_id"), "route_kind": "reauthorize", "route": "reauthorize", "platform": platform_code,
            "reason": "永久账号仍保留，只需要重新授权，不需要重新绑定 Mission、服务或手机。",
        }
    if limited:
        account = limited[0]
        return {
            "status": "platform_limited", "owner_status": "平台限制", "account": account, "account_id": account.get("account_id"),
            "device": None, "device_id": account.get("preferred_device_id"), "route_kind": "platform_limited", "route": "platform_limited", "platform": platform_code,
            "reason": "账号资产存在，但平台当前能力/审批不允许自动执行。",
        }
    return {
        "status": "no_matching_account", "owner_status": "未添加账号", "account": None, "account_id": None,
        "device": None, "device_id": None, "route_kind": "add_account", "route": "add_account", "platform": platform_code,
        "reason": "当前没有覆盖该平台/区域/服务范围的永久账号资产。",
    }
