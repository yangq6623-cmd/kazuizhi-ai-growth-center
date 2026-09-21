"""CPU fallback performance patch for R8 video production.

GitHub hosted Windows runners and user machines without working NVENC must not
spend several minutes encoding short vertical clips with libx264 medium. The
quality target remains CRF 23, but the CPU fallback uses the veryfast preset so
zero-material safe-fallback production can complete within bounded acceptance
windows. RTX/NVENC behavior is unchanged.
"""

from promotion import video_worker


_INSTALLED = False
_ORIGINAL = None


def _encode_args(worker):
    if worker.get("status") == "ready":
        return ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "23", "-b:v", "0"]
    return ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23"]


def install():
    global _INSTALLED, _ORIGINAL
    if _INSTALLED:
        return
    _ORIGINAL = video_worker._encode_args
    video_worker._encode_args = _encode_args
    _INSTALLED = True


install()
