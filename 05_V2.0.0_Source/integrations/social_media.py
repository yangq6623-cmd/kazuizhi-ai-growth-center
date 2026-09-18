"""R8 social-media workspace registry.

Each workspace binds one platform account to one real Android device. The module
never stores plaintext platform passwords. Initial sign-in happens on the real
phone (or through an official authorization flow); R8 stores only the binding
and the verified login/authorization state.
"""

import uuid
from core.storage import now_iso, read_json, write_json

STATE_PATH = "r8/social_media.json"

PLATFORMS = [
    {"id": "douyin", "name": "抖音", "short": "抖", "status": "planned"},
    {"id": "xiaohongshu", "name": "小红书", "short": "小", "status": "planned"},
    {"id": "wechat_channels", "name": "视频号", "short": "视", "status": "planned"},
    {"id": "weibo", "name": "微博", "short": "微", "status": "planned"},
]
PLATFORM_IDS = {item["id"] for item in PLATFORMS}


def _state():
    value = read_json(STATE_PATH, None)
    if not isinstance(value, dict):
        value = {"workspaces": [], "updated_at": now_iso()}
        write_json(STATE_PATH, value)
    value.setdefault("workspaces", [])
    return value


def _save(value):
    value["updated_at"] = now_iso()
    write_json(STATE_PATH, value)
    return value


def status():
    value = _state()
    workspaces = list(value.get("workspaces") or [])
    return {
        "platforms": PLATFORMS,
        "workspaces": workspaces,
        "count": len(workspaces),
        "updated_at": value.get("updated_at"),
        "credential_policy": {
            "plaintext_password_storage": False,
            "preferred_login": "real_device_or_official_authorization",
            "message": "平台密码不写入项目、日志或普通 JSON。首次登录在真实手机或平台官方授权页完成，R8 只保存设备绑定和已验证登录状态。",
        },
        "binding_rule": "同一平台下，一个设备只能绑定一个账号工作窗口；同一设备可在不同平台分别建立工作窗口。",
    }


def add_workspace(payload):
    payload = payload or {}
    platform_id = str(payload.get("platform_id") or "").strip()
    device_id = str(payload.get("device_id") or "").strip()
    account_alias = str(payload.get("account_alias") or "").strip()[:120]
    if platform_id not in PLATFORM_IDS:
        raise ValueError("请选择支持的社媒平台")
    if not device_id:
        raise ValueError("请选择真实 Android 手机")
    if not account_alias:
        raise ValueError("请填写平台账号名称/备注")
    if payload.get("password"):
        raise ValueError("为避免明文凭据风险，社媒中心不接收平台密码；请在真实手机完成登录或官方授权")

    value = _state()
    workspaces = value.get("workspaces") or []
    if any(x.get("platform_id") == platform_id and x.get("device_id") == device_id for x in workspaces):
        raise ValueError("该手机在这个平台已经建立了账号工作窗口")

    item = {
        "workspace_id": uuid.uuid4().hex[:16],
        "platform_id": platform_id,
        "device_id": device_id,
        "account_alias": account_alias,
        "login_status": "needs_login",
        "authorization_status": "not_verified",
        "control_status": "waiting_login",
        "current_task": None,
        "last_action": None,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    }
    workspaces.append(item)
    value["workspaces"] = workspaces
    _save(value)
    return status()


def update_workspace(payload):
    payload = payload or {}
    workspace_id = str(payload.get("workspace_id") or "").strip()
    action = str(payload.get("action") or "").strip()
    if not workspace_id:
        raise ValueError("workspace_id 不能为空")
    value = _state()
    item = next((x for x in value.get("workspaces", []) if x.get("workspace_id") == workspace_id), None)
    if not item:
        raise ValueError("未找到账号工作窗口")

    if action == "confirm_logged_in":
        item["login_status"] = "logged_in"
        item["authorization_status"] = "verified_by_owner"
        item["control_status"] = "ready"
        item["last_action"] = "老板确认真实手机已完成登录/授权"
    elif action == "require_login":
        item["login_status"] = "needs_login"
        item["authorization_status"] = "not_verified"
        item["control_status"] = "waiting_login"
        item["last_action"] = "登录状态已重置，等待人工登录/授权"
    elif action == "rename":
        alias = str(payload.get("account_alias") or "").strip()[:120]
        if not alias:
            raise ValueError("账号名称不能为空")
        item["account_alias"] = alias
        item["last_action"] = "更新账号备注"
    else:
        raise ValueError("不支持的账号工作窗口操作")
    item["updated_at"] = now_iso()
    _save(value)
    return status()


def delete_workspace(payload):
    payload = payload or {}
    workspace_id = str(payload.get("workspace_id") or "").strip()
    value = _state()
    before = len(value.get("workspaces") or [])
    value["workspaces"] = [x for x in value.get("workspaces", []) if x.get("workspace_id") != workspace_id]
    if len(value["workspaces"]) == before:
        raise ValueError("未找到账号工作窗口")
    _save(value)
    return status()
