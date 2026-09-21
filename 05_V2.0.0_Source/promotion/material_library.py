"""Structured local material inbox and index for the R8 content factory.

The owner may drop optional files under ``data/r8/material_inbox/<campaign_id>``.
Every file is indexed, but a file is promoted into the usable content library
only when a sidecar explicitly classifies it. Real customer/repair material
also requires explicit consent metadata. Repeated scans reuse fingerprints for
unchanged files so a large inbox does not waste disk/GPU workstation resources.
"""

from __future__ import annotations

import hashlib
import json
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
            entry = {
                "campaign_id": campaign_id,
                "path": str(path),
                "filename": path.name,
                "extension": path.suffix.lower(),
                "media_class": _media_class(path),
                "bytes": stat.st_size,
                "mtime_ns": stat.st_mtime_ns,
                "fingerprint": fingerprint,
                "kind": kind or None,
                "consent_confirmed": consent,
                "tags": [str(x)[:80] for x in tags[:30]],
                "license": license_meta,
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
                    "media_metadata": {
                        "filename": path.name,
                        "extension": path.suffix.lower(),
                        "media_class": entry["media_class"],
                        "bytes": stat.st_size,
                        "mtime_ns": stat.st_mtime_ns,
                    },
                })
                known_assets[fingerprint] = asset
                promoted += 1
            entry["status"] = "已进入可选素材池"
            entry["asset_id"] = known_assets[fingerprint].get("id")
            items.append(entry)

    result = {
        "schema": 2,
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
                "hash_reused": 0, "hash_computed": 0,
            },
            "items": [],
        }
    value.setdefault("root", str(inbox_root()))
    value.setdefault("summary", {
        "indexed": 0, "promoted": 0, "unclassified": 0, "invalid": 0,
        "hash_reused": 0, "hash_computed": 0,
    })
    return value
