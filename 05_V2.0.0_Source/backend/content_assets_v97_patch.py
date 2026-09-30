"""#97 bind reusable person/scene/voice/series assets into real generation.

The #92 asset center already stores durable assets. This patch makes selected
assets affect the actual project and Wan prompt instead of remaining UI-only
metadata. It preserves rights checks and never invents a face reference file.
"""
from __future__ import annotations

from backend import kz_local_control_patch as _video
from backend import server
from backend import series_asset_center_v92_patch as _series
from promotion import ai_production_center as _center

_INSTALLED = False
_ORIGINAL_QUEUE = _center.queue_candidate_generation
_ORIGINAL_POSITIVE = _video._positive_prompt
_ORIGINAL_ASSET_FOR_SHOT = _video._asset_for_shot


def _center_asset(data, identifier):
    return next((x for x in data.get("assets") or [] if x.get("id") == identifier), None)


def _series_item_from_center(asset):
    if not asset:
        return None
    identifier = str(asset.get("series_asset_id") or "")
    if not identifier:
        return None
    return _series._find(_series._load(), identifier)


def _persist_bindings(payload, task):
    shot_id = str(payload.get("shot_id") or "").strip()
    asset_ids = [str(x) for x in (payload.get("asset_ids") or []) if str(x).strip()]
    data = _center._load()
    shot = next((x for x in data.get("storyboards") or [] if x.get("id") == shot_id), None)
    if not shot:
        return task
    project = next((x for x in data.get("projects") or [] if x.get("id") == shot.get("project_id")), None)
    bindings = {"character": "", "scene": "", "voice": "", "series": ""}
    shot["asset_ids"] = list(dict.fromkeys(asset_ids))
    for identifier in asset_ids:
        asset = _center_asset(data, identifier)
        if not asset or asset.get("enabled") is False or asset.get("rights") == "待确认":
            continue
        item = _series_item_from_center(asset)
        asset_type = str(asset.get("asset_type") or "")
        if asset_type == "人物":
            bindings["character"] = identifier
            shot["character_asset_id"] = identifier
            if project:
                project["default_character_id"] = identifier
        elif asset_type == "场景":
            bindings["scene"] = identifier
            shot["scene_asset_id"] = identifier
            if project:
                project["default_scene_id"] = identifier
        elif asset_type == "声音":
            bindings["voice"] = identifier
            shot["voice_asset_id"] = identifier
            if project:
                project["default_voice_id"] = identifier
        if item:
            shot.setdefault("series_asset_ids", {})[str(item.get("type") or asset_type)] = item.get("id")
    shot["asset_bindings"] = bindings
    shot["asset_binding_version"] = "#97"
    if project:
        project["asset_binding_version"] = "#97"
        project["updated_at"] = _center.now_iso()
    _center._audit(data, "production_assets_bound", shot_id, "#97 已将当前选择的人物/场景/声音资产绑定到真实镜头生成合同。")
    _center._save(data)
    return task


def queue_candidate_generation_v97(payload):
    task = _ORIGINAL_QUEUE(payload)
    return _persist_bindings(payload, task)


def _bound_assets(shot):
    data = _center._load()
    identifiers = list(shot.get("asset_ids") or [])
    for key in ("character_asset_id", "scene_asset_id", "voice_asset_id"):
        value = str(shot.get(key) or "")
        if value and value not in identifiers:
            identifiers.append(value)
    project = next((x for x in data.get("projects") or [] if x.get("id") == shot.get("project_id")), None)
    if project:
        for key in ("default_character_id", "default_scene_id", "default_voice_id"):
            value = str(project.get(key) or "")
            if value and value not in identifiers:
                identifiers.append(value)
    return data, [_center_asset(data, x) for x in identifiers if _center_asset(data, x)]


def _asset_prompt_fragments(shot):
    _, assets = _bound_assets(shot)
    parts = []
    for asset in assets:
        item = _series_item_from_center(asset)
        kind = str(asset.get("asset_type") or "")
        name = str(asset.get("name") or "").strip()
        metadata = asset.get("metadata") if isinstance(asset.get("metadata"), dict) else {}
        if kind == "人物":
            appearance = str((item or {}).get("appearance") or metadata.get("appearance") or "").strip()
            outfit = str((item or {}).get("outfit") or metadata.get("outfit") or "").strip()
            rules = str((item or {}).get("identity_rules") or "").strip()
            text = "固定人物" + (f"“{name}”" if name else "")
            if appearance:
                text += f"；外观必须保持：{appearance}"
            if outfit:
                text += f"；服装必须保持：{outfit}"
            if rules:
                text += f"；一致性：{rules}"
            parts.append(text)
        elif kind == "场景":
            rules = str((item or {}).get("scene_rules") or metadata.get("scene_rules") or asset.get("note") or "").strip()
            variables = str((item or {}).get("variables") or "").strip()
            text = "固定/推荐场景" + (f"“{name}”" if name else "")
            if rules:
                text += f"；场景规则：{rules}"
            if variables:
                text += f"；允许变化：{variables}"
            parts.append(text)
    if parts:
        parts.append("同一系列内人物脸型、发型、服装、工具、主体比例与品牌视觉必须稳定；不得无理由换人或换装。")
    return parts


def _positive_prompt_v97(shot):
    base = _ORIGINAL_POSITIVE(shot)
    extras = _asset_prompt_fragments(shot)
    return (base + ("。" if base and extras else "") + "。".join(extras))[:2600]


def _reference_image_candidates(shot):
    data, assets = _bound_assets(shot)
    result = []
    for asset in assets:
        item = _series_item_from_center(asset)
        reference_ids = list((item or {}).get("reference_asset_ids") or [])
        for reference_id in reference_ids:
            ref = _center_asset(data, reference_id)
            if ref and ref not in result:
                result.append(ref)
        # A synced asset can itself point at a real file after future imports.
        if str(asset.get("mime_type") or "").startswith("image/") and asset not in result:
            result.append(asset)
    return result


def _asset_for_shot_v97(shot):
    references = _reference_image_candidates(shot)
    if references:
        data = _center._load()
        for ref in references:
            try:
                if ref.get("enabled") is False or ref.get("rights") == "待确认":
                    continue
                return _video._ensure_comfy_input(ref, data)
            except (OSError, RuntimeError):
                continue
    return _ORIGINAL_ASSET_FOR_SHOT(shot)


def apply_series_template(payload):
    project_id = str(payload.get("project_id") or "").strip()
    series_id = str(payload.get("series_id") or "").strip()
    store = _series._load()
    template = _series._find(store, series_id)
    if not template or template.get("type") != "series":
        raise ValueError("没有找到系列模板")
    data = _center._load()
    project = next((x for x in data.get("projects") or [] if x.get("id") == project_id), None)
    if not project:
        raise ValueError("没有找到生产项目")
    mapping = {
        "default_character_id": template.get("default_character_id"),
        "default_voice_id": template.get("default_voice_id"),
        "default_scene_id": template.get("default_scene_id"),
    }
    # Series template stores series-asset IDs. Translate them to synced center IDs.
    for field, series_asset_id in mapping.items():
        if not series_asset_id:
            continue
        center_asset = next((x for x in data.get("assets") or [] if x.get("series_asset_id") == series_asset_id and x.get("enabled") is not False), None)
        if center_asset:
            project[field] = center_asset.get("id")
    project["series_template_id"] = series_id
    project["subtitle_style"] = template.get("subtitle_style") or ""
    project["ratio"] = template.get("ratio") or project.get("ratio") or "9:16"
    project["target_resolution"] = template.get("resolution") or "1080x1920"
    project["target_fps"] = int(template.get("fps") or 30)
    project["series_continuity_rules"] = template.get("continuity_rules") or ""
    project["series_cta"] = template.get("cta") or ""
    project["updated_at"] = _center.now_iso()
    for shot in data.get("storyboards") or []:
        if shot.get("project_id") != project_id:
            continue
        shot["series_template_id"] = series_id
        locks = list(shot.get("consistency_locks") or [])
        rule = str(template.get("continuity_rules") or "").strip()
        if rule and rule not in locks:
            locks.append(rule[:180])
        shot["consistency_locks"] = locks[:10]
    _center._audit(data, "series_template_applied", project_id, f"#97 已应用系列模板：{template.get('name') or series_id}。")
    _center._save(data)
    return {"ok": True, "project": project, "template": template}


def _read_json(handler, limit=64 * 1024):
    import json
    length = int(handler.headers.get("Content-Length", "0") or 0)
    if length <= 0 or length > limit:
        raise ValueError("请求内容为空或超过限制")
    return json.loads(handler.rfile.read(length) or b"{}")


def _origin_allowed(handler):
    origin = str(handler.headers.get("Origin") or "").strip()
    return not origin or origin in {f"http://127.0.0.1:{handler.server.server_port}", f"http://localhost:{handler.server.server_port}"}


def install():
    global _INSTALLED
    if _INSTALLED:
        return
    old_post = server.DashboardHandler.do_POST

    def do_post(handler):
        from urllib.parse import urlsplit
        path = urlsplit(handler.path).path
        if path != "/api/content-final/series/apply":
            return old_post(handler)
        if not _origin_allowed(handler):
            handler._json_error(403, "仅允许本机应用系列模板")
            return
        try:
            handler._json_ok(apply_series_template(_read_json(handler)))
        except (ValueError, TypeError, OSError) as error:
            handler._json_error(400, error)

    server.DashboardHandler.do_POST = do_post
    _center.queue_candidate_generation = queue_candidate_generation_v97
    _video._positive_prompt = _positive_prompt_v97
    _video._asset_for_shot = _asset_for_shot_v97
    server.DashboardHandler._kz_content_assets_v97 = True
    _INSTALLED = True


install()
