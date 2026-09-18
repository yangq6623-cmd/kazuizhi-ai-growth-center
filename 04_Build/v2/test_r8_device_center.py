import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SRC))

from backend import server  # noqa: E402
from integrations import android_device  # noqa: E402

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
assert android_device._safe_transfer_name("报告 01.pdf") == "报告_01.pdf"
assert android_device._safe_transfer_name("../unsafe.exe") == "unsafe.exe"

backend = (SRC / "backend" / "server.py").read_text(encoding="utf-8")
forms = (SRC / "web" / "forms.js").read_text(encoding="utf-8")
ui = (SRC / "web" / "r8_device_center.js").read_text(encoding="utf-8")
file_ui = (SRC / "web" / "r8_device_file_patch.js").read_text(encoding="utf-8")
control = (SRC / "core" / "r8_control.py").read_text(encoding="utf-8")
adapter = (SRC / "integrations" / "android_device.py").read_text(encoding="utf-8")

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
assert "r8_device_power_policy.js" not in forms, "auto-wake policy is deferred until stable Gate 2 recovery"
assert "社媒中心 · R8-01 单真机终端详情" in ui
assert "社媒中心唯一的真机操作入口" in ui
assert "querySelector('#social-center')" in ui
assert "querySelector('#connections')" not in ui
assert "data-social-device-control" in ui
assert "只接受本机 ADB" in ui
assert "发送文件到手机" in file_ui and "下载到电脑" in file_ui
assert "Download/Kazuizhi" in file_ui
for field in ("当前平台", "当前账号", "当前任务", "风险状态", "屏幕状态"):
    assert field in ui, f"device card missing field: {field}"
assert "锁屏/熄屏" in ui
assert "screen_locked_or_off" in adapter
assert "device_connected" in adapter and "device_disconnected" in adapter
assert "file_push" in adapter and "file_pull" in adapter
assert "source != \"adb\"" in control
assert "registered_not_verified" in control

for forbidden in (
    "spoof_imei", "spoof_android_id", "spoof_gps", "bypass_captcha",
):
    assert forbidden not in ui and forbidden not in file_ui, f"unsafe device UI action exposed: {forbidden}"

print("PASS: R7 GET routes are isolated from ADB, phone controls live only in social center, and #190 device/file/safety capabilities remain wired")
