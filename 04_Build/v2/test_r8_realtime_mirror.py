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

# Browser UX must start the live stream directly and only enter the old PNG path
# when the continuous stream fails or is deliberately tested.
assert "实时手机投屏" in mirror_ui
assert "/api/r8/device/live?device_id=" in mirror_ui
assert "/api/r8/device/live-status?device_id=" in mirror_ui
assert "H.264 持续采集" in mirror_ui
assert "实时流暂不可用 · 单帧备用" in mirror_ui
assert "function activateFallback" in mirror_ui
assert "function startContinuous" in mirror_ui
assert "validPng" in mirror_ui, "single-frame emergency fallback must remain truthful"

# Packaged FFmpeg is already part of the Windows runtime and is reused for local
# low-latency decode. No external browser service or unsafe phone spoofing is added.
assert "imageio-ffmpeg" in requirements
for forbidden in ("bypass_captcha", "spoof_imei", "spoof_android_id", "spoof_gps"):
    assert forbidden not in mirror_backend
    assert forbidden not in mirror_ui

idle = android_live_mirror.live_status("PHONE-TEST")
assert idle["state"] == "idle"
assert idle["source"] == "screenrecord_h264"
assert idle["target_fps"] == 20

print("PASS: Android mirror uses persistent H.264 capture with low-latency browser stream and PNG fallback")
