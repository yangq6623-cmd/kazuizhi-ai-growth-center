"""R8-23.2 task-aware model router.

Local model is the default high-frequency executor. The configured cloud route
(Doubao on the owner's machine) is mandatory for critical SEO/GEO semantic
steps and a fallback/quality escalation elsewhere. Model responses remain
C-level auxiliary output and never become external Evidence by themselves.
"""
from __future__ import annotations

from core.storage import now_iso
from core.r8_23_2_runtime_truth import model_route


def _invoke(route: str, task_kind: str, prompt: str) -> dict:
    from integrations import ai_gateway

    status = ai_gateway.gateway_status()
    route_status = (status.get("routes") or {}).get(route) or {}
    if not route_status.get("configured"):
        return {"route": route, "status": "not_configured", "success": False, "at": now_iso()}
    profile = ai_gateway._profile(route)
    profile["route"] = route
    key, _ = ai_gateway._api_key(route)
    if route == "cloud" and not key:
        return {"route": route, "status": "credential_missing", "success": False, "at": now_iso()}
    model = str(profile.get("model") or "")
    request_prompt = (
        "你是卡嘴子AI自动运营执行模型。只做分析、生成或质量复核，不执行发布、账号、权限或资金操作。"
        "不得伪造搜索结果、GEO Evidence、平台回执、订单或用户数据。"
        f"\nTASK_KIND={task_kind}\n\n{str(prompt or '')[:12000]}"
    )
    payload = {"model": model, "input": request_prompt, "max_output_tokens": 2200}
    raw = ai_gateway._http_transport(payload, key, profile)
    text = ai_gateway._extract_text(raw)
    return {
        "route": route,
        "provider": route_status.get("provider"),
        "label": route_status.get("label"),
        "model": model,
        "status": "completed",
        "success": True,
        "output": str(text or "")[:12000],
        "at": now_iso(),
        "truth_level": "C_auxiliary",
    }


def execute(task_kind: str, prompt: str, *, local_quality: float | None = None) -> dict:
    policy = model_route(task_kind, local_quality=local_quality)
    attempts = []
    final_text = ""
    local_ok = False

    try:
        local = _invoke("local", task_kind, prompt)
    except (OSError, ValueError, RuntimeError, TypeError, KeyError, AttributeError) as error:
        local = {"route": "local", "status": "failed", "success": False, "error": str(error)[:500], "at": now_iso()}
    attempts.append(local)
    local_ok = bool(local.get("success"))
    if local_ok:
        final_text = str(local.get("output") or "")

    need_cloud = bool(policy.get("doubao_required")) or not local_ok
    cloud = None
    if need_cloud:
        cloud_prompt = prompt
        if final_text:
            cloud_prompt += "\n\nLOCAL_MODEL_DRAFT_OR_ANALYSIS:\n" + final_text[:8000] + "\n\n请做增强、纠错或语义复核，并明确不能证明的外部事实。"
        try:
            cloud = _invoke("cloud", task_kind, cloud_prompt)
        except (OSError, ValueError, RuntimeError, TypeError, KeyError, AttributeError) as error:
            cloud = {"route": "cloud", "status": "failed", "success": False, "error": str(error)[:500], "at": now_iso()}
        attempts.append(cloud)
        if cloud.get("success"):
            final_text = str(cloud.get("output") or "")

    required_cloud_missing = bool(policy.get("doubao_required")) and not bool((cloud or {}).get("success"))
    success = bool(final_text) and not required_cloud_missing
    result = {
        "task_kind": task_kind,
        "policy": policy,
        "attempts": attempts,
        "success": success,
        "degraded": required_cloud_missing or (not local_ok and bool((cloud or {}).get("success"))),
        "required_cloud_missing": required_cloud_missing,
        "output": final_text[:12000],
        "truth_level": "C_auxiliary",
        "formal_evidence": False,
        "at": now_iso(),
    }
    try:
        from core import r8_23_growth_operating_system as growth_os
        for attempt in attempts:
            capability = "local_model" if attempt.get("route") == "local" else "doubao_cloud"
            growth_os.record_utilization(
                capability,
                success=bool(attempt.get("success")),
                result={"reason": attempt.get("status")},
                reason=f"R8-23.2 model route: {task_kind}",
                context={"task_kind": task_kind, "required": capability == "doubao_cloud" and bool(policy.get("doubao_required"))},
            )
    except (ImportError, OSError, ValueError, RuntimeError, TypeError, KeyError, AttributeError):
        pass
    return result
