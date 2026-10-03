"""Managed local-media intake for the R8 content factory.

The owner only drops files into the material box. Initial media type is
inferred from the file extension; semantic classification, scoring and final
selection remain ChatGPT/system responsibilities. Local material is optional
and never blocks production.
"""

from __future__ import annotations

import os
import re
from pathlib import Path
from uuid import uuid4
from urllib.parse import unquote

from core.storage import data_root
from promotion import content_factory as cf


MAX_UPLOAD = 300 * 1024 * 1024
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".avi", ".mkv", ".webm", ".3gp", ".mts", ".m2ts"}
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".heic", ".heif"}
AUDIO_EXTENSIONS = {".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg", ".wma"}
ALLOWED_EXTENSIONS = VIDEO_EXTENSIONS | IMAGE_EXTENSIONS | AUDIO_EXTENSIONS


def _safe_name(name):
    """Preserve the real extension even when the original stem is Chinese."""
    base = Path(str(name or "material.bin")).name
    suffix = Path(base).suffix.lower()
    if suffix not in ALLOWED_EXTENSIONS:
        suffix = re.sub(r"[^0-9A-Za-z.]", "", suffix)[:12]
    raw_stem = Path(base).stem
    safe_stem = re.sub(r"[^0-9A-Za-z_-]+", "_", raw_stem).strip("_")[:90]
    if not safe_stem:
        safe_stem = "material"
    return f"{safe_stem}{suffix}" if suffix else safe_stem


def infer_kind(filename, requested=""):
    """Return a conservative initial technical class for a user-uploaded file."""
    suffix = Path(str(filename or "")).suffix.lower()
    if suffix in VIDEO_EXTENSIONS:
        return "真实现场视频"
    if suffix in IMAGE_EXTENSIONS:
        return "真实现场照片"
    if suffix in AUDIO_EXTENSIONS:
        return "师傅讲解"
    requested = str(requested or "").strip()
    # Compatibility only for older brand/AI material callers. Real uploaded
    # photos/video/audio are classified from the file itself, not a dropdown.
    if requested in {"品牌素材", "AI辅助镜头"}:
        return requested
    raise ValueError("暂不支持该素材格式；请上传常见图片、视频或音频文件")


def receive(stream, length, headers):
    if length <= 0:
        raise ValueError("没有收到素材文件")
    if length > MAX_UPLOAD:
        raise ValueError("单个素材暂限300MB")
    campaign_id = unquote(str(headers.get("X-Campaign-ID") or "")).strip()
    requested_kind = unquote(str(headers.get("X-Asset-Kind") or "")).strip()
    consent = str(headers.get("X-Consent-Confirmed") or "").lower() in {"1", "true", "yes"}
    original_filename = unquote(str(headers.get("X-Filename") or ""))
    filename = _safe_name(original_filename)
    kind = infer_kind(filename, requested_kind)
    if kind.startswith("真实") and not consent:
        raise ValueError("上传真实照片或视频前，请确认拥有使用权及必要的拍摄/发布授权")
    directory = data_root() / "r8" / "assets" / re.sub(r"[^0-9A-Za-z-]", "", campaign_id)[:64]
    directory.mkdir(parents=True, exist_ok=True)
    final_path = directory / f"{uuid4().hex[:10]}_{filename}"
    temporary = final_path.with_suffix(final_path.suffix + ".uploading")
    remaining = length
    try:
        with temporary.open("xb") as handle:
            while remaining:
                chunk = stream.read(min(1024 * 1024, remaining))
                if not chunk:
                    raise ValueError("素材上传中断，请重新选择文件")
                handle.write(chunk)
                remaining -= len(chunk)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, final_path)
        # Resolve through the module at call time so the final V2 extension
        # wrapper adds source/provenance/index metadata after all patches load.
        return cf.add_asset({
            "campaign_id": campaign_id,
            "kind": kind,
            "local_path": str(final_path),
            "consent_confirmed": consent,
            "note": "由内容工厂批量投递；初始类型自动识别，最终是否采用由ChatGPT决定",
            "source_origin": "manual_upload",
            "media_metadata": {
                "original_filename": Path(original_filename).name[:180],
                "stored_filename": filename,
                "auto_classified": True,
            },
        })
    except Exception:
        if temporary.exists():
            try:
                temporary.unlink()
            except OSError:
                pass
        raise
