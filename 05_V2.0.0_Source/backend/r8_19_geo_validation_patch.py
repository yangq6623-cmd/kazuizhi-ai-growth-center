"""R8-19 Phase 1 HTTP bridge for truth-gated GEO validation.

This patch is deliberately additive. Existing SEO/GEO endpoints remain intact.
The new surface orchestrates GEO work but never treats a generic/local model as
external GEO proof.
"""
from __future__ import annotations

import json
from urllib.parse import parse_qs, urlsplit

from backend import server
from core.geo_validation import (
    audit_events,
    bootstrap_question_set,
    claim_next_task,
    create_and_enqueue_plan,
    dashboard,
    fail_task,
    manual_requirements,
    pause_task,
    question_set,
    queue_summary,
    receipts,
    record_result,
    resume_task,
    retry_task,
    set_decision,
)

_INSTALLED = False


def _origin_allowed(handler):
    origin = handler.headers.get("Origin")
    return not origin or origin in {
        f"http://127.0.0.1:{handler.server.server_port}",
        f"http://localhost:{handler.server.server_port}",
    }


def _read_json(handler):
    length = int(handler.headers.get("Content-Length", "0") or 0)
    if length < 0 or length > 256 * 1024:
        raise ValueError("请求内容过大")
    return json.loads(handler.rfile.read(length) or b"{}") if length else {}


def _task_id(payload):
    value = str((payload or {}).get("task_id") or "").strip()
    if not value:
        raise ValueError("task_id_required")
    return value


def install():
    global _INSTALLED
    if _INSTALLED:
        return
    original_get = server.DashboardHandler.do_GET
    original_post = server.DashboardHandler.do_POST

    def do_get(handler):
        parsed = urlsplit(handler.path)
        path = parsed.path
        query = parse_qs(parsed.query)
        if path == "/api/r8-19/geo":
            handler._json_ok(dashboard())
            return
        if path == "/api/r8-19/geo/questions":
            handler._json_ok(question_set())
            return
        if path == "/api/r8-19/geo/queue":
            handler._json_ok(queue_summary())
            return
        if path == "/api/r8-19/geo/receipts":
            handler._json_ok({"receipts": receipts(query.get("limit", [200])[0])})
            return
        if path == "/api/r8-19/geo/manual":
            handler._json_ok(manual_requirements())
            return
        if path == "/api/r8-19/geo/audit":
            handler._json_ok({"events": audit_events(query.get("limit", [200])[0])})
            return
        return original_get(handler)

    def do_post(handler):
        path = urlsplit(handler.path).path
        supported = {
            "/api/r8-19/geo/bootstrap",
            "/api/r8-19/geo/plan",
            "/api/r8-19/geo/run",
            "/api/r8-19/geo/receipt",
            "/api/r8-19/geo/fail",
            "/api/r8-19/geo/pause",
            "/api/r8-19/geo/resume",
            "/api/r8-19/geo/retry",
            "/api/r8-19/geo/decision",
        }
        if path not in supported:
            return original_post(handler)
        if not _origin_allowed(handler):
            handler._json_error(403, "Cross-origin changes are not allowed")
            return
        try:
            payload = _read_json(handler)
            if path == "/api/r8-19/geo/bootstrap":
                result = bootstrap_question_set(force=bool(payload.get("force")))
            elif path == "/api/r8-19/geo/plan":
                result = create_and_enqueue_plan(
                    limit=payload.get("limit", 10),
                    provider=payload.get("provider", "external_ai"),
                    test_method=payload.get("test_method", "browser"),
                    mission_id=payload.get("mission_id", ""),
                    question_ids=payload.get("question_ids") or None,
                )
            elif path == "/api/r8-19/geo/run":
                # The caller must provide a verified external executor contract.
                # Without it the task truthfully becomes authorization_required.
                result = claim_next_task(payload.get("executor") or payload)
            elif path == "/api/r8-19/geo/receipt":
                result = record_result(payload)
            elif path == "/api/r8-19/geo/fail":
                result = fail_task(
                    _task_id(payload),
                    payload.get("reason") or "execution_failed",
                )
            elif path == "/api/r8-19/geo/pause":
                result = pause_task(_task_id(payload))
            elif path == "/api/r8-19/geo/resume":
                result = resume_task(_task_id(payload))
            elif path == "/api/r8-19/geo/retry":
                result = retry_task(
                    _task_id(payload),
                    approved_by=str(payload.get("approved_by") or "chatgpt"),
                )
            else:
                result = set_decision(payload)
            handler._json_ok({"result": result, "geo": dashboard()})
        except (OSError, ValueError, RuntimeError, TypeError, KeyError, json.JSONDecodeError) as error:
            handler._json_error(400, error)

    server.DashboardHandler.do_GET = do_get
    server.DashboardHandler.do_POST = do_post
    server.DashboardHandler._kz_r8_19_geo_validation = True
    _INSTALLED = True


install()
