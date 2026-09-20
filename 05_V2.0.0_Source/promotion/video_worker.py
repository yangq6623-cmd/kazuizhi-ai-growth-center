"""Local R8 video execution worker controlled by ChatGPT production contracts.

The worker never invents strategy.  It executes ChatGPT's validated storyboard,
prefers suitable local real material when available, and degrades safely to
truthful information/brand cards when material is missing.  A missing owner
asset therefore cannot block MP4 output, while synthetic content is never
presented as a real repair/customer case.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
import threading
from pathlib import Path

from core.storage import data_root
from promotion import content_factory


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}
_WORKER_LOCK = threading.Lock()


def _flags():
    return getattr(subprocess, "CREATE_NO_WINDOW", 0)


def _run(args, timeout=30):
    return subprocess.run(args, capture_output=True, timeout=timeout,
                          creationflags=_flags(), check=False)


def find_ffmpeg():
    configured = os.environ.get("KAZUIZHI_FFMPEG_PATH")
    if configured:
        try:
            if Path(configured).is_file():
                return Path(configured)
        except OSError:
            pass
    direct = shutil.which("ffmpeg")
    if direct:
        return Path(direct)
    try:
        import imageio_ffmpeg
        candidate = Path(imageio_ffmpeg.get_ffmpeg_exe())
        if candidate.is_file():
            return candidate
    except (ImportError, OSError, AttributeError):
        pass
    roots = []
    if getattr(sys, "frozen", False):
        roots.append(Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)))
        roots.append(Path(sys.executable).parent)
    roots.append(Path(__file__).resolve().parents[1])
    for root in roots:
        for pattern in ("imageio_ffmpeg/binaries/ffmpeg*.exe", "vendor/imageio_ffmpeg/binaries/ffmpeg*.exe", "tools/ffmpeg.exe"):
            try:
                matches = list(root.glob(pattern))
            except OSError:
                matches = []
            if matches:
                return matches[0]
    return None


def _nvidia():
    executable = shutil.which("nvidia-smi")
    if not executable:
        return {"available": False, "message": "未找到 NVIDIA 驱动工具"}
    result = _run([executable, "--query-gpu=name,driver_version,memory.total", "--format=csv,noheader"], 10)
    text = result.stdout.decode("utf-8", "replace").strip()
    if result.returncode != 0 or not text:
        return {"available": False, "message": "NVIDIA 驱动状态读取失败"}
    return {"available": True, "description": text.splitlines()[0]}


def status():
    ffmpeg = find_ffmpeg()
    gpu = _nvidia()
    nvenc = False
    version = ""
    if ffmpeg:
        encoders = _run([str(ffmpeg), "-hide_banner", "-encoders"], 20)
        listing = (encoders.stdout + encoders.stderr).decode("utf-8", "replace")
        nvenc = "h264_nvenc" in listing
        probe = _run([str(ffmpeg), "-hide_banner", "-version"], 10)
        version = probe.stdout.decode("utf-8", "replace").splitlines()[0] if probe.stdout else ""
    ready = bool(ffmpeg and gpu.get("available") and nvenc)
    data = content_factory._load()
    waiting = sum(1 for x in data.get("videos", []) if x.get("status") == "等待生产")
    return {
        "status": "ready" if ready else "partial",
        "ffmpeg_found": bool(ffmpeg), "ffmpeg_path": str(ffmpeg or ""),
        "ffmpeg_version": version, "gpu": gpu, "nvenc": nvenc,
        "encoder": "h264_nvenc" if nvenc else "libx264",
        "busy": _WORKER_LOCK.locked(), "queue_depth": waiting,
        "message": "RTX 3060 视频执行队列已就绪" if ready else "视频执行可降级到兼容编码；请检查GPU/NVENC状态",
        "generation_scope": (
            "执行ChatGPT分镜；本地真实素材可选。缺素材时先走安全降级并继续输出MP4；"
            "AI生成镜头仅在本地生成适配器可用时启用，真实维修过程不会被伪造。"
        ),
    }


def _font():
    candidates = [
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "msyh.ttc",
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "msyhbd.ttc",
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "simhei.ttf",
    ]
    return next((x for x in candidates if x.is_file()), None)


def _wrapped(text, width=14, max_lines=8):
    text = str(text or "").strip()
    if not text:
        return ""
    rows = []
    for paragraph in text.splitlines() or [text]:
        paragraph = paragraph.strip()
        for index in range(0, len(paragraph), width):
            rows.append(paragraph[index:index + width])
            if len(rows) >= max_lines:
                break
        if len(rows) >= max_lines:
            break
    return "\n".join(rows)


def _card(path, title, subtitle, accent="#2865df", badge="卡嘴子 · 淮安本地服务",
          footnote="AI辅助排版 · 最终由人工审核"):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as error:
        raise RuntimeError("视频画面组件缺失，请重新安装最终版") from error
    width, height = 1080, 1920
    image = Image.new("RGB", (width, height), "#0d2445")
    draw = ImageDraw.Draw(image)
    for y in range(height):
        ratio = y / height
        draw.line((0, y, width, y), fill=(13 + int(22 * ratio), 36 + int(38 * ratio), 69 + int(72 * ratio)))
    draw.rounded_rectangle((82, 116, 998, 1740), radius=50, fill="#ffffff", outline=accent, width=8)
    draw.rounded_rectangle((142, 202, 938, 326), radius=25, fill=accent)
    font_path = _font()
    title_font = ImageFont.truetype(str(font_path), 70) if font_path else ImageFont.load_default()
    sub_font = ImageFont.truetype(str(font_path), 40) if font_path else ImageFont.load_default()
    small_font = ImageFont.truetype(str(font_path), 30) if font_path else ImageFont.load_default()
    draw.text((180, 225), badge[:28], font=sub_font, fill="white")
    draw.multiline_text((145, 530), _wrapped(title, 11, 7), font=title_font, fill="#13213a", spacing=24)
    draw.multiline_text((145, 1190), _wrapped(subtitle, 19, 7), font=sub_font, fill="#53627a", spacing=17)
    draw.text((145, 1600), footnote[:34], font=small_font, fill=accent)
    image.save(path, "PNG")


def _encode_args(worker):
    if worker.get("status") == "ready":
        return ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "23", "-b:v", "0"]
    return ["-c:v", "libx264", "-preset", "medium", "-crf", "23"]


def _render_segment(ffmpeg, source, output, duration, width, height, fps, worker):
    source = Path(source)
    if source.suffix.lower() in IMAGE_SUFFIXES:
        input_args = ["-loop", "1", "-i", str(source)]
    elif source.suffix.lower() in VIDEO_SUFFIXES:
        input_args = ["-stream_loop", "-1", "-i", str(source)]
    else:
        raise ValueError(f"不支持的素材格式：{source.suffix}")
    vf = (
        f"scale={width}:{height}:force_original_aspect_ratio=decrease,"
        f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps={fps}"
    )
    command = [
        str(ffmpeg), "-y", "-hide_banner", "-loglevel", "error",
        *input_args, "-t", str(duration), "-vf", vf, "-an",
        *_encode_args(worker), "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output),
    ]
    result = _run(command, timeout=max(120, int(duration * 25)))
    if result.returncode != 0 or not output.is_file() or output.stat().st_size < 1024:
        error = result.stderr.decode("utf-8", "replace")[-1200:]
        raise RuntimeError(f"镜头渲染失败：{error or '未生成有效镜头'}")


def _asset_buckets(video, data):
    ids = set(video.get("asset_ids") or [])
    assets = [x for x in data.get("assets", []) if x.get("id") in ids and Path(x.get("local_path", "")).is_file()]
    real = [x for x in assets if x.get("kind") in {"真实现场视频", "真实现场照片", "师傅讲解"}]
    synthetic = [x for x in assets if x.get("kind") == "AI辅助镜头"]
    brand = [x for x in assets if x.get("kind") == "品牌素材"]
    return {"all": assets, "real": real, "synthetic": synthetic, "brand": brand}


def _route_shot(shot, buckets, cursors):
    chain = shot.get("source_preference") or ["local_real", "licensed_external", "ai_generated", "info_card"]
    for source_type in chain:
        if source_type == "local_real" and buckets["real"]:
            index = cursors["real"] % len(buckets["real"])
            cursors["real"] += 1
            asset = buckets["real"][index]
            return source_type, asset, "使用本地真实素材"
        if source_type == "ai_generated" and not shot.get("required_real") and buckets["synthetic"]:
            index = cursors["synthetic"] % len(buckets["synthetic"])
            cursors["synthetic"] += 1
            asset = buckets["synthetic"][index]
            return source_type, asset, "使用已入库AI辅助镜头，并保持AI辅助标识"
        if source_type == "brand_card" and buckets["brand"]:
            index = cursors["brand"] % len(buckets["brand"])
            cursors["brand"] += 1
            asset = buckets["brand"][index]
            return source_type, asset, "使用品牌素材"
        if source_type == "info_card":
            return "info_card", None, "素材不足时使用知识信息卡，不伪造真实案例"
        # licensed_external requires a separately verified/licensed source adapter;
        # until such a source is mounted it is skipped rather than scraped blindly.
    return "info_card", None, "可用素材链耗尽，安全降级为知识信息卡"


def _technical_qc(ffmpeg, output, width, height):
    checks = {
        "file_exists": output.is_file(),
        "non_empty": output.is_file() and output.stat().st_size >= 10 * 1024,
        "decode_ok": False,
        "expected_dimensions": f"{width}x{height}",
    }
    if checks["non_empty"]:
        probe = _run([str(ffmpeg), "-v", "error", "-i", str(output), "-f", "null", "-"], timeout=180)
        checks["decode_ok"] = probe.returncode == 0
    checks["passed"] = bool(checks["file_exists"] and checks["non_empty"] and checks["decode_ok"])
    return checks


def _render_inner(video_id):
    data = content_factory._load()
    video = content_factory._by_id(data["videos"], video_id, "视频任务")
    if video.get("status") not in {"等待生产", "生产中"}:
        raise ValueError("当前视频状态不允许进入本地生产")
    plan = video.get("production_plan")
    if not isinstance(plan, dict) or not plan.get("storyboard"):
        raise ValueError("尚未收到ChatGPT结构化生产方案，不能进入执行层")

    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError("未找到视频合成组件，请重新安装最终版")
    worker = status()
    campaign = content_factory._by_id(data["campaigns"], video["campaign_id"], "增长任务")
    output_spec = plan.get("output") or {}
    width = int(output_spec.get("width") or 1080)
    height = int(output_spec.get("height") or 1920)
    fps = int(output_spec.get("fps") or 30)

    output_root = data_root() / "r8" / "video_output" / video["campaign_id"] / video_id
    output_root.mkdir(parents=True, exist_ok=True)
    segment_root = output_root / "segments"
    segment_root.mkdir(parents=True, exist_ok=True)
    output = output_root / "FINAL.mp4"
    concat_list = output_root / "concat.txt"

    content_factory.update_runtime_state(
        video_id, status="生产中", bottleneck="正在执行ChatGPT分镜",
        auto_action="本地执行器正在逐镜头路由素材并渲染",
    )

    buckets = _asset_buckets(video, data)
    cursors = {"real": 0, "synthetic": 0, "brand": 0}
    source_summary = []
    segment_paths = []
    shot_states = []

    intro = output_root / "intro.png"
    _card(intro, plan.get("cover", {}).get("title") or campaign["title"],
          plan.get("cover", {}).get("subtitle") or f"{campaign['region']} · {campaign['service']}",
          "#2865df", footnote="ChatGPT策划 · 本地执行 · 最终人工审核")
    intro_segment = segment_root / "000_intro.mp4"
    _render_segment(ffmpeg, intro, intro_segment, 2, width, height, fps, worker)
    segment_paths.append(intro_segment)

    for index, raw_shot in enumerate(plan.get("storyboard") or [], 1):
        shot = dict(raw_shot)
        source_type, asset, route_note = _route_shot(shot, buckets, cursors)
        duration = max(1, min(float(shot.get("duration_seconds") or 3), 15))
        source_path = None
        disclosure = str(shot.get("synthetic_disclosure") or "").strip()
        if asset:
            source_path = Path(asset["local_path"])
            if source_type == "ai_generated" and not disclosure:
                disclosure = "AI辅助示意"
        if source_path is None:
            source_path = output_root / f"shot_{index:02d}.png"
            subtitle = shot.get("subtitle") or shot.get("narration") or route_note
            if shot.get("required_real"):
                subtitle = (subtitle + "\n\n真实操作素材暂缺，本镜头仅作知识说明，不模拟真实维修现场。").strip()
            elif "ai_generated" in (shot.get("source_preference") or []):
                subtitle = (subtitle + "\n\n当前本地AI生成镜头未就绪，已自动降级为信息画面。").strip()
            _card(source_path, shot.get("purpose") or plan.get("topic") or campaign["title"], subtitle,
                  "#7357c7" if shot.get("required_real") else "#2865df",
                  badge="卡嘴子 · 内容说明",
                  footnote="真实素材不足时自动降级 · 不伪造真实案例")
            source_type = "info_card"
            disclosure = "信息卡"
        segment = segment_root / f"{index:03d}_{shot.get('shot_id') or 'shot'}.mp4"
        _render_segment(ffmpeg, source_path, segment, duration, width, height, fps, worker)
        segment_paths.append(segment)
        shot.update({
            "status": "完成",
            "selected_source": source_type,
            "selected_asset_id": asset.get("id") if asset else None,
            "attempts": int(shot.get("attempts") or 0) + 1,
            "last_error": None,
            "route_note": route_note,
        })
        shot_states.append(shot)
        source_summary.append({
            "shot_id": shot.get("shot_id"), "source": source_type,
            "asset_id": asset.get("id") if asset else None,
            "disclosure": disclosure, "note": route_note,
        })
        content_factory.update_runtime_state(
            video_id, status="生产中",
            bottleneck=f"正在处理镜头 {index}/{len(plan.get('storyboard') or [])}",
            auto_action=route_note, shot_tasks=shot_states + list((plan.get("storyboard") or [])[index:]),
        )

    outro = output_root / "outro.png"
    _card(outro, "有需要，先提交问题", plan.get("cta") or video.get("cta"), "#13845c",
          footnote="卡嘴子本地服务 · 审核通过后再发布")
    outro_segment = segment_root / "999_outro.mp4"
    _render_segment(ffmpeg, outro, outro_segment, 3, width, height, fps, worker)
    segment_paths.append(outro_segment)

    concat_list.write_text("\n".join(f"file '{p.resolve().as_posix()}'" for p in segment_paths), encoding="utf-8")
    content_factory.update_runtime_state(
        video_id, status="生产中", bottleneck="正在合成FINAL.MP4",
        auto_action=f"FFmpeg正在拼接{len(segment_paths)}个标准化镜头", shot_tasks=shot_states,
    )
    concat_result = _run([
        str(ffmpeg), "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0",
        "-i", str(concat_list), "-c", "copy", "-movflags", "+faststart", str(output),
    ], timeout=600)
    if concat_result.returncode != 0 or not output.is_file() or output.stat().st_size < 1024:
        error = concat_result.stderr.decode("utf-8", "replace")[-1200:]
        raise RuntimeError(f"整片合成失败：{error or '未生成有效FINAL.MP4'}")

    content_factory.update_runtime_state(
        video_id, status="技术质检", bottleneck="正在进行成片技术质检",
        auto_action="检查文件存在、大小与完整解码",
    )
    qc = _technical_qc(ffmpeg, output, width, height)
    if not qc["passed"]:
        raise RuntimeError("FINAL.MP4技术质检未通过")

    candidate = content_factory.record_candidate({
        "video_id": video_id,
        "local_path": str(output),
        "duration_seconds": sum(float(x.get("duration_seconds") or 0) for x in shot_states) + 5,
        "quality_notes": (
            f"按ChatGPT生产合同V{video.get('plan_version') or 1}逐镜头执行；"
            f"{width}×{height}；{worker.get('encoder')}；本地素材为可选增强，缺失镜头已安全降级。"
        ),
        "technical_qc": qc,
        "source_summary": source_summary,
        "ai_score": None,
    })
    return {"status": "awaiting_owner_review", "candidate": candidate, "worker": worker, "output": str(output)}


def _mark_failure(video_id, error):
    updated = content_factory.update_runtime_state(
        video_id, status="异常待处理", bottleneck=str(error)[:300],
        auto_action="本地执行器正在判断是否自动重试", last_error=str(error)[:1000], retry_increment=True,
    )
    retries = int(updated.get("retry_count") or 0)
    if retries < 3:
        return content_factory.update_runtime_state(
            video_id, status="等待生产", bottleneck=str(error)[:300],
            auto_action=f"已进入自动重试队列（{retries}/3），无需人工处理", last_error=str(error)[:1000],
        )
    return content_factory.update_runtime_state(
        video_id, status="异常待处理", bottleneck=str(error)[:300],
        auto_action="连续3次失败，暂停自动重试并在总控台提示人工检查", last_error=str(error)[:1000],
    )


def render(video_id):
    video_id = str(video_id or "").strip()
    if not video_id:
        raise ValueError("视频ID不能为空")
    if not _WORKER_LOCK.acquire(blocking=False):
        raise RuntimeError("RTX 3060当前正在处理另一条视频，本任务会继续排队")
    try:
        return _render_inner(video_id)
    except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as error:
        _mark_failure(video_id, error)
        raise
    finally:
        _WORKER_LOCK.release()


def run_pending(limit=1):
    """Process queued production plans automatically, one GPU-heavy job at a time."""
    if _WORKER_LOCK.locked():
        return {"processed": 0, "busy": True}
    data = content_factory._load()
    queued = [x for x in data.get("videos", []) if x.get("status") == "等待生产" and isinstance(x.get("production_plan"), dict)]
    processed = []
    for video in queued[:max(1, int(limit or 1))]:
        try:
            result = render(video["id"])
            processed.append({"video_id": video["id"], "status": result.get("status")})
        except (ValueError, RuntimeError, OSError, subprocess.SubprocessError) as error:
            processed.append({"video_id": video["id"], "status": "failed", "error": str(error)[:300]})
    return {"processed": len(processed), "busy": _WORKER_LOCK.locked(), "items": processed}
