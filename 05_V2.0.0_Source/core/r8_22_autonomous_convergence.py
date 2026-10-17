"""R8-22 autonomous convergence for the 7x24 operating loop.

This module does not replace any SEO, GEO, model, publishing or evidence
capability.  It closes the control-plane gaps between an already-authorized
owner Command and the existing Mission/Plan/Task/Receipt pipeline.

Truth boundaries remain strict:
- a local/model result never becomes an external publish/search/GEO success;
- financial, credential, captcha, identity and irreversible permission work is
  human-only;
- an unavailable optional distribution channel is deferred, not allowed to
  block website SEO/GEO work.
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from core.storage import now_iso, read_json, write_json

STATE_FILE = "ops/r8_22_autonomous_convergence.json"
PHASE_RECEIPT_SECONDS = 15 * 60
CURRENT_PRIORITY = "P0_current_mission"
BACKLOG_PRIORITY = "P3_backlog"

_HUMAN_MARKERS = (
    "资金", "付款", "退款", "提现", "结算", "充值", "赔付", "改价",
    "验证码", "人脸", "实名", "oauth", "登录", "授权", "权限", "密钥", "token",
    "不可逆", "删除账号", "账号安全",
)
_OPTIONAL_CHANNEL_MARKERS = (
    "抖音", "视频号", "快手", "小红书", "b站", "微博", "社媒", "手机", "短视频",
)


def _default_state():
    return {
        "schema": 1,
        "active_command_id": None,
        "active_mission_id": None,
        "plan": None,
        "phase_receipts": [],
        "last_phase_receipt_at": None,
        "updated_at": now_iso(),
    }


def _load_state():
    data = read_json(STATE_FILE, _default_state())
    if not isinstance(data, dict):
        data = _default_state()
    for key, value in _default_state().items():
        data.setdefault(key, value)
    if not isinstance(data.get("phase_receipts"), list):
        data["phase_receipts"] = []
    return data


def _save_state(data):
    data["updated_at"] = now_iso()
    data["phase_receipts"] = (data.get("phase_receipts") or [])[-192:]
    return write_json(STATE_FILE, data)


def _parse_time(value):
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00"))
    except ValueError:
        return None


def _latest_authorized_command():
    from core import command_execution

    for link in command_execution.command_links(100):
        if command_execution._authorized(link):
            return link
    return None


def _mission_for_command(data, command_id):
    target = str(command_id or "")
    for mission in data.get("missions", []):
        if isinstance(mission, dict) and str(mission.get("command_id") or "") == target:
            return mission
    return None


def ensure_command_mission():
    """Promote the newest verified owner Command into the active Mission.

    This is idempotent by command_id.  It intentionally does not fabricate a
    Growth/Content campaign; existing production subsystems continue to own
    their own truthful artifacts and receipts.
    """
    from core import autonomous_ops

    link = _latest_authorized_command()
    if not link:
        return None
    command_id = str(link.get("command_id") or "").strip()
    if not command_id:
        return None

    data = autonomous_ops._load()
    mission = _mission_for_command(data, command_id)
    created = False
    if mission is None:
        objective = str(link.get("objective") or "").strip()
        mission = {
            "mission_id": autonomous_ops._mission_id(),
            "growth_id": None,
            "created_at": link.get("created_at") or now_iso(),
            "updated_at": now_iso(),
            "source": "owner_command",
            "title": (objective[:72] or "老板实时经营目标"),
            "region": "",
            "service": "",
            "goal": objective[:2000],
            "priority": CURRENT_PRIORITY,
            "autonomy_level": "L4_key_gates_human",
            "state": "active",
            "stage": "自动编排",
            "user_state": "自动处理中",
            "r7_context": {},
            "children": {"video_ids": [], "publish_plan_ids": [], "receipt_ids": []},
            "verified_publications": 0,
            "last_result": None,
            "command_id": command_id,
            "command_receipt_id": link.get("control_receipt_id"),
            "command_status": link.get("status"),
            "command_transport": link.get("transport"),
            "command_objective": objective,
            "command_bound_at": link.get("created_at") or now_iso(),
        }
        data.setdefault("missions", []).insert(0, mission)
        created = True

    previous_active = data.get("active_mission_id")
    for other in data.get("missions", []):
        if not isinstance(other, dict) or other is mission:
            continue
        if other.get("source") == "owner_command" and other.get("state") == "active":
            other["state"] = "superseded"
            other["priority"] = BACKLOG_PRIORITY
            other["updated_at"] = now_iso()
    mission.update(
        priority=CURRENT_PRIORITY,
        state="active",
        user_state="自动处理中",
        command_status=link.get("status"),
        command_receipt_id=link.get("control_receipt_id"),
        updated_at=now_iso(),
    )
    data["active_mission_id"] = mission["mission_id"]
    objective = str(link.get("objective") or "").strip()
    if objective:
        previous_goal = data.get("owner_goal") if isinstance(data.get("owner_goal"), dict) else {}
        data["owner_goal"] = {
            **previous_goal,
            "objective": objective[:2000],
            "updated_at": now_iso(),
            "source": "owner_command",
            "command_id": command_id,
        }

    if created:
        autonomous_ops._event(data, mission, "command_promoted", "老板 Command 已自动建立并接管当前 Mission", {
            "command_id": command_id,
            "transport": link.get("transport"),
        })
    elif previous_active != mission["mission_id"]:
        autonomous_ops._event(data, mission, "mission_reactivated", "最新老板 Command 已恢复为当前 Mission", {
            "command_id": command_id,
        })
    autonomous_ops._save(data)

    state = _load_state()
    if state.get("active_command_id") != command_id:
        state["active_command_id"] = command_id
        state["active_mission_id"] = mission["mission_id"]
        state["plan"] = None
        state["last_phase_receipt_at"] = None
        _save_state(state)
    return mission


def _plan_lanes(objective):
    text = str(objective or "").lower()
    lanes = [
        {"id": "health", "label": "系统/模型/服务器健康", "mode": "autonomous"},
    ]
    wants_growth = any(word in text for word in ("推广", "增长", "运营", "seo", "geo", "搜索", "内容")) or not text
    if wants_growth or "seo" in text or "搜索" in text:
        lanes.append({"id": "seo", "label": "SEO机会→内容→QC→发布→搜索提交", "mode": "autonomous"})
    if wants_growth or "geo" in text or "ai" in text:
        lanes.append({"id": "geo", "label": "GEO缺口→优化→发布→真实A/B复测", "mode": "autonomous_truth_gated"})
    if wants_growth:
        lanes.append({"id": "content", "label": "内容生产与质量闭环", "mode": "autonomous"})
        lanes.append({"id": "publish", "label": "官网优先发布；未验证社交渠道延后", "mode": "verified_receipt_required"})
    lanes.append({"id": "measure", "label": "Receipt/Evidence/经营数据回流与下一轮判断", "mode": "truth_only"})
    return lanes


def ensure_controller_plan(mission=None):
    mission = mission or ensure_command_mission()
    if not mission:
        return None
    state = _load_state()
    command_id = str(mission.get("command_id") or "")
    plan = state.get("plan") if isinstance(state.get("plan"), dict) else None
    if plan and plan.get("command_id") == command_id and plan.get("mission_id") == mission.get("mission_id"):
        return plan

    objective = str(mission.get("command_objective") or mission.get("goal") or "").strip()
    plan = {
        "schema": "kazuizhi.ai.controller.plan.r8_22.v1",
        "plan_id": f"PLAN-{uuid4().hex[:10].upper()}",
        "command_id": command_id,
        "mission_id": mission.get("mission_id"),
        "objective": objective,
        "priority": CURRENT_PRIORITY,
        "status": "active",
        "created_at": now_iso(),
        "lanes": _plan_lanes(objective),
        "execution_policy": {
            "autonomous_non_financial": True,
            "human_only": ["资金操作", "验证码/实名/人脸", "账号权限/核心授权", "不可逆高风险动作"],
            "optional_channel_offline": "defer_channel_and_continue_core_mission",
            "truth": "没有真实 Receipt/Evidence 不得升级发布、收录、排名、GEO 或经营结果",
        },
    }
    state["active_command_id"] = command_id
    state["active_mission_id"] = mission.get("mission_id")
    state["plan"] = plan
    _save_state(state)

    from core import autonomous_ops
    data = autonomous_ops._load()
    live = autonomous_ops._find_mission(data, mission_id=mission.get("mission_id"))
    if live:
        live["controller_plan_id"] = plan["plan_id"]
        live["stage"] = "自动执行"
        live["updated_at"] = now_iso()
        autonomous_ops._event(data, live, "controller_plan_created", "当前 Command 已自动编译为 Controller Plan", {
            "plan_id": plan["plan_id"], "lane_count": len(plan["lanes"]),
        })
        autonomous_ops._save(data)
    return plan


def _job_after_command(job, command):
    job_time = _parse_time(job.get("created_at"))
    command_time = _parse_time(command.get("created_at"))
    if not job_time or not command_time:
        return False
    try:
        return job_time >= command_time
    except TypeError:
        return str(job.get("created_at") or "") >= str(command.get("created_at") or "")


def bind_current_jobs():
    """Give current-Mission work P0 without rewriting historical truth."""
    from core import r7_engine

    mission = ensure_command_mission()
    command = _latest_authorized_command()
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
            belongs = (
                str(job.get("command_id") or "") == command_id
                or str(job.get("mission_id") or "") == mission_id
                or _job_after_command(job, command)
            )
            if belongs:
                updates = {
                    "mission_id": mission_id,
                    "command_id": command_id,
                    "command_receipt_id": command.get("control_receipt_id"),
                    "authorization_state": "authorized",
                    "authorization_note": "R8-22 当前老板 Mission：非资金任务已授权自动执行。",
                    "priority_class": CURRENT_PRIORITY,
                }
                if any(job.get(key) != value for key, value in updates.items()):
                    job.update(updates, updated_at=now_iso())
                    bound += 1
                    changed = True
            elif job.get("state") == "queued" and not job.get("priority_class"):
                job["priority_class"] = BACKLOG_PRIORITY
                job["updated_at"] = now_iso()
                backlog += 1
                changed = True
        if changed:
            write_json(r7_engine.JOBS, data)
    return {"jobs_bound": bound, "jobs_backlog": backlog, "command_id": command_id, "mission_id": mission_id}


def _human_and_deferred():
    human = []
    deferred = []
    try:
        from core.autonomy import human_interventions
        for item in human_interventions().get("items", []):
            if not isinstance(item, dict):
                continue
            text = " ".join(str(item.get(key) or "") for key in ("title", "reason", "detail", "action"))
            lower = text.lower()
            if any(marker in lower for marker in _HUMAN_MARKERS):
                human.append(item)
            elif any(marker in lower for marker in _OPTIONAL_CHANNEL_MARKERS):
                deferred.append({**item, "deferred_reason": "可选渠道不可用；核心 SEO/GEO Mission 继续"})
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
                    "policy": "deferred_channel",
                })
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError):
        pass
    return human[:50], deferred[:50]


def _metrics(command_id=None, mission_id=None):
    try:
        from core import r7_engine
        jobs = r7_engine.list_jobs().get("items", [])
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError):
        jobs = []
    current = [x for x in jobs if isinstance(x, dict) and (
        (command_id and str(x.get("command_id") or "") == str(command_id))
        or (mission_id and str(x.get("mission_id") or "") == str(mission_id))
    )]
    try:
        from core import seo_geo_autonomy
        seo_geo = seo_geo_autonomy.status()
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError):
        seo_geo = {}
    return {
        "tasks": {
            "total": len(current),
            "queued": sum(x.get("state") == "queued" for x in current),
            "running": sum(x.get("state") == "running" for x in current),
            "completed": sum(x.get("state") == "completed" for x in current),
            "failed": sum(x.get("state") == "failed" for x in current),
            "receipts": sum(isinstance(x.get("execution_receipt"), dict) for x in current),
        },
        "seo_geo": seo_geo,
    }


def maybe_phase_receipt(force=False):
    state = _load_state()
    command_id = state.get("active_command_id")
    mission_id = state.get("active_mission_id")
    if not command_id or not mission_id:
        return None
    now = datetime.now().astimezone()
    last = _parse_time(state.get("last_phase_receipt_at"))
    if not force and last is not None:
        try:
            if (now - last).total_seconds() < PHASE_RECEIPT_SECONDS:
                return None
        except TypeError:
            pass
    human, deferred = _human_and_deferred()
    receipt = {
        "receipt_id": f"PHASE-{uuid4().hex[:10].upper()}",
        "kind": "r8_22_phase_receipt",
        "created_at": now_iso(),
        "command_id": command_id,
        "mission_id": mission_id,
        "metrics": _metrics(command_id, mission_id),
        "human_blockers": len(human),
        "deferred_channels": len(deferred),
        "truth_note": "阶段回执只汇总真实本地任务/现有 SEO-GEO 状态；不把本地完成冒充外部发布、收录、排名或正式 GEO 成绩。",
    }
    state.setdefault("phase_receipts", []).append(receipt)
    state["last_phase_receipt_at"] = receipt["created_at"]
    _save_state(state)
    try:
        from core import autonomous_ops
        data = autonomous_ops._load()
        mission = autonomous_ops._find_mission(data, mission_id=mission_id)
        if mission:
            autonomous_ops._event(data, mission, "phase_receipt", "已生成15分钟自治阶段回执", {
                "receipt_id": receipt["receipt_id"],
                "tasks": receipt["metrics"]["tasks"],
            })
            autonomous_ops._save(data)
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError):
        pass
    return receipt


def priority_due_job_ids():
    """Return due P0 work first; while a current Mission exists, admit only a
    small backlog slice per scheduler tick so legacy backlog cannot starve it.
    """
    from core import r7_engine

    now = datetime.now().astimezone()
    with r7_engine.LOCK:
        due = []
        for job in r7_engine._store().get("items", []):
            if not isinstance(job, dict) or job.get("state") != "queued" or job.get("mode") != "local":
                continue
            when = _parse_time(job.get("due_at")) or now
            if when.tzinfo is None:
                when = when.astimezone()
            if when <= now:
                due.append(job)
    rank = {CURRENT_PRIORITY: 0, "P1_closed_loop": 1, "P2_today": 2, BACKLOG_PRIORITY: 3}
    due.sort(key=lambda x: (rank.get(str(x.get("priority_class") or ""), 2), str(x.get("created_at") or "")))
    p0 = [x for x in due if x.get("priority_class") == CURRENT_PRIORITY]
    if p0:
        rest = [x for x in due if x.get("priority_class") != CURRENT_PRIORITY][:2]
        due = p0 + rest
    return [str(x.get("id")) for x in due if x.get("id")]


def event_stream(limit=40):
    from core import autonomous_ops

    state = _load_state()
    mission_id = state.get("active_mission_id")
    data = autonomous_ops._load()
    rows = [x for x in data.get("events", []) if isinstance(x, dict) and (not mission_id or x.get("mission_id") == mission_id)]
    try:
        from core import r7_engine
        for event in r7_engine.audit_history().get("events", []):
            if not isinstance(event, dict):
                continue
            detail = event.get("detail") if isinstance(event.get("detail"), dict) else {}
            rows.append({
                "id": event.get("id"), "at": event.get("at"), "kind": event.get("kind"),
                "message": detail.get("title") or event.get("kind") or "任务状态变化",
                "mission_id": mission_id, "detail": {"job_id": event.get("job_id"), **detail},
            })
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError):
        pass
    rows.sort(key=lambda x: str(x.get("at") or ""), reverse=True)
    return rows[:max(1, min(int(limit or 40), 100))]


def snapshot():
    mission = ensure_command_mission()
    plan = ensure_controller_plan(mission) if mission else None
    bind = bind_current_jobs() if mission else {"jobs_bound": 0, "jobs_backlog": 0}
    maybe_phase_receipt(force=False)
    state = _load_state()
    human, deferred = _human_and_deferred()
    metrics = _metrics(state.get("active_command_id"), state.get("active_mission_id"))
    tasks = metrics.get("tasks") or {}
    total = int(tasks.get("total") or 0)
    done = int(tasks.get("completed") or 0)
    progress = round(done * 100 / total) if total else 0
    current_action = "等待下一轮自治调度"
    if tasks.get("running"):
        current_action = "当前 Mission 有任务正在执行"
    elif tasks.get("queued"):
        current_action = "当前 Mission 队列等待调度"
    return {
        "schema": "kazuizhi.r8_22.autonomy.v1",
        "generated_at": now_iso(),
        "command": _latest_authorized_command(),
        "mission": mission,
        "plan": plan,
        "progress": {"percent": progress, **tasks},
        "current_action": current_action,
        "next_action": "由 Controller Plan 与真实 Receipt 自动决定下一步",
        "human_blockers": human,
        "deferred_channels": deferred,
        "events": event_stream(40),
        "phase_receipts": (state.get("phase_receipts") or [])[-8:][::-1],
        "job_binding": bind,
        "truth_rule": "Command→Mission→Plan→Task 自动收口；外部发布/搜索/GEO/经营结果仍只认真实 Receipt/Evidence。",
    }


def controller_tick():
    mission = ensure_command_mission()
    plan = ensure_controller_plan(mission) if mission else None
    binding = bind_current_jobs() if mission else {"jobs_bound": 0, "jobs_backlog": 0}
    receipt = maybe_phase_receipt(force=False) if mission else None
    return {"mission_id": (mission or {}).get("mission_id"), "plan_id": (plan or {}).get("plan_id"), "binding": binding, "phase_receipt": receipt}
