import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SRC))

from backend import server  # noqa: E402
import backend.realtime_mirror_patch  # noqa: F401,E402
from integrations import android_live_mirror  # noqa: E402

mirror_backend = (SRC / "integrations" / "android_live_mirror.py").read_text(encoding="utf-8")
route_patch = (SRC / "backend" / "realtime_mirror_patch.py").read_text(encoding="utf-8")
mirror_ui = (SRC / "web" / "r8_device_b4_mirror_hotfix.js").read_text(encoding="utf-8")
operational_ui = (SRC / "web" / "operational-device.js").read_text(encoding="utf-8")
operational_html = (SRC / "web" / "operational.html").read_text(encoding="utf-8")
operational_runtime_test = (ROOT / "04_Build" / "v2" / "test_operational_device_live.js").read_text(encoding="utf-8")
run_source = (SRC / "run.py").read_text(encoding="utf-8")
requirements = (SRC / "requirements.txt").read_text(encoding="utf-8")

# Real-time mirror transport must be a persistent video producer, not one ADB
# screencap process per displayed frame.
assert "screenrecord" in mirror_backend
assert "--output-format=h264" in mirror_backend
assert "imageio_ffmpeg" in mirror_backend
assert "multipart/x-mixed-replace" in mirror_backend or "stream_mjpeg" in mirror_backend
assert "TARGET_FPS = 20" in mirror_backend
assert "browser_transport" in mirror_backend and "mjpeg" in mirror_backend

# The local HTTP layer exposes one long-lived stream plus a lightweight status
# endpoint. The old PNG screenshot route remains available only as fallback.
assert "/api/r8/device/live" in route_patch
assert "/api/r8/device/live-status" in route_patch
assert getattr(server.DashboardHandler, "_kz_realtime_mirror_patched", False) is True
assert "realtime_mirror_patch" in run_source

# Both device consoles must use the same persistent live stream. This specifically
# protects the Operational page from regressing to its former 1.2-second PNG loop.
for ui in (mirror_ui, operational_ui):
    assert "/api/r8/device/live?device_id=" in ui
    assert "/api/r8/device/live-status?device_id=" in ui
    assert "实时流暂不可用" in ui
    assert "/api/r8/device/screenshot?device_id=" in ui, "single-frame emergency fallback must remain available"

assert "实时手机投屏" in mirror_ui
assert "H.264 持续采集" in mirror_ui
assert "function activateFallback" in mirror_ui
assert "function startContinuous" in mirror_ui
assert "validPng" in mirror_ui

assert "实时投屏真实 Android 手机" in operational_ui
assert "持续视频流" in operational_ui
assert "function activateFallback" in operational_ui
assert "function pollLiveStatus" in operational_ui
assert "function startFallbackLoop" in operational_ui
assert "function heartbeat" in operational_ui
assert "heartbeatTimer" in operational_ui
assert "setTimeout(()=>schedule(false),1200)" not in operational_ui
assert "function schedule(" not in operational_ui
assert "setMirror('连续同步正常'" not in operational_ui
for metric_id in ("device-live-state", "device-live-fps", "device-live-latency", "device-live-reconnects", "device-live-fallback"):
    assert metric_id in operational_html
assert "normal live mode must not continue the old screenshot polling loop" in operational_runtime_test
assert "requests.filter(request => request.url.includes('/api/r8/device/screenshot')).length" in operational_runtime_test

# Packaged FFmpeg is already part of the Windows runtime and is reused for local
# low-latency decode. No external browser service or unsafe phone spoofing is added.
assert "imageio-ffmpeg" in requirements
for forbidden in ("bypass_captcha", "spoof_imei", "spoof_android_id", "spoof_gps"):
    assert forbidden not in mirror_backend
    assert forbidden not in mirror_ui
    assert forbidden not in operational_ui

idle = android_live_mirror.live_status("PHONE-TEST")
assert idle["state"] == "idle"
assert idle["source"] == "screenrecord_h264"
assert idle["target_fps"] == 20

print("PASS: main and Operational Android consoles use persistent H.264/MJPEG live mirror with PNG fallback")
