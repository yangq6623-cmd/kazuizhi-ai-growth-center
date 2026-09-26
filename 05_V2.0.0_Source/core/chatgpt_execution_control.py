"""Daily execution permits issued only through the verified ChatGPT control loop.

This is deliberately a small gate, not another planner.  The desktop can
collect local evidence at any time, but a Mission may generate, publish or
submit SEO/GEO work only after ChatGPT has returned a dated plan through the
signed Command -> Receipt path.
"""
from __future__ import annotations

from copy import deepcopy
from datetime import datetime, timedelta

from core.storage import now_iso, read_json, write_json

STORE = "r8_18/chatgpt_execution_plans.json"
SCHEMA = "kz.chatgpt-execution-plan.v1"
SEO_GEO_ACTIONS = {
    "seo_discovery", "seo_plan", "seo_generate", "seo_qc", "seo_publish",
    "seo_submit", "seo_monitor", "geo_baseline", "geo_observe", "attribution_review",
}
PLATFORM_ACTIONS = {
    "market_scan", "content_generate", "content_qc", "social_draft",
    "video_generate", "local_analysis", "conversion_analysis", "daily_review",
    "publish_plan", "publish_execute",
}
EXECUTION_ACTIONS = SEO_GEO_ACTIONS | PLATFORM_ACTIONS


def _today() -> str:
    return datetime.now().astimezone().date().isoformat()


def _default() -> dict:
    return {"schema": SCHEMA, "plans": [], "updated_at": ""}


def _load() -> dict:
    data = read_json(STORE, _default())
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        data = _default()
    data.setdefault("plans", [])
    return data


def _save(data: dict) -> None:
    data["schema"] = SCHEMA
    data["updated_at"] = now_iso()
    data["plans"] = list(data.get("plans") or [])[-180:]
    write_json(STORE, data)


def normalize_plan(value: dict | None) -> dict:
    """Validate the narrow plan ChatGPT may attach to a Mission command."""
    if not isinstance(value, dict):
        raise ValueError("ChatGPT 执行计划必须是对象")
    date = str(value.get("date") or _today()).strip()
    try:
        effective = datetime.fromisoformat(date).date()
    except ValueError as error:
        raise ValueError("执行计划日期格式应为 YYYY-MM-DD") from error
    today = datetime.now().astimezone().date()
    if effective < today - timedelta(days=1) or effective > today + timedelta(days=14):
        raise ValueError("执行计划日期必须在昨天至未来14天内")
    focus = str(value.get("focus") or "").strip()
    if not focus or len(focus) > 500:
        raise ValueError("执行计划需要 1–500 字的当日重点")
    raw_actions = value.get("actions")
    if not isinstance(raw_actions, list) or not raw_actions:
        raise ValueError("执行计划至少需要一个 actions 动作")
    actions = []
    for item in raw_actions:
        action = str(item or "").strip()
        if action not in EXECUTION_ACTIONS:
            raise ValueError(f"不支持的总控执行动作：{action}")
        if action not in actions:
            actions.append(action)
    if len(actions) > 9:
        raise ValueError("单日执行计划最多包含 9 个动作")
    return {"date": date, "focus": focus, "actions": actions}


def record_verified_plan(*, command_id: str, receipt_id: str, mission_id: str, plan: dict) -> dict:
    """Persist a permit after the normal control connector has verified it."""
    normalized = normalize_plan(plan)
    mission = str(mission_id or "").strip()
    if not mission:
        raise ValueError("执行计划缺少 Mission")
    data = _load()
    item = {
        **normalized,
        "command_id": str(command_id or "").strip(),
        "receipt_id": str(receipt_id or "").strip(),
        "mission_id": mission,
        "authorized_at": now_iso(),
        "source": "verified_chatgpt_command_receipt",
    }
    data["plans"] = [row for row in data["plans"] if not (
        row.get("mission_id") == mission and row.get("date") == item["date"]
    )]
    data["plans"].append(item)
    _save(data)
    return deepcopy(item)


def execution_gate(mission_id: str | None, *, date: str | None = None) -> dict:
    """Return an explainable allow/deny decision for execution side effects."""
    from integrations.chatgpt_control import control_status

    state = control_status()
    mission = str(mission_id or "").strip()
    current_date = str(date or _today())
    if not state.get("verified"):
        return {
            "allowed": False,
            "code": "chatgpt_not_verified",
            "reason": "ChatGPT 总控尚未完成真实双向验证；系统只保留观察和证据采集，不执行 SEO/GEO 生产、发布或提交。",
            "plan": None,
        }
    if not mission:
        return {
            "allowed": False,
            "code": "chatgpt_mission_required",
            "reason": "当前没有已由 ChatGPT 选定的 Mission，不能执行 SEO/GEO 工作。",
            "plan": None,
        }
    data = _load()
    plan = next((row for row in reversed(data["plans"]) if row.get("mission_id") == mission and row.get("date") == current_date), None)
    if not plan:
        return {
            "allowed": False,
            "code": "chatgpt_daily_plan_required",
            "reason": "等待 ChatGPT 下达并回执今日 SEO/GEO 执行计划；系统不会自行生成、发布或提交。",
            "plan": None,
        }
    return {"allowed": True, "code": "approved", "reason": "今日执行计划已由 ChatGPT 总控回执。", "plan": deepcopy(plan)}


def allows_action(gate: dict | None, *actions: str) -> bool:
    """Whether a verified daily plan explicitly permits at least one action."""
    if not isinstance(gate, dict) or not gate.get("allowed"):
        return False
    approved = set((gate.get("plan") or {}).get("actions") or [])
    return bool(approved.intersection(str(action or "").strip() for action in actions))


def status(mission_id: str | None = None) -> dict:
    gate = execution_gate(mission_id)
    data = _load()
    return {
        "gate": gate,
        "today": _today(),
        "recent_plans": deepcopy(list(reversed(data.get("plans") or []))[:10]),
    }
