"""Safe real-device staging executor for Douyin publish dry-runs.

R8-12.2 takes a queued ``douyin_publish_dry_run`` task and proves that the
approved FINAL.MP4 can reach the selected real Android device. It may copy the
file, refresh Android media indexing and open the official Douyin app.

It deliberately does NOT select a video, type a caption, bypass verification or
press the final publish control. Those later steps require a selector-safe
composer executor. A dry-run remains non-public until a real platform Content /
Post ID + URL / Receipt is collected.
"""
from __future__ import annotations

from pathlib import Path

from core.storage import now_iso, read_json, write_json
from integrations import android_device
from promotion import content_factory as cf

TASK_KIND = "douyin_publish_dry_run"
DOUYIN_PACKAGE = "com.ss.android.ugc.aweme"
REMOTE_DIR = "/sdcard/DCIM/Kazuizhi"
EXECUTABLE_STATES = {"queued", "staging"}


def _candidate(video: dict) -> dict | None:
    candidates = [x for x in (video.get("candidates") or []) if isinstance(x, dict)]
    for item in reversed(candidates):
        path = Path(str(item.get("local_path") or ""))
        if path.is_file() and path.stat().st_size > 10 * 1024:
            return item
    return None


def _save_task(runtime: dict, adb_id: str, task: dict) -> None:
    entry = runtime.setdefault("devices", {}).setdefault(adb_id, {})
    task["updated_at"] = now_iso()
    entry["current_task"] = task
    entry["updated_at"] = now_iso()
    write_json(android_device.RUNTIME_PATH, runtime)


def _audit(adb_id: str, task: dict, action: str, result: str, detail=None) -> None:
    try:
        android_device._append_audit({
            "device_id": adb_id,
            "device_asset_id": task.get("device_asset_id"),
            "action": action,
            "actor": "system",
            "task_id": task.get("task_id"),
            "account_id": task.get("account_id"),
            "result": result,
            "detail": detail or {},
        })
    except (OSError, ValueError, RuntimeError, TypeError):
        pass


def _stage_one(runtime: dict, adb_id: str, task: dict, factory: dict) -> dict:
    if task.get("kind") != TASK_KIND or task.get("status") not in EXECUTABLE_STATES:
        return {"executed": False, "reason": "task_not_executable"}
    if task.get("final_publish_allowed") is not False or task.get("publishes_content") is not False:
        raise ValueError("dry-run truth gate violated")

    video = next((x for x in factory.get("videos", []) if x.get("id") == task.get("video_id")), None)
    if not isinstance(video, dict):
        return {"executed": False, "reason": "video_not_found"}
    if not video.get("approved_at") or (video.get("review") or {}).get("decision") != "确认发布":
        return {"executed": False, "reason": "owner_approval_missing"}
    candidate = _candidate(video)
    if not candidate:
        task.update({
            "status": "needs_human",
            "stage": "本地成片缺失",
            "next_action": "找不到真实 FINAL.MP4；禁止伪造干跑，请先恢复或重新生成真实成片。",
        })
        _save_task(runtime, adb_id, task)
        return {"executed": False, "reason": "final_media_missing", "task": task}

    snapshot = android_device.scan_and_sync()
    device = next((x for x in snapshot.get("devices", []) if x.get("device_id") == adb_id), None)
    if not device or not device.get("connected"):
        task.update({"status": "queued", "stage": "等待真机上线", "next_action": "ELE-AL00 上线后自动继续真实设备干跑。"})
        _save_task(runtime, adb_id, task)
        return {"executed": False, "reason": "device_offline", "task": task}
    if device.get("screen_state") in {"secure_lock", "keyguard"}:
        task.update({"status": "needs_human", "stage": "等待人工解锁", "next_action": "请只解锁手机；系统不会绕过锁屏/验证码/人脸。"})
        _save_task(runtime, adb_id, task)
        return {"executed": False, "reason": "device_locked", "task": task}

    local_path = Path(str(candidate.get("local_path"))).resolve()
    remote_name = f"KZ-{task.get('video_id') or 'VIDEO'}.mp4"
    remote_path = f"{REMOTE_DIR}/{remote_name}"
    task.update({"status": "staging", "stage": "正在准备真机素材", "local_path": str(local_path), "remote_path": remote_path})
    _save_task(runtime, adb_id, task)

    try:
        android_device._run(["-s", adb_id, "shell", "mkdir", "-p", REMOTE_DIR], timeout=12)
        android_device._run(["-s", adb_id, "push", str(local_path), remote_path], timeout=180)
        android_device._run([
            "-s", adb_id, "shell", "am", "broadcast",
            "-a", "android.intent.action.MEDIA_SCANNER_SCAN_FILE",
            "-d", f"file://{remote_path}",
        ], timeout=15)
        android_device._run([
            "-s", adb_id, "shell", "monkey", "-p", DOUYIN_PACKAGE,
            "-c", "android.intent.category.LAUNCHER", "1",
        ], timeout=20)
    except (OSError, RuntimeError) as error:
        task.update({
            "status": "needs_human",
            "stage": "真机准备失败",
            "next_action": "保留任务与永久账号，不重绑；检查ADB/抖音后可继续同一任务。",
            "last_error": str(error)[:500],
        })
        _save_task(runtime, adb_id, task)
        _audit(adb_id, task, "douyin_dry_run_stage", "failed", {"error": str(error)[:300]})
        return {"executed": False, "reason": "staging_failed", "task": task}

    task.update({
        "status": "ready_for_composer",
        "stage": "真实成片已上机，抖音已打开",
        "media_staged_at": now_iso(),
        "next_action": "下一步进入抖音创作/选择该成片；最终发布按钮仍禁止自动点击，直到安全执行器和真实回执链通过。",
        "final_publish_allowed": False,
        "publishes_content": False,
        "truth_rule": "素材上机和打开抖音都不等于发布；只有真实 Content/Post ID + URL / Receipt 才能计为已发布。",
    })
    _save_task(runtime, adb_id, task)
    _audit(adb_id, task, "douyin_dry_run_media_staged", "ok", {"remote_path": remote_path, "publishes_content": False})
    return {"executed": True, "task": task, "publishes_content": False}


def run_pending(limit: int = 1) -> dict:
    runtime = read_json(android_device.RUNTIME_PATH, {})
    if not isinstance(runtime, dict):
        runtime = {"devices": {}}
    factory = cf._load()
    items = []
    for adb_id, entry in list((runtime.get("devices") or {}).items()):
        if len(items) >= max(1, int(limit or 1)):
            break
        task = entry.get("current_task") if isinstance(entry, dict) and isinstance(entry.get("current_task"), dict) else None
        if not task or task.get("kind") != TASK_KIND or task.get("status") not in EXECUTABLE_STATES:
            continue
        try:
            items.append(_stage_one(runtime, adb_id, task, factory))
        except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
            items.append({"executed": False, "reason": "executor_error", "error": str(error)[:300]})
    return {
        "processed": len(items),
        "items": items,
        "publishes_content": False,
        "truth_rule": "真机干跑只准备真实素材/应用，不自动点击最终发布。",
    }
