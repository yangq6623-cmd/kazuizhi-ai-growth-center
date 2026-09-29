"""Local-only HTTP surface for the R8-18 release manifest and evidence ledger."""
from __future__ import annotations

import json
from urllib.parse import parse_qs, urlsplit

from backend import server
from core.growth_evidence import refresh_legacy_import, status as evidence_status
from core.version import release_manifest

_INSTALLED = False


def _origin_allowed(handler):
    origin = handler.headers.get("Origin")
    return not origin or origin in {f"http://127.0.0.1:{handler.server.server_port}", f"http://localhost:{handler.server.server_port}"}


def _read_json(handler):
    length = int(handler.headers.get("Content-Length", "0") or 0)
    if length < 0 or length > 16 * 1024:
        raise ValueError("请求内容过大")
    return json.loads(handler.rfile.read(length) or b"{}") if length else {}


def install():
    global _INSTALLED
    if _INSTALLED:
        return
    original_get = server.DashboardHandler.do_GET
    original_post = server.DashboardHandler.do_POST

    def do_get(handler):
        parsed = urlsplit(handler.path)
        if parsed.path == "/api/r8-18/release-manifest":
            handler._json_ok(release_manifest())
            return
        if parsed.path == "/api/r8-18/evidence-ledger":
            query = parse_qs(parsed.query)
            handler._json_ok(evidence_status(query.get("limit", [100])[0]))
            return
        return original_get(handler)

    def do_post(handler):
        path = urlsplit(handler.path).path
        if path != "/api/r8-18/evidence-ledger/refresh":
            return original_post(handler)
        if not _origin_allowed(handler):
            handler._json_error(403, "Cross-origin changes are not allowed")
            return
        try:
            _read_json(handler)
            handler._json_ok({"result": refresh_legacy_import(), "ledger": evidence_status()})
        except (OSError, ValueError, RuntimeError, TypeError, KeyError, json.JSONDecodeError) as error:
            handler._json_error(400, error)

    server.DashboardHandler.do_GET = do_get
    server.DashboardHandler.do_POST = do_post
    server.DashboardHandler._kz_r8_18_evidence_ledger = True
    _INSTALLED = True


install()

# R8-18 #71: load the truthful final-cut executor after the HTTP server and
# production-monitor surfaces are available. This automatically resumes a #70
# "完整成片合成" task without regenerating the already completed shot candidates.
from backend import final_render_patch as _final_render_patch  # noqa: E402,F401

# #71.1/#74: probe real NVENC support, fall back to libx264 when necessary,
# publish immutable versioned finals, and close duplicate final-render tasks.
from backend import final_render_compat_patch as _final_render_compat_patch  # noqa: E402,F401

# R8-18 #75: director-grade finalization. Rewrite one coherent audience-facing
# narration, use real TTS duration as the master clock, prefer unused candidate
# clips as B-roll, forbid looping short Wan clips to fake duration, use precise
# subtitles and restrained visual transitions, and generate future 9:16 Wan
# candidates in a native portrait canvas where applicable.
from backend import final_director_v75_patch as _final_director_v75_patch  # noqa: E402,F401

# #75 stability layer: never replay the last candidate to fill a short gap and
# transparently fall back to clean cuts when xfade is unavailable or fails.
from backend import final_director_v75_stability_patch as _final_director_v75_stability_patch  # noqa: E402,F401

# #75 controlled short-video acceptance mode: expose truthful 5s/10s options,
# force an explicitly requested 5-second two-shot test to stay at two shots,
# and route the two newest local image references one-per-shot for continuity.
from backend import short_video_test_patch as _short_video_test_patch  # noqa: E402,F401

# #80 resilience: retry transient local Router/socket failures and, only for the
# explicit 5-second two-shot acceptance path, fall back to truthful text-only
# structure analysis so a temporary Router stall cannot block the whole test.
from backend import short_test_ai_resilience_patch as _short_test_ai_resilience_patch  # noqa: E402,F401

# #82.1 controlled-test director fallback: the 5-second continuity acceptance
# path is not a creative-ideation benchmark.  After the user's text is understood,
# create its exact two-shot director contract locally so a second Router stall
# cannot block real Wan continuity validation. Normal production still uses AI.
from backend import short_test_director_fallback_patch as _short_test_director_fallback_patch  # noqa: E402,F401
