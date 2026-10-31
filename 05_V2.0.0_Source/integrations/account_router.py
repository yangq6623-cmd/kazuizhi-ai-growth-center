"""R8-12/R8-13 durable account/authorization/device route planner.

Safety rules:
- Mission routing never re-binds an account.
- Multiple accounts are supported, but routing is sticky/deterministic rather
  than rotating accounts to evade quotas or platform controls.
- A risk-paused account never silently fails over to another account for the
  same explicitly bound task; the system pauses for owner review.
- Official API is used only when a real scope is recorded; otherwise a verified
  real device can be used when the platform workflow permits it.
- No branch claims publication success.
"""
from __future__ import annotations

import hashlib

from core.account_registry import migrate_legacy_assets, snapshot, sync_device_health
from integrations.account_environment import routing_allowed
from integrations.oauth_adapters import provider_status

PLATFORM_ALIASES = {
    "抖音": "douyin", "douyin": "douyin", "快手": "kuaishou", "kuaishou": "kuaishou",
    "小红书": "xiaohongshu", "xiaohongshu": "xiaohongshu", "视频号": "wechat_channels",
    "微信视频号": "wechat_channels", "wechat_channels": "wechat_channels", "微博": "weibo", "weibo": "weibo",
    "B站": "bilibili", "哔哩哔哩": "bilibili", "bilibili": "bilibili",
    "Google Search Console": "google_search_console", "google_search_console": "google_search_console",
    "Bing Webmaster": "bing_webmaster", "bing_webmaster": "bing_webmaster",
    "百度搜索资源平台": "baidu_search_resource", "baidu_search_resource": "baidu_search_resource",
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
    try:
        migrate_legacy_assets()
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError):
        pass
    try:
        from integrations import android_device
        sync_device_health(android_device.scan_and_sync())
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError):
        pass


def _sticky_score(account_id: str, task_key: str) -> str:
    seed = f"{task_key}|{account_id}" if task_key else str(account_id or "")
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()


def route_account(*, platform, region="", service="", require_publish=True, refresh_devices=True,
                  preferred_account_id="", task_key=""):
    if refresh_devices:
        _refresh_live_assets()
    platform_code = normalize_platform(platform)
    preferred_account_id = str(preferred_account_id or "").strip()
    task_key = str(task_key or "").strip()
    data = snapshot()
    devices = {x.get("device_id"): x for x in data.get("devices", []) if isinstance(x, dict)}
    eligible, auth_blocked, limited, risk_paused = [], [], [], []

    for account in data.get("accounts", []):
        if not isinstance(account, dict) or normalize_platform(account.get("platform")) != platform_code: continue
        if preferred_account_id and account.get("account_id") != preferred_account_id: continue
        if not _region_match(account.get("region_scope") or {}, region): continue
        if not _service_match(account.get("service_scope") or {}, service): continue
        if account.get("auth_status") == "platform_limited": limited.append(account); continue
        if account.get("auth_status") != "connected": auth_blocked.append(account); continue
        environment = routing_allowed(str(account.get("account_id") or ""))
        if not environment.get("allowed"):
            risk_paused.append({"account": account, "environment": environment})
            continue
        device = devices.get(account.get("preferred_device_id"))
        official = provider_status(platform_code)
        eligible.append({
            "account": account, "device": device, "official": official, "environment": environment,
            "api_ready": bool(require_publish and official.get("configured") and _has_publish_scope(account)),
            "device_ready": _device_ready(device),
        })

    if eligible:
        # Stable task->account mapping. Do not rotate across accounts because of transient errors.
        eligible.sort(key=lambda row: (
            0 if preferred_account_id and row["account"].get("account_id") == preferred_account_id else 1,
            0 if row["api_ready"] else 1,
            0 if row["device_ready"] else 1,
            _sticky_score(str(row["account"].get("account_id") or ""), task_key),
        ))
        choice = eligible[0]; account, device = choice["account"], choice["device"]
        common = {
            "status": "ready", "owner_status": "已连接", "account": account,
            "account_id": account.get("account_id"), "device": device,
            "device_id": device.get("device_id") if isinstance(device, dict) else None,
            "platform": platform_code, "environment": choice.get("environment"),
            "routing_policy": "sticky_no_risk_failover",
        }
        if choice["api_ready"]:
            return dict(common, route_kind="official_api", route="official_api", truth="官方应用已配置且账号记录真实 scope；最终成功仍必须回收平台真实 URL/Post ID/Receipt。")
        if choice["device_ready"]:
            return dict(common, route_kind="real_device", route="real_device", truth="账号身份与设备解耦；当前由在线真实设备执行，最终成功仍必须有真实平台回执。")
        return {
            **common, "status": "device_offline", "owner_status": "设备离线", "route_kind": "wait_device", "route": "wait_device",
            "reason": "账号身份有效，但当前没有已批准的官方执行路径且首选真实设备不在线。",
        }

    if risk_paused:
        blocked = risk_paused[0]
        return {
            "status": "risk_pause", "owner_status": "风控暂停", "account": blocked["account"],
            "account_id": blocked["account"].get("account_id"), "device": None,
            "device_id": blocked["account"].get("preferred_device_id"), "route_kind": "wait_owner", "route": "wait_owner",
            "platform": platform_code, "environment": blocked["environment"],
            "reason": "账号环境/平台风控状态要求暂停。不会自动切换其他账号来绕过限制。",
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
