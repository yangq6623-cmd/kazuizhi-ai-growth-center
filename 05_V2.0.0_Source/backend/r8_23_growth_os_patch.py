"""Production integration for R8-23 Final Autonomous Growth OS."""
from __future__ import annotations

import json
import time
from urllib.parse import urlsplit

from backend import server
from core import r8_22_autonomous_convergence as convergence
from core import r8_23_growth_operating_system as growth_os
from integrations import ai_gateway, search_engine_submitter, seo_public_deployer
from core import seo_geo_autonomy
from promotion import video_worker

_INSTALLED = False
_ORIGINAL_CONTROLLER_TICK = convergence.controller_tick
_ORIGINAL_AI_RUN = ai_gateway.run_once
_ORIGINAL_SEO_GEO_RUN = seo_geo_autonomy.run_once
_ORIGINAL_VIDEO_RUN = video_worker.run_pending
_ORIGINAL_DEPLOY_RUN = seo_public_deployer.deploy_pending
_ORIGINAL_SEARCH_RUN = search_engine_submitter.submit_pending
GROWTH_CYCLE_INTERVAL_SECONDS = 300
_LAST_GROWTH_CYCLE_MONOTONIC = 0.0
_LAST_GROWTH_PLAN_ID = None


def _origin_allowed(handler):
    origin = handler.headers.get("Origin")
    return not origin or origin in {
        f"http://127.0.0.1:{handler.server.server_port}",
        f"http://localhost:{handler.server.server_port}",
    }


def _read_json(handler):
    length = int(handler.headers.get("Content-Length", "0") or 0)
    if length < 0 or length > 64 * 1024:
        raise ValueError("请求内容过大")
    return json.loads(handler.rfile.read(length) or b"{}") if length else {}


def _success(result):
    if not isinstance(result, dict):
        return True
    if result.get("skipped"):
        return None
    if result.get("ok") is False:
        return False
    if int(result.get("failed_count") or 0) > 0 and int(result.get("submitted_count") or result.get("processed") or 0) == 0:
        return False
    return True


def _controller_tick():
    global _LAST_GROWTH_CYCLE_MONOTONIC, _LAST_GROWTH_PLAN_ID
    result = _ORIGINAL_CONTROLLER_TICK()
    mission = convergence.ensure_command_mission() or {}
    plan = convergence.ensure_controller_plan(mission) if mission else {}
    plan_id = str(plan.get("plan_id") or "")
    current = time.monotonic()
    due = bool(plan_id and (plan_id != _LAST_GROWTH_PLAN_ID or current - _LAST_GROWTH_CYCLE_MONOTONIC >= GROWTH_CYCLE_INTERVAL_SECONDS))
    if not due:
        result["r8_23"] = {"deferred": True, "reason": "stable_growth_cycle_throttle", "plan_id": plan_id}
        return result
    try:
        result["r8_23"] = growth_os.decision_cycle(mission, plan, reason="controller_tick")
        growth_os.record_utilization("chatgpt_controller", success=True, reason="controller_cycle", context={"mission_id": mission.get("mission_id"), "plan_id": plan_id})
        _LAST_GROWTH_CYCLE_MONOTONIC = current
        _LAST_GROWTH_PLAN_ID = plan_id
    except (OSError, ValueError, RuntimeError, TypeError, KeyError, AttributeError) as error:
        result["r8_23"] = {"degraded": True, "reason": str(error)}
    return result


def _ai_run(*args, **kwargs):
    try:
        result = _ORIGINAL_AI_RUN(*args, **kwargs)
    except Exception as error:
        try:
            route = ai_gateway.gateway_status().get("active_route")
            capability = "local_model" if route == "local" else "doubao_cloud"
            growth_os.record_utilization(capability, success=False, reason=str(error), context={"source": "ai_gateway"})
        finally:
            raise
    route = ai_gateway.gateway_status().get("active_route")
    capability = "local_model" if route == "local" else "doubao_cloud"
    growth_os.record_utilization(capability, success=_success(result), result=result, reason="ai_gateway_run", context={"route": route})
    return result


def _seo_geo_run(*args, **kwargs):
    try:
        result = _ORIGINAL_SEO_GEO_RUN(*args, **kwargs)
    except Exception as error:
        growth_os.record_utilization("seo_website", success=False, reason=str(error), context={"source": "seo_geo_autonomy"})
        raise
    growth_os.record_utilization("seo_website", success=_success(result), result=result, reason="seo_geo_autonomy_cycle", context={"source": "seo_geo_autonomy"})
    return result


def _video_run(*args, **kwargs):
    try:
        result = _ORIGINAL_VIDEO_RUN(*args, **kwargs)
    except Exception as error:
        gpu = growth_os.gpu_status()
        if gpu.get("rtx3060"):
            growth_os.record_utilization("rtx3060", success=False, reason=str(error), context={"source": "video_worker", "gpu_detected": True})
        raise
    gpu = growth_os.gpu_status()
    if gpu.get("rtx3060") and isinstance(result, dict) and not result.get("skipped"):
        growth_os.record_utilization("rtx3060", success=_success(result), result=result, reason="video_worker_with_3060_detected", context={"source": "video_worker", "gpus": gpu.get("gpus")})
    return result


def _deploy_run(*args, **kwargs):
    try:
        result = _ORIGINAL_DEPLOY_RUN(*args, **kwargs)
    except Exception as error:
        growth_os.record_utilization("seo_website", success=False, reason=str(error), context={"source": "seo_public_deployer"})
        raise
    growth_os.record_utilization("seo_website", success=_success(result), result=result, reason="public_deploy_attempt", context={"source": "seo_public_deployer"})
    return result


def _search_run(*args, **kwargs):
    try:
        result = _ORIGINAL_SEARCH_RUN(*args, **kwargs)
    except Exception as error:
        growth_os.record_utilization("search_submission", success=False, reason=str(error), context={"source": "search_engine_submitter"})
        raise
    growth_os.record_utilization("search_submission", success=_success(result), result=result, reason="search_submit_attempt", context={"source": "search_engine_submitter"})
    return result


def _serve_autonomous_ops(handler):
    web = server.get_web_path()
    source = "\n;\n".join([
        (web / "autonomous-ops.js").read_text(encoding="utf-8"),
        (web / "r8_22_autonomy.js").read_text(encoding="utf-8"),
        (web / "r8_23_growth_os.js").read_text(encoding="utf-8"),
    ])
    data = source.encode("utf-8")
    handler.send_response(200)
    handler.send_header("Content-Type", "application/javascript; charset=utf-8")
    handler.send_header("Cache-Control", "no-store")
    handler.send_header("Content-Length", str(len(data)))
    handler.end_headers()
    handler.wfile.write(data)


def install():
    global _INSTALLED
    if _INSTALLED:
        return

    convergence.controller_tick = _controller_tick
    ai_gateway.run_once = _ai_run
    seo_geo_autonomy.run_once = _seo_geo_run
    video_worker.run_pending = _video_run
    seo_public_deployer.deploy_pending = _deploy_run
    search_engine_submitter.submit_pending = _search_run

    original_get = server.DashboardHandler.do_GET
    original_post = server.DashboardHandler.do_POST

    def do_get(handler):
        path = urlsplit(handler.path).path
        try:
            if path == "/autonomous-ops.js":
                _serve_autonomous_ops(handler)
                return
            if path == "/api/r8-23/growth-os":
                handler._json_ok(growth_os.snapshot())
                return
            if path == "/api/r8-23/growth-os/employees":
                handler._json_ok({"items": list(growth_os.AI_EMPLOYEES), "count": len(growth_os.AI_EMPLOYEES)})
                return
            if path == "/api/r8-23/growth-os/capabilities":
                handler._json_ok({"items": growth_os.capability_status(), "truth": "已连接不等于已调用；调用不等于外部成功。"})
                return
            if path == "/api/r8-23/growth-os/utilization":
                snap = growth_os.snapshot()
                handler._json_ok({"items": [{"id": row.get("id"), "name": row.get("name"), "ready": row.get("ready"), "state": row.get("state"), "utilization": row.get("utilization")} for row in snap.get("capabilities", [])]})
                return
        except (OSError, ValueError, RuntimeError, TypeError, KeyError, AttributeError) as error:
            handler._json_error(400, error)
            return
        return original_get(handler)

    def do_post(handler):
        path = urlsplit(handler.path).path
        if path != "/api/r8-23/growth-os/run":
            return original_post(handler)
        if not _origin_allowed(handler):
            handler._json_error(403, "Cross-origin changes are not allowed")
            return
        try:
            payload = _read_json(handler)
            result = convergence.controller_tick()
            handler._json_ok({"result": result, "growth_os": growth_os.snapshot(), "reason": payload.get("reason") or "manual_controller_tick"})
        except (OSError, ValueError, RuntimeError, TypeError, KeyError, AttributeError, json.JSONDecodeError) as error:
            handler._json_error(400, error)

    server.DashboardHandler.do_GET = do_get
    server.DashboardHandler.do_POST = do_post
    server.DashboardHandler._kz_r8_23_growth_os = True
    _INSTALLED = True


install()
