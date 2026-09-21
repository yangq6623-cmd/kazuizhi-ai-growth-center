"""Execution extensions for the R8 local video worker.

Adds verified licensed-media and AI-generated-shot adapter routing, per-shot
safe fallback, plus optional local TTS/subtitle/Whisper execution. Strategy
remains entirely in ChatGPT's production contract; this module only executes.
"""

from __future__ import annotations

from pathlib import Path

from promotion import content_factory, media_adapters, speech_pipeline, video_worker
from promotion import content_factory_v2_finalization_patch as finalization


_INSTALLED = False
_ORIGINAL = {}
_SEGMENT_FALLBACKS = {}


def _asset_buckets(video, data):
    buckets = _ORIGINAL["asset_buckets"](video, data)
    adapters = media_adapters.list_assets(video.get("campaign_id"))
    buckets["licensed"] = adapters.get("licensed") or []
    buckets["generated_adapter"] = adapters.get("generated") or []
    buckets["video_id"] = video.get("id")
    buckets["campaign_id"] = video.get("campaign_id")
    return buckets


def _pick(items, cursor_name, cursors, shot_id=None):
    if not items:
        return None
    if shot_id:
        matched = [x for x in items if str(x.get("shot_id") or "") == str(shot_id)]
        if matched:
            items = matched
    index = int(cursors.get(cursor_name, 0)) % len(items)
    cursors[cursor_name] = int(cursors.get(cursor_name, 0)) + 1
    return items[index]


def _route_shot(shot, buckets, cursors):
    chain = shot.get("source_preference") or ["local_real", "licensed_external", "ai_generated", "info_card"]
    video_id = buckets.get("video_id")
    campaign_id = buckets.get("campaign_id")
    for source_type in chain:
        if source_type == "local_real" and buckets.get("real"):
            asset = _pick(buckets["real"], "real", cursors)
            return source_type, asset, "使用本地真实素材"
        if source_type == "licensed_external":
            asset = _pick(buckets.get("licensed") or [], "licensed", cursors)
            if asset:
                return source_type, asset, "使用已验证商业授权的公开素材"
            media_adapters.request_asset(video_id, campaign_id, shot, source_type)
        if source_type == "ai_generated" and not shot.get("required_real"):
            adapter_asset = _pick(
                buckets.get("generated_adapter") or [], "generated_adapter", cursors,
                shot.get("shot_id"),
            )
            if adapter_asset:
                return source_type, adapter_asset, "使用已批准视觉生成器产出的AI辅助镜头"
            if buckets.get("synthetic"):
                asset = _pick(buckets["synthetic"], "synthetic", cursors)
                return source_type, asset, "使用已入库AI辅助镜头，并保持AI辅助标识"
            media_adapters.request_asset(video_id, campaign_id, shot, source_type)
        if source_type == "brand_card" and buckets.get("brand"):
            asset = _pick(buckets["brand"], "brand", cursors)
            return source_type, asset, "使用品牌素材"
        if source_type == "info_card":
            return "info_card", None, "素材不足时使用知识信息卡，不伪造真实案例"
    return "info_card", None, "素材适配链耗尽，自动安全降级为知识信息卡"


def _shot_id_from_segment(path):
    stem = Path(path).stem
    if "_" not in stem:
        return stem
    return stem.split("_", 1)[1]


def _render_segment(ffmpeg, source, output, duration, width, height, fps, worker):
    """Downgrade a single unreadable source instead of failing the whole video.

    If FFmpeg itself is unavailable/broken, rendering the fallback card also
    fails and the base worker's normal whole-job retry policy remains active.
    """
    try:
        return _ORIGINAL["render_segment"](ffmpeg, source, output, duration, width, height, fps, worker)
    except Exception as error:
        shot_id = _shot_id_from_segment(output)
        fallback = Path(output).with_suffix(".fallback.png")
        try:
            video_worker._card(
                fallback,
                "当前镜头素材暂不可用",
                "系统已自动切换为安全说明画面，不会伪造真实服务现场",
                "#b45309",
                badge="卡嘴子 · 自动降级",
                footnote="原素材读取失败 · 已记录原因并继续生产",
            )
            result = _ORIGINAL["render_segment"](
                ffmpeg, fallback, output, duration, width, height, fps, worker
            )
            _SEGMENT_FALLBACKS[shot_id] = str(error)[:500]
            return result
        except Exception:
            raise error


def _status():
    value = _ORIGINAL["status"]()
    value["media_adapters"] = media_adapters.status()
    value["speech_pipeline"] = speech_pipeline.status()
    value["shot_failure_policy"] = "单镜头素材解码失败时自动降级为信息卡；FFmpeg系统故障才触发整条任务重试"
    return value


def _apply_segment_fallbacks(source_summary):
    updated = []
    for item in source_summary or []:
        value = dict(item) if isinstance(item, dict) else {"note": str(item)}
        shot_id = str(value.get("shot_id") or "")
        error = _SEGMENT_FALLBACKS.get(shot_id)
        if error:
            value.update({
                "source": "info_card",
                "asset_id": None,
                "disclosure": "信息卡",
                "note": f"原计划素材渲染失败，已自动安全降级：{error}",
                "render_fallback": True,
            })
        updated.append(value)
    return updated


def _render_inner(video_id):
    _SEGMENT_FALLBACKS.clear()
    result = _ORIGINAL["render_inner"](video_id)
    output = Path(str(result.get("output") or ""))
    candidate = result.get("candidate") or {}
    if not output.is_file() or not candidate.get("id"):
        return result

    data = content_factory._load()
    video = content_factory._by_id(data.get("videos", []), video_id, "视频任务")
    plan = video.get("production_plan") if isinstance(video.get("production_plan"), dict) else {}
    ffmpeg = video_worker.find_ffmpeg()
    enhancements = speech_pipeline.enhance_final(video_id, plan, output, ffmpeg) if ffmpeg else {
        "subtitle": {"status": "not_run"}, "tts": {"status": "not_run"},
        "whisper_qc": {"status": "not_run", "passed": None},
    }
    spec = plan.get("output") or {}
    technical_qc = video_worker._technical_qc(
        ffmpeg, output, int(spec.get("width") or 1080), int(spec.get("height") or 1920)
    ) if ffmpeg else {"passed": False, "error": "ffmpeg unavailable after enhancement"}
    source_summary = _apply_segment_fallbacks(candidate.get("source_summary") or [])
    finished_candidate, finished_video = finalization.finish_enhancements(
        video_id, candidate["id"], enhancements, technical_qc, source_summary=source_summary
    )
    result["candidate"] = finished_candidate
    result["speech_pipeline"] = enhancements
    result["status"] = "awaiting_chatgpt_qc" if finished_video.get("status") == "等待ChatGPT质检" else "post_processing_failed"
    result["shot_render_fallbacks"] = dict(_SEGMENT_FALLBACKS)
    _SEGMENT_FALLBACKS.clear()
    return result


def install():
    global _INSTALLED
    if _INSTALLED:
        return
    _ORIGINAL.update({
        "asset_buckets": video_worker._asset_buckets,
        "route_shot": video_worker._route_shot,
        "render_segment": video_worker._render_segment,
        "status": video_worker.status,
        "render_inner": video_worker._render_inner,
    })
    video_worker._asset_buckets = _asset_buckets
    video_worker._route_shot = _route_shot
    video_worker._render_segment = _render_segment
    video_worker.status = _status
    video_worker._render_inner = _render_inner

    # The HTTP server imported status/render aliases before this extension.
    try:
        from backend import server
        server.video_worker_status = _status
        server.render_local_video = video_worker.render
    except (ImportError, AttributeError):
        pass
    _INSTALLED = True


install()
