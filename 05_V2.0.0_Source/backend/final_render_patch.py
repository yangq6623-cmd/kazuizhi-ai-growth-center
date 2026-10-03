"""R8-18 #71: automatic final-cut executor for the AI Content Production Center.

Consumes already generated/selected #70 shot candidates, standardizes every shot
to a truthful 1080-class delivery frame at 30 fps, adds local TTS/subtitles when
available, performs FFmpeg technical QC, persists FINAL.mp4, and exposes it to
the localhost production UI. Existing #70 candidate files are never regenerated.
"""
from __future__ import annotations

import json
import mimetypes
import os
import shutil
import subprocess
import threading
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from backend import server
from backend import production_runtime_monitor_patch as _monitor
from core.storage import data_root
from promotion import ai_production_center as _center
from promotion import speech_pipeline
from promotion.video_worker import find_ffmpeg

_FINAL_LOCK = threading.Lock()
_FINAL_THREAD = None
_FILTER_CACHE = {}
_FINAL_STATE = {
    "status": "idle",
    "stage": "等待成片任务",
    "progress": 0,
    "project_id": "",
    "task_id": "",
    "output_id": "",
    "message": "等待老板确认镜头或等待历史成片任务恢复。",
    "last_error": "",
    "updated_at": "",
}


def _now():
    return _center.now_iso()


def _set_state(**patch):
    with _FINAL_LOCK:
        _FINAL_STATE.update(patch)
        _FINAL_STATE["updated_at"] = _now()


def _snapshot():
    with _FINAL_LOCK:
        value = dict(_FINAL_STATE)
    value["busy"] = bool(_FINAL_THREAD is not None and _FINAL_THREAD.is_alive())
    value["output"] = _latest_final_output(value.get("project_id") or None)
    if value["output"] and value.get("status") == "idle" and not value["busy"]:
        value.update({
            "status": "completed",
            "stage": "最终成片已完成",
            "progress": 100,
            "project_id": value["output"].get("project_id") or "",
            "output_id": value["output"].get("id") or "",
            "message": "已读取最近一次真实最终成片。",
        })
    return value


def _run(args, timeout=600):
    flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.run(
        [str(x) for x in args],
        capture_output=True,
        timeout=timeout,
        check=False,
        creationflags=flags,
    )


def _final_root():
    preferred_base = Path(r"F:\KazuizhiAI")
    if os.name == "nt" and preferred_base.exists():
        return preferred_base / "Outputs" / "FinalVideos"
    return data_root() / "r8" / "final_videos"


def _ratio_dimensions(ratio):
    value = str(ratio or "9:16").replace(" ", "")
    if value in {"16:9", "16/9"}:
        return 1920, 1080
    if value in {"1:1", "1/1"}:
        return 1080, 1080
    return 1080, 1920


def _encoder_args(ffmpeg):
    cache_key = ("encoder", str(ffmpeg))
    cached = _FILTER_CACHE.get(cache_key)
    if cached:
        return list(cached)
    result = _run([ffmpeg, "-hide_banner", "-encoders"], timeout=30)
    listing = (result.stdout + result.stderr).decode("utf-8", "replace")
    if "h264_nvenc" in listing:
        args = ["-c:v", "h264_nvenc", "-preset", "p5", "-cq", "19", "-b:v", "0"]
    else:
        args = ["-c:v", "libx264", "-preset", "medium", "-crf", "18"]
    _FILTER_CACHE[cache_key] = tuple(args)
    return args


def _has_filter(ffmpeg, name):
    cache_key = ("filter", str(ffmpeg), str(name))
    if cache_key in _FILTER_CACHE:
        return bool(_FILTER_CACHE[cache_key])
    result = _run([ffmpeg, "-hide_banner", "-filters"], timeout=30)
    listing = (result.stdout + result.stderr).decode("utf-8", "replace")
    found = str(name) in listing
    _FILTER_CACHE[cache_key] = found
    return found


def _valid_video_output(item):
    path = Path(str(item.get("file_path") or ""))
    return (
        item.get("kind") == "镜头候选视频"
        and path.is_file()
        and path.suffix.lower() in {".mp4", ".webm", ".mov", ".mkv", ".m4v"}
        and path.stat().st_size > 10 * 1024
    )


def _candidate_score(item):
    path = Path(str(item.get("file_path") or ""))
    try:
        size = path.stat().st_size
    except OSError:
        size = 0
    try:
        index = int(item.get("candidate_index") or 0)
    except (TypeError, ValueError):
        index = 0
    return (1 if _valid_video_output(item) else 0, size, -index)


def _selected_plan(project_id, persist_auto=True):
    data = _center._load()
    project = _center._find(data.get("projects") or [], project_id, "项目")
    shots = sorted(
        [x for x in data.get("storyboards") or [] if x.get("project_id") == project_id],
        key=lambda x: int(x.get("order") or 0),
    )
    if not shots:
        raise RuntimeError("当前项目没有正式镜头")
    selected = []
    changed = False
    for shot in shots:
        candidates = [
            x for x in data.get("outputs") or []
            if x.get("project_id") == project_id
            and x.get("shot_id") == shot.get("id")
            and _valid_video_output(x)
        ]
        manual = [
            x for x in candidates
            if x.get("selected") is True or str(x.get("status") or "") in {"已采用", "已确认"}
        ]
        if manual:
            chosen = max(manual, key=_candidate_score)
            mode = "老板已采用"
        elif candidates:
            chosen = max(candidates, key=_candidate_score)
            mode = "自动选片"
            if persist_auto:
                for item in data.get("outputs") or []:
                    if item.get("shot_id") == shot.get("id"):
                        item["selected"] = item.get("id") == chosen.get("id")
                        if item.get("selected"):
                            item["status"] = "自动采用"
                            item["auto_selected_at"] = _now()
                shot["status"] = "候选已确认"
                changed = True
        else:
            raise RuntimeError(f"镜头 {shot.get('order')} 没有可用的真实候选视频文件")
        selected.append({"shot": shot, "output": chosen, "selection_mode": mode})
    if changed:
        _center._audit(data, "final_auto_selection", project_id, "未手动选择的镜头已按真实文件完整性自动选片；人工选择优先且不会被覆盖。")
        _center._save(data)
    return project, selected


def _task_update(task_id, *, status=None, progress=None, detail=None, project_status=None):
    data = _center._load()
    task = next((x for x in data.get("tasks") or [] if x.get("id") == task_id), None)
    if task:
        if status is not None:
            task["status"] = status
        if progress is not None:
            task["progress"] = max(0, min(100, int(progress)))
        if detail is not None:
            task["detail"] = str(detail)[:1200]
        task["updated_at"] = _now()
        project_id = task.get("project_id")
        if project_status and project_id:
            for project in data.get("projects") or []:
                if project.get("id") == project_id:
                    project["status"] = project_status
                    project["updated_at"] = _now()
                    break
        _center._save(data)
    return task


def _subtitle_stamp(seconds):
    milliseconds = max(0, int(round(float(seconds) * 1000)))
    hours, rest = divmod(milliseconds, 3600000)
    minutes, rest = divmod(rest, 60000)
    secs, ms = divmod(rest, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def _write_srt(selected, path):
    current = 0.0
    blocks = []
    index = 1
    for entry in selected:
        shot = entry["shot"]
        duration = max(1.0, min(float(shot.get("duration_seconds") or 4), 12.0))
        text = str(shot.get("narration") or shot.get("purpose") or "").strip()
        if text:
            blocks.append(
                f"{index}\n{_subtitle_stamp(current)} --> {_subtitle_stamp(current + duration)}\n{text}\n"
            )
            index += 1
        current += duration
    Path(path).write_text("\n".join(blocks), encoding="utf-8")
    return current


def _narration(selected):
    return "。".join(
        str(entry["shot"].get("narration") or "").strip()
        for entry in selected
        if str(entry["shot"].get("narration") or "").strip()
    )


def _vf_complex(width, height, fps, interpolate=True):
    cadence = (
        f"minterpolate=fps={fps}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1"
        if interpolate else f"fps={fps}"
    )
    return (
        f"[0:v]{cadence}[base];"
        f"[base]split=2[bg][fg];"
        f"[bg]scale={width}:{height}:force_original_aspect_ratio=increase,"
        f"crop={width}:{height},boxblur=20:2[bg2];"
        f"[fg]scale={width}:{height}:force_original_aspect_ratio=decrease[fg2];"
        f"[bg2][fg2]overlay=(W-w)/2:(H-h)/2,"
        f"unsharp=5:5:0.35:5:5:0.0,setsar=1,format=yuv420p[v]"
    )


def _render_shot(ffmpeg, source, target, duration, width, height, fps):
    encoder = _encoder_args(ffmpeg)
    interpolate = _has_filter(ffmpeg, "minterpolate")
    command = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-stream_loop", "-1", "-i", source,
        "-t", f"{duration:.3f}",
        "-filter_complex", _vf_complex(width, height, fps, interpolate),
        "-map", "[v]", "-an",
        *encoder, "-pix_fmt", "yuv420p", "-movflags", "+faststart", target,
    ]
    result = _run(command, timeout=max(600, int(duration * 90)))
    if result.returncode != 0 and interpolate:
        fallback = [
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-stream_loop", "-1", "-i", source,
            "-t", f"{duration:.3f}",
            "-filter_complex", _vf_complex(width, height, fps, False),
            "-map", "[v]", "-an",
            *encoder, "-pix_fmt", "yuv420p", "-movflags", "+faststart", target,
        ]
        result = _run(fallback, timeout=max(600, int(duration * 60)))
    target = Path(target)
    if result.returncode != 0 or not target.is_file() or target.stat().st_size < 10 * 1024:
        error = (result.stderr or result.stdout).decode("utf-8", "replace")[-1200:]
        raise RuntimeError(f"镜头1080P/30fps标准化失败：{error or '没有生成有效镜头'}")


def _concat(ffmpeg, segments, output):
    list_path = Path(output).with_name("concat.txt")
    list_path.write_text(
        "\n".join(f"file '{Path(x).resolve().as_posix()}'" for x in segments),
        encoding="utf-8",
    )
    result = _run([
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-f", "concat", "-safe", "0", "-i", list_path,
        "-c", "copy", "-movflags", "+faststart", output,
    ], timeout=900)
    output = Path(output)
    if result.returncode != 0 or not output.is_file() or output.stat().st_size < 50 * 1024:
        error = (result.stderr or result.stdout).decode("utf-8", "replace")[-1200:]
        raise RuntimeError(f"FFmpeg整片拼接失败：{error or '没有生成有效成片'}")


def _burn_subtitles_hq(ffmpeg, video, srt):
    srt = Path(srt)
    if not srt.is_file() or srt.stat().st_size == 0 or not _has_filter(ffmpeg, "subtitles"):
        return {"status": "sidecar_only", "path": str(srt), "message": "保留SRT旁挂字幕"}
    video = Path(video)
    temp = video.with_name("FINAL.subtitles.tmp.mp4")
    escaped = srt.resolve().as_posix().replace(":", r"\:").replace("'", r"\'")
    vf = f"subtitles='{escaped}'"
    result = _run([
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-i", video, "-vf", vf, "-an",
        *_encoder_args(ffmpeg), "-pix_fmt", "yuv420p", "-movflags", "+faststart", temp,
    ], timeout=1200)
    if result.returncode == 0 and temp.is_file() and temp.stat().st_size > 50 * 1024:
        os.replace(temp, video)
        return {"status": "burned", "path": str(srt), "message": "字幕已烧录进最终成片"}
    try:
        temp.unlink(missing_ok=True)
    except OSError:
        pass
    message = (result.stderr or result.stdout).decode("utf-8", "replace")[-600:]
    return {"status": "sidecar_only", "path": str(srt), "message": message or "字幕烧录不可用，保留SRT"}


def _mux_voice(ffmpeg, video, wav):
    video = Path(video)
    wav = Path(wav)
    temp = video.with_name("FINAL.audio.tmp.mp4")
    result = _run([
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-i", video, "-i", wav,
        "-filter_complex", "[1:a]dynaudnorm,apad[a]",
        "-map", "0:v:0", "-map", "[a]",
        "-c:v", "copy", "-c:a", "aac", "-b:a", "160k",
        "-shortest", "-movflags", "+faststart", temp,
    ], timeout=600)
    if result.returncode == 0 and temp.is_file() and temp.stat().st_size > 50 * 1024:
        os.replace(temp, video)
        return {"status": "ready", "path": str(wav), "message": "本地配音已封装进最终成片"}
    try:
        temp.unlink(missing_ok=True)
    except OSError:
        pass
    message = (result.stderr or result.stdout).decode("utf-8", "replace")[-600:]
    return {"status": "failed", "path": str(wav), "message": message or "配音封装失败"}


def _qc(ffmpeg, output):
    output = Path(output)
    checks = {
        "file_exists": output.is_file(),
        "non_empty": output.is_file() and output.stat().st_size >= 100 * 1024,
        "decode_ok": False,
    }
    if checks["non_empty"]:
        probe = _run([ffmpeg, "-v", "error", "-i", output, "-f", "null", "-"], timeout=600)
        checks["decode_ok"] = probe.returncode == 0
        if probe.returncode != 0:
            checks["error"] = (probe.stderr or probe.stdout).decode("utf-8", "replace")[-800:]
    checks["passed"] = bool(checks["file_exists"] and checks["non_empty"] and checks["decode_ok"])
    return checks


def _latest_final_output(project_id=None):
    data = _center._load()
    finals = [
        x for x in data.get("outputs") or []
        if x.get("kind") == "最终成片"
        and (not project_id or x.get("project_id") == project_id)
        and Path(str(x.get("file_path") or "")).is_file()
    ]
    finals.sort(key=lambda x: str(x.get("created_at") or ""), reverse=True)
    return finals[0] if finals else None


def _register_final(task, project, selected, output, srt, tts, subtitle, qc, width, height, fps):
    data = _center._load()
    existing = next(
        (
            x for x in data.get("outputs") or []
            if x.get("kind") == "最终成片"
            and x.get("final_task_id") == task.get("id")
            and Path(str(x.get("file_path") or "")).is_file()
        ),
        None,
    )
    if existing:
        return existing
    output_id = _center._id("FINAL")
    file_url = f"/api/final-output/file?id={output_id}"
    item = {
        "id": output_id,
        "project_id": project.get("id"),
        "kind": "最终成片",
        "status": "成片已完成",
        "created_at": _now(),
        "source": "FFmpeg #71 自动成片",
        "file_path": str(Path(output)),
        "file_url": file_url,
        "url": file_url,
        "download_url": f"/api/final-output/download?id={output_id}",
        "subtitle_path": str(Path(srt)),
        "tts": tts,
        "subtitle": subtitle,
        "technical_qc": qc,
        "resolution": f"{width}x{height}",
        "fps": fps,
        "final_task_id": task.get("id"),
        "selected_shots": [
            {
                "shot_id": entry["shot"].get("id"),
                "order": entry["shot"].get("order"),
                "candidate_id": entry["output"].get("id"),
                "selection_mode": entry["selection_mode"],
            }
            for entry in selected
        ],
    }
    data.setdefault("outputs", []).append(item)
    for current in data.get("tasks") or []:
        if current.get("id") == task.get("id"):
            current.update({
                "status": "已完成",
                "progress": 100,
                "detail": f"真实最终成片已生成：{width}×{height} / {fps}fps；可在内容生产中心直接播放、保存或打开文件位置。",
                "output_id": output_id,
                "updated_at": _now(),
            })
            break
    for current in data.get("projects") or []:
        if current.get("id") == project.get("id"):
            current["status"] = "最终成片已完成"
            current["final_output_id"] = output_id
            current["final_output_url"] = file_url
            current["updated_at"] = _now()
            break
    _center._audit(data, "final_video_completed", output_id, f"#71 已生成真实最终成片 {width}x{height} {fps}fps。")
    _center._save(data)
    return item


def _render_task(task):
    project_id = str(task.get("project_id") or "")
    task_id = str(task.get("id") or "")
    ffmpeg_path = find_ffmpeg()
    if not ffmpeg_path:
        raise RuntimeError("没有找到 FFmpeg，无法进入最终成片")
    ffmpeg = str(ffmpeg_path)
    project, selected = _selected_plan(project_id, persist_auto=True)
    width, height = _ratio_dimensions(project.get("ratio"))
    fps = 30

    existing = next(
        (
            x for x in _center._load().get("outputs") or []
            if x.get("kind") == "最终成片"
            and x.get("final_task_id") == task_id
            and Path(str(x.get("file_path") or "")).is_file()
        ),
        None,
    )
    if existing:
        _task_update(task_id, status="已完成", progress=100, detail="检测到已完成的真实成片文件，直接恢复。", project_status="最终成片已完成")
        _set_state(status="completed", stage="最终成片已完成", progress=100, output_id=existing.get("id"), message="已恢复历史最终成片。", last_error="")
        return existing

    output_root = _final_root() / project_id
    segments_root = output_root / "segments"
    segments_root.mkdir(parents=True, exist_ok=True)
    output = output_root / "FINAL_1080P_30FPS.mp4"
    srt = output_root / "FINAL.srt"
    wav = output_root / "narration.wav"

    _set_state(status="running", stage="镜头检查 / 自动选片", progress=5, project_id=project_id, task_id=task_id, message=f"已确认 {len(selected)} 个正式镜头；人工选择优先。", last_error="")
    _task_update(task_id, status="AI自动选片", progress=5, detail=f"已读取 {len(selected)} 个正式镜头。已采用的老板选择不会被覆盖；未选镜头才自动选择真实可播放候选。", project_status="最终成片处理中")

    segment_paths = []
    total = max(1, len(selected))
    for index, entry in enumerate(selected, 1):
        shot = entry["shot"]
        source = Path(str(entry["output"].get("file_path") or ""))
        duration = max(1.0, min(float(shot.get("duration_seconds") or 4), 12.0))
        target = segments_root / f"{index:03d}_shot_{int(shot.get('order') or index):02d}.mp4"
        progress = 10 + int((index - 1) / total * 48)
        _set_state(status="running", stage="1080P / 30fps 清晰化", progress=progress, message=f"正在处理正式镜头 {index}/{total}。")
        _task_update(task_id, status="1080P清晰化与补帧", progress=progress, detail=f"正在标准化镜头 {index}/{total}：1080P级输出、30fps；优先运动插帧，失败则安全回退标准帧率转换。")
        _render_shot(ffmpeg, source, target, duration, width, height, fps)
        segment_paths.append(target)

    _set_state(status="running", stage="FFmpeg 自动剪辑", progress=62, message=f"正在拼接 {len(segment_paths)} 个已确认镜头。")
    _task_update(task_id, status="FFmpeg自动剪辑", progress=62, detail=f"正在按导演顺序拼接 {len(segment_paths)} 个正式镜头。")
    _concat(ffmpeg, segment_paths, output)

    _write_srt(selected, srt)
    _set_state(status="running", stage="字幕", progress=72, message="正在生成时间轴字幕并尝试烧录。")
    _task_update(task_id, status="字幕生成", progress=72, detail="已按每个正式镜头时长生成SRT时间轴，正在尝试烧录中文字幕。")
    subtitle = _burn_subtitles_hq(ffmpeg, output, srt)

    _set_state(status="running", stage="本地配音", progress=82, message="正在生成本地旁白并封装到成片。")
    _task_update(task_id, status="本地配音", progress=82, detail="正在使用本机可用语音引擎生成旁白；配音不可用时保留无配音成片与字幕，不伪造成功。")
    narration = _narration(selected)
    tts = speech_pipeline._sapi_tts(narration, wav)
    if tts.get("status") == "ready":
        tts["mux"] = _mux_voice(ffmpeg, output, wav)
    else:
        tts["mux"] = {"status": "skipped", "message": "没有可封装的真实本地配音文件"}

    _set_state(status="running", stage="最终技术质检", progress=94, message="正在完整解码最终MP4。")
    _task_update(task_id, status="最终技术质检", progress=94, detail="正在检查最终MP4存在性、文件大小和完整解码。")
    qc = _qc(ffmpeg, output)
    if not qc.get("passed"):
        raise RuntimeError("最终MP4技术质检未通过：" + str(qc.get("error") or "完整解码失败"))

    item = _register_final(task, project, selected, output, srt, tts, subtitle, qc, width, height, fps)
    _set_state(status="completed", stage="最终成片已完成", progress=100, project_id=project_id, task_id=task_id, output_id=item.get("id"), message="最终视频已完成，可在平台直接观看和保存。", last_error="")
    return item


def _pending_final_tasks():
    data = _center._load()
    tasks = [
        x for x in data.get("tasks") or []
        if x.get("kind") == "完整成片合成"
        and str(x.get("status") or "") not in {"已完成", "完成", "取消", "已取消"}
    ]
    tasks.sort(key=lambda x: str(x.get("created_at") or ""))
    return tasks


def _worker():
    global _FINAL_THREAD
    try:
        while True:
            pending = _pending_final_tasks()
            if not pending:
                if _FINAL_STATE.get("status") != "completed":
                    _set_state(status="idle", stage="等待成片任务", progress=0, message="没有待执行的完整成片任务。")
                return
            task = pending[0]
            try:
                _render_task(task)
            except Exception as error:
                _task_update(
                    task.get("id"),
                    status="执行失败",
                    detail=f"#71 最终成片本轮失败：{error}。#70已生成候选文件不会删除或重跑。",
                    project_status="最终成片异常待处理",
                )
                _set_state(
                    status="error",
                    stage="最终成片失败",
                    progress=int(task.get("progress") or 0),
                    project_id=task.get("project_id") or "",
                    task_id=task.get("id") or "",
                    message="最终成片没有完成；已保留全部候选和已完成步骤。",
                    last_error=str(error),
                )
                return
    finally:
        with _FINAL_LOCK:
            _FINAL_THREAD = None


def _start_worker():
    global _FINAL_THREAD
    with _FINAL_LOCK:
        if _FINAL_THREAD is not None and _FINAL_THREAD.is_alive():
            return False
        _FINAL_THREAD = threading.Thread(target=_worker, name="kazuizhi-final-render-71", daemon=True)
        _FINAL_THREAD.start()
        return True


_ORIGINAL_FINAL_QUEUE = _monitor._queue_final_render


def _queue_final_and_start(payload):
    task = _ORIGINAL_FINAL_QUEUE(payload)
    _set_state(
        status="queued",
        stage="等待成片执行器",
        progress=0,
        project_id=task.get("project_id") or "",
        task_id=task.get("id") or "",
        output_id="",
        message="已建立真实成片任务，正在启动 #71 执行器。",
        last_error="",
    )
    _start_worker()
    return task


def _safe_final_output(output_id):
    data = _center._load()
    item = next(
        (x for x in data.get("outputs") or [] if x.get("id") == output_id and x.get("kind") == "最终成片"),
        None,
    )
    if not item:
        raise ValueError("没有找到最终成片")
    path = Path(str(item.get("file_path") or "")).resolve()
    root = _final_root().resolve()
    if not path.is_file() or root not in path.parents:
        raise ValueError("最终成片文件不存在或路径不允许访问")
    return item, path


def _stream(handler, path, *, download=False):
    size = path.stat().st_size
    start, end = 0, size - 1
    range_header = str(handler.headers.get("Range") or "")
    partial = False
    if range_header.startswith("bytes=") and not download:
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
    handler.send_header("Content-Type", mimetypes.guess_type(path.name)[0] or "video/mp4")
    handler.send_header("Accept-Ranges", "bytes")
    handler.send_header("Content-Length", str(length))
    if partial:
        handler.send_header("Content-Range", f"bytes {start}-{end}/{size}")
    if download:
        handler.send_header("Content-Disposition", 'attachment; filename="Kazuizhi_FINAL_1080P_30FPS.mp4"')
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


def _origin_ok(handler):
    origin = str(handler.headers.get("Origin") or "")
    return not origin or origin in {
        f"http://127.0.0.1:{handler.server.server_port}",
        f"http://localhost:{handler.server.server_port}",
    }


def _read_json(handler):
    length = int(handler.headers.get("Content-Length", "0") or 0)
    if length < 0 or length > 32 * 1024:
        raise ValueError("请求内容过大")
    return json.loads(handler.rfile.read(length) or b"{}") if length else {}


def _install_http():
    cls = server.DashboardHandler
    if getattr(cls, "_kz_final_render_71_patched", False):
        return
    original_get = cls.do_GET
    original_post = cls.do_POST

    def do_get(handler):
        path = urlsplit(handler.path).path
        if path == "/api/final-render/status":
            handler._json_ok({"ok": True, "executor": _snapshot()})
            return
        if path in {"/api/final-output/file", "/api/final-output/download"}:
            output_id = (parse_qs(urlsplit(handler.path).query).get("id") or [""])[0]
            try:
                _, file_path = _safe_final_output(output_id)
                _stream(handler, file_path, download=path.endswith("/download"))
            except (OSError, ValueError) as error:
                handler._json_error(404, error)
            return
        return original_get(handler)

    def do_post(handler):
        path = urlsplit(handler.path).path
        if path != "/api/final-output/open-folder":
            return original_post(handler)
        if not _origin_ok(handler):
            handler._json_error(403, "仅允许当前本机工作台操作")
            return
        try:
            payload = _read_json(handler)
            _, file_path = _safe_final_output(str(payload.get("id") or ""))
            if os.name == "nt":
                subprocess.Popen(["explorer.exe", "/select,", str(file_path)], creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
            else:
                raise RuntimeError("当前系统不支持直接打开文件位置")
            handler._json_ok({"ok": True, "path": str(file_path)})
        except (OSError, ValueError, RuntimeError) as error:
            handler._json_error(400, error)

    cls.do_GET = do_get
    cls.do_POST = do_post
    cls._kz_final_render_71_patched = True


if not getattr(_monitor, "_kz_final_queue_71_patched", False):
    _monitor._queue_final_render = _queue_final_and_start
    _monitor._kz_final_queue_71_patched = True

_install_http()

if _pending_final_tasks():
    _start_worker()
