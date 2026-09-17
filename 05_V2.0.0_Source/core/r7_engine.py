"""R7 local command bus with autonomous non-financial execution and audit history."""

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

FINANCIAL_TERMS = (
    "支付", "付款", "退款", "提现", "结算", "改价", "调价", "充值", "转账",
    "打款", "赔付", "补贴", "佣金", "资金", "余额", "收款", "扣款", "财务",
)

KINDS = {
    "manual_task": {"name": "通用运营任务", "mode": "local", "agent": "运营协调员"},
    "daily_review": {"name": "本地每日复盘", "mode": "local", "agent": "数据复盘员"},
    "diagnostics": {"name": "本地系统体检", "mode": "local", "agent": "系统巡检员"},
    "market_research": {"name": "本地市场调研", "mode": "local", "agent": "市场情报员"},
    "seo_draft": {"name": "SEO/GEO 内容准备", "mode": "local", "agent": "SEO/GEO 增长员"},
    "local_growth": {"name": "本地增长任务", "mode": "local", "agent": "本地增长员"},
    "finance_task": {"name": "资金相关任务", "mode": "manual", "agent": "本机管理员"},
}

AGENTS = [
    ("market", "市场情报员", "自动整理可核验的市场观察和公开信号"),
    ("seo", "SEO/GEO 增长员", "自动准备搜索内容与本地优化草稿"),
    ("content", "内容运营员", "自动准备内容草稿并记录结果"),
    ("social", "社媒运营员", "自动准备社媒选题与素材计划"),
    ("video", "短视频运营员", "自动准备短视频脚本和发布计划"),
    ("local", "本地增长员", "自动梳理区域、服务和本地增长任务"),
    ("conversion", "用户转化员", "自动分析已验证的咨询与转化"),
    ("review", "数据复盘员", "自动执行复盘、学习记忆和次日计划"),
]


def _store():
    data = read_json(JOBS, {"schema": 2, "items": []})
    return data if isinstance(data, dict) and isinstance(data.get("items"), list) else {"schema": 2, "items": []}


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
            if not relative.parts or relative.parts[0] == "r7":
                continue
            if source.name.endswith(".tmp"):
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


def _financial(title, kind=""):
    text = f"{kind} {title}".lower()
    return kind == "finance_task" or any(term.lower() in text for term in FINANCIAL_TERMS)


def list_jobs():
    with LOCK:
        items = _store()["items"]
        return {
            "items": items[:200],
            "count": len(items),
            "execution": "auto_non_financial_finance_human_only",
            "policy": "除资金类任务外默认自动批准并由本地调度器执行；资金类任务保留人工审批。",
        }


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

    finance = _financial(title, kind)
    actual_kind = "finance_task" if finance else kind
    mode = "manual" if finance else KINDS[actual_kind]["mode"]
    state = "awaiting_approval" if finance else "queued"
    approved_by = None if finance else "policy:auto_non_financial"
    job = {
        "id": uuid.uuid4().hex,
        "kind": actual_kind,
        "title": title,
        "mode": mode,
        "agent": KINDS[actual_kind]["agent"],
        "state": state,
        "progress": 0,
        "completed_steps": 0,
        "total_steps": 1,
        "due_at": due_at,
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "approved_by": approved_by,
        "approval_policy": "finance_human_only" if finance else "auto_non_financial",
        "result": None,
        "error": None,
    }
    with LOCK:
        if audit_history()["integrity"] != "verified":
            raise ValueError("审计记录校验失败，已暂停任务写入")
        data = _store()
        data["items"].insert(0, job)
        write_json(JOBS, data)
        _audit("job_created", job["id"], "owner", {"kind": actual_kind, "title": title, "policy": job["approval_policy"]})
        if not finance:
            _audit("job_auto_approved", job["id"], "policy_engine", {"reason": "non_financial"})
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
        elif action == "retry" and before == "failed":
            if job.get("approval_policy") == "finance_human_only" and not job.get("approved_by"):
                raise ValueError("资金任务重试前仍需人工批准")
            job.update(state="queued", error=None, completed_steps=0, progress=0)
        else:
            raise ValueError("当前任务状态不允许此操作")
        job["updated_at"] = now_iso()
        write_json(JOBS, data)
        _audit("job_" + action, job_id, actor, {"from": before, "to": job["state"]})
        return job


def _region_service(title):
    region = "涟水" if "涟水" in title else "淮安" if "淮安" in title else "涟水"
    service_map = ("水电维修", "家电维修", "管道疏通", "门锁维修", "马桶维修", "上门维修", "维修")
    service = next((item for item in service_map if item in title), "本地维修")
    return region, service


def _run_generic(job):
    title = job["title"]
    region, service = _region_service(title)
    if any(word in title for word in ("市场", "调研", "数据收集", "公开数据", "需求", "维修数据", "关键词")):
        from operations.workspace import demand_insights, generate_calendar
        insight = demand_insights()
        calendar = generate_calendar({"region": region, "service": service})
        top = "、".join(item["name"] for item in insight.get("top_needs", [])[:5]) or "暂无足够公开信号"
        return {
            "outcome": f"已自动整理{region}{service}现有公开研究信号：共 {insight.get('public_signal_count', 0)} 条；当前可见需求方向：{top}。已同步生成 7 天本地增长日历。",
            "source": "local_public_signal_library",
            "limitations": "当前结果基于R7已同步的公开研究信号，不把关键词数量解释为真实客户、订单或市场份额。",
            "calendar_days": len(calendar.get("items", [])),
        }
    if any(word in title.lower() for word in ("seo", "geo", "内容", "文案", "短视频", "脚本")):
        from promotion.content_center import generate_geo, generate_seo, generate_video
        payload = {"region": region, "service": service, "keyword": f"{region}{service}服务", "audience": "本地有维修需求的用户"}
        if "短视频" in title or "脚本" in title:
            record = generate_video(payload)
        elif "geo" in title.lower():
            record = generate_geo(payload)
        else:
            record = generate_seo(payload)
        return {"outcome": f"已自动生成{record.get('kind', '内容')}并保存到内容增长记录。", "source": "local_content_workflow"}
    if any(word in title for word in ("复盘", "明日计划", "第二天计划", "计划优化")):
        from ai_center.daily_review import generate_review
        review = generate_review(None)
        return {"outcome": "已自动完成复盘并生成下一日计划。", "headline": review.get("summary", {}).get("headline", "复盘已完成"), "source": "local_review_workflow"}
    from operations.workspace import command_center
    center = command_center()
    return {
        "outcome": "已自动完成通用运营检查，并记录当前任务、内容、关键词和数据接入状态。",
        "source": "local_operations_center",
        "snapshot": {
            "task_counts": center.get("task_counts"),
            "draft_count": center.get("draft_count"),
            "keyword_count": center.get("keyword_count"),
        },
    }


def _record_learning(job, result):
    try:
        from memory.memory_store import remember
        statement = f"任务“{job['title']}”已由{job['agent']}自动执行完成。"
        evidence = f"job_id={job['id']}; source={result.get('source', 'local')}"
        remember("自动运营学习", statement, evidence)
    except (OSError, ValueError, KeyError, TypeError):
        pass


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
        _audit("job_started", job_id, "scheduler", {"kind": kind, "policy": job.get("approval_policy")})
    try:
        if kind == "daily_review":
            from ai_center.daily_review import generate_review
            review = generate_review(None)
            result = {"headline": review.get("summary", {}).get("headline", "复盘已完成"), "source": "daily_review"}
        elif kind == "diagnostics":
            from integrations.manager import system_diagnostics
            result = {"summary": system_diagnostics()["summary"], "source": "diagnostics"}
        else:
            result = _run_generic(job)
        state, error = "completed", None
    except (ValueError, OSError, KeyError, TypeError) as exc:
        state, error, result = "failed", str(exc)[:300], None
    with LOCK:
        data = _store()
        job = _find(data, job_id)
        job.update(state=state, result=result, error=error, updated_at=now_iso(),
                   completed_steps=1 if state == "completed" else 0,
                   progress=100 if state == "completed" else 0)
        write_json(JOBS, data)
        _audit("job_" + state, job_id, "scheduler", {"error": error})
    if state == "completed" and result:
        _record_learning(job, result)


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
                job.update(state="queued", error="程序中断，已自动恢复到待执行队列", updated_at=now_iso())
                _audit("job_recovered", job["id"], "system", {})
        write_json(JOBS, data)


def agent_registry():
    return {"items": [{"id": key, "name": name, "purpose": purpose,
                       "status": "role_defined", "execution": "auto_non_financial"}
                      for key, name, purpose in AGENTS]}


def engine_status():
    jobs = list_jobs()["items"]
    return {
        "jobs": {state: sum(x["state"] == state for x in jobs) for state in
                 ("awaiting_approval", "queued", "running", "completed", "failed")},
        "next_local_job": next((x["title"] for x in jobs if x["state"] == "queued" and x["mode"] == "local"), None),
        "migration": read_json(MIGRATION, {"result": "pending"}),
        "audit_integrity": audit_history()["integrity"],
        "autonomy_policy": "auto_non_financial_finance_human_only",
        "learning_mode": "audited_memory_and_plan_optimization",
    }
