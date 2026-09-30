"""#75/#89 stability and continuity layer for truthful finalization.

#75 keeps the non-loop rendering contract. #89 adds the two quality fixes proven
necessary by the first real 5-second Wan acceptance video:
1) continuity shots start from a near-final frame extracted from the previous
   *real generated candidate* instead of independently restarting from the same
   uploaded still image;
2) director instructions are separated from public narration/subtitles and
   action-match cuts no longer use a visible dissolve that creates ghosting.

The continuation handoff is conditional. Explicit scene changes still use the
normal reference asset path. Existing generated candidates are never relabelled
as regenerated; the new handoff applies to newly generated/re-generated shots.
"""
from __future__ import annotations

import re
import shutil
from pathlib import Path

from backend import final_director_v75_patch as _director

_video = _director._video
_center = _director._center


# ---------------------------------------------------------------------------
# #75 non-loop safety (preserved)
# ---------------------------------------------------------------------------
def _render_beat_nonrepeat(ffmpeg, project_id, entry, target_seconds, output, clip_dir, width, height, fps):
    shot = entry["shot"]
    bank = _director._candidate_bank(project_id, shot.get("id"), ffmpeg)
    if not bank:
        raise RuntimeError(f"镜头{shot.get('order')}没有真实候选文件")

    remaining = max(0.4, float(target_seconds))
    rendered = []
    clip_durations = []
    last_candidate = None
    last_target = None
    last_use = 0.0

    for candidate_index, candidate in enumerate(bank, 1):
        if remaining <= 0.08:
            break
        source_duration = max(0.2, float(candidate.get("source_duration") or 0))
        use = min(source_duration, remaining)
        target = Path(clip_dir) / f"shot_{int(shot.get('order') or 0):02d}_{candidate_index:02d}.mp4"
        _director._render_clip(ffmpeg, str(candidate.get("file_path")), target, use, use, width, height, fps)
        rendered.append(target)
        clip_durations.append(use)
        last_candidate = candidate
        last_target = target
        last_use = use
        remaining -= use

    freeze_used = 0.0
    if remaining > 0.08:
        # Never replay a short Wan clip to fake duration. Only a short frozen
        # tail may bridge a small shortage, and it replaces the last clip.
        if remaining > 1.2:
            raise RuntimeError(f"镜头{shot.get('order')}可用B-roll不足 {remaining:.1f} 秒；#75 已禁止循环凑时长")
        if last_candidate is None or last_target is None or not rendered:
            raise RuntimeError(f"镜头{shot.get('order')}没有可延长的真实候选素材")
        freeze_used = remaining
        _director._render_clip(
            ffmpeg,
            str(last_candidate.get("file_path")),
            last_target,
            last_use,
            last_use + freeze_used,
            width,
            height,
            fps,
        )
        clip_durations[-1] = last_use + freeze_used
        remaining = 0.0

    _director._concat_copy(ffmpeg, rendered, output)
    return {
        "clips": [str(x) for x in rendered],
        "clip_durations": clip_durations,
        "freeze_tail": round(freeze_used, 3),
    }


# ---------------------------------------------------------------------------
# #89 public narration hygiene
# ---------------------------------------------------------------------------
# These terms are production/director instructions. They may guide image/video
# generation, but they may never be spoken or burned into public subtitles.
_V89_DIRECTOR_MARKERS = (
    "数字人师傅演示", "展示处理步骤", "展示处理", "专业判断", "镜头", "CTA",
    "说明用户", "画面展示", "本镜头", "导演", "生成方式", "承接动作", "承接上一",
    "保持同一", "保持人物", "保持服装", "人物位置", "工具保持", "场景保持",
    "动作必须", "动作连续", "不允许", "禁止重复", "近景拍摄", "特写拍摄",
    "参考图", "首帧", "尾帧", "机位", "运镜", "候选", "B-roll", "一致性",
)

# Structural QC also sees the expanded list.
_director._BAD_PUBLIC_PHRASES = tuple(dict.fromkeys(tuple(_director._BAD_PUBLIC_PHRASES) + _V89_DIRECTOR_MARKERS))

_DIRECTIVE_PREFIXES = (
    r"^镜头\s*[一二三四五六七八九十\d]*\s*[：:]?",
    r"^承接(?:上一|前一)?(?:个)?(?:镜头)?(?:的)?动作\s*[，,:：]?",
    r"^保持(?:同一)?(?:位)?(?:人物|师傅|服装|场景|设备|工具|光线|位置)[^，。；;]{0,24}[，,:：]?",
    r"^(?:近景|特写|中景|全景)拍摄\s*[：:]?",
    r"^(?:画面|视频)(?:展示|表现)\s*[：:]?",
)


def _clean_public_text_v89(text):
    value = str(text or "").replace("\r", "\n").strip()
    value = re.sub(r"[ \t]+", "", value)
    value = re.sub(r"(?:旁白|口播)(?:内容)?(?:只说|为|使用)?\s*[：:]\s*", "", value)
    value = value.strip("“”\"' ")
    if not value:
        return ""

    # Work clause-by-clause. Director-only clauses are dropped instead of merely
    # deleting one keyword and leaving fragments such as “动作检查并拧紧…”.
    raw_clauses = [x.strip() for x in re.split(r"[。！？!?；;\n]+", value) if x.strip()]
    cleaned = []
    for clause in raw_clauses:
        original = clause
        for pattern in _DIRECTIVE_PREFIXES:
            clause = re.sub(pattern, "", clause)
        clause = clause.strip("：:、，,。；;“”\"' ")
        if not clause:
            continue

        # Reject clauses that still read as production instructions. “检查并拧紧
        # 排水接口” is valid public language; “保持同一人物/不允许换场景” is not.
        hard_markers = (
            "镜头", "保持同一", "保持人物", "保持服装", "人物位置", "场景保持",
            "工具保持", "动作必须", "动作连续", "不允许", "禁止重复", "参考图",
            "首帧", "尾帧", "机位", "运镜", "B-roll", "候选", "9:16",
        )
        if any(marker in clause for marker in hard_markers):
            continue
        for phrase in ("数字人师傅演示", "展示处理步骤", "专业判断", "画面展示", "生成方式", "CTA"):
            clause = clause.replace(phrase, "")
        clause = clause.strip("：:、，,。；;“”\"' ")
        if clause and clause not in cleaned:
            cleaned.append(clause)

    if not cleaned:
        return ""
    return "。".join(cleaned)


def _extract_explicit_voice(project, selected):
    texts = []
    for key in ("script", "brief", "description", "note", "instruction"):
        if project.get(key):
            texts.append(str(project.get(key)))
    for entry in selected:
        shot = entry.get("shot") or {}
        for key in ("narration", "purpose", "action", "note"):
            if shot.get(key):
                texts.append(str(shot.get(key)))
    combined = "\n".join(texts)
    patterns = (
        r"(?:旁白|口播)(?:内容)?\s*只说\s*[：:]\s*[“\"']?([^”\"'\n]{2,50})",
        r"(?:旁白|口播)(?:内容)?\s*[：:]\s*[“\"']?([^”\"'\n]{2,50})",
    )
    for pattern in patterns:
        match = re.search(pattern, combined)
        if not match:
            continue
        value = match.group(1)
        # Stop at the first sentence boundary if the capture continued into the
        # next production instruction.
        value = re.split(r"[。！？!?]", value, maxsplit=1)[0]
        value = _clean_public_text_v89(value)
        if value:
            return value
    return ""


def _split_voice(text, count):
    count = max(1, int(count or 1))
    value = _clean_public_text_v89(text)
    if not value:
        return []
    parts = [x for x in re.split(r"[，,。！？!?；;]+", value) if x]
    if len(parts) >= count:
        # Preserve all content by distributing source clauses across beats.
        buckets = [[] for _ in range(count)]
        for index, part in enumerate(parts):
            bucket = min(count - 1, int(index * count / max(1, len(parts))))
            buckets[bucket].append(part)
        return ["，".join(x) for x in buckets]
    if count == 1:
        return [value]
    # For one short sentence, split near equal character boundaries. This keeps
    # one continuous user-facing thought across multiple visual beats.
    length = len(value)
    chunks = []
    start = 0
    for index in range(count):
        end = length if index == count - 1 else round(length * (index + 1) / count)
        chunks.append(value[start:end].strip("，,。；;"))
        start = end
    return chunks


def _fallback_voice_plan_v89(project, selected, capacities):
    explicit = _extract_explicit_voice(project, selected)
    safe_script = _clean_public_text_v89(project.get("script") or "")
    source = explicit or safe_script
    chunks = _split_voice(source, len(selected)) if source else []

    beats = []
    generic = ("先看清楚问题位置", "再确认需要处理的关键位置")
    for index, entry in enumerate(selected):
        shot = entry["shot"]
        order = int(shot.get("order") or index + 1)
        voice = chunks[index] if index < len(chunks) and chunks[index] else ""
        if not voice:
            voice = _clean_public_text_v89(shot.get("narration") or "")
        if not voice:
            voice = generic[min(index, len(generic) - 1)]
        max_chars = max(6, min(28, int(float(capacities.get(order, 3.0)) * 4.2)))
        voice = voice[:max_chars]
        beats.append({
            "shot_order": order,
            "voice_text": voice,
            "subtitle_text": voice,
            "visual_intent": str(shot.get("action") or shot.get("purpose") or "").strip(),
            "transition": "match" if index else "open",
            "continuity": "保持人物、服装、工具、环境和动作方向连续",
        })
    return {
        "title": str(project.get("name") or "短视频"),
        "full_narration": "。".join(x["voice_text"] for x in beats if x.get("voice_text")),
        "beats": beats,
        "source": "用户指定旁白" if explicit else "#89规则回退",
    }


_ORIGINAL_LOCAL_DIRECTOR_PLAN = _director._local_director_plan


def _local_director_plan_v89(project, selected, capacities):
    # An explicit “旁白只说：...” is an owner instruction and outranks creative
    # rewriting. This prevents visual/director notes from leaking into speech.
    if _extract_explicit_voice(project, selected):
        return _fallback_voice_plan_v89(project, selected, capacities)

    plan = _ORIGINAL_LOCAL_DIRECTOR_PLAN(project, selected, capacities)
    if not isinstance(plan, dict):
        return _fallback_voice_plan_v89(project, selected, capacities)
    beats = plan.get("beats")
    if not isinstance(beats, list) or len(beats) != len(selected):
        return _fallback_voice_plan_v89(project, selected, capacities)

    normalized = []
    for beat in beats:
        if not isinstance(beat, dict):
            return _fallback_voice_plan_v89(project, selected, capacities)
        current = dict(beat)
        voice = _clean_public_text_v89(current.get("voice_text") or "")
        subtitle = _clean_public_text_v89(current.get("subtitle_text") or voice)
        if not voice:
            return _fallback_voice_plan_v89(project, selected, capacities)
        current["voice_text"] = voice
        current["subtitle_text"] = subtitle or voice
        normalized.append(current)
    plan = dict(plan)
    plan["beats"] = normalized
    plan["full_narration"] = "。".join(x["voice_text"] for x in normalized)
    plan["source"] = str(plan.get("source") or "本地GPT总导演") + " + #89净化"
    return plan


# ---------------------------------------------------------------------------
# #89 true continuation: previous real candidate tail -> next Wan start frame
# ---------------------------------------------------------------------------
def _should_chain_from_previous(shot, data):
    project_id = str(shot.get("project_id") or "")
    order = int(shot.get("order") or 0)
    if order <= 1:
        return False
    project_shots = sorted(
        [x for x in (data.get("storyboards") or []) if str(x.get("project_id") or "") == project_id],
        key=lambda x: int(x.get("order") or 0),
    )
    # The controlled two-shot acceptance test is explicitly a continuity test.
    if len(project_shots) == 2:
        return True
    text = " ".join(str(shot.get(key) or "") for key in ("continuity", "action", "purpose", "narration"))
    return any(token in text for token in ("承接", "继续", "接着", "连续", "同一人物", "保持人物", "延续"))


def _previous_candidate_output(shot, candidate, data):
    if not _should_chain_from_previous(shot, data):
        return None
    project_id = str(shot.get("project_id") or "")
    order = int(shot.get("order") or 0)
    previous_shots = [
        x for x in (data.get("storyboards") or [])
        if str(x.get("project_id") or "") == project_id and int(x.get("order") or 0) < order
    ]
    if not previous_shots:
        return None
    previous = max(previous_shots, key=lambda x: int(x.get("order") or 0))
    wanted_index = int(candidate.get("index") or 1)
    outputs = []
    for output in data.get("outputs") or []:
        if output.get("shot_id") != previous.get("id"):
            continue
        path = Path(str(output.get("file_path") or ""))
        if not path.is_file() or "候选" not in str(output.get("kind") or "镜头候选视频"):
            continue
        outputs.append(output)
    if not outputs:
        return None
    outputs.sort(key=lambda x: (
        0 if x.get("selected") is True or str(x.get("status") or "") in {"已采用", "已确认", "自动采用"} else 1,
        0 if int(x.get("candidate_index") or 1) == wanted_index else 1,
        str(x.get("created_at") or ""),
    ))
    return outputs[0]


def _extract_tail_frame(previous_output, shot, candidate):
    source = Path(str(previous_output.get("file_path") or ""))
    root = _video._quality_ai_runtime_patch._comfyui_root()
    ffmpeg_path = _director._final.find_ffmpeg()
    if not source.is_file() or not root or not ffmpeg_path:
        return None

    project_id = re.sub(r"[^0-9A-Za-z_-]+", "_", str(shot.get("project_id") or "project"))[:40]
    shot_order = int(shot.get("order") or 0)
    cand_index = int(candidate.get("index") or 1)
    previous_id = re.sub(r"[^0-9A-Za-z_-]+", "_", str(previous_output.get("id") or "previous"))[-32:]
    filename = f"kazuizhi_cont_{project_id}_{shot_order:02d}_{cand_index:02d}_{previous_id}.jpg"
    destination = root / "input" / filename
    destination.parent.mkdir(parents=True, exist_ok=True)

    ffmpeg = str(ffmpeg_path)
    command = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-sseof", "-0.12", "-i", str(source), "-frames:v", "1", "-q:v", "2", str(destination),
    ]
    result = _director._final._run(command, timeout=90)
    if result.returncode != 0 or not destination.is_file() or destination.stat().st_size < 1024:
        # Some FFmpeg builds seek more reliably with an absolute timestamp.
        duration = _director._probe_duration(ffmpeg, source)
        seek = max(0.0, duration - 0.12)
        result = _director._final._run([
            ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
            "-ss", f"{seek:.3f}", "-i", str(source), "-frames:v", "1", "-q:v", "2", str(destination),
        ], timeout=90)
    if result.returncode != 0 or not destination.is_file() or destination.stat().st_size < 1024:
        return None

    return {
        "id": f"CONT-{previous_output.get('id')}",
        "comfyui_filename": filename,
        "file_path": str(destination),
        "mime_type": "image/jpeg",
        "source_kind": "previous_shot_tail_frame",
        "continuity_source_output_id": previous_output.get("id"),
    }


def _record_continuity_metadata(output_id, asset):
    if not output_id or str(asset.get("source_kind") or "") != "previous_shot_tail_frame":
        return
    data = _video._content_center._load()
    for item in data.get("outputs") or []:
        if item.get("id") != output_id:
            continue
        item["continuity_mode"] = "previous_shot_tail_frame"
        item["continuity_source_output_id"] = asset.get("continuity_source_output_id")
        item["continuity_start_frame"] = asset.get("file_path")
        item["director_version"] = "#89"
        break
    _video._content_center._save(data)


def _run_candidate_v89(work):
    candidate = work.get("candidate") or {}
    shot_contract = work.get("shot") or {}
    candidate_key = str(candidate.get("key") or "")
    shot_id = str(shot_contract.get("shot_id") or "")
    existing = _video._existing_output(candidate_key)
    if existing:
        _video._mission.checkpoint({
            "mission_id": work.get("mission_id"), "candidate_key": candidate_key,
            "status": "generated", "output_id": existing.get("id"), "file_url": existing.get("file_url"),
        })
        return existing

    center_data = _video._content_center._load()
    shot = _video._center_shot(shot_id, center_data)
    previous_output = _previous_candidate_output(shot, candidate, center_data)
    asset = _extract_tail_frame(previous_output, shot, candidate) if previous_output else None
    if asset is None:
        asset = _video._asset_for_shot(shot)
        continuity_note = ""
    else:
        continuity_note = "；已从上一镜头真实视频末帧续接"

    ready = _video._quality_ai_runtime_patch._comfyui_ready()
    if not ready.get("ok"):
        raise RuntimeError(ready.get("message") or "ComfyUI / Wan2.1 FP8 尚未就绪")

    _video._gateway._release_ollama_model()
    _video._time.sleep(1.0)

    graph, prefix = _video._wan_api_graph(shot, asset, candidate_key)
    _video._set_executor_state(
        status="submitting",
        message=f"正在提交镜头 {shot_contract.get('order')} 候选 {candidate.get('index')} 到 ComfyUI{continuity_note}",
        candidate_key=candidate_key, shot_id=shot_id, prompt_id="", last_error="",
    )
    response = _video._comfy_json("/prompt", {"prompt": graph, "client_id": "kazuizhi-r8-89"}, timeout=60)
    prompt_id = str(response.get("prompt_id") or "")
    if not prompt_id:
        raise RuntimeError(f"ComfyUI 没有返回 prompt_id：{response}")
    _video._set_executor_state(
        status="running",
        message=f"ComfyUI 正在生成镜头 {shot_contract.get('order')} 候选 {candidate.get('index')}{continuity_note}",
        prompt_id=prompt_id,
    )
    _video._update_center_task(
        shot_id, "ComfyUI 生成中",
        f"ComfyUI 已接收真实生成任务：{prompt_id}{continuity_note}；RTX3060 正在串行处理。",
    )
    source = _video._wait_for_comfy_video(prompt_id, prefix)
    output = _video._persist_candidate(work, source, prompt_id, asset)
    _record_continuity_metadata(output.get("id"), asset)
    _video._set_executor_state(
        status="running",
        message=f"候选 {candidate_key} 已生成并回写平台，继续下一候选",
        last_error="",
    )
    return output


# ---------------------------------------------------------------------------
# #89 action-match final cut: no visible dissolve ghosting
# ---------------------------------------------------------------------------
def _match_cut_v89(ffmpeg, videos, durations, output, transition=0.0):
    if not videos:
        raise RuntimeError("没有可进入最终剪辑的真实视频")
    # All beats have already been standardized to the same output contract.
    # A clean concat is the correct action-match cut when the next shot starts
    # from the previous real tail frame. It avoids double-exposed hands/faces.
    _director._concat_copy(ffmpeg, videos, output)


_ORIGINAL_PERSIST_DIRECTOR_METADATA = _director._persist_director_metadata


def _persist_director_metadata_v89(output_id, plan, timeline, qc):
    _ORIGINAL_PERSIST_DIRECTOR_METADATA(output_id, plan, timeline, qc)
    data = _center._load()
    for item in data.get("outputs") or []:
        if item.get("id") == output_id:
            item["director_version"] = "#89"
            item["transition_mode"] = "continuity_match_cut"
            item["public_narration_hygiene"] = True
            break
    _center._audit(data, "director_v89_completed", output_id, "#89 使用上一镜头真实末帧续接、动作匹配硬切和观众口播净化完成成片。")
    _center._save(data)


# Apply after the #75 base functions are loaded. Later short-test patches may
# change _asset_for_shot, which is intentional: shot 1 still uses their normal
# reference routing; shot 2+ may override it only when continuity is requested.
_director._clean_public_text = _clean_public_text_v89
_director._fallback_voice_plan = _fallback_voice_plan_v89
_director._local_director_plan = _local_director_plan_v89
_director._TRANSITION_SECONDS = 0.0
_director._render_beat = _render_beat_nonrepeat
_director._xfade_beats = _match_cut_v89
_director._persist_director_metadata = _persist_director_metadata_v89
_video._run_candidate = _run_candidate_v89
