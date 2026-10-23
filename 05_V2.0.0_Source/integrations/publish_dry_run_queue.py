"""Truthful real-device dry-run queue for approved social publication plans.

The queue bridges a verified publication plan to the already-bound Android
runtime.  It deliberately does not click the platform's final publish control
and it never marks content as published.  Real publication still requires a
platform Content ID + URL receipt.
"""
from __future__ import annotations

from core.storage import now_iso, read_json, write_json
from integrations import android_device

TASK_KIND = "douyin_publish_dry_run"
ACTIVE_TASK_STATES = {"queued", "staging", "ready_for_owner_final_publish", "needs_human"}


def _runtime():
    value = read_json(android_device.RUNTIME_PATH, {})
    if not isinstance(value, dict):
        value = {}
    value.setdefault("devices", {})
    return value


def queue_plan(plan: dict, account: dict, video: dict) -> dict:
    """Attach one approved plan to its verified bound real phone.

    This is an idempotent queueing operation only.  It does not launch, click,
    type, upload or publish on the social platform.
    """
    plan = plan if isinstance(plan, dict) else {}
    account = account if isinstance(account, dict) else {}
    video = video if isinstance(video, dict) else {}
    platform = str(plan.get("platform") or account.get("platform") or "").strip()
    if platform != "抖音":
        return {"queued": False, "reason": "pilot_only_douyin", "publishes_content": False}
    if account.get("connection_status") != "已验证可发布":
        return {"queued": False, "reason": "account_not_verified", "publishes_content": False}
    device_id = str(account.get("device_id") or "").strip()
    if not device_id:
        return {"queued": False, "reason": "account_has_no_bound_device", "publishes_content": False}

    snapshot = android_device.scan_and_sync()
    device = next((item for item in snapshot.get("devices", []) if item.get("device_id") == device_id), None)
    if not device or not device.get("connected"):
        return {"queued": False, "reason": "bound_device_offline", "device_id": device_id, "publishes_content": False}

    plan_id = str(plan.get("id") or "").strip()
    video_id = str(plan.get("video_id") or video.get("id") or "").strip()
    if not plan_id or not video_id:
        return {"queued": False, "reason": "missing_plan_or_video_id", "publishes_content": False}

    runtime = _runtime()
    entry = runtime.setdefault("devices", {}).setdefault(device_id, {"mode": "r8", "keep_awake": False})
    existing = entry.get("current_task") if isinstance(entry.get("current_task"), dict) else None
    if existing and existing.get("plan_id") == plan_id and existing.get("status") in ACTIVE_TASK_STATES:
        return {"queued": True, "idempotent": True, "task": existing, "publishes_content": False}
    if existing and existing.get("status") in ACTIVE_TASK_STATES and existing.get("plan_id") != plan_id:
        return {
            "queued": False,
            "reason": "device_busy_with_another_publish_dry_run",
            "device_id": device_id,
            "current_task": existing,
            "publishes_content": False,
        }

    task = {
        "task_id": f"DRYRUN-{plan_id}",
        "kind": TASK_KIND,
        "plan_id": plan_id,
        "video_id": video_id,
        "campaign_id": str(plan.get("campaign_id") or video.get("campaign_id") or ""),
        "account_id": str(plan.get("account_id") or account.get("id") or ""),
        "platform": "抖音",
        "status": "queued",
        "stage": "等待真机干跑",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "final_publish_allowed": False,
        "publishes_content": False,
        "next_action": "准备 FINAL.MP4 真机干跑；必须停在抖音最终发布按钮之前，等待老板现场确认。",
        "truth_rule": "进入真机干跑不等于发布成功；只有真实 Content ID + URL / Receipt 才能计为已发布。",
    }
    entry["current_task"] = task
    entry["updated_at"] = now_iso()
    write_json(android_device.RUNTIME_PATH, runtime)
    try:
        android_device._append_audit({
            "device_id": device_id,
            "action": "publish_dry_run_queued",
            "actor": "system",
            "task_id": task["task_id"],
            "account_id": task["account_id"],
            "result": "ok",
            "detail": {"plan_id": plan_id, "video_id": video_id, "platform": "抖音", "publishes_content": False},
        })
    except (OSError, ValueError, RuntimeError, TypeError):
        pass
    return {"queued": True, "idempotent": False, "task": task, "publishes_content": False}
