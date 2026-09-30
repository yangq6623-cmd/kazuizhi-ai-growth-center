"""#98 authorized local voice-clone / dialect TTS routing.

The reusable voice registry from #92 is the source of truth. A selected
self/authorized clone can be rendered through a loopback GPT-SoVITS compatible
service (default http://127.0.0.1:17779). The runtime never sends reference
recordings to a public host and never silently labels Windows SAPI as a clone.

If no clone voice is selected, the existing SAPI path remains the safe fallback.
If a clone voice is selected but the local engine is unavailable, generation
fails truthfully instead of impersonating the requested voice with another one.
"""
from __future__ import annotations

import json
import os
import shutil
import socket
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from backend import final_render_patch as _final
from backend import server
from backend import series_asset_center_v92_patch as _series
from promotion import ai_production_center as _center
from promotion import speech_pipeline

_INSTALLED = False
_ORIGINAL_SAPI = speech_pipeline._sapi_tts
_DEFAULT_BASE = "http://127.0.0.1:17779"


def _base_url():
    value = str(os.environ.get("KAZUIZHI_TTS_BASE_URL") or _DEFAULT_BASE).strip().rstrip("/")
    parsed = urlsplit(value)
    if parsed.scheme != "http" or parsed.hostname not in {"127.0.0.1", "localhost", "::1"}:
        raise RuntimeError("声音克隆引擎只允许连接本机 loopback HTTP 服务")
    return value


def _probe(path, timeout=1.5):
    try:
        with urlopen(Request(_base_url() + path, headers={"Accept": "application/json"}), timeout=timeout) as response:
            return response.status < 500
    except (HTTPError, URLError, TimeoutError, OSError, RuntimeError):
        return False


def engine_status():
    try:
        base = _base_url()
    except RuntimeError as error:
        return {"available": False, "engine": "invalid_config", "message": str(error)}
    available = any(_probe(path) for path in ("/health", "/api/health", "/docs", "/"))
    return {
        "available": bool(available),
        "engine": "GPT-SoVITS-compatible local reference voice" if available else "not_detected",
        "base_url": base,
        "loopback_only": True,
        "message": (
            "本地声音服务可访问；本人/已授权参考录音可进入真实参考声纹TTS。" if available else
            "未检测到 127.0.0.1:17779 本地声音服务；声音资产仍安全保留，但不会伪报克隆可用。"
        ),
    }


def _voice_for_project(project_id):
    data = _center._load()
    project = next((x for x in data.get("projects") or [] if x.get("id") == project_id), None)
    if not project:
        return None, None
    center_id = str(project.get("default_voice_id") or "")
    asset = next((x for x in data.get("assets") or [] if x.get("id") == center_id), None)
    if not asset:
        return project, None
    series_id = str(asset.get("series_asset_id") or "")
    item = _series._find(_series._load(), series_id) if series_id else None
    return project, item


def _current_project_id():
    project_id = str((_final._FINAL_STATE or {}).get("project_id") or "")
    if project_id:
        return project_id
    data = _center._load()
    return str(((data.get("projects") or [{}])[0]).get("id") or "")


def _language_code(item):
    language = str((item or {}).get("language") or "普通话").lower()
    # GPT-SoVITS accepts zh/all_zh in common APIs. Dialect identity is primarily
    # carried by the authorized reference voice; we do not claim translation.
    if "英" in language or "english" in language:
        return "en"
    if "日" in language or "japanese" in language:
        return "ja"
    return "zh"


def _write_audio_response(response, output):
    content_type = str(response.headers.get("Content-Type") or "").lower()
    raw = response.read(64 * 1024 * 1024)
    if len(raw) < 1024:
        raise RuntimeError("本地声音引擎没有返回有效音频")
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    # Most local engines return WAV for media_type=wav. If a gateway returns
    # another audio format we keep the exact bytes but report it truthfully.
    output.write_bytes(raw)
    return content_type, len(raw)


def _gpt_sovits_tts(text, output, item):
    audio = Path(str(item.get("audio_file") or ""))
    if not audio.is_file():
        return {"status": "failed", "path": None, "message": "选择的克隆声音没有真实参考录音"}
    source_kind = str(item.get("source_kind") or "")
    rights = str(item.get("rights") or "")
    if source_kind not in {"self_clone", "authorized_clone"}:
        return {"status": "failed", "path": None, "message": "该声音不是本人/明确授权的克隆声音类型"}
    if source_kind == "self_clone" and rights != "本人或公司自有":
        return {"status": "failed", "path": None, "message": "本人克隆声音授权状态未确认"}
    if source_kind == "authorized_clone" and rights != "已取得授权":
        return {"status": "failed", "path": None, "message": "第三方声音必须先登记明确授权"}
    status = engine_status()
    if not status.get("available"):
        return {"status": "failed", "path": None, "message": status.get("message")}
    lang = _language_code(item)
    body = {
        "text": str(text or ""),
        "text_lang": lang,
        "ref_audio_path": str(audio.resolve()),
        "prompt_lang": lang,
        "prompt_text": str(item.get("reference_text") or item.get("prompt_text") or ""),
        "text_split_method": "cut5",
        "batch_size": 1,
        "media_type": "wav",
        "streaming_mode": False,
    }
    request = Request(
        _base_url() + "/tts",
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "audio/wav,application/octet-stream,application/json"},
        method="POST",
    )
    try:
        with urlopen(request, timeout=300) as response:
            content_type, size = _write_audio_response(response, output)
        if "json" in content_type:
            Path(output).unlink(missing_ok=True)
            return {"status": "failed", "path": None, "message": "本地声音服务返回了JSON而不是音频，请检查GPT-SoVITS API配置"}
        return {
            "status": "ready", "path": str(Path(output)),
            "message": "本地授权参考声纹TTS已生成",
            "engine": "GPT-SoVITS-compatible", "voice_id": item.get("id"),
            "dialect": item.get("dialect") or "", "bytes": size,
        }
    except HTTPError as error:
        try:
            detail = error.read().decode("utf-8", "replace")[:700]
        except OSError:
            detail = ""
        return {"status": "failed", "path": None, "message": f"本地声音服务 HTTP {error.code}: {detail or '请求失败'}"}
    except (URLError, TimeoutError, OSError, RuntimeError) as error:
        return {"status": "failed", "path": None, "message": f"本地声音克隆执行失败：{str(error)[:500]}"}


def _mark_voice_verified(item_id):
    data = _series._load()
    item = _series._find(data, item_id)
    if not item:
        return
    item["clone_status"] = "参考声纹已验证可用"
    item["engine"] = "本地 GPT-SoVITS-compatible"
    item["updated_at"] = _center.now_iso()
    _series._save(data)
    _series._sync_center_asset(item)


def _routed_tts(text, output):
    project_id = _current_project_id()
    _, item = _voice_for_project(project_id)
    if not item:
        return _ORIGINAL_SAPI(text, output)
    source = str(item.get("source_kind") or "")
    if source in {"self_clone", "authorized_clone"}:
        result = _gpt_sovits_tts(text, output, item)
        if result.get("status") == "ready":
            _mark_voice_verified(item.get("id"))
        return result
    # Public licensed / AI-original voices are metadata until a concrete local
    # synthesis engine/voice ID is configured. Do not call them clones.
    if source in {"public_licensed", "ai_original"}:
        return {
            "status": "failed", "path": None,
            "message": "该声音资产尚未绑定真实本地音色ID。请绑定支持的本地TTS后再使用；系统不会用默认SAPI冒充指定声音。",
        }
    return _ORIGINAL_SAPI(text, output)


def preview(payload):
    voice_id = str(payload.get("voice_id") or "").strip()
    text = str(payload.get("text") or "这是一段卡嘴子声音试听。").strip()[:300]
    if not voice_id:
        raise ValueError("请选择声音资产")
    data = _series._load()
    item = _series._find(data, voice_id)
    if not item or item.get("type") != "voice":
        raise ValueError("没有找到声音资产")
    folder = Path(str(item.get("audio_file") or "")).parent if item.get("audio_file") else Path(os.environ.get("TEMP") or ".")
    folder.mkdir(parents=True, exist_ok=True)
    output = folder / f"{voice_id}_preview.wav"
    result = _gpt_sovits_tts(text, output, item)
    if result.get("status") == "ready":
        _mark_voice_verified(voice_id)
        result["preview_url"] = f"/api/content-final/voice/preview-audio?id={voice_id}"
    return result


def _serve_preview(handler, voice_id):
    item = _series._find(_series._load(), voice_id)
    if not item:
        handler._json_error(404, "没有找到声音资产")
        return
    audio_file = Path(str(item.get("audio_file") or ""))
    path = audio_file.parent / f"{voice_id}_preview.wav" if audio_file.parent else Path()
    if not path.is_file():
        handler._json_error(404, "尚未生成试听音频")
        return
    raw = path.read_bytes()
    handler.send_response(200)
    handler.send_header("Content-Type", "audio/wav")
    handler.send_header("Content-Length", str(len(raw)))
    handler.send_header("Cache-Control", "no-store")
    handler.end_headers()
    handler.wfile.write(raw)


def _read_json(handler, limit=64 * 1024):
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
    old_get = server.DashboardHandler.do_GET
    old_post = server.DashboardHandler.do_POST

    def do_get(handler):
        parsed = urlsplit(handler.path)
        if parsed.path == "/api/content-final/voice/status":
            voices = [x for x in (_series._load().get("items") or []) if x.get("type") == "voice"]
            handler._json_ok({"engine": engine_status(), "voices": voices})
            return
        if parsed.path == "/api/content-final/voice/preview-audio":
            from urllib.parse import parse_qs
            voice_id = (parse_qs(parsed.query).get("id") or [""])[0]
            _serve_preview(handler, voice_id)
            return
        return old_get(handler)

    def do_post(handler):
        if urlsplit(handler.path).path != "/api/content-final/voice/preview":
            return old_post(handler)
        if not _origin_allowed(handler):
            handler._json_error(403, "仅允许本机试听声音资产")
            return
        try:
            result = preview(_read_json(handler))
            code = 200 if result.get("status") == "ready" else 409
            handler._json_ok(result, code=code)
        except (ValueError, TypeError, OSError, json.JSONDecodeError) as error:
            handler._json_error(400, error)

    server.DashboardHandler.do_GET = do_get
    server.DashboardHandler.do_POST = do_post
    speech_pipeline._sapi_tts = _routed_tts
    server.DashboardHandler._kz_voice_clone_v98 = True
    _INSTALLED = True


install()
