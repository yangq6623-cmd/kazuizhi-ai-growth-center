"""Truthful real-device social login/session verification for R8-11.

The first pilot supports Douyin on a real Android phone over ADB. The verifier
never reads/stores passwords or tokens, never bypasses captcha/face/SMS checks,
and never publishes content. It only turns a bound account into an authorized
session when the real app UI provides strong, non-risk login evidence.
"""
from __future__ import annotations

import re
import time
from html import unescape

from core import r8_control
from integrations import android_device

DOUYIN_PACKAGE = "com.ss.android.ugc.aweme"
PROBE_INTERVAL_SECONDS = 10
_LAST_PROBE = {}

LOGIN_BLOCK_MARKERS = (
    "请先登录", "登录抖音", "手机号登录", "验证码登录", "密码登录", "注册登录",
    "安全验证", "人脸验证", "滑块验证", "账号异常", "登录异常", "身份验证",
)
PROFILE_MARKERS = ("编辑主页", "抖音号", "获赞", "关注", "粉丝", "作品")


def _plain_xml(xml_text):
    text = unescape(str(xml_text or ""))
    # UIAutomator XML keeps visible text/content-desc in attributes; flattening
    # is enough for conservative marker checks and does not use OCR.
    return re.sub(r"\s+", " ", text)


def evaluate_douyin_session(*, alias, package_installed, foreground_text, ui_xml):
    """Pure evaluator used by runtime and CI.

    Returns authorized only when Douyin is installed + foreground, no login/risk
    challenge is visible, and the current profile UI contains the bound alias
    together with authenticated-profile controls.
    """
    alias = str(alias or "").strip()
    foreground = str(foreground_text or "")
    ui = _plain_xml(ui_xml)
    if not package_installed:
        return {"status": "inconclusive", "reason": "douyin_not_installed", "detail": "未检测到抖音 App"}
    if DOUYIN_PACKAGE not in foreground:
        return {"status": "inconclusive", "reason": "douyin_not_foreground", "detail": "抖音当前不在前台"}
    blocked = next((marker for marker in LOGIN_BLOCK_MARKERS if marker in ui), None)
    if blocked:
        login_markers = {"请先登录", "登录抖音", "手机号登录", "验证码登录", "密码登录", "注册登录"}
        status = "logged_out" if blocked in login_markers else "needs_human"
        return {"status": status, "reason": "human_verification_or_login", "detail": f"真机页面检测到：{blocked}"}
    profile_hits = [marker for marker in PROFILE_MARKERS if marker in ui]
    alias_match = bool(alias and alias in ui)
    if alias_match and len(profile_hits) >= 2:
        return {
            "status": "authorized",
            "reason": "real_device_profile_verified",
            "detail": f"真机抖音前台已匹配账号“{alias}”，并检测到个人主页控件：{'、'.join(profile_hits[:4])}",
        }
    return {
        "status": "inconclusive",
        "reason": "insufficient_profile_evidence",
        "detail": "抖音已在前台，但尚未取得足够的绑定账号主页证据",
    }


def _shell(device_id, *args, timeout=8):
    return android_device._shell(device_id, *args, timeout=timeout)  # internal ADB adapter; read-only probe


def _package_installed(device_id, package):
    try:
        output = _shell(device_id, "pm", "path", package, timeout=8)
        return "package:" in str(output or "")
    except (RuntimeError, OSError):
        return False


def _foreground(device_id):
    for args in (("dumpsys", "window", "windows"), ("dumpsys", "activity", "activities")):
        try:
            text = _shell(device_id, *args, timeout=8)
            if DOUYIN_PACKAGE in str(text or ""):
                return str(text or "")
        except (RuntimeError, OSError):
            continue
    return ""


def _ui_xml(device_id):
    remote = "/sdcard/Download/kazuizhi_login_probe.xml"
    try:
        _shell(device_id, "uiautomator", "dump", "--compressed", remote, timeout=12)
        return _shell(device_id, "cat", remote, timeout=8)
    except (RuntimeError, OSError):
        return ""
    finally:
        try:
            _shell(device_id, "rm", "-f", remote, timeout=4)
        except (RuntimeError, OSError):
            pass


def probe_account(account, *, now_monotonic=None, force=False):
    """Probe one bound account without clicking, typing, launching or publishing."""
    account = dict(account or {})
    account_id = str(account.get("account_id") or "").strip()
    platform = str(account.get("platform") or "").strip()
    device_id = str(account.get("device_id") or "").strip()
    if not account_id or not device_id:
        return {"status": "inconclusive", "reason": "missing_binding", "account_id": account_id}
    if platform != "douyin":
        return {"status": "unsupported", "reason": "pilot_only_douyin", "account_id": account_id}

    now_value = time.monotonic() if now_monotonic is None else float(now_monotonic)
    if not force and now_value - float(_LAST_PROBE.get(account_id, 0)) < PROBE_INTERVAL_SECONDS:
        return {"status": "throttled", "reason": "probe_interval", "account_id": account_id}
    _LAST_PROBE[account_id] = now_value

    state = r8_control.control_status()
    device = next((item for item in state.get("devices", []) if item.get("device_id") == device_id), None)
    online = bool(device and device.get("connection") == "connected" and device.get("probe_source") == "adb")
    if not online:
        return {"status": "inconclusive", "reason": "device_offline", "detail": "绑定真机当前未通过 ADB 在线验证", "account_id": account_id}

    result = evaluate_douyin_session(
        alias=account.get("alias") or account.get("label"),
        package_installed=_package_installed(device_id, DOUYIN_PACKAGE),
        foreground_text=_foreground(device_id),
        ui_xml=_ui_xml(device_id),
    )
    result["account_id"] = account_id
    result["device_id"] = device_id
    result["platform"] = platform
    return result


def _persist_probe(account_id, result):
    status = str(result.get("status") or "")
    payload = {"account_id": account_id, "verification_source": "device_probe"}
    if status == "authorized":
        payload.update(login_status="authorized", risk_level="normal", automation_paused=False, last_error="")
    elif status == "needs_human":
        payload.update(login_status="needs_human", risk_level="attention", automation_paused=True, last_error=result.get("detail") or "需要人工验证")
    elif status == "logged_out":
        payload.update(login_status="logged_out", risk_level="normal", automation_paused=True, last_error=result.get("detail") or "平台账号已退出")
    else:
        return
    # deep_productization_patch permits authorized writes only from trusted
    # verification_source=device_probe and then delegates to the core state writer.
    r8_control.update_account_status(payload)
    state = r8_control.control_status()
    account = next((item for item in state.get("accounts", []) if item.get("account_id") == account_id), None)
    if account is not None:
        account["last_login_probe_source"] = "device_probe"
        account["last_login_probe_result"] = status
        account["last_login_probe_detail"] = str(result.get("detail") or "")[:240]
        account["last_login_probe_at"] = r8_control.now_iso()
        r8_control._save(state)


def verify_pending_accounts(*, force=False):
    """Probe pending bound accounts and persist only conclusive real-device truth."""
    state = r8_control.control_status()
    results = []
    for account in list(state.get("accounts") or []):
        if account.get("login_status") == "authorized" and not force:
            continue
        result = probe_account(account, force=force)
        results.append(result)
        if result.get("status") in {"authorized", "needs_human", "logged_out"}:
            _persist_probe(str(account.get("account_id") or ""), result)
    return {"checked": len(results), "results": results, "source": "device_probe", "publishes_content": False}
