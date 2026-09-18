import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SRC))

sandbox = Path(tempfile.mkdtemp(prefix="kazuizhi-r8-00-"))
os.environ["LOCALAPPDATA"] = str(sandbox)

try:
    from core.r8_control import (
        authorize_action, control_status, record_device_probe, register_account,
        register_device, set_global_pause, set_owner_focus,
    )

    state = control_status()
    if state.get("schema") != "kazuizhi-r8-control/v1":
        raise AssertionError("R8 control schema missing")
    if state.get("pilot", {}).get("device_limit") != 1:
        raise AssertionError("R8 must start with one real-device pilot")
    rules = state.get("hard_rules", {})
    required_rules = (
        "real_device_only", "no_device_spoofing", "no_risk_evasion",
        "verification_requires_human", "video_publish_requires_owner_approval",
        "finance_requires_human", "truthful_receipts_required",
    )
    for key in required_rules:
        if rules.get(key) is not True:
            raise AssertionError(f"R8 hard rule missing: {key}")

    state = register_device({"device_id": "ANDROID-TEST-01", "label": "测试手机01", "transport": "usb"})
    device = state["devices"][0]
    if device.get("connection") != "registered_not_verified":
        raise AssertionError("Registering a device must not pretend it is connected")

    try:
        register_device({"device_id": "ANDROID-TEST-02", "label": "测试手机02"})
    except ValueError as exc:
        if "单真机试点" not in str(exc):
            raise
    else:
        raise AssertionError("Second device must be blocked during the pilot")

    state = record_device_probe("ANDROID-TEST-01", True, source="adb", detail="test adapter")
    if state["devices"][0].get("connection") != "connected":
        raise AssertionError("ADB probe did not mark real device connected")

    state = register_account({
        "platform": "douyin", "device_id": "ANDROID-TEST-01", "alias": "抖音试点账号"
    })
    if state["accounts"][0].get("platform") != "douyin":
        raise AssertionError("Platform account was not registered")

    set_owner_focus({
        "mode": "platform_learning",
        "instruction": "明天以平台学习和正常浏览为重点，少量有价值互动，不做批量刷量。",
    })
    set_global_pause(False, "single-device pilot enabled")

    browse = authorize_action({
        "platform": "douyin", "device_id": "ANDROID-TEST-01", "action": "platform_learning"
    })
    if not browse.get("allowed"):
        raise AssertionError(f"Low-risk platform learning should be allowed: {browse}")

    video = authorize_action({
        "platform": "douyin", "device_id": "ANDROID-TEST-01", "action": "publish_video"
    })
    if video.get("allowed") or not video.get("requires_human"):
        raise AssertionError("Video publishing must require owner approval")

    video_approved = authorize_action({
        "platform": "douyin", "device_id": "ANDROID-TEST-01", "action": "publish_video",
        "owner_approved": True,
    })
    if not video_approved.get("allowed"):
        raise AssertionError("Owner-approved video should pass the R8-00 gate")

    verify = authorize_action({
        "platform": "douyin", "device_id": "ANDROID-TEST-01", "action": "comment",
        "verification_required": True,
    })
    if verify.get("allowed") or not verify.get("requires_human"):
        raise AssertionError("Verification must stop automation and require human handling")

    for forbidden in ("pay", "spoof_device", "rotate_ip_to_evade_risk"):
        result = authorize_action({
            "platform": "douyin", "device_id": "ANDROID-TEST-01", "action": forbidden
        })
        if result.get("allowed"):
            raise AssertionError(f"Forbidden R8 action was allowed: {forbidden}")

    print("PASS: R8-00 single-real-device pilot, owner focus, video approval gate, finance/manual boundary, anti-spoofing and verification fail-safe")
finally:
    shutil.rmtree(sandbox, ignore_errors=True)
