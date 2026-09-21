"""Structured local material inbox and technical index for R8.

The owner may drop optional files under ``data/r8/material_inbox/<campaign_id>``.
Every supported file is indexed, but it becomes usable only when a sidecar
classifies it. Real customer/repair material additionally requires consent.
Unchanged files reuse both fingerprints and technical probes, making frequent
background scans inexpensive even when the library grows.
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
from pathlib import Path

from core.storage import data_root, now_iso, read_json, write_json


INDEX_FILE = "r8/material_index.json"
SUPPORTED = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".wav", ".mp3", ".m4a"}
PUBLISHABLE_KINDS = {"真实现场视频", "真实现场照片", "师傅讲解", "品牌素材", "AI辅助镜头"}


def inbox_root():
    root = data_root() / "r8" / "material_inbox"
    root.mkdir(parents=True, exist_ok=True)
    return root


def _fingerprint(path):
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _sidecar(path):
    candidates = [
        path.with_name(path.name + ".json"),
        path.with_suffix(path.suffix + ".json"),
        path.with_suffix(".json"),
    ]
    for candidate in candidates:
        if not candidate.is_file():
            continue
        try:
            value = json.loads(candidate.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            continue
        if isinstance(value, dict):
            return value, candidate
    return {}, None


def _media_class(path):
    suffix = path.suffix.lower()
    if suffix in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}:
        return "image"
    if suffix in {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}:
        return "video"
    return "audio"


def _quality_score(media_class, width=None, height=None, duration=None, bytes_size=0):
    score = 45 if bytes_size else 0
    if media_class in {"image", "video"} and width and height:
        short = min(int(width), int(height))
        long = max(int(width), int(height))
        if short >= 1080 and long >= 1920:
            score += 45
        elif short >= 720 and long >= 1280:
            score += 35
        elif short >= 540:
            score += 22
        else:
            score += 8
    elif media_class == "audio":
        score += 25
    if duration is not None and float(duration) > 0:
        score += 10
    return max(0, min(100, int(score)))


def _probe_image(path, bytes_size):
    try:
        from PIL import Image
        with Image.open(path) as image:
            width, height = image.size
            return {
                "probe_status": "ok",
                "width": int(width), "height": int(height),
                "aspect_ratio": round(width / height, 4) if height else None,
                "format": str(image.format or path.suffix.lstrip(".")).lower(),
                "technical_quality_score": _quality_score("image", width, height, None, bytes_size),
            }
    except Exception as error:
        return {
            "probe_status": "unreadable",
            "probe_error": str(error)[:240],
            "technical_quality_score": 10 if bytes_size else 0,
        }


def _probe_av(path, media_class, bytes_size):
    try:
        from promotion.video_worker import find_ffmpeg
        ffmpeg = find_ffmpeg()
    except (ImportError, OSError):
        ffmpeg = None
    if not ffmpeg:
        return {
            "probe_status": "ffmpeg_unavailable",
            "technical_quality_score": _quality_score(media_class, bytes_size=bytes_size),
        }
    try:
        result = subprocess.run(
            [str(ffmpeg), "-hide_banner", "-i", str(path)],
            capture_output=True, timeout=12, check=False,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        text = (result.stderr + result.stdout).decode("utf-8", "replace")
        duration = None
        match = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", text)
        if match:
            duration = int(match.group(1)) * 3600 + int(match.group(2)) * 60 + float(match.group(3))
        width = height = None
        if media_class == "video":
            dimensions = re.search(r"Video:.*?(\d{2,5})x(\d{2,5})", text, re.S)
            if dimensions:
                width, height = int(dimensions.group(1)), int(dimensions.group(2))
        sample_rate = None
        audio = re.search(r"Audio:.*?(\d{4,6})\s*Hz", text, re.S)
        if audio:
            sample_rate = int(audio.group(1))
        return {
            "probe_status": "ok" if (duration is not None or width or sample_rate) else "limited",
            "duration_seconds": round(duration, 3) if duration is not None else None,
            "width": width, "height": height,
            "aspect_ratio": round(width / height, 4) if width and height else None,
            "sample_rate_hz": sample_rate,
            "technical_quality_score": _quality_score(media_class, width, height, duration, bytes_size),
        }
    except (OSError, subprocess.SubprocessError) as error:
        return {
            "probe_status": "probe_failed", "probe_error": str(error)[:240],
            "technical_quality_score": _quality_score(media_class, bytes_size=bytes_size),
        }


def _probe(path, media_class, bytes_size):
    return _probe_image(path, bytes_size) if media_class == "image" else _probe_av(path, media_class, bytes_size)


def scan_material_inbox():
    from promotion import content_factory

    data = content_factory._load()
    campaign_ids = {str(x.get("id")) for x in data.get("campaigns", []) if x.get("id")}
    previous = read_json(INDEX_FILE, {"schema": 1, "items": []})
    previous_items = previous.get("items", []) if isinstance(previous, dict) else []
    previous_by_path = {
        str(item.get("path")): item for item in previous_items
        if isinstance(item, dict) and item.get("path")
    }
    known_assets = {
        str(x.get("source_fingerprint")): x for x in data.get("assets", [])
        if x.get("source_fingerprint")
    }
    items = []
    promoted = 0
    unclassified = 0
    invalid = 0
    hash_reused = 0
    hash_computed = 0
    probe_reused = 0
    probe_computed = 0

    root = inbox_root()
    for campaign_dir in sorted(root.iterdir() if root.exists() else []):
        if not campaign_dir.is_dir():
            continue
        campaign_id = campaign_dir.name
        for path in sorted(campaign_dir.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in SUPPORTED:
                continue
            try:
                stat = path.stat()
                prior = previous_by_path.get(str(path)) or {}
                unchanged = (
                    prior.get("fingerprint")
                    and int(prior.get("bytes") or -1) == int(stat.st_size)
                    and int(prior.get("mtime_ns") or -1) == int(stat.st_mtime_ns)
                )
                if unchanged:
                    fingerprint = str(prior["fingerprint"])
                    hash_reused += 1
                else:
                    fingerprint = _fingerprint(path)
                    hash_computed += 1
            except OSError as error:
                items.append({
                    "campaign_id": campaign_id, "path": str(path), "status": "读取失败",
                    "error": str(error)[:240], "indexed_at": now_iso(),
                })
                invalid += 1
                continue

            meta, sidecar_path = _sidecar(path)
            kind = str(meta.get("kind") or "").strip()
            consent = bool(meta.get("consent_confirmed"))
            license_meta = meta.get("license") if isinstance(meta.get("license"), dict) else {}
            tags = meta.get("tags") if isinstance(meta.get("tags"), list) else []
            media_class = _media_class(path)
            if unchanged and isinstance(prior.get("media_metadata"), dict):
                media_metadata = dict(prior["media_metadata"])
                probe_reused += 1
            else:
                media_metadata = _probe(path, media_class, stat.st_size)
                probe_computed += 1
            media_metadata.update({
                "filename": path.name,
                "extension": path.suffix.lower(),
                "media_class": media_class,
                "bytes": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
            })
            entry = {
                "campaign_id": campaign_id,
                "path": str(path),
                "filename": path.name,
                "extension": path.suffix.lower(),
                "media_class": media_class,
                "bytes": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
                "fingerprint": fingerprint,
                "kind": kind or None,
                "consent_confirmed": consent,
                "tags": [str(x)[:80] for x in tags[:30]],
                "license": license_meta,
                "media_metadata": media_metadata,
                "quality_score": media_metadata.get("technical_quality_score"),
                "sidecar": str(sidecar_path) if sidecar_path else None,
                "indexed_at": now_iso(),
                "status": "已索引",
            }

            if campaign_id not in campaign_ids:
                entry["status"] = "增长ID不存在"
                invalid += 1
                items.append(entry)
                continue
            if not kind:
                entry["status"] = "待分类"
                unclassified += 1
                items.append(entry)
                continue
            if kind not in PUBLISHABLE_KINDS:
                entry["status"] = "素材类型不支持"
                invalid += 1
                items.append(entry)
                continue
            if kind.startswith("真实") and not consent:
                entry["status"] = "真实素材缺少发布同意"
                invalid += 1
                items.append(entry)
                continue

            if fingerprint not in known_assets:
                asset = content_factory.add_asset({
                    "campaign_id": campaign_id,
                    "kind": kind,
                    "local_path": str(path),
                    "consent_confirmed": consent,
                    "note": str(meta.get("note") or "由本地素材投递箱自动扫描并建立索引")[:300],
                    "tags": entry["tags"],
                    "source_origin": "material_inbox",
                    "source_fingerprint": fingerprint,
                    "license": license_meta,
                    "media_metadata": media_metadata,
                    "quality_score": entry["quality_score"],
                })
                known_assets[fingerprint] = asset
                promoted += 1
            entry["status"] = "已进入可选素材池"
            entry["asset_id"] = known_assets[fingerprint].get("id")
            items.append(entry)

    result = {
        "schema": 3,
        "scanned_at": now_iso(),
        "root": str(root),
        "items": items[-1000:],
        "summary": {
            "indexed": len(items),
            "promoted": promoted,
            "unclassified": unclassified,
            "invalid": invalid,
            "hash_reused": hash_reused,
            "hash_computed": hash_computed,
            "probe_reused": probe_reused,
            "probe_computed": probe_computed,
        },
        "previous_scan_at": previous.get("scanned_at") if isinstance(previous, dict) else None,
    }
    write_json(INDEX_FILE, result)
    return result


def status():
    value = read_json(INDEX_FILE, {})
    if not isinstance(value, dict) or not value:
        return {
            "root": str(inbox_root()), "scanned_at": None,
            "summary": {
                "indexed": 0, "promoted": 0, "unclassified": 0, "invalid": 0,
                "hash_reused": 0, "hash_computed": 0, "probe_reused": 0, "probe_computed": 0,
            },
            "items": [],
        }
    value.setdefault("root", str(inbox_root()))
    value.setdefault("summary", {
        "indexed": 0, "promoted": 0, "unclassified": 0, "invalid": 0,
        "hash_reused": 0, "hash_computed": 0, "probe_reused": 0, "probe_computed": 0,
    })
    return value
