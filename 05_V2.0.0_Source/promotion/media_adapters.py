"""Safe media adapter interfaces used by the local R8 execution layer.

No adapter scrapes arbitrary websites or invokes a second planning model.  The
licensed-media adapter consumes only locally mounted files with explicit
commercial-use metadata.  The AI-shot adapter consumes output produced by an
approved local visual generator.  When either adapter is unavailable the video
worker remains non-blocking and falls back to information cards.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

from core.storage import data_root, now_iso, write_json


MEDIA_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}


def _root(kind):
    path = data_root() / "r8" / "media_adapters" / kind
    path.mkdir(parents=True, exist_ok=True)
    return path


def _read_json(path):
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError, TypeError):
        return {}
    return value if isinstance(value, dict) else {}


def _safe_campaign(campaign_id):
    return re.sub(r"[^0-9A-Za-z-]", "", str(campaign_id or ""))[:64]


def _safe_shot(shot_id):
    return re.sub(r"[^0-9A-Za-z_.-]", "", str(shot_id or ""))[:64]


def _licensed_assets(campaign_id):
    directory = _root("licensed") / _safe_campaign(campaign_id)
    directory.mkdir(parents=True, exist_ok=True)
    items = []
    for manifest in sorted(directory.glob("*.json")):
        meta = _read_json(manifest)
        filename = str(meta.get("file") or "").strip()
        path = (directory / filename).resolve() if filename else None
        try:
            inside = path is not None and directory.resolve() in path.parents
        except OSError:
            inside = False
        license_meta = meta.get("license") if isinstance(meta.get("license"), dict) else {}
        commercial = bool(license_meta.get("commercial_use"))
        source_url = str(license_meta.get("source_url") or "").strip()
        license_name = str(license_meta.get("name") or "").strip()
        if not path or not inside or not path.is_file() or path.suffix.lower() not in MEDIA_SUFFIXES:
            continue
        if not commercial or not source_url or not license_name:
            continue
        items.append({
            "id": "LICENSED-" + manifest.stem[:48],
            "kind": "许可公开素材",
            "local_path": str(path),
            "source_origin": "licensed_external",
            "license": license_meta,
            "query": str(meta.get("query") or ""),
            "tags": meta.get("tags") if isinstance(meta.get("tags"), list) else [],
        })
    return items


def _generated_assets(campaign_id):
    directory = _root("ai_generated") / _safe_campaign(campaign_id)
    directory.mkdir(parents=True, exist_ok=True)
    items = []
    for path in sorted(directory.iterdir() if directory.exists() else []):
        if not path.is_file() or path.suffix.lower() not in MEDIA_SUFFIXES:
            continue
        meta = _read_json(path.with_name(path.name + ".json"))
        shot_id = str(meta.get("shot_id") or path.stem.split("__", 1)[0] or "").strip()
        items.append({
            "id": "AIGEN-" + path.stem[:48],
            "kind": "AI辅助镜头",
            "local_path": str(path),
            "source_origin": "ai_generated_adapter",
            "shot_id": shot_id,
            "synthetic_disclosure": str(meta.get("synthetic_disclosure") or "AI辅助示意"),
            "generator": str(meta.get("generator") or "approved-local-visual-adapter"),
        })
    return items


def list_assets(campaign_id):
    return {
        "licensed": _licensed_assets(campaign_id),
        "generated": _generated_assets(campaign_id),
    }


def request_asset(video_id, campaign_id, shot, source_type):
    """Write an idempotent adapter request for an external execution component."""
    if source_type not in {"licensed_external", "ai_generated"}:
        return None
    shot_id = _safe_shot((shot or {}).get("shot_id") or "shot")
    directory = _root("requests") / _safe_campaign(campaign_id) / _safe_shot(video_id)
    directory.mkdir(parents=True, exist_ok=True)
    path = directory / f"{shot_id}_{source_type}.json"
    payload = {
        "schema": "kazuizhi-media-adapter-request/v1",
        "requested_at": now_iso(),
        "video_id": str(video_id or ""),
        "campaign_id": str(campaign_id or ""),
        "shot_id": str((shot or {}).get("shot_id") or ""),
        "source_type": source_type,
        "material_query": str((shot or {}).get("material_query") or (shot or {}).get("purpose") or ""),
        "required_real": bool((shot or {}).get("required_real")),
        "synthetic_disclosure": str((shot or {}).get("synthetic_disclosure") or "AI辅助示意"),
        "rule": (
            "licensed_external必须有明确商业使用授权元数据；ai_generated不得用于required_real镜头，"
            "并必须保留AI辅助标识。"
        ),
    }
    write_json(str(path.relative_to(data_root())).replace("\\", "/"), payload)
    return str(path)


def status(campaign_id=None):
    result = {
        "schema": "kazuizhi-media-adapters/v1",
        "licensed_external": {
            "root": str(_root("licensed")),
            "mode": "verified_local_manifest",
            "ready": True,
            "note": "只读取带商业使用授权元数据的本地挂载公开素材，不自动抓取未知网站。",
        },
        "ai_generated": {
            "root": str(_root("ai_generated")),
            "mode": "approved_generator_output_inbox",
            "ready": True,
            "note": "读取已批准视觉生成器的输出；ChatGPT仍是唯一内容与分镜决策层。",
        },
        "requests_root": str(_root("requests")),
    }
    if campaign_id:
        assets = list_assets(campaign_id)
        result["licensed_external"]["available"] = len(assets["licensed"])
        result["ai_generated"]["available"] = len(assets["generated"])
    return result
