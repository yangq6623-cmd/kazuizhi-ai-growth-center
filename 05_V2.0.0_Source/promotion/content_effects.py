"""Verified post-publication performance feedback for the content factory."""

from __future__ import annotations

from core.storage import now_iso
from promotion import content_factory, platform_rules


def record_effect_metrics(payload):
    payload = payload or {}
    data = content_factory._load()
    plan_id = content_factory._clean(payload.get("plan_id"), "发布计划ID", 64)
    plan = content_factory._by_id(data.get("publication_plans", []), plan_id, "发布计划")
    if plan.get("status") != "已验证发布":
        raise ValueError("只有带真实成功发布回执的计划才能记录效果数据")
    receipt = next((
        x for x in data.get("receipts", [])
        if x.get("plan_id") == plan_id and x.get("result") == "成功"
    ), None)
    if not receipt or not receipt.get("platform_content_id") or not receipt.get("url"):
        raise ValueError("缺少真实平台内容ID或URL，不能进入效果学习")
    checkpoint = str(payload.get("checkpoint") or "").strip()
    source = str(payload.get("source") or "").strip()
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {
        key: payload.get(key, 0) for key in platform_rules.METRIC_FIELDS
    }
    summary = platform_rules.record_metrics(
        plan.get("platform"), plan_id, checkpoint, metrics, source,
        metadata={
            "video_id": plan.get("video_id"),
            "campaign_id": plan.get("campaign_id"),
            "platform_content_id": receipt.get("platform_content_id"),
            "url": receipt.get("url"),
        },
    )
    events = data.setdefault("events", [])
    events.append({
        "id": content_factory._id("EVT"), "created_at": now_iso(), "kind": "verified_effect_metrics",
        "video_id": plan.get("video_id"), "campaign_id": plan.get("campaign_id"),
        "detail": {"plan_id": plan_id, "checkpoint": checkpoint, "source": source, "metrics": metrics},
    })
    data["events"] = events[-1000:]
    content_factory._save(data)
    return {
        "recorded": True, "plan_id": plan_id, "checkpoint": checkpoint,
        "platform": plan.get("platform"), "learning_summary": summary,
    }
