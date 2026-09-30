"""#96 real reference parsing and no-material keyframe routing.

This patch closes two gaps without pretending an unavailable model exists:
- public HTTP(S) pages are fetched and parsed only when they are really readable;
- when a production mission has no local image, a real ComfyUI text-to-image
  checkpoint is used to create a keyframe before Wan I2V starts.

Anti-bot/login failures and a missing T2I checkpoint are reported truthfully.
No private-network URL is fetched and no fake reference text/keyframe is created.
"""
from __future__ import annotations

import html
import ipaddress
import json
import re
import shutil
import socket
import time
from html.parser import HTMLParser
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

from backend import candidate_executor_activation_patch as _activation
from backend import kz_local_control_patch as _video
from backend import quality_ai_runtime_patch as _quality
from backend import server
from core.storage import data_root
from promotion import ai_production_center as _center

_INSTALLED = False
_PARSE_PATH = "/api/content-final/reference/parse"
_STATUS_PATH = "/api/content-final/reference/status"
_MAX_HTML = 2 * 1024 * 1024


class _TextParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.title = ""
        self._in_title = False
        self._skip = 0
        self.text = []
        self.meta = {}

    def handle_starttag(self, tag, attrs):
        tag = tag.lower()
        pairs = {str(k).lower(): str(v or "") for k, v in attrs}
        if tag == "title":
            self._in_title = True
        if tag in {"script", "style", "noscript", "svg"}:
            self._skip += 1
        if tag == "meta":
            key = (pairs.get("property") or pairs.get("name") or "").lower()
            value = pairs.get("content") or ""
            if key and value:
                self.meta[key] = value

    def handle_endtag(self, tag):
        tag = tag.lower()
        if tag == "title":
            self._in_title = False
        if tag in {"script", "style", "noscript", "svg"} and self._skip:
            self._skip -= 1

    def handle_data(self, data):
        value = re.sub(r"\s+", " ", str(data or "")).strip()
        if not value:
            return
        if self._in_title:
            self.title = (self.title + " " + value).strip()
        if not self._skip and len(value) >= 2:
            self.text.append(value)


def _read_json(handler, limit=64 * 1024):
    length = int(handler.headers.get("Content-Length", "0") or 0)
    if length <= 0 or length > limit:
        raise ValueError("请求内容为空或超过限制")
    return json.loads(handler.rfile.read(length) or b"{}")


def _origin_allowed(handler):
    origin = str(handler.headers.get("Origin") or "").strip()
    return not origin or origin in {
        f"http://127.0.0.1:{handler.server.server_port}",
        f"http://localhost:{handler.server.server_port}",
    }


def _public_url(value):
    raw = str(value or "").strip()
    parsed = urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("只支持公开 HTTP/HTTPS 内容链接")
    host = parsed.hostname.strip().lower()
    if host in {"localhost", "localhost.localdomain"} or host.endswith(".local"):
        raise ValueError("不允许解析本机或私有网络地址")
    try:
        infos = socket.getaddrinfo(host, parsed.port or (443 if parsed.scheme == "https" else 80), type=socket.SOCK_STREAM)
    except OSError as error:
        raise ValueError(f"无法解析来源域名：{error}") from error
    for info in infos:
        address = info[4][0].split("%", 1)[0]
        try:
            ip = ipaddress.ip_address(address)
        except ValueError:
            continue
        if not ip.is_global:
            raise ValueError("不允许解析本机、局域网或其他非公开地址")
    return raw


def _clean_page_text(parser):
    candidates = []
    for key in ("og:description", "description", "twitter:description"):
        value = re.sub(r"\s+", " ", html.unescape(parser.meta.get(key, ""))).strip()
        if value and value not in candidates:
            candidates.append(value)
    body = []
    seen = set()
    for piece in parser.text:
        value = re.sub(r"\s+", " ", html.unescape(piece)).strip()
        if len(value) < 4 or value in seen:
            continue
        if re.fullmatch(r"[\W_]+", value):
            continue
        seen.add(value)
        body.append(value)
        if sum(len(x) for x in body) >= 12000:
            break
    merged = "\n".join(candidates + body)
    return merged[:12000].strip()


def parse_reference(payload):
    url = _public_url(payload.get("url"))
    supplied = str(payload.get("text") or "").strip()
    request = Request(url, headers={
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 KazuizhiAI/2.2",
        "Accept": "text/html,application/xhtml+xml,application/json;q=0.8,*/*;q=0.5",
        "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.5",
    })
    try:
        with urlopen(request, timeout=15) as response:
            final_url = _public_url(response.geturl())
            content_type = str(response.headers.get("Content-Type") or "").lower()
            raw = response.read(_MAX_HTML + 1)
    except HTTPError as error:
        return {
            "ok": False, "status": "needs_text", "url": url,
            "message": f"来源站点返回 HTTP {error.code}；可能需要登录/验证码。系统没有猜测原内容，请粘贴分享文字或字幕。",
            "text": supplied,
        }
    except (URLError, TimeoutError, OSError, ValueError) as error:
        return {
            "ok": False, "status": "needs_text", "url": url,
            "message": f"公开页面当前无法真实读取：{str(error)[:220]}。系统没有伪造解析结果。",
            "text": supplied,
        }
    if len(raw) > _MAX_HTML:
        raw = raw[:_MAX_HTML]
    charset = "utf-8"
    match = re.search(r"charset=([\w.-]+)", content_type)
    if match:
        charset = match.group(1)
    text = raw.decode(charset, "replace")
    title = ""
    extracted = ""
    if "json" in content_type:
        try:
            obj = json.loads(text)
            extracted = json.dumps(obj, ensure_ascii=False)[:12000]
        except json.JSONDecodeError:
            extracted = text[:12000]
    else:
        parser = _TextParser()
        parser.feed(text)
        title = re.sub(r"\s+", " ", parser.meta.get("og:title") or parser.title).strip()[:180]
        extracted = _clean_page_text(parser)
    if supplied and supplied not in extracted:
        extracted = (supplied + "\n" + extracted).strip()[:12000]
    meaningful = len(re.sub(r"\s+", "", extracted)) >= 40
    return {
        "ok": meaningful,
        "status": "parsed" if meaningful else "needs_text",
        "url": final_url,
        "title": title,
        "text": extracted if meaningful else supplied,
        "content_type": content_type[:120],
        "message": (
            "已从公开页面真实读取可分析文本。" if meaningful else
            "页面可访问，但没有提取到足够正文；可能是客户端渲染或登录页。请补充分享文字/字幕。"
        ),
        "truthful": True,
    }


def _comfy_root():
    return _quality._comfyui_root()


def discover_t2i_checkpoint():
    root = _comfy_root()
    if not root:
        return None
    folder = root / "models" / "checkpoints"
    if not folder.is_dir():
        return None
    candidates = []
    for ext in ("*.safetensors", "*.ckpt", "*.pt"):
        candidates.extend(folder.rglob(ext))
    candidates = [x for x in candidates if x.is_file() and x.stat().st_size > 50 * 1024 * 1024]
    if not candidates:
        return None
    # Prefer an SDXL / realistic checkpoint when names provide a useful hint.
    def score(path):
        name = path.name.lower()
        preferred = sum(token in name for token in ("xl", "real", "photo", "jugger", "dream"))
        return preferred, path.stat().st_size
    chosen = max(candidates, key=score)
    return chosen.relative_to(folder).as_posix()


def keyframe_status():
    checkpoint = discover_t2i_checkpoint()
    root = _comfy_root()
    return {
        "ready": bool(root and checkpoint),
        "comfyui_root": str(root or ""),
        "checkpoint": checkpoint or "",
        "message": (
            "检测到真实 ComfyUI 文生图 checkpoint；无上传素材时可自动生成首帧。" if checkpoint else
            "未检测到 ComfyUI models/checkpoints 文生图模型；代码已接通，但纯文案首帧生成会明确提示安装模型，不会伪造素材。"
        ),
    }


def _image_from_history(value):
    if isinstance(value, dict):
        filename = str(value.get("filename") or "")
        if Path(filename).suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"}:
            return value
        for child in value.values():
            found = _image_from_history(child)
            if found:
                return found
    elif isinstance(value, list):
        for child in value:
            found = _image_from_history(child)
            if found:
                return found
    return None


def _resolve_comfy_image(item):
    root = _comfy_root()
    if not root or not item:
        return None
    filename = Path(str(item.get("filename") or "")).name
    subfolder = str(item.get("subfolder") or "").replace("\\", "/").strip("/")
    kind = str(item.get("type") or "output")
    base = root / ("output" if kind == "output" else kind)
    path = base / subfolder / filename if subfolder else base / filename
    return path if path.is_file() else None


def _wait_image(prompt_id, prefix, timeout=30 * 60):
    started = time.time()
    while time.time() - started < timeout:
        history = _video._comfy_json(f"/history/{prompt_id}", timeout=20)
        entry = history.get(prompt_id) if isinstance(history, dict) else None
        if isinstance(entry, dict):
            image = _resolve_comfy_image(_image_from_history(entry.get("outputs") or {}))
            if image:
                return image
            state = entry.get("status") if isinstance(entry.get("status"), dict) else {}
            if str(state.get("status_str") or "").lower() in {"error", "failed"}:
                raise RuntimeError("ComfyUI 文生图任务执行失败")
            if state.get("completed") is True:
                break
        root = _comfy_root()
        if root:
            output = root / "output"
            matches = sorted(output.rglob(prefix + "*"), key=lambda p: p.stat().st_mtime if p.is_file() else 0, reverse=True)
            for path in matches:
                if path.is_file() and path.suffix.lower() in {".png", ".jpg", ".jpeg", ".webp"} and path.stat().st_mtime >= started - 5:
                    return path
        time.sleep(2)
    raise RuntimeError("ComfyUI 文生图已结束或超时，但没有找到真实首帧文件")


def _keyframe_prompt(project, shot):
    fields = [
        project.get("name"), project.get("director_style"), shot.get("purpose"),
        shot.get("character"), shot.get("scene"), shot.get("props"), shot.get("action"),
    ]
    text = "。".join(str(x).strip() for x in fields if str(x or "").strip())
    return (text + "。真实本地服务纪实摄影，真实人物，真实家庭环境，自然光，手部正常，竖屏商业短视频首帧，无文字无水印。photorealistic documentary photo, natural light, realistic hands, no text, no watermark")[:1800]


def generate_keyframe(project, shot):
    checkpoint = discover_t2i_checkpoint()
    if not checkpoint:
        raise RuntimeError("当前没有可用图片素材，同时未检测到 ComfyUI 文生图 checkpoint。请先在 ComfyUI/models/checkpoints 安装一个可用的 SD/SDXL 模型；系统不会用占位图冒充 AI 首帧。")
    _activation._ensure_comfyui_ready()
    _video._gateway._release_ollama_model()
    width, height = (576, 1024) if str(project.get("ratio") or "9:16").replace(" ", "") not in {"16:9", "16/9", "1:1", "1/1"} else ((1024, 576) if "16" in str(project.get("ratio")) else (768, 768))
    prefix = f"image/kazuizhi_auto_{str(project.get('id') or 'p')[-10:]}_{int(shot.get('order') or 0):02d}"
    graph = {
        "1": {"inputs": {"ckpt_name": checkpoint}, "class_type": "CheckpointLoaderSimple"},
        "2": {"inputs": {"text": _keyframe_prompt(project, shot), "clip": ["1", 1]}, "class_type": "CLIPTextEncode"},
        "3": {"inputs": {"text": "low quality, blurry, deformed hands, extra fingers, text, watermark, logo, duplicate person, oversaturated", "clip": ["1", 1]}, "class_type": "CLIPTextEncode"},
        "4": {"inputs": {"width": width, "height": height, "batch_size": 1}, "class_type": "EmptyLatentImage"},
        "5": {"inputs": {"seed": int(time.time_ns() % (2**63 - 1)), "steps": 24, "cfg": 6.0, "sampler_name": "euler", "scheduler": "normal", "denoise": 1.0, "model": ["1", 0], "positive": ["2", 0], "negative": ["3", 0], "latent_image": ["4", 0]}, "class_type": "KSampler"},
        "6": {"inputs": {"samples": ["5", 0], "vae": ["1", 2]}, "class_type": "VAEDecode"},
        "7": {"inputs": {"filename_prefix": prefix, "images": ["6", 0]}, "class_type": "SaveImage"},
    }
    response = _video._comfy_json("/prompt", {"prompt": graph, "client_id": "kazuizhi-r8-v96"}, timeout=60)
    prompt_id = str(response.get("prompt_id") or "")
    if not prompt_id:
        raise RuntimeError(f"ComfyUI 文生图没有返回 prompt_id：{response}")
    source = _wait_image(prompt_id, Path(prefix).name)
    folder = data_root() / "r8" / "auto_keyframes" / str(project.get("id") or "project")
    folder.mkdir(parents=True, exist_ok=True)
    destination = folder / f"SHOT_{int(shot.get('order') or 0):02d}_{prompt_id[:10]}{source.suffix.lower()}"
    shutil.copy2(source, destination)
    asset_id = _center._id("ASSET")
    asset = {
        "id": asset_id, "created_at": _center.now_iso(), "asset_type": "真实素材",
        "name": f"自动首帧 · 镜头{int(shot.get('order') or 0)}", "rights": "虚拟资产",
        "tags": "#96自动首帧、AI生成", "note": "无用户图片时由本机 ComfyUI 文生图真实生成",
        "enabled": True, "mime_type": "image/" + ("jpeg" if destination.suffix.lower() in {".jpg", ".jpeg"} else destination.suffix.lower().lstrip(".")),
        "file_path": str(destination), "source_kind": "auto_t2i_keyframe", "prompt_id": prompt_id,
        "checkpoint": checkpoint, "project_id": project.get("id"), "shot_id": shot.get("id"),
    }
    data = _center._load()
    data.setdefault("assets", []).insert(0, asset)
    for current in data.get("storyboards") or []:
        if current.get("id") == shot.get("id"):
            current["asset_ids"] = [asset_id] + [x for x in (current.get("asset_ids") or []) if x != asset_id]
            current["auto_keyframe_asset_id"] = asset_id
            current["auto_keyframe_prompt_id"] = prompt_id
            break
    _center._audit(data, "auto_keyframe_generated", asset_id, f"#96 使用真实 ComfyUI checkpoint 为镜头{shot.get('order')}生成首帧。")
    _center._save(data)
    return asset


def ensure_project_keyframes(project, shots):
    data = _center._load()
    images = _video._recent_image_assets(data)
    if images:
        return {"generated": 0, "existing": len(images)}
    generated = 0
    # One initial image is sufficient for a continuity chain. Scene changes can
    # request additional keyframes later through _asset_for_shot.
    if shots:
        generate_keyframe(project, shots[0])
        generated = 1
    return {"generated": generated, "existing": 0}


_ORIGINAL_ACTIVATE = _activation._activate_latest_mission
_ORIGINAL_ASSET_FOR_SHOT = _video._asset_for_shot


def _activate_v96():
    project, shots = _activation._latest_project_and_shots()
    ensure_project_keyframes(project, shots)
    return _ORIGINAL_ACTIVATE()


def _asset_for_shot_v96(shot):
    try:
        return _ORIGINAL_ASSET_FOR_SHOT(shot)
    except RuntimeError as error:
        if "可用的本地图片素材" not in str(error):
            raise
    data = _center._load()
    project = next((x for x in data.get("projects") or [] if x.get("id") == shot.get("project_id")), None)
    if not project:
        raise RuntimeError("没有找到当前镜头所属项目")
    generate_keyframe(project, shot)
    return _ORIGINAL_ASSET_FOR_SHOT(_video._center_shot(shot.get("id")))


def reference_status():
    return {
        "parser": "real_public_http_parser",
        "truthful_fallback": True,
        "max_html_bytes": _MAX_HTML,
        "auto_keyframe": keyframe_status(),
    }


def install():
    global _INSTALLED
    if _INSTALLED:
        return
    old_get = server.DashboardHandler.do_GET
    old_post = server.DashboardHandler.do_POST

    def do_get(handler):
        path = urlsplit(handler.path).path
        if path == _STATUS_PATH:
            handler._json_ok(reference_status())
            return
        return old_get(handler)

    def do_post(handler):
        path = urlsplit(handler.path).path
        if path != _PARSE_PATH:
            return old_post(handler)
        if not _origin_allowed(handler):
            handler._json_error(403, "仅允许本机内容中心解析参考来源")
            return
        try:
            handler._json_ok(parse_reference(_read_json(handler)))
        except (ValueError, TypeError, OSError, json.JSONDecodeError) as error:
            handler._json_error(400, error)

    server.DashboardHandler.do_GET = do_get
    server.DashboardHandler.do_POST = do_post
    _activation._activate_latest_mission = _activate_v96
    _video._asset_for_shot = _asset_for_shot_v96
    server.DashboardHandler._kz_content_reference_v96 = True
    _INSTALLED = True


install()
