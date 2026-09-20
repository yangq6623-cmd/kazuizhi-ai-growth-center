"""Low-latency Android live mirror transport for R8.

The old mirror path executed ``adb screencap`` for every visible frame. That is
truthful but it can only behave like a slideshow. This module keeps one Android
``screenrecord`` H.264 producer alive, decodes it locally with the already
packaged imageio-ffmpeg binary, and exposes a continuous MJPEG stream to the
local browser. Control actions remain on the existing audited ADB control path.

Security boundaries are unchanged: this module only mirrors the display. It
never unlocks secure PIN/password/biometric screens and it never bypasses
platform verification.
"""

from __future__ import annotations

import collections
import subprocess
import threading
import time
import uuid

from imageio_ffmpeg import get_ffmpeg_exe

from . import android_device as _base

TARGET_FPS = 20
MAX_WIDTH = 720
BIT_RATE = 6_000_000
BOUNDARY = "kzframe"
_CREATE_NO_WINDOW = getattr(subprocess, "CREATE_NO_WINDOW", 0)

_ORIGINAL_SCAN = _base.scan_and_sync

_LOCK = threading.RLock()
_ACTIVE = {}
_STATS = {}


def _now():
    return time.time()


def _empty_stats(device_id):
    return {
        "device_id": device_id,
        "state": "idle",
        "source": "screenrecord_h264",
        "transport": "usb_adb",
        "browser_transport": "mjpeg",
        "target_fps": TARGET_FPS,
        "fps": 0.0,
        "frame_count": 0,
        "last_frame_at": None,
        "last_frame_age_ms": None,
        "restart_count": 0,
        "clients": 0,
        "last_error": None,
    }


def _stats_for(device_id):
    with _LOCK:
        return _STATS.setdefault(device_id, _empty_stats(device_id))


def live_status(device_id):
    device_id = str(device_id or "").strip()
    if not device_id:
        return _empty_stats("")
    with _LOCK:
        snapshot = dict(_STATS.get(device_id) or _empty_stats(device_id))
    last = snapshot.get("last_frame_at")
    snapshot["last_frame_age_ms"] = int(max(0, (_now() - last) * 1000)) if last else None
    return snapshot


def _terminate(process):
    if not process:
        return
    try:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=1.5)
            except subprocess.TimeoutExpired:
                process.kill()
    except OSError:
        pass


class _LiveSession:
    def __init__(self, device_id):
        self.device_id = device_id
        self.token = uuid.uuid4().hex
        self.stop = threading.Event()
        self.screen = None
        self.ffmpeg = None

    def close(self):
        self.stop.set()
        _terminate(self.ffmpeg)
        _terminate(self.screen)


def _replace_session(device_id):
    session = _LiveSession(device_id)
    with _LOCK:
        previous = _ACTIVE.get(device_id)
        _ACTIVE[device_id] = session
    if previous:
        previous.close()
    return session


def _is_current(session):
    with _LOCK:
        return _ACTIVE.get(session.device_id) is session and not session.stop.is_set()


def _record_error(device_id, error):
    with _LOCK:
        stats = _STATS.setdefault(device_id, _empty_stats(device_id))
        stats["state"] = "recovering"
        stats["last_error"] = str(error)[:300]


def _record_start(device_id, restarted=False):
    with _LOCK:
        stats = _STATS.setdefault(device_id, _empty_stats(device_id))
        stats["state"] = "connecting"
        stats["clients"] = 1
        stats["last_error"] = None
        if restarted:
            stats["restart_count"] = int(stats.get("restart_count") or 0) + 1


def _record_frame(device_id, stamps):
    now = _now()
    stamps.append(now)
    while stamps and now - stamps[0] > 2.0:
        stamps.popleft()
    fps = 0.0
    if len(stamps) > 1:
        span = max(0.001, stamps[-1] - stamps[0])
        fps = (len(stamps) - 1) / span
    with _LOCK:
        stats = _STATS.setdefault(device_id, _empty_stats(device_id))
        stats["state"] = "streaming"
        stats["frame_count"] = int(stats.get("frame_count") or 0) + 1
        stats["last_frame_at"] = now
        stats["fps"] = round(fps, 1)
        stats["last_error"] = None


def _record_stop(device_id, session):
    with _LOCK:
        if _ACTIVE.get(device_id) is session:
            _ACTIVE.pop(device_id, None)
        stats = _STATS.setdefault(device_id, _empty_stats(device_id))
        stats["clients"] = 0
        if stats.get("state") != "recovering":
            stats["state"] = "idle"


def _start_pipeline(device_id, restarted=False):
    adb = _base.find_adb()
    if not adb:
        raise RuntimeError("未找到 adb.exe，无法启动实时投屏")
    state = str(_base._run(["-s", device_id, "get-state"], timeout=4) or "").strip()
    if state != "device":
        raise RuntimeError("真实手机当前未通过 ADB 在线")

    ffmpeg_exe = get_ffmpeg_exe()
    screen_cmd = [
        adb, "-s", device_id, "exec-out", "screenrecord",
        "--output-format=h264", "--bit-rate", str(BIT_RATE), "-",
    ]
    ffmpeg_cmd = [
        ffmpeg_exe,
        "-hide_banner", "-loglevel", "error",
        "-fflags", "nobuffer", "-flags", "low_delay",
        "-f", "h264", "-i", "pipe:0",
        "-an",
        "-vf", f"fps={TARGET_FPS},scale={MAX_WIDTH}:-2",
        "-q:v", "5",
        "-f", "image2pipe", "-vcodec", "mjpeg", "pipe:1",
    ]
    screen = subprocess.Popen(
        screen_cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
        creationflags=_CREATE_NO_WINDOW,
    )
    if not screen.stdout:
        _terminate(screen)
        raise RuntimeError("Android 实时画面通道没有返回视频数据")
    ffmpeg = subprocess.Popen(
        ffmpeg_cmd,
        stdin=screen.stdout,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        bufsize=0,
        creationflags=_CREATE_NO_WINDOW,
    )
    screen.stdout.close()
    _record_start(device_id, restarted=restarted)
    return screen, ffmpeg


def _jpeg_frames(stream, session):
    """Yield complete JPEG images from ffmpeg's image2pipe stdout."""
    buffer = bytearray()
    while _is_current(session):
        chunk = stream.read(64 * 1024)
        if not chunk:
            return
        buffer.extend(chunk)
        while True:
            start = buffer.find(b"\xff\xd8")
            if start < 0:
                if len(buffer) > 2:
                    del buffer[:-2]
                break
            end = buffer.find(b"\xff\xd9", start + 2)
            if end < 0:
                if start:
                    del buffer[:start]
                break
            end += 2
            frame = bytes(buffer[start:end])
            del buffer[:end]
            if len(frame) > 1024:
                yield frame


def stream_mjpeg(handler, device_id):
    """Write a long-lived multipart MJPEG response to ``handler.wfile``."""
    device_id = str(device_id or "").strip()
    if not device_id:
        raise ValueError("device_id 不能为空")
    _base._require_connected(device_id)
    get_ffmpeg_exe()  # fail before headers if the packaged decoder is unavailable

    session = _replace_session(device_id)
    handler.send_response(200)
    handler.send_header("Content-Type", f"multipart/x-mixed-replace; boundary={BOUNDARY}")
    handler.send_header("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
    handler.send_header("Pragma", "no-cache")
    handler.send_header("Connection", "close")
    handler.end_headers()

    stamps = collections.deque(maxlen=80)
    first = True
    try:
        while _is_current(session):
            screen = ffmpeg = None
            try:
                screen, ffmpeg = _start_pipeline(device_id, restarted=not first)
                session.screen, session.ffmpeg = screen, ffmpeg
                first = False
                if not ffmpeg.stdout:
                    raise RuntimeError("本地视频解码器没有输出实时画面")
                for frame in _jpeg_frames(ffmpeg.stdout, session):
                    if not _is_current(session):
                        break
                    _record_frame(device_id, stamps)
                    header = (
                        f"--{BOUNDARY}\r\n"
                        "Content-Type: image/jpeg\r\n"
                        f"Content-Length: {len(frame)}\r\n\r\n"
                    ).encode("ascii")
                    handler.wfile.write(header)
                    handler.wfile.write(frame)
                    handler.wfile.write(b"\r\n")
                    handler.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, ConnectionAbortedError):
                break
            except (OSError, RuntimeError, subprocess.SubprocessError) as error:
                _record_error(device_id, error)
                if not _is_current(session):
                    break
                time.sleep(0.45)
            finally:
                _terminate(ffmpeg)
                _terminate(screen)
                session.ffmpeg = None
                session.screen = None
    finally:
        session.close()
        _record_stop(device_id, session)


def scan_and_sync():
    """Add live-mirror truth to the existing device status without extra ADB work."""
    result = _ORIGINAL_SCAN()
    for item in result.get("devices") or []:
        item["live_mirror"] = live_status(item.get("device_id"))
    primary = result.get("primary_device_id")
    result["live_mirror"] = live_status(primary) if primary else _empty_stats("")
    return result


# Keep the stable backend API surface. server.py imports these names from
# integrations.android_device after package initialisation, so replacing the
# scan function here automatically gives every device page one shared truth.
_base.scan_and_sync = scan_and_sync
_base.live_mirror_status = live_status
