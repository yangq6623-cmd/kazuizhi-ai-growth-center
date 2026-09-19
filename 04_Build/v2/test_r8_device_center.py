import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SRC))

from backend import server  # noqa: E402
from integrations import android_device, bridge  # noqa: E402

sample = """List of devices attached
M5QNU22319503960 device product:demo model:ETO-BD00 device:demo transport_id:1
SECOND unauthorized transport_id:2
"""
items = android_device._parse_devices_output(sample)
assert len(items) == 2
assert items[0]["device_id"] == "M5QNU22319503960"
assert items[0]["state"] == "device"
assert items[0]["model_hint"] == "ETO-BD00"
assert items[1]["state"] == "unauthorized"
assert android_device._parse_battery_output("AC powered: true\n  level: 87\n") == 87
assert android_device._parse_screen_size("Physical size: 1080x2400\n") == {"width": 1080, "height": 2400}
assert android_device._parse_awake("mWakefulness=Awake") is True
assert android_device._parse_awake("mWakefulness=Asleep") is False
assert android_device._parse_awake("vendor-specific unknown state") is None
assert android_device._parse_trust_state("deviceLocked=true deviceSecure=true") == {"locked": True, "secure": True}
assert android_device._screen_state(False, True, True)[0] == "screen_off"
assert android_device._screen_state(True, True, True)[0] == "secure_lock"
assert android_device._screen_state(True, False, True)[0] == "awake"
assert android_device._safe_transfer_name("报告 01.pdf") == "报告_01.pdf"
assert android_device._safe_transfer_name("../unsafe.exe") == "unsafe.exe"
assert bridge._drive_relative_tail(r"G:\我的云端硬盘\AI_Command") == "我的云端硬盘/AI_Command"

# Persisted ADB path must survive process restarts/upgrades because it lives in
# the durable LOCALAPPDATA data root rather than the installation directory.
with tempfile.TemporaryDirectory() as tmp:
    old_local = os.environ.get("LOCALAPPDATA")
    old_adb = os.environ.get("KAZUIZHI_ADB_PATH")
    try:
        os.environ["LOCALAPPDATA"] = tmp
        fake = Path(tmp) / "platform-tools" / "adb.exe"
        fake.parent.mkdir(parents=True, exist_ok=True)
        fake.write_bytes(b"fake")
        os.environ["KAZUIZHI_ADB_PATH"] = str(fake)
        assert android_device.find_adb() == str(fake.resolve())
        os.environ.pop("KAZUIZHI_ADB_PATH", None)
        assert next(iter(android_device._candidate_adb_paths())) == fake.resolve()
    finally:
        if old_local is None:
            os.environ.pop("LOCALAPPDATA", None)
        else:
            os.environ["LOCALAPPDATA"] = old_local
        if old_adb is None:
            os.environ.pop("KAZUIZHI_ADB_PATH", None)
        else:
            os.environ["KAZUIZHI_ADB_PATH"] = old_adb

backend = (SRC / "backend" / "server.py").read_text(encoding="utf-8")
forms = (SRC / "web" / "forms.js").read_text(encoding="utf-8")
index_ui = (SRC / "web" / "index.html").read_text(encoding="utf-8")
ui = (SRC / "web" / "r8_device_center.js").read_text(encoding="utf-8")
file_ui = (SRC / "web" / "r8_device_file_patch.js").read_text(encoding="utf-8")
persistence_ui = (SRC / "web" / "r8_persistence_patch.js").read_text(encoding="utf-8")
cockpit_ui = (SRC / "web" / "r8_terminal_cockpit_patch.js").read_text(encoding="utf-8")
b3_ui = (SRC / "web" / "r8_device_b3_patch.js").read_text(encoding="utf-8")
b4_ui = (SRC / "web" / "r8_device_b4_mirror_hotfix.js").read_text(encoding="utf-8")
identity_ui = (SRC / "web" / "r8_identity.js").read_text(encoding="utf-8")
control = (SRC / "core" / "r8_control.py").read_text(encoding="utf-8")
adapter = (SRC / "integrations" / "android_device.py").read_text(encoding="utf-8")
adapter_b3 = (SRC / "integrations" / "android_device_b3.py").read_text(encoding="utf-8")
bridge_source = (SRC / "integrations" / "bridge.py").read_text(encoding="utf-8")

for route in (
    "/api/r8/device/status",
    "/api/r8/device/screenshot",
    "/api/r8/device/action",
    "/api/r8/device/takeover",
    "/api/r8/device/audit",
    "/api/r8/device/files",
    "/api/r8/device/file",
    "/api/r8/device/file-push",
):
    assert route in backend, f"missing backend route: {route}"

# R7 and R8 must be resolved lazily. An ordinary R7 status request must not
# touch ADB at all, even if the phone adapter would fail.
handler = object.__new__(server.DashboardHandler)
original_scan = server.device_scan_and_sync
try:
    def fail_if_scanned():
        raise AssertionError("R7 request must not scan ADB")

    server.device_scan_and_sync = fail_if_scanned
    status = handler._api_get_payload("/api/status")
    assert status["status"] == "online"
finally:
    server.device_scan_and_sync = original_scan

sentinel = {"devices": [], "message": "explicit r8 scan"}
try:
    server.device_scan_and_sync = lambda: sentinel
    assert handler._api_get_payload("/api/r8/device/status") is sentinel
finally:
    server.device_scan_and_sync = original_scan

assert "routes = {" not in backend, "GET routes must not eagerly execute every R7/R8 provider"
assert backend.count("device_scan_and_sync()") == 1, "ADB scan must only live behind its explicit R8 device route"
assert "r8_device_center.js" in forms
assert "r8_device_file_patch.js" in forms
assert "r8_persistence_patch.js" in forms
assert "社媒中心 · R8-01B 真机操作台" in ui
assert "电脑端直接操作真实 Android 手机" in ui
assert "querySelector('#social-center')" in ui
assert "querySelector('#connections')" not in ui
assert "data-social-device-control" in ui
assert "pointerdown" in ui and "pointerup" in ui
assert "普通熄屏" in ui and "安全锁" in ui
assert "keep_awake" in ui and "keep_awake_on" in adapter and "keep_awake_off" in adapter
assert 'data-r8-action="wake"' in ui
assert "auto_wake" in adapter
assert "screen_off" in adapter and "secure_lock" in adapter and "keyguard_locked" in adapter
assert "ADB_CONFIG_PATH" in adapter and "last_device_id" in adapter
assert "device_connected" in adapter and "device_disconnected" in adapter
assert "file_push" in adapter and "file_pull" in adapter
assert "source != \"adb\"" in control
assert "registered_not_verified" in control
assert "auto_drive_recovery" in bridge_source and "_candidate_relocated_roots" in bridge_source
assert "/api/business-source/test" in persistence_ui
assert "KAZUIZHI_SAVED_KEY" in persistence_ui
assert "发送文件到手机" in file_ui and "下载到电脑" in file_ui
assert "Download/Kazuizhi" in file_ui
for field in ("当前平台", "当前账号", "当前任务", "风险状态", "屏幕状态"):
    assert field in ui, f"device console missing field: {field}"

# R8-01B.2/3 cockpit contract: platform icons/context, virtual screen refresh,
# ordinary screen-off auto resume, non-secure keyguard dismissal and safe app launch.
assert "kz-platform-dock" in cockpit_ui and "kz-platform-icon" in cockpit_ui
assert "任务" in cockpit_ui and "平台" in cockpit_ui and "人工处理" in cockpit_ui and "日志" in cockpit_ui
mirror_tag = 'r8_device_b4_mirror_hotfix.js?v=R8-01B.5'
assert mirror_tag in index_ui, "stable phone mirror must be loaded directly by index.html"
assert index_ui.index(mirror_tag) < index_ui.index('forms.js'), "phone mirror must boot before dynamic UI patches"
assert "r8_device_b3_patch.js" in identity_ui
assert "r8_device_b4_mirror_hotfix.js" in identity_ui, "identity loader must retain a runtime fallback"
assert "R8-01B.5" in identity_ui
assert "R8-01B.4.3" in identity_ui
assert "R8DeviceMirrorSync" in b4_ui and "validPng" in b4_ui
assert "keep_awake_on" in b3_ui and "keep_awake_off" in b3_ui
assert "refreshMirror" in b3_ui and "screen_off" in b3_ui
assert "data-kz-platform" in b3_ui and "launch_app" in b3_ui
assert "PLATFORM_PACKAGES" in adapter_b3 and "launch_app" in adapter_b3
assert "auto_dismiss_keyguard" in adapter_b3 and "device_secure" in adapter_b3
for package in (
    "com.ss.android.ugc.aweme", "com.xingin.xhs", "com.smile.gifmaker",
    "com.tencent.mm", "com.sina.weibo", "tv.danmaku.bili",
):
    assert package in adapter_b3, f"missing safe platform package allowlist: {package}"

for forbidden in (
    "spoof_imei", "spoof_android_id", "spoof_gps", "bypass_captcha",
):
    assert forbidden not in ui and forbidden not in file_ui and forbidden not in adapter and forbidden not in adapter_b3 and forbidden not in b3_ui, f"unsafe device action exposed: {forbidden}"

print("PASS: R8-01A durable configuration and R8-01B.3 virtual phone control contracts are wired without breaking R7 route isolation")
