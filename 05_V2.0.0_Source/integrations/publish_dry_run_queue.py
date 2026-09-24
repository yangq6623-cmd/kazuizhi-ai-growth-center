"""Truthful real-device dry-run queue for R8-12 durable publication plans.

The queue receives a stable Account Asset route.  The stable device asset ID is
translated to the real ADB ID only at execution time.  Changing phones therefore
does not change the account identity or Mission history.

This module queues preparation only.  It never clicks the platform's final
publish control and never marks content as published.
"""
from __future__ import annotations

from core.storage import now_iso, read_json, write_json
from integrations import android_device
from integrations.account_router import normalize_platform

TASK_KIND = "douyin_publish_dry_run"
ACTIVE_TASK_STATES = {"queued", "staging", "ready_for_owner_final_publish", "needs_human"}


def _runtime():
    value = read_json(android_device.RUNTIME_PATH, {})
    if not isinstance(value, dict):
        value = {}
    value.setdefault("devices", {})
    return value


def _resolve_route(route_or_account: dict) -> tuple[dict, dict | None]:
    value = route_or_account if isinstance(route_or_account, dict) else {}
    # R8-12 route object.
    if isinstance(value.get("account"), dict):
        return value.get("account") or {}, value.get("device") if isinstance(value.get("device"), dict) else None
    # Legacy compatibility for already-created plans during an in-place upgrade.
    account = value
    device_id = str(account.get("device_id") or "").strip()
    return account, ({"device_id": device_id, "legacy_device_id": device_id, "connection": "connected"} if device_id else None)


def queue_plan(plan: dict, route_or_account: dict, video: dict) -> dict:
    """Queue one approved plan on its currently selected real device.

    Idempotency is by plan_id.  A device busy with another active dry-run will
    not be overwritten.
    """
    plan = plan if isinstance(plan, dict) else {}
    video = video if isinstance(video, dict) else {}
    account, device_asset = _resolve_route(route_or_account)
    platform_code = normalize_platform(plan.get("platform_code") or plan.get("platform") or account.get("platform"))
    if platform_code != "douyin":
        return {"queued": False, "reason": "pilot_only_douyin", "publishes_content": False}

    # New route objects already passed the authorization gate.  Legacy inputs
    # still require the old verified status for backward compatibility.
    if isinstance(route_or_account, dict) and route_or_account.get("route_kind"):
        if route_or_account.get("status") != "ready" or route_or_account.get("route_kind") != "real_device":
            return {"queued": False, "reason": "route_not_real_device_ready", "publishes_content": False}
    elif account.get("connection_status") != "已验证可发布":
        return {"queued": False, "reason": "account_not_verified", "publishes_content": False}

    stable_device_id = str((device_asset or {}).get("device_id") or plan.get("device_asset_id") or "").strip()
    adb_device_id = str((device_asset or {}).get("legacy_device_id") or account.get("device_id") or "").strip()
    if not adb_device_id:
        return {
            "queued": False,
            "reason": "account_has_no_execution_device",
            "device_asset_id": stable_device_id or None,
            "publishes_content": False,
        }

    snapshot = android_device.scan_and_sync()
    device = next((item for item in snapshot.get("devices", []) if item.get("device_id") == adb_device_id), None)
    if not device or not device.get("connected"):
        return {
            "queued": False,
            "reason": "execution_device_offline",
            "device_asset_id": stable_device_id or None,
            "adb_device_id": adb_device_id,
            "publishes_content": False,
        }

    plan_id = str(plan.get("id") or "").strip()
    video_id = str(plan.get("video_id") or video.get("id") or "").strip()
    account_id = str(plan.get("account_asset_id") or plan.get("account_id") or account.get("account_id") or account.get("id") or "").strip()
    if not plan_id or not video_id or not account_id:
        return {"queued": False, "reason": "missing_plan_video_or_account_id", "publishes_content": False}

    runtime = _runtime()
    entry = runtime.setdefault("devices", {}).setdefault(adb_device_id, {"mode": "r8", "keep_awake": False})
    existing = entry.get("current_task") if isinstance(entry.get("current_task"), dict) else None
    if existing and existing.get("plan_id") == plan_id and existing.get("status") in ACTIVE_TASK_STATES:
        return {"queued": True, "idempotent": True, "task": existing, "publishes_content": False}
    if existing and existing.get("status") in ACTIVE_TASK_STATES and existing.get("plan_id") != plan_id:
        return {
            "queued": False,
            "reason": "device_busy_with_another_publish_dry_run",
            "device_asset_id": stable_device_id or None,
            "adb_device_id": adb_device_id,
            "current_task": existing,
            "publishes_content": False,
        }

    task = {
        "task_id": f"DRYRUN-{plan_id}",
        "kind": TASK_KIND,
        "plan_id": plan_id,
        "video_id": video_id,
        "campaign_id": str(plan.get("campaign_id") or video.get("campaign_id") or ""),
        "account_id": account_id,
        "account_asset_id": account_id,
        "device_asset_id": stable_device_id or None,
        "adb_device_id": adb_device_id,
        "platform": "抖音",
        "platform_code": "douyin",
        "status": "queued",
        "stage": "等待真机干跑",
        "created_at": now_iso(),
        "updated_at": now_iso(),
        "final_publish_allowed": False,
        "publishes_content": False,
        "next_action": "准备 FINAL.MP4 真机干跑；必须停在抖音最终发布动作之前，等待安全闸门。",
        "truth_rule": "进入真机干跑不等于发布成功；只有真实 Content/Post ID + URL / Receipt 才能计为已发布。",
    }
    entry["current_task"] = task
    entry["account_asset_id"] = account_id
    entry["device_asset_id"] = stable_device_id or entry.get("device_asset_id")
    entry["updated_at"] = now_iso()
    write_json(android_device.RUNTIME_PATH, runtime)
    try:
        android_device._append_audit({
            "device_id": adb_device_id,
            "device_asset_id": stable_device_id or None,
            "action": "publish_dry_run_queued",
            "actor": "system",
            "task_id": task["task_id"],
            "account_id": account_id,
            "result": "ok",
            "detail": {
                "plan_id": plan_id,
                "video_id": video_id,
                "platform": "抖音",
                "publishes_content": False,
            },
        })
    except (OSError, ValueError, RuntimeError, TypeError):
        pass
    return {"queued": True, "idempotent": False, "task": task, "publishes_content": False}
