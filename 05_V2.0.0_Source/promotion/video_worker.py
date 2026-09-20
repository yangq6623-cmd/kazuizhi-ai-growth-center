"""Local short-video compositor with RTX 3060/NVENC acceleration.

This worker creates a real MP4 from owner-provided local material.  It does
not claim that synthetic footage is a real service case.  The output is
registered as a review candidate and can never bypass the owner approval gate.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

from core.storage import data_root
from promotion import content_factory


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}
VIDEO_SUFFIXES = {".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v"}


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
    return {
        "status": "ready" if ready else "partial",
        "ffmpeg_found": bool(ffmpeg), "ffmpeg_path": str(ffmpeg or ""),
        "ffmpeg_version": version, "gpu": gpu, "nvenc": nvenc,
        "encoder": "h264_nvenc" if nvenc else "libx264",
        "message": "RTX 3060 视频合成与硬件编码已就绪" if ready else "视频合成可用性尚未完全通过体检",
        "generation_scope": "用真实素材自动剪辑、片头片尾、竖屏适配和硬件编码；生成式视频模型需单独下载模型权重后启用。",
    }


def _font():
    candidates = [
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "msyh.ttc",
        Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts" / "simhei.ttf",
    ]
    return next((x for x in candidates if x.is_file()), None)


def _card(path, title, subtitle, accent):
    try:
        from PIL import Image, ImageDraw, ImageFont
    except ImportError as error:
        raise RuntimeError("视频片头组件缺失，请重新安装最终版") from error
    width, height = 1080, 1920
    image = Image.new("RGB", (width, height), "#0d2445")
    draw = ImageDraw.Draw(image)
    for y in range(height):
        ratio = y / height
        draw.line((0, y, width, y), fill=(13 + int(20 * ratio), 36 + int(35 * ratio), 69 + int(70 * ratio)))
    draw.rounded_rectangle((82, 116, 998, 1740), radius=50, fill="#ffffff", outline=accent, width=8)
    draw.rounded_rectangle((142, 202, 938, 326), radius=25, fill=accent)
    font_path = _font()
    title_font = ImageFont.truetype(str(font_path), 72) if font_path else ImageFont.load_default()
    sub_font = ImageFont.truetype(str(font_path), 42) if font_path else ImageFont.load_default()
    small_font = ImageFont.truetype(str(font_path), 32) if font_path else ImageFont.load_default()
    draw.text((180, 222), "卡嘴子 · 淮安本地服务", font=sub_font, fill="white")
    def lines(text, size=12):
        text = str(text or "")
        return "\n".join(text[index:index + size] for index in range(0, len(text), size))
    draw.multiline_text((145, 560), lines(title, 11), font=title_font, fill="#13213a", spacing=26)
    draw.multiline_text((145, 1180), lines(subtitle, 18), font=sub_font, fill="#53627a", spacing=18)
    draw.text((145, 1590), "真实素材 · 人工审核后发布", font=small_font, fill=accent)
    image.save(path, "PNG")


def render(video_id):
    video_id = str(video_id or "").strip()
    data = content_factory._load()
    video = content_factory._by_id(data["videos"], video_id, "视频任务")
    if video.get("status") not in {"等待生产", "生产中", "退回修改"}:
        raise ValueError("当前视频状态不允许重新生产")
    assets = [item for item in data["assets"] if item.get("id") in video.get("asset_ids", []) and Path(item.get("local_path", "")).is_file()]
    if not assets:
        raise ValueError("没有可读取的本地素材")
    media = Path(assets[0]["local_path"])
    if media.suffix.lower() not in IMAGE_SUFFIXES | VIDEO_SUFFIXES:
        raise ValueError("首个素材格式暂不支持，请使用图片或常见视频格式")
    worker = status()
    ffmpeg = find_ffmpeg()
    if not ffmpeg:
        raise RuntimeError("未找到视频合成组件，请重新安装最终版")
    output_root = data_root() / "r8" / "video_output" / video["campaign_id"]
    output_root.mkdir(parents=True, exist_ok=True)
    intro = output_root / f"{video_id}_intro.png"
    outro = output_root / f"{video_id}_outro.png"
    output = output_root / f"{video_id}.mp4"
    campaign = content_factory._by_id(data["campaigns"], video["campaign_id"], "增长任务")
    _card(intro, campaign["title"], f"{campaign['region']} · {campaign['service']}", "#2865df")
    _card(outro, "有需要，先提交问题", video.get("cta") or "通过小程序提交需求，等待师傅报价", "#13845c")
    target = max(10, min(int(video.get("duration_target") or 18), 45))
    middle = max(5, target - 5)
    media_args = ["-loop", "1", "-i", str(media)] if media.suffix.lower() in IMAGE_SUFFIXES else ["-stream_loop", "-1", "-i", str(media)]
    filters = (
        f"[0:v]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps=30,trim=duration=2,setpts=PTS-STARTPTS[v0];"
        f"[1:v]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps=30,trim=duration={middle},setpts=PTS-STARTPTS[v1];"
        f"[2:v]scale=1080:1920:force_original_aspect_ratio=decrease,pad=1080:1920:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,fps=30,trim=duration=3,setpts=PTS-STARTPTS[v2];"
        "[v0][v1][v2]concat=n=3:v=1:a=0[outv]"
    )
    encoder = "h264_nvenc" if worker.get("status") == "ready" else "libx264"
    encode_args = ["-c:v", "h264_nvenc", "-preset", "p4", "-cq", "23", "-b:v", "0"] if encoder == "h264_nvenc" else ["-c:v", "libx264", "-preset", "medium", "-crf", "23"]
    command = [str(ffmpeg), "-y", "-hide_banner", "-loglevel", "error", "-loop", "1", "-i", str(intro), *media_args, "-loop", "1", "-i", str(outro), "-filter_complex", filters, "-map", "[outv]", "-an", *encode_args, "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output)]
    video["status"] = "生产中"
    content_factory._save(data)
    result = _run(command, timeout=600)
    if result.returncode != 0 or not output.is_file() or output.stat().st_size < 1024:
        data = content_factory._load()
        latest = content_factory._by_id(data["videos"], video_id, "视频任务")
        latest["status"] = "等待生产"
        content_factory._save(data)
        error = result.stderr.decode("utf-8", "replace")[-1200:]
        raise RuntimeError(f"视频合成失败：{error or '未生成有效成片'}")
    candidate = content_factory.record_candidate({
        "video_id": video_id, "local_path": str(output), "duration_seconds": target,
        "quality_notes": f"竖屏1080×1920；{encoder}编码；真实素材与品牌片头片尾自动合成",
        "ai_score": None,
    })
    return {"status": "awaiting_owner_review", "candidate": candidate, "worker": worker}
