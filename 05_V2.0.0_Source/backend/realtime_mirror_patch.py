"""Runtime HTTP routes for the low-latency Android live mirror."""

from urllib.parse import parse_qs, urlsplit

from backend import server as _server
from integrations.android_live_mirror import live_status, stream_mjpeg


if not getattr(_server.DashboardHandler, "_kz_realtime_mirror_patched", False):
    _original_do_get = _server.DashboardHandler.do_GET

    def _do_get(self):
        parsed = urlsplit(self.path)
        path = parsed.path
        query = parse_qs(parsed.query)

        if path == "/api/r8/device/live-status":
            device_id = str((query.get("device_id") or [""])[0]).strip()
            if not device_id:
                self._json_error(400, "device_id 不能为空")
                return
            self._json_ok(live_status(device_id))
            return

        if path == "/api/r8/device/live":
            device_id = str((query.get("device_id") or [""])[0]).strip()
            if not device_id:
                self._json_error(400, "device_id 不能为空")
                return
            try:
                stream_mjpeg(self, device_id)
            except (ValueError, RuntimeError, OSError) as error:
                # stream_mjpeg validates before sending headers. Runtime stream
                # disconnects are handled inside the transport and do not try to
                # write a second HTTP response.
                try:
                    self._json_error(400, error)
                except (BrokenPipeError, ConnectionResetError, OSError):
                    pass
            return

        return _original_do_get(self)

    _server.DashboardHandler.do_GET = _do_get
    _server.DashboardHandler._kz_realtime_mirror_patched = True
