"""R7 local command bus: autonomous non-financial work with audited finance guardrails."""

import hashlib
import json
import shutil
import threading
import uuid
from datetime import datetime

from core.autonomy import (
    classify,
    execute_autonomous,
    human_interventions,
    learn_from_job,
    learning_status,
    record_human_intervention,
)
from core.storage import data_root, now_iso, read_json, write_json


JOBS = "r7/jobs.json"
AUDIT = "r7/audit.json"
MIGRATION = "r7/migration.json"
LOCK = threading.RLock()
KINDS = {
    "manual_task": {"name": "运营任务", "mode": "policy"},
    "daily_review": {"name": "本地每日复盘", "mode": "local", "agent": "数据复盘员", "task_type": "review"},
    "diagnostics": {"name": "本地系统体检", "mode": "local", "agent": "系统巡检员", "task_type": "diagnostics"},
}
AGENTS = [
    ("market", "市场情报员", "自动整理可核验的市场观察与公开信号"),
    ("seo", "SEO/GEO 增长员", "自动准备搜索与本地优化内容草稿"),
    ("content", "内容运营员", "自动准备合规内容草稿"),
    ("social", "社媒运营员", "自动准备社媒选题与执行记录"),
    ("video", "短视频运营员", "自动准备短视频脚本"),
    ("local", "本地增长员", "自动梳理区域、服务与增长动作"),
    ("conversion", "用户转化员", "自动分析已验证的咨询与转化"),
    ("review", "数据复盘员", "自动复盘、学习并调整次日计划"),
]


def _store():
    data = read_json(JOBS, {"schema": 1, "items": []})
    return data if isinstance(data, dict) and isinstance(data.get("items"), list) else {"schema": 1, "items": []}


def _audit(kind, job_id, actor, detail):
    if audit_history()["integrity"] != "verified":
        raise ValueError("审计记录校验失败，已暂停任务写入")
    data = read_json(AUDIT, {"schema": 1, "events": []})
    events = data.setdefault("events", [])
    previous = events[-1]["hash"] if events else "0" * 64
    event = {"id": uuid.uuid4().hex, "at": now_iso(), "kind": kind,
             "job_id": job_id, "actor": actor, "detail": detail, "previous_hash": previous}
    canonical = json.dumps(event, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    event["hash"] = hashlib.sha256(canonical.encode("utf-8")).hexdigest()
    events.append(event)
    write_json(AUDIT, data)
    return event


def audit_history():
    with LOCK:
        path = data_root() / AUDIT
        try:
            data = json.loads(path.read_text(encoding="utf-8")) if path.exists() else {"schema": 1, "events": []}
            if not isinstance(data, dict) or not isinstance(data.get("events"), list):
                raise ValueError("invalid audit structure")
        except (OSError, ValueError):
            return {"integrity": "failed", "events": []}
        previous = "0" * 64
        for event in data.get("events", []):
            if not isinstance(event, dict):
                return {"integrity": "failed", "events": []}
            body = {key: value for key, value in event.items() if key != "hash"}
            canonical = json.dumps(body, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
            if event.get("previous_hash") != previous or hashlib.sha256(canonical.encode("utf-8")).hexdigest() != event.get("hash"):
                return {"integrity": "failed", "events": data.get("events", [])[-100:]}
            previous = event["hash"]
        return {"integrity": "verified", "events": data.get("events", [])[-100:]}


def migrate_r6():
    """Take one immutable copy of all pre-R7 user data before R7 writes."""
    with LOCK:
        marker = read_json(MIGRATION, {})
        if marker.get("from") == "R6" and marker.get("to") == "R7":
            return marker
        root = data_root()
        backup = root / "r7" / "backup_r6"
        copied = []
        sources = [path for path in root.rglob("*") if path.is_file()]
        for source in sorted(sources, key=lambda item: item.as_posix()):
            relative = source.relative_to(root)
            if not relative.parts or relative.parts[0] == "r7" or source.name.endswith(".tmp"):
                continue
            target = backup / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)
            copied.append(relative.as_posix())
        marker = {"from": "R6", "to": "R7", "at": now_iso(), "copied": copied,
                  "mode": "full_copy_before_write", "result": "complete"}
        write_json(MIGRATION, marker)
        _audit("migration", "", "system", {"copied": copied, "count": len(copied)})
        return marker


def list_jobs():
    with LOCK:
        items = _store()["items"]
        return {"items": items[:200], "count": len(items),
                "execution": "non_financial_autonomous_financial_platform_manual"}


def _find(data, job_id):
    for job in data["items"]:
        if job["id"] == job_id:
            return job
    raise ValueError("任务不存在")


def create_job(payload):
    kind = str(payload.get("kind") or "manual_task")
    if kind not in KINDS:
        raise ValueError("此类动作未经授权")
    title = str(payload.get("title") or KINDS[kind]["name"]).strip()
    if not title or len(title) > 160:
        raise ValueError("任务名称需为 1 到 160 字")
    due_at = str(payload.get("due_at") or "").strip()
    if due_at:
        try:
            datetime.fromisoformat(due_at)
        except ValueError:
            raise ValueError("执行时间格式不正确") from None

    if kind == "manual_task":
        policy = classify(title)
        mode = "manual" if policy["risk"] == "financial" else "local"
        state = "human_required" if policy["risk"] == "financial" else "queued"
        approved_by = None if policy["risk"] == "financial" else "autonomy_policy"
        agent = policy["agent"]
        task_type = policy["task_type"]
        risk = policy["risk"]
        execution = policy["execution"]
    else:
        meta = KINDS[kind]
        mode, state, approved_by = "local", "queued", "autonomy_policy"
        agent, task_type = meta["agent"], meta["task_type"]
        risk, execution = "non_financial", "autonomous"

    job = {
        "id": uuid.uuid4().hex, "kind": kind, "title": title,
        "mode": mode, "agent": agent, "task_type": task_type,
        "risk": risk, "execution": execution,
        "state": state, "progress": 0, "completed_steps": 0,
        "total_steps": 1, "due_at": due_at, "created_at": now_iso(),
        "updated_at": now_iso(), "approved_by": approved_by,
        "result": None, "error": None, "retry_count": 0,
    }
    with LOCK:
        if audit_history()["integrity"] != "verified":
            raise ValueError("审计记录校验失败，已暂停任务写入")
        data = _store()
        data["items"].insert(0, job)
        write_json(JOBS, data)
        _audit("job_created", job["id"], "bridge_or_local", {
            "kind": kind, "title": title, "risk": risk, "execution": execution,
        })
        if state == "human_required":
            record_human_intervention(job)
            _audit("job_routed_to_platform_manual", job["id"], "autonomy_policy", {"reason": "financial"})
        else:
            _audit("job_auto_queued", job["id"], "autonomy_policy", {"task_type": task_type})
    return job


def command(payload):
    action = str(payload.get("action") or "")
    job_id = str(payload.get("id") or "")
    actor = "local_operator"
    with LOCK:
        if audit_history()["integrity"] != "verified":
            raise ValueError("审计记录校验失败，已暂停任务写入")
        data = _store()
        job = _find(data, job_id)
        before = job["state"]
        if action == "approve" and before == "awaiting_approval":
            job["state"] = "queued"
            job["approved_by"] = actor
        elif action == "start" and before == "queued" and job["mode"] == "manual":
            job["state"] = "running"
        elif action == "complete" and before == "running" and job["mode"] == "manual":
            outcome = str(payload.get("outcome") or "").strip()
            if not outcome or len(outcome) > 1000:
                raise ValueError("请填写 1 到 1000 字的真实完成结果")
            job.update(state="completed", completed_steps=1, progress=100,
                       result={"outcome": outcome, "source": "人工确认"})
        elif action == "cancel" and before in {"awaiting_approval", "queued", "running", "failed"}:
            job["state"] = "cancelled"
        elif action == "retry" and before == "failed" and job.get("risk") != "financial":
            job.update(state="queued", error=None, completed_steps=0, progress=0,
                       approved_by="autonomy_policy")
        else:
            raise ValueError("当前任务状态不允许此操作")
        job["updated_at"] = now_iso()
        write_json(JOBS, data)
        _audit("job_" + action, job_id, actor, {"from": before, "to": job["state"]})
        return job


def _run(job_id):
    with LOCK:
        data = _store()
        job = _find(data, job_id)
        if job["state"] != "queued" or job["mode"] != "local" or not job.get("approved_by"):
            return
        job["state"] = "running"
        job["updated_at"] = now_iso()
        kind = job["kind"]
        write_json(JOBS, data)
        _audit("job_started", job_id, "scheduler", {"kind": kind, "task_type": job.get("task_type")})

    try:
        if kind == "daily_review":
            from ai_center.daily_review import generate_review
            raw = generate_review(None)
            result = {"summary": raw.get("summary", {}).get("headline", "复盘已完成"),
                      "next_actions": [x.get("title", "") if isinstance(x, dict) else str(x)
                                       for x in raw.get("tomorrow_plan", {}).get("tasks", [])[:3]],
                      "source_note": "仅使用本机已验证数据和已记录执行结果生成。"}
        elif kind == "diagnostics":
            from integrations.manager import system_diagnostics
            diagnostic = system_diagnostics()
            result = {"summary": "系统体检已完成",
                      "key_findings": [f"通过 {diagnostic['summary'].get('passed', 0)} 项",
                                       f"失败 {diagnostic['summary'].get('failed', 0)} 项"],
                      "source_note": "结果来自本机系统体检接口。"}
        else:
            result = execute_autonomous(job)
        state, error = "completed", None
    except (ValueError, OSError, KeyError, TypeError) as exc:
        state, error, result = "failed", str(exc)[:300], None

    with LOCK:
        data = _store()
        job = _find(data, job_id)
        retry_count = int(job.get("retry_count") or 0)
        if state == "failed" and retry_count < 2:
            job.update(state="queued", result=None, error=error, updated_at=now_iso(),
                       completed_steps=0, progress=0, retry_count=retry_count + 1)
            write_json(JOBS, data)
            _audit("job_auto_retry", job_id, "scheduler", {"error": error, "retry_count": retry_count + 1})
            return
        job.update(state=state, result=result, error=error, updated_at=now_iso(),
                   completed_steps=1 if state == "completed" else 0,
                   progress=100 if state == "completed" else 0,
                   retry_count=retry_count)
        write_json(JOBS, data)
        _audit("job_" + state, job_id, "scheduler", {"error": error})
        learn_from_job(job)


def run_due_jobs(allowed_task_types=None):
    now = datetime.now().astimezone()
    allowed = {str(item or "").strip() for item in (allowed_task_types or []) if str(item or "").strip()}
    with LOCK:
        if audit_history()["integrity"] != "verified":
            raise ValueError("审计记录校验失败，已暂停任务执行")
        due = []
        for job in _store()["items"]:
            if job["state"] != "queued" or job["mode"] != "local":
                continue
            if allowed and str(job.get("task_type") or "") not in allowed:
                continue
            when = datetime.fromisoformat(job["due_at"]) if job["due_at"] else now
            if when.tzinfo is None:
                when = when.astimezone()
            if when <= now:
                due.append(job["id"])
    for job_id in due:
        _run(job_id)
    return {"processed": len(due), "at": now_iso(), "allowed_task_types": sorted(allowed)}


def recover_interrupted():
    """Recover interrupted work and migrate legacy approval-era jobs into the current policy."""
    with LOCK:
        data = _store()
        changed = False
        for job in data["items"]:
            if job.get("state") == "running" and job.get("mode") == "local":
                job.update(state="queued", error="程序中断，已自动重新排队", updated_at=now_iso(),
                           approved_by="autonomy_policy")
                _audit("job_requeued_after_interrupt", job["id"], "system", {})
                changed = True
                continue
            if job.get("state") != "awaiting_approval":
                continue
            policy = classify(job.get("title", ""))
            if policy["risk"] == "financial":
                job.update(state="human_required", mode="manual", approved_by=None,
                           risk="financial", execution="platform_manual",
                           agent=policy["agent"], task_type=policy["task_type"],
                           error=None, updated_at=now_iso())
                record_human_intervention(job)
                _audit("job_migrated_to_platform_manual", job["id"], "autonomy_policy", {"reason": "financial"})
            else:
                job.update(state="queued", mode="local", approved_by="autonomy_policy",
                           risk="non_financial", execution="autonomous",
                           agent=policy["agent"], task_type=policy["task_type"],
                           error=None, updated_at=now_iso())
                _audit("job_migrated_to_autonomy", job["id"], "autonomy_policy", {"task_type": policy["task_type"]})
            changed = True
        if changed:
            write_json(JOBS, data)


def agent_registry():
    return {"items": [{"id": key, "name": name, "purpose": purpose,
                       "status": "role_defined", "execution": "autonomous_non_financial"}
                      for key, name, purpose in AGENTS]}


def engine_status():
    jobs = list_jobs()["items"]
    states = ("awaiting_approval", "human_required", "queued", "running", "completed", "failed", "cancelled")
    return {
        "jobs": {state: sum(x.get("state") == state for x in jobs) for state in states},
        "next_local_job": next((x["title"] for x in jobs if x.get("state") == "queued" and x.get("mode") == "local"), None),
        "migration": read_json(MIGRATION, {"result": "pending"}),
        "audit_integrity": audit_history()["integrity"],
        "autonomy_policy": "非资金任务自动执行；资金事项仅记录并交平台人工处理",
        "human_interventions": human_interventions().get("items", [])[:20],
        "learning": learning_status(),
    }
