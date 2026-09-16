"""R7 local command bus: approved jobs, truthful progress and audit history."""

import hashlib
import json
import shutil
import threading
import uuid
from datetime import datetime

from core.storage import data_root, now_iso, read_json, write_json


JOBS = "r7/jobs.json"
AUDIT = "r7/audit.json"
MIGRATION = "r7/migration.json"
LOCK = threading.RLock()
KINDS = {
    "manual_task": {"name": "人工运营任务", "mode": "manual", "agent": "运营协调员"},
    "daily_review": {"name": "本地每日复盘", "mode": "local", "agent": "数据复盘员"},
    "diagnostics": {"name": "本地系统体检", "mode": "local", "agent": "系统巡检员"},
}
AGENTS = [
    ("market", "市场情报员", "整理可核验的市场观察"),
    ("seo", "SEO/GEO 增长员", "准备搜索内容草稿"),
    ("content", "内容运营员", "准备待审核内容"),
    ("social", "社媒运营员", "准备社媒选题，发布需审批"),
    ("video", "短视频运营员", "准备脚本，发布需审批"),
    ("local", "本地增长员", "梳理区域与服务信息"),
    ("conversion", "用户转化员", "分析已验证的咨询与转化"),
    ("review", "数据复盘员", "执行本地复盘与结果核对"),
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
    """Take one immutable copy of R6 user data before R7 starts writing."""
    with LOCK:
        marker = read_json(MIGRATION, {})
        if marker.get("from") == "R6" and marker.get("to") == "R7":
            return marker
        root = data_root()
        backup = root / "r7" / "backup_r6"
        copied = []
        for relative in ("operations/tasks.json", "operations/promotion_calendar.json",
                         "memory/learning_memory.json", "memory/experiments.json",
                         "integrations/config.json", "integrations/ai_key.bin"):
            source = root / relative
            if source.is_file():
                target = backup / relative
                target.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(source, target)
                copied.append(relative)
        marker = {"from": "R6", "to": "R7", "at": now_iso(), "copied": copied,
                  "mode": "copy_before_write", "result": "complete"}
        write_json(MIGRATION, marker)
        _audit("migration", "", "system", {"copied": copied})
        return marker


def list_jobs():
    with LOCK:
        items = _store()["items"]
        return {"items": items[:200], "count": len(items), "execution": "approval_required"}


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
    job = {"id": uuid.uuid4().hex, "kind": kind, "title": title,
           "mode": KINDS[kind]["mode"], "agent": KINDS[kind]["agent"],
           "state": "awaiting_approval", "progress": 0, "completed_steps": 0,
           "total_steps": 1, "due_at": due_at, "created_at": now_iso(),
           "updated_at": now_iso(), "approved_by": None, "result": None, "error": None}
    with LOCK:
        if audit_history()["integrity"] != "verified":
            raise ValueError("审计记录校验失败，已暂停任务写入")
        data = _store()
        data["items"].insert(0, job)
        write_json(JOBS, data)
        _audit("job_created", job["id"], "owner", {"kind": kind, "title": title})
    return job


def command(payload):
    action = str(payload.get("action") or "")
    job_id = str(payload.get("id") or "")
    # This is a single-user loopback application, not an authenticated team service.
    # Never accept a caller-supplied name as proof of a person's identity.
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
        elif action == "retry" and before == "failed" and job["approved_by"]:
            job.update(state="queued", error=None, completed_steps=0, progress=0)
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
        if job["state"] != "queued" or job["mode"] != "local" or not job["approved_by"]:
            return
        job["state"] = "running"
        job["updated_at"] = now_iso()
        kind = job["kind"]
        write_json(JOBS, data)
        _audit("job_started", job_id, "scheduler", {"kind": kind})
    try:
        if kind == "daily_review":
            from ai_center.daily_review import generate_review
            result = generate_review(None)
            result = {"headline": result.get("summary", {}).get("headline", "复盘已完成")}
        elif kind == "diagnostics":
            from integrations.manager import system_diagnostics
            result = {"summary": system_diagnostics()["summary"]}
        else:
            raise ValueError("本地执行器不支持此动作")
        state, error = "completed", None
    except (ValueError, OSError, KeyError) as exc:
        state, error, result = "failed", str(exc)[:300], None
    with LOCK:
        data = _store()
        job = _find(data, job_id)
        job.update(state=state, result=result, error=error, updated_at=now_iso(),
                   completed_steps=1 if state == "completed" else 0,
                   progress=100 if state == "completed" else 0)
        write_json(JOBS, data)
        _audit("job_" + state, job_id, "scheduler", {"error": error})


def run_due_jobs():
    now = datetime.now().astimezone()
    with LOCK:
        if audit_history()["integrity"] != "verified":
            raise ValueError("审计记录校验失败，已暂停任务执行")
        due = []
        for job in _store()["items"]:
            if job["state"] != "queued" or job["mode"] != "local":
                continue
            when = datetime.fromisoformat(job["due_at"]) if job["due_at"] else now
            if when.tzinfo is None:
                when = when.astimezone()
            if when <= now:
                due.append(job["id"])
    for job_id in due:
        _run(job_id)
    return {"processed": len(due), "at": now_iso()}


def recover_interrupted():
    with LOCK:
        data = _store()
        for job in data["items"]:
            if job["state"] == "running" and job["mode"] == "local":
                job.update(state="failed", error="程序中断，需人工确认后重试", updated_at=now_iso())
                _audit("job_interrupted", job["id"], "system", {})
        write_json(JOBS, data)


def agent_registry():
    return {"items": [{"id": key, "name": name, "purpose": purpose,
                       "status": "role_defined", "execution": "requires_approved_job"}
                      for key, name, purpose in AGENTS]}


def engine_status():
    jobs = list_jobs()["items"]
    return {"jobs": {state: sum(x["state"] == state for x in jobs) for state in
                      ("awaiting_approval", "queued", "running", "completed", "failed")},
            "next_local_job": next((x["title"] for x in jobs if x["state"] == "queued" and x["mode"] == "local"), None),
            "migration": read_json(MIGRATION, {"result": "pending"}),
            "audit_integrity": audit_history()["integrity"]}
