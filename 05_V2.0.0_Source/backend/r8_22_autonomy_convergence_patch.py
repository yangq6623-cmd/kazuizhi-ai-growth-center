"""R8-22 production patch: converge Command -> Mission -> Plan -> Task -> Receipt."""
from __future__ import annotations

import json
from urllib.parse import parse_qs, urlsplit

from backend import server
from core import autonomous_ops
from core import command_execution
from core import r7_engine
from core import r8_22_autonomous_convergence as convergence
from core.storage import now_iso, write_json

_INSTALLED = False
_ORIGINAL_AUTONOMOUS_SYNC = autonomous_ops.sync_from_runtime
_ORIGINAL_ACTIVE_AUTHORIZATION = command_execution.active_authorization
_ORIGINAL_RECONCILE = command_execution.reconcile
_ORIGINAL_RUN_DUE_JOBS = r7_engine.run_due_jobs
_ORIGINAL_ENSURE_COMMAND_MISSION = convergence.ensure_command_mission

_FINANCIAL_OR_CORE_HUMAN = (
    "资金", "付款", "退款", "提现", "结算", "充值", "赔付", "改价",
    "人脸", "实名", "不可逆", "删除账号", "账号安全", "核心权限", "核心授权",
)
_OPTIONAL_CHANNEL_MARKERS = (
    "抖音", "视频号", "快手", "小红书", "b站", "微博", "社媒", "手机", "短视频",
)
_OTHER_HUMAN_MARKERS = ("验证码", "oauth", "登录", "授权", "权限", "密钥", "token")
MAX_CURRENT_JOBS_PER_TICK = 4
MAX_BACKGROUND_JOBS_PER_TICK = 1


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


def _belongs_to_current(job, command_id, mission_id, command):
    """Never steal a task already bound to a different Command/Mission."""
    existing_command = str(job.get("command_id") or "")
    existing_mission = str(job.get("mission_id") or "")
    if existing_command:
        return existing_command == command_id
    if existing_mission:
        return existing_mission == mission_id
    return _job_after_command(job, command)


def _bind_current_jobs():
    mission = convergence.ensure_command_mission()
    command = convergence._latest_authorized_command()
    if not mission or not command:
        return {"jobs_bound": 0, "jobs_backlog": 0, "command_id": None}
    command_id = str(command.get("command_id") or "")
    mission_id = str(mission.get("mission_id") or "")
    bound = backlog = 0
    with r7_engine.LOCK:
        data = r7_engine._store()
        changed = False
        for job in data.get("items", []):
            if not isinstance(job, dict) or job.get("risk") == "financial" or job.get("state") not in {"queued", "running"}:
                continue
            belongs = _belongs_to_current(job, command_id, mission_id, command)
            if belongs:
                updates = {
                    "mission_id": mission_id,
                    "command_id": command_id,
                    "command_receipt_id": command.get("control_receipt_id"),
                    "authorization_state": "authorized",
                    "authorization_note": "R8-22 当前老板 Mission：非资金任务已授权自动执行。",
                    "priority_class": convergence.CURRENT_PRIORITY,
                }
                if any(job.get(key) != value for key, value in updates.items()):
                    job.update(updates, updated_at=now_iso())
                    bound += 1
                    changed = True
            elif job.get("state") == "queued" and job.get("priority_class") != convergence.BACKLOG_PRIORITY:
                # Explicitly demote P0 from a superseded Mission; never delete it.
                job["priority_class"] = convergence.BACKLOG_PRIORITY
                job["updated_at"] = now_iso()
                backlog += 1
                changed = True
        if changed:
            write_json(r7_engine.JOBS, data)
    return {"jobs_bound": bound, "jobs_backlog": backlog, "command_id": command_id, "mission_id": mission_id}


def _human_and_deferred():
    """Only real owner-only gates remain human; optional distribution is deferred."""
    human = []
    deferred = []
    try:
        from core.autonomy import human_interventions
        for item in human_interventions().get("items", []):
            if not isinstance(item, dict):
                continue
            text = " ".join(str(item.get(key) or "") for key in ("title", "reason", "detail", "action"))
            lower = text.lower()
            financial_or_core = any(marker in lower for marker in _FINANCIAL_OR_CORE_HUMAN)
            optional = any(marker in lower for marker in _OPTIONAL_CHANNEL_MARKERS)
            other_human = any(marker in lower for marker in _OTHER_HUMAN_MARKERS)
            if financial_or_core:
                human.append(item)
            elif optional:
                deferred.append({**item, "deferred_reason": "可选分发渠道待登录/验证；官网 SEO/GEO 核心 Mission 继续"})
            elif other_human:
                human.append(item)
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError):
        pass
    try:
        from core import r8_control
        social = r8_control.social_center_status()
        for account in social.get("accounts", []) or []:
            if not isinstance(account, dict):
                continue
            status = str(account.get("login_status") or "")
            if status in {"needs_human", "logged_out"}:
                deferred.append({
                    "channel": account.get("platform") or account.get("name"),
                    "reason": "外部分发账号未在线/待登录",
                    "policy": "deferred_channel_not_core_blocker",
                })
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError):
        pass
    return human[:50], deferred[:50]


def _priority_due_job_ids():
    """Bound each scheduler tick so a large P0 Mission cannot freeze heartbeats."""
    now = convergence.datetime.now().astimezone()
    with r7_engine.LOCK:
        due = []
        for job in r7_engine._store().get("items", []):
            if not isinstance(job, dict) or job.get("state") != "queued" or job.get("mode") != "local":
                continue
            when = convergence._parse_time(job.get("due_at")) or now
            if when.tzinfo is None:
                when = when.astimezone()
            if when <= now:
                due.append(job)
    rank = {convergence.CURRENT_PRIORITY: 0, "P1_closed_loop": 1, "P2_today": 2, convergence.BACKLOG_PRIORITY: 3}
    due.sort(key=lambda x: (rank.get(str(x.get("priority_class") or ""), 2), str(x.get("due_at") or x.get("created_at") or "")))
    current = [x for x in due if x.get("priority_class") == convergence.CURRENT_PRIORITY][:MAX_CURRENT_JOBS_PER_TICK]
    background = [x for x in due if x.get("priority_class") != convergence.CURRENT_PRIORITY][:MAX_BACKGROUND_JOBS_PER_TICK]
    selected = current + background if current else due[:MAX_CURRENT_JOBS_PER_TICK]
    return [str(x.get("id")) for x in selected if x.get("id")]


def _event_stream(limit=40):
    """Do not relabel historical audit events as if they belonged to this Mission."""
    state = convergence._load_state()
    mission_id = state.get("active_mission_id")
    command_id = state.get("active_command_id")
    data = autonomous_ops._load()
    rows = [x for x in data.get("events", []) if isinstance(x, dict) and (not mission_id or x.get("mission_id") == mission_id)]
    try:
        jobs = r7_engine._store().get("items", [])
        current_job_ids = {
            str(job.get("id")) for job in jobs
            if isinstance(job, dict) and (
                (command_id and str(job.get("command_id") or "") == str(command_id))
                or (mission_id and str(job.get("mission_id") or "") == str(mission_id))
            )
        }
        for event in r7_engine.audit_history().get("events", []):
            if not isinstance(event, dict) or str(event.get("job_id") or "") not in current_job_ids:
                continue
            detail = event.get("detail") if isinstance(event.get("detail"), dict) else {}
            rows.append({
                "id": event.get("id"), "at": event.get("at"), "kind": event.get("kind"),
                "message": detail.get("title") or event.get("kind") or "任务状态变化",
                "mission_id": mission_id,
                "detail": {"job_id": event.get("job_id"), **detail},
            })
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError):
        pass
    rows.sort(key=lambda x: str(x.get("at") or ""), reverse=True)
    return rows[:max(1, min(int(limit or 40), 100))]


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
    # current owner Command mission. This preserves the old content campaign as
    # evidence/history without allowing it to overwrite a newer owner Command.
    _ORIGINAL_AUTONOMOUS_SYNC(autostart=autostart)
    convergence.ensure_command_mission()
    convergence.ensure_controller_plan()
    return autonomous_ops.snapshot(sync=False)


def _run_due_jobs():
    """Run current-Mission work first without starving heartbeats/background."""
    convergence.bind_current_jobs()
    ids = convergence.priority_due_job_ids()
    if not ids:
        return {"processed": 0, "at": convergence.now_iso(), "priority": "none"}
    for job_id in ids:
        r7_engine._run(job_id)
    return {
        "processed": len(ids),
        "at": convergence.now_iso(),
        "priority": "current_mission_first_bounded",
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
    convergence.bind_current_jobs = _bind_current_jobs
    convergence._human_and_deferred = _human_and_deferred
    convergence.priority_due_job_ids = _priority_due_job_ids
    convergence.event_stream = _event_stream
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
