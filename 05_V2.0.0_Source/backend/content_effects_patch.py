"""HTTP endpoint for verified 24h/72h/7d content performance feedback."""

import json
from urllib.parse import urlsplit

from backend import server as _server
from promotion.content_effects import record_effect_metrics


if not getattr(_server.DashboardHandler, "_kz_content_effects_patched", False):
    _original_do_post = _server.DashboardHandler.do_POST

    def _do_post(self):
        path = urlsplit(self.path).path
        if path == "/api/content-factory/effect-metrics":
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
                self._json_ok(record_effect_metrics(payload), code=201)
            except (ValueError, TypeError, json.JSONDecodeError) as error:
                self._json_error(400, error)
            return
        return _original_do_post(self)

    _server.DashboardHandler.do_POST = _do_post
    _server.DashboardHandler._kz_content_effects_patched = True
