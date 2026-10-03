"""Local-first control service for the Kazuizhi AI workbench.

This module is the preferred ChatGPT transport when the owner opens the local
workbench in the ChatGPT desktop app built-in browser and Site Tools/WebMCP are
available.  It never exposes the runtime beyond localhost and it does not turn a
normal browser visit into a verified ChatGPT connection.

A verified local control session requires an actual WebMCP tool invocation. The
page supplies a fresh challenge/invocation id, the backend records a canonical
verification Command/Receipt pair, and every mutating tool subsequently writes a
normal Command -> execution Receipt audit trail.

Cloud Relay remains a remote/unattended fallback. Finance, account verification,
final-publication approval and fabricated external outcomes are never granted by
this local control surface.
"""
from __future__ import annotations

import hashlib
import secrets
from datetime import datetime

from core.storage import now_iso, read_json, write_json
from integrations import chatgpt_control as control

LOCAL_STATE_FILE = "r8_10/kz_local_control.json"
PAIRINGS_FILE = "r8_10/kz_local_control_pairings.json"
REQUESTS_FILE = "r8_10/kz_local_control_requests.json"
AUDIT_FILE = "r8_10/kz_local_control_audit.json"
CONNECTOR_ID = "kz-local-webmcp"
PROOF_SOURCE = "chatgpt_app"
TRANSPORT = "webmcp_localhost"
MAX_ITEMS = 1000

READ_TOOLS = {
    "get_system_status",
    "get_current_mission",
    "get_ai_employee_status",
    "read_receipts",
    "get_business_results",
    "get_human_attention",
}
WRITE_TOOLS = {
    "create_mission",
    "set_primary_mission",
    "start_content_task",
}
ALLOWED_TOOLS = READ_TOOLS | WRITE_TOOLS
FORBIDDEN_TOOL_WORDS = {
    "refund", "payment", "withdrawal", "settlement", "recharge", "finance",
    "commission", "compensation", "subsidy", "approve_publish", "verify_account",
}


def _clean(value, label: str, limit: int = 500, required: bool = True) -> str:
    text = str(value or "").strip()
    if required and not text:
        raise ValueError(f"{label}不能为空")
    if len(text) > limit:
        raise ValueError(f"{label}长度不能超过{limit}个字符")
    return text


def _load_list(path: str) -> list[dict]:
    value = read_json(path, [])
    return [x for x in value if isinstance(x, dict)] if isinstance(value, list) else []


def _save_list(path: str, values: list[dict], limit: int = MAX_ITEMS) -> None:
    write_json(path, values[-limit:])


def _audit(kind: str, detail=None) -> None:
    rows = _load_list(AUDIT_FILE)
    rows.append({
        "id": f"LAUDIT-{secrets.token_hex(5).upper()}",
        "at": now_iso(),
        "kind": str(kind or "event")[:80],
        "detail": detail if isinstance(detail, dict) else {},
    })
    _save_list(AUDIT_FILE, rows)


def recent_audit(limit: int = 50) -> list[dict]:
    size = min(200, max(1, int(limit or 50)))
    return _load_list(AUDIT_FILE)[-size:][::-1]


def _verified_here() -> bool:
    state = control.control_status()
    return bool(
        state.get("verified")
        and state.get("connector_id") == CONNECTOR_ID
        and state.get("proof_source") == PROOF_SOURCE
    )


def status() -> dict:
    canonical = control.control_status()
    local = read_json(LOCAL_STATE_FILE, {})
    if not isinstance(local, dict):
        local = {}
    verified = _verified_here()
    return {
        "available": True,
        "preferred_transport": True,
        "transport": TRANSPORT,
        "bind_scope": "localhost_only",
        "public_port_required": False,
        "server_required": False,
        "site_tools_required": True,
        "verified": verified,
        "connection_state": canonical.get("connection_state") if verified else "LOCAL_READY",
        "status_label": "本机直连已验证" if verified else "本机直连待首次调用",
        "connector_id": canonical.get("connector_id") if verified else CONNECTOR_ID,
        "last_pairing_at": local.get("last_pairing_at"),
        "last_tool_at": local.get("last_tool_at"),
        "last_tool": local.get("last_tool"),
        "last_command_id": canonical.get("last_command_id") if verified else None,
        "last_receipt_id": canonical.get("last_receipt_id") if verified else None,
        "relay_fallback": True,
        "truth_rule": "只有 ChatGPT 桌面端 Site Tools/WebMCP 实际调用本页工具并形成匹配回执后，才把本机直连标记为已验证。",
    }


def pair_webmcp(payload: dict) -> dict:
    values = payload if isinstance(payload, dict) else {}
    challenge_id = _clean(values.get("challenge_id"), "challenge_id", 180)
    invocation_id = _clean(values.get("invocation_id"), "invocation_id", 180)
    client = _clean(values.get("client") or "chatgpt-desktop-webmcp", "client", 120)
    if client not in {"chatgpt-desktop-webmcp", "chatgpt-work-webmcp"}:
        raise ValueError("不接受未知的本机控制客户端")

    rows = _load_list(PAIRINGS_FILE)
    existing = next((x for x in rows if x.get("challenge_id") == challenge_id), None)
    if existing:
        if existing.get("invocation_id") != invocation_id:
            raise ValueError("本机配对 challenge 已使用，拒绝重放")
        return {"idempotent": True, "pairing": existing, "status": status()}

    digest = hashlib.sha256(f"{challenge_id}:{invocation_id}".encode("utf-8")).hexdigest()[:12].upper()
    command_id = f"CMD-LOCAL-VERIFY-{digest}"
    receipt_id = f"RECEIPT-LOCAL-VERIFY-{digest}"
    canonical = control.record_verified_roundtrip(
        connector_id=CONNECTOR_ID,
        proof_source=PROOF_SOURCE,
        challenge_id=challenge_id,
        command_id=command_id,
        receipt_id=receipt_id,
        permissions=control.DEFAULT_PERMISSIONS,
    )
    item = {
        "challenge_id": challenge_id,
        "invocation_id": invocation_id,
        "client": client,
        "command_id": command_id,
        "receipt_id": receipt_id,
        "paired_at": now_iso(),
    }
    rows.append(item)
    _save_list(PAIRINGS_FILE, rows, 200)
    write_json(LOCAL_STATE_FILE, {
        "transport": TRANSPORT,
        "client": client,
        "last_pairing_at": item["paired_at"],
        "last_tool_at": item["paired_at"],
        "last_tool": "pair_webmcp",
    })
    _audit("webmcp_verified", {
        "client": client,
        "command_id": command_id,
        "receipt_id": receipt_id,
    })
    return {"idempotent": False, "pairing": item, "status": canonical}


def _require_verified() -> dict:
    if not _verified_here():
        raise ValueError("本机 Site Tools 尚未完成真实调用验证")
    return control.control_status()


def _request_record(request_id: str) -> dict | None:
    return next((x for x in _load_list(REQUESTS_FILE) if x.get("request_id") == request_id), None)


def _save_request(item: dict) -> None:
    rows = _load_list(REQUESTS_FILE)
    rows.append(item)
    _save_list(REQUESTS_FILE, rows)


def _system_status() -> dict:
    from core.autonomous_ops import snapshot
    return {
        "local_control": status(),
        "chatgpt_control": control.control_status(),
        "primary_blocker": control.primary_blocker(),
        "operations": snapshot(sync=False),
    }


def _current_mission() -> dict:
    from core.autonomous_ops import snapshot
    data = snapshot(sync=False)
    return {
        "owner_goal": data.get("owner_goal"),
        "active_mission": data.get("active_mission"),
        "world_state": data.get("world_state") or {},
        "timeline": data.get("timeline") or [],
        "truth_rule": data.get("truth_rule"),
    }


def _ai_employee_status() -> dict:
    from core.r7_engine import agent_registry
    registry = agent_registry()
    items = registry.get("items") or []
    return {
        "count": len(items),
        "items": items,
        "truth_rule": "AI 员工是统一 ChatGPT 总脑下的职责角色；这里只返回已注册角色与真实运行状态，不虚构任务已完成。",
    }


def _receipts(args: dict) -> dict:
    limit = min(100, max(1, int(args.get("limit") or 20)))
    return {"items": control.recent_receipts(limit)}


def _business_results() -> dict:
    from core.autonomous_ops import snapshot
    from promotion import content_factory as cf
    ops = snapshot(sync=False)
    factory = cf.dashboard()
    campaigns = factory.get("campaigns") or []
    videos = factory.get("videos") or []
    plans = factory.get("publication_plans") or []
    receipts = factory.get("receipts") or []
    return {
        "active_mission": ops.get("active_mission"),
        "world_state": ops.get("world_state") or {},
        "counts": {
            "campaigns": len(campaigns),
            "videos": len(videos),
            "publication_plans": len(plans),
            "platform_receipts": len(receipts),
        },
        "action_center": factory.get("action_center") or {},
        "truth_rule": "平台发布、SEO收录、咨询与订单只有存在对应真实来源/回执时才计入经营结果。",
    }


def _human_attention() -> dict:
    from promotion import content_factory as cf
    factory = cf.dashboard()
    return factory.get("action_center") or {"human_count": 0, "human_items": []}


def _canonical_business_command(objective: str) -> dict:
    command = control.create_owner_command({"objective": objective})
    control.acknowledge_command(command["command_id"])
    return command


def _create_mission(args: dict) -> dict:
    from core.autonomous_mission_decisions import apply_chatgpt_mission_decision
    from core.autonomous_ops import snapshot
    region = _clean(args.get("region"), "region", 40)
    service = _clean(args.get("service"), "service", 60)
    title = _clean(args.get("title"), "title", 120)
    evidence = _clean(args.get("evidence"), "evidence", 500)
    goal = _clean(args.get("goal") or "获得可追溯的真实咨询", "goal", 160)
    reason = _clean(args.get("reason") or "ChatGPT 通过本机 Site Tools 根据老板目标创建经营 Mission", "reason", 500)
    objective = _clean(args.get("objective") or f"重点推广{region}{service}，目标是{goal}", "objective", 1200)
    command = _canonical_business_command(objective)
    decision = apply_chatgpt_mission_decision({
        "action": "create_mission",
        "region": region,
        "service": service,
        "title": title,
        "evidence": evidence,
        "goal": goal,
        "reason": reason,
    })
    ops = snapshot(sync=False)
    mission_id = decision.get("mission_id") or (ops.get("active_mission") or {}).get("mission_id")
    receipt = control.record_command_receipt(command["command_id"], {
        "tool": "create_mission",
        "decision": decision,
        "mission": ops.get("active_mission"),
        "external_result_truth": "本回执只证明本地 Mission 已建立并进入执行链，不代表平台已发布、SEO已收录或已经产生咨询/订单。",
    }, mission_id=mission_id)
    return {"command": command, "receipt": receipt, "mission": ops.get("active_mission")}


def _set_primary_mission(args: dict) -> dict:
    from core.autonomous_ops import activate_mission, snapshot
    mission_id = _clean(args.get("mission_id"), "mission_id", 120)
    reason = _clean(args.get("reason") or "ChatGPT 将该 Mission 调整为当前 P1 经营主线", "reason", 500)
    command = _canonical_business_command(f"将 Mission {mission_id} 调整为当前优先经营主线。原因：{reason}")
    mission = activate_mission({"mission_id": mission_id})
    ops = snapshot(sync=False)
    receipt = control.record_command_receipt(command["command_id"], {
        "tool": "set_primary_mission",
        "mission": mission,
        "active_mission": ops.get("active_mission"),
    }, mission_id=mission_id)
    return {"command": command, "receipt": receipt, "mission": ops.get("active_mission")}


def _start_content_task(args: dict) -> dict:
    from core.autonomous_mission_decisions import apply_chatgpt_mission_decision
    from core.autonomous_ops import snapshot
    mission_id = _clean(args.get("mission_id"), "mission_id", 120)
    reason = _clean(args.get("reason") or "ChatGPT 通过本机 Site Tools 启动/继续当前 Mission 的内容生产", "reason", 500)
    command = _canonical_business_command(f"继续 Mission {mission_id} 的内容生产。原因：{reason}")
    decision = apply_chatgpt_mission_decision({
        "action": "continue",
        "mission_id": mission_id,
        "reason": reason,
    })
    ops = snapshot(sync=False)
    receipt = control.record_command_receipt(command["command_id"], {
        "tool": "start_content_task",
        "decision": decision,
        "mission": ops.get("active_mission"),
        "truth_rule": "启动内容任务不等于最终成片已通过，更不等于已经发布。",
    }, mission_id=mission_id)
    return {"command": command, "receipt": receipt, "mission": ops.get("active_mission"), "decision": decision}


def execute_tool(name: str, args=None, *, request_id: str | None = None) -> dict:
    tool = _clean(name, "tool", 80)
    if tool in FORBIDDEN_TOOL_WORDS or any(word in tool.lower() for word in FORBIDDEN_TOOL_WORDS):
        raise ValueError("本机直连禁止资金、账号验证或绕过最终审核的工具")
    if tool not in ALLOWED_TOOLS:
        raise ValueError("不支持的本机控制工具")
    _require_verified()
    values = args if isinstance(args, dict) else {}
    request = _clean(request_id or f"LOCAL-{secrets.token_hex(8).upper()}", "request_id", 180)

    if tool in WRITE_TOOLS:
        existing = _request_record(request)
        if existing:
            return {"idempotent": True, "request_id": request, "result": existing.get("result")}

    if tool == "get_system_status":
        result = _system_status()
    elif tool == "get_current_mission":
        result = _current_mission()
    elif tool == "get_ai_employee_status":
        result = _ai_employee_status()
    elif tool == "read_receipts":
        result = _receipts(values)
    elif tool == "get_business_results":
        result = _business_results()
    elif tool == "get_human_attention":
        result = _human_attention()
    elif tool == "create_mission":
        result = _create_mission(values)
    elif tool == "set_primary_mission":
        result = _set_primary_mission(values)
    elif tool == "start_content_task":
        result = _start_content_task(values)
    else:
        raise ValueError("不支持的本机控制工具")

    if tool in WRITE_TOOLS:
        _save_request({
            "request_id": request,
            "tool": tool,
            "created_at": now_iso(),
            "result": result,
        })
    local = read_json(LOCAL_STATE_FILE, {})
    if not isinstance(local, dict):
        local = {}
    local.update({"last_tool_at": now_iso(), "last_tool": tool})
    write_json(LOCAL_STATE_FILE, local)
    _audit("tool_executed", {
        "tool": tool,
        "request_id": request,
        "mutating": tool in WRITE_TOOLS,
        "mission_id": ((result.get("mission") or {}).get("mission_id") if isinstance(result, dict) else None),
    })
    return {"idempotent": False, "request_id": request, "tool": tool, "result": result}


def tool_catalog() -> list[dict]:
    return [
        {"name": "get_system_status", "read_only": True},
        {"name": "get_current_mission", "read_only": True},
        {"name": "get_ai_employee_status", "read_only": True},
        {"name": "read_receipts", "read_only": True},
        {"name": "get_business_results", "read_only": True},
        {"name": "get_human_attention", "read_only": True},
        {"name": "create_mission", "read_only": False},
        {"name": "set_primary_mission", "read_only": False},
        {"name": "start_content_task", "read_only": False},
    ]
