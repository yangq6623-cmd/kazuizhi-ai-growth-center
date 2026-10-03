"""Install R8-23.2 task idempotency, stale recovery and pilot governance."""
from __future__ import annotations

from urllib.parse import urlsplit

from backend import server
from core import r7_engine
from core import r8_23_2_runtime_safety as safety

_INSTALLED = False


def install():
    global _INSTALLED
    if _INSTALLED:
        return

    original_create_job = r7_engine.create_job
    original_run_due_jobs = r7_engine.run_due_jobs

    if not getattr(original_create_job, "_r8232_wrapped", False):
        def create_job(payload):
            duplicate = safety.duplicate_job(payload if isinstance(payload, dict) else {})
            if duplicate:
                result = dict(duplicate)
                result["idempotent_reuse"] = True
                result["idempotency_rule"] = "same kind/title/due or recent unscheduled equivalent"
                return result
            return original_create_job(payload)
        create_job._r8232_wrapped = True
        r7_engine.create_job = create_job

    if not getattr(original_run_due_jobs, "_r8232_wrapped", False):
        def run_due_jobs():
            recovery = safety.recover_stale_running_jobs()
            result = original_run_due_jobs()
            if isinstance(result, dict):
                result["r8_23_2_recovery"] = recovery
            return result
        run_due_jobs._r8232_wrapped = True
        r7_engine.run_due_jobs = run_due_jobs

    original_get = server.DashboardHandler.do_GET

    def do_get(handler):
        path = urlsplit(handler.path).path
        try:
            if path == "/api/r8-23-2/task-integrity":
                handler._json_ok(safety.task_integrity())
                return
            if path == "/api/r8-23-2/social-pilot":
                handler._json_ok(safety.social_pilot())
                return
            if path == "/api/r8-23-2/metric-semantics":
                handler._json_ok(safety.metric_semantics())
                return
        except (OSError, ValueError, RuntimeError, TypeError, KeyError, AttributeError) as error:
            handler._json_error(400, error)
            return
        return original_get(handler)

    server.DashboardHandler.do_GET = do_get
    server.DashboardHandler._kz_r8_23_2_runtime_safety = True
    _INSTALLED = True


install()
