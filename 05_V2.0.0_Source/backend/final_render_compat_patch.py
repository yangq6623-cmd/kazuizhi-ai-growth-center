"""#71.2 stability hotfix for Windows final-render delivery.

Fixes two production issues discovered during the first real 1080P delivery:
1) FFmpeg may advertise h264_nvenc while the installed NVIDIA driver cannot
   satisfy the required NVENC API. We probe a tiny real encode and fall back to
   high-quality libx264 when necessary.
2) A previously registered FINAL file can be opened by the browser while a
   retry is still trying to replace that same path during subtitle/audio muxing.
   Windows then raises WinError 5 (Access denied). Final outputs are now built in
   a private work directory and published to an immutable versioned filename
   only after subtitles/audio and full decode QC have finished.

Existing #70 candidates and owner-selected shots are never regenerated.
"""
from __future__ import annotations

import os
import shutil
import threading
import time
from pathlib import Path

from backend import final_render_patch as _final
from promotion import ai_production_center as _center
from promotion import speech_pipeline

_PROBE_LOCK = threading.Lock()
_PROBE_CACHE = {}
_ORIGINAL_QUEUE_FINAL = _final._monitor._queue_final_render


def _software_encoder_args():
    return ["-c:v", "libx264", "-preset", "medium", "-crf", "18"]


def _nvenc_probe(ffmpeg):
    key = str(ffmpeg)
    with _PROBE_LOCK:
        if key in _PROBE_CACHE:
            return _PROBE_CACHE[key]

    listing = _final._run([ffmpeg, "-hide_banner", "-encoders"], timeout=30)
    encoders = (listing.stdout + listing.stderr).decode("utf-8", "replace")
    if "h264_nvenc" not in encoders:
        result = {"ok": False, "reason": "FFmpeg未提供h264_nvenc"}
    else:
        probe = _final._run([
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-f", "lavfi", "-i", "color=c=black:s=64x64:r=1:d=0.2",
            "-frames:v", "1", "-c:v", "h264_nvenc", "-preset", "p5",
            "-f", "null", "-",
        ], timeout=45)
        text = (probe.stderr or probe.stdout).decode("utf-8", "replace")[-1200:]
        result = {
            "ok": probe.returncode == 0,
            "reason": "NVENC真实编码探测通过" if probe.returncode == 0 else (text or "NVENC真实编码探测失败"),
        }

    with _PROBE_LOCK:
        _PROBE_CACHE[key] = result
    return result


def _encoder_args(ffmpeg):
    cache_key = ("encoder", str(ffmpeg))
    cached = _final._FILTER_CACHE.get(cache_key)
    if cached:
        return list(cached)
    probe = _nvenc_probe(ffmpeg)
    if probe.get("ok"):
        args = ["-c:v", "h264_nvenc", "-preset", "p5", "-cq", "19", "-b:v", "0"]
        mode = "NVENC"
    else:
        args = _software_encoder_args()
        mode = "libx264"
    _final._FILTER_CACHE[cache_key] = tuple(args)
    _final._FILTER_CACHE[("encoder_mode", str(ffmpeg))] = mode
    _final._FILTER_CACHE[("encoder_probe", str(ffmpeg))] = probe
    return list(args)


def _active_final_task(project_id):
    data = _center._load()
    active = [
        task for task in data.get("tasks") or []
        if task.get("kind") == "完整成片合成"
        and task.get("project_id") == project_id
        and str(task.get("status") or "") not in {"已完成", "完成", "取消", "已取消"}
    ]
    active.sort(key=lambda x: str(x.get("created_at") or ""))
    return active[0] if active else None


def _queue_final_deduplicated(payload):
    project_id = str((payload or {}).get("project_id") or "").strip()
    if project_id:
        existing = _active_final_task(project_id)
        if existing:
            _final._set_state(
                status="queued",
                stage="继续现有成片任务",
                progress=int(existing.get("progress") or 0),
                project_id=project_id,
                task_id=existing.get("id") or "",
                output_id="",
                message="检测到同项目已有成片任务，继续原任务，不重复创建。",
                last_error="",
            )
            _final._start_worker()
            return existing
    return _ORIGINAL_QUEUE_FINAL(payload)


def _complete_duplicates(project_id, keep_task_id, output_id):
    data = _center._load()
    changed = False
    for task in data.get("tasks") or []:
        if task.get("kind") != "完整成片合成" or task.get("project_id") != project_id:
            continue
        if task.get("id") == keep_task_id:
            continue
        if str(task.get("status") or "") in {"已完成", "完成", "取消", "已取消"}:
            continue
        task.update({
            "status": "已完成",
            "progress": 100,
            "detail": "同项目已有通过技术质检的最终成片，本重复任务已自动收口，不重复渲染。",
            "output_id": output_id,
            "updated_at": _center.now_iso(),
        })
        changed = True
    if changed:
        _center._audit(data, "duplicate_final_tasks_closed", project_id, "最终成片成功后已自动关闭同项目重复成片任务。")
        _center._save(data)


def _safe_tag(task_id):
    value = "".join(ch for ch in str(task_id or "") if ch.isalnum())
    return (value[-10:] if value else str(int(time.time())))


def _render_task_versioned(task):
    project_id = str(task.get("project_id") or "")
    task_id = str(task.get("id") or "")
    ffmpeg_path = _final.find_ffmpeg()
    if not ffmpeg_path:
        raise RuntimeError("没有找到 FFmpeg，无法进入最终成片")
    ffmpeg = str(ffmpeg_path)
    project, selected = _final._selected_plan(project_id, persist_auto=True)
    width, height = _final._ratio_dimensions(project.get("ratio"))
    fps = 30

    existing = next(
        (
            x for x in _center._load().get("outputs") or []
            if x.get("kind") == "最终成片"
            and x.get("final_task_id") == task_id
            and Path(str(x.get("file_path") or "")).is_file()
            and bool((x.get("technical_qc") or {}).get("passed"))
        ),
        None,
    )
    if existing:
        _final._task_update(task_id, status="已完成", progress=100, detail="检测到该任务已有通过质检的真实成片，直接恢复。", project_status="最终成片已完成")
        _complete_duplicates(project_id, task_id, existing.get("id"))
        _final._set_state(status="completed", stage="最终成片已完成", progress=100, project_id=project_id, task_id=task_id, output_id=existing.get("id"), message="已恢复历史最终成片。", last_error="")
        return existing

    tag = _safe_tag(task_id)
    output_root = _final._final_root() / project_id
    work_root = output_root / f"work_{tag}"
    segments_root = work_root / "segments"
    segments_root.mkdir(parents=True, exist_ok=True)
    work_video = work_root / "FINAL_WORK.mp4"
    final_output = output_root / f"FINAL_1080P_30FPS_{tag}.mp4"
    srt = output_root / f"FINAL_{tag}.srt"
    wav = work_root / "narration.wav"

    _final._set_state(status="running", stage="镜头检查 / 自动选片", progress=5, project_id=project_id, task_id=task_id, output_id="", message=f"已确认 {len(selected)} 个正式镜头；人工选择优先。", last_error="")
    _final._task_update(task_id, status="AI自动选片", progress=5, detail=f"已读取 {len(selected)} 个正式镜头。人工选择优先；本轮使用独立工作文件，不覆盖浏览器正在读取的旧成片。", project_status="最终成片处理中")

    segment_paths = []
    total = max(1, len(selected))
    for index, entry in enumerate(selected, 1):
        shot = entry["shot"]
        source = Path(str(entry["output"].get("file_path") or ""))
        duration = max(1.0, min(float(shot.get("duration_seconds") or 4), 12.0))
        target = segments_root / f"{index:03d}_shot_{int(shot.get('order') or index):02d}.mp4"
        progress = 10 + int((index - 1) / total * 48)
        _final._set_state(status="running", stage="1080P / 30fps 清晰化", progress=progress, message=f"正在处理正式镜头 {index}/{total}。")
        _final._task_update(task_id, status="1080P清晰化与补帧", progress=progress, detail=f"正在标准化镜头 {index}/{total}：1080P级输出、30fps；NVENC不兼容时自动使用libx264。")
        _final._render_shot(ffmpeg, source, target, duration, width, height, fps)
        segment_paths.append(target)

    _final._set_state(status="running", stage="FFmpeg 自动剪辑", progress=62, message=f"正在拼接 {len(segment_paths)} 个已确认镜头。")
    _final._task_update(task_id, status="FFmpeg自动剪辑", progress=62, detail=f"正在按导演顺序拼接 {len(segment_paths)} 个正式镜头。")
    _final._concat(ffmpeg, segment_paths, work_video)

    _final._write_srt(selected, srt)
    _final._set_state(status="running", stage="字幕", progress=72, message="正在生成时间轴字幕并尝试烧录。")
    _final._task_update(task_id, status="字幕生成", progress=72, detail="已生成SRT时间轴，正在独立工作文件中烧录字幕。")
    subtitle = _final._burn_subtitles_hq(ffmpeg, work_video, srt)

    _final._set_state(status="running", stage="本地配音", progress=82, message="正在生成本地旁白并封装到工作成片。")
    _final._task_update(task_id, status="本地配音", progress=82, detail="正在生成旁白并封装；工作文件尚未暴露给浏览器，因此不会发生Windows文件占用冲突。")
    narration = _final._narration(selected)
    tts = speech_pipeline._sapi_tts(narration, wav)
    if tts.get("status") == "ready":
        tts["mux"] = _final._mux_voice(ffmpeg, work_video, wav)
    else:
        tts["mux"] = {"status": "skipped", "message": "没有可封装的真实本地配音文件"}

    _final._set_state(status="running", stage="最终技术质检", progress=94, message="正在完整解码工作成片。")
    _final._task_update(task_id, status="最终技术质检", progress=94, detail="正在检查工作成片存在性、文件大小和完整解码；通过后才发布最终文件。")
    qc = _final._qc(ffmpeg, work_video)
    if not qc.get("passed"):
        raise RuntimeError("最终MP4技术质检未通过：" + str(qc.get("error") or "完整解码失败"))

    final_output.parent.mkdir(parents=True, exist_ok=True)
    if final_output.exists():
        final_output.unlink()
    os.replace(work_video, final_output)
    published_qc = _final._qc(ffmpeg, final_output)
    if not published_qc.get("passed"):
        raise RuntimeError("发布后的最终MP4技术质检未通过：" + str(published_qc.get("error") or "完整解码失败"))

    item = _final._register_final(task, project, selected, final_output, srt, tts, subtitle, published_qc, width, height, fps)
    _complete_duplicates(project_id, task_id, item.get("id"))
    _final._set_state(status="completed", stage="最终成片已完成", progress=100, project_id=project_id, task_id=task_id, output_id=item.get("id"), message="最终视频已完成并通过二次完整解码，可在平台直接观看和保存。", last_error="")

    try:
        shutil.rmtree(work_root, ignore_errors=True)
    except OSError:
        pass
    return item


def _snapshot_stable():
    with _final._FINAL_LOCK:
        value = dict(_final._FINAL_STATE)
    busy = bool(_final._FINAL_THREAD is not None and _final._FINAL_THREAD.is_alive())
    value["busy"] = busy

    # Never expose an older final file while a retry is still rendering. Doing
    # so can let the browser lock that file on Windows and break an in-place mux.
    if busy or str(value.get("status") or "") in {"running", "queued"}:
        value["output"] = None
        return value

    if str(value.get("status") or "") == "error":
        value["output"] = None
        return value

    output = _final._latest_final_output(value.get("project_id") or None)
    if output and bool((output.get("technical_qc") or {}).get("passed")):
        value.update({
            "status": "completed",
            "stage": "最终成片已完成",
            "progress": 100,
            "project_id": output.get("project_id") or "",
            "output_id": output.get("id") or "",
            "message": "已读取通过技术质检的真实最终成片。",
            "last_error": "",
            "output": output,
        })
    else:
        value["output"] = None
    return value


def _retry_pending_after_patch():
    # final_render_patch may start a recovery thread milliseconds before this
    # hotfix is imported. Wait for that attempt to exit, then continue the same
    # persisted task with immutable/versioned final output semantics.
    for _ in range(1800):
        time.sleep(1)
        thread = getattr(_final, "_FINAL_THREAD", None)
        if thread is None or not thread.is_alive():
            if _final._pending_final_tasks():
                _final._set_state(
                    status="queued",
                    stage="Windows稳定性修复后重试",
                    progress=0,
                    output_id="",
                    message="正在继续原成片任务；候选和已选镜头全部保留。",
                    last_error="",
                )
                _final._start_worker()
            return


# Install all runtime overrides before the owner UI reads final-render state.
_final._FILTER_CACHE.pop(("encoder", str(_final.find_ffmpeg() or "")), None)
_final._encoder_args = _encoder_args
_final._render_task = _render_task_versioned
_final._snapshot = _snapshot_stable
_final._monitor._queue_final_render = _queue_final_deduplicated

threading.Thread(
    target=_retry_pending_after_patch,
    name="kazuizhi-final-render-71-2-retry",
    daemon=True,
).start()
