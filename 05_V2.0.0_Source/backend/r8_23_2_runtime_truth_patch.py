"""R8-23.2 Pilot HTTP integration.

Adds one consistent owner-facing runtime contract without removing legacy APIs.
"""
from __future__ import annotations

from urllib.parse import urlsplit

from backend import server
from core import r8_23_2_runtime_truth as runtime_truth

_INSTALLED = False


def install():
    global _INSTALLED
    if _INSTALLED:
        return
    original_get = server.DashboardHandler.do_GET
    original_post = server.DashboardHandler.do_POST

    def do_get(handler):
        path = urlsplit(handler.path).path
        try:
            if path in {"/api/r8-23-2/pilot", "/api/r8-23-2/runtime-truth"}:
                handler._json_ok(runtime_truth.snapshot())
                return
            if path == "/api/version":
                handler._json_ok(runtime_truth.release_manifest())
                return
            if path == "/api/readiness":
                handler._json_ok(runtime_truth.readiness())
                return
            if path == "/api/health":
                ready = runtime_truth.readiness()
                handler._json_ok({
                    "alive": True,
                    "status": "ok" if ready.get("state") != "BLOCKED" else "blocked",
                    "phase": runtime_truth.PILOT_VERSION,
                    "readiness": ready.get("state"),
                    "generated_at": runtime_truth.now_iso(),
                })
                return
            if path in {"/api/runtime-health", "/api/r8-23-2/runtime-health"}:
                snap = runtime_truth.snapshot()
                handler._json_ok({
                    "alive": True,
                    "readiness": snap.get("readiness"),
                    "truth": snap.get("truth"),
                    "queue": snap.get("queue"),
                    "release": snap.get("release"),
                    "generated_at": runtime_truth.now_iso(),
                })
                return
            if path == "/api/r8-23-2/queue":
                handler._json_ok(runtime_truth.queue_diagnostics())
                return
            if path == "/api/r8-23-2/decision-pack":
                handler._json_ok(runtime_truth.decision_pack())
                return
        except (OSError, ValueError, RuntimeError, TypeError, KeyError, AttributeError) as error:
            handler._json_error(400, error)
            return
        return original_get(handler)

    def do_post(handler):
        path = urlsplit(handler.path).path
        try:
            if path == "/api/r8-23-2/model-route":
                length = int(handler.headers.get("Content-Length", "0") or 0)
                if length < 0 or length > 32 * 1024:
                    raise ValueError("请求内容过大")
                import json
                body = json.loads(handler.rfile.read(length) or b"{}") if length else {}
                kind = body.get("task_kind") or "general"
                quality = body.get("local_quality")
                handler._json_ok(runtime_truth.model_route(kind, local_quality=quality))
                return
        except (OSError, ValueError, RuntimeError, TypeError, KeyError, AttributeError) as error:
            handler._json_error(400, error)
            return
        return original_post(handler)

    server.DashboardHandler.do_GET = do_get
    server.DashboardHandler.do_POST = do_post
    _INSTALLED = True


install()
