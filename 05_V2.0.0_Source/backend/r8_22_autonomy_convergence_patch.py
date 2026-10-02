"""R8-22 production patch: converge Command -> Mission -> Plan -> Task -> Receipt."""
from __future__ import annotations

import json
from urllib.parse import parse_qs, urlsplit

from backend import server
from core import autonomous_ops
from core import command_execution
from core import r7_engine
from core import r8_22_autonomous_convergence as convergence

_INSTALLED = False
_ORIGINAL_AUTONOMOUS_SYNC = autonomous_ops.sync_from_runtime
_ORIGINAL_ACTIVE_AUTHORIZATION = command_execution.active_authorization
_ORIGINAL_RECONCILE = command_execution.reconcile
_ORIGINAL_RUN_DUE_JOBS = r7_engine.run_due_jobs
_ORIGINAL_ENSURE_COMMAND_MISSION = convergence.ensure_command_mission


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


def _ensure_command_mission():
    """Avoid rewriting stable Mission state on every 5/15-second UI/scheduler poll."""
    link = convergence._latest_authorized_command()
    if not link:
        return None
    command_id = str(link.get("command_id") or "")
    state = convergence._load_state()
    data = autonomous_ops._load()
    mission = autonomous_ops._find_mission(data, mission_id=state.get("active_mission_id"))
    if (
        mission
        and data.get("active_mission_id") == mission.get("mission_id")
        and str(mission.get("command_id") or "") == command_id
        and str(mission.get("command_status") or "") == str(link.get("status") or "")
        and str(mission.get("command_receipt_id") or "") == str(link.get("control_receipt_id") or "")
    ):
        return mission
    return _ORIGINAL_ENSURE_COMMAND_MISSION()


def _job_after_command(job, command):
    """Future scheduled daily work belongs to a new owner Command even when the
    daily schedule row itself was created earlier in the morning.
    """
    command_time = convergence._parse_time(command.get("created_at"))
    effective = convergence._parse_time(job.get("due_at")) or convergence._parse_time(job.get("created_at"))
    if not command_time or not effective:
        return False
    try:
        return effective >= command_time
    except TypeError:
        return str(job.get("due_at") or job.get("created_at") or "") >= str(command.get("created_at") or "")


def _active_authorization(mission_id=None):
    direct = _ORIGINAL_ACTIVE_AUTHORIZATION(mission_id)
    if direct or not mission_id:
        return direct
    data = autonomous_ops._load()
    mission = autonomous_ops._find_mission(data, mission_id=str(mission_id))
    command_id = str((mission or {}).get("command_id") or "")
    if not command_id:
        return None
    for link in command_execution.command_links(100):
        if str(link.get("command_id") or "") == command_id and command_execution._authorized(link):
            return link
    return None


def _reconcile_jobs():
    return convergence.bind_current_jobs()


def _reconcile():
    # Promotion must happen before legacy reconciliation so the newest verified
    # owner Command, not an old content campaign, is the control authority.
    convergence.controller_tick()
    result = _ORIGINAL_RECONCILE()
    convergence.controller_tick()
    if isinstance(result, dict):
        state = convergence._load_state()
        result["r8_22"] = {
            "active_command_id": state.get("active_command_id"),
            "active_mission_id": state.get("active_mission_id"),
            "controller_plan": bool(state.get("plan")),
        }
    return result


def _sync_from_runtime(*, autostart=True):
    # Let existing R7/R8 truth owners synchronize first, then re-assert the
    # current owner Command mission.  This prevents active_growth from
    # overwriting a newer owner Command while preserving all campaign state.
    _ORIGINAL_AUTONOMOUS_SYNC(autostart=autostart)
    convergence.ensure_command_mission()
    convergence.ensure_controller_plan()
    return autonomous_ops.snapshot(sync=False)


def _run_due_jobs():
    """Run P0 current-Mission work first without starving the background."""
    convergence.bind_current_jobs()
    ids = convergence.priority_due_job_ids()
    if not ids:
        return {"processed": 0, "at": convergence.now_iso(), "priority": "none"}
    for job_id in ids:
        r7_engine._run(job_id)
    return {
        "processed": len(ids),
        "at": convergence.now_iso(),
        "priority": "current_mission_first",
        "current_mission": convergence._load_state().get("active_mission_id"),
    }


def _serve_autonomous_ops(handler):
    web = server.get_web_path()
    source = "\n;\n".join([
        (web / "autonomous-ops.js").read_text(encoding="utf-8"),
        (web / "r8_22_autonomy.js").read_text(encoding="utf-8"),
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

    convergence.ensure_command_mission = _ensure_command_mission
    convergence._job_after_command = _job_after_command
    command_execution.active_authorization = _active_authorization
    command_execution.reconcile_jobs = _reconcile_jobs
    command_execution.reconcile = _reconcile
    autonomous_ops.sync_from_runtime = _sync_from_runtime
    r7_engine.run_due_jobs = _run_due_jobs

    original_get = server.DashboardHandler.do_GET
    original_post = server.DashboardHandler.do_POST

    def do_get(handler):
        path = urlsplit(handler.path).path
        try:
            if path == "/autonomous-ops.js":
                _serve_autonomous_ops(handler)
                return
            if path == "/api/r8-22/autonomy":
                handler._json_ok(convergence.snapshot())
                return
            if path == "/api/r8-22/autonomy/events":
                query = parse_qs(urlsplit(handler.path).query)
                try:
                    limit = int((query.get("limit") or [40])[0])
                except (TypeError, ValueError):
                    limit = 40
                handler._json_ok({"items": convergence.event_stream(limit), "generated_at": convergence.now_iso()})
                return
            if path == "/api/r8-22/autonomy/receipt":
                state = convergence._load_state()
                handler._json_ok({
                    "active_command_id": state.get("active_command_id"),
                    "active_mission_id": state.get("active_mission_id"),
                    "items": (state.get("phase_receipts") or [])[-16:][::-1],
                    "truth_rule": "阶段 Receipt 只汇总真实记录，不补造外部结果。",
                })
                return
        except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
            handler._json_error(400, error)
            return
        return original_get(handler)

    def do_post(handler):
        path = urlsplit(handler.path).path
        if path != "/api/r8-22/autonomy/run":
            return original_post(handler)
        if not _origin_allowed(handler):
            handler._json_error(403, "Cross-origin changes are not allowed")
            return
        try:
            payload = _read_json(handler)
            result = convergence.controller_tick()
            if bool(payload.get("phase_receipt")):
                result["phase_receipt"] = convergence.maybe_phase_receipt(force=True)
            handler._json_ok({"result": result, "autonomy": convergence.snapshot()})
        except (OSError, ValueError, RuntimeError, TypeError, KeyError, json.JSONDecodeError) as error:
            handler._json_error(400, error)

    server.DashboardHandler.do_GET = do_get
    server.DashboardHandler.do_POST = do_post
    server.DashboardHandler._kz_r8_22_autonomy_convergence = True
    _INSTALLED = True


install()
