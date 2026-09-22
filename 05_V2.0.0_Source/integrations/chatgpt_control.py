"""Truthful ChatGPT control-connector state for R8-10.

This module deliberately does not infer a ChatGPT connection from a writable
folder, the fallback operations bridge, or an OpenAI API credential. A verified
state may only be written by a future authorized connector adapter after a real
round trip (read -> command -> receipt) has been proven.
"""
from __future__ import annotations

import secrets
from datetime import datetime

from core.storage import now_iso, read_json, write_json

STATE_FILE = "r8_10/chatgpt_control.json"
COMMANDS_FILE = "r8_10/chatgpt_control_commands.json"
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


def _default_state() -> dict:
    return {
        "status": "unverified",
        "status_label": "未验证连接",
        "verified": False,
        "connector_id": None,
        "proof_source": None,
        "challenge_id": None,
        "last_command_id": None,
        "last_receipt_id": None,
        "last_receipt_at": None,
        "verified_at": None,
        "permissions": [],
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


def control_status() -> dict:
    raw = read_json(STATE_FILE, _default_state())
    state = _default_state()
    if isinstance(raw, dict):
        state.update(raw)
    proof_complete = all(
        state.get(key)
        for key in ("connector_id", "proof_source", "challenge_id", "last_command_id", "last_receipt_id", "verified_at")
    )
    source_ok = state.get("proof_source") in ALLOWED_PROOF_SOURCES
    verified = bool(state.get("verified")) and proof_complete and source_ok
    state["verified"] = verified
    if verified:
        state["status"] = "verified"
        state["status_label"] = "已验证连接"
        state["permissions"] = _clean_permissions(state.get("permissions"))
        state["message"] = "ChatGPT 总控已完成真实往返验证；所有动作仍受权限与人工门禁约束。"
    else:
        state["status"] = "unverified"
        state["status_label"] = "未验证连接"
        state["permissions"] = []
        state["message"] = "文件桥、备用 API 或可写目录均不能作为 ChatGPT 已连接的证明。"
    return state


def record_verified_roundtrip(*, connector_id: str, proof_source: str, challenge_id: str,
                              command_id: str, receipt_id: str, permissions=None) -> dict:
    """Internal adapter hook; intentionally not exposed as a local UI endpoint."""
    source = str(proof_source or "").strip()
    if source not in ALLOWED_PROOF_SOURCES:
        raise ValueError("不接受未授权的 ChatGPT 连接证明来源")
    required = {
        "connector_id": connector_id,
        "challenge_id": challenge_id,
        "command_id": command_id,
        "receipt_id": receipt_id,
    }
    if any(not str(value or "").strip() for value in required.values()):
        raise ValueError("ChatGPT 往返验证信息不完整")
    current = now_iso()
    state = {
        "status": "verified",
        "status_label": "已验证连接",
        "verified": True,
        "connector_id": str(connector_id).strip(),
        "proof_source": source,
        "challenge_id": str(challenge_id).strip(),
        "last_command_id": str(command_id).strip(),
        "last_receipt_id": str(receipt_id).strip(),
        "last_receipt_at": current,
        "verified_at": current,
        "permissions": _clean_permissions(permissions or DEFAULT_PERMISSIONS),
        "message": "ChatGPT 总控已完成真实双向验证。",
    }
    write_json(STATE_FILE, state)
    return control_status()


def mark_unverified(reason: str = "连接证明失效") -> dict:
    state = _default_state()
    state["message"] = str(reason or "连接证明失效")[:300]
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
    commands = read_json(COMMANDS_FILE, [])
    if not isinstance(commands, list):
        commands = []
    item = {
        "command_id": command_id,
        "objective": objective,
        "source": "owner_workbench",
        "status": "queued_for_verified_connector",
        "created_at": now_iso(),
        "connector_id": status.get("connector_id"),
    }
    commands.append(item)
    write_json(COMMANDS_FILE, commands[-300:])
    return item
