"""R8-10 owner-facing state convergence.

The active Mission is the owner's foreground truth. Historical failed video
attempts stay in audit/history, but they must not keep the current owner-action
badge red after a newer attempt for the same Growth ID has progressed normally.

Content-factory video records are stored newest-first (create_video inserts at
index 0). Deep-productization previously tried to re-sort them using a partial
set of timestamps; a recovered/legacy failure could therefore outrank the real
foreground task and remain visible as a stale "自动恢复失败" item.
"""
from __future__ import annotations

from backend import deep_productization_patch as deep_productization

_INSTALLED = False
_ORIGINAL_CURRENT_MISSION_VIDEOS = None


def _current_mission_videos(data):
    """Return the canonical newest foreground video for the active Mission.

    Keep historical attempts in storage/audit. Only the first scoped record is
    allowed to drive the owner attention center because the factory guarantees
    newest-first insertion order. If that current record is truly abnormal it
    remains visible; only older stale failures are suppressed.
    """
    videos = data.get("videos") or []
    active = deep_productization._active_id(data)
    if not active:
        return []
    scoped = [item for item in videos if item.get("campaign_id") == active]
    return scoped[:1]


def install():
    global _INSTALLED, _ORIGINAL_CURRENT_MISSION_VIDEOS
    if _INSTALLED:
        return
    _ORIGINAL_CURRENT_MISSION_VIDEOS = deep_productization._current_mission_videos
    deep_productization._current_mission_videos = _current_mission_videos
    _INSTALLED = True


install()
