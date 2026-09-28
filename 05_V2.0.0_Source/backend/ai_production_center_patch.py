"""Local HTTP boundary for the standalone AI Content Production Center."""
from __future__ import annotations

import json
from urllib.parse import urlsplit

from backend import server as _server
from promotion import ai_production_center as center


def _origin_allowed(handler):
    origin = handler.headers.get("Origin")
    allowed = {f"http://127.0.0.1:{handler.server.server_port}", f"http://localhost:{handler.server.server_port}"}
    return not origin or origin in allowed


def _body(handler):
    length = int(handler.headers.get("Content-Length", "0") or 0)
    if length <= 0 or length > 128 * 1024:
        raise ValueError("请求内容不能为空或超过限制")
    return json.loads(handler.rfile.read(length) or b"{}")


if not getattr(_server.DashboardHandler, "_kz_ai_production_center_patched", False):
    _get = _server.DashboardHandler.do_GET
    _post = _server.DashboardHandler.do_POST

    def _do_get(self):
        if urlsplit(self.path).path == "/api/ai-content-center":
            self._json_ok(center.dashboard()); return
        return _get(self)

    def _do_post(self):
        path = urlsplit(self.path).path
        actions = {
            "/api/ai-content-center/projects": center.create_project,
            "/api/ai-content-center/assets": center.add_asset,
            "/api/ai-content-center/storyboards/generate": center.create_storyboard_draft,
            "/api/ai-content-center/candidates/queue": center.queue_candidate_generation,
        }
        action = actions.get(path)
        if not action:
            return _post(self)
        if not _origin_allowed(self):
            self._json_error(403, "不允许跨站修改本地内容中心"); return
        try:
            self._json_ok(action(_body(self)), code=201)
        except (ValueError, TypeError, json.JSONDecodeError) as error:
            self._json_error(400, error)

    _server.DashboardHandler.do_GET = _do_get
    _server.DashboardHandler.do_POST = _do_post
    _server.DashboardHandler._kz_ai_production_center_patched = True
