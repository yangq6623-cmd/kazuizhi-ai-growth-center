"""R8-12 durable account/authorization/device route planner.

Mission routing never re-binds an account.  It selects a stable Account Asset and
then chooses the safest currently-available execution channel:

1. official API only when the official adapter is configured AND the durable
   account records an actually granted publish scope;
2. otherwise a verified real-device path when the preferred device is online;
3. otherwise a truthful owner-facing blocker.

No branch here claims that content was published.
"""
from __future__ import annotations

from core.account_registry import snapshot
from integrations.oauth_adapters import provider_status

PLATFORM_ALIASES = {
    "抖音": "douyin",
    "douyin": "douyin",
    "快手": "kuaishou",
    "kuaishou": "kuaishou",
    "小红书": "xiaohongshu",
    "xiaohongshu": "xiaohongshu",
    "视频号": "wechat_channels",
    "微信视频号": "wechat_channels",
    "wechat_channels": "wechat_channels",
    "微博": "weibo",
    "weibo": "weibo",
    "B站": "bilibili",
    "哔哩哔哩": "bilibili",
    "bilibili": "bilibili",
}

# These are capability labels stored only after a real authorization adapter or
# administrator configuration records them.  Merely configuring Client ID/Secret
# does not grant any of these scopes.
PUBLISH_SCOPE_HINTS = {
    "publish",
    "video_publish",
    "video.publish",
    "content_publish",
    "content.publish",
    "user_video_publish",
}


def normalize_platform(value: str) -> str:
    text = str(value or "").strip()
    return PLATFORM_ALIASES.get(text, text)


def _service_match(scope: dict, service: str) -> bool:
    if scope.get("all_local_services"):
        return True
    wanted = str(service or "").strip()
    return not wanted or wanted in (scope.get("services") or [])


def _region_match(scope: dict, region: str) -> bool:
    if scope.get("all_regions"):
        return True
    wanted = str(region or "").strip()
    if wanted == "涟水":
        wanted = "涟水县"
    return not wanted or wanted in (scope.get("regions") or [])


def _has_publish_scope(account: dict) -> bool:
    scopes = {str(x or "").strip().lower() for x in (account.get("authorized_scopes") or [])}
    return bool(scopes & PUBLISH_SCOPE_HINTS)


def _device_ready(device: dict | None) -> bool:
    if not isinstance(device, dict):
        return False
    return device.get("connection") == "connected" and str(device.get("health") or "").lower() not in {"blocked", "high_risk", "failed"}


def route_account(*, platform: str, region: str = "", service: str = "", require_publish=True) -> dict:
    """Resolve one stable account and an execution route for a Mission.

    The returned ``account_id`` is durable.  ``device_id`` is optional and may
    change later without changing the account identity.
    """
    platform_code = normalize_platform(platform)
    data = snapshot()
    devices = {x.get("device_id"): x for x in data.get("devices", []) if isinstance(x, dict)}
    eligible = []
    auth_blocked = []
    limited = []

    for account in data.get("accounts", []):
        if not isinstance(account, dict) or normalize_platform(account.get("platform")) != platform_code:
            continue
        if not _region_match(account.get("region_scope") or {}, region):
            continue
        if not _service_match(account.get("service_scope") or {}, service):
            continue
        auth_status = account.get("auth_status")
        if auth_status == "platform_limited":
            limited.append(account)
            continue
        if auth_status != "connected":
            auth_blocked.append(account)
            continue

        device = devices.get(account.get("preferred_device_id"))
        official = provider_status(platform_code)
        api_ready = bool(
            require_publish
            and official.get("configured")
            and _has_publish_scope(account)
        )
        device_ready = _device_ready(device)
        eligible.append({
            "account": account,
            "device": device,
            "api_ready": api_ready,
            "device_ready": device_ready,
            "official": official,
        })

    if eligible:
        # Prefer an actually-authorized official publishing route; otherwise use
        # the real-device path.  Recent account metadata is only a tie breaker.
        eligible.sort(
            key=lambda row: (
                bool(row["api_ready"]),
                bool(row["device_ready"]),
                str(row["account"].get("updated_at") or ""),
            ),
            reverse=True,
        )
        choice = eligible[0]
        account = choice["account"]
        device = choice["device"]
        if choice["api_ready"]:
            return {
                "status": "ready",
                "owner_status": "已连接",
                "account": account,
                "account_id": account.get("account_id"),
                "device": device,
                "device_id": device.get("device_id") if isinstance(device, dict) else None,
                "route_kind": "official_api",
                "route": "official_api",
                "platform": platform_code,
                "truth": "官方应用配置存在且该账号记录了真实发布 scope；最终成功仍必须回收平台 Content ID + URL / Receipt。",
            }
        if choice["device_ready"]:
            return {
                "status": "ready",
                "owner_status": "已连接",
                "account": account,
                "account_id": account.get("account_id"),
                "device": device,
                "device_id": device.get("device_id"),
                "route_kind": "real_device",
                "route": "real_device",
                "platform": platform_code,
                "truth": "账号身份与设备解耦；当前由在线真实设备执行，最终成功仍必须有真实平台回执。",
            }
        return {
            "status": "device_offline",
            "owner_status": "设备离线",
            "account": account,
            "account_id": account.get("account_id"),
            "device": device,
            "device_id": device.get("device_id") if isinstance(device, dict) else account.get("preferred_device_id"),
            "route_kind": "wait_device",
            "route": "wait_device",
            "platform": platform_code,
            "reason": "账号身份有效，但当前没有已批准的官方发布 API 路径，且首选真实设备不在线。",
        }

    if auth_blocked:
        account = auth_blocked[0]
        return {
            "status": "needs_authorization",
            "owner_status": "需授权",
            "account": account,
            "account_id": account.get("account_id"),
            "device": None,
            "device_id": account.get("preferred_device_id"),
            "route_kind": "reauthorize",
            "route": "reauthorize",
            "platform": platform_code,
            "reason": "永久账号仍保留，只需要重新授权，不需要重新绑定 Mission、服务或手机。",
        }

    if limited:
        account = limited[0]
        return {
            "status": "platform_limited",
            "owner_status": "平台限制",
            "account": account,
            "account_id": account.get("account_id"),
            "device": None,
            "device_id": account.get("preferred_device_id"),
            "route_kind": "platform_limited",
            "route": "platform_limited",
            "platform": platform_code,
            "reason": "账号资产存在，但平台当前能力/审批不允许自动执行。",
        }

    return {
        "status": "no_matching_account",
        "owner_status": "未添加账号",
        "account": None,
        "account_id": None,
        "device": None,
        "device_id": None,
        "route_kind": "add_account",
        "route": "add_account",
        "platform": platform_code,
        "reason": "当前没有覆盖该平台/区域/服务范围的永久账号资产。",
    }
