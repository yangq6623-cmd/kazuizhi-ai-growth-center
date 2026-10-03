"""R8-21 unified SEO/GEO connector capability router.

This module is the missing wiring layer between the existing connection center
and the SEO/GEO operating loop.  It does not invent external authorization or
Evidence.  Instead it translates each already-known connection into explicit
capabilities (SEO, GEO, content distribution, AI execution, business
attribution) and reports whether the route is software-ready, externally
verified, or still blocked by a real login/Relay/credential requirement.

Truth rules:
- software_route_ready never means an external platform action succeeded;
- ordinary cloud/local model calls are auxiliary C-level signals, never formal
  GEO A/B Evidence;
- social channels may provide distribution/brand signals but never count as
  formal GEO Evidence by themselves;
- external publication/search/indexing/AI visibility still require the existing
  Receipt/Evidence ledgers;
- missing credentials are surfaced, not fabricated or silently bypassed.
"""
from __future__ import annotations

from copy import deepcopy

from core.storage import now_iso
from integrations.channel_registry import snapshot as channel_registry_snapshot


SOCIAL_IDS = {"douyin", "wechat_channels", "kuaishou", "xiaohongshu", "bilibili", "weibo"}
SEARCH_IDS = {"baidu_search", "wechat_search", "sogou_search", "360_search"}
OWNED_IDS = {"website", "mini_program"}
LOCAL_DISCOVERY_IDS = {"maps_local", "local_life"}
COMMUNITY_IDS = {"qa", "forum"}

CAPABILITIES = {
    "douyin": ["content_distribution", "brand_signal", "geo_support_signal"],
    "wechat_channels": ["content_distribution", "brand_signal", "geo_support_signal"],
    "kuaishou": ["content_distribution", "brand_signal", "geo_support_signal"],
    "xiaohongshu": ["content_distribution", "brand_signal", "geo_support_signal"],
    "bilibili": ["content_distribution", "brand_signal", "geo_support_signal"],
    "weibo": ["content_distribution", "brand_signal", "geo_support_signal"],
    "baidu_search": ["seo_discovery", "seo_visibility", "geo_discovery"],
    "wechat_search": ["seo_discovery", "seo_visibility", "geo_discovery"],
    "sogou_search": ["seo_discovery", "seo_visibility", "geo_discovery"],
    "360_search": ["seo_discovery", "seo_visibility", "geo_discovery"],
    "maps_local": ["local_discovery", "brand_signal", "geo_support_signal"],
    "local_life": ["local_discovery", "brand_signal", "geo_support_signal"],
    "qa": ["content_distribution", "source_discovery", "geo_support_signal"],
    "forum": ["content_distribution", "source_discovery", "geo_support_signal"],
    "website": ["seo_publish", "geo_publish", "owned_source", "source_tracking"],
    "mini_program": ["business_attribution", "conversion_source"],
}


def _safe(callable_obj, fallback):
    try:
        value = callable_obj()
        return value if isinstance(value, dict) else deepcopy(fallback)
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError, AttributeError):
        return deepcopy(fallback)


def _formal_evidence_policy(channel_id: str) -> str:
    if channel_id in SEARCH_IDS:
        return "仅真实搜索抓取/收录/排名/曝光/点击 Evidence 可进入SEO真值；连接状态本身不算成绩。"
    if channel_id == "website":
        return "真实公网 URL/HTTP 回执可证明发布；不能证明搜索收录或GEO命中。"
    if channel_id == "mini_program":
        return "仅真实经营事件可进入业务归因；不作为GEO A/B Evidence。"
    if channel_id in SOCIAL_IDS | LOCAL_DISCOVERY_IDS | COMMUNITY_IDS:
        return "仅作为分发、品牌或来源辅助信号；不能直接进入正式GEO A/B成绩。"
    return "需要对应真实 Evidence/Receipt 才能升级外部结果。"


def _route_flags(channel_id: str, capabilities: list[str]) -> dict:
    caps = set(capabilities)
    return {
        "use_for_seo": bool(caps & {"seo_publish", "seo_discovery", "seo_visibility", "source_tracking", "source_discovery"}),
        "use_for_geo": bool(caps & {"geo_publish", "geo_discovery", "geo_support_signal", "source_discovery", "owned_source"}),
        "use_for_distribution": "content_distribution" in caps,
        "use_for_ai_execution": False,
        "use_for_business_attribution": bool(caps & {"business_attribution", "conversion_source"}),
    }


def _channel_rows() -> list[dict]:
    registry = _safe(channel_registry_snapshot, {"channels": []})
    rows = []
    for raw in registry.get("channels") or []:
        if not isinstance(raw, dict):
            continue
        channel_id = str(raw.get("id") or "").strip()
        if not channel_id:
            continue
        capabilities = list(CAPABILITIES.get(channel_id) or [])
        external_verified = bool(raw.get("external_verified"))
        software_ready = bool(raw.get("software_route_ready"))
        group = str(raw.get("group") or "")
        if external_verified:
            route_state = "ready"
        elif software_ready:
            route_state = "software_ready_external_pending"
        else:
            route_state = "not_ready"
        rows.append({
            "id": channel_id,
            "name": raw.get("name") or channel_id,
            "kind": "channel",
            "group": group,
            "software_route_ready": software_ready,
            "external_verified": external_verified,
            "route_state": route_state,
            "capabilities": capabilities,
            **_route_flags(channel_id, capabilities),
            "formal_geo_evidence": False,
            "formal_evidence_policy": _formal_evidence_policy(channel_id),
            "state_source": raw.get("state"),
            "evidence": raw.get("evidence") or "",
            "human_gates": list(raw.get("human_gates") or []),
            "next_action": (
                "直接进入对应SEO/GEO/分发路由；最终结果继续等待真实Evidence/Receipt。"
                if external_verified else
                "软件路由已接通；如平台需要登录/验证码/外部验证则保持等待，不伪造成功。"
                if software_ready else
                "连接尚未达到可路由状态。"
            ),
        })
    return rows


def _system_rows(check_live=False) -> list[dict]:
    from integrations.ai_gateway import gateway_status
    from integrations.chatgpt_control import control_status
    from integrations.chatgpt_relay_agent import relay_config_status
    from integrations.remote_agent import status as remote_agent_status

    model = _safe(gateway_status, {})
    relay = _safe(relay_config_status, {})
    control = _safe(control_status, {})
    remote = _safe(lambda: remote_agent_status(check_live=bool(check_live)), {})

    routes = model.get("routes") if isinstance(model.get("routes"), dict) else {}
    cloud = routes.get("cloud") if isinstance(routes.get("cloud"), dict) else {}
    local = routes.get("local") if isinstance(routes.get("local"), dict) else {}

    def model_row(route_id, route, name):
        configured = bool(route.get("configured"))
        verified = bool(route.get("verified"))
        return {
            "id": route_id,
            "name": name,
            "kind": "model",
            "group": "ai_execution",
            "software_route_ready": configured,
            "external_verified": verified,
            "route_state": "ready" if verified else "configured_waiting_test" if configured else "not_configured",
            "capabilities": ["analysis", "content_generation", "qc", "geo_auxiliary"],
            "use_for_seo": configured,
            "use_for_geo": configured,
            "use_for_distribution": False,
            "use_for_ai_execution": configured,
            "use_for_business_attribution": False,
            "formal_geo_evidence": False,
            "formal_evidence_policy": "模型可参与分析/生成/QC；普通API或本地模型输出只属于辅助信号，不能升级成正式GEO A/B Evidence。",
            "provider": route.get("provider"),
            "model": route.get("model"),
            "last_test_at": route.get("last_test_at"),
            "last_error": route.get("last_error"),
            "human_gates": [],
            "next_action": "已纳入SEO/GEO执行层。" if configured else "需要先完成模型配置。",
        }

    remote_ready = bool(remote.get("configured") and remote.get("connected") and remote.get("website_ready"))
    control_ready = bool(control.get("verified"))
    relay_ready = bool(relay.get("configured"))
    return [
        model_row("model_cloud", cloud, "云端大模型"),
        model_row("model_local", local, "本地大模型"),
        {
            "id": "remote_agent", "name": "公网服务器 Remote Agent", "kind": "system", "group": "owned",
            "software_route_ready": bool(remote.get("configured")), "external_verified": remote_ready,
            "route_state": "ready" if remote_ready else "configured_waiting_live" if remote.get("configured") else "not_configured",
            "capabilities": ["seo_publish", "geo_publish", "server_execution", "public_receipt"],
            "use_for_seo": True, "use_for_geo": True, "use_for_distribution": False, "use_for_ai_execution": False,
            "use_for_business_attribution": False, "formal_geo_evidence": False,
            "formal_evidence_policy": "服务器回执只证明公网发布/执行；搜索收录和GEO命中仍需各自真实Evidence。",
            "last_health_at": remote.get("last_health_at"), "last_error": remote.get("last_error"), "human_gates": [],
            "next_action": "用于SEO/GEO真实公网发布。" if remote_ready else "等待Remote Agent真实健康检查通过。",
        },
        {
            "id": "chatgpt_control", "name": "ChatGPT 总控", "kind": "system", "group": "controller",
            "software_route_ready": control_ready, "external_verified": control_ready,
            "route_state": "ready" if control_ready else str(control.get("connection_state") or "not_verified").lower(),
            "capabilities": ["controller_read", "controller_decision", "mission_priority"],
            "use_for_seo": control_ready, "use_for_geo": control_ready, "use_for_distribution": False,
            "use_for_ai_execution": False, "use_for_business_attribution": False, "formal_geo_evidence": False,
            "formal_evidence_policy": "总控只负责决策/任务；不能把控制通道当作SEO或GEO成绩。",
            "last_heartbeat": control.get("last_heartbeat"), "human_gates": [],
            "next_action": "已纳入SEO/GEO总脑决策层。" if control_ready else "需要完成真实Command→Receipt验证。",
        },
        {
            "id": "chatgpt_relay", "name": "ChatGPT 安全 Relay", "kind": "system", "group": "controller_transport",
            "software_route_ready": relay_ready, "external_verified": relay_ready,
            "route_state": "ready" if relay_ready else "not_configured",
            "capabilities": ["remote_command", "remote_receipt", "heartbeat"],
            "use_for_seo": relay_ready, "use_for_geo": relay_ready, "use_for_distribution": False,
            "use_for_ai_execution": False, "use_for_business_attribution": False, "formal_geo_evidence": False,
            "formal_evidence_policy": "Relay只承载签名Command/Receipt；不产生SEO/GEO业务真值。",
            "poll_seconds": relay.get("poll_seconds"), "human_gates": ["trusted_relay_pairing"] if not relay_ready else [],
            "next_action": "已允许远程Command→Receipt。" if relay_ready else str(relay.get("reason") or "需要配置Relay URL、Connector ID和安全凭据。"),
        },
    ]


def snapshot(*, check_live=False) -> dict:
    rows = _channel_rows() + _system_rows(check_live=check_live)
    summary = {
        "total": len(rows),
        "software_ready": sum(1 for row in rows if row.get("software_route_ready")),
        "externally_verified": sum(1 for row in rows if row.get("external_verified")),
        "seo_routes": sum(1 for row in rows if row.get("use_for_seo")),
        "geo_routes": sum(1 for row in rows if row.get("use_for_geo")),
        "distribution_routes": sum(1 for row in rows if row.get("use_for_distribution")),
        "ai_execution_routes": sum(1 for row in rows if row.get("use_for_ai_execution")),
        "business_attribution_routes": sum(1 for row in rows if row.get("use_for_business_attribution")),
        "formal_geo_routes": sum(1 for row in rows if row.get("formal_geo_evidence")),
        "blocked": sum(1 for row in rows if row.get("route_state") in {"not_ready", "not_configured", "needs_login_or_device_validation"}),
    }
    blockers = [
        {"id": row.get("id"), "name": row.get("name"), "state": row.get("route_state"), "next_action": row.get("next_action")}
        for row in rows if not row.get("software_route_ready")
    ]
    return {
        "schema": "kz.seo-geo-connector-router.v1",
        "generated_at": now_iso(),
        "summary": summary,
        "connectors": rows,
        "blockers": blockers,
        "truth_rule": "连接进入SEO/GEO路由不等于外部结果成功；发布、提交、抓取、收录、排名与GEO A/B仍分别要求真实Evidence/Receipt。",
    }


def sync_growth_health(*, check_live=False) -> dict:
    """Feed real connector availability into the existing R8-20 safeguard layer.

    Only configured/active infrastructure is written as a health signal.  A
    platform that merely awaits login is a routing blocker, not a fake runtime
    failure, so it remains visible in the matrix without poisoning the global
    health score.
    """
    matrix = snapshot(check_live=check_live)
    try:
        from core import seo_geo_growth_intelligence as growth
        for row in matrix.get("connectors") or []:
            if not isinstance(row, dict) or not row.get("software_route_ready"):
                continue
            name = f"route:{row.get('id')}"
            ok = bool(row.get("external_verified") or row.get("kind") in {"model", "channel"})
            detail = f"state={row.get('route_state')}; caps={','.join(row.get('capabilities') or [])}"
            growth.record_connector_health(name, ok, detail)
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError, AttributeError):
        pass
    return matrix


def route_summary_for_controller(*, check_live=False) -> dict:
    matrix = snapshot(check_live=check_live)
    rows = matrix.get("connectors") or []
    return {
        "summary": matrix.get("summary") or {},
        "seo": [row.get("id") for row in rows if row.get("use_for_seo") and row.get("software_route_ready")],
        "geo": [row.get("id") for row in rows if row.get("use_for_geo") and row.get("software_route_ready")],
        "distribution": [row.get("id") for row in rows if row.get("use_for_distribution") and row.get("software_route_ready")],
        "ai_execution": [row.get("id") for row in rows if row.get("use_for_ai_execution") and row.get("software_route_ready")],
        "business_attribution": [row.get("id") for row in rows if row.get("use_for_business_attribution") and row.get("software_route_ready")],
        "blockers": matrix.get("blockers") or [],
        "truth_rule": matrix.get("truth_rule"),
    }
