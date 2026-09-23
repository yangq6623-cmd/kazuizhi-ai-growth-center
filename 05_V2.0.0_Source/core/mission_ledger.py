"""R8-11 Mission ledger and execution backflow spine.

This module joins Command/Decision Pack, Mission, Growth, content/video,
publish-plan, real platform Receipt and verified business context into one
read-only operating ledger.  It is deliberately derived from existing truthful
stores instead of introducing a second competing state machine.

The ledger can also publish sanitized state snapshots to the existing PRIVATE
GitHub Control Bus.  It does not require a paid third-party token service and it
does not claim external success without a real platform receipt.
"""
from __future__ import annotations

from core.storage import now_iso, write_json

LEDGER_FILE = "r8_11/mission_ledger.json"
SCHEMA = "kz.mission-ledger.v1"


def _safe_factory() -> dict:
    try:
        from promotion import content_factory as cf
        value = cf._load()
        return value if isinstance(value, dict) else {}
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError):
        return {}


def _safe_ops() -> dict:
    try:
        from core.autonomous_ops import snapshot
        value = snapshot(sync=True)
        return value if isinstance(value, dict) else {}
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError):
        return {}


def _safe_bus_receipts() -> list[dict]:
    try:
        from integrations.async_control_bus import recent_receipts
        return [x for x in recent_receipts(200) if isinstance(x, dict)]
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError):
        return []


def _safe_business() -> dict:
    try:
        from analytics.business_metrics import build_analytics
        value = build_analytics()
        return value if isinstance(value, dict) else {}
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError):
        return {}


def _safe_channels() -> dict:
    try:
        from integrations.channel_registry import snapshot
        value = snapshot()
        return value if isinstance(value, dict) else {}
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError):
        return {"channels": [], "summary": {}}


def _safe_routes(active: dict | None) -> dict:
    try:
        from integrations.channel_router import build_routes
        value = build_routes(active or {})
        return value if isinstance(value, dict) else {}
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError):
        return {"routes": [], "summary": {}}


def _candidate_summary(video: dict | None) -> dict | None:
    if not isinstance(video, dict):
        return None
    candidates = [x for x in (video.get("candidates") or []) if isinstance(x, dict)]
    candidate = next((x for x in reversed(candidates) if x.get("exists")), None)
    if not candidate:
        return None
    technical = candidate.get("technical_qc") or video.get("technical_qc") or {}
    return {
        "candidate_id": candidate.get("id"),
        "exists": bool(candidate.get("exists")),
        "duration_seconds": candidate.get("duration_seconds"),
        "technical_qc_passed": bool(technical.get("passed")),
        "local_qc": video.get("local_qc") or {},
        "truth": "存在本地成片不等于已发布；外部发布必须等待真实平台 Receipt。",
    }


def _next_action(mission: dict, video: dict | None, real_receipts: list[dict]) -> str:
    if real_receipts:
        return "读取真实曝光/访问/咨询/订单并回流 ChatGPT，决定继续、调整或停止 Mission"
    if not isinstance(video, dict):
        return "建立当前 Mission 的第一条可追溯执行任务"
    status = str(video.get("status") or "")
    if status in {"等待ChatGPT策划", "退回重做"}:
        return "完成安全内容策划并进入本地生产队列"
    if status in {"等待素材路由", "等待生产", "生产中", "技术质检", "等待ChatGPT质检"}:
        return "继续本地生产、技术质检和自治内容 QC"
    if status == "等待人工审核":
        return "等待老板审核 FINAL.MP4；通过仅进入发布队列"
    if status in {"已授权发布", "等待账号"}:
        return "验证真实平台账号/真机后创建发布计划"
    if status in {"等待最佳时间", "发布执行中"}:
        return "执行真实平台发布并取得 Post ID / URL / Receipt"
    if status == "异常待处理":
        return "按真实 bottleneck 处理异常；不可伪造成功"
    if status == "已暂缓":
        return "等待老板或 ChatGPT 的 continue/create_mission 决策"
    return "按 Mission 当前状态继续到下一真实关口"


def _command_links(mission_id: str, bus_receipts: list[dict]) -> list[dict]:
    rows = []
    for receipt in bus_receipts:
        if receipt.get("mission_id") != mission_id:
            continue
        rows.append({
            "command_id": receipt.get("command_id"),
            "decision_pack_id": receipt.get("decision_pack_id"),
            "control_receipt_id": receipt.get("receipt_id"),
            "status": receipt.get("status"),
            "created_at": receipt.get("created_at"),
            "transport": receipt.get("transport"),
        })
    return rows


def _mission_row(mission: dict, factory: dict, bus_receipts: list[dict], channels: dict) -> dict:
    growth_id = str(mission.get("growth_id") or "")
    videos = [x for x in factory.get("videos", []) if x.get("campaign_id") == growth_id]
    active_video_id = mission.get("active_video_id")
    video = next((x for x in videos if x.get("id") == active_video_id), None) or (videos[0] if videos else None)
    plans = [x for x in factory.get("publication_plans", []) if x.get("campaign_id") == growth_id]
    plan_ids = {x.get("id") for x in plans if x.get("id")}
    receipts = [x for x in factory.get("receipts", []) if x.get("plan_id") in plan_ids]
    successful = [x for x in receipts if x.get("result") == "成功" and x.get("platform_content_id") and x.get("url")]
    latest_plan = plans[0] if plans else None
    latest_receipt = receipts[0] if receipts else None
    command_links = _command_links(str(mission.get("mission_id") or ""), bus_receipts)
    blocker = (video or {}).get("bottleneck") or mission.get("bottleneck")
    return {
        "mission_id": mission.get("mission_id"),
        "growth_id": growth_id or None,
        "command": command_links[0] if command_links else None,
        "command_history": command_links,
        "title": mission.get("title"),
        "region": mission.get("region"),
        "service": mission.get("service"),
        "goal": mission.get("goal"),
        "state": mission.get("state"),
        "stage": mission.get("stage"),
        "user_state": mission.get("user_state"),
        "updated_at": mission.get("updated_at"),
        "last_chatgpt_decision": mission.get("last_chatgpt_decision"),
        "children": {
            "video_ids": [x.get("id") for x in videos if x.get("id")],
            "publish_plan_ids": [x.get("id") for x in plans if x.get("id")],
            "platform_receipt_ids": [x.get("id") for x in receipts if x.get("id")],
        },
        "active_video": None if not video else {
            "video_id": video.get("id"),
            "status": video.get("status"),
            "plan_version": video.get("plan_version"),
            "plan_source": video.get("plan_source"),
            "review": video.get("review"),
            "auto_action": video.get("auto_action"),
            "bottleneck": video.get("bottleneck"),
            "candidate": _candidate_summary(video),
        },
        "latest_publish_plan": None if not latest_plan else {
            "plan_id": latest_plan.get("id"),
            "video_id": latest_plan.get("video_id"),
            "account_id": latest_plan.get("account_id"),
            "platform": latest_plan.get("platform"),
            "status": latest_plan.get("status"),
            "scheduled_for": latest_plan.get("scheduled_for"),
            "created_at": latest_plan.get("created_at"),
        },
        "latest_platform_receipt": None if not latest_receipt else {
            "receipt_id": latest_receipt.get("id"),
            "plan_id": latest_receipt.get("plan_id"),
            "result": latest_receipt.get("result"),
            "platform_content_id": latest_receipt.get("platform_content_id"),
            "url": latest_receipt.get("url"),
            "created_at": latest_receipt.get("created_at"),
            "reason": latest_receipt.get("reason"),
        },
        "verified_publications": len(successful),
        "blocker": blocker,
        "next_action": _next_action(mission, video, successful),
        "channel_summary": channels.get("summary") or {},
        "truth": "Mission 状态来自真实本地记录；只有带真实平台 Content ID + URL 的成功 Receipt 才计入已验证发布。",
    }


def snapshot() -> dict:
    ops = _safe_ops()
    factory = _safe_factory()
    bus_receipts = _safe_bus_receipts()
    channels = _safe_channels()
    business = _safe_business()
    missions = [x for x in (ops.get("missions") or []) if isinstance(x, dict)]
    rows = [_mission_row(mission, factory, bus_receipts, channels) for mission in missions]
    active_id = (ops.get("active_mission") or {}).get("mission_id")
    active = next((x for x in rows if x.get("mission_id") == active_id), rows[0] if rows else None)
    routes = _safe_routes(active)
    timeline = [x for x in (ops.get("timeline") or []) if isinstance(x, dict)]
    payload = {
        "schema": SCHEMA,
        "generated_at": now_iso(),
        "active_mission_id": active_id,
        "active_mission": active,
        "missions": rows[:50],
        "timeline": timeline[:100],
        "channel_registry": channels,
        "channel_routes": routes,
        "business_snapshot": business,
        "control_bus": {
            "decision_receipts_seen": len(bus_receipts),
            "transport": "github_private_control_bus",
            "paid_third_party_token_required": False,
        },
        "truth_rule": "Command→Mission→执行→发布→经营结果必须逐层有真实证据；任何缺失环节保持待验证，不补造成功。",
    }
    write_json(LEDGER_FILE, payload)
    return payload


def export_to_control_bus(client=None) -> dict:
    """Write Mission/channel state to the existing private Control Bus.

    A caller may pass a fake/test client.  When no configured bus is available,
    the local ledger is still refreshed and returned truthfully.
    """
    ledger = snapshot()
    try:
        if client is None:
            from integrations.async_control_bus import _client_from_config
            client = _client_from_config()
        if client is None:
            return {"exported": False, "reason": "control_bus_not_configured", "ledger": ledger}
        client.ensure_private_repo()
        client.write_json("state/mission_ledger.json", ledger, "R8-11 Mission ledger sync")
        client.write_json("state/channel_registry.json", ledger.get("channel_registry") or {}, "R8-11 channel registry sync")
        client.write_json("state/channel_routes.json", ledger.get("channel_routes") or {}, "R8-11 channel routes sync")
        active = ledger.get("active_mission") or {}
        mission_id = str(active.get("mission_id") or "").strip()
        if mission_id:
            client.write_json(f"state/missions/{mission_id}.json", active, f"R8-11 {mission_id} state sync")
        return {"exported": True, "mission_id": mission_id or None, "generated_at": ledger.get("generated_at")}
    except (OSError, RuntimeError, TypeError, ValueError, KeyError) as error:
        return {"exported": False, "reason": "control_bus_export_failed", "error": str(error)[:800], "ledger": ledger}


def sync_backbone(client=None) -> dict:
    """Single scheduler entry point for steps 1-3 of the R8-11 backbone."""
    return export_to_control_bus(client=client)
