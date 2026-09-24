"""CPU fallback performance patch for R8 video production.

GitHub hosted Windows runners and user machines without working NVENC must not
spend several minutes encoding short vertical clips before the automatic worker
can reach ChatGPT content QC. RTX/NVENC behavior is unchanged.

The CPU fallback keeps H.264, the requested frame size/fps and CRF 23, but uses
x264's ultrafast preset. Preset changes compression efficiency/file size rather
than relaxing the technical-QC contract, and is appropriate only when NVENC is
not available. This keeps zero-material safe-fallback production bounded while
preserving a standards-compatible MP4 for the same downstream QC path.
"""

from promotion import video_worker


_INSTALLED = False
_ORIGINAL = None


def _encode_args(worker):
    if worker.get("status") == "ready":
        return ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "23", "-b:v", "0"]
    return ["-c:v", "libx264", "-preset", "ultrafast", "-crf", "23"]


def install():
    global _INSTALLED, _ORIGINAL
    if _INSTALLED:
        return
    _ORIGINAL = video_worker._encode_args
    video_worker._encode_args = _encode_args
    _INSTALLED = True


install()
