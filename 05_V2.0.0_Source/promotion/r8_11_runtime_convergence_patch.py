"""R8-11/R8-12 runtime convergence for truthful restored Missions.

R8-12 adds a monotonic runtime integrity checkpoint before autonomous work:
partial degradation (lost video/plan/receipt indexes or same-Growth Mission-ID
drift) is repaired without waiting for the whole runtime to become empty.

Existing convergence rules remain:
1. owner-approved ``等待账号`` content may resume after the same real account
   becomes usable;
2. duplicate recovery-race production tasks are paused;
3. the foreground video prefers the approved publish chain.

No recovery function invents media or external publication truth.
"""
from __future__ import annotations

from core import autonomous_ops
from core.runtime_integrity import checkpoint_runtime, recover_runtime_if_degraded
from core.storage import now_iso, read_json
from promotion import content_factory as cf
from promotion import chatgpt_handoff_watchdog as watchdog

PUBLISH_CHAIN_STATES = {"已授权发布", "等待账号", "等待最佳时间", "发布执行中"}
PENDING_PRODUCTION_STATES = {"等待ChatGPT策划", "退回重做", "等待素材路由", "等待生产", "生产中", "技术质检", "等待ChatGPT质检"}
TRUSTED_RECOVERY_SOURCES = {"r8_11_upgrade_recovery", "r8_11_last_nonempty_mission"}
_INSTALLED = False
_ORIGINAL = {}


def can_resume_publish(video: dict) -> bool:
    """Return True only for a previously owner-approved waiting-account video."""
    if not isinstance(video, dict) or video.get("status") != "等待账号":
        return False
    review = video.get("review") if isinstance(video.get("review"), dict) else {}
    return bool(video.get("approved_at") and review.get("decision") == "确认发布")


def select_foreground_video(videos, growth_id):
    """Prefer the already-approved publish chain over accidental newer work."""
    items = [x for x in (videos or []) if isinstance(x, dict) and x.get("campaign_id") == growth_id]
    if not items:
        return None

    def stamp(item):
        return str(item.get("runtime_updated_at") or item.get("plan_received_at") or item.get("requested_at") or item.get("created_at") or "")

    publish = [x for x in items if x.get("status") in PUBLISH_CHAIN_STATES and x.get("approved_at")]
    if publish:
        return max(publish, key=stamp)
    review = [x for x in items if x.get("status") == "等待人工审核"]
    if review:
        return max(review, key=stamp)
    return max(items, key=stamp)


def _trusted_recovered_growth_ids() -> set[str]:
    ops = read_json("ops/autonomous_ops.json", {})
    missions = (ops or {}).get("missions") if isinstance(ops, dict) else []
    trusted = set()
    for mission in missions or []:
        if not isinstance(mission, dict):
            continue
        if mission.get("source") in TRUSTED_RECOVERY_SOURCES or mission.get("recovered_from") in TRUSTED_RECOVERY_SOURCES:
            growth_id = str(mission.get("growth_id") or "").strip()
            if growth_id:
                trusted.add(growth_id)
    return trusted


def _pause_recovery_race_duplicates() -> int:
    """Pause only unapproved duplicates when the same Growth already has approval."""
    data = cf._load()
    changed = 0
    by_campaign = {}
    for video in data.get("videos", []):
        if isinstance(video, dict):
            by_campaign.setdefault(video.get("campaign_id"), []).append(video)
    for growth_id, videos in by_campaign.items():
        approved = [
            x for x in videos
            if x.get("approved_at") and (x.get("review") or {}).get("decision") == "确认发布"
            and x.get("status") in PUBLISH_CHAIN_STATES
        ]
        if not approved:
            continue
        owner_video = select_foreground_video(approved, growth_id)
        for video in videos:
            if video is owner_video or video.get("approved_at"):
                continue
            if video.get("status") not in PENDING_PRODUCTION_STATES:
                continue
            video["status"] = "已暂缓"
            video["bottleneck"] = "同一 Mission 已有老板确认发布的成片，恢复竞态产生的重复生产任务已暂停"
            video["auto_action"] = "继续优先执行已授权成片；不重复生产、不重复发布"
            video["runtime_updated_at"] = now_iso()
            video["suppressed_by_video_id"] = owner_video.get("id") if owner_video else None
            changed += 1
    if changed:
        cf._save(data)
    return changed


def create_publish_plan(payload):
    """Legacy compatibility: resume a truthful owner-approved waiting-account video.

    R8-12 normal publication routing no longer depends on this legacy account
    lookup; it is kept for older UI/API requests during migration.
    """
    data = cf._load()
    video_id = str((payload or {}).get("video_id") or "").strip()
    video = next((x for x in data.get("videos", []) if x.get("id") == video_id), None)
    if can_resume_publish(video):
        video["status"] = "已授权发布"
        video["bottleneck"] = None
        video["auto_action"] = "账号已满足发布条件，恢复老板已授权的发布编排"
        video["runtime_updated_at"] = now_iso()
        cf._save(data)
    return _ORIGINAL["create_publish_plan"](payload)


def sync_from_runtime(*, autostart=True):
    """Repair the active lineage before autonomous work, then checkpoint it."""
    if autostart:
        try:
            recover_runtime_if_degraded()
        except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError):
            pass
        try:
            # Older R8-11 fallback remains useful only when no R8-12 checkpoint
            # exists yet and both legacy local indexes really are empty.
            from core.mission_ledger import recover_if_empty
            recover_if_empty(client=None)
        except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError):
            pass
        _pause_recovery_race_duplicates()
    result = _ORIGINAL["sync_from_runtime"](autostart=autostart)
    try:
        checkpoint_runtime("autonomous_runtime_sync")
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError):
        pass
    return result


def _recover_authorized_local_plans():
    """Allow trusted recovered Missions to use the existing local planner."""
    data = cf._load()
    trusted_growths = _trusted_recovered_growth_ids()
    campaign_by_id = {x.get("id"): x for x in data.get("campaigns", []) if isinstance(x, dict)}
    publish_growths = {
        x.get("campaign_id") for x in data.get("videos", [])
        if isinstance(x, dict) and x.get("approved_at") and (x.get("review") or {}).get("decision") == "确认发布"
        and x.get("status") in PUBLISH_CHAIN_STATES
    }
    candidate_ids = []
    for video in data.get("videos", []):
        if not isinstance(video, dict) or video.get("production_plan"):
            continue
        if video.get("status") not in {"等待ChatGPT策划", "退回重做", "异常待处理"}:
            continue
        growth_id = video.get("campaign_id")
        if growth_id in publish_growths:
            continue
        campaign = campaign_by_id.get(growth_id) or {}
        source = str(campaign.get("source_type") or "").strip()
        if source != watchdog.MISSION_SOURCE and growth_id not in trusted_growths:
            continue
        handoff = video.get("chatgpt_handoff") if isinstance(video.get("chatgpt_handoff"), dict) else {}
        if video.get("status") == "异常待处理" and handoff.get("kind") not in {None, "content_production"}:
            continue
        candidate_ids.append(video.get("id"))

    if not candidate_ids:
        return []
    from promotion.local_mission_planner import recover_video
    recovered = []
    for video_id in candidate_ids:
        try:
            result = recover_video(video_id)
            if result:
                recovered.append(result)
        except (OSError, ValueError, RuntimeError, TypeError, KeyError) as error:
            recovered.append({"video_id": video_id, "status": "failed", "error": str(error)[:300]})
    return recovered


def install():
    global _INSTALLED
    if _INSTALLED:
        return
    _ORIGINAL["create_publish_plan"] = cf.create_publish_plan
    _ORIGINAL["sync_from_runtime"] = autonomous_ops.sync_from_runtime
    cf.create_publish_plan = create_publish_plan
    autonomous_ops.sync_from_runtime = sync_from_runtime
    autonomous_ops._latest_video = select_foreground_video
    watchdog._recover_authorized_local_plans = _recover_authorized_local_plans
    _INSTALLED = True


install()
