"""R8-10 idempotency hardening for concurrent autonomous/UI video creation.

The autonomous Mission scheduler may create the first content job immediately
after a campaign becomes active. A near-simultaneous owner/test/API request for
the same campaign must not turn that healthy race into HTTP 400. We preserve the
single-active-video invariant and return the already-created active job instead.
"""
from __future__ import annotations

from promotion import content_factory as cf
from backend import server

_INSTALLED = False

ACTIVE_VIDEO_STATES = {
    "等待ChatGPT策划", "等待素材路由", "等待生产", "生产中", "技术质检", "等待ChatGPT质检",
    "等待人工审核", "退回重做", "已授权发布", "等待账号", "等待最佳时间", "发布执行中", "异常待处理",
}


def install():
    global _INSTALLED
    if _INSTALLED:
        return

    original = cf.create_video

    def create_video_idempotent(payload):
        values = payload if isinstance(payload, dict) else {}
        campaign_id = str(values.get("campaign_id") or "").strip()
        if campaign_id:
            data = cf._load()
            existing = next(
                (
                    item for item in data.get("videos", [])
                    if item.get("campaign_id") == campaign_id
                    and item.get("status") in ACTIVE_VIDEO_STATES
                ),
                None,
            )
            if existing:
                # Do not mutate/persist the existing job merely to report that
                # this near-simultaneous request reused it.
                result = dict(existing)
                result["idempotent_reuse"] = True
                result["idempotency_reason"] = "同一增长任务已有活动视频任务，复用现有任务而不重复生产"
                return result
        return original(payload)

    cf.create_video = create_video_idempotent
    # server.py captured this callable at import time, so repoint the route alias
    # after the deep-productization layer has installed its single-job guard.
    server.factory_create_video = create_video_idempotent
    _INSTALLED = True


install()
