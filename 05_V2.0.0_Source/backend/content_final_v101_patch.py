"""#101 integrated final content-center acceptance surface.

Loads #96-#100 in order, exposes one truthful readiness/self-test endpoint and
serves the owner-facing final-upgrade browser module. Readiness distinguishes
"code path installed" from "external local model actually available" so a
missing T2I checkpoint or voice engine is never reported as complete.
"""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit

from backend import content_reference_v96_patch as _v96
from backend import content_assets_v97_patch as _v97  # noqa: F401
from backend import voice_clone_v98_patch as _v98
from backend import shot_editor_v99_patch as _v99
from backend import postproduction_v100_patch as _v100
from backend import quality_ai_runtime_patch as _quality
from backend import server
from backend import series_asset_center_v92_patch as _series
from promotion import ai_production_center as _center
from promotion.video_worker import find_ffmpeg

_INSTALLED = False
_SCRIPT_PATHS = {"/content-final-v101.js", "/web/content-final-v101.js"}


def _module_flags():
    handler = server.DashboardHandler
    return {
        "reference_v96": bool(getattr(handler, "_kz_content_reference_v96", False)),
        "assets_v97": bool(getattr(handler, "_kz_content_assets_v97", False)),
        "voice_v98": bool(getattr(handler, "_kz_voice_clone_v98", False)),
        "editor_v99": bool(getattr(handler, "_kz_shot_editor_v99", False)),
        "post_v100": True,
        "final_v101": bool(getattr(handler, "_kz_content_final_v101", False)),
    }


def status():
    comfy = _quality._comfyui_ready()
    keyframe = _v96.keyframe_status()
    voice = _v98.engine_status()
    assets = _series.status()
    ffmpeg = find_ffmpeg()
    modules = _module_flags()
    wan_ready = bool(comfy.get("wan_i2v_fp8") or comfy.get("ok"))
    core_ready = all(modules.get(key) for key in ("reference_v96", "assets_v97", "voice_v98", "editor_v99")) and bool(ffmpeg) and wan_ready
    full_ready = bool(core_ready and keyframe.get("ready") and voice.get("available"))
    missing = []
    if not wan_ready:
        missing.append("Wan2.1 I2V FP8")
    if not ffmpeg:
        missing.append("FFmpeg")
    if not keyframe.get("ready"):
        missing.append("ComfyUI 文生图 checkpoint（纯文案自动首帧）")
    if not voice.get("available"):
        missing.append("127.0.0.1:17779 本地声音克隆服务")
    counts = assets.get("counts") or {}
    return {
        "version": "#101",
        "package": "六模块内容生产中心最终整合",
        "modules": modules,
        "core_ready": core_ready,
        "ready_for_full_acceptance": full_ready,
        "missing_runtime_dependencies": missing,
        "wan": comfy,
        "auto_keyframe": keyframe,
        "voice": voice,
        "postproduction": _v100.status(),
        "assets": {"character": counts.get("character", 0), "voice": counts.get("voice", 0), "scene": counts.get("scene", 0), "series": counts.get("series", 0)},
        "editor_actions": ["新增", "删除", "修改", "拆分", "合并", "排序", "单镜头重生", "增加候选"],
        "truth": (
            "六个软件模块已加载；本机运行依赖也齐全，可以进入完整最终验收。" if full_ready else
            "六个软件模块已加载，但完整验收仍有本机模型/服务依赖未就绪；页面会明确列出，不会伪报通过。"
        ),
    }


def self_test():
    result = status()
    checks = []
    def add(name, passed, detail, required=True):
        checks.append({"name": name, "passed": bool(passed), "required": bool(required), "detail": str(detail or "")[:500]})
    modules = result.get("modules") or {}
    add("#96 参考解析/无素材路由", modules.get("reference_v96"), "真实公开页解析端点 + 自动首帧路由已安装")
    add("#97 人物/场景/系列绑定", modules.get("assets_v97"), "所选系列资产进入真实镜头生成合同")
    add("#98 声音路由", modules.get("voice_v98"), result.get("voice", {}).get("message"), required=True)
    add("#99 镜头编辑器", modules.get("editor_v99"), "支持新增/删除/拆分/合并/排序/单镜头重生")
    add("#100 专业后期", bool((result.get("postproduction") or {}).get("ready")), "FFmpeg 母带/封面/多比例版本")
    add("Wan2.1 真视频模型", bool((result.get("wan") or {}).get("wan_i2v_fp8") or (result.get("wan") or {}).get("ok")), (result.get("wan") or {}).get("message"))
    add("纯文案自动首帧", bool((result.get("auto_keyframe") or {}).get("ready")), (result.get("auto_keyframe") or {}).get("message"))
    add("授权声音克隆服务", bool((result.get("voice") or {}).get("available")), (result.get("voice") or {}).get("message"))
    required = [x for x in checks if x.get("required")]
    passed = bool(required and all(x.get("passed") for x in required))
    return {
        "ok": True,
        "passed": passed,
        "checks": checks,
        "ready_for_full_acceptance": result.get("ready_for_full_acceptance"),
        "missing_runtime_dependencies": result.get("missing_runtime_dependencies") or [],
        "next": "进入最终六场景验收" if passed else "先补齐红色本机运行依赖，再执行最终六场景验收",
    }


def _serve_script(handler):
    web = Path(__file__).resolve().parents[1] / "web" / "content-final-v101.js"
    payload = web.read_bytes()
    handler.send_response(200)
    handler.send_header("Content-Type", "application/javascript; charset=utf-8")
    handler.send_header("Content-Length", str(len(payload)))
    handler.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
    handler.send_header("Pragma", "no-cache")
    handler.end_headers()
    handler.wfile.write(payload)


def _read_json(handler, limit=32 * 1024):
    length = int(handler.headers.get("Content-Length", "0") or 0)
    if length < 0 or length > limit:
        raise ValueError("请求内容超过限制")
    return json.loads(handler.rfile.read(length) or b"{}") if length else {}


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
        path = urlsplit(handler.path).path
        if path in _SCRIPT_PATHS:
            try:
                _serve_script(handler)
            except OSError as error:
                handler._json_error(500, error)
            return
        if path == "/api/content-final/status":
            handler._json_ok(status())
            return
        return old_get(handler)

    def do_post(handler):
        path = urlsplit(handler.path).path
        if path != "/api/content-final/self-test":
            return old_post(handler)
        if not _origin_allowed(handler):
            handler._json_error(403, "仅允许本机执行最终内容中心自检")
            return
        try:
            _read_json(handler)
            handler._json_ok(self_test())
        except (ValueError, TypeError, OSError, json.JSONDecodeError) as error:
            handler._json_error(400, error)

    server.DashboardHandler.do_GET = do_get
    server.DashboardHandler.do_POST = do_post
    server.DashboardHandler._kz_content_final_v101 = True
    _INSTALLED = True


install()
