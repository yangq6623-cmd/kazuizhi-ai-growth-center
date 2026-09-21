"""R8-01B.3+ runtime patch for safe Android recovery and owner controls.

This module extends the existing Android adapter without weakening its security
boundary. Non-secure keyguard screens may be dismissed after a normal wake;
secure locks and platform verification remain human-only. V2.2.1 also exposes
common owner controls (recents, volume, orientation) through the same audited
device action route used by the existing buttons.
"""

import time

from integrations import android_device as _base

PLATFORM_PACKAGES = {
    "douyin": "com.ss.android.ugc.aweme",
    "xiaohongshu": "com.xingin.xhs",
    "kuaishou": "com.smile.gifmaker",
    "wechat_channels": "com.tencent.mm",
    "weibo": "com.sina.weibo",
    "bilibili": "tv.danmaku.bili",
}

OWNER_KEYEVENTS = {
    "recents": "187",
    "volume_up": "24",
    "volume_down": "25",
}

# Android user_rotation values: 0 portrait, 1 landscape clockwise, 2 reverse
# portrait, 3 landscape counter-clockwise. We only expose owner-triggered
# left/right landscape controls; automatic rotation can be restored separately.
OWNER_ROTATIONS = {
    "rotate_left": "3",
    "rotate_right": "1",
}

_ORIGINAL_EXECUTE_ACTION = _base.execute_action


def _dismiss_nonsecure_keyguard(device_id, device, requested_action):
    """Dismiss only a non-secure Android keyguard after wake.

    This is intentionally not used for PIN/password/biometric secure locks.
    """
    if not device or device.get("device_locked") is not True or device.get("device_secure") is True:
        return device
    try:
        _base._shell(device_id, "wm", "dismiss-keyguard")
        time.sleep(0.35)
        refreshed = _base._fresh_device_details(device_id)
        if refreshed.get("device_locked") is True and refreshed.get("device_secure") is not True:
            _base._shell(device_id, "input", "keyevent", "82")
            time.sleep(0.35)
            refreshed = _base._fresh_device_details(device_id)
        _base._append_audit({
            "device_id": device_id,
            "action": "auto_dismiss_keyguard",
            "actor": "system",
            "result": "ok" if refreshed.get("device_locked") is not True else "blocked",
            "detail": {
                "requested_action": requested_action,
                "screen_state": refreshed.get("screen_state"),
                "secure": refreshed.get("device_secure"),
            },
        })
        return refreshed
    except Exception as error:
        _base._append_audit({
            "device_id": device_id,
            "action": "auto_dismiss_keyguard",
            "actor": "system",
            "result": "blocked",
            "detail": {"requested_action": requested_action, "error": str(error)[:240]},
        })
        return device


def _prepare_for_interaction(device_id, requested_action):
    device = _base._require_connected(device_id)
    if device.get("screen_awake") is False:
        _base._shell(device_id, "input", "keyevent", "26")
        time.sleep(0.65)
        device = _base._fresh_device_details(device_id)
        _base._append_audit({
            "device_id": device_id,
            "action": "auto_wake",
            "actor": "system",
            "result": "ok" if device.get("screen_awake") else "blocked",
            "detail": {"requested_action": requested_action, "screen_state": device.get("screen_state")},
        })
    if device.get("screen_awake"):
        device = _dismiss_nonsecure_keyguard(device_id, device, requested_action)
    return device


def _require_owner_ready(device_id, action):
    """Prepare a phone for a manual owner control without bypassing secure lock."""
    device = _prepare_for_interaction(device_id, action)
    if device.get("screen_awake") is False:
        raise ValueError("手机自动唤醒失败，请检查设备后人工处理")
    if device.get("device_secure") is True and device.get("device_locked") is True:
        raise ValueError("手机处于安全锁定状态，请先人工解锁后再继续")
    if device.get("device_locked") is True:
        raise ValueError("手机仍停留在锁屏界面，请人工确认后继续")
    return device


def _audit_owner_control(device_id, action, actor, payload, detail):
    event = _base._append_audit({
        "device_id": device_id,
        "action": action,
        "actor": actor,
        "task_id": str(payload.get("task_id") or "")[:120] or None,
        "account_id": str(payload.get("account_id") or "")[:180] or None,
        "result": "ok",
        "detail": detail,
    })
    return {"ok": True, "device": _base._fresh_device_details(device_id), "event": event}


def execute_action(payload):
    payload = payload or {}
    device_id = str(payload.get("device_id") or "").strip()
    action = str(payload.get("action") or "").strip().lower()
    actor = str(payload.get("actor") or "owner")[:40]
    if not device_id:
        raise ValueError("device_id 不能为空")

    if action == "launch_app":
        platform = str(payload.get("platform") or "").strip().lower()
        package = PLATFORM_PACKAGES.get(platform)
        if not package:
            raise ValueError("当前平台没有已登记的 Android 启动入口")
        _require_owner_ready(device_id, "launch_app")
        output = _base._shell(
            device_id,
            "monkey", "-p", package, "-c", "android.intent.category.LAUNCHER", "1",
            timeout=12,
        )
        text = str(output or "")
        if "No activities found" in text or "monkey aborted" in text.lower():
            raise ValueError("该平台 App 未安装或没有可启动入口")
        event = _base._append_audit({
            "device_id": device_id,
            "action": "launch_app",
            "actor": actor,
            "task_id": str(payload.get("task_id") or "")[:120] or None,
            "account_id": str(payload.get("account_id") or "")[:180] or None,
            "result": "ok",
            "detail": {"platform": platform, "package": package},
        })
        return {"ok": True, "device": _base._fresh_device_details(device_id), "event": event}

    if action in OWNER_KEYEVENTS:
        _require_owner_ready(device_id, action)
        keyevent = OWNER_KEYEVENTS[action]
        _base._shell(device_id, "input", "keyevent", keyevent)
        return _audit_owner_control(device_id, action, actor, payload, {"keyevent": keyevent, "owner_control": True})

    if action in OWNER_ROTATIONS:
        _require_owner_ready(device_id, action)
        rotation = OWNER_ROTATIONS[action]
        _base._shell(device_id, "settings", "put", "system", "accelerometer_rotation", "0")
        _base._shell(device_id, "settings", "put", "system", "user_rotation", rotation)
        time.sleep(0.25)
        return _audit_owner_control(
            device_id, action, actor, payload,
            {"user_rotation": int(rotation), "auto_rotate": False, "owner_control": True},
        )

    if action == "rotate_auto":
        _require_owner_ready(device_id, action)
        _base._shell(device_id, "settings", "put", "system", "accelerometer_rotation", "1")
        return _audit_owner_control(device_id, action, actor, payload, {"auto_rotate": True, "owner_control": True})

    if action not in {"power", "keep_awake_on", "keep_awake_off"}:
        _prepare_for_interaction(device_id, action)

    result = _ORIGINAL_EXECUTE_ACTION(payload)
    if action == "wake":
        refreshed = _base._fresh_device_details(device_id)
        refreshed = _dismiss_nonsecure_keyguard(device_id, refreshed, "wake")
        result["device"] = refreshed
    return result


# Patch the function that backend.server imports from integrations.android_device.
_base.execute_action = execute_action
