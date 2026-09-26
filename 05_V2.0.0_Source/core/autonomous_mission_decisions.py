"""Validated ChatGPT decisions for the autonomous Mission loop.

This is deliberately narrow: ChatGPT may continue a Mission, pause a Mission,
or create a new non-financial growth campaign. It cannot approve final video
publication, forge account verification, alter finance, or claim real-world
results.
"""
from __future__ import annotations

from core import autonomous_ops
from core.storage import now_iso

ALLOWED_ACTIONS = {"continue", "stop", "create_mission"}


def _clean(value, label, limit=300, required=True):
    text = str(value or "").strip()
    if required and not text:
        raise ValueError(f"{label}不能为空")
    if len(text) > limit:
        raise ValueError(f"{label}长度不能超过{limit}个字符")
    return text


def _current_mission(data, mission_id=None):
    if mission_id:
        mission = autonomous_ops._find_mission(data, mission_id=mission_id)
        if mission:
            return mission
    return autonomous_ops._find_mission(data, mission_id=data.get("active_mission_id"))


def apply_chatgpt_mission_decision(payload):
    if not isinstance(payload, dict):
        raise ValueError("mission_decision格式不正确")
    action = _clean(payload.get("action"), "action", 40)
    if action not in ALLOWED_ACTIONS:
        raise ValueError("mission_decision只允许continue、stop或create_mission")
    reason = _clean(payload.get("reason") or "ChatGPT根据R7/R8真实状态做出的自治经营决策", "reason", 500)
    raw_plan = payload.get("execution_plan", payload.get("plan"))
    chatgpt_plan = None
    if raw_plan is not None:
        from core.chatgpt_execution_control import normalize_plan
        chatgpt_plan = normalize_plan(raw_plan)

    from promotion import content_factory as cf

    data = autonomous_ops._load()
    mission = _current_mission(data, str(payload.get("mission_id") or "").strip())

    if action == "stop":
        if not mission:
            raise ValueError("当前没有可停止的Mission")
        factory = cf._load()
        video = next(
            (x for x in factory.get("videos", []) if x.get("campaign_id") == mission.get("growth_id")),
            None,
        )
        if video and video.get("status") in {
            "等待ChatGPT策划", "等待素材路由", "等待生产", "生产中", "技术质检", "等待ChatGPT质检",
            "退回重做", "已授权发布", "等待账号", "等待最佳时间", "发布执行中", "异常待处理",
        }:
            cf.update_runtime_state(
                video["id"], status="已暂缓",
                bottleneck="ChatGPT基于经营复盘停止当前非资金执行",
                auto_action="保留全部记录，等待新的老板目标或ChatGPT下一轮Mission决策",
            )
        mission["state"] = "paused"
        mission["stage"] = "已暂停"
        mission["user_state"] = "已完成"
        mission["last_chatgpt_decision"] = {"action": action, "reason": reason, "at": now_iso()}
        autonomous_ops._event(data, mission, "chatgpt_mission_stop", "ChatGPT已停止当前低收益/不再优先的经营任务", {"reason": reason})
        autonomous_ops._save(data)
        autonomous_ops.sync_from_runtime(autostart=False)
        return {"action": action, "mission_id": mission.get("mission_id"), "state": "paused", "chatgpt_plan": None}

    if action == "continue":
        if not mission:
            raise ValueError("当前没有可继续的Mission")
        factory = cf._load()
        active = next(
            (x for x in factory.get("videos", []) if x.get("campaign_id") == mission.get("growth_id") and x.get("status") in autonomous_ops.ACTIVE_VIDEO_STATES),
            None,
        )
        started = None
        if not active:
            started = cf.create_video({"campaign_id": mission.get("growth_id")})
        mission["state"] = "active"
        mission["last_chatgpt_decision"] = {"action": action, "reason": reason, "at": now_iso()}
        autonomous_ops._event(data, mission, "chatgpt_mission_continue", "ChatGPT决定继续当前Mission并进入下一轮执行", {
            "reason": reason,
            "video_id": (started or active or {}).get("id"),
        })
        autonomous_ops._save(data)
        autonomous_ops.sync_from_runtime(autostart=False)
        return {"action": action, "mission_id": mission.get("mission_id"), "video_id": (started or active or {}).get("id"), "chatgpt_plan": chatgpt_plan}

    # create_mission: only a structured, non-financial campaign may be created.
    region = _clean(payload.get("region"), "region", 40)
    service = _clean(payload.get("service"), "service", 60)
    title = _clean(payload.get("title"), "title", 120)
    evidence = _clean(payload.get("evidence"), "evidence", 500)
    goal = _clean(payload.get("goal") or "获得可追溯的真实咨询或订单", "goal", 160)
    if region not in cf.REGIONS:
        raise ValueError("region不在当前已开放运营范围")
    if service not in cf.SERVICES:
        raise ValueError("service不在当前内容工厂范围")
    campaign = cf.create_campaign({
        "region": region,
        "service": service,
        "title": title,
        "evidence": evidence,
        "goal": goal,
        "source_type": "ChatGPT自治经营决策",
        "owner_note": reason,
    })

    # Creating a campaign is not enough: it must become the active Growth ID
    # before the shared R7/R8 Mission synchronizer can bind the new Mission.
    # Persist this explicitly instead of relying on UI/extension side effects so
    # signed Connector, tests and packaged runtime all behave identically.
    factory = cf._load()
    factory["active_campaign_id"] = campaign["id"]
    cf._save(factory)

    result = autonomous_ops.sync_from_runtime(autostart=True)
    new_mission = result.get("active_mission") or {}
    data = autonomous_ops._load()
    current = autonomous_ops._find_mission(data, growth_id=campaign.get("id"))
    if current:
        current["last_chatgpt_decision"] = {"action": action, "reason": reason, "at": now_iso()}
        autonomous_ops._event(data, current, "chatgpt_mission_created", "ChatGPT根据R7复盘创建下一轮经营Mission", {
            "reason": reason,
            "growth_id": campaign.get("id"),
        })
        autonomous_ops._save(data)
    return {
        "action": action,
        "mission_id": new_mission.get("mission_id") or (current or {}).get("mission_id"),
        "growth_id": campaign.get("id"),
        "video_id": (new_mission or {}).get("active_video_id"),
        "state": "active",
        "chatgpt_plan": chatgpt_plan,
    }
