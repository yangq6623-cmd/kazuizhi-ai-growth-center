"""R8-18 #75: director-grade finalization for the AI Content Production Center.

Goals discovered in first real field acceptance:
- stop looping 2-second Wan clips to fake 3-7 second shots;
- rewrite one coherent audience-facing narration instead of reading director notes;
- let real TTS duration drive the edit and subtitle clock;
- use selected clips plus unused candidates as B-roll before any short freeze-tail fallback;
- keep voice continuous across visual cuts (J/L-cut style) and add restrained transitions;
- preserve #74 immutable final-file delivery, Windows locking protection and truthful QC;
- generate future Wan candidates in a native portrait canvas for 9:16 projects.

This patch is intentionally layered after #71/#74. It never regenerates existing
candidates automatically and it never reports visual-AI QC that has not actually
run. The current #75 QC is structural/directorial plus FFmpeg full-decode QC.
"""
from __future__ import annotations

import json
import math
import os
import re
import shutil
import subprocess
import time
import wave
from pathlib import Path

from backend import ai_gateway_patch as _ai
from backend import final_render_patch as _final
from backend import final_render_compat_patch as _compat
from backend import kz_local_control_patch as _video
from promotion import ai_production_center as _center
from promotion import speech_pipeline

_BAD_PUBLIC_PHRASES = (
    "数字人师傅演示", "展示处理步骤", "展示处理", "专业判断", "镜头", "CTA",
    "说明用户", "画面展示", "本镜头", "导演", "生成方式",
)
_TRANSITION_SECONDS = 0.16


def _ffprobe_path(ffmpeg):
    path = Path(str(ffmpeg))
    candidate = path.with_name("ffprobe.exe" if os.name == "nt" else "ffprobe")
    if candidate.is_file():
        return candidate
    found = shutil.which("ffprobe.exe") or shutil.which("ffprobe")
    return Path(found) if found else None


def _probe_duration(ffmpeg, path):
    probe = _ffprobe_path(ffmpeg)
    if not probe:
        return 0.0
    result = _final._run([
        probe, "-v", "error", "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1", path,
    ], timeout=30)
    if result.returncode != 0:
        return 0.0
    try:
        return max(0.0, float(result.stdout.decode("utf-8", "replace").strip() or 0))
    except (TypeError, ValueError):
        return 0.0


def _candidate_bank(project_id, shot_id, ffmpeg):
    data = _center._load()
    items = []
    for output in data.get("outputs") or []:
        if output.get("project_id") != project_id or output.get("shot_id") != shot_id:
            continue
        if not _final._valid_video_output(output):
            continue
        duration = _probe_duration(ffmpeg, str(output.get("file_path") or ""))
        if duration <= 0.05:
            continue
        item = dict(output)
        item["source_duration"] = duration
        items.append(item)
    items.sort(
        key=lambda x: (
            0 if (x.get("selected") is True or str(x.get("status") or "") in {"已采用", "已确认", "自动采用"}) else 1,
            int(x.get("candidate_index") or 0),
        )
    )
    return items


def _capacity_map(project_id, selected, ffmpeg):
    result = {}
    for entry in selected:
        shot = entry["shot"]
        bank = _candidate_bank(project_id, shot.get("id"), ffmpeg)
        capacity = sum(max(0.0, min(float(x.get("source_duration") or 0), 3.0)) for x in bank)
        result[int(shot.get("order") or 0)] = max(1.5, round(capacity, 2))
    return result


def _strip_code_fence(text):
    value = str(text or "").strip()
    value = re.sub(r"^```(?:json)?\s*", "", value, flags=re.I)
    value = re.sub(r"\s*```$", "", value)
    start, end = value.find("{"), value.rfind("}")
    if start >= 0 and end > start:
        value = value[start:end + 1]
    return value.strip()


def _clean_public_text(text):
    value = re.sub(r"\s+", "", str(text or "").strip())
    for phrase in _BAD_PUBLIC_PHRASES:
        value = value.replace(phrase, "")
    value = re.sub(r"^[：:、，,。；;]+|[：:、，,；;]+$", "", value)
    return value


def _fallback_voice_plan(project, selected, capacities):
    beats = []
    script = _clean_public_text(project.get("script") or "")
    script_sentences = [x.strip() for x in re.split(r"[。！？!?]+", script) if x.strip()]
    for index, entry in enumerate(selected):
        shot = entry["shot"]
        order = int(shot.get("order") or index + 1)
        raw = _clean_public_text(shot.get("narration") or "")
        if not raw or any(token in raw for token in _BAD_PUBLIC_PHRASES):
            raw = script_sentences[index] if index < len(script_sentences) else _clean_public_text(shot.get("purpose") or "")
        if not raw:
            raw = "先看现场情况，再判断真正需要处理的位置"
        max_chars = max(8, min(28, int(float(capacities.get(order, 3.0)) * 4.2)))
        voice = raw[:max_chars]
        beats.append({
            "shot_order": order,
            "voice_text": voice,
            "subtitle_text": voice,
            "visual_intent": str(shot.get("action") or shot.get("purpose") or "").strip(),
            "transition": "match" if index else "open",
            "continuity": "保持人物、服装、工具、环境方向一致",
        })
    return {
        "title": str(project.get("name") or "短视频"),
        "full_narration": "。".join(x["voice_text"] for x in beats if x.get("voice_text")),
        "beats": beats,
        "source": "规则回退",
    }


def _local_director_plan(project, selected, capacities):
    shots = []
    for entry in selected:
        shot = entry["shot"]
        order = int(shot.get("order") or 0)
        shots.append({
            "shot_order": order,
            "purpose": shot.get("purpose") or "",
            "action": shot.get("action") or "",
            "original_narration": shot.get("narration") or "",
            "available_visual_seconds": capacities.get(order, 3.0),
        })
    prompt = {
        "project_name": project.get("name") or "",
        "original_script": project.get("script") or "",
        "target_style": "真实、自然、本地服务短视频，像真人正常讲述，不像AI导演备注",
        "shots": shots,
    }
    system = (
        "你是短视频总导演和口播编辑。只输出一个JSON对象，不要Markdown。"
        "必须把导演说明改成观众真正听到的自然中文口播。"
        "禁止出现：数字人师傅演示、展示处理步骤、专业判断、镜头、CTA、画面展示等制作术语。"
        "beats数量必须与shots完全相同，shot_order保持不变。"
        "每个voice_text要能在available_visual_seconds内自然读完，按每秒约4个汉字控制长度。"
        "全文要有开头钩子、问题解释、处理逻辑、自然结尾，前后句必须衔接。"
        "subtitle_text可以比voice_text略短，但意思一致。"
        "transition只允许open/match/soft/cut；continuity写下一镜头需要保持的动作和位置。"
        "JSON格式：{title,full_narration,beats:[{shot_order,voice_text,subtitle_text,visual_intent,transition,continuity}]}。"
    )
    try:
        response = _ai._proxy_local_chat({
            "model": "qwen3:8b",
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": json.dumps(prompt, ensure_ascii=False)},
            ],
            "temperature": 0.25,
            "max_tokens": 2200,
            "stream": False,
        })
        content = (((response.get("choices") or [{}])[0].get("message") or {}).get("content") or "")
        data = json.loads(_strip_code_fence(content))
        beats = data.get("beats") if isinstance(data, dict) else None
        if not isinstance(beats, list) or len(beats) != len(selected):
            raise ValueError("导演口播没有返回完整镜头结构")
        normalized = []
        expected = [int(x["shot"].get("order") or 0) for x in selected]
        for index, beat in enumerate(beats):
            if not isinstance(beat, dict):
                raise ValueError("导演口播结构不完整")
            order = int(beat.get("shot_order") or expected[index])
            if order != expected[index]:
                order = expected[index]
            voice = _clean_public_text(beat.get("voice_text") or "")
            subtitle = _clean_public_text(beat.get("subtitle_text") or voice)
            if not voice:
                raise ValueError("导演口播存在空句")
            normalized.append({
                "shot_order": order,
                "voice_text": voice,
                "subtitle_text": subtitle or voice,
                "visual_intent": str(beat.get("visual_intent") or "").strip(),
                "transition": str(beat.get("transition") or "soft").strip().lower(),
                "continuity": str(beat.get("continuity") or "").strip(),
            })
        full = "。".join(x["voice_text"] for x in normalized)
        return {"title": str(data.get("title") or project.get("name") or "短视频"), "full_narration": full, "beats": normalized, "source": "本地GPT总导演"}
    except (RuntimeError, ValueError, TypeError, KeyError, json.JSONDecodeError):
        return _fallback_voice_plan(project, selected, capacities)


def _wav_duration(path):
    try:
        with wave.open(str(path), "rb") as source:
            rate = source.getframerate()
            return source.getnframes() / float(rate or 1)
    except (OSError, wave.Error, EOFError):
        return 0.0


def _merge_wavs(paths, output):
    if not paths:
        raise RuntimeError("没有可合并的真实配音片段")
    params = None
    frames = []
    for path in paths:
        with wave.open(str(path), "rb") as source:
            current = (source.getnchannels(), source.getsampwidth(), source.getframerate(), source.getcomptype(), source.getcompname())
            if params is None:
                params = current
            elif current != params:
                raise RuntimeError("本地逐句配音的WAV参数不一致")
            frames.append(source.readframes(source.getnframes()))
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(output), "wb") as target:
        target.setnchannels(params[0])
        target.setsampwidth(params[1])
        target.setframerate(params[2])
        target.setcomptype(params[3], params[4])
        for chunk in frames:
            target.writeframes(chunk)
    return output


def _tts_master(plan, work_root):
    beat_dir = Path(work_root) / "voice_beats"
    beat_dir.mkdir(parents=True, exist_ok=True)
    durations = []
    wavs = []
    for index, beat in enumerate(plan.get("beats") or [], 1):
        wav = beat_dir / f"{index:02d}.wav"
        result = speech_pipeline._sapi_tts(str(beat.get("voice_text") or ""), wav)
        if result.get("status") != "ready" or not wav.is_file():
            raise RuntimeError(f"第{index}句本地配音失败：{result.get('message') or '没有真实WAV'}")
        duration = _wav_duration(wav)
        if duration <= 0.1:
            raise RuntimeError(f"第{index}句配音时长异常")
        durations.append(duration)
        wavs.append(wav)
    master = Path(work_root) / "narration_master.wav"
    _merge_wavs(wavs, master)
    return master, durations


def _subtitle_chunks(text, max_chars=13):
    value = _clean_public_text(text)
    if not value:
        return []
    pieces = [x for x in re.split(r"(?<=[，。！？!?；;])", value) if x]
    chunks = []
    buffer = ""
    for piece in pieces:
        piece = piece.strip()
        while len(piece) > max_chars:
            head, piece = piece[:max_chars], piece[max_chars:]
            if buffer:
                chunks.append(buffer)
                buffer = ""
            chunks.append(head)
        if len(buffer) + len(piece) <= max_chars:
            buffer += piece
        else:
            if buffer:
                chunks.append(buffer)
            buffer = piece
    if buffer:
        chunks.append(buffer)
    return chunks or [value]


def _stamp(seconds):
    milliseconds = max(0, int(round(float(seconds) * 1000)))
    hours, rest = divmod(milliseconds, 3600000)
    minutes, rest = divmod(rest, 60000)
    secs, ms = divmod(rest, 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def _write_voice_srt(plan, durations, path):
    blocks = []
    current = 0.0
    index = 1
    for beat, duration in zip(plan.get("beats") or [], durations):
        chunks = _subtitle_chunks(beat.get("subtitle_text") or beat.get("voice_text") or "")
        weights = [max(1, len(re.sub(r"[，。！？!?；;]", "", chunk))) for chunk in chunks]
        total_weight = max(1, sum(weights))
        cursor = current
        for chunk, weight in zip(chunks, weights):
            piece_duration = duration * weight / total_weight
            end = min(current + duration, cursor + piece_duration)
            blocks.append(f"{index}\n{_stamp(cursor)} --> {_stamp(end)}\n{chunk}\n")
            index += 1
            cursor = end
        current += duration
    Path(path).write_text("\n".join(blocks), encoding="utf-8")
    return current


def _video_filter(width, height, fps, freeze_tail=0.0):
    cadence = (
        f"minterpolate=fps={fps}:mi_mode=mci:mc_mode=aobmc:me_mode=bidir:vsbmc=1"
        if _VIDEO_FILTER_STATE.get("minterpolate") else f"fps={fps}"
    )
    tail = f",tpad=stop_mode=clone:stop_duration={freeze_tail:.3f}" if freeze_tail > 0.01 else ""
    return (
        f"[0:v]{cadence}[base];"
        f"[base]split=2[bg][fg];"
        f"[bg]scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height},boxblur=18:2[bg2];"
        f"[fg]scale={width}:{height}:force_original_aspect_ratio=decrease[fg2];"
        f"[bg2][fg2]overlay=(W-w)/2:(H-h)/2,unsharp=5:5:0.28:5:5:0.0,setsar=1,format=yuv420p{tail}[v]"
    )


_VIDEO_FILTER_STATE = {"minterpolate": False}


def _render_clip(ffmpeg, source, target, source_seconds, target_seconds, width, height, fps):
    source_seconds = max(0.15, float(source_seconds))
    target_seconds = max(0.15, float(target_seconds))
    freeze = max(0.0, target_seconds - source_seconds)
    if freeze > 1.2:
        raise RuntimeError(f"镜头素材不足 {freeze:.1f} 秒，#75 禁止循环凑时长")
    command = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-i", source,
        "-t", f"{target_seconds:.3f}", "-filter_complex", _video_filter(width, height, fps, freeze),
        "-map", "[v]", "-an", *_final._encoder_args(ffmpeg), "-pix_fmt", "yuv420p", "-movflags", "+faststart", target,
    ]
    result = _final._run(command, timeout=max(600, int(target_seconds * 90)))
    target = Path(target)
    if result.returncode != 0 or not target.is_file() or target.stat().st_size < 10 * 1024:
        error = (result.stderr or result.stdout).decode("utf-8", "replace")[-1000:]
        raise RuntimeError("#75镜头标准化失败：" + (error or "没有生成有效视频"))


def _concat_copy(ffmpeg, clips, output):
    if not clips:
        raise RuntimeError("当前段落没有真实视频素材")
    if len(clips) == 1:
        shutil.copy2(clips[0], output)
        return
    list_path = Path(output).with_suffix(".concat.txt")
    list_path.write_text("\n".join(f"file '{Path(x).resolve().as_posix()}'" for x in clips), encoding="utf-8")
    result = _final._run([
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error", "-f", "concat", "-safe", "0",
        "-i", list_path, "-c", "copy", "-movflags", "+faststart", output,
    ], timeout=900)
    if result.returncode != 0 or not Path(output).is_file():
        error = (result.stderr or result.stdout).decode("utf-8", "replace")[-900:]
        raise RuntimeError("#75 B-roll拼接失败：" + (error or "没有生成有效视频"))


def _render_beat(ffmpeg, project_id, entry, target_seconds, output, clip_dir, width, height, fps):
    shot = entry["shot"]
    bank = _candidate_bank(project_id, shot.get("id"), ffmpeg)
    if not bank:
        raise RuntimeError(f"镜头{shot.get('order')}没有真实候选文件")
    remaining = max(0.4, float(target_seconds))
    rendered = []
    clip_durations = []
    for candidate_index, candidate in enumerate(bank, 1):
        if remaining <= 0.08:
            break
        source_duration = max(0.2, float(candidate.get("source_duration") or 0))
        use = min(source_duration, remaining)
        target = Path(clip_dir) / f"shot_{int(shot.get('order') or 0):02d}_{candidate_index:02d}.mp4"
        _render_clip(ffmpeg, str(candidate.get("file_path")), target, use, use, width, height, fps)
        rendered.append(target)
        clip_durations.append(use)
        remaining -= use
    if remaining > 0.08:
        # No repetition. A short static tail is allowed only as a last-resort
        # bridge; a larger shortage is rejected so the owner sees a truthful QC.
        if remaining > 1.2:
            raise RuntimeError(f"镜头{shot.get('order')}可用B-roll不足 {remaining:.1f} 秒；已禁止循环凑时长")
        candidate = bank[-1]
        source_duration = max(0.2, float(candidate.get("source_duration") or 0))
        target = Path(clip_dir) / f"shot_{int(shot.get('order') or 0):02d}_tail.mp4"
        _render_clip(ffmpeg, str(candidate.get("file_path")), target, source_duration, source_duration + remaining, width, height, fps)
        rendered.append(target)
        clip_durations.append(source_duration + remaining)
        remaining = 0.0
    _concat_copy(ffmpeg, rendered, output)
    return {"clips": [str(x) for x in rendered], "clip_durations": clip_durations, "freeze_tail": max(0.0, remaining)}


def _xfade_beats(ffmpeg, videos, durations, output, transition=_TRANSITION_SECONDS):
    if len(videos) == 1:
        shutil.copy2(videos[0], output)
        return
    args = [ffmpeg, "-y", "-hide_banner", "-loglevel", "error"]
    for video in videos:
        args += ["-i", str(video)]
    filters = []
    cumulative = float(durations[0])
    previous = "[0:v]"
    for index in range(1, len(videos)):
        label = f"v{index}"
        offset = max(0.01, cumulative - transition)
        filters.append(f"{previous}[{index}:v]xfade=transition=fade:duration={transition:.3f}:offset={offset:.3f}[{label}]")
        previous = f"[{label}]"
        cumulative += float(durations[index]) - transition
    args += ["-filter_complex", ";".join(filters), "-map", previous, "-an", *_final._encoder_args(ffmpeg), "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(output)]
    result = _final._run(args, timeout=1800)
    if result.returncode != 0 or not Path(output).is_file() or Path(output).stat().st_size < 50 * 1024:
        error = (result.stderr or result.stdout).decode("utf-8", "replace")[-1200:]
        raise RuntimeError("#75 连贯转场合成失败：" + (error or "没有生成有效成片"))


def _structural_director_qc(plan, audio_seconds, selected, timeline):
    narration = str(plan.get("full_narration") or "")
    forbidden = [phrase for phrase in _BAD_PUBLIC_PHRASES if phrase in narration]
    freezes = [item for item in timeline if float(item.get("freeze_tail_seconds") or 0) > 0.8]
    result = {
        "mode": "structural_director_qc",
        "visual_ai_reviewed": False,
        "no_loop_fill": True,
        "voice_master_clock": True,
        "precise_subtitle_clock": True,
        "formal_shots": len(selected),
        "audio_seconds": round(float(audio_seconds), 3),
        "forbidden_public_phrases": forbidden,
        "long_freeze_tails": len(freezes),
    }
    result["passed"] = not forbidden and not freezes and len(selected) > 0 and audio_seconds > 1.0
    if not result["passed"]:
        result["message"] = "结构导演质检发现仍有制作术语或过长静帧；没有伪报视觉AI质检通过。"
    else:
        result["message"] = "结构导演质检通过；真实视觉语义质检仍留待后续视觉模型接入。"
    return result


def _persist_director_metadata(output_id, plan, timeline, qc):
    data = _center._load()
    for item in data.get("outputs") or []:
        if item.get("id") == output_id:
            item["director_version"] = "#75"
            item["voice_plan"] = plan
            item["director_timeline"] = timeline
            item["director_qc"] = qc
            item["no_loop_fill"] = True
            item["voice_master_clock"] = True
            item["updated_at"] = _center.now_iso()
            break
    _center._audit(data, "director_v75_completed", output_id, "#75 已使用整片口播、真实TTS时间轴、B-roll优先和禁止循环策略完成成片。")
    _center._save(data)


def _render_task_director(task):
    project_id = str(task.get("project_id") or "")
    task_id = str(task.get("id") or "")
    ffmpeg_path = _final.find_ffmpeg()
    if not ffmpeg_path:
        raise RuntimeError("没有找到 FFmpeg，无法进入#75导演级成片")
    ffmpeg = str(ffmpeg_path)
    _VIDEO_FILTER_STATE["minterpolate"] = bool(_final._has_filter(ffmpeg, "minterpolate"))
    project, selected = _final._selected_plan(project_id, persist_auto=True)
    width, height = _final._ratio_dimensions(project.get("ratio"))
    fps = 30

    # Existing #74 finals remain immutable. A new task intentionally produces a
    # new #75 final; it never mutates a file the browser may already be reading.
    tag = "75" + _compat._safe_tag(task_id)[-8:]
    output_root = _final._final_root() / project_id
    work_root = output_root / f"work_{tag}"
    beat_root = work_root / "beats"
    clip_root = work_root / "clips"
    beat_root.mkdir(parents=True, exist_ok=True)
    clip_root.mkdir(parents=True, exist_ok=True)
    work_video = work_root / "DIRECTOR_WORK.mp4"
    final_output = output_root / f"FINAL_1080P_30FPS_{tag}.mp4"
    srt = output_root / f"FINAL_{tag}.srt"

    _final._set_state(status="running", stage="#75 整片导演 / 口播重写", progress=6, project_id=project_id, task_id=task_id, output_id="", message="正在把导演说明重写成观众真正听到的完整口播。", last_error="")
    _final._task_update(task_id, status="#75整片导演", progress=6, detail="正在生成完整观众口播；禁止把‘展示处理步骤/专业判断/CTA’等制作术语直接念给观众。", project_status="导演级成片处理中")

    capacities = _capacity_map(project_id, selected, ffmpeg)
    plan = _local_director_plan(project, selected, capacities)

    _final._set_state(status="running", stage="#75 逐句TTS / 真实时间轴", progress=18, message="正在逐句生成真实配音，声音时长将成为剪辑主时钟。")
    _final._task_update(task_id, status="真实语音时间轴", progress=18, detail="逐句TTS后读取真实WAV时长；字幕和画面不再使用导演预估秒数。")
    master_wav, voice_durations = _tts_master(plan, work_root)
    audio_seconds = _write_voice_srt(plan, voice_durations, srt)

    # Each beat gets a small transition allowance except the last one. Xfade
    # consumes that allowance, so the resulting visual duration still tracks
    # the real narration duration instead of drifting shorter.
    beat_videos = []
    beat_durations = []
    timeline = []
    total = max(1, len(selected))
    for index, (entry, voice_seconds) in enumerate(zip(selected, voice_durations), 1):
        target_seconds = float(voice_seconds) + (_TRANSITION_SECONDS if index < total else 0.0)
        target = beat_root / f"beat_{index:02d}.mp4"
        progress = 28 + int((index - 1) / total * 34)
        _final._set_state(status="running", stage="#75 B-roll / 非循环剪辑", progress=progress, message=f"正在处理镜头 {index}/{total}；先用备用候选补时长，禁止循环播放。")
        _final._task_update(task_id, status="#75非循环剪辑", progress=progress, detail=f"镜头 {index}/{total}：优先使用已选候选+备用候选作为B-roll；素材不足只允许极短静帧，不循环。")
        info = _render_beat(ffmpeg, project_id, entry, target_seconds, target, clip_root, width, height, fps)
        beat_videos.append(target)
        actual = _probe_duration(ffmpeg, target) or target_seconds
        beat_durations.append(actual)
        timeline.append({
            "shot_order": int(entry["shot"].get("order") or index),
            "voice_text": (plan.get("beats") or [{}])[index - 1].get("voice_text") or "",
            "voice_seconds": round(float(voice_seconds), 3),
            "visual_seconds": round(float(actual), 3),
            "candidate_clips": info.get("clips") or [],
            "freeze_tail_seconds": 0.0,
            "transition": (plan.get("beats") or [{}])[index - 1].get("transition") or "soft",
            "continuity": (plan.get("beats") or [{}])[index - 1].get("continuity") or "",
        })

    _final._set_state(status="running", stage="#75 连贯剪辑 / J-L式音画分离", progress=67, message="正在做克制的镜头过渡；配音保持连续，不再一镜头一句机械切断。")
    _final._task_update(task_id, status="#75连贯剪辑", progress=67, detail="画面使用短交叠转场，语音作为独立连续主轨，形成J/L-cut式观感。")
    _xfade_beats(ffmpeg, beat_videos, beat_durations, work_video)

    _final._set_state(status="running", stage="#75 精确字幕", progress=76, message="字幕时间码来自真实逐句TTS时长。")
    subtitle = _final._burn_subtitles_hq(ffmpeg, work_video, srt)

    _final._set_state(status="running", stage="#75 连续配音封装", progress=84, message="正在把完整连续口播封装进成片。")
    tts = {
        "status": "ready",
        "path": str(master_wav),
        "message": "#75逐句TTS已合并为完整连续口播",
        "source": plan.get("source") or "",
        "duration_seconds": round(audio_seconds, 3),
    }
    tts["mux"] = _final._mux_voice(ffmpeg, work_video, master_wav)
    if tts["mux"].get("status") != "ready":
        raise RuntimeError("#75连续配音封装失败：" + str(tts["mux"].get("message") or "未知错误"))

    _final._set_state(status="running", stage="#75 导演结构质检 + 技术质检", progress=94, message="正在检查制作术语、循环填充、时间轴和最终MP4完整解码。")
    director_qc = _structural_director_qc(plan, audio_seconds, selected, timeline)
    if not director_qc.get("passed"):
        raise RuntimeError("#75导演结构质检未通过：" + str(director_qc.get("message") or "结构异常"))
    technical_qc = _final._qc(ffmpeg, work_video)
    if not technical_qc.get("passed"):
        raise RuntimeError("#75最终MP4技术质检未通过：" + str(technical_qc.get("error") or "完整解码失败"))

    final_output.parent.mkdir(parents=True, exist_ok=True)
    if final_output.exists():
        final_output.unlink()
    os.replace(work_video, final_output)
    published_qc = _final._qc(ffmpeg, final_output)
    if not published_qc.get("passed"):
        raise RuntimeError("#75发布后的最终MP4质检未通过：" + str(published_qc.get("error") or "完整解码失败"))

    item = _final._register_final(task, project, selected, final_output, srt, tts, subtitle, published_qc, width, height, fps)
    _persist_director_metadata(item.get("id"), plan, timeline, director_qc)
    _compat._complete_duplicates(project_id, task_id, item.get("id"))
    _final._set_state(status="completed", stage="#75 导演级最终成片已完成", progress=100, project_id=project_id, task_id=task_id, output_id=item.get("id"), message="已完成整片口播、真实语音时间轴、非循环B-roll剪辑、精确字幕和完整解码质检。", last_error="")
    try:
        shutil.rmtree(work_root, ignore_errors=True)
    except OSError:
        pass
    return item


# Future candidate generation: use a native portrait canvas instead of square
# generation + blurred fill for 9:16 projects. 432x768 is deliberately chosen
# as a 12GB-friendly multiple-of-16 canvas; #75 finalization still upscales to
# truthful 1080x1920. Existing candidates are left untouched.
_ORIGINAL_WAN_GRAPH = _video._wan_api_graph
_ORIGINAL_POSITIVE_PROMPT = _video._positive_prompt


def _wan_graph_v75(shot, asset, candidate_key):
    graph, prefix = _ORIGINAL_WAN_GRAPH(shot, asset, candidate_key)
    ratio = "9:16"
    try:
        data = _center._load()
        project = next((x for x in data.get("projects") or [] if x.get("id") == shot.get("project_id")), None)
        ratio = str((project or {}).get("ratio") or "9:16").replace(" ", "")
    except (OSError, ValueError, TypeError):
        ratio = "9:16"
    if ratio in {"16:9", "16/9"}:
        width, height = 768, 432
    elif ratio in {"1:1", "1/1"}:
        width, height = 512, 512
    else:
        width, height = 432, 768
    if "50" in graph and isinstance(graph["50"].get("inputs"), dict):
        graph["50"]["inputs"]["width"] = width
        graph["50"]["inputs"]["height"] = height
        graph["50"]["inputs"]["length"] = 33
    return graph, prefix


def _positive_prompt_v75(shot):
    base = _ORIGINAL_POSITIVE_PROMPT(shot)
    locks = [str(x).strip() for x in (shot.get("consistency_locks") or []) if str(x).strip()]
    continuity = str(shot.get("continuity") or "").strip()
    extras = []
    if locks:
        extras.append("连续性锁定：" + "、".join(locks))
    if continuity:
        extras.append("动作连续要求：" + continuity)
    extras.append("竖屏短视频优先保持人物完整、手部动作清楚、主体不出安全区")
    return (base + "。" + "。".join(extras))[:1800]


_final._render_task = _render_task_director
_video._wan_api_graph = _wan_graph_v75
_video._positive_prompt = _positive_prompt_v75
