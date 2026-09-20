"""Managed local-media intake for the R8 content factory."""

from __future__ import annotations

import os
import re
from pathlib import Path
from uuid import uuid4
from urllib.parse import unquote

from core.storage import data_root
from promotion.content_factory import add_asset


MAX_UPLOAD = 300 * 1024 * 1024


def _safe_name(name):
    base = Path(str(name or "material.bin")).name
    stem = re.sub(r"[^0-9A-Za-z._-]+", "_", base).strip("._")[:100]
    return stem or "material.bin"


def receive(stream, length, headers):
    if length <= 0:
        raise ValueError("没有收到素材文件")
    if length > MAX_UPLOAD:
        raise ValueError("单个素材暂限300MB")
    campaign_id = unquote(str(headers.get("X-Campaign-ID") or "")).strip()
    kind = unquote(str(headers.get("X-Asset-Kind") or "")).strip()
    consent = str(headers.get("X-Consent-Confirmed") or "").lower() in {"1", "true", "yes"}
    filename = _safe_name(unquote(str(headers.get("X-Filename") or "")))
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
        return add_asset({
            "campaign_id": campaign_id, "kind": kind,
            "local_path": str(final_path), "consent_confirmed": consent,
            "note": "由内容工厂上传并纳入本地素材库",
        })
    except Exception:
        if temporary.exists():
            try:
                temporary.unlink()
            except OSError:
                pass
        raise
