"""#71.1 stability hotfix for final-render encoder compatibility.

Some bundled FFmpeg builds expose h264_nvenc in `-encoders` even when the
installed NVIDIA driver only supports an older NVENC API. #71 originally used
that listing as the readiness check, so a real encode could fail with messages
such as "Driver does not support the required nvenc API version".

This patch probes one tiny real NVENC encode before selecting the hardware
encoder. If the probe fails for any reason, final rendering transparently falls
back to high-quality libx264. Candidate files and selected shots are preserved.
"""
from __future__ import annotations

import threading
import time

from backend import final_render_patch as _final

_PROBE_LOCK = threading.Lock()
_PROBE_CACHE = {}


def _software_encoder_args():
    return ["-c:v", "libx264", "-preset", "medium", "-crf", "18"]


def _nvenc_probe(ffmpeg):
    key = str(ffmpeg)
    with _PROBE_LOCK:
        if key in _PROBE_CACHE:
            return _PROBE_CACHE[key]

    # A real encode probe is required. Merely seeing h264_nvenc in FFmpeg's
    # encoder list does not prove that the installed driver supports the NVENC
    # API version expected by this FFmpeg build.
    listing = _final._run([ffmpeg, "-hide_banner", "-encoders"], timeout=30)
    encoders = (listing.stdout + listing.stderr).decode("utf-8", "replace")
    if "h264_nvenc" not in encoders:
        result = {"ok": False, "reason": "FFmpeg未提供h264_nvenc"}
    else:
        probe = _final._run([
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "color=c=black:s=64x64:r=1:d=0.2",
            "-frames:v", "1", "-c:v", "h264_nvenc", "-preset", "p5",
            "-f", "null", "-",
        ], timeout=45)
        text = (probe.stderr or probe.stdout).decode("utf-8", "replace")[-1200:]
        result = {
            "ok": probe.returncode == 0,
            "reason": "NVENC真实编码探测通过" if probe.returncode == 0 else (text or "NVENC真实编码探测失败"),
        }

    with _PROBE_LOCK:
        _PROBE_CACHE[key] = result
    return result


def _encoder_args(ffmpeg):
    cache_key = ("encoder", str(ffmpeg))
    cached = _final._FILTER_CACHE.get(cache_key)
    if cached:
        return list(cached)
    probe = _nvenc_probe(ffmpeg)
    if probe.get("ok"):
        args = ["-c:v", "h264_nvenc", "-preset", "p5", "-cq", "19", "-b:v", "0"]
        mode = "NVENC"
    else:
        args = _software_encoder_args()
        mode = "libx264"
    _final._FILTER_CACHE[cache_key] = tuple(args)
    _final._FILTER_CACHE[("encoder_mode", str(ffmpeg))] = mode
    _final._FILTER_CACHE[("encoder_probe", str(ffmpeg))] = probe
    return list(args)


def _retry_pending_after_patch():
    # final_render_patch may have started its recovery worker a few milliseconds
    # before this compatibility layer was imported. Give that old attempt time
    # to exit, then restart the still-persisted final task with the patched
    # encoder selector. Completed #70 candidates are never regenerated.
    for _ in range(20):
        time.sleep(0.5)
        thread = getattr(_final, "_FINAL_THREAD", None)
        if thread is None or not thread.is_alive():
            if _final._pending_final_tasks():
                _final._set_state(
                    status="queued",
                    stage="兼容性回退后重试",
                    message="检测到NVENC兼容问题时会自动回退libx264；正在继续原成片任务。",
                    last_error="",
                )
                _final._start_worker()
            return


# Replace the selector before any later render/subtitle call resolves it.
_final._FILTER_CACHE.pop(("encoder", str(_final.find_ffmpeg() or "")), None)
_final._encoder_args = _encoder_args

threading.Thread(
    target=_retry_pending_after_patch,
    name="kazuizhi-final-render-71-1-retry",
    daemon=True,
).start()
