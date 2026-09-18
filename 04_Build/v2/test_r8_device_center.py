import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SRC))

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

backend = (SRC / "backend" / "server.py").read_text(encoding="utf-8")
forms = (SRC / "web" / "forms.js").read_text(encoding="utf-8")
ui = (SRC / "web" / "r8_device_center.js").read_text(encoding="utf-8")
control = (SRC / "core" / "r8_control.py").read_text(encoding="utf-8")
adapter = (SRC / "integrations" / "android_device.py").read_text(encoding="utf-8")

for route in (
    "/api/r8/device/status",
    "/api/r8/device/screenshot",
    "/api/r8/device/action",
    "/api/r8/device/takeover",
    "/api/r8/device/audit",
):
    assert route in backend, f"missing backend route: {route}"
assert "r8_device_center.js" in forms
assert "R8-01 单真机设备中心" in ui
assert "只接受本机 ADB" in ui
for field in ("当前平台", "当前账号", "当前任务", "风险状态", "屏幕状态"):
    assert field in ui, f"device card missing field: {field}"
assert "锁屏/熄屏" in ui
assert "screen_locked_or_off" in adapter
assert "device_connected" in adapter and "device_disconnected" in adapter
assert "source != \"adb\"" in control
assert "registered_not_verified" in control

for forbidden in (
    "spoof_imei", "spoof_android_id", "spoof_gps", "bypass_captcha",
):
    assert forbidden not in ui, f"unsafe device UI action exposed: {forbidden}"

print("PASS: R8-01 ADB parsing, device state, lock-stop, audit, UI wiring and safety boundaries are present")
