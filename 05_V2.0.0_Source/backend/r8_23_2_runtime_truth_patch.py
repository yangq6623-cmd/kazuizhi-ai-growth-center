"""Production integration for R8-23.2 Runtime Truth & Closed-Loop Acceptance."""
from __future__ import annotations

import json
from urllib.parse import parse_qs, urlsplit

from backend import server
from core import r7_engine
from core import r8_22_autonomous_convergence as convergence
from core import r8_23_2_runtime_truth as truth
from core import seo_geo_autonomy as seo_core
from integrations import seo_geo_model_collaboration as model_collaboration

_INSTALLED = False
_ORIGINAL_CONTROLLER_TICK = convergence.controller_tick
_ORIGINAL_RUN_DUE_JOBS = r7_engine.run_due_jobs
_ORIGINAL_SEO_GEO_RUN = seo_core.run_once
_ORIGINAL_SEO_GEO_STATUS = seo_core.status


def _origin_allowed(handler):
    origin = handler.headers.get("Origin")
    return not origin or origin in {
        f"http://127.0.0.1:{handler.server.server_port}",
        f"http://localhost:{handler.server.server_port}",
    }


def _read_json(handler):
    length = int(handler.headers.get("Content-Length", "0") or 0)
    if length < 0 or length > 128 * 1024:
        raise ValueError("请求内容过大")
    return json.loads(handler.rfile.read(length) or b"{}") if length else {}


def _controller_tick():
    result = _ORIGINAL_CONTROLLER_TICK()
    try:
        result["r8_23_2"] = truth.controller_tick()
    except (OSError, ValueError, RuntimeError, TypeError, KeyError, AttributeError) as error:
        result["r8_23_2"] = {"degraded": True, "reason": str(error)}
    return result


def _run_due_jobs():
    try:
        truth.govern_queue()
    except (OSError, ValueError, RuntimeError, TypeError, KeyError, AttributeError):
        pass
    result = _ORIGINAL_RUN_DUE_JOBS()
    try:
        truth.govern_queue()
    except (OSError, ValueError, RuntimeError, TypeError, KeyError, AttributeError):
        pass
    return result


def _seo_geo_run(force=False):
    """Run inherited SEO/GEO loop, then real Doubao collaboration at key stages.

    Failure of the cloud collaborator is fail-soft and never erases successful
    local/public/search work.  A Doubao receipt proves only model collaboration.
    """
    value = _ORIGINAL_SEO_GEO_RUN(force=force)
    result = dict(value) if isinstance(value, dict) else {"seo_geo": value}
    try:
        collaboration = model_collaboration.run_cycle(force=bool(force))
    except (OSError, ValueError, RuntimeError, PermissionError, TypeError, KeyError, AttributeError) as error:
        collaboration = {"skipped": False, "completed": 0, "failed": 1, "error": str(error)[:500], "evidence_level": "C_auxiliary"}
    result["doubao_collaboration"] = collaboration
    try:
        from core import r8_23_growth_operating_system as growth_os
        for row in collaboration.get("results") or []:
            if not isinstance(row, dict):
                continue
            success = row.get("status") == "completed"
            growth_os.record_utilization(
                "doubao_cloud",
                success=success,
                result={"stage": row.get("stage"), "receipt_id": row.get("receipt_id"), "evidence_level": "C_auxiliary"},
                reason="R8-23.2 SEO/GEO关键协作" if success else str(row.get("error") or "SEO/GEO协作失败")[:300],
            )
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError, AttributeError):
        pass
    return result


def _seo_geo_status():
    value = _ORIGINAL_SEO_GEO_STATUS()
    result = dict(value) if isinstance(value, dict) else {"seo_geo": value}
    result["doubao_collaboration"] = model_collaboration.status()
    return result


def _runtime_health():
    ready = truth.readiness()
    try:
        from core import runtime_resilience
        runtime = runtime_resilience.snapshot()
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError, AttributeError):
        runtime = {"status": "unknown"}
    return {
        "status": "online",
        "autonomy_state": ready.get("state"),
        "readiness": ready,
        "runtime": runtime,
        "truth": "HTTP在线、Worker健康、自治READY和外部增长成功是四种不同状态。",
    }


def _status_payload(handler):
    base = handler._status_payload()
    identity = truth.release_identity()
    base.update({
        "version": identity.get("product_version"),
        "display_version": identity.get("release"),
        "runtime_build": identity.get("runtime_build"),
        "r8_phase": identity.get("phase"),
        "build_number": identity.get("build_number"),
        "commit": identity.get("commit"),
        "release_manifest": identity,
        "autonomy_readiness": truth.readiness().get("state"),
    })
    return base


def _serve_autonomous_ops(handler):
    web = server.get_web_path()
    names = ("autonomous-ops.js", "r8_22_autonomy.js", "r8_23_growth_os.js", "r8_23_2_runtime_truth.js")
    source = "\n;\n".join((web / name).read_text(encoding="utf-8") for name in names)
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
    r7_engine.run_due_jobs = _run_due_jobs
    seo_core.run_once = _seo_geo_run
    seo_core.status = _seo_geo_status

    original_get = server.DashboardHandler.do_GET
    original_post = server.DashboardHandler.do_POST

    def do_get(handler):
        path = urlsplit(handler.path).path
        try:
            if path == "/autonomous-ops.js":
                _serve_autonomous_ops(handler)
                return
            if path == "/api/status":
                handler._json_ok(_status_payload(handler))
                return
            if path in {"/api/health", "/api/runtime-health"}:
                handler._json_ok(_runtime_health())
                return
            if path == "/api/version":
                handler._json_ok(truth.release_identity())
                return
            if path == "/api/readiness":
                handler._json_ok(truth.readiness())
                return
            if path == "/api/r8-23-2/runtime-truth":
                handler._json_ok(truth.snapshot(reconcile=False))
                return
            if path == "/api/r8-23-2/decision-pack":
                handler._json_ok(truth.decision_pack_status())
                return
            if path == "/api/r8-23-2/queue":
                handler._json_ok({"items": truth._load().get("queue") or {}, "generated_at": truth.now_iso()})
                return
            if path == "/api/r8-23-2/model-routing":
                handler._json_ok({
                    "policy": truth.snapshot(reconcile=False).get("model_routing"),
                    "collaboration": model_collaboration.status(),
                    "examples": {
                        "batch": truth.model_route_for("batch_tagging"),
                        "seo": truth.model_route_for("seo_semantic_qc"),
                        "geo": truth.model_route_for("geo_gap_analysis"),
                    },
                    "truth": "豆包是SEO/GEO关键协作模型，但普通API结果仍是C级辅助，不能成为正式GEO Evidence。",
                })
                return
            if path == "/api/r8-23-2/doubao-collaboration":
                query = parse_qs(urlsplit(handler.path).query)
                try:
                    limit = int((query.get("limit") or [50])[0])
                except (TypeError, ValueError):
                    limit = 50
                handler._json_ok({"status": model_collaboration.status(), "receipts": model_collaboration.receipts(limit)})
                return
        except (OSError, ValueError, RuntimeError, TypeError, KeyError, AttributeError) as error:
            handler._json_error(500, error)
            return
        return original_get(handler)

    def do_post(handler):
        path = urlsplit(handler.path).path
        if path not in {"/api/r8-23-2/controller-tick", "/api/r8-23-2/doubao-collaboration/run"}:
            return original_post(handler)
        if not _origin_allowed(handler):
            handler._json_error(403, "Cross-origin changes are not allowed")
            return
        try:
            payload = _read_json(handler)
            if path == "/api/r8-23-2/doubao-collaboration/run":
                handler._json_ok(model_collaboration.run_cycle(force=bool(payload.get("force", True))))
                return
            result = convergence.controller_tick()
            handler._json_ok({"result": result, "snapshot": truth.snapshot(reconcile=False)})
        except (OSError, ValueError, RuntimeError, TypeError, KeyError, AttributeError, json.JSONDecodeError) as error:
            handler._json_error(400, error)

    server.DashboardHandler.do_GET = do_get
    server.DashboardHandler.do_POST = do_post
    server.DashboardHandler._kz_r8_23_2_runtime_truth = True
    _INSTALLED = True


install()
