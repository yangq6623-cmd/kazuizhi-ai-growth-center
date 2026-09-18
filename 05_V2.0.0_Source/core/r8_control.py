"""R8 platform safety and single-device pilot control plane.

R8-00 is intentionally conservative: one real Android device first, stable account
binding, explicit platform rules, owner-gated video publishing and hard stops for
finance, verification bypass, device spoofing and risk events.  It stores control
state only; actual Android/ADB execution is added by the device adapter in the next
R8 block so this module never pretends a phone is connected when it is not.
"""

from datetime import date

from core.storage import now_iso, read_json, write_json


STATE_PATH = "r8/control.json"
SCHEMA = "kazuizhi-r8-control/v1"

PLATFORMS = {
    "douyin": "抖音",
    "xiaohongshu": "小红书",
    "wechat_channels": "视频号",
    "weibo": "微博",
    "forum": "论坛/社区",
    "blog": "博客/内容站",
}

LOW_RISK_ACTIONS = {
    "browse", "search", "read_comments", "collect_public_signal",
    "capture_public_evidence", "platform_learning",
}
INTERACTION_ACTIONS = {"comment", "reply", "like", "follow"}
TEXT_PUBLICATION_ACTIONS = {"publish_text", "publish_image_post"}
VIDEO_PUBLICATION_ACTIONS = {"publish_video"}
HARD_BLOCKED_ACTIONS = {
    "pay", "refund", "withdraw", "settle", "transfer", "reprice",
    "bypass_captcha", "bypass_face_verification", "bypass_sms_verification",
    "spoof_device", "spoof_imei", "spoof_android_id", "spoof_gps",
    "rotate_ip_to_evade_risk", "hide_automation_framework",
}


def _default_state():
    return {
        "schema": SCHEMA,
        "phase": "R8-00",
        "pilot": {
            "enabled": True,
            "device_limit": 1,
            "strategy": "先单真机跑通，再增加第二台设备",
        },
        "global": {
            "paused": True,
            "pause_reason": "R8 单真机尚未完成真实设备接入验收",
            "updated_at": now_iso(),
        },
        "devices": [],
        "accounts": [],
        "platforms": {
            key: {
                "id": key,
                "name": name,
                "status": "not_connected",
                "automation_paused": False,
                "risk_level": "unknown",
                "last_error": None,
            }
            for key, name in PLATFORMS.items()
        },
        "owner_focus": {
            "date": None,
            "mode": "balanced",
            "instruction": "",
            "updated_at": None,
        },
        "hard_rules": {
            "real_device_only": True,
            "no_device_spoofing": True,
            "no_risk_evasion": True,
            "verification_requires_human": True,
            "video_publish_requires_owner_approval": True,
            "finance_requires_human": True,
            "platform_policy_required": True,
            "truthful_receipts_required": True,
        },
        "updated_at": now_iso(),
    }


def control_status():
    state = read_json(STATE_PATH, None)
    if not isinstance(state, dict) or state.get("schema") != SCHEMA:
        state = _default_state()
        write_json(STATE_PATH, state)
    return state


def _save(state):
    state["updated_at"] = now_iso()
    return write_json(STATE_PATH, state)


def set_global_pause(paused, reason=""):
    state = control_status()
    state["global"] = {
        "paused": bool(paused),
        "pause_reason": str(reason or "")[:240],
        "updated_at": now_iso(),
    }
    return _save(state)


def set_owner_focus(payload):
    payload = payload or {}
    instruction = str(payload.get("instruction") or "").strip()
    if not instruction or len(instruction) > 500:
        raise ValueError("老板重点需为 1-500 字")
    mode = str(payload.get("mode") or "balanced").strip()
    allowed = {"balanced", "platform_learning", "interaction", "content", "publishing"}
    if mode not in allowed:
        raise ValueError("老板重点模式不支持")
    state = control_status()
    state["owner_focus"] = {
        "date": str(payload.get("date") or date.today()),
        "mode": mode,
        "instruction": instruction,
        "updated_at": now_iso(),
    }
    return _save(state)


def register_device(payload):
    """Register one real Android pilot device without claiming it is connected."""
    payload = payload or {}
    device_id = str(payload.get("device_id") or "").strip()
    label = str(payload.get("label") or "").strip()
    if not device_id or len(device_id) > 120:
        raise ValueError("设备 ID 不能为空")
    if not label or len(label) > 80:
        raise ValueError("设备名称不能为空")
    if str(payload.get("device_type") or "real_android") != "real_android":
        raise ValueError("R8 单机试点只接受真实 Android 设备")
    state = control_status()
    devices = state.setdefault("devices", [])
    existing = next((item for item in devices if item.get("device_id") == device_id), None)
    if existing:
        existing.update(label=label, updated_at=now_iso())
        return _save(state)
    limit = int((state.get("pilot") or {}).get("device_limit") or 1)
    if len(devices) >= limit:
        raise ValueError("R8 当前为单真机试点；请先完成第一台设备验收，再开放第二台")
    devices.append({
        "device_id": device_id,
        "label": label,
        "device_type": "real_android",
        "transport": str(payload.get("transport") or "usb")[:20],
        "connection": "registered_not_verified",
        "probe_source": None,
        "health": "unknown",
        "risk_level": "unknown",
        "last_seen_at": None,
        "created_at": now_iso(),
        "updated_at": now_iso(),
    })
    return _save(state)


def record_device_probe(device_id, connected, source="adb", detail=""):
    """Accept connection truth only from the hardware adapter (ADB in pilot)."""
    if source != "adb":
        raise ValueError("设备连接状态只能由 ADB 真机探测写入")
    state = control_status()
    device = next((item for item in state.get("devices", []) if item.get("device_id") == device_id), None)
    if not device:
        raise ValueError("设备尚未登记")
    device.update({
        "connection": "connected" if connected else "disconnected",
        "probe_source": "adb",
        "health": "normal" if connected else "offline",
        "last_seen_at": now_iso() if connected else device.get("last_seen_at"),
        "probe_detail": str(detail or "")[:240],
        "updated_at": now_iso(),
    })
    return _save(state)


def register_account(payload):
    payload = payload or {}
    platform = str(payload.get("platform") or "").strip()
    device_id = str(payload.get("device_id") or "").strip()
    alias = str(payload.get("alias") or "").strip()
    if platform not in PLATFORMS:
        raise ValueError("暂不支持该平台")
    if not alias or len(alias) > 100:
        raise ValueError("账号别名不能为空")
    state = control_status()
    device = next((item for item in state.get("devices", []) if item.get("device_id") == device_id), None)
    if not device:
        raise ValueError("账号必须绑定已登记真机")
    account_id = str(payload.get("account_id") or f"{platform}:{device_id}:{alias}")[:180]
    accounts = state.setdefault("accounts", [])
    existing = next((item for item in accounts if item.get("account_id") == account_id), None)
    record = {
        "account_id": account_id,
        "platform": platform,
        "platform_name": PLATFORMS[platform],
        "device_id": device_id,
        "alias": alias,
        "login_status": "not_verified",
        "health": "unknown",
        "risk_level": "unknown",
        "automation_paused": False,
        "created_at": existing.get("created_at") if existing else now_iso(),
        "updated_at": now_iso(),
    }
    if existing:
        existing.update(record)
    else:
        accounts.append(record)
    return _save(state)


def authorize_action(payload):
    """Return a truthful execution decision for a proposed platform action."""
    payload = payload or {}
    action = str(payload.get("action") or "").strip()
    platform = str(payload.get("platform") or "").strip()
    device_id = str(payload.get("device_id") or "").strip()
    owner_approved = bool(payload.get("owner_approved"))
    verification_required = bool(payload.get("verification_required"))
    state = control_status()

    def deny(reason, human=False):
        return {"allowed": False, "action": action, "reason": reason, "requires_human": bool(human)}

    if action in HARD_BLOCKED_ACTIONS:
        human = action in {"pay", "refund", "withdraw", "settle", "transfer", "reprice"}
        return deny("该动作被 R8 永久安全策略禁止自动执行", human=human)
    if verification_required:
        return deny("出现验证码/短信/人脸/风险验证，必须暂停并转人工", human=True)
    if (state.get("global") or {}).get("paused"):
        return deny((state.get("global") or {}).get("pause_reason") or "R8 全局自动化已暂停")
    if platform not in PLATFORMS:
        return deny("平台未登记")
    pstate = (state.get("platforms") or {}).get(platform) or {}
    if pstate.get("automation_paused"):
        return deny("该平台自动化已熔断")
    device = next((item for item in state.get("devices", []) if item.get("device_id") == device_id), None)
    if not device or device.get("connection") != "connected" or device.get("probe_source") != "adb":
        return deny("没有经过 ADB 验证的真实 Android 设备在线")
    if device.get("risk_level") not in ("unknown", "normal"):
        return deny("设备处于风险状态，已停止自动动作", human=True)
    if action in VIDEO_PUBLICATION_ACTIONS and not owner_approved:
        return deny("视频必须经过老板人工审核并点击确认发布", human=True)
    if action in LOW_RISK_ACTIONS | INTERACTION_ACTIONS | TEXT_PUBLICATION_ACTIONS | VIDEO_PUBLICATION_ACTIONS:
        return {
            "allowed": True,
            "action": action,
            "reason": "通过 R8-00 安全门；执行器仍需遵守平台规则、频率限制和真实回执要求",
            "requires_human": False,
        }
    return deny("动作不在 R8 安全白名单")
