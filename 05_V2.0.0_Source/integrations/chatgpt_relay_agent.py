"""Outbound-only transport for the Kazuizhi ChatGPT Control Connector.

The desktop runtime remains bound to localhost. Instead of exposing port 8876 to
the Internet, this worker may poll a trusted HTTPS relay when one is explicitly
provisioned. The relay can carry signed Connector envelopes from a supported
ChatGPT App/Plugin/Connector transport and receive signed processing results.

This module does NOT make ChatGPT Plus an API and does not mark the connector as
verified by itself. Verification still requires the signed challenge -> receipt
round trip enforced by chatgpt_connector_adapter.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
import time
import urllib.error
import urllib.request
from urllib.parse import urlsplit

from core.storage import now_iso, read_json, write_json
from integrations import chatgpt_control as control
from integrations import chatgpt_connector_adapter as adapter

RELAY_URL_ENV = "KAZUIZHI_CHATGPT_RELAY_URL"
CONNECTOR_ID_ENV = "KAZUIZHI_CHATGPT_CONNECTOR_ID"
POLL_SECONDS_ENV = "KAZUIZHI_CHATGPT_RELAY_POLL_SECONDS"
RESPONSE_NONCES_FILE = "r8_10/chatgpt_relay_response_nonces.json"
MAX_SKEW_SECONDS = 300
DEFAULT_POLL_SECONDS = 15
MIN_POLL_SECONDS = 5
MAX_POLL_SECONDS = 300
MAX_RESPONSE_BYTES = 256 * 1024
PROTOCOL = "kz-chatgpt-relay-v1"


def _clean(value, label: str, limit: int = 500, required: bool = True) -> str:
    text = str(value or "").strip()
    if required and not text:
        raise ValueError(f"{label}不能为空")
    if len(text) > limit:
        raise ValueError(f"{label}长度不能超过{limit}个字符")
    return text


def _relay_url(explicit: str | None = None) -> str:
    url = _clean(explicit or os.environ.get(RELAY_URL_ENV), "ChatGPT Relay URL", 1000)
    parsed = urlsplit(url)
    host = (parsed.hostname or "").lower()
    local = host in {"127.0.0.1", "localhost", "::1"}
    if parsed.scheme != "https" and not (local and parsed.scheme == "http"):
        raise ValueError("ChatGPT Relay 必须使用 HTTPS；只有本机测试允许 HTTP")
    if not parsed.netloc:
        raise ValueError("ChatGPT Relay URL 不完整")
    return url.rstrip("/")


def _connector_id(explicit: str | None = None) -> str:
    return _clean(explicit or os.environ.get(CONNECTOR_ID_ENV), "connector_id", 120)


def poll_seconds() -> int:
    try:
        value = int(os.environ.get(POLL_SECONDS_ENV) or DEFAULT_POLL_SECONDS)
    except (TypeError, ValueError):
        value = DEFAULT_POLL_SECONDS
    return max(MIN_POLL_SECONDS, min(MAX_POLL_SECONDS, value))


def relay_config_status() -> dict:
    raw_url = str(os.environ.get(RELAY_URL_ENV) or "").strip()
    raw_id = str(os.environ.get(CONNECTOR_ID_ENV) or "").strip()
    secret_ok = len(str(os.environ.get(adapter.SECRET_ENV) or "").strip()) >= 32
    url_ok = False
    reason = None
    if raw_url:
        try:
            _relay_url(raw_url)
            url_ok = True
        except ValueError as error:
            reason = str(error)
    configured = bool(url_ok and raw_id and secret_ok)
    return {
        "configured": configured,
        "relay_url_configured": bool(raw_url),
        "relay_url_valid": url_ok,
        "connector_id_configured": bool(raw_id),
        "credential_configured": secret_ok,
        "poll_seconds": poll_seconds(),
        "reason": reason or (None if configured else "尚未完成受信任 Relay 的安全配对配置"),
        "transport": "outbound_https_poll",
        "inbound_port_exposed": False,
    }


def _json_bytes(value) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sign_message(payload: dict, *, secret: str | None = None) -> dict:
    body = dict(payload)
    body.pop("signature", None)
    signature = hmac.new(adapter._secret(secret), _json_bytes(body), hashlib.sha256).hexdigest()
    body["signature"] = signature
    return body


def _verify_message(payload: dict, *, connector_id: str, secret: str | None = None) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("Relay 响应格式不正确")
    supplied = _clean(payload.get("signature"), "Relay signature", 128)
    unsigned = dict(payload)
    unsigned.pop("signature", None)
    expected = hmac.new(adapter._secret(secret), _json_bytes(unsigned), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(supplied.lower(), expected.lower()):
        raise ValueError("Relay 响应签名验证失败")
    if payload.get("protocol") != PROTOCOL:
        raise ValueError("Relay 协议版本不匹配")
    if str(payload.get("connector_id") or "") != connector_id:
        raise ValueError("Relay connector_id 不匹配")
    try:
        stamp = int(payload.get("timestamp"))
    except (TypeError, ValueError):
        raise ValueError("Relay timestamp 不正确") from None
    if abs(int(time.time()) - stamp) > MAX_SKEW_SECONDS:
        raise ValueError("Relay 响应已过期或时间偏差过大")
    nonce = _clean(payload.get("nonce"), "Relay nonce", 160)
    _consume_response_nonce(connector_id, nonce, stamp)
    return payload


def _consume_response_nonce(connector_id: str, nonce: str, timestamp: int) -> None:
    values = read_json(RESPONSE_NONCES_FILE, [])
    items = [x for x in values if isinstance(x, dict)] if isinstance(values, list) else []
    cutoff = int(time.time()) - (MAX_SKEW_SECONDS * 2)
    items = [x for x in items if int(x.get("timestamp") or 0) >= cutoff]
    if any(x.get("connector_id") == connector_id and x.get("nonce") == nonce for x in items):
        raise ValueError("Relay 响应 nonce 已使用，拒绝重放")
    items.append({"connector_id": connector_id, "nonce": nonce, "timestamp": timestamp, "used_at": now_iso()})
    write_json(RESPONSE_NONCES_FILE, items[-2000:])


def _post_json(url: str, payload: dict, *, timeout: int = 12, opener=None) -> dict:
    data = _json_bytes(payload)
    request = urllib.request.Request(
        url,
        data=data,
        method="POST",
        headers={
            "Content-Type": "application/json; charset=utf-8",
            "Accept": "application/json",
            "User-Agent": "Kazuizhi-ChatGPT-Relay-Agent/1",
        },
    )
    open_fn = opener or urllib.request.urlopen
    response = open_fn(request, timeout=timeout)
    try:
        raw = response.read(MAX_RESPONSE_BYTES + 1)
    finally:
        close = getattr(response, "close", None)
        if callable(close):
            close()
    if len(raw) > MAX_RESPONSE_BYTES:
        raise ValueError("Relay 响应过大")
    try:
        result = json.loads(raw.decode("utf-8") or "{}")
    except (UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ValueError("Relay 返回了无效 JSON") from error
    if not isinstance(result, dict):
        raise ValueError("Relay 返回格式不正确")
    return result


def _base_message(connector_id: str, kind: str, data: dict) -> dict:
    return {
        "protocol": PROTOCOL,
        "kind": kind,
        "connector_id": connector_id,
        "timestamp": int(time.time()),
        "nonce": secrets.token_urlsafe(18),
        "data": data,
    }


def _state_summary() -> dict:
    state = control.control_status()
    return {
        "connection_state": state.get("connection_state"),
        "verified": bool(state.get("verified")),
        "last_command_id": state.get("last_command_id"),
        "last_receipt_id": state.get("last_receipt_id"),
        "last_heartbeat": state.get("last_heartbeat"),
    }


def poll_once(*, relay_url: str | None = None, connector_id: str | None = None,
              secret: str | None = None, opener=None) -> dict:
    """Poll one trusted relay cycle and process zero or more signed envelopes."""
    url = _relay_url(relay_url)
    connector = _connector_id(connector_id)
    # Resolve the secret up front so a missing credential cannot be mistaken for
    # a network failure or cause any connector state elevation.
    adapter._secret(secret)

    request_payload = _sign_message(
        _base_message(connector, "poll", {"state": _state_summary()}),
        secret=secret,
    )
    try:
        response = _post_json(f"{url}/v1/poll", request_payload, opener=opener)
        verified_response = _verify_message(response, connector_id=connector, secret=secret)
        envelopes = verified_response.get("data", {}).get("envelopes", [])
        if not isinstance(envelopes, list):
            raise ValueError("Relay envelopes 格式不正确")

        processed = []
        for envelope in envelopes[:20]:
            result = adapter.process_envelope(envelope, secret=secret)
            processed.append(result)

        result_message = _sign_message(
            _base_message(
                connector,
                "result",
                {
                    "poll_nonce": verified_response.get("nonce"),
                    "processed": processed,
                    "state": _state_summary(),
                },
            ),
            secret=secret,
        )
        # Always return a result/heartbeat to close the relay cycle, even when
        # there were no commands. A server response is not treated as a business
        # Receipt; only adapter-validated command results are.
        ack = _post_json(f"{url}/v1/result", result_message, opener=opener)
        ack_verified = _verify_message(ack, connector_id=connector, secret=secret)
        if ack_verified.get("kind") != "result_ack":
            raise ValueError("Relay result acknowledgement 类型不正确")

        state = control.control_status()
        if state.get("verified"):
            control.set_runtime_state(control.CONNECTED_VERIFIED, issue=None)
        return {
            "ok": True,
            "processed": len(processed),
            "connection_state": control.control_status().get("connection_state"),
            "relay": "reachable",
        }
    except urllib.error.HTTPError as error:
        if error.code in {401, 403}:
            current = control.control_status()
            if current.get("verified"):
                control.set_runtime_state(control.HUMAN_ACTION_REQUIRED, issue="ChatGPT Relay 鉴权失败，需要重新授权或配对。")
        raise
    except (urllib.error.URLError, TimeoutError, OSError) as error:
        current = control.control_status()
        if current.get("verified"):
            control.set_runtime_state(control.DEGRADED, issue="ChatGPT Relay 暂时不可达，本地自治继续运行已批准任务。")
        raise RuntimeError(f"ChatGPT Relay 暂时不可达：{error}") from error


def safe_poll_once() -> dict:
    status = relay_config_status()
    if not status.get("configured"):
        return {"ok": False, "skipped": True, "reason": status.get("reason"), "config": status}
    try:
        return poll_once()
    except (ValueError, RuntimeError, urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError) as error:
        return {"ok": False, "skipped": False, "reason": str(error), "connection_state": control.control_status().get("connection_state")}
