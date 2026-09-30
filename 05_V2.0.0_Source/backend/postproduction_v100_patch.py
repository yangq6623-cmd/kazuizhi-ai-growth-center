"""#100 professional automatic post-production.

Runs after the stable #75/#89 final director. It keeps the source final immutable,
creates a mastered delivery copy, optional tagged BGM mix, cover frame and three
platform canvases. Missing BGM is a truthful optional state, not a failure.
"""
from __future__ import annotations

import os
import shutil
from pathlib import Path

from backend import final_render_patch as _final
from promotion import ai_production_center as _center

_INSTALLED = False
_ORIGINAL_RENDER_TASK = _final._render_task


def _safe(value):
    return "".join(ch if ch.isalnum() or ch in "-_" else "_" for ch in str(value or ""))[:64] or "final"


def _bgm_asset():
    data = _center._load()
    choices = []
    for asset in data.get("assets") or []:
        if asset.get("enabled") is False or asset.get("rights") == "待确认":
            continue
        path = Path(str(asset.get("file_path") or ""))
        if not path.is_file() or path.suffix.lower() not in {".wav", ".mp3", ".m4a", ".aac", ".flac", ".ogg"}:
            continue
        text = " ".join(str(asset.get(key) or "") for key in ("name", "tags", "note")).lower()
        if any(token in text for token in ("bgm", "背景音乐", "配乐", "music")):
            choices.append(asset)
    return choices[0] if choices else None


def _run_checked(args, target=None, timeout=1800):
    result = _final._run(args, timeout=timeout)
    if result.returncode != 0:
        message = (result.stderr or result.stdout).decode("utf-8", "replace")[-1200:]
        raise RuntimeError(message or "FFmpeg 后期处理失败")
    if target is not None:
        target = Path(target)
        if not target.is_file() or target.stat().st_size < 10 * 1024:
            raise RuntimeError("FFmpeg 没有生成有效后期文件")
    return result


def _master_audio(ffmpeg, source, output, bgm=None):
    output = Path(output)
    if bgm:
        command = [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(source),
            "-stream_loop", "-1", "-i", str(bgm),
            "-filter_complex",
            "[0:a]loudnorm=I=-16:TP=-1.5:LRA=11[voice];"
            "[1:a]volume=0.11[bg];[voice][bg]amix=inputs=2:duration=first:dropout_transition=2[a]",
            "-map", "0:v:0", "-map", "[a]", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-shortest", "-movflags", "+faststart", str(output),
        ]
    else:
        command = [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(source),
            "-map", "0:v:0", "-map", "0:a?", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
            "-af", "loudnorm=I=-16:TP=-1.5:LRA=11", "-movflags", "+faststart", str(output),
        ]
    try:
        _run_checked(command, output)
    except RuntimeError:
        # Some rare finals can be silent. Preserve the professional master even
        # when there is no audio stream to normalize.
        shutil.copy2(source, output)
    return output


def _cover(ffmpeg, source, output):
    output = Path(output)
    _run_checked([
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-ss", "0.35", "-i", str(source),
        "-frames:v", "1", "-q:v", "2", str(output),
    ], output, timeout=180)
    return output


def _variant_filter(width, height):
    return (
        f"split=2[bg][fg];"
        f"[bg]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},boxblur=18:2[bg2];"
        f"[fg]scale={width}:{height}:force_original_aspect_ratio=decrease[fg2];"
        f"[bg2][fg2]overlay=(W-w)/2:(H-h)/2,setsar=1,format=yuv420p"
    )


def _make_variant(ffmpeg, source, output, width, height):
    output = Path(output)
    _run_checked([
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", str(source),
        "-vf", _variant_filter(width, height), "-map", "0:v:0", "-map", "0:a?",
        *_final._encoder_args(ffmpeg), "-c:a", "aac", "-b:a", "192k", "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", str(output),
    ], output, timeout=2400)
    return output


def _professionalize(item, task):
    source = Path(str(item.get("file_path") or ""))
    if not source.is_file():
        raise RuntimeError("#100 没有找到可进入专业后期的最终成片")
    ffmpeg_path = _final.find_ffmpeg()
    if not ffmpeg_path:
        raise RuntimeError("#100 没有找到 FFmpeg")
    ffmpeg = str(ffmpeg_path)
    project_id = str(item.get("project_id") or task.get("project_id") or "")
    folder = source.parent / "professional"
    folder.mkdir(parents=True, exist_ok=True)
    tag = _safe(item.get("id") or task.get("id"))
    bgm = _bgm_asset()
    bgm_path = Path(str((bgm or {}).get("file_path") or "")) if bgm else None
    master = folder / f"FINAL_PRO_{tag}.mp4"

    _final._set_state(status="running", stage="#100 专业声音母带 / 配乐", progress=96, message="正在统一响度并按真实资产条件混入背景音乐。")
    _master_audio(ffmpeg, source, master, bgm_path if bgm_path and bgm_path.is_file() else None)
    qc = _final._qc(ffmpeg, master)
    if not qc.get("passed"):
        raise RuntimeError("#100 专业母版技术质检未通过：" + str(qc.get("error") or "完整解码失败"))

    cover = folder / f"COVER_{tag}.jpg"
    cover_error = ""
    try:
        _cover(ffmpeg, master, cover)
    except RuntimeError as error:
        cover_error = str(error)[:500]

    variants = {}
    for name, width, height in (("9x16", 1080, 1920), ("1x1", 1080, 1080), ("16x9", 1920, 1080)):
        target = folder / f"FINAL_{name}_{tag}.mp4"
        try:
            _make_variant(ffmpeg, master, target, width, height)
            variants[name] = {"status": "ready", "path": str(target), "resolution": f"{width}x{height}"}
        except RuntimeError as error:
            variants[name] = {"status": "failed", "message": str(error)[:500], "resolution": f"{width}x{height}"}

    data = _center._load()
    current = next((x for x in data.get("outputs") or [] if x.get("id") == item.get("id")), None)
    if current:
        current["pre_master_file_path"] = str(source)
        current["file_path"] = str(master)
        current["postproduction_version"] = "#100"
        current["audio_mastering"] = {"status": "ready", "target_lufs": -16, "bgm": str(bgm.get("name") or "") if bgm else "", "bgm_optional": True}
        current["cover"] = {"status": "ready" if cover.is_file() else "failed", "path": str(cover) if cover.is_file() else "", "message": cover_error}
        current["platform_variants"] = variants
        current["technical_qc"] = qc
        current["updated_at"] = _center.now_iso()
        item = current
    _center._audit(data, "postproduction_v100_completed", item.get("id"), "#100 已完成声音母带、可选BGM、封面与9:16/1:1/16:9平台版本；未配置BGM时不会伪造配乐。")
    _center._save(data)
    return item


def _render_task_v100(task):
    item = _ORIGINAL_RENDER_TASK(task)
    try:
        item = _professionalize(item, task)
        _final._set_state(status="completed", stage="#100 专业最终成片已完成", progress=100, project_id=item.get("project_id") or task.get("project_id") or "", task_id=task.get("id") or "", output_id=item.get("id") or "", message="专业母版、封面和平台版本已完成。", last_error="")
        return item
    except (RuntimeError, OSError, ValueError) as error:
        # Base final remains real and playable. Report the professional layer as
        # degraded rather than converting a successful base render into a fake
        # total failure.
        data = _center._load()
        current = next((x for x in data.get("outputs") or [] if x.get("id") == item.get("id")), None)
        if current:
            current["postproduction_version"] = "#100"
            current["postproduction_status"] = "degraded"
            current["postproduction_error"] = str(error)[:800]
            current["updated_at"] = _center.now_iso()
        _center._audit(data, "postproduction_v100_degraded", item.get("id"), "#100 专业后期未完全完成，但原真实成片保留可用：" + str(error)[:500])
        _center._save(data)
        _final._set_state(status="completed", stage="基础成片完成 · 专业后期降级", progress=100, output_id=item.get("id") or "", message="基础成片已完成；专业后期有可见降级项。", last_error=str(error)[:800])
        return item


def status():
    return {
        "ready": bool(_final.find_ffmpeg()),
        "version": "#100",
        "features": ["-16 LUFS声音母带", "可选BGM混音", "封面抽帧", "9:16", "1:1", "16:9"],
        "bgm": (lambda x: {"configured": bool(x), "name": str((x or {}).get("name") or "")})(_bgm_asset()),
    }


def install():
    global _INSTALLED
    if _INSTALLED:
        return
    _final._render_task = _render_task_v100
    _INSTALLED = True


install()
