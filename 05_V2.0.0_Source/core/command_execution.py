"""R8-18 ChatGPT Command -> Mission -> task execution reconciliation.

This module intentionally does not create a second decision maker.  It makes
the already verified ChatGPT control connector the authorization record for
non-financial local work, and joins that record to the existing Mission and
R7 task stores.  External publication is deliberately outside this module.
"""
from __future__ import annotations

from core.storage import now_iso, write_json


def _control_state() -> dict:
    try:
        from integrations.chatgpt_control import control_status
        value = control_status()
        return value if isinstance(value, dict) else {}
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError):
        return {}


def command_links(limit: int = 200) -> list[dict]:
    """Return normalized links from both supported ChatGPT transports.

    R8-11 originally read only the private async bus.  Local WebMCP commands
    are durable receipts too, so omitting them made a valid Command look like
    "尚无" in the owner ledger.
    """
    rows: list[dict] = []
    try:
        from integrations.chatgpt_control import recent_commands, recent_receipts
        commands = {str(x.get("command_id") or ""): x for x in recent_commands(limit) if isinstance(x, dict)}
        for receipt in recent_receipts(limit):
            if not isinstance(receipt, dict) or receipt.get("kind") == "verification_receipt":
                continue
            command_id = str(receipt.get("command_id") or "").strip()
            command = commands.get(command_id, {})
            rows.append({
                "command_id": command_id or None,
                "decision_pack_id": None,
                "control_receipt_id": receipt.get("receipt_id"),
                "status": receipt.get("status") or command.get("status"),
                "created_at": receipt.get("created_at") or command.get("created_at"),
                "transport": "kz_local_control",
                "mission_id": receipt.get("mission_id") or command.get("mission_id"),
                "objective": command.get("objective"),
                "source": command.get("source") or "owner_workbench",
            })
        # An accepted command is already an authorization, even before the
        # completion receipt returns.  It must be shown as waiting, not lost.
        receipt_command_ids = {str(x.get("command_id") or "") for x in rows}
        for command in commands.values():
            if command.get("kind") == "verification_challenge" or command.get("command_id") in receipt_command_ids:
                continue
            if command.get("status") not in {"accepted", "queued_for_verified_connector", "completed"}:
                continue
            rows.append({
                "command_id": command.get("command_id"),
                "decision_pack_id": None,
                "control_receipt_id": command.get("receipt_id"),
                "status": command.get("status"),
                "created_at": command.get("accepted_at") or command.get("created_at"),
                "transport": "kz_local_control",
                "mission_id": command.get("mission_id"),
                "objective": command.get("objective"),
                "source": command.get("source") or "owner_workbench",
            })
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError):
        pass
    try:
        from integrations.async_control_bus import recent_receipts
        for receipt in recent_receipts(limit):
            if not isinstance(receipt, dict):
                continue
            rows.append({
                "command_id": receipt.get("command_id"),
                "decision_pack_id": receipt.get("decision_pack_id"),
                "control_receipt_id": receipt.get("receipt_id"),
                "status": receipt.get("status"),
                "created_at": receipt.get("created_at"),
                "transport": receipt.get("transport") or "github_private_control_bus",
                "mission_id": receipt.get("mission_id"),
                "objective": receipt.get("objective"),
                "source": "async_control_bus",
            })
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError):
        pass
    rows.sort(key=lambda x: str(x.get("created_at") or ""), reverse=True)
    return rows[:limit]


def _authorized(link: dict) -> bool:
    return bool(_control_state().get("verified")) and str(link.get("status") or "") in {
        "accepted", "completed", "running", "acknowledged"
    } and bool(link.get("command_id"))


def active_authorization(mission_id: str | None = None) -> dict | None:
    target = str(mission_id or "").strip()
    for link in command_links():
        if target and str(link.get("mission_id") or "") != target:
            continue
        if _authorized(link):
            return link
    return None


def reconcile_missions() -> dict:
    """Persist the Command binding on existing Missions without inventing work."""
    from core import autonomous_ops

    data = autonomous_ops._load()
    changed = 0
    for mission in data.get("missions", []):
        if not isinstance(mission, dict):
            continue
        link = active_authorization(str(mission.get("mission_id") or ""))
        if not link:
            continue
        updates = {
            "command_id": link.get("command_id"),
            "command_receipt_id": link.get("control_receipt_id"),
            "command_status": link.get("status"),
            "command_transport": link.get("transport"),
            "command_objective": link.get("objective"),
            "command_bound_at": link.get("created_at") or now_iso(),
        }
        if any(mission.get(key) != value for key, value in updates.items()):
            mission.update(updates)
            mission["updated_at"] = now_iso()
            autonomous_ops._event(data, mission, "command_bound", "ChatGPT Command 已绑定到 Mission", {
                "command_id": link.get("command_id"), "transport": link.get("transport"),
            })
            changed += 1
    if changed:
        autonomous_ops._save(data)
    return {"missions_bound": changed}


def reconcile_jobs() -> dict:
    """Attach the active Command/Mission to non-financial scheduled work.

    Historical completed/running tasks are not rewritten.  A task without an
    active authorization remains queued with an explicit wait reason rather
    than being marked completed or silently executed.
    """
    from core import r7_engine
    from core.autonomous_ops import snapshot

    ops = snapshot(sync=True)
    active = ops.get("active_mission") if isinstance(ops, dict) else {}
    mission_id = str((active or {}).get("mission_id") or "")
    link = active_authorization(mission_id) if mission_id else None
    bound = waiting = 0
    with r7_engine.LOCK:
        data = r7_engine._store()
        changed = False
        for job in data.get("items", []):
            if not isinstance(job, dict) or job.get("risk") == "financial" or job.get("state") not in {"queued", "running"}:
                continue
            if job.get("state") == "running":
                continue
            if link:
                updates = {
                    "mission_id": mission_id,
                    "command_id": link.get("command_id"),
                    "command_receipt_id": link.get("control_receipt_id"),
                    "authorization_state": "authorized",
                    "authorization_note": "已绑定 ChatGPT Command，可在到期后执行本地非资金任务。",
                }
                if any(job.get(key) != value for key, value in updates.items()):
                    job.update(updates, updated_at=now_iso())
                    bound += 1
                    changed = True
            elif job.get("schedule_source") == "daily_workforce":
                note = "等待 ChatGPT Command 绑定；未绑定前不会自动执行。"
                if job.get("authorization_state") != "waiting_for_chatgpt" or job.get("authorization_note") != note:
                    job.update(authorization_state="waiting_for_chatgpt", authorization_note=note, updated_at=now_iso())
                    waiting += 1
                    changed = True
        if changed:
            write_json(r7_engine.JOBS, data)
    return {"jobs_bound": bound, "jobs_waiting": waiting, "command_id": (link or {}).get("command_id")}


def job_is_authorized(job: dict) -> bool:
    if not isinstance(job, dict) or job.get("risk") == "financial":
        return False
    command_id = str(job.get("command_id") or "").strip()
    if not command_id:
        return False
    return any(str(link.get("command_id") or "") == command_id and _authorized(link) for link in command_links())


def reconcile() -> dict:
    missions = reconcile_missions()
    jobs = reconcile_jobs()
    return {"generated_at": now_iso(), "mission": missions, "jobs": jobs, "control_verified": bool(_control_state().get("verified"))}


def status() -> dict:
    try:
        from core import r7_engine
        jobs = r7_engine.list_jobs().get("items", [])
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError):
        jobs = []
    return {
        "generated_at": now_iso(),
        "control_verified": bool(_control_state().get("verified")),
        "active_authorization": active_authorization(),
        "commands": command_links(20),
        "tasks": {
            "authorized": sum(x.get("authorization_state") == "authorized" for x in jobs),
            "waiting_for_chatgpt": sum(x.get("authorization_state") == "waiting_for_chatgpt" for x in jobs),
            "running": sum(x.get("state") == "running" for x in jobs),
            "completed": sum(x.get("state") == "completed" for x in jobs),
            "local_execution_receipts": sum(isinstance(x.get("execution_receipt"), dict) for x in jobs),
        },
        "truth_rule": "没有 ChatGPT Command 绑定的非资金任务保持等待；外部发布仍须真实平台回执。",
    }
