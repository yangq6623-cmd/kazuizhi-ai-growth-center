"""Runtime HTTP routes used by the R8 content-factory review UI."""

import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

from backend import server as _server
from promotion import content_factory


def _registered_candidate(video_id, candidate_id):
    data = content_factory._load()
    video = content_factory._by_id(data.get("videos", []), video_id, "视频任务")
    candidate = content_factory._by_id(video.get("candidates", []), candidate_id, "成片候选")
    path = Path(str(candidate.get("local_path") or ""))
    if not candidate.get("exists") or not path.is_file():
        raise ValueError("成片文件不存在")
    return path


def _serve_mp4(handler, path):
    size = path.stat().st_size
    range_header = str(handler.headers.get("Range") or "").strip()
    start, end = 0, size - 1
    partial = False
    if range_header.startswith("bytes="):
        try:
            spec = range_header[6:].split(",", 1)[0]
            left, right = spec.split("-", 1)
            if left:
                start = max(0, int(left))
            if right:
                end = min(size - 1, int(right))
            if not left and right:
                suffix = min(size, int(right))
                start = size - suffix
                end = size - 1
            if start > end or start >= size:
                raise ValueError
            partial = True
        except (ValueError, TypeError):
            handler.send_response(416)
            handler.send_header("Content-Range", f"bytes */{size}")
            handler.end_headers()
            return

    length = end - start + 1
    handler.send_response(206 if partial else 200)
    handler.send_header("Content-Type", "video/mp4")
    handler.send_header("Accept-Ranges", "bytes")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(length))
    if partial:
        handler.send_header("Content-Range", f"bytes {start}-{end}/{size}")
    handler.end_headers()
    try:
        with path.open("rb") as handle:
            handle.seek(start)
            remaining = length
            while remaining > 0:
                chunk = handle.read(min(1024 * 256, remaining))
                if not chunk:
                    break
                handler.wfile.write(chunk)
                remaining -= len(chunk)
    except (BrokenPipeError, ConnectionResetError):
        pass


def _enhanced_handoff(limit=20):
    """Compatibility handoff used before the completion extension installs."""
    data = content_factory._load()
    requests = []
    for video in data.get("videos", []):
        if video.get("status") not in {"等待ChatGPT策划", "退回重做"}:
            continue
        campaign = next((x for x in data.get("campaigns", []) if x.get("id") == video.get("campaign_id")), None)
        if not campaign:
            continue
        previous = video.get("production_plan") if isinstance(video.get("production_plan"), dict) else None
        review = video.get("review") if isinstance(video.get("review"), dict) else None
        requests.append({
            "video_id": video["id"],
            "campaign_id": campaign["id"],
            "region": campaign.get("region"),
            "service": campaign.get("service"),
            "growth_goal": campaign.get("goal"),
            "user_problem": campaign.get("title"),
            "evidence": campaign.get("evidence"),
            "available_local_assets": len([
                x for x in data.get("assets", [])
                if x.get("campaign_id") == campaign["id"] and x.get("exists")
            ]),
            "local_material_optional": True,
            "owner_review": review,
            "previous_chatgpt_qc": video.get("chatgpt_qc"),
            "previous_plan_version": video.get("plan_version") or 0,
            "previous_topic": (previous or {}).get("topic"),
            "previous_titles": (previous or {}).get("titles") or [],
            "instruction": (
                "由ChatGPT作为唯一总控制生成或重做选题深化、痛点、标题、深层脚本、分镜、素材决策、"
                "平台适配与质检标准。若存在owner_review、previous_chatgpt_qc和previous_*字段，"
                "必须避免机械重复被退回版本。按kazuizhi-content-production/v1返回content_production指令。"
            ),
        })
        if len(requests) >= limit:
            break
    return {"schema": "kazuizhi-content-production-requests/v1", "items": requests, "count": len(requests)}


# The completion extension installed by run.py replaces this compatibility
# helper with the richer asset/rule/QC-aware handoff.
content_factory.pending_chatgpt_handoff = _enhanced_handoff


if not getattr(_server.DashboardHandler, "_kz_content_factory_patched", False):
    _original_do_get = _server.DashboardHandler.do_GET
    _original_do_post = _server.DashboardHandler.do_POST

    def _do_get(self):
        parsed = urlsplit(self.path)
        if parsed.path == "/api/content-factory/candidate-file":
            query = parse_qs(parsed.query)
            video_id = str((query.get("video_id") or [""])[0]).strip()
            candidate_id = str((query.get("candidate_id") or [""])[0]).strip()
            if not video_id or not candidate_id:
                self._json_error(400, "video_id 和 candidate_id 不能为空")
                return
            try:
                path = _registered_candidate(video_id, candidate_id)
                _serve_mp4(self, path)
            except (ValueError, OSError) as error:
                self._json_error(404, error)
            return
        return _original_do_get(self)

    def _do_post(self):
        parsed = urlsplit(self.path)
        dedicated = {
            "/api/content-factory/chatgpt-plan",
            "/api/content-factory/chatgpt-qc",
            "/api/content-factory/review",
        }
        if parsed.path in dedicated:
            origin = self.headers.get("Origin")
            allowed_origins = {
                f"http://127.0.0.1:{self.server.server_port}",
                f"http://localhost:{self.server.server_port}",
            }
            if origin and origin not in allowed_origins:
                self._json_error(403, "Cross-origin changes are not allowed")
                return
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > 64 * 1024:
                self._json_error(413 if length > 64 * 1024 else 400, "请求大小不正确")
                return
            try:
                payload = json.loads(self.rfile.read(length) or b"{}")
                if parsed.path == "/api/content-factory/chatgpt-plan":
                    result = content_factory.apply_chatgpt_plan(payload)
                    self._json_ok(result, code=201)
                    return
                if parsed.path == "/api/content-factory/chatgpt-qc":
                    handler = getattr(content_factory, "apply_chatgpt_qc", None)
                    if not callable(handler):
                        raise ValueError("当前运行时尚未启用ChatGPT成片质检")
                    result = handler(payload)
                    self._json_ok(result)
                    return
                result = content_factory.review_video(payload)
                # Compatibility fallback for runtimes without the completion layer.
                if str(payload.get("decision") or "").strip() in {"退回重做", "退回修改", "整片重做", "重做指定镜头"} and result.get("status") == "退回重做":
                    result = content_factory.update_runtime_state(
                        result["id"], status="等待ChatGPT策划",
                        bottleneck="老板已退回当前成片，等待ChatGPT重新策划",
                        auto_action="把上一版方案和审核结果回传ChatGPT，生成新版本；无需人工处理中间步骤",
                    )
                self._json_ok(result)
            except (ValueError, TypeError, json.JSONDecodeError) as error:
                self._json_error(400, error)
            return
        return _original_do_post(self)

    _server.DashboardHandler.do_GET = _do_get
    _server.DashboardHandler.do_POST = _do_post
    _server.DashboardHandler._kz_content_factory_patched = True
