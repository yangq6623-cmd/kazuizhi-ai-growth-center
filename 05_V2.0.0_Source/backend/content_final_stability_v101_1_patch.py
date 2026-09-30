"""#101.1 media isolation for final content-center acceptance.

A new pure-text project must never silently reuse an unrelated historical image
just because an older upload is still registered globally. Current-project media
means one of: explicitly bound to the current shot, generated for this project,
or a recent local image uploaded close to project creation. Otherwise #96 must
create a fresh keyframe (or truthfully report that the T2I checkpoint is missing).
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from backend import content_reference_v96_patch as _v96
from backend import kz_local_control_patch as _video
from promotion import ai_production_center as _center

_WINDOW_SECONDS = 30 * 60
_ORIGINAL_ENSURE = _v96.ensure_project_keyframes


def _dt(value):
    try:
        parsed = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        return parsed
    except (TypeError, ValueError):
        return None


def _is_real_image(asset):
    if not isinstance(asset, dict) or asset.get("enabled") is False or asset.get("rights") == "待确认":
        return False
    if not str(asset.get("mime_type") or "").startswith("image/"):
        return False
    return Path(str(asset.get("file_path") or "")).is_file()


def _bind_first_shot(asset, shots):
    if not asset or not shots:
        return
    data = _center._load()
    first_id = str(shots[0].get("id") or "")
    for shot in data.get("storyboards") or []:
        if str(shot.get("id") or "") != first_id:
            continue
        ids = [str(x) for x in (shot.get("asset_ids") or []) if str(x)]
        aid = str(asset.get("id") or "")
        if aid and aid not in ids:
            ids.insert(0, aid)
        shot["asset_ids"] = ids[:12]
        shot["current_reference_asset_id"] = aid
        shot["media_isolation_version"] = "#101.1"
        break
    _center._save(data)


def _current_images(project, shots):
    data = _center._load()
    images = [x for x in data.get("assets") or [] if _is_real_image(x)]
    if not images:
        return []
    explicit = set()
    for shot in shots or []:
        explicit.update(str(x) for x in (shot.get("asset_ids") or []) if str(x))
        for key in ("auto_keyframe_asset_id", "current_reference_asset_id"):
            value = str(shot.get(key) or "")
            if value:
                explicit.add(value)
    project_id = str(project.get("id") or "")
    direct = [x for x in images if str(x.get("id") or "") in explicit or str(x.get("project_id") or "") == project_id]
    if direct:
        return direct

    created = _dt(project.get("created_at"))
    if created is None:
        return []
    recent = []
    for asset in images:
        stamp = _dt(asset.get("created_at"))
        if stamp is None:
            continue
        try:
            delta = (created - stamp).total_seconds()
        except TypeError:
            continue
        # A local reference is normally uploaded before pressing Start. Accept a
        # small clock skew after project creation, but reject stale media.
        if -120 <= delta <= _WINDOW_SECONDS:
            recent.append(asset)
    recent.sort(key=lambda x: str(x.get("created_at") or ""), reverse=True)
    return recent


def ensure_project_keyframes_v101_1(project, shots):
    current = _current_images(project, shots)
    if current:
        _bind_first_shot(current[0], shots)
        return {"generated": 0, "existing": len(current), "policy": "current_project_media_only"}
    generated = 0
    if shots:
        asset = _v96.generate_keyframe(project, shots[0])
        _bind_first_shot(asset, shots)
        generated = 1
    return {"generated": generated, "existing": 0, "policy": "fresh_auto_keyframe"}


_v96.ensure_project_keyframes = ensure_project_keyframes_v101_1
