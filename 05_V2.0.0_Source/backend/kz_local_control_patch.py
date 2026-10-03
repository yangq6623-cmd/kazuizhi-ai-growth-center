"""Localhost-only HTTP adapter for Kazuizhi Site Tools/WebMCP control."""
from __future__ import annotations

import ipaddress
import json
from urllib.parse import urlsplit

from backend import server
from integrations.kz_local_control import (
    execute_tool,
    pair_webmcp,
    recent_audit,
    status,
    tool_catalog,
)

_INSTALLED = False
SITE_TOOLS_MARKER = "webmcp-local"


def _client_is_loopback(handler) -> bool:
    try:
        host = str((handler.client_address or ("", 0))[0] or "")
        return ipaddress.ip_address(host).is_loopback
    except (ValueError, TypeError):
        return False


def _origin_allowed(handler) -> bool:
    if not _client_is_loopback(handler):
        return False
    if str(handler.headers.get("X-KZ-Site-Tools") or "").strip() != SITE_TOOLS_MARKER:
        return False
    origin = str(handler.headers.get("Origin") or "").strip()
    if not origin:
        # Non-browser/local automation clients are not accepted on the preferred
        # WebMCP path. Remote/unattended automation must use the signed Relay.
        return False
    return origin in {
        f"http://127.0.0.1:{handler.server.server_port}",
        f"http://localhost:{handler.server.server_port}",
    }


def _read_json(handler, *, max_bytes=64 * 1024):
    length = int(handler.headers.get("Content-Length", "0"))
    if length <= 0 or length > max_bytes:
        raise ValueError("请求大小不正确")
    return json.loads(handler.rfile.read(length) or b"{}")


def install():
    global _INSTALLED
    if _INSTALLED:
        return

    original_get = server.DashboardHandler.do_GET
    original_post = server.DashboardHandler.do_POST

    def do_get(handler):
        path = urlsplit(handler.path).path
        if path.startswith("/api/kz-local-control/") and not _client_is_loopback(handler):
            handler._json_error(403, "KZ Local Control 只允许本机访问")
            return
        try:
            if path == "/api/kz-local-control/status":
                handler._json_ok(status())
                return
            if path == "/api/kz-local-control/tools":
                handler._json_ok({"items": tool_catalog()})
                return
            if path == "/api/kz-local-control/audit":
                handler._json_ok({"items": recent_audit(50)})
                return
        except (OSError, ValueError, RuntimeError, TypeError) as error:
            handler._json_error(500, error)
            return
        return original_get(handler)

    def do_post(handler):
        path = urlsplit(handler.path).path
        if path not in {"/api/kz-local-control/pair", "/api/kz-local-control/tool"}:
            return original_post(handler)
        if not _origin_allowed(handler):
            handler._json_error(403, "KZ Local Control 只接受当前本机工作台的 Site Tools 调用")
            return
        try:
            payload = _read_json(handler)
            if path.endswith("/pair"):
                result = pair_webmcp(payload)
                handler._json_ok(result, code=200)
                return
            result = execute_tool(
                payload.get("tool"),
                payload.get("args") if isinstance(payload.get("args"), dict) else {},
                request_id=payload.get("request_id"),
            )
            handler._json_ok(result, code=200)
        except json.JSONDecodeError as error:
            handler._json_error(400, error)
        except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
            handler._json_error(409, error)

    server.DashboardHandler.do_GET = do_get
    server.DashboardHandler.do_POST = do_post
    server.DashboardHandler._kz_local_control_patched = True
    _INSTALLED = True


install()

# Apply the quality-first local AI policy after the base AI gateway has finished
# installing.  This keeps long RTX3060 text work alive instead of declaring a
# false failure while the GPU is still actively computing.
from backend import quality_ai_runtime_patch as _quality_ai_runtime_patch  # noqa: E402,F401

# R8-18 #70: real local candidate execution.  The owner continues to operate
# only the Kazuizhi platform.  This layer consumes persisted candidate
# checkpoints, sends a real Wan2.1 I2V API graph to the already-running ComfyUI
# on :8188, waits for a real output file, and only then records the candidate as
# generated.  Work is serialized for the RTX3060 12 GB card and stops on the
# first executor error so a bad workflow can never burn through every candidate.
import mimetypes as _mimetypes  # noqa: E402
import random as _random  # noqa: E402
import shutil as _shutil  # noqa: E402
import threading as _threading  # noqa: E402
import time as _time  # noqa: E402
from pathlib import Path as _Path  # noqa: E402
from urllib.error import HTTPError as _HTTPError, URLError as _URLError  # noqa: E402
from urllib.parse import parse_qs as _parse_qs  # noqa: E402
from urllib.request import Request as _Request, urlopen as _urlopen  # noqa: E402

from backend import ai_gateway_patch as _gateway  # noqa: E402
from backend import production_mission_patch as _mission  # noqa: E402
from core.storage import data_root as _data_root  # noqa: E402
from promotion import ai_production_center as _content_center  # noqa: E402

_COMFY_BASE = "http://127.0.0.1:8188"
_COMFY_VIDEO_EXTS = {".mp4", ".webm", ".mov", ".mkv"}
_EXECUTOR_LOCK = _threading.Lock()
_EXECUTOR_THREAD = None
_EXECUTOR_STATE = {
    "status": "idle",
    "message": "等待镜头候选任务",
    "candidate_key": "",
    "shot_id": "",
    "prompt_id": "",
    "last_error": "",
    "updated_at": "",
}


def _executor_now():
    return _content_center.now_iso()


def _set_executor_state(**patch):
    with _EXECUTOR_LOCK:
        _EXECUTOR_STATE.update(patch)
        _EXECUTOR_STATE["updated_at"] = _executor_now()


def _executor_snapshot():
    with _EXECUTOR_LOCK:
        state = dict(_EXECUTOR_STATE)
    state["comfyui"] = _quality_ai_runtime_patch._comfyui_ready()
    return state


def _comfy_json(path, payload=None, timeout=30):
    url = f"{_COMFY_BASE}{path}"
    data = None
    method = "GET"
    headers = {"Accept": "application/json"}
    if payload is not None:
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        method = "POST"
        headers["Content-Type"] = "application/json"
    request = _Request(url, data=data, headers=headers, method=method)
    try:
        with _urlopen(request, timeout=timeout) as response:
            raw = response.read()
    except _HTTPError as error:
        try:
            detail = error.read().decode("utf-8", errors="replace")
        except OSError:
            detail = ""
        raise RuntimeError(f"ComfyUI HTTP {error.code}: {detail[:600] or '请求被拒绝'}") from error
    except (_URLError, TimeoutError, OSError) as error:
        raise RuntimeError(f"无法访问 ComfyUI 8188：{error}") from error
    if not raw:
        return {}
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise RuntimeError("ComfyUI 返回了无法解析的数据") from error


def _recent_image_assets(data=None):
    data = data or _content_center._load()
    result = []
    for asset in data.get("assets") or []:
        if asset.get("enabled") is False or asset.get("rights") == "待确认":
            continue
        mime_type = str(asset.get("mime_type") or "")
        path = _Path(str(asset.get("file_path") or ""))
        if not mime_type.startswith("image/") or not path.is_file():
            continue
        result.append(asset)
    return result


def _ensure_comfy_input(asset, data=None):
    data = data or _content_center._load()
    root = _quality_ai_runtime_patch._comfyui_root()
    if not root:
        raise RuntimeError("没有找到 ComfyUI 主目录")
    source = _Path(str(asset.get("file_path") or ""))
    if not source.is_file():
        raise RuntimeError("上传的起始图片文件不存在")
    filename = str(asset.get("comfyui_filename") or "").strip()
    if not filename:
        filename = f"kazuizhi_{asset.get('id')}{source.suffix.lower()}"
    target = root / "input" / filename
    if not target.exists() or target.stat().st_size != source.stat().st_size:
        target.parent.mkdir(parents=True, exist_ok=True)
        _shutil.copy2(source, target)
    for item in data.get("assets") or []:
        if item.get("id") == asset.get("id"):
            item["comfyui_filename"] = filename
            item["comfyui_input_path"] = str(target)
            item["comfyui_synced"] = True
            asset = item
            break
    _content_center._save(data)
    return asset


def _center_shot(shot_id, data=None):
    data = data or _content_center._load()
    for shot in data.get("storyboards") or []:
        if shot.get("id") == shot_id:
            return shot
    raise RuntimeError("没有找到当前镜头")


def _asset_for_shot(shot):
    data = _content_center._load()
    preferred = set(shot.get("asset_ids") or [])
    images = _recent_image_assets(data)
    if preferred:
        preferred_images = [x for x in images if x.get("id") in preferred]
        if preferred_images:
            return _ensure_comfy_input(preferred_images[0], data)
    if images:
        return _ensure_comfy_input(images[0], data)
    raise RuntimeError("当前任务没有可用的本地图片素材，请先在平台上传图片")


def _positive_prompt(shot):
    fields = [
        shot.get("purpose"), shot.get("narration"), shot.get("action"),
        shot.get("character"), shot.get("scene"), shot.get("motion"),
    ]
    parts = [str(x).strip() for x in fields if str(x or "").strip()]
    parts.append("真实自然的本地维修纪实短视频，人物动作稳定自然，环境细节真实，镜头连贯，不要明显AI感")
    parts.append("realistic documentary style, natural human motion, stable camera, detailed environment, cinematic but authentic")
    return "。".join(parts)[:1800]


def _negative_prompt(shot):
    base = [
        "低质量", "模糊", "过曝", "画面闪烁", "人物变形", "多余手指", "畸形手",
        "重复人物", "字幕乱码", "水印", "静止不动", "背景杂乱", "low quality",
        "blurry", "deformed hands", "extra fingers", "flicker", "watermark",
    ]
    base.extend(str(x).strip() for x in (shot.get("negative_constraints") or []) if str(x).strip())
    return ", ".join(base)[:1800]


def _wan_api_graph(shot, asset, candidate_key):
    # #70 intentionally mirrors the official Wan2.1 I2V template that the owner
    # has already opened successfully.  The first closed-loop uses a conservative
    # 512x512 / 33-frame contract to prove reliability on 12 GB before #71 tunes
    # aspect ratio, duration and shot-specific quality budgets.
    safe_key = "".join(ch if ch.isalnum() else "_" for ch in candidate_key)[:70]
    prefix = f"video/kazuizhi_{safe_key}"
    graph = {
        "37": {"inputs": {"unet_name": "wan2.1_i2v_480p_14B_fp8_scaled.safetensors", "weight_dtype": "default"}, "class_type": "UNETLoader"},
        "38": {"inputs": {"clip_name": "umt5_xxl_fp8_e4m3fn_scaled.safetensors", "type": "wan", "device": "default"}, "class_type": "CLIPLoader"},
        "39": {"inputs": {"vae_name": "wan_2.1_vae.safetensors"}, "class_type": "VAELoader"},
        "49": {"inputs": {"clip_name": "clip_vision_h.safetensors"}, "class_type": "CLIPVisionLoader"},
        "6": {"inputs": {"text": _positive_prompt(shot), "clip": ["38", 0]}, "class_type": "CLIPTextEncode"},
        "7": {"inputs": {"text": _negative_prompt(shot), "clip": ["38", 0]}, "class_type": "CLIPTextEncode"},
        "52": {"inputs": {"image": asset.get("comfyui_filename"), "upload": "image"}, "class_type": "LoadImage"},
        "51": {"inputs": {"crop": "none", "clip_vision": ["49", 0], "image": ["52", 0]}, "class_type": "CLIPVisionEncode"},
        "50": {"inputs": {"width": 512, "height": 512, "length": 33, "batch_size": 1, "positive": ["6", 0], "negative": ["7", 0], "vae": ["39", 0], "clip_vision_output": ["51", 0], "start_image": ["52", 0]}, "class_type": "WanImageToVideo"},
        "54": {"inputs": {"shift": 8, "model": ["37", 0]}, "class_type": "ModelSamplingSD3"},
        "3": {"inputs": {"seed": _random.randint(0, 2**63 - 1), "steps": 20, "cfg": 6, "sampler_name": "uni_pc", "scheduler": "simple", "denoise": 1.0, "model": ["54", 0], "positive": ["50", 0], "negative": ["50", 1], "latent_image": ["50", 2]}, "class_type": "KSampler"},
        "8": {"inputs": {"samples": ["3", 0], "vae": ["39", 0]}, "class_type": "VAEDecode"},
        "55": {"inputs": {"fps": 16, "images": ["8", 0]}, "class_type": "CreateVideo"},
        "56": {"inputs": {"filename_prefix": prefix, "format": "auto", "codec": "auto", "video": ["55", 0]}, "class_type": "SaveVideo"},
    }
    return graph, prefix


def _history_video_item(value):
    if isinstance(value, dict):
        filename = str(value.get("filename") or "")
        if _Path(filename).suffix.lower() in _COMFY_VIDEO_EXTS:
            return value
        for child in value.values():
            result = _history_video_item(child)
            if result:
                return result
    elif isinstance(value, list):
        for child in value:
            result = _history_video_item(child)
            if result:
                return result
    return None


def _resolve_history_video(item):
    if not item:
        return None
    root = _quality_ai_runtime_patch._comfyui_root()
    if not root:
        return None
    filename = _Path(str(item.get("filename") or "")).name
    if not filename:
        return None
    subfolder = str(item.get("subfolder") or "").replace("\\", "/").strip("/")
    kind = str(item.get("type") or "output")
    base = root / ("output" if kind == "output" else kind)
    path = base / subfolder / filename if subfolder else base / filename
    return path if path.is_file() else None


def _scan_prefixed_video(prefix, started_at):
    root = _quality_ai_runtime_patch._comfyui_root()
    if not root:
        return None
    relative = _Path(prefix)
    folder = root / "output" / relative.parent
    if not folder.is_dir():
        return None
    candidates = []
    for path in folder.glob(f"{relative.name}*"):
        try:
            if path.is_file() and path.suffix.lower() in _COMFY_VIDEO_EXTS and path.stat().st_mtime >= started_at - 5:
                candidates.append(path)
        except OSError:
            continue
    return max(candidates, key=lambda p: p.stat().st_mtime) if candidates else None


def _wait_for_comfy_video(prompt_id, prefix, timeout=6 * 60 * 60):
    started = _time.time()
    while _time.time() - started < timeout:
        history = _comfy_json(f"/history/{prompt_id}", timeout=20)
        entry = history.get(prompt_id) if isinstance(history, dict) else None
        if isinstance(entry, dict):
            item = _history_video_item(entry.get("outputs") or {})
            resolved = _resolve_history_video(item)
            if resolved:
                return resolved
            status = entry.get("status") if isinstance(entry.get("status"), dict) else {}
            status_text = str(status.get("status_str") or "").lower()
            if status_text in {"error", "failed"}:
                raise RuntimeError("ComfyUI 执行失败，请查看 ComfyUI 控制台")
            if status.get("completed") is True:
                scanned = _scan_prefixed_video(prefix, started)
                if scanned:
                    return scanned
                raise RuntimeError("ComfyUI 已结束任务，但没有找到真实视频输出文件")
        scanned = _scan_prefixed_video(prefix, started)
        if scanned:
            return scanned
        _time.sleep(5)
    raise RuntimeError("ComfyUI 单个镜头运行超过6小时，任务检查点已保留")


def _existing_output(candidate_key):
    data = _content_center._load()
    for output in data.get("outputs") or []:
        if output.get("candidate_key") == candidate_key:
            path = _Path(str(output.get("file_path") or ""))
            if path.is_file():
                return output
    return None


def _update_center_task(shot_id, status, detail=""):
    data = _content_center._load()
    shot = None
    for item in data.get("storyboards") or []:
        if item.get("id") == shot_id:
            shot = item
            break
    total = max(1, int((shot or {}).get("candidate_count") or 1))
    done = len([x for x in data.get("outputs") or [] if x.get("shot_id") == shot_id and _Path(str(x.get("file_path") or "")).is_file()])
    progress = min(100, int(round(done / total * 100)))
    if shot:
        shot["status"] = "候选已生成" if done >= total else ("候选生成中" if status != "执行失败" else "候选生成异常")
    for task in data.get("tasks") or []:
        if task.get("shot_id") != shot_id or "候选" not in str(task.get("kind") or ""):
            continue
        task["executor"] = "ComfyUI 8188 · Wan2.1 I2V FP8"
        task["status"] = "已完成" if done >= total else status
        task["progress"] = 100 if done >= total else progress
        if detail:
            task["detail"] = detail[:800]
    _content_center._save(data)


def _persist_candidate(work, source_path, prompt_id, asset):
    candidate = work.get("candidate") or {}
    shot_contract = work.get("shot") or {}
    candidate_key = str(candidate.get("key") or "")
    existing = _existing_output(candidate_key)
    if existing:
        _mission.checkpoint({"mission_id": work.get("mission_id"), "candidate_key": candidate_key, "status": "generated", "output_id": existing.get("id"), "file_url": existing.get("file_url")})
        return existing

    project_id = str(work.get("project_id") or "project")
    shot_id = str(shot_contract.get("shot_id") or "")
    output_id = _content_center._id("OUT")
    ext = source_path.suffix.lower() if source_path.suffix.lower() in _COMFY_VIDEO_EXTS else ".mp4"
    folder = _data_root() / "r8" / "generated_candidates" / project_id
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / f"{output_id}{ext}"
    _shutil.copy2(source_path, destination)
    file_url = f"/api/production-output/file?id={output_id}"
    output = {
        "id": output_id,
        "project_id": project_id,
        "shot_id": shot_id,
        "candidate_key": candidate_key,
        "candidate_index": candidate.get("index"),
        "kind": "镜头候选视频",
        "status": "候选已生成",
        "selected": False,
        "created_at": _executor_now(),
        "source": "ComfyUI Wan2.1 I2V 480P 14B FP8 scaled",
        "prompt_id": prompt_id,
        "asset_id": asset.get("id"),
        "file_path": str(destination),
        "file_url": file_url,
        "url": file_url,
    }
    data = _content_center._load()
    data.setdefault("outputs", []).append(output)
    _content_center._audit(data, "real_candidate_generated", output_id, f"镜头 {shot_contract.get('order')} 候选 {candidate.get('index')} 已由 ComfyUI 生成真实视频文件。")
    _content_center._save(data)
    _mission.checkpoint({"mission_id": work.get("mission_id"), "candidate_key": candidate_key, "status": "generated", "output_id": output_id, "file_url": file_url})
    _update_center_task(shot_id, "ComfyUI 生成中", f"已生成真实候选文件；镜头 {shot_contract.get('order')} 正在继续串行处理剩余候选。")
    return output


def _run_candidate(work):
    candidate = work.get("candidate") or {}
    shot_contract = work.get("shot") or {}
    candidate_key = str(candidate.get("key") or "")
    shot_id = str(shot_contract.get("shot_id") or "")
    existing = _existing_output(candidate_key)
    if existing:
        _mission.checkpoint({"mission_id": work.get("mission_id"), "candidate_key": candidate_key, "status": "generated", "output_id": existing.get("id"), "file_url": existing.get("file_url")})
        return existing

    center_data = _content_center._load()
    shot = _center_shot(shot_id, center_data)
    asset = _asset_for_shot(shot)
    ready = _quality_ai_runtime_patch._comfyui_ready()
    if not ready.get("ok"):
        raise RuntimeError(ready.get("message") or "ComfyUI / Wan2.1 FP8 尚未就绪")

    # Release any resident Ollama text model before the 14B video model loads.
    _gateway._release_ollama_model()
    _time.sleep(1.0)

    graph, prefix = _wan_api_graph(shot, asset, candidate_key)
    _set_executor_state(status="submitting", message=f"正在提交镜头 {shot_contract.get('order')} 候选 {candidate.get('index')} 到 ComfyUI", candidate_key=candidate_key, shot_id=shot_id, prompt_id="", last_error="")
    response = _comfy_json("/prompt", {"prompt": graph, "client_id": "kazuizhi-r8-70"}, timeout=60)
    prompt_id = str(response.get("prompt_id") or "")
    if not prompt_id:
        raise RuntimeError(f"ComfyUI 没有返回 prompt_id：{response}")
    _set_executor_state(status="running", message=f"ComfyUI 正在生成镜头 {shot_contract.get('order')} 候选 {candidate.get('index')}", prompt_id=prompt_id)
    _update_center_task(shot_id, "ComfyUI 生成中", f"ComfyUI 已接收真实生成任务：{prompt_id}；RTX3060 正在串行处理。")
    source = _wait_for_comfy_video(prompt_id, prefix)
    output = _persist_candidate(work, source, prompt_id, asset)
    _set_executor_state(status="running", message=f"候选 {candidate_key} 已生成并回写平台，继续下一候选", last_error="")
    return output


def _worker_loop():
    global _EXECUTOR_THREAD
    try:
        ready = _quality_ai_runtime_patch._comfyui_ready()
        if not ready.get("ok"):
            _set_executor_state(status="waiting", message=ready.get("message") or "等待 ComfyUI 就绪")
            return
        if not _recent_image_assets():
            _set_executor_state(status="waiting", message="等待平台上传可用图片素材")
            return
        _set_executor_state(status="running", message="ComfyUI 候选执行器已启动", last_error="")
        while True:
            claim = _mission.claim_next({})
            work = claim.get("work") if isinstance(claim, dict) else None
            if not work:
                mission = claim.get("mission") if isinstance(claim, dict) else {}
                if isinstance(mission, dict) and mission.get("status") == "waiting_retry":
                    _set_executor_state(status="waiting_retry", message="等待当前失败候选到达自动重试时间")
                    _time.sleep(10)
                    continue
                _set_executor_state(status="completed", message="当前已没有待执行的镜头候选", candidate_key="", shot_id="", prompt_id="", last_error="")
                return
            candidate = work.get("candidate") or {}
            shot = work.get("shot") or {}
            try:
                _run_candidate(work)
            except Exception as error:  # keep completed checkpoints; stop on first real executor error
                candidate_key = str(candidate.get("key") or "")
                shot_id = str(shot.get("shot_id") or "")
                try:
                    _mission.fail({"mission_id": work.get("mission_id"), "candidate_key": candidate_key, "error": str(error), "retryable": True})
                except Exception:
                    pass
                _update_center_task(shot_id, "执行失败", f"ComfyUI 本轮未完成：{error}。已完成候选不会重跑；修复后可从当前检查点继续。")
                _set_executor_state(status="error", message="ComfyUI 本轮执行未完成，已停止后续候选以避免重复失败", candidate_key=candidate_key, shot_id=shot_id, last_error=str(error))
                return
    finally:
        with _EXECUTOR_LOCK:
            _EXECUTOR_THREAD = None


def _start_comfy_worker():
    global _EXECUTOR_THREAD
    with _EXECUTOR_LOCK:
        if _EXECUTOR_THREAD is not None and _EXECUTOR_THREAD.is_alive():
            return False
        _EXECUTOR_THREAD = _threading.Thread(target=_worker_loop, name="kazuizhi-comfyui-wan-worker", daemon=True)
        _EXECUTOR_THREAD.start()
        return True


def _has_pending_candidate_tasks():
    data = _content_center._load()
    for task in data.get("tasks") or []:
        if "候选" not in str(task.get("kind") or ""):
            continue
        if str(task.get("status") or "") not in {"已完成", "完成", "取消", "已取消"}:
            return True
    return False


def _attach_assets_and_start(payload):
    patched = dict(payload or {})
    requested = [str(x) for x in (patched.get("asset_ids") or []) if str(x)]
    data = _content_center._load()
    valid = [x.get("id") for x in _recent_image_assets(data)]
    if not requested:
        requested = valid[:6]
    else:
        requested = [x for x in requested if x in valid]
    patched["asset_ids"] = requested
    task = _ORIGINAL_QUEUE_CANDIDATE(patched)

    data = _content_center._load()
    for shot in data.get("storyboards") or []:
        if shot.get("id") == patched.get("shot_id"):
            shot["asset_ids"] = list(requested)
            break
    for item in data.get("tasks") or []:
        if item.get("id") == task.get("id"):
            item["asset_ids"] = list(requested)
            item["executor"] = "ComfyUI 8188 · Wan2.1 I2V FP8"
            item["detail"] = f"已绑定 {len(requested)} 个本地图片素材；等待/执行 ComfyUI 真实候选生成。"
            break
    _content_center._save(data)
    task["asset_ids"] = list(requested)
    _start_comfy_worker()
    return task


def _stream_output(handler, path, mime_type):
    size = path.stat().st_size
    start, end = 0, size - 1
    range_header = str(handler.headers.get("Range") or "")
    partial = False
    if range_header.startswith("bytes="):
        try:
            spec = range_header[6:].split(",", 1)[0]
            left, right = spec.split("-", 1)
            if left:
                start = max(0, int(left))
            if right:
                end = min(size - 1, int(right))
            if start > end:
                raise ValueError
            partial = True
        except (ValueError, TypeError):
            handler.send_response(416)
            handler.send_header("Content-Range", f"bytes */{size}")
            handler.end_headers()
            return
    length = end - start + 1
    handler.send_response(206 if partial else 200)
    handler.send_header("Content-Type", mime_type)
    handler.send_header("Accept-Ranges", "bytes")
    handler.send_header("Content-Length", str(length))
    if partial:
        handler.send_header("Content-Range", f"bytes {start}-{end}/{size}")
    handler.end_headers()
    with path.open("rb") as stream:
        stream.seek(start)
        remaining = length
        while remaining > 0:
            chunk = stream.read(min(1024 * 1024, remaining))
            if not chunk:
                break
            handler.wfile.write(chunk)
            remaining -= len(chunk)


def _serve_production_output(handler):
    output_id = (_parse_qs(urlsplit(handler.path).query).get("id") or [""])[0]
    data = _content_center._load()
    output = next((x for x in data.get("outputs") or [] if x.get("id") == output_id), None)
    if not output:
        handler._json_error(404, "没有找到该候选视频")
        return
    path = _Path(str(output.get("file_path") or ""))
    try:
        root = (_data_root() / "r8" / "generated_candidates").resolve()
        resolved = path.resolve()
        if not resolved.is_file() or root not in resolved.parents:
            raise ValueError("候选视频文件不存在或路径不允许访问")
        mime_type = _mimetypes.guess_type(resolved.name)[0] or "video/mp4"
        _stream_output(handler, resolved, mime_type)
    except (OSError, ValueError) as error:
        handler._json_error(404, error)


def _install_comfy_executor_surface():
    handler_cls = server.DashboardHandler
    if getattr(handler_cls, "_kz_comfy_executor_patched", False):
        return
    original_get = handler_cls.do_GET

    def do_get(handler):
        path = urlsplit(handler.path).path
        if path == "/api/comfyui-executor/status":
            handler._json_ok({"ok": True, "executor": _executor_snapshot()})
            return
        if path == "/api/production-output/file":
            _serve_production_output(handler)
            return
        return original_get(handler)

    handler_cls.do_GET = do_get
    handler_cls._kz_comfy_executor_patched = True


_ORIGINAL_QUEUE_CANDIDATE = _content_center.queue_candidate_generation
if not getattr(_content_center, "_kz_comfy_queue_patched", False):
    _content_center.queue_candidate_generation = _attach_assets_and_start
    _content_center._kz_comfy_queue_patched = True

_install_comfy_executor_surface()

# #69 may already have persisted "待本地执行器" tasks.  After installing #70,
# resume them automatically without asking the owner to recreate the project.
if _has_pending_candidate_tasks():
    _start_comfy_worker()
