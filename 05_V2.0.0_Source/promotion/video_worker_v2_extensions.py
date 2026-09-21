"""Execution extensions for the R8 local video worker.

Adds verified licensed-media and AI-generated-shot adapter routing plus optional
local TTS/subtitle/Whisper execution.  Strategy remains entirely in ChatGPT's
production contract; this module only resolves and executes requested sources.
"""

from __future__ import annotations

from pathlib import Path

from promotion import content_factory, media_adapters, speech_pipeline, video_worker


_INSTALLED = False
_ORIGINAL = {}


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


def _status():
    value = _ORIGINAL["status"]()
    value["media_adapters"] = media_adapters.status()
    value["speech_pipeline"] = speech_pipeline.status()
    return value


def _update_candidate(video_id, candidate_id, enhancements, technical_qc):
    data = content_factory._load()
    video = content_factory._by_id(data.get("videos", []), video_id, "视频任务")
    candidate = content_factory._by_id(video.get("candidates", []), candidate_id, "成片候选")
    candidate["enhancements"] = enhancements
    candidate["technical_qc"] = technical_qc
    video["technical_qc"] = technical_qc
    if not technical_qc.get("passed"):
        video["status"] = "异常待处理"
        video["bottleneck"] = "语音/字幕增强后技术质检未通过"
        video["auto_action"] = "保留原始生产记录并进入自动重试/降级流程"
    content_factory._save(data)


def _render_inner(video_id):
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
    _update_candidate(video_id, candidate["id"], enhancements, technical_qc)
    result["candidate"]["enhancements"] = enhancements
    result["candidate"]["technical_qc"] = technical_qc
    result["speech_pipeline"] = enhancements
    return result


def install():
    global _INSTALLED
    if _INSTALLED:
        return
    _ORIGINAL.update({
        "asset_buckets": video_worker._asset_buckets,
        "route_shot": video_worker._route_shot,
        "status": video_worker.status,
        "render_inner": video_worker._render_inner,
    })
    video_worker._asset_buckets = _asset_buckets
    video_worker._route_shot = _route_shot
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
