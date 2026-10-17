"""R8-23.2 runtime safety helpers for the first landing pilot."""
from __future__ import annotations

from datetime import datetime, timedelta

from core.storage import now_iso, write_json

DEDUP_WINDOW_MINUTES = 15
STALE_RUNNING_MINUTES = 90
SOCIAL_PLATFORM_ORDER = ("douyin", "xiaohongshu", "wechat_channels", "kuaishou", "bilibili", "weibo")


def _parse(value):
    try:
        return datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    except ValueError:
        return None


def duplicate_job(payload: dict) -> dict | None:
    """Return an equivalent recent queued/running job instead of creating another."""
    title = str(payload.get("title") or "").strip()
    kind = str(payload.get("kind") or "manual_task")
    due_at = str(payload.get("due_at") or "").strip()
    if not title:
        return None
    try:
        from core import r7_engine
        jobs = r7_engine.list_jobs().get("items", [])
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError, AttributeError):
        return None
    now = datetime.now().astimezone()
    for job in jobs:
        if not isinstance(job, dict) or job.get("state") not in {"queued", "running"}:
            continue
        if str(job.get("title") or "").strip() != title or str(job.get("kind") or "") != kind:
            continue
        existing_due = str(job.get("due_at") or "").strip()
        if due_at or existing_due:
            if due_at == existing_due:
                return job
            continue
        created = _parse(job.get("created_at"))
        if created is None:
            continue
        if created.tzinfo is None:
            created = created.astimezone()
        if now - created <= timedelta(minutes=DEDUP_WINDOW_MINUTES):
            return job
    return None


def recover_stale_running_jobs(max_minutes: int = STALE_RUNNING_MINUTES) -> dict:
    """Requeue stale non-financial running jobs after crash/restart.

    Financial jobs are never touched. A stale job is retried at most one more
    time here; the existing R7 retry guard still applies during execution.
    """
    try:
        from core import r7_engine
    except ImportError:
        return {"recovered": 0, "items": []}
    now = datetime.now().astimezone()
    recovered = []
    with r7_engine.LOCK:
        data = r7_engine._store()
        changed = False
        for job in data.get("items", []):
            if not isinstance(job, dict) or job.get("state") != "running" or job.get("risk") == "financial":
                continue
            updated = _parse(job.get("updated_at") or job.get("created_at"))
            if updated is None:
                continue
            if updated.tzinfo is None:
                updated = updated.astimezone()
            age = int((now - updated).total_seconds() // 60)
            if age < max(1, int(max_minutes)):
                continue
            retries = int(job.get("retry_count") or 0)
            if retries >= 3:
                job.update(state="failed", error="stale_running_recovery_exhausted", updated_at=now_iso())
                event = "job_stale_failed"
            else:
                job.update(
                    state="queued", progress=0, completed_steps=0,
                    retry_count=retries + 1, error="recovered_after_stale_running",
                    recovery_state="auto_requeued_after_restart_or_worker_loss",
                    updated_at=now_iso(),
                )
                event = "job_stale_requeued"
            recovered.append({"id": job.get("id"), "age_minutes": age, "state": job.get("state")})
            changed = True
            try:
                r7_engine._audit(event, job.get("id"), "r8_23_2_recovery", {"age_minutes": age, "retry_count": job.get("retry_count")})
            except (OSError, ValueError, RuntimeError, TypeError, KeyError):
                pass
        if changed:
            write_json(r7_engine.JOBS, data)
    return {"recovered": len(recovered), "items": recovered, "at": now_iso()}


def task_integrity() -> dict:
    try:
        from core import r7_engine
        jobs = r7_engine.list_jobs().get("items", [])
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError, AttributeError):
        jobs = []
    now = datetime.now().astimezone()
    duplicate_keys = {}
    stale = []
    orphan = []
    for job in jobs:
        if not isinstance(job, dict):
            continue
        if job.get("state") in {"queued", "running"}:
            key = (str(job.get("command_id") or ""), str(job.get("title") or "").strip(), str(job.get("due_at") or ""))
            duplicate_keys.setdefault(key, []).append(job.get("id"))
        if job.get("state") == "running":
            updated = _parse(job.get("updated_at") or job.get("created_at"))
            if updated:
                if updated.tzinfo is None:
                    updated = updated.astimezone()
                if now - updated >= timedelta(minutes=STALE_RUNNING_MINUTES):
                    stale.append(job.get("id"))
        if job.get("state") == "queued" and job.get("schedule_source") == "daily_workforce" and not job.get("command_id"):
            orphan.append(job.get("id"))
    duplicates = [ids for key, ids in duplicate_keys.items() if key[1] and len(ids) > 1]
    try:
        integrity = r7_engine.audit_history().get("integrity")
    except Exception:
        integrity = "unknown"
    return {
        "audit_integrity": integrity,
        "duplicate_groups": duplicates,
        "duplicate_count": sum(max(0, len(x) - 1) for x in duplicates),
        "stale_running": stale,
        "orphan_waiting": orphan,
        "healthy": integrity == "verified" and not duplicates and not stale,
        "generated_at": now_iso(),
    }


def social_pilot() -> dict:
    """Choose only one real social platform for the first closed-loop acceptance."""
    try:
        from integrations import seo_geo_connector_router_v2 as router
        snap = router.snapshot(check_live=False)
        rows = {str(x.get("id") or ""): x for x in snap.get("connectors", []) if isinstance(x, dict)}
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError, AttributeError):
        rows = {}
    selected = None
    candidates = []
    for platform in SOCIAL_PLATFORM_ORDER:
        row = rows.get(platform)
        if not row:
            continue
        item = {
            "platform": platform,
            "route_ready": bool(row.get("software_route_ready")),
            "external_verified": bool(row.get("external_verified")),
            "route_state": row.get("route_state"),
        }
        candidates.append(item)
        if selected is None and item["route_ready"]:
            selected = item
    return {
        "strategy": "one_real_platform_first_then_copy",
        "selected": selected,
        "candidates": candidates,
        "publish_gate": "QC + account/action authorization + real Post ID/URL Receipt",
        "multi_platform_autonomy": False,
        "generated_at": now_iso(),
    }


def metric_semantics() -> dict:
    return {
        "windows": ["today", "7d", "30d", "all_time"],
        "state_order": ["configured", "invoked", "generated", "qc_passed", "published", "submitted", "crawled", "indexed", "external_verified"],
        "colors": {
            "waiting_or_warning": "amber",
            "running_or_queued": "primary",
            "completed_or_verified": "green",
            "failed_or_abnormal": "red",
            "not_started_or_not_applicable": "gray",
        },
        "rule": "数据源接通不等于经营结果；配置成功不等于外部验证成功。",
    }
