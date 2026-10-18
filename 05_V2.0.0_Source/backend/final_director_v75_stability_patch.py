"""#75 stability layer for truthful non-loop director finalization.

This layer is loaded after final_director_v75_patch. It fixes two acceptance
risks without changing the preserved #74 final files:
1) A short visual shortage may extend the *last already-used* candidate with a
   tiny frozen tail, but must never append/replay that candidate a second time.
2) xfade is optional. When the bundled FFmpeg has no xfade filter, or an xfade
   command fails, finalization safely falls back to concat rather than failing.
"""
from __future__ import annotations

import shutil
from pathlib import Path

from backend import final_director_v75_patch as _director


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
        # #75 explicitly forbids replaying a short Wan clip to fake duration.
        # Only a very short frozen tail is allowed as a truthful last-resort
        # bridge. Re-render/replace the last clip with tpad; never append it.
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


def _xfade_beats_safe(ffmpeg, videos, durations, output, transition=_director._TRANSITION_SECONDS):
    if not videos:
        raise RuntimeError("没有可进入最终剪辑的真实视频")
    if len(videos) == 1:
        shutil.copy2(videos[0], output)
        return

    # Some packaged FFmpeg variants do not expose xfade. Continuity quality is
    # preferred, but truthful completion is more important than a fake success.
    if not _director._final._has_filter(ffmpeg, "xfade"):
        _director._concat_copy(ffmpeg, videos, output)
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
        filters.append(
            f"{previous}[{index}:v]xfade=transition=fade:duration={transition:.3f}:offset={offset:.3f}[{label}]"
        )
        previous = f"[{label}]"
        cumulative += float(durations[index]) - transition

    args += [
        "-filter_complex", ";".join(filters), "-map", previous, "-an",
        *_director._final._encoder_args(ffmpeg), "-pix_fmt", "yuv420p",
        "-movflags", "+faststart", str(output),
    ]
    result = _director._final._run(args, timeout=1800)
    valid = result.returncode == 0 and Path(output).is_file() and Path(output).stat().st_size >= 50 * 1024
    if valid:
        return

    # Do not let an optional transition filter destroy the entire completed
    # production. Remove a partial output and use a clean cut fallback.
    try:
        Path(output).unlink(missing_ok=True)
    except OSError:
        pass
    _director._concat_copy(ffmpeg, videos, output)


_director._render_beat = _render_beat_nonrepeat
_director._xfade_beats = _xfade_beats_safe
