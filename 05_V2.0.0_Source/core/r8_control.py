"""R8 platform safety, device/account binding and social-center control plane.

The control plane is intentionally conservative: real Android devices only,
truthful ADB connection state, explicit platform/account bindings, owner-gated
video publishing and hard stops for finance, verification bypass, device
spoofing and risk events. Platform passwords are never stored here.

Runtime model: one real phone is an operations terminal that may host multiple
platform accounts. A single phone executes foreground platform work serially;
multiple phones may work in parallel after the single-device pilot passes.
"""

from datetime import date

from core.storage import now_iso, read_json, write_json


STATE_PATH = "r8/control.json"
SCHEMA = "kazuizhi-r8-control/v1"

PLATFORMS = {
    "douyin": "抖音",
    "xiaohongshu": "小红书",
    "kuaishou": "快手",
    "wechat_channels": "视频号",
    "weibo": "微博",
    "bilibili": "哔哩哔哩",
    "forum": "论坛/社区",
    "blog": "博客/内容站",
    "other": "其他平台",
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
        "phase": "R8-01",
        "pilot": {
            "enabled": True,
            "device_limit": 1,
            "strategy": "先单真机跑通，再增加第二台设备；单手机多平台串行，多手机并行",
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
            "platform_passwords_not_stored": True,
            "one_platform_account_per_device_binding": True,
            "one_device_many_platform_accounts": True,
            "single_device_foreground_serial": True,
            "multi_device_parallel_after_pilot": True,
        },
        "updated_at": now_iso(),
    }


def _migrate_state(state):
    changed = False
    if state.get("phase") != "R8-01":
        state["phase"] = "R8-01"
        changed = True
    pilot = state.setdefault("pilot", {})
    strategy = "先单真机跑通，再增加第二台设备；单手机多平台串行，多手机并行"
    if pilot.get("strategy") != strategy:
        pilot["strategy"] = strategy
        changed = True
    platforms = state.setdefault("platforms", {})
    for key, name in PLATFORMS.items():
        if key not in platforms:
            platforms[key] = {
                "id": key,
                "name": name,
                "status": "not_connected",
                "automation_paused": False,
                "risk_level": "unknown",
                "last_error": None,
            }
            changed = True
    hard = state.setdefault("hard_rules", {})
    rules = {
        "platform_passwords_not_stored": True,
        "one_platform_account_per_device_binding": True,
        "one_device_many_platform_accounts": True,
        "single_device_foreground_serial": True,
        "multi_device_parallel_after_pilot": True,
    }
    for key, value in rules.items():
        if hard.get(key) != value:
            hard[key] = value
            changed = True
    if "one_platform_window_per_device" in hard:
        hard.pop("one_platform_window_per_device", None)
        changed = True
    state.setdefault("accounts", [])
    state.setdefault("devices", [])
    return changed


def control_status():
    state = read_json(STATE_PATH, None)
    if not isinstance(state, dict) or state.get("schema") != SCHEMA:
        state = _default_state()
        write_json(STATE_PATH, state)
    elif _migrate_state(state):
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
    """Create/update one platform account bound to one real phone.

    One phone may host many different platform accounts, while a specific
    phone/platform binding has one active account record. Passwords/tokens are
    intentionally not accepted or stored. Login verification happens in the
    real platform app and is marked separately by the owner.
    """
    payload = payload or {}
    platform = str(payload.get("platform") or "").strip()
    device_id = str(payload.get("device_id") or "").strip()
    alias = str(payload.get("alias") or "").strip()
    label = str(payload.get("label") or alias).strip()
    if platform not in PLATFORMS:
        raise ValueError("暂不支持该平台")
    if not alias or len(alias) > 100:
        raise ValueError("账号别名不能为空")
    if not label or len(label) > 80:
        raise ValueError("窗口名称不能为空")
    if any(key in payload for key in ("password", "passcode", "secret", "token")):
        raise ValueError("社媒中心不保存平台密码、验证码或登录令牌")

    state = control_status()
    device = next((item for item in state.get("devices", []) if item.get("device_id") == device_id), None)
    if not device:
        raise ValueError("平台账号必须绑定已登记真机")

    accounts = state.setdefault("accounts", [])
    existing_by_binding = next(
        (item for item in accounts if item.get("platform") == platform and item.get("device_id") == device_id),
        None,
    )
    requested_id = str(payload.get("account_id") or "").strip()
    if existing_by_binding and requested_id and existing_by_binding.get("account_id") != requested_id:
        raise ValueError("同一台手机的同一平台只能保留一个当前账号绑定")

    existing = existing_by_binding
    account_id = existing.get("account_id") if existing else (requested_id or f"{platform}:{device_id}")
    now = now_iso()
    if existing:
        existing.update({
            "alias": alias,
            "label": label,
            "platform_name": PLATFORMS[platform],
            "updated_at": now,
        })
    else:
        accounts.append({
            "account_id": account_id[:180],
            "platform": platform,
            "platform_name": PLATFORMS[platform],
            "device_id": device_id,
            "alias": alias,
            "label": label,
            "login_status": "not_verified",
            "login_verified_at": None,
            "health": "unknown",
            "risk_level": "unknown",
            "automation_paused": False,
            "last_error": None,
            "created_at": now,
            "updated_at": now,
        })
    return _save(state)


def update_account_status(payload):
    payload = payload or {}
    account_id = str(payload.get("account_id") or "").strip()
    state = control_status()
    account = next((item for item in state.get("accounts", []) if item.get("account_id") == account_id), None)
    if not account:
        raise ValueError("社媒平台账号不存在")

    if "login_status" in payload:
        login_status = str(payload.get("login_status") or "").strip()
        if login_status not in {"not_verified", "authorized", "needs_human", "logged_out"}:
            raise ValueError("登录状态不支持")
        account["login_status"] = login_status
        account["login_verified_at"] = now_iso() if login_status == "authorized" else None
    if "automation_paused" in payload:
        account["automation_paused"] = bool(payload.get("automation_paused"))
    if "risk_level" in payload:
        risk = str(payload.get("risk_level") or "unknown").strip()
        if risk not in {"unknown", "normal", "attention", "high"}:
            raise ValueError("风险状态不支持")
        account["risk_level"] = risk
    if "last_error" in payload:
        account["last_error"] = str(payload.get("last_error") or "")[:240] or None
    account["updated_at"] = now_iso()
    return _save(state)


def remove_account(payload):
    payload = payload or {}
    account_id = str(payload.get("account_id") or "").strip()
    state = control_status()
    before = len(state.get("accounts", []))
    state["accounts"] = [item for item in state.get("accounts", []) if item.get("account_id") != account_id]
    if len(state["accounts"]) == before:
        raise ValueError("社媒平台账号不存在")
    return _save(state)


def social_center_status():
    state = control_status()
    devices = list(state.get("devices", []))
    accounts = list(state.get("accounts", []))
    online_ids = {
        item.get("device_id") for item in devices
        if item.get("connection") == "connected" and item.get("probe_source") == "adb"
    }
    platform_rows = []
    for platform_id, name in PLATFORMS.items():
        rows = [item for item in accounts if item.get("platform") == platform_id]
        platform_rows.append({
            "id": platform_id,
            "name": name,
            "windows": len(rows),
            "online": sum(1 for item in rows if item.get("device_id") in online_ids),
            "authorized": sum(1 for item in rows if item.get("login_status") == "authorized"),
            "attention": sum(
                1 for item in rows
                if item.get("login_status") in {"needs_human", "logged_out"}
                or item.get("risk_level") in {"attention", "high"}
            ),
        })

    terminal_rows = []
    for device in devices:
        device_id = device.get("device_id")
        bound = [item for item in accounts if item.get("device_id") == device_id]
        terminal_rows.append({
            "device_id": device_id,
            "label": device.get("label") or device_id,
            "connection": device.get("connection"),
            "health": device.get("health"),
            "risk_level": device.get("risk_level", "unknown"),
            "last_seen_at": device.get("last_seen_at"),
            "platform_count": len(bound),
            "authorized_count": sum(1 for item in bound if item.get("login_status") == "authorized"),
            "attention_count": sum(
                1 for item in bound
                if item.get("login_status") in {"needs_human", "logged_out"}
                or item.get("risk_level") in {"attention", "high"}
            ),
            "accounts": bound,
        })

    return {
        "phase": state.get("phase"),
        "pilot": state.get("pilot"),
        "platforms": platform_rows,
        "terminals": terminal_rows,
        "devices": devices,
        "accounts": accounts,
        "rules": {
            "one_device_many_platform_accounts": True,
            "one_phone_platform_binding_one_current_account": True,
            "single_device_foreground_serial": True,
            "multi_device_parallel_after_pilot": True,
            "passwords_stored": False,
            "verification_requires_human": True,
            "finance_requires_human": True,
        },
        "updated_at": state.get("updated_at"),
    }


def authorize_action(payload):
    """Return a truthful execution decision for a proposed platform action."""
    payload = payload or {}
    action = str(payload.get("action") or "").strip()
    platform = str(payload.get("platform") or "").strip()
    device_id = str(payload.get("device_id") or "").strip()
    account_id = str(payload.get("account_id") or "").strip()
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
    if account_id:
        account = next((item for item in state.get("accounts", []) if item.get("account_id") == account_id), None)
        if not account or account.get("platform") != platform or account.get("device_id") != device_id:
            return deny("社媒账号与设备/平台绑定不一致")
        if account.get("login_status") != "authorized":
            return deny("平台账号尚未完成人工登录/授权验证", human=True)
        if account.get("automation_paused"):
            return deny("该平台账号已暂停自动化")
        if account.get("risk_level") in {"attention", "high"}:
            return deny("账号处于风险状态，已停止自动动作", human=True)
    if action in VIDEO_PUBLICATION_ACTIONS and not owner_approved:
        return deny("视频必须经过老板人工审核并点击确认发布", human=True)
    if action in LOW_RISK_ACTIONS | INTERACTION_ACTIONS | TEXT_PUBLICATION_ACTIONS | VIDEO_PUBLICATION_ACTIONS:
        return {
            "allowed": True,
            "action": action,
            "reason": "通过 R8 安全门；执行器仍需遵守平台规则、频率限制和真实回执要求",
            "requires_human": False,
        }
    return deny("动作不在 R8 安全白名单")
