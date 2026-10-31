"""Unified autonomous operations core for the Kazuizhi R7/R8 runtime.

R7 and R8 are two views over one operating loop, not two independent systems.
This module owns the shared Mission identity, world-state snapshot and business
pipeline timeline.  It never invents external results: publish completion only
comes from verified receipts already recorded by the R8 content factory.

The core intentionally keeps execution conservative:
- R7 analysis is attached to the active Mission and sent into ChatGPT planning.
- A ready content campaign can automatically create its first production task.
- Owner review, platform verification, finance and real-world compliance remain
  explicit human/verified boundaries.
"""
from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from core.storage import now_iso, read_json, write_json

OPS_FILE = "ops/autonomous_ops.json"
MAX_EVENTS = 1200
ACTIVE_VIDEO_STATES = {
    "等待ChatGPT策划", "等待素材路由", "等待生产", "生产中", "技术质检", "等待ChatGPT质检",
    "等待人工审核", "退回重做", "已授权发布", "等待账号", "等待最佳时间", "发布执行中", "异常待处理",
}


def _default():
    return {
        "schema": 1,
        "owner_goal": None,
        "active_mission_id": None,
        "missions": [],
        "events": [],
        "updated_at": now_iso(),
    }


def _load():
    data = read_json(OPS_FILE, _default())
    if not isinstance(data, dict):
        data = _default()
    for key, value in _default().items():
        data.setdefault(key, value)
    if not isinstance(data.get("missions"), list):
        data["missions"] = []
    if not isinstance(data.get("events"), list):
        data["events"] = []
    return data


def _save(data):
    data["updated_at"] = now_iso()
    data["events"] = data.get("events", [])[-MAX_EVENTS:]
    return write_json(OPS_FILE, data)


def _mission_id():
    stamp = datetime.now().astimezone().strftime("%Y%m%d")
    return f"MISSION-{stamp}-{uuid4().hex[:6].upper()}"


def _event(data, mission, kind, message, detail=None):
    event = {
        "id": f"EVT-{uuid4().hex[:10].upper()}",
        "at": now_iso(),
        "mission_id": mission.get("mission_id") if mission else None,
        "growth_id": mission.get("growth_id") if mission else None,
        "kind": str(kind or "event")[:80],
        "message": str(message or "")[:300],
        "detail": detail if isinstance(detail, dict) else {},
    }
    data.setdefault("events", []).append(event)
    return event


def _find_mission(data, *, mission_id=None, growth_id=None):
    for item in data.get("missions", []):
        if mission_id and item.get("mission_id") == mission_id:
            return item
        if growth_id and item.get("growth_id") == growth_id:
            return item
    return None


def _latest_video(videos, growth_id):
    items = [x for x in videos if x.get("campaign_id") == growth_id]
    return items[0] if items else None


def _stage_for(video, verified_publications):
    if not video:
        return "待自动立项"
    status = str(video.get("status") or "")
    if verified_publications or status == "已验证发布":
        return "效果回流"
    if status in {"等待ChatGPT策划", "退回重做"}:
        return "AI决策"
    if status in {"等待素材路由", "等待生产", "生产中", "技术质检", "等待ChatGPT质检"}:
        return "自动生产"
    if status == "等待人工审核":
        return "待老板审核"
    if status in {"已授权发布", "等待账号", "等待最佳时间", "发布执行中"}:
        return "自动发布"
    if status == "异常待处理":
        return "异常"
    if status == "已暂缓":
        return "已暂停"
    if status == "发布失败":
        return "异常"
    return "自动处理中"


def _user_state(stage):
    if stage == "待老板审核":
        return "等待你处理"
    if stage == "异常":
        return "异常"
    if stage in {"效果回流", "已完成"}:
        return "已完成"
    return "自动处理中"


def _safe_decision_snapshot():
    try:
        from core.decision_center import decision_snapshot
        return decision_snapshot()
    except (ImportError, OSError, ValueError, RuntimeError, KeyError, TypeError):
        return {}


def _safe_social_snapshot():
    try:
        from core import r8_control
        return r8_control.social_center_status()
    except (ImportError, OSError, ValueError, RuntimeError, KeyError, TypeError):
        return {"devices": [], "accounts": [], "terminals": []}


def _r7_context(report):
    return {
        "generated_at": report.get("generated_at"),
        "manager_summary": report.get("manager_summary") or {},
        "manager_decisions": (report.get("manager_decisions") or [])[:6],
        "employee_proposals": (report.get("employee_proposals") or [])[:12],
        "region_strategy": report.get("region_strategy") or {},
    }


def sync_from_runtime(*, autostart=True):
    """Synchronize Mission/world state from truthful R7 and R8 records.

    This is idempotent.  It may automatically create the first R8 video request
    only when a real campaign already exists and is explicitly ready for AI
    production.  It never auto-approves owner review or fabricates publication.
    """
    from promotion import content_factory as cf

    factory = cf._load()
    report = _safe_decision_snapshot()
    social = _safe_social_snapshot()
    data = _load()
    r7 = _r7_context(report)

    active_growth = str(factory.get("active_campaign_id") or "").strip()
    campaigns = factory.get("campaigns") or []
    videos = factory.get("videos") or []
    plans = factory.get("publication_plans") or []
    receipts = factory.get("receipts") or []

    for campaign in campaigns:
        growth_id = str(campaign.get("id") or "").strip()
        if not growth_id:
            continue
        mission = _find_mission(data, growth_id=growth_id)
        if mission is None:
            mission = {
                "mission_id": _mission_id(),
                "growth_id": growth_id,
                "created_at": now_iso(),
                "updated_at": now_iso(),
                "source": "r7_r8_shared_pipeline",
                "title": campaign.get("title") or "经营任务",
                "region": campaign.get("region") or "",
                "service": campaign.get("service") or "",
                "goal": campaign.get("goal") or "",
                "priority": "P1" if growth_id == active_growth else "P2",
                "autonomy_level": "L4_key_gates_human",
                "state": "active",
                "stage": "待自动立项",
                "user_state": "自动处理中",
                "r7_context": {},
                "children": {"video_ids": [], "publish_plan_ids": [], "receipt_ids": []},
                "verified_publications": 0,
                "last_result": None,
            }
            data["missions"].insert(0, mission)
            _event(data, mission, "mission_created", "R7/R8 已建立统一经营任务主线")

        mission.update({
            "title": campaign.get("title") or mission.get("title"),
            "region": campaign.get("region") or mission.get("region"),
            "service": campaign.get("service") or mission.get("service"),
            "goal": campaign.get("goal") or mission.get("goal"),
            "priority": "P1" if growth_id == active_growth else mission.get("priority", "P2"),
            "r7_context": r7,
        })
        video_ids = [x.get("id") for x in videos if x.get("campaign_id") == growth_id and x.get("id")]
        plan_ids = [x.get("id") for x in plans if x.get("campaign_id") == growth_id and x.get("id")]
        plan_set = set(plan_ids)
        receipt_ids = [x.get("id") for x in receipts if x.get("plan_id") in plan_set and x.get("id")]
        verified = [x for x in receipts if x.get("plan_id") in plan_set and x.get("result") == "成功"]
        latest = _latest_video(videos, growth_id)
        stage = _stage_for(latest, len(verified))
        previous_stage = mission.get("stage")
        mission["children"] = {
            "video_ids": video_ids,
            "publish_plan_ids": plan_ids,
            "receipt_ids": receipt_ids,
        }
        mission["verified_publications"] = len(verified)
        mission["stage"] = stage
        mission["user_state"] = _user_state(stage)
        mission["state"] = "attention" if stage == "异常" else ("paused" if stage == "已暂停" else "active")
        mission["updated_at"] = now_iso()
        if latest:
            mission["active_video_id"] = latest.get("id")
            mission["video_status"] = latest.get("status")
            mission["bottleneck"] = latest.get("bottleneck")
            mission["auto_action"] = latest.get("auto_action")
        if verified:
            mission["last_result"] = {
                "kind": "verified_publication",
                "count": len(verified),
                "latest_at": verified[0].get("created_at"),
                "source": "real_platform_receipt",
            }
        if previous_stage and previous_stage != stage:
            _event(data, mission, "stage_changed", f"经营主线：{previous_stage} → {stage}", {
                "video_id": mission.get("active_video_id"),
                "video_status": mission.get("video_status"),
            })

    active_mission = _find_mission(data, growth_id=active_growth) if active_growth else None
    if active_mission:
        data["active_mission_id"] = active_mission["mission_id"]

    # First R8 execution task is automatic once a campaign is ready.  This is
    # the key R7 -> ChatGPT -> R8 handoff: the owner does not click another
    # "start video" button after the strategic campaign already exists.
    auto_started = None
    if autostart and active_growth:
        campaign = next((x for x in campaigns if x.get("id") == active_growth), None)
        has_active = any(
            x.get("campaign_id") == active_growth and x.get("status") in ACTIVE_VIDEO_STATES
            for x in videos
        )
        if campaign and not has_active and campaign.get("status") in {"可开始AI生产", "待开始", "准备执行"}:
            try:
                auto_started = cf.create_video({"campaign_id": active_growth})
                mission = _find_mission(data, growth_id=active_growth)
                if mission:
                    mission["active_video_id"] = auto_started.get("id")
                    mission["stage"] = "AI决策"
                    mission["user_state"] = "自动处理中"
                    _event(data, mission, "r8_auto_started", "R7 经营任务已自动进入 ChatGPT 策划与 R8 执行", {
                        "video_id": auto_started.get("id")
                    })
            except (ValueError, OSError):
                auto_started = None

    data["world_state"] = {
        "generated_at": now_iso(),
        "r7_manager": report.get("manager_summary") or {},
        "r7_decisions": (report.get("manager_decisions") or [])[:6],
        "active_growth_id": active_growth or None,
        "active_mission_id": data.get("active_mission_id"),
        "running_missions": sum(1 for x in data.get("missions", []) if x.get("state") == "active"),
        "attention_missions": sum(1 for x in data.get("missions", []) if x.get("state") == "attention"),
        "waiting_owner_review": sum(1 for x in videos if x.get("status") == "等待人工审核"),
        "verified_publications": sum(1 for x in receipts if x.get("result") == "成功"),
        "devices_online": sum(1 for x in (social.get("devices") or []) if x.get("connection") == "connected"),
        "accounts_needing_human": sum(
            1 for x in (social.get("accounts") or [])
            if x.get("login_status") in {"needs_human", "logged_out"} or x.get("risk_level") in {"attention", "high"}
        ),
        "continuity": "老板目标 → ChatGPT总决策 → R7分析 → Mission → R8执行 → 发布/转化 → R7复盘",
    }
    _save(data)
    return snapshot(sync=False)


def snapshot(*, sync=True):
    if sync:
        return sync_from_runtime(autostart=False)
    data = _load()
    active = _find_mission(data, mission_id=data.get("active_mission_id"))
    events = [x for x in data.get("events", []) if not active or x.get("mission_id") == active.get("mission_id")]
    return {
        "status": "available",
        "owner_goal": data.get("owner_goal"),
        "active_mission": active,
        "missions": data.get("missions", [])[:50],
        "timeline": events[-30:][::-1],
        "world_state": data.get("world_state") or {},
        "truth_rule": "只有真实平台回执、真实咨询/订单数据和人工确认可以升级真实经营结果；本地自动化不得伪造成功。",
        "autonomy": {
            "default": "L4",
            "meaning": "非资金、非验证类工作自动执行；最终成片审核、扫码/验证码/人脸、资金和重大合规歧义由老板处理。",
        },
    }


def set_owner_goal(payload):
    values = payload if isinstance(payload, dict) else {}
    objective = str(values.get("objective") or "").strip()
    if not objective or len(objective) > 300:
        raise ValueError("老板经营目标需为 1 到 300 字")
    data = _load()
    data["owner_goal"] = {
        "objective": objective,
        "metric": str(values.get("metric") or "真实咨询/订单").strip()[:80],
        "target": str(values.get("target") or "").strip()[:80],
        "deadline": str(values.get("deadline") or "").strip()[:40],
        "updated_at": now_iso(),
        "source": "owner",
    }
    active = _find_mission(data, mission_id=data.get("active_mission_id"))
    if active:
        _event(data, active, "owner_goal_updated", "老板经营目标已更新；下一轮 ChatGPT 决策自动读取", {
            "objective": objective,
        })
    _save(data)
    return data["owner_goal"]


def activate_mission(payload):
    values = payload if isinstance(payload, dict) else {}
    mission_id = str(values.get("mission_id") or "").strip()
    data = _load()
    mission = _find_mission(data, mission_id=mission_id)
    if not mission:
        raise ValueError("未找到经营任务")
    data["active_mission_id"] = mission_id
    _event(data, mission, "mission_activated", "已切换为当前经营主线")
    _save(data)
    try:
        from promotion import content_factory as cf
        factory = cf._load()
        if mission.get("growth_id") and any(x.get("id") == mission.get("growth_id") for x in factory.get("campaigns", [])):
            factory["active_campaign_id"] = mission["growth_id"]
            factory["active_campaign_updated_at"] = now_iso()
            cf._save(factory)
    except (ImportError, OSError, ValueError):
        pass
    return mission


def mission_context_for_growth(growth_id):
    data = _load()
    mission = _find_mission(data, growth_id=str(growth_id or "").strip())
    if not mission:
        return None
    return {
        "mission_id": mission.get("mission_id"),
        "growth_id": mission.get("growth_id"),
        "goal": mission.get("goal"),
        "region": mission.get("region"),
        "service": mission.get("service"),
        "stage": mission.get("stage"),
        "owner_goal": data.get("owner_goal"),
        "r7_context": mission.get("r7_context") or {},
        "instruction": "ChatGPT须在同一Mission上下文中延续R7判断，并让R8执行结果可回流复盘；不要把R7/R8当成两套独立任务。",
    }


def feedback_for_r7(limit=12):
    """Return only persisted R8/Mission facts; safe for decision_center imports."""
    data = _load()
    rows = []
    for mission in data.get("missions", [])[:max(1, int(limit or 12))]:
        rows.append({
            "mission_id": mission.get("mission_id"),
            "growth_id": mission.get("growth_id"),
            "title": mission.get("title"),
            "stage": mission.get("stage"),
            "user_state": mission.get("user_state"),
            "verified_publications": int(mission.get("verified_publications") or 0),
            "last_result": mission.get("last_result"),
            "active_video_id": mission.get("active_video_id"),
            "video_status": mission.get("video_status"),
            "bottleneck": mission.get("bottleneck"),
        })
    return {
        "active_mission_id": data.get("active_mission_id"),
        "items": rows,
        "count": len(rows),
        "source": "shared_mission_store",
    }
