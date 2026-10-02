"""R8-21 connector router enrichment for real search connectors and GEO A/B.

Keeps the base channel/model/control mapping small while adding the concrete
search submission adapters already present in R8-16 plus the formal external-AI
browser route used by R8-19. Capability availability is not a success claim.
"""
from __future__ import annotations

from copy import deepcopy

from integrations import seo_geo_connector_router as base


def _safe(callable_obj, fallback):
    try:
        value = callable_obj()
        return value if isinstance(value, dict) else deepcopy(fallback)
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError, AttributeError):
        return deepcopy(fallback)


def _search_rows() -> list[dict]:
    from integrations.search_engine_submitter import status as search_status
    from integrations.seo_public_deployer import status as deploy_status

    search = _safe(search_status, {})
    deploy = _safe(deploy_status, {})
    connectors = search.get("connectors") if isinstance(search.get("connectors"), dict) else {}

    def search_row(connector_id, source_key, name):
        raw = connectors.get(source_key) if isinstance(connectors.get(source_key), dict) else {}
        configured = bool(raw.get("configured"))
        ready = bool(raw.get("ready"))
        return {
            "id": connector_id,
            "name": name,
            "kind": "search_connector",
            "group": "search_submit",
            "software_route_ready": configured or (source_key == "bing"),
            "external_verified": ready,
            "route_state": "ready" if ready else "configured_waiting_external" if configured else "auto_prepare" if source_key == "bing" else "not_configured",
            "capabilities": ["seo_submit", "search_receipt", "seo_visibility_input"],
            "use_for_seo": True,
            "use_for_geo": False,
            "use_for_distribution": False,
            "use_for_ai_execution": False,
            "use_for_business_attribution": False,
            "formal_geo_evidence": False,
            "formal_evidence_policy": "搜索平台接收回执只推进到SUBMITTED；抓取、收录、排名和GEO引用必须继续等待各自真实Evidence。",
            "reason": raw.get("reason") or "",
            "human_gates": ["owner_authorization"] if raw.get("requires_owner") else [],
            "next_action": "已纳入SEO自动提交路由。" if ready else str(raw.get("reason") or "等待连接器准备完成。"),
        }

    deploy_ready = bool(deploy.get("ready"))
    return [
        search_row("baidu_search_resource_api", "baidu", "百度搜索资源平台 API"),
        search_row("bing_indexnow", "bing", "Bing / IndexNow"),
        search_row("google_search_console", "google", "Google Search Console"),
        {
            "id": "seo_public_deployer",
            "name": "SEO/GEO 公网发布器",
            "kind": "system",
            "group": "owned",
            "software_route_ready": bool(deploy.get("configured") or deploy_ready),
            "external_verified": deploy_ready,
            "route_state": "ready" if deploy_ready else "configured_waiting_live" if deploy.get("configured") else "not_configured",
            "capabilities": ["seo_publish", "geo_publish", "public_url_verification"],
            "use_for_seo": True,
            "use_for_geo": True,
            "use_for_distribution": False,
            "use_for_ai_execution": False,
            "use_for_business_attribution": False,
            "formal_geo_evidence": False,
            "formal_evidence_policy": "真实公网URL/HTTP验证只证明PUBLISHED；不证明搜索收录、排名或AI引用。",
            "reason": deploy.get("reason") or "",
            "human_gates": [],
            "next_action": "已纳入SEO/GEO真实公网发布路由。" if deploy_ready else str(deploy.get("reason") or "等待公网发布器就绪。"),
        },
        {
            "id": "geo_external_ai_browser",
            "name": "真实外部 AI 网页 A/B 验证",
            "kind": "geo_validation",
            "group": "formal_geo",
            "software_route_ready": True,
            "external_verified": False,
            "route_state": "ready_for_real_evidence",
            "capabilities": ["formal_geo_validation", "browser_evidence", "before_after_retest"],
            "use_for_seo": False,
            "use_for_geo": True,
            "use_for_distribution": False,
            "use_for_ai_execution": False,
            "use_for_business_attribution": False,
            "formal_geo_evidence": True,
            "formal_evidence_policy": "只有真实外部AI网页回答、URL/时间/Provider等证据满足Truth Gate后，才能形成A/B Evidence；路由可用本身不增加正式题数。",
            "human_gates": ["login_or_captcha_when_platform_requires"],
            "next_action": "作为GEO正式验收与Phase3复测通道；遇到登录/验证码时转待处理，其他自治任务继续。",
        },
    ]


def _correct_live_transport_truth(rows: list[dict]) -> None:
    """Configuration is not the same as a live remote transport round trip."""
    try:
        from core.runtime_resilience import snapshot as runtime_snapshot
        runtime = runtime_snapshot()
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError, AttributeError):
        runtime = {}
    workers = runtime.get("workers") if isinstance(runtime.get("workers"), dict) else {}
    relay_worker = workers.get("chatgpt_relay") if isinstance(workers.get("chatgpt_relay"), dict) else {}
    for row in rows:
        if row.get("id") != "chatgpt_relay":
            continue
        configured = bool(row.get("software_route_ready"))
        live = bool(
            configured
            and relay_worker.get("enabled")
            and relay_worker.get("state") == "healthy"
            and int(relay_worker.get("cycles") or 0) > 0
            and relay_worker.get("last_ok_at")
        )
        row["external_verified"] = live
        if live:
            row["route_state"] = "ready"
            row["next_action"] = "安全 Relay 已有实时成功心跳，可承载远程 Command→Receipt。"
        elif configured:
            row["route_state"] = "configured_waiting_live"
            row["next_action"] = "Relay 参数已配置，但还没有当前进程的成功轮询心跳；不能把配置状态当作远程通道已在线。"
        else:
            row["route_state"] = "not_configured"


def snapshot(*, check_live=False) -> dict:
    data = base.snapshot(check_live=check_live)
    rows = list(data.get("connectors") or []) + _search_rows()
    _correct_live_transport_truth(rows)
    summary = {
        "total": len(rows),
        "software_ready": sum(1 for row in rows if row.get("software_route_ready")),
        "externally_verified": sum(1 for row in rows if row.get("external_verified")),
        "seo_routes": sum(1 for row in rows if row.get("use_for_seo") and row.get("software_route_ready")),
        "geo_routes": sum(1 for row in rows if row.get("use_for_geo") and row.get("software_route_ready")),
        "distribution_routes": sum(1 for row in rows if row.get("use_for_distribution") and row.get("software_route_ready")),
        "ai_execution_routes": sum(1 for row in rows if row.get("use_for_ai_execution") and row.get("software_route_ready")),
        "business_attribution_routes": sum(1 for row in rows if row.get("use_for_business_attribution") and row.get("software_route_ready")),
        "formal_geo_routes": sum(1 for row in rows if row.get("formal_geo_evidence") and row.get("software_route_ready")),
        "blocked": sum(1 for row in rows if not row.get("software_route_ready")),
    }
    blockers = [
        {"id": row.get("id"), "name": row.get("name"), "state": row.get("route_state"), "next_action": row.get("next_action")}
        for row in rows if not row.get("software_route_ready") or row.get("route_state") in {"configured_waiting_live", "configured_waiting_external"}
    ]
    data.update({"schema": "kz.seo-geo-connector-router.v2", "summary": summary, "connectors": rows, "blockers": blockers})
    return data


def sync_growth_health(*, check_live=False) -> dict:
    base.sync_growth_health(check_live=check_live)
    matrix = snapshot(check_live=check_live)
    try:
        from core import seo_geo_growth_intelligence as growth
        for row in _search_rows():
            if not row.get("software_route_ready"):
                continue
            detail = f"state={row.get('route_state')}; caps={','.join(row.get('capabilities') or [])}"
            growth.record_connector_health(f"route:{row.get('id')}", True, detail)
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
        "formal_geo": [row.get("id") for row in rows if row.get("formal_geo_evidence") and row.get("software_route_ready")],
        "live_remote_control": [row.get("id") for row in rows if row.get("id") == "chatgpt_relay" and row.get("external_verified")],
        "blockers": matrix.get("blockers") or [],
        "truth_rule": matrix.get("truth_rule"),
    }
