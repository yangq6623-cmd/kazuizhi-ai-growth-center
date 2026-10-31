"""Signed external adapter for the Kazuizhi ChatGPT Control Connector.

This module is deliberately transport-neutral. A future ChatGPT Plugin/App or
trusted relay may deliver signed envelopes through HTTP, a local helper or
another supported connector transport. The adapter is the only layer allowed to
turn a verified external round trip into the canonical ChatGPT control state.

Truth and safety rules:
- ChatGPT Plus is not treated as an unattended API credential.
- A writable folder, local HTTP request or configured OpenAI API key is not
  enough to mark the connector verified.
- Every external envelope is HMAC authenticated, timestamp bounded and nonce
  replay protected.
- Finance permissions are never granted through this connector.
- Command processing is idempotent: retrying the same business command returns
  its existing Receipt instead of creating duplicate Missions.
- Real publication, search indexing, consultations and orders are never claimed
  unless the underlying R8 ledgers contain verified receipts/data.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
from datetime import datetime

from core.storage import now_iso, read_json, write_json
from integrations import chatgpt_control as control

PAIRINGS_FILE = "r8_10/chatgpt_connector_pairings.json"
NONCES_FILE = "r8_10/chatgpt_connector_nonces.json"
AUDIT_FILE = "r8_10/chatgpt_connector_audit.json"
SECRET_ENV = "KAZUIZHI_CHATGPT_RELAY_SECRET"
MAX_SKEW_SECONDS = 300
PAIRING_TTL_SECONDS = 600
MAX_NONCES = 2000
MAX_AUDIT = 1000
ALLOWED_ACTIONS = {
    "begin_pairing",
    "complete_pairing",
    "heartbeat",
    "pull_commands",
    "read_state",
    "apply_decision",
}


def _load_list(path: str) -> list[dict]:
    value = read_json(path, [])
    return [item for item in value if isinstance(item, dict)] if isinstance(value, list) else []


def _save_list(path: str, items: list[dict], limit: int) -> None:
    write_json(path, items[-limit:])


def _clean(value, label: str, limit: int = 300, required: bool = True) -> str:
    text = str(value or "").strip()
    if required and not text:
        raise ValueError(f"{label}不能为空")
    if len(text) > limit:
        raise ValueError(f"{label}长度不能超过{limit}个字符")
    return text


def _secret(explicit: str | None = None) -> bytes:
    value = str(explicit or os.environ.get(SECRET_ENV) or "").strip()
    if len(value) < 32:
        raise ValueError("ChatGPT Connector 尚未完成安全配对凭据配置")
    return value.encode("utf-8")


def adapter_status() -> dict:
    state = control.control_status()
    configured = len(str(os.environ.get(SECRET_ENV) or "").strip()) >= 32
    return {
        "id": "kz_chatgpt_control_connector",
        "transport": "signed_relay_contract",
        "credential_source": "environment" if configured else "not_provisioned",
        "credential_configured": configured,
        "connection_state": state.get("connection_state"),
        "verified": bool(state.get("verified")),
        "connector_id": state.get("connector_id"),
        "last_heartbeat": state.get("last_heartbeat"),
        "last_command_id": state.get("last_command_id"),
        "last_receipt_id": state.get("last_receipt_id"),
        "truth_rule": "只有签名验证、挑战往返和匹配 Receipt 全部成立才显示 ChatGPT 总控已验证连接。",
    }


def _canonical(connector_id: str, timestamp: int, nonce: str, action: str, data) -> bytes:
    body = json.dumps(data if isinstance(data, dict) else {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    value = f"{connector_id}\n{timestamp}\n{nonce}\n{action}\n{digest}"
    return value.encode("utf-8")


def sign_envelope(*, connector_id: str, action: str, data=None, timestamp: int | None = None,
                  nonce: str | None = None, secret: str | None = None) -> dict:
    """Helper used by connector clients/tests; the shared secret is never logged."""
    connector = _clean(connector_id, "connector_id", 120)
    action_name = _clean(action, "action", 80)
    if action_name not in ALLOWED_ACTIONS:
        raise ValueError("不支持的 Connector action")
    stamp = int(timestamp if timestamp is not None else time.time())
    nonce_value = _clean(nonce or secrets.token_urlsafe(18), "nonce", 160)
    payload = data if isinstance(data, dict) else {}
    signature = hmac.new(
        _secret(secret),
        _canonical(connector, stamp, nonce_value, action_name, payload),
        hashlib.sha256,
    ).hexdigest()
    return {
        "connector_id": connector,
        "timestamp": stamp,
        "nonce": nonce_value,
        "action": action_name,
        "data": payload,
        "signature": signature,
    }


def _consume_nonce(connector_id: str, nonce: str, timestamp: int) -> None:
    items = _load_list(NONCES_FILE)
    cutoff = int(time.time()) - (MAX_SKEW_SECONDS * 2)
    items = [item for item in items if int(item.get("timestamp") or 0) >= cutoff]
    if any(item.get("connector_id") == connector_id and item.get("nonce") == nonce for item in items):
        raise ValueError("Connector nonce 已使用，拒绝重放请求")
    items.append({"connector_id": connector_id, "nonce": nonce, "timestamp": int(timestamp), "used_at": now_iso()})
    _save_list(NONCES_FILE, items, MAX_NONCES)


def verify_envelope(envelope: dict, *, secret: str | None = None, consume_nonce: bool = True) -> dict:
    if not isinstance(envelope, dict):
        raise ValueError("Connector envelope 格式不正确")
    connector = _clean(envelope.get("connector_id"), "connector_id", 120)
    action = _clean(envelope.get("action"), "action", 80)
    if action not in ALLOWED_ACTIONS:
        raise ValueError("不支持的 Connector action")
    nonce = _clean(envelope.get("nonce"), "nonce", 160)
    try:
        timestamp = int(envelope.get("timestamp"))
    except (TypeError, ValueError):
        raise ValueError("Connector timestamp 不正确") from None
    if abs(int(time.time()) - timestamp) > MAX_SKEW_SECONDS:
        raise ValueError("Connector 请求已过期或本机时间偏差过大")
    data = envelope.get("data") if isinstance(envelope.get("data"), dict) else {}
    supplied = _clean(envelope.get("signature"), "signature", 128)
    expected = hmac.new(_secret(secret), _canonical(connector, timestamp, nonce, action, data), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(supplied.lower(), expected.lower()):
        raise ValueError("Connector 签名验证失败")
    if consume_nonce:
        _consume_nonce(connector, nonce, timestamp)
    return {"connector_id": connector, "timestamp": timestamp, "nonce": nonce, "action": action, "data": data}


def _audit(kind: str, connector_id: str, detail=None) -> None:
    items = _load_list(AUDIT_FILE)
    items.append({
        "id": f"CAUDIT-{secrets.token_hex(5).upper()}",
        "at": now_iso(),
        "kind": str(kind or "event")[:80],
        "connector_id": str(connector_id or "")[:120],
        "detail": detail if isinstance(detail, dict) else {},
    })
    _save_list(AUDIT_FILE, items, MAX_AUDIT)


def recent_audit(limit: int = 50) -> list[dict]:
    size = min(200, max(1, int(limit or 50)))
    return _load_list(AUDIT_FILE)[-size:][::-1]


def _find_pairing(connector_id: str, challenge_id: str) -> dict | None:
    for item in reversed(_load_list(PAIRINGS_FILE)):
        if item.get("connector_id") == connector_id and item.get("challenge_id") == challenge_id:
            return item
    return None


def _begin_pairing(connector_id: str, data: dict) -> dict:
    proof_source = str(data.get("proof_source") or "signed_relay").strip()
    if proof_source != "signed_relay":
        raise ValueError("当前外部适配层只接受 signed_relay 证明来源")
    challenge_id = f"CHALLENGE-{datetime.now().astimezone():%Y%m%d}-{secrets.token_hex(5).upper()}"
    command_id = f"CMD-VERIFY-{secrets.token_hex(5).upper()}"
    created = int(time.time())
    pairing = {
        "connector_id": connector_id,
        "proof_source": proof_source,
        "challenge_id": challenge_id,
        "command_id": command_id,
        "created_unix": created,
        "expires_unix": created + PAIRING_TTL_SECONDS,
        "created_at": now_iso(),
        "completed_at": None,
        "receipt_id": None,
        "permissions": control._clean_permissions(data.get("permissions") or control.DEFAULT_PERMISSIONS),
    }
    items = _load_list(PAIRINGS_FILE)
    items.append(pairing)
    _save_list(PAIRINGS_FILE, items, 200)
    # Authorization/pairing exists, but no round-trip proof exists yet.
    raw = control._default_state()
    raw.update({
        "connection_state": control.CONNECTED_UNVERIFIED,
        "status": "authorized",
        "verified": False,
        "connector_id": connector_id,
        "proof_source": proof_source,
        "challenge_id": challenge_id,
        "last_command_id": command_id,
        "last_command_at": now_iso(),
        "last_heartbeat": now_iso(),
        "message": "安全配对挑战已创建，等待外部 ChatGPT Connector 返回签名 Receipt。",
    })
    write_json(control.STATE_FILE, raw)
    _audit("pairing_started", connector_id, {"challenge_id": challenge_id, "command_id": command_id})
    return {
        "challenge_id": challenge_id,
        "command_id": command_id,
        "expires_unix": pairing["expires_unix"],
        "proof_source": proof_source,
    }


def _complete_pairing(connector_id: str, data: dict) -> dict:
    challenge_id = _clean(data.get("challenge_id"), "challenge_id", 160)
    command_id = _clean(data.get("command_id"), "command_id", 160)
    receipt_id = _clean(data.get("receipt_id"), "receipt_id", 160)
    pairing = _find_pairing(connector_id, challenge_id)
    if not pairing:
        raise ValueError("未找到匹配的 Connector 配对挑战")
    if pairing.get("command_id") != command_id:
        raise ValueError("Connector 配对 Command 不匹配")
    if int(pairing.get("expires_unix") or 0) < int(time.time()):
        raise ValueError("Connector 配对挑战已过期")
    if pairing.get("completed_at"):
        state = control.control_status()
        if state.get("verified") and pairing.get("receipt_id") == receipt_id:
            return state
        raise ValueError("Connector 配对挑战已完成，Receipt 不匹配")

    state = control.record_verified_roundtrip(
        connector_id=connector_id,
        proof_source="signed_relay",
        challenge_id=challenge_id,
        command_id=command_id,
        receipt_id=receipt_id,
        permissions=pairing.get("permissions") or control.DEFAULT_PERMISSIONS,
    )
    items = _load_list(PAIRINGS_FILE)
    for item in items:
        if item.get("connector_id") == connector_id and item.get("challenge_id") == challenge_id:
            item["completed_at"] = now_iso()
            item["receipt_id"] = receipt_id
    _save_list(PAIRINGS_FILE, items, 200)
    _audit("pairing_verified", connector_id, {"challenge_id": challenge_id, "receipt_id": receipt_id})
    return state


def _require_verified(connector_id: str, permission: str | None = None) -> dict:
    state = control.control_status()
    if not state.get("verified") or state.get("connector_id") != connector_id:
        raise ValueError("ChatGPT Connector 尚未完成真实双向验证")
    if permission and permission not in (state.get("permissions") or []):
        raise ValueError(f"Connector 未获得权限：{permission}")
    return state


def _existing_receipt(command_id: str) -> dict | None:
    for item in control.recent_receipts(200):
        if item.get("command_id") == command_id and item.get("kind") == "execution_receipt":
            return item
    return None


def _pending_commands(connector_id: str, limit: int = 20) -> list[dict]:
    _require_verified(connector_id, "read_missions")
    result = []
    for item in control.recent_commands(200):
        if item.get("connector_id") != connector_id:
            continue
        if item.get("kind") != "owner_objective":
            continue
        if item.get("status") not in {"queued_for_verified_connector", "accepted"}:
            continue
        result.append(item)
        if len(result) >= min(50, max(1, int(limit or 20))):
            break
    return result


def _read_state(connector_id: str) -> dict:
    _require_verified(connector_id, "read_execution_status")
    from core.autonomous_ops import snapshot
    from core.r7_engine import agent_registry
    ops = snapshot(sync=False)
    agents = agent_registry().get("items") or []
    return {
        "control": control.control_status(),
        "active_mission": ops.get("active_mission"),
        "world_state": ops.get("world_state") or {},
        "timeline": (ops.get("timeline") or [])[:20],
        "ai_employee_roles": agents,
        "ai_employee_role_count": len(agents),
        "truth_rule": ops.get("truth_rule"),
    }


def _permission_for_decision(decision: dict) -> str:
    action = str((decision or {}).get("action") or "").strip()
    if action == "create_mission":
        return "create_mission"
    if action == "stop":
        return "pause_non_financial_mission"
    if action == "continue":
        return "start_content_production"
    raise ValueError("mission_decision 只允许 create_mission、continue 或 stop")


def _apply_decision(connector_id: str, data: dict) -> dict:
    command_id = _clean(data.get("command_id"), "command_id", 160)
    decision = data.get("decision") if isinstance(data.get("decision"), dict) else {}
    _require_verified(connector_id, _permission_for_decision(decision))

    existing = _existing_receipt(command_id)
    if existing:
        _audit("command_retry_idempotent", connector_id, {"command_id": command_id, "receipt_id": existing.get("receipt_id")})
        return {"idempotent": True, "receipt": existing, "state": _read_state(connector_id)}

    command = next((item for item in control.recent_commands(200) if item.get("command_id") == command_id), None)
    if not command or command.get("kind") != "owner_objective":
        raise ValueError("未找到可执行的老板经营 Command")
    if command.get("connector_id") != connector_id:
        raise ValueError("Command 不属于当前 Connector")

    control.acknowledge_command(command_id)
    from core.autonomous_mission_decisions import apply_chatgpt_mission_decision
    from core.autonomous_ops import snapshot
    from core.r7_engine import agent_registry

    decision_result = apply_chatgpt_mission_decision(decision)
    ops = snapshot(sync=False)
    mission_id = decision_result.get("mission_id") or (ops.get("active_mission") or {}).get("mission_id")
    roles = agent_registry().get("items") or []
    receipt_result = {
        "objective": command.get("objective"),
        "decision": decision_result,
        "mission": ops.get("active_mission"),
        "world_state": ops.get("world_state") or {},
        "ai_employee_roles_available": len(roles),
        "employee_truth": "8个AI员工为统一ChatGPT总脑下的职责角色；这里只证明角色已注册，不伪造全部任务已执行。",
        "external_result_truth": "平台发布、SEO收录、咨询和订单必须等待各自真实回执/数据，当前 Receipt 不代表这些外部结果已经发生。",
    }
    receipt = control.record_command_receipt(command_id, receipt_result, mission_id=mission_id)
    _audit("command_completed", connector_id, {"command_id": command_id, "receipt_id": receipt.get("receipt_id"), "mission_id": mission_id})
    return {"idempotent": False, "receipt": receipt, "state": _read_state(connector_id)}


def process_envelope(envelope: dict, *, secret: str | None = None) -> dict:
    verified = verify_envelope(envelope, secret=secret, consume_nonce=True)
    connector_id = verified["connector_id"]
    action = verified["action"]
    data = verified["data"]

    if action == "begin_pairing":
        result = _begin_pairing(connector_id, data)
    elif action == "complete_pairing":
        result = _complete_pairing(connector_id, data)
    elif action == "heartbeat":
        _require_verified(connector_id)
        result = control.set_runtime_state(control.CONNECTED_VERIFIED, issue=None)
        _audit("heartbeat", connector_id, {"state": result.get("connection_state")})
    elif action == "pull_commands":
        result = {"items": _pending_commands(connector_id, data.get("limit") or 20)}
        _audit("commands_pulled", connector_id, {"count": len(result["items"])})
    elif action == "read_state":
        result = _read_state(connector_id)
        _audit("state_read", connector_id, {"mission_id": (result.get("active_mission") or {}).get("mission_id")})
    elif action == "apply_decision":
        result = _apply_decision(connector_id, data)
    else:
        raise ValueError("不支持的 Connector action")

    return {
        "ok": True,
        "action": action,
        "connector_id": connector_id,
        "processed_at": now_iso(),
        "result": result,
    }
