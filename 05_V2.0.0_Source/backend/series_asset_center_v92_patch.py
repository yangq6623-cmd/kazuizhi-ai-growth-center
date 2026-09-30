"""#92 reusable person / voice / scene / series asset center.

This layer turns the simple-mode "人物 / 场景 / 声音" selectors into durable,
owner-managed reusable assets without claiming a voice clone exists before a
real clone engine has produced it.

Voice governance is explicit:
- self_clone: owner/company voice recorded for cloning;
- authorized_clone: a third party who explicitly authorized cloning/use;
- public_licensed: a library voice whose license/source is recorded;
- ai_original: a synthetic brand voice that does not impersonate a real person.

Publicly audible speech is not treated as permission to clone. A public-library
voice must carry license/source information before it can be enabled.
"""
from __future__ import annotations

import base64
import json
import mimetypes
import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from uuid import uuid4

from backend import server
from core.storage import data_root, now_iso, read_json, write_json
from promotion import ai_production_center as _center

_FILE = "r8/series_asset_center_v92.json"
_AUDIO_DIR = "r8/voice_assets"
_TYPES = ("character", "voice", "scene", "series")
_RIGHTS = ("本人或公司自有", "已取得授权", "公开许可", "虚拟资产", "待确认")
_VOICE_SOURCES = ("self_clone", "authorized_clone", "public_licensed", "ai_original")
_AUDIO_EXTS = {".wav", ".mp3", ".m4a", ".aac", ".ogg", ".flac"}
_MAX_AUDIO = 30 * 1024 * 1024
_INSTALLED = False


def _default():
    return {
        "schema": "kazuizhi-series-assets/v92",
        "items": [],
        "updated_at": "",
    }


def _load():
    data = read_json(_FILE, _default())
    if not isinstance(data, dict):
        data = _default()
    data.setdefault("items", [])
    return data


def _save(data):
    data["updated_at"] = now_iso()
    write_json(_FILE, data)
    return data


def _id(kind):
    prefix = {"character": "CHAR", "voice": "VOICE", "scene": "SCENE", "series": "SERIES"}.get(kind, "ASSET")
    return f"{prefix}-{uuid4().hex[:10].upper()}"


def _text(value, limit=1000):
    return str(value or "").strip()[:limit]


def _list(value, limit=12):
    if not isinstance(value, list):
        return []
    result = []
    for item in value[:limit]:
        text = _text(item, 180)
        if text and text not in result:
            result.append(text)
    return result


def _find(data, identifier):
    for item in data.get("items") or []:
        if str(item.get("id") or "") == str(identifier or ""):
            return item
    return None


def _sync_center_asset(item):
    kind = item.get("type")
    asset_type = {"character": "人物", "voice": "声音", "scene": "场景"}.get(kind)
    if not asset_type:
        return
    center = _center._load()
    existing = next((x for x in center.get("assets") or [] if x.get("series_asset_id") == item.get("id")), None)
    rights = item.get("rights") or "待确认"
    center_rights = "已取得授权" if rights == "公开许可" else rights
    if center_rights not in _center.RIGHTS:
        center_rights = "待确认"
    enabled = bool(item.get("enabled", True)) and center_rights != "待确认"
    if kind == "voice" and item.get("source_kind") == "public_licensed":
        enabled = enabled and bool(item.get("license_note") and item.get("source_name"))
    payload = {
        "asset_type": asset_type,
        "name": item.get("name") or item.get("id"),
        "rights": center_rights,
        "tags": "、".join(item.get("tags") or []),
        "note": item.get("description") or item.get("style") or "",
        "enabled": enabled,
        "series_asset_id": item.get("id"),
        "series_asset_type": kind,
        "metadata": {
            "source_kind": item.get("source_kind"),
            "language": item.get("language"),
            "dialect": item.get("dialect"),
            "style": item.get("style"),
            "engine": item.get("engine"),
            "clone_status": item.get("clone_status"),
            "audio_file": item.get("audio_file"),
            "source_name": item.get("source_name"),
            "license_note": item.get("license_note"),
            "appearance": item.get("appearance"),
            "outfit": item.get("outfit"),
            "scene_rules": item.get("scene_rules"),
        },
    }
    if existing:
        existing.update(payload)
    else:
        payload.update({"id": _center._id("ASSET"), "created_at": now_iso()})
        center["assets"].insert(0, payload)
    _center._audit(center, "series_asset_synced", item.get("id"), f"#92 已同步{asset_type}资产：{payload['name']}。")
    _center._save(center)


def _validate_voice(item):
    source = item.get("source_kind") or "self_clone"
    if source not in _VOICE_SOURCES:
        raise ValueError("声音来源类型不正确")
    rights = item.get("rights") or "待确认"
    if source == "self_clone" and rights not in {"本人或公司自有", "待确认"}:
        raise ValueError("本人声音克隆应使用“本人或公司自有”授权")
    if source == "authorized_clone" and rights not in {"已取得授权", "待确认"}:
        raise ValueError("授权克隆声音应登记为“已取得授权”")
    if source == "public_licensed":
        if rights not in {"公开许可", "已取得授权", "待确认"}:
            raise ValueError("公共声音必须记录公开许可或明确授权")
        if rights != "待确认" and not (item.get("source_name") and item.get("license_note")):
            raise ValueError("公共声音启用前必须填写来源名称和许可证/使用许可说明")
    if source == "ai_original" and rights not in {"虚拟资产", "待确认"}:
        raise ValueError("AI原创声音应登记为“虚拟资产”")


def save_item(payload):
    data = _load()
    kind = _text(payload.get("type"), 20)
    if kind not in _TYPES:
        raise ValueError("资产类型不正确")
    name = _text(payload.get("name"), 100)
    if not name:
        raise ValueError("名称不能为空")
    rights = _text(payload.get("rights") or ("虚拟资产" if kind == "series" else "待确认"), 30)
    if kind != "series" and rights not in _RIGHTS:
        raise ValueError("授权状态不正确")

    identifier = _text(payload.get("id"), 64)
    item = _find(data, identifier) if identifier else None
    if item is None:
        item = {"id": _id(kind), "created_at": now_iso(), "type": kind}
        data["items"].insert(0, item)
    elif item.get("type") != kind:
        raise ValueError("不能直接修改资产类型")

    common = {
        "name": name,
        "description": _text(payload.get("description"), 1200),
        "rights": rights,
        "tags": _list(payload.get("tags")),
        "enabled": bool(payload.get("enabled", True)),
        "updated_at": now_iso(),
    }
    item.update(common)

    if kind == "character":
        item.update({
            "appearance": _text(payload.get("appearance"), 1200),
            "outfit": _text(payload.get("outfit"), 800),
            "identity_rules": _text(payload.get("identity_rules"), 1000),
            "reference_asset_ids": _list(payload.get("reference_asset_ids")),
        })
    elif kind == "scene":
        item.update({
            "scene_rules": _text(payload.get("scene_rules"), 1200),
            "variables": _text(payload.get("variables"), 1200),
            "reference_asset_ids": _list(payload.get("reference_asset_ids")),
        })
    elif kind == "voice":
        item.update({
            "source_kind": _text(payload.get("source_kind") or item.get("source_kind") or "self_clone", 40),
            "language": _text(payload.get("language") or item.get("language") or "普通话", 60),
            "dialect": _text(payload.get("dialect") or item.get("dialect"), 80),
            "style": _text(payload.get("style") or item.get("style"), 500),
            "engine": _text(payload.get("engine") or item.get("engine") or "本地克隆引擎（待接入）", 100),
            "source_name": _text(payload.get("source_name") or item.get("source_name"), 160),
            "license_note": _text(payload.get("license_note") or item.get("license_note"), 600),
            "clone_status": _text(payload.get("clone_status") or item.get("clone_status") or ("AI原创待配置" if payload.get("source_kind") == "ai_original" else "待录音/待克隆"), 80),
            "audio_file": item.get("audio_file") or "",
            "audio_original_name": item.get("audio_original_name") or "",
        })
        _validate_voice(item)
    else:
        item.update({
            "default_character_id": _text(payload.get("default_character_id"), 80),
            "default_voice_id": _text(payload.get("default_voice_id"), 80),
            "default_scene_id": _text(payload.get("default_scene_id"), 80),
            "subtitle_style": _text(payload.get("subtitle_style") or "简洁白字描边", 200),
            "ratio": _text(payload.get("ratio") or "9:16", 20),
            "resolution": _text(payload.get("resolution") or "1080x1920", 30),
            "fps": int(payload.get("fps") or 30),
            "default_duration": _text(payload.get("default_duration") or "30 秒", 30),
            "cta": _text(payload.get("cta"), 500),
            "continuity_rules": _text(payload.get("continuity_rules") or "固定人物与声音；场景按内容可替换；同一条视频人物服装和声纹保持一致。", 1200),
        })
    _save(data)
    _sync_center_asset(item)
    return item


def delete_item(payload):
    data = _load()
    identifier = _text(payload.get("id"), 64)
    item = _find(data, identifier)
    if not item:
        raise ValueError("未找到资产")
    data["items"] = [x for x in data["items"] if x.get("id") != identifier]
    _save(data)
    if item.get("type") in {"character", "voice", "scene"}:
        center = _center._load()
        for asset in center.get("assets") or []:
            if asset.get("series_asset_id") == identifier:
                asset["enabled"] = False
                asset["note"] = (asset.get("note") or "") + "；#92 资产中心已停用"
        _center._save(center)
    return {"ok": True, "id": identifier}


def upload_audio(payload):
    data = _load()
    identifier = _text(payload.get("id"), 64)
    item = _find(data, identifier)
    if not item or item.get("type") != "voice":
        raise ValueError("请先保存一个声音资产")
    filename = Path(_text(payload.get("name"), 180)).name
    ext = Path(filename).suffix.lower()
    if ext not in _AUDIO_EXTS:
        raise ValueError("录音仅支持 WAV / MP3 / M4A / AAC / OGG / FLAC")
    encoded = str(payload.get("base64") or "")
    if "," in encoded:
        encoded = encoded.split(",", 1)[1]
    try:
        raw = base64.b64decode(encoded, validate=True)
    except Exception as error:
        raise ValueError("录音文件内容无效") from error
    if not raw or len(raw) > _MAX_AUDIO:
        raise ValueError("录音文件不能为空且不能超过30MB")
    folder = data_root() / _AUDIO_DIR
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{identifier}{ext}"
    path.write_bytes(raw)
    item["audio_file"] = str(path)
    item["audio_original_name"] = filename
    item["audio_size_bytes"] = len(raw)
    item["clone_status"] = "录音已保存 · 等待声纹克隆"
    item["updated_at"] = now_iso()
    _save(data)
    _sync_center_asset(item)
    return {"ok": True, "item": item, "audio_url": f"/api/series-asset-center/audio?id={identifier}"}


def status():
    data = _load()
    items = list(data.get("items") or [])
    counts = {kind: sum(1 for x in items if x.get("type") == kind) for kind in _TYPES}
    return {
        **data,
        "counts": counts,
        "voice_source_types": {
            "self_clone": "本人/公司自有声音克隆",
            "authorized_clone": "已授权真人声音克隆",
            "public_licensed": "公共授权声音库",
            "ai_original": "AI原创品牌声音",
        },
        "rights_options": list(_RIGHTS),
        "voice_engine_status": "资产与录音管理已接通；真正声纹克隆/TTS模型执行将在下一阶段接入，未完成前不会标记为‘克隆可用’。",
    }


def _origin_allowed(handler):
    origin = str(handler.headers.get("Origin") or "").strip()
    return not origin or origin in {
        f"http://127.0.0.1:{handler.server.server_port}",
        f"http://localhost:{handler.server.server_port}",
    }


def _body(handler, limit=45 * 1024 * 1024):
    length = int(handler.headers.get("Content-Length", "0") or 0)
    if length <= 0 or length > limit:
        raise ValueError("请求内容为空或超过限制")
    return json.loads(handler.rfile.read(length) or b"{}")


def _serve_audio(handler, identifier):
    item = _find(_load(), identifier)
    if not item or item.get("type") != "voice" or not item.get("audio_file"):
        handler._json_error(404, "没有找到参考录音")
        return
    path = Path(str(item.get("audio_file") or ""))
    if not path.is_file():
        handler._json_error(404, "参考录音文件不存在")
        return
    payload = path.read_bytes()
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    handler.send_response(200)
    handler.send_header("Content-Type", mime)
    handler.send_header("Content-Length", str(len(payload)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(payload)


def install():
    global _INSTALLED
    if _INSTALLED:
        return
    old_get = server.DashboardHandler.do_GET
    old_post = server.DashboardHandler.do_POST

    def do_get(handler):
        parsed = urlsplit(handler.path)
        if parsed.path == "/api/series-asset-center":
            handler._json_ok(status())
            return
        if parsed.path == "/api/series-asset-center/audio":
            identifier = (parse_qs(parsed.query).get("id") or [""])[0]
            _serve_audio(handler, identifier)
            return
        return old_get(handler)

    def do_post(handler):
        path = urlsplit(handler.path).path
        actions = {
            "/api/series-asset-center/save": save_item,
            "/api/series-asset-center/delete": delete_item,
            "/api/series-asset-center/audio-upload": upload_audio,
        }
        action = actions.get(path)
        if not action:
            return old_post(handler)
        if not _origin_allowed(handler):
            handler._json_error(403, "仅允许本机工作台修改系列资产")
            return
        try:
            handler._json_ok(action(_body(handler)))
        except (ValueError, TypeError, OSError, json.JSONDecodeError) as error:
            handler._json_error(400, error)

    server.DashboardHandler.do_GET = do_get
    server.DashboardHandler.do_POST = do_post
    server.DashboardHandler._kz_series_asset_center_v92 = True
    _INSTALLED = True


install()
