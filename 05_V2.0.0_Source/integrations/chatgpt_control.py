"""Truthful ChatGPT control connector state for R8-10.

The connector state is the single source of truth for all owner-facing pages.
A writable folder, fallback bridge, local AI gateway, or configured API key can
never elevate the state to CONNECTED_VERIFIED. Verification requires a real
external connector round trip that produces a matching Command + Receipt pair.
"""
from __future__ import annotations

import secrets
from datetime import datetime

from core.storage import now_iso, read_json, write_json

STATE_FILE = "r8_10/chatgpt_control.json"
COMMANDS_FILE = "r8_10/chatgpt_control_commands.json"
RECEIPTS_FILE = "r8_10/chatgpt_control_receipts.json"

CONNECTED_VERIFIED = "CONNECTED_VERIFIED"
CONNECTED_UNVERIFIED = "CONNECTED_UNVERIFIED"
WAITING_RESPONSE = "WAITING_RESPONSE"
DEGRADED = "DEGRADED"
DISCONNECTED = "DISCONNECTED"
HUMAN_ACTION_REQUIRED = "HUMAN_ACTION_REQUIRED"
ALLOWED_STATES = {
    CONNECTED_VERIFIED,
    CONNECTED_UNVERIFIED,
    WAITING_RESPONSE,
    DEGRADED,
    DISCONNECTED,
    HUMAN_ACTION_REQUIRED,
}
ALLOWED_PROOF_SOURCES = {"chatgpt_app", "chatgpt_plugin", "signed_relay"}
DEFAULT_PERMISSIONS = [
    "read_missions",
    "read_execution_status",
    "read_business_summary",
    "create_mission",
    "adjust_mission_priority",
    "start_content_production",
    "start_brand_growth",
    "pause_non_financial_mission",
]
FORBIDDEN_PERMISSIONS = {
    "payment", "refund", "withdrawal", "settlement", "recharge",
    "subsidy", "compensation", "commission_payment",
}
STATE_LABELS = {
    CONNECTED_VERIFIED: "已验证连接",
    CONNECTED_UNVERIFIED: "已授权待验证",
    WAITING_RESPONSE: "等待 ChatGPT 返回",
    DEGRADED: "降级运行",
    DISCONNECTED: "未验证连接",
    HUMAN_ACTION_REQUIRED: "需要处理",
}


def _default_state() -> dict:
    return {
        "connection_state": DISCONNECTED,
        "status": "unverified",
        "status_label": STATE_LABELS[DISCONNECTED],
        "verified": False,
        "connector_id": None,
        "proof_source": None,
        "challenge_id": None,
        "last_command_id": None,
        "last_receipt_id": None,
        "last_command_at": None,
        "last_receipt_at": None,
        "last_heartbeat": None,
        "verified_at": None,
        "permissions": [],
        "runtime_issue": None,
        "message": "尚未完成 ChatGPT 总控的真实双向往返验证。",
    }


def _clean_permissions(values) -> list[str]:
    result = []
    for value in values or []:
        name = str(value or "").strip()
        if not name or name in FORBIDDEN_PERMISSIONS or name in result:
            continue
        result.append(name)
    return result


def _load_list(path: str) -> list[dict]:
    value = read_json(path, [])
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, dict)]


def _save_list(path: str, values: list[dict], limit: int = 500) -> None:
    write_json(path, values[-limit:])


def _find(items: list[dict], key: str, value: str):
    target = str(value or "").strip()
    for item in reversed(items):
        if str(item.get(key) or "").strip() == target:
            return item
    return None


def _proof_is_valid(state: dict) -> bool:
    """Validate the durable verification handshake, not the latest business command.

    last_command_id/last_receipt_id are operational pointers and legitimately
    change while an owner command is waiting for a new receipt. Verification
    must therefore be anchored to the earlier verification challenge ledger.
    """
    required = ("connector_id", "proof_source", "challenge_id", "verified_at")
    if not all(state.get(key) for key in required):
        return False
    if state.get("proof_source") not in ALLOWED_PROOF_SOURCES:
        return False

    connector_id = str(state.get("connector_id") or "")
    challenge_id = str(state.get("challenge_id") or "")
    commands = _load_list(COMMANDS_FILE)
    receipts = _load_list(RECEIPTS_FILE)
    for receipt in reversed(receipts):
        if receipt.get("kind") != "verification_receipt":
            continue
        if str(receipt.get("connector_id") or "") != connector_id:
            continue
        if str(receipt.get("challenge_id") or "") != challenge_id:
            continue
        command = _find(commands, "command_id", receipt.get("command_id"))
        if not command or command.get("kind") != "verification_challenge":
            continue
        if str(command.get("connector_id") or "") != connector_id:
            continue
        if str(command.get("challenge_id") or "") != challenge_id:
            continue
        return True
    return False


def _legacy_status(connection_state: str, verified: bool) -> str:
    if verified and connection_state == CONNECTED_VERIFIED:
        return "verified"
    if connection_state == CONNECTED_UNVERIFIED:
        return "authorized"
    if connection_state == WAITING_RESPONSE:
        return "waiting_response"
    if connection_state == DEGRADED:
        return "degraded"
    if connection_state == HUMAN_ACTION_REQUIRED:
        return "human_action_required"
    return "unverified"


def control_status() -> dict:
    raw = read_json(STATE_FILE, _default_state())
    state = _default_state()
    if isinstance(raw, dict):
        state.update(raw)

    connection_state = str(state.get("connection_state") or DISCONNECTED)
    if connection_state not in ALLOWED_STATES:
        connection_state = DISCONNECTED

    proof_valid = bool(state.get("verified")) and _proof_is_valid(state)
    if not proof_valid and connection_state == CONNECTED_VERIFIED:
        connection_state = DISCONNECTED

    state["verified"] = bool(proof_valid)
    state["connection_state"] = connection_state
    state["status"] = _legacy_status(connection_state, bool(proof_valid))
    state["status_label"] = STATE_LABELS[connection_state]
    state["permissions"] = _clean_permissions(state.get("permissions")) if proof_valid else []

    if proof_valid and connection_state == CONNECTED_VERIFIED:
        state["message"] = "ChatGPT 总控已完成真实 Command → Receipt 往返验证。"
    elif connection_state == WAITING_RESPONSE:
        state["message"] = state.get("runtime_issue") or "已发送真实指令，正在等待 ChatGPT 返回。"
    elif connection_state == DEGRADED:
        state["message"] = state.get("runtime_issue") or "ChatGPT 总控当前降级，本地自治继续执行已批准任务。"
    elif connection_state == HUMAN_ACTION_REQUIRED:
        state["message"] = state.get("runtime_issue") or "自动恢复已达到上限，需要人工处理连接问题。"
    elif connection_state == CONNECTED_UNVERIFIED:
        state["message"] = "已建立授权关系，但尚未完成 Command → Receipt 往返验证。"
    else:
        state["message"] = "文件桥、备用 API 或可写目录均不能作为 ChatGPT 已连接的证明。"
    return state


def recent_commands(limit: int = 50) -> list[dict]:
    size = min(200, max(1, int(limit or 50)))
    return _load_list(COMMANDS_FILE)[-size:][::-1]


def recent_receipts(limit: int = 50) -> list[dict]:
    size = min(200, max(1, int(limit or 50)))
    return _load_list(RECEIPTS_FILE)[-size:][::-1]


def primary_blocker() -> dict:
    state = control_status()
    connection_state = state.get("connection_state")
    if connection_state == HUMAN_ACTION_REQUIRED:
        return {"code": "chatgpt_human_action_required", "severity": 100, "title": "ChatGPT 总控需要处理", "detail": state.get("message")}
    if not state.get("verified"):
        return {"code": "chatgpt_not_verified", "severity": 95, "title": "ChatGPT 总控未验证连接", "detail": state.get("message")}
    if connection_state == DEGRADED:
        return {"code": "chatgpt_degraded", "severity": 90, "title": "ChatGPT 总控降级运行", "detail": state.get("message")}
    if connection_state == WAITING_RESPONSE:
        return {"code": "chatgpt_waiting", "severity": 70, "title": "等待 ChatGPT 返回", "detail": state.get("message")}
    return {"code": "none", "severity": 0, "title": "无总控阻塞", "detail": "ChatGPT 总控连接未发现阻塞。"}


def _write_state(**updates) -> dict:
    raw = read_json(STATE_FILE, _default_state())
    state = _default_state()
    if isinstance(raw, dict):
        state.update(raw)
    state.update(updates)
    write_json(STATE_FILE, state)
    return control_status()


def set_runtime_state(connection_state: str, *, issue: str | None = None) -> dict:
    state_name = str(connection_state or "").strip().upper()
    if state_name not in ALLOWED_STATES:
        raise ValueError("未知 ChatGPT 总控状态")
    current = control_status()
    if state_name == CONNECTED_VERIFIED and not current.get("verified"):
        raise ValueError("没有真实 Command → Receipt 证明，不能标记为已验证连接")
    return _write_state(
        connection_state=state_name,
        runtime_issue=(str(issue or "").strip()[:500] or None),
        last_heartbeat=now_iso(),
    )


def record_verified_roundtrip(*, connector_id: str, proof_source: str, challenge_id: str,
                              command_id: str, receipt_id: str, permissions=None) -> dict:
    """Authorized connector adapter hook; never exposed as a normal owner UI action."""
    source = str(proof_source or "").strip()
    if source not in ALLOWED_PROOF_SOURCES:
        raise ValueError("不接受未授权的 ChatGPT 连接证明来源")
    values = {
        "connector_id": connector_id,
        "challenge_id": challenge_id,
        "command_id": command_id,
        "receipt_id": receipt_id,
    }
    if any(not str(value or "").strip() for value in values.values()):
        raise ValueError("ChatGPT 往返验证信息不完整")

    current = now_iso()
    connector = str(connector_id).strip()
    challenge = str(challenge_id).strip()
    command = str(command_id).strip()
    receipt = str(receipt_id).strip()

    commands = _load_list(COMMANDS_FILE)
    if not _find(commands, "command_id", command):
        commands.append({
            "command_id": command,
            "kind": "verification_challenge",
            "source": source,
            "status": "completed",
            "connector_id": connector,
            "challenge_id": challenge,
            "created_at": current,
            "accepted_at": current,
            "completed_at": current,
        })
        _save_list(COMMANDS_FILE, commands)

    receipts = _load_list(RECEIPTS_FILE)
    if not _find(receipts, "receipt_id", receipt):
        receipts.append({
            "receipt_id": receipt,
            "command_id": command,
            "kind": "verification_receipt",
            "status": "completed",
            "connector_id": connector,
            "challenge_id": challenge,
            "created_at": current,
            "result": {"verified": True},
        })
        _save_list(RECEIPTS_FILE, receipts)

    state = {
        "connection_state": CONNECTED_VERIFIED,
        "status": "verified",
        "status_label": STATE_LABELS[CONNECTED_VERIFIED],
        "verified": True,
        "connector_id": connector,
        "proof_source": source,
        "challenge_id": challenge,
        "last_command_id": command,
        "last_receipt_id": receipt,
        "last_command_at": current,
        "last_receipt_at": current,
        "last_heartbeat": current,
        "verified_at": current,
        "permissions": _clean_permissions(permissions or DEFAULT_PERMISSIONS),
        "runtime_issue": None,
        "message": "ChatGPT 总控已完成真实双向验证。",
    }
    write_json(STATE_FILE, state)
    return control_status()


def mark_unverified(reason: str = "连接证明失效") -> dict:
    state = _default_state()
    state["runtime_issue"] = str(reason or "连接证明失效")[:500]
    state["message"] = state["runtime_issue"]
    write_json(STATE_FILE, state)
    return control_status()


def create_owner_command(payload: dict) -> dict:
    status = control_status()
    if not status.get("verified"):
        raise ValueError("ChatGPT 总控尚未完成真实双向验证，不能把本地目标标记为已送达 ChatGPT")
    objective = str((payload or {}).get("objective") or "").strip()
    if not objective:
        raise ValueError("经营目标不能为空")
    if len(objective) > 1200:
        raise ValueError("经营目标过长")

    now = datetime.now().astimezone()
    command_id = f"CMD-{now:%Y%m%d}-{secrets.token_hex(3).upper()}"
    commands = _load_list(COMMANDS_FILE)
    item = {
        "command_id": command_id,
        "kind": "owner_objective",
        "objective": objective,
        "source": "owner_workbench",
        "status": "queued_for_verified_connector",
        "created_at": now_iso(),
        "accepted_at": None,
        "completed_at": None,
        "mission_id": None,
        "receipt_id": None,
        "connector_id": status.get("connector_id"),
        "challenge_id": status.get("challenge_id"),
    }
    commands.append(item)
    _save_list(COMMANDS_FILE, commands)
    _write_state(
        connection_state=WAITING_RESPONSE,
        last_command_id=command_id,
        last_command_at=item["created_at"],
        last_heartbeat=now_iso(),
        runtime_issue="经营目标已进入真实总控队列，等待 ChatGPT 接收并返回执行回执。",
    )
    return item


def acknowledge_command(command_id: str, *, mission_id: str | None = None) -> dict:
    status = control_status()
    if not status.get("verified"):
        raise ValueError("ChatGPT 总控未验证，不能确认外部接收")
    commands = _load_list(COMMANDS_FILE)
    item = _find(commands, "command_id", command_id)
    if not item:
        raise ValueError("未找到 Command")
    item["status"] = "accepted"
    item["accepted_at"] = now_iso()
    if mission_id:
        item["mission_id"] = str(mission_id).strip()
    _save_list(COMMANDS_FILE, commands)
    _write_state(
        connection_state=WAITING_RESPONSE,
        last_command_id=item["command_id"],
        last_command_at=item.get("accepted_at"),
        last_heartbeat=now_iso(),
        runtime_issue="Command 已被 ChatGPT 总控接收，等待 Mission 执行结果回执。",
    )
    return dict(item)


def record_command_receipt(command_id: str, result, *, mission_id: str | None = None,
                           receipt_status: str = "completed") -> dict:
    status = control_status()
    if not status.get("verified"):
        raise ValueError("ChatGPT 总控未验证，不能写入已验证执行回执")
    commands = _load_list(COMMANDS_FILE)
    item = _find(commands, "command_id", command_id)
    if not item:
        raise ValueError("未找到 Command")

    current = now_iso()
    receipt_id = f"RECEIPT-{datetime.now().astimezone():%Y%m%d}-{secrets.token_hex(3).upper()}"
    mission = str(mission_id or item.get("mission_id") or "").strip() or None
    receipt = {
        "receipt_id": receipt_id,
        "command_id": item["command_id"],
        "kind": "execution_receipt",
        "status": str(receipt_status or "completed").strip(),
        "connector_id": status.get("connector_id"),
        "challenge_id": status.get("challenge_id"),
        "mission_id": mission,
        "created_at": current,
        "result": result if isinstance(result, (dict, list, str, int, float, bool)) or result is None else str(result),
    }
    receipts = _load_list(RECEIPTS_FILE)
    receipts.append(receipt)
    _save_list(RECEIPTS_FILE, receipts)

    item["status"] = receipt["status"]
    item["completed_at"] = current
    item["receipt_id"] = receipt_id
    item["mission_id"] = mission
    _save_list(COMMANDS_FILE, commands)

    _write_state(
        connection_state=CONNECTED_VERIFIED,
        last_command_id=item["command_id"],
        last_receipt_id=receipt_id,
        last_receipt_at=current,
        last_heartbeat=current,
        runtime_issue=None,
    )
    return receipt
