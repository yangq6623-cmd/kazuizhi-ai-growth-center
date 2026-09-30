"""R8-18 #90: continuity acceptance QC + truthful UI state closure.

This layer is loaded after #89 and the candidate activation patch.
It deliberately does not regenerate a completed previous shot. For a continuity
shot it:
- extracts a near-final frame from the previous real candidate at the last
  practical frame boundary;
- locks the next Wan generation to that pose for its opening frames;
- compares the handoff frame against the new clip opening with FFmpeg SSIM/PSNR;
- automatically regenerates only the current/next shot when the handoff is too
  discontinuous, up to three quality-first attempts;
- never persists or labels a failed continuity attempt as a generated candidate.

The browser layer also closes two acceptance/UI gaps seen in #89: the actual
current project duration is reflected in the simple-mode selector, and an old
text-AI warning is not shown as a current failure after the same project has a
truthful completed final video.
"""
from __future__ import annotations

import re
from pathlib import Path

from backend import ai_gateway_patch as _ai
from backend import candidate_executor_activation_patch as _activation
from backend import final_director_v75_stability_patch as _v89

_director = _v89._director
_video = _v89._video
_center = _v89._center

_MAX_CONTINUITY_ATTEMPTS = 3
_SSIM_START_MIN = 0.74
_SSIM_EARLY_MIN = 0.60
_PSNR_START_MIN = 19.0
_PSNR_EARLY_MIN = 15.0


def _safe_piece(value, fallback="item"):
    cleaned = re.sub(r"[^0-9A-Za-z_-]+", "_", str(value or fallback))
    return cleaned.strip("_")[:48] or fallback


def _extract_frame(ffmpeg, source, destination, seek_seconds):
    destination = Path(destination)
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        destination.unlink(missing_ok=True)
    except OSError:
        pass
    command = [
        ffmpeg, "-y", "-hide_banner", "-loglevel", "error",
        "-ss", f"{max(0.0, float(seek_seconds)):.4f}", "-i", str(source),
        "-frames:v", "1", "-q:v", "2", str(destination),
    ]
    result = _director._final._run(command, timeout=90)
    return bool(result.returncode == 0 and destination.is_file() and destination.stat().st_size >= 1024)


def _extract_tail_frame_v90(previous_output, shot, candidate):
    source = Path(str((previous_output or {}).get("file_path") or ""))
    root = _video._quality_ai_runtime_patch._comfyui_root()
    ffmpeg_path = _director._final.find_ffmpeg()
    if not source.is_file() or not root or not ffmpeg_path:
        return None

    ffmpeg = str(ffmpeg_path)
    duration = _director._probe_duration(ffmpeg, source)
    if duration <= 0.08:
        return None

    # Wan is currently encoded at 16 fps. 0.04s is close enough to the final
    # displayable frame to avoid the #89 0.12s pose mismatch, while still being
    # seekable across packaged FFmpeg variants.
    tail_offset = 0.04
    seek = max(0.0, duration - tail_offset)
    filename = (
        f"kazuizhi_cont90_{_safe_piece(shot.get('project_id'),'project')}_"
        f"{int(shot.get('order') or 0):02d}_{int(candidate.get('index') or 1):02d}_"
        f"{_safe_piece((previous_output or {}).get('id'),'previous')}.jpg"
    )
    destination = root / "input" / filename
    if not _extract_frame(ffmpeg, source, destination, seek):
        return None

    return {
        "id": f"CONT90-{(previous_output or {}).get('id')}",
        "comfyui_filename": filename,
        "file_path": str(destination),
        "mime_type": "image/jpeg",
        "source_kind": "previous_shot_tail_frame_v90",
        "continuity_source_output_id": (previous_output or {}).get("id"),
        "continuity_source_duration": round(duration, 4),
        "continuity_seek_seconds": round(seek, 4),
        "continuity_tail_offset": tail_offset,
    }


def _metric_result(ffmpeg, reference, sample, filter_name):
    reference = str(reference)
    sample = str(sample)
    normalize = (
        "scale=288:512:force_original_aspect_ratio=decrease,"
        "pad=288:512:(ow-iw)/2:(oh-ih)/2:black,format=yuv420p"
    )
    command = [
        ffmpeg, "-hide_banner", "-loglevel", "info", "-i", reference, "-i", sample,
        "-filter_complex", f"[0:v]{normalize}[a];[1:v]{normalize}[b];[a][b]{filter_name}",
        "-frames:v", "1", "-f", "null", "-",
    ]
    result = _director._final._run(command, timeout=90)
    text = ((result.stderr or b"") + (result.stdout or b"")).decode("utf-8", "replace")
    if filter_name == "ssim":
        matches = re.findall(r"All:([0-9.]+)", text)
    else:
        matches = re.findall(r"average:([0-9.]+)", text)
    if result.returncode != 0 or not matches:
        return None
    try:
        return float(matches[-1])
    except (TypeError, ValueError):
        return None


def _continuity_qc(asset, generated_video, attempt):
    if str(asset.get("source_kind") or "") != "previous_shot_tail_frame_v90":
        return {"applicable": False, "passed": True, "attempt": attempt, "message": "非连续镜头，不执行首尾连续性质检。"}

    ffmpeg_path = _director._final.find_ffmpeg()
    reference = Path(str(asset.get("file_path") or ""))
    source = Path(str(generated_video or ""))
    root = _video._quality_ai_runtime_patch._comfyui_root()
    if not ffmpeg_path or not reference.is_file() or not source.is_file() or not root:
        return {"applicable": True, "passed": False, "attempt": attempt, "message": "连续性质检缺少真实帧或FFmpeg。"}

    ffmpeg = str(ffmpeg_path)
    qc_dir = root / "temp" / "kazuizhi_continuity_qc"
    base = f"q{_safe_piece(source.stem)}_{attempt}"
    first = qc_dir / f"{base}_first.jpg"
    early = qc_dir / f"{base}_early.jpg"
    if not _extract_frame(ffmpeg, source, first, 0.0):
        return {"applicable": True, "passed": False, "attempt": attempt, "message": "无法提取新镜头首帧。"}
    # Roughly the second/third display frame of a 16fps Wan clip. We require it
    # to remain recognizably close to the handoff frame, not frozen-identical.
    if not _extract_frame(ffmpeg, source, early, 0.125):
        early = first

    has_ssim = bool(_director._final._has_filter(ffmpeg, "ssim"))
    metric = "ssim" if has_ssim else "psnr"
    start = _metric_result(ffmpeg, reference, first, metric)
    early_score = _metric_result(ffmpeg, reference, early, metric)
    if start is None or early_score is None:
        return {
            "applicable": True, "passed": False, "attempt": attempt, "metric": metric,
            "message": f"{metric.upper()}连续性质检没有返回可验证分数。",
        }

    if metric == "ssim":
        passed = start >= _SSIM_START_MIN and early_score >= _SSIM_EARLY_MIN
        limits = {"start": _SSIM_START_MIN, "early": _SSIM_EARLY_MIN}
    else:
        passed = start >= _PSNR_START_MIN and early_score >= _PSNR_EARLY_MIN
        limits = {"start": _PSNR_START_MIN, "early": _PSNR_EARLY_MIN}
    return {
        "applicable": True,
        "passed": bool(passed),
        "attempt": attempt,
        "metric": metric,
        "start_score": round(start, 4),
        "early_score": round(early_score, 4),
        "limits": limits,
        "reference_frame": str(reference),
        "first_frame": str(first),
        "early_frame": str(early),
        "message": "连续性通过" if passed else "首尾姿态/构图跳变过大，自动只重生成当前镜头。",
    }


def _lock_continuity_graph(graph, attempt):
    if not isinstance(graph, dict):
        return graph
    prompt_node = graph.get("6") if isinstance(graph.get("6"), dict) else None
    if prompt_node and isinstance(prompt_node.get("inputs"), dict):
        base = str(prompt_node["inputs"].get("text") or "")
        lock = (
            "连续镜头硬约束：第一帧必须严格继承输入参考帧的人物姿势、双手位置、身体角度、"
            "工具位置、洗衣机位置、镜头构图与光线；前0.3秒只允许小幅自然连续运动，然后再进入下一动作；"
            "禁止手部瞬移、身体跳位、突然换机位、突然改变人物比例或重新起动作。"
        )
        prompt_node["inputs"]["text"] = (base + "。" + lock)[:1800]
    negative_node = graph.get("7") if isinstance(graph.get("7"), dict) else None
    if negative_node and isinstance(negative_node.get("inputs"), dict):
        negative = str(negative_node["inputs"].get("text") or "")
        extra = "jump cut pose, sudden pose change, hand teleport, body teleport, camera jump, different starting pose"
        negative_node["inputs"]["text"] = (negative + ", " + extra)[:1800]
    sampler = graph.get("3") if isinstance(graph.get("3"), dict) else None
    if sampler and isinstance(sampler.get("inputs"), dict):
        sampler["inputs"]["steps"] = max(24, int(sampler["inputs"].get("steps") or 20))
        # Each retry progressively increases the opening-pose lock. We keep the
        # first attempt close to the #89 motion budget, then tighten only when QC
        # proves the transition is visibly discontinuous.
        sampler["inputs"]["denoise"] = {1: 0.95, 2: 0.90, 3: 0.86}.get(attempt, 0.90)
    return graph


def _record_v90_metadata(output_id, asset, qc, attempts):
    data = _video._content_center._load()
    for item in data.get("outputs") or []:
        if item.get("id") != output_id:
            continue
        item["director_version"] = "#90"
        item["continuity_mode"] = "tail_frame_pose_lock_qc"
        item["continuity_source_output_id"] = asset.get("continuity_source_output_id")
        item["continuity_start_frame"] = asset.get("file_path")
        item["continuity_qc"] = qc
        item["continuity_attempts"] = attempts
        break
    _video._content_center._audit(
        data, "continuity_v90_passed", output_id,
        f"#90 首尾连续性质检通过；仅当前镜头生成 {attempts} 次，上一镜头未重跑。",
    )
    _video._content_center._save(data)


def _run_candidate_v90(work):
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
    previous_output = _v89._previous_candidate_output(shot, candidate, center_data)
    if not previous_output:
        return _v89._run_candidate_v89(work)

    asset = _extract_tail_frame_v90(previous_output, shot, candidate)
    if asset is None:
        return _v89._run_candidate_v89(work)

    ready = _video._quality_ai_runtime_patch._comfyui_ready()
    if not ready.get("ok"):
        raise RuntimeError(ready.get("message") or "ComfyUI / Wan2.1 FP8 尚未就绪")

    _video._gateway._release_ollama_model()
    _video._time.sleep(1.0)
    last_qc = None

    for attempt in range(1, _MAX_CONTINUITY_ATTEMPTS + 1):
        attempt_key = f"{candidate_key}_cq{attempt}"
        graph, prefix = _video._wan_api_graph(shot, asset, attempt_key)
        graph = _lock_continuity_graph(graph, attempt)
        _video._set_executor_state(
            status="submitting",
            message=f"镜头 {shot_contract.get('order')} 连续性生成第 {attempt}/{_MAX_CONTINUITY_ATTEMPTS} 次；已锁定上一镜头末帧姿态",
            candidate_key=candidate_key, shot_id=shot_id, prompt_id="", last_error="",
        )
        response = _video._comfy_json("/prompt", {"prompt": graph, "client_id": "kazuizhi-r8-90"}, timeout=60)
        prompt_id = str(response.get("prompt_id") or "")
        if not prompt_id:
            raise RuntimeError(f"ComfyUI 没有返回 prompt_id：{response}")
        _video._set_executor_state(
            status="running",
            message=f"ComfyUI 正在生成镜头 {shot_contract.get('order')}；连续性质检尝试 {attempt}/{_MAX_CONTINUITY_ATTEMPTS}",
            prompt_id=prompt_id,
        )
        _video._update_center_task(
            shot_id, "ComfyUI 连续性生成中",
            f"#90 正在生成当前镜头第 {attempt}/{_MAX_CONTINUITY_ATTEMPTS} 次；上一镜头不会重跑。",
        )
        source = _video._wait_for_comfy_video(prompt_id, prefix)
        last_qc = _continuity_qc(asset, source, attempt)
        if last_qc.get("passed"):
            output = _video._persist_candidate(work, source, prompt_id, asset)
            _record_v90_metadata(output.get("id"), asset, last_qc, attempt)
            _video._update_center_task(
                shot_id, "连续性通过",
                f"#90 连续性质检通过：{last_qc.get('metric','').upper()} 首帧 {last_qc.get('start_score')} / 早期 {last_qc.get('early_score')}。",
            )
            _video._set_executor_state(
                status="running",
                message=f"镜头 {shot_contract.get('order')} 连续性质检通过，已回写真实候选",
                last_error="",
            )
            return output

        if attempt < _MAX_CONTINUITY_ATTEMPTS:
            _video._update_center_task(
                shot_id, "连续性自动重试",
                f"#90 第 {attempt} 次首尾连续性不足（{last_qc.get('metric','').upper()}：{last_qc.get('start_score')} / {last_qc.get('early_score')}），仅重生成当前镜头。",
            )
            _video._set_executor_state(
                status="running",
                message=f"连续性不足，自动只重生成镜头 {shot_contract.get('order')}（下一次 {attempt + 1}/{_MAX_CONTINUITY_ATTEMPTS}）",
                last_error="",
            )

    raise RuntimeError(
        "#90 连续性质检连续3次未达到阈值；上一镜头已保留，当前镜头未被伪报为完成。"
        f" 最后分数：{(last_qc or {}).get('metric','')} {(last_qc or {}).get('start_score')} / {(last_qc or {}).get('early_score')}。"
    )


# ---------------------------------------------------------------------------
# #90 browser closure: real duration + successful-project state wins over stale
# text-AI warnings. Candidate activation owns these two script routes, so replace
# its script renderer while preserving its own one-click/ComfyUI browser append.
# ---------------------------------------------------------------------------
_V90_BROWSER_APPEND = r'''
;(() => {
  if (window.__KZ_V90_UI_CLOSURE__) return;
  window.__KZ_V90_UI_CLOSURE__ = true;
  const completed = value => /已完成|完成|已通过|completed/i.test(String(value||''));
  const finalLike = item => /成片|final/i.test(String(item?.kind||item?.type||''));

  function inferSeconds(project, shots){
    const texts=[project?.name,project?.script,project?.director_goal,project?.director_summary]
      .concat((shots||[]).flatMap(x=>[x?.purpose,x?.narration,x?.action,x?.duration,x?.duration_seconds]))
      .filter(Boolean).join(' ');
    const m=texts.match(/(?:目标时长|视频时长|制作一个|时长)?\s*[:：]?\s*(5|10|15|30|45|60)\s*秒/);
    if(m) return Number(m[1]);
    const numeric=(shots||[]).map(x=>Number(x?.duration_seconds||x?.duration||0)).filter(x=>Number.isFinite(x)&&x>0);
    const sum=numeric.reduce((a,b)=>a+b,0);
    if((shots||[]).length===2 && sum>=4 && sum<=7) return 5;
    return 0;
  }

  function setDuration(seconds){
    if(!seconds) return;
    const select=document.getElementById('kz-simple-duration');
    if(!select) return;
    const value=`${seconds} 秒`;
    if([...select.options].some(o=>o.value===value) && select.value!==value) select.value=value;
  }

  function clearStaleFailure(){
    document.querySelectorAll('#kz-production-monitor .kz-prod-error').forEach(node=>{ node.hidden=true; });
    const live=document.querySelector('#kz-production-monitor .kz-prod-live');
    if(live && live.classList.contains('bad')){
      live.classList.remove('bad','idle');
      live.innerHTML='<i></i>本轮完成';
    }
    const result=document.getElementById('kz-simple-result');
    if(result && /AI 服务响应较慢|本地 AI 分析失败|稍后重试/.test(result.textContent||'')){
      result.hidden=true;
    }
  }

  async function sync(){
    try{
      const r=await fetch('/api/ai-content-center',{cache:'no-store'});
      if(!r.ok) return;
      const center=await r.json();
      const project=(center.projects||[])[0];
      if(!project) return;
      const pid=String(project.id||'');
      const shots=(center.storyboards||[]).filter(x=>String(x.project_id||'')===pid).sort((a,b)=>(a.order||0)-(b.order||0));
      setDuration(inferSeconds(project,shots));
      const finals=(center.outputs||[]).filter(x=>String(x.project_id||'')===pid && finalLike(x) && completed(x.status));
      if(finals.length) clearStaleFailure();
    }catch(_){ }
  }
  setTimeout(sync,500);
  setInterval(sync,2500);
})();
'''


def _serve_script_v90(handler, path):
    filename = _activation._SCRIPT_FILES[path]
    web_file = Path(__file__).resolve().parents[1] / "web" / filename
    source = web_file.read_text(encoding="utf-8")
    if filename == "content-studio-simple.js":
        # Make short acceptance options part of the real served script so the
        # later candidate-activation route cannot accidentally hide them.
        if 'value="5 秒"' not in source:
            source = source.replace(
                '<option value="15 秒">15 秒</option><option value="30 秒" selected>30 秒</option>',
                '<option value="5 秒">5 秒（双镜头测试）</option><option value="10 秒">10 秒（短视频测试）</option><option value="15 秒">15 秒</option><option value="30 秒" selected>30 秒</option>',
                1,
            )
        source = source.replace(
            "versionCount:Math.max(1,Math.min(3,Number(byId('kz-simple-version-count')?.value||3))),",
            "versionCount:(byId('kz-simple-duration')?.value==='5 秒'?1:Math.max(1,Math.min(3,Number(byId('kz-simple-version-count')?.value||3)))),",
            1,
        )
        source = _ai._rewrite_browser_script(source)
    source += _activation._BROWSER_APPEND
    source += _V90_BROWSER_APPEND
    payload = source.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/javascript; charset=utf-8")
    handler.send_header("Content-Length", str(len(payload)))
    handler.send_header("Cache-Control", "no-store, no-cache, must-revalidate")
    handler.send_header("Pragma", "no-cache")
    handler.end_headers()
    handler.wfile.write(payload)


# Dynamic lookups in both worker loops make these monkey patches safe after boot.
_v89._extract_tail_frame = _extract_tail_frame_v90
_video._run_candidate = _run_candidate_v90
_activation._serve_script = _serve_script_v90
