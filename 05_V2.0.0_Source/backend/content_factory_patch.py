"""Runtime HTTP routes used by the R8 content-factory review UI."""

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


if not getattr(_server.DashboardHandler, "_kz_content_factory_patched", False):
    _original_do_get = _server.DashboardHandler.do_GET

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

    _server.DashboardHandler.do_GET = _do_get
    _server.DashboardHandler._kz_content_factory_patched = True
