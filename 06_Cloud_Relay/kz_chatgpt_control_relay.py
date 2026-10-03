"""Deployable cloud relay for the Kazuizhi ChatGPT Control Connector.

The Windows client never exposes its local dashboard port. It makes outbound
HTTPS requests to this relay. A supported ChatGPT-side App/Connector talks to a
separate controller surface. The relay bridges the two trust zones without
pretending that a ChatGPT Plus subscription is an API credential.

Security model
--------------
* agent_secret authenticates the Windows outbound Relay Agent and signs local
  Connector envelopes. It is never returned by any endpoint.
* controller_secret authenticates the ChatGPT-side controller. It is separate
  from agent_secret so a controller cannot forge desktop transport messages.
* timestamp + nonce replay protection is enforced independently for both trust
  zones.
* queued controller actions are durable and idempotent by idempotency_key.
* financial actions are not part of the adapter action allow-list.
* the service stores receipts/results only; it never invents platform publish,
  SEO indexing, inquiry or order outcomes.

Production deployment must terminate HTTPS in front of this process (reverse
proxy/serverless ingress/load balancer). The desktop agent refuses public HTTP.
"""
from __future__ import annotations

import argparse
import hashlib
import hmac
import json
import os
import secrets
import threading
import time
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

RELAY_PROTOCOL = "kz-chatgpt-relay-v1"
CONTROLLER_PROTOCOL = "kz-chatgpt-controller-v1"
ALLOWED_ACTIONS = {
    "begin_pairing",
    "complete_pairing",
    "heartbeat",
    "pull_commands",
    "read_state",
    "apply_decision",
}
MAX_SKEW_SECONDS = 300
LEASE_SECONDS = 60
MAX_BODY_BYTES = 256 * 1024
MAX_JOBS = 5000
MAX_NONCES = 5000
MAX_AUDIT = 5000

AGENT_SECRET_ENV = "KAZUIZHI_CHATGPT_RELAY_SECRET"
CONTROLLER_SECRET_ENV = "KAZUIZHI_CHATGPT_CONTROLLER_SECRET"
CONNECTOR_ID_ENV = "KAZUIZHI_CHATGPT_CONNECTOR_ID"
STORE_FILE_ENV = "KAZUIZHI_CHATGPT_RELAY_STORE"


def _clean(value: Any, label: str, limit: int = 500, required: bool = True) -> str:
    text = str(value or "").strip()
    if required and not text:
        raise ValueError(f"{label}不能为空")
    if len(text) > limit:
        raise ValueError(f"{label}长度不能超过{limit}个字符")
    return text


def _secret(value: str, label: str) -> bytes:
    text = str(value or "").strip()
    if len(text) < 32:
        raise ValueError(f"{label}至少需要32个字符")
    return text.encode("utf-8")


def _json_bytes(value: Any) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")


def _sign_full(payload: dict, secret: bytes) -> dict:
    body = dict(payload)
    body.pop("signature", None)
    body["signature"] = hmac.new(secret, _json_bytes(body), hashlib.sha256).hexdigest()
    return body


def _verify_full(payload: dict, secret: bytes) -> None:
    if not isinstance(payload, dict):
        raise ValueError("消息格式不正确")
    supplied = _clean(payload.get("signature"), "signature", 128)
    body = dict(payload)
    body.pop("signature", None)
    expected = hmac.new(secret, _json_bytes(body), hashlib.sha256).hexdigest()
    if not hmac.compare_digest(supplied.lower(), expected.lower()):
        raise ValueError("签名验证失败")


def _adapter_canonical(connector_id: str, timestamp: int, nonce: str, action: str, data: dict) -> bytes:
    body = json.dumps(data if isinstance(data, dict) else {}, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    digest = hashlib.sha256(body.encode("utf-8")).hexdigest()
    return f"{connector_id}\n{timestamp}\n{nonce}\n{action}\n{digest}".encode("utf-8")


def sign_adapter_envelope(*, connector_id: str, action: str, data: dict, agent_secret: bytes,
                          timestamp: int | None = None, nonce: str | None = None) -> dict:
    if action not in ALLOWED_ACTIONS:
        raise ValueError("不支持的 Connector action")
    stamp = int(time.time() if timestamp is None else timestamp)
    nonce_value = _clean(nonce or secrets.token_urlsafe(18), "nonce", 160)
    body = data if isinstance(data, dict) else {}
    signature = hmac.new(
        agent_secret,
        _adapter_canonical(connector_id, stamp, nonce_value, action, body),
        hashlib.sha256,
    ).hexdigest()
    return {
        "connector_id": connector_id,
        "timestamp": stamp,
        "nonce": nonce_value,
        "action": action,
        "data": body,
        "signature": signature,
    }


def sign_controller_message(*, connector_id: str, kind: str, data: dict, controller_secret: str,
                            timestamp: int | None = None, nonce: str | None = None) -> dict:
    secret = _secret(controller_secret, "controller_secret")
    payload = {
        "protocol": CONTROLLER_PROTOCOL,
        "kind": _clean(kind, "kind", 80),
        "connector_id": _clean(connector_id, "connector_id", 120),
        "timestamp": int(time.time() if timestamp is None else timestamp),
        "nonce": _clean(nonce or secrets.token_urlsafe(18), "nonce", 160),
        "data": data if isinstance(data, dict) else {},
    }
    return _sign_full(payload, secret)


def _utc_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec="seconds")


class JsonStore:
    def __init__(self, path: str | Path):
        self.path = Path(path)
        self.lock = threading.RLock()

    def _default(self) -> dict:
        return {
            "version": 1,
            "jobs": [],
            "leases": [],
            "agent_nonces": [],
            "controller_nonces": [],
            "audit": [],
            "last_agent_seen": None,
        }

    def load(self) -> dict:
        with self.lock:
            if not self.path.is_file():
                return self._default()
            try:
                value = json.loads(self.path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError):
                value = self._default()
            if not isinstance(value, dict):
                value = self._default()
            default = self._default()
            for key, fallback in default.items():
                value.setdefault(key, fallback)
            return value

    def save(self, value: dict) -> None:
        with self.lock:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            temp = self.path.with_suffix(self.path.suffix + ".tmp")
            temp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
            temp.replace(self.path)


class RelayCore:
    def __init__(self, *, agent_secret: str, controller_secret: str, connector_id: str,
                 store_path: str | Path):
        self.agent_secret = _secret(agent_secret, "agent_secret")
        self.controller_secret = _secret(controller_secret, "controller_secret")
        self.connector_id = _clean(connector_id, "connector_id", 120)
        self.store = JsonStore(store_path)
        self.lock = threading.RLock()

    def _consume_nonce(self, bucket: str, connector_id: str, nonce: str, stamp: int) -> None:
        now = int(time.time())
        if abs(now - stamp) > MAX_SKEW_SECONDS:
            raise ValueError("消息已过期或系统时间偏差过大")
        with self.lock:
            state = self.store.load()
            values = state.get(bucket) if isinstance(state.get(bucket), list) else []
            cutoff = now - (MAX_SKEW_SECONDS * 2)
            values = [x for x in values if isinstance(x, dict) and int(x.get("timestamp") or 0) >= cutoff]
            if any(x.get("connector_id") == connector_id and x.get("nonce") == nonce for x in values):
                raise ValueError("nonce 已使用，拒绝重放")
            values.append({"connector_id": connector_id, "nonce": nonce, "timestamp": stamp, "used_at": _utc_iso()})
            state[bucket] = values[-MAX_NONCES:]
            self.store.save(state)

    def _verify_agent(self, message: dict) -> dict:
        _verify_full(message, self.agent_secret)
        if message.get("protocol") != RELAY_PROTOCOL:
            raise ValueError("Relay 协议版本不匹配")
        connector = _clean(message.get("connector_id"), "connector_id", 120)
        if connector != self.connector_id:
            raise ValueError("connector_id 不匹配")
        stamp = int(message.get("timestamp"))
        nonce = _clean(message.get("nonce"), "nonce", 160)
        self._consume_nonce("agent_nonces", connector, nonce, stamp)
        return message

    def _verify_controller(self, message: dict) -> dict:
        _verify_full(message, self.controller_secret)
        if message.get("protocol") != CONTROLLER_PROTOCOL:
            raise ValueError("Controller 协议版本不匹配")
        connector = _clean(message.get("connector_id"), "connector_id", 120)
        if connector != self.connector_id:
            raise ValueError("connector_id 不匹配")
        stamp = int(message.get("timestamp"))
        nonce = _clean(message.get("nonce"), "nonce", 160)
        self._consume_nonce("controller_nonces", connector, nonce, stamp)
        return message

    def _agent_response(self, kind: str, data: dict) -> dict:
        payload = {
            "protocol": RELAY_PROTOCOL,
            "kind": kind,
            "connector_id": self.connector_id,
            "timestamp": int(time.time()),
            "nonce": secrets.token_urlsafe(18),
            "data": data,
        }
        return _sign_full(payload, self.agent_secret)

    def _controller_response(self, kind: str, data: dict) -> dict:
        payload = {
            "protocol": CONTROLLER_PROTOCOL,
            "kind": kind,
            "connector_id": self.connector_id,
            "timestamp": int(time.time()),
            "nonce": secrets.token_urlsafe(18),
            "data": data,
        }
        return _sign_full(payload, self.controller_secret)

    def _audit(self, state: dict, kind: str, detail: dict | None = None) -> None:
        items = state.get("audit") if isinstance(state.get("audit"), list) else []
        items.append({"at": _utc_iso(), "kind": kind, "detail": detail or {}})
        state["audit"] = items[-MAX_AUDIT:]

    def controller_enqueue(self, message: dict) -> dict:
        verified = self._verify_controller(message)
        if verified.get("kind") != "enqueue":
            raise ValueError("Controller kind 必须是 enqueue")
        data = verified.get("data") if isinstance(verified.get("data"), dict) else {}
        action = _clean(data.get("action"), "action", 80)
        if action not in ALLOWED_ACTIONS:
            raise ValueError("不支持的 Connector action")
        action_data = data.get("data") if isinstance(data.get("data"), dict) else {}
        idem = _clean(data.get("idempotency_key") or secrets.token_urlsafe(18), "idempotency_key", 180)
        with self.lock:
            state = self.store.load()
            jobs = state.get("jobs") if isinstance(state.get("jobs"), list) else []
            existing = next((x for x in jobs if x.get("idempotency_key") == idem), None)
            if existing:
                return self._controller_response("enqueue_ack", {"job": existing, "idempotent": True})
            job = {
                "job_id": f"RJOB-{secrets.token_hex(6).upper()}",
                "idempotency_key": idem,
                "action": action,
                "data": action_data,
                "status": "queued",
                "created_at": _utc_iso(),
                "delivered_at": None,
                "completed_at": None,
                "attempts": 0,
                "result": None,
                "last_error": None,
            }
            jobs.append(job)
            state["jobs"] = jobs[-MAX_JOBS:]
            self._audit(state, "controller_enqueued", {"job_id": job["job_id"], "action": action})
            self.store.save(state)
        return self._controller_response("enqueue_ack", {"job": job, "idempotent": False})

    def controller_status(self, message: dict) -> dict:
        verified = self._verify_controller(message)
        if verified.get("kind") != "status":
            raise ValueError("Controller kind 必须是 status")
        data = verified.get("data") if isinstance(verified.get("data"), dict) else {}
        limit = max(1, min(100, int(data.get("limit") or 20)))
        job_id = str(data.get("job_id") or "").strip()
        with self.lock:
            state = self.store.load()
            jobs = state.get("jobs") if isinstance(state.get("jobs"), list) else []
            if job_id:
                jobs = [x for x in jobs if x.get("job_id") == job_id]
            else:
                jobs = jobs[-limit:]
            return self._controller_response("status_response", {
                "jobs": jobs,
                "last_agent_seen": state.get("last_agent_seen"),
                "truth_rule": "Relay结果只是受签名的控制/执行回执；平台发布、SEO收录、咨询、订单仍必须由各自真实来源证明。",
            })

    def agent_poll(self, message: dict) -> dict:
        verified = self._verify_agent(message)
        if verified.get("kind") != "poll":
            raise ValueError("Relay Agent kind 必须是 poll")
        now = time.time()
        with self.lock:
            state = self.store.load()
            jobs = state.get("jobs") if isinstance(state.get("jobs"), list) else []
            selected = []
            for job in jobs:
                if job.get("status") == "completed":
                    continue
                delivered = float(job.get("delivered_unix") or 0)
                if job.get("status") == "delivered" and now - delivered < LEASE_SECONDS:
                    continue
                selected.append(job)
                if len(selected) >= 20:
                    break
            response_nonce = secrets.token_urlsafe(18)
            envelopes = []
            job_ids = []
            for job in selected:
                envelope_data = dict(job.get("data") or {})
                envelopes.append(sign_adapter_envelope(
                    connector_id=self.connector_id,
                    action=job["action"],
                    data=envelope_data,
                    agent_secret=self.agent_secret,
                ))
                job["status"] = "delivered"
                job["delivered_at"] = _utc_iso()
                job["delivered_unix"] = now
                job["attempts"] = int(job.get("attempts") or 0) + 1
                job_ids.append(job["job_id"])
            leases = state.get("leases") if isinstance(state.get("leases"), list) else []
            leases.append({"poll_nonce": response_nonce, "job_ids": job_ids, "created_unix": now, "created_at": _utc_iso()})
            cutoff = now - 3600
            state["leases"] = [x for x in leases if float(x.get("created_unix") or 0) >= cutoff][-1000:]
            state["last_agent_seen"] = _utc_iso()
            self._audit(state, "agent_poll", {"count": len(envelopes)})
            self.store.save(state)
        response = {
            "protocol": RELAY_PROTOCOL,
            "kind": "poll_response",
            "connector_id": self.connector_id,
            "timestamp": int(time.time()),
            "nonce": response_nonce,
            "data": {"envelopes": envelopes},
        }
        return _sign_full(response, self.agent_secret)

    def agent_result(self, message: dict) -> dict:
        verified = self._verify_agent(message)
        if verified.get("kind") != "result":
            raise ValueError("Relay Agent kind 必须是 result")
        data = verified.get("data") if isinstance(verified.get("data"), dict) else {}
        poll_nonce = _clean(data.get("poll_nonce"), "poll_nonce", 160)
        processed = data.get("processed") if isinstance(data.get("processed"), list) else []
        with self.lock:
            state = self.store.load()
            lease = next((x for x in reversed(state.get("leases") or []) if x.get("poll_nonce") == poll_nonce), None)
            if not lease:
                raise ValueError("未找到匹配的 poll lease")
            job_ids = lease.get("job_ids") if isinstance(lease.get("job_ids"), list) else []
            if len(processed) != len(job_ids):
                raise ValueError("Relay processed 数量与投递任务不一致")
            jobs = state.get("jobs") if isinstance(state.get("jobs"), list) else []
            for job_id, result in zip(job_ids, processed):
                job = next((x for x in jobs if x.get("job_id") == job_id), None)
                if not job:
                    raise ValueError("Relay job 已不存在")
                job["status"] = "completed"
                job["completed_at"] = _utc_iso()
                job["result"] = result if isinstance(result, dict) else {"value": result}
                job["last_error"] = None
            state["last_agent_seen"] = _utc_iso()
            self._audit(state, "agent_result", {"count": len(processed), "poll_nonce": poll_nonce})
            self.store.save(state)
        return self._agent_response("result_ack", {"accepted": True, "count": len(processed)})

    def health(self) -> dict:
        state = self.store.load()
        jobs = state.get("jobs") if isinstance(state.get("jobs"), list) else []
        return {
            "ok": True,
            "service": "kazuizhi-chatgpt-control-relay",
            "protocol": RELAY_PROTOCOL,
            "connector_id": self.connector_id,
            "last_agent_seen": state.get("last_agent_seen"),
            "queued": len([x for x in jobs if x.get("status") == "queued"]),
            "delivered": len([x for x in jobs if x.get("status") == "delivered"]),
            "completed": len([x for x in jobs if x.get("status") == "completed"]),
            "secrets_exposed": False,
        }


def make_handler(core: RelayCore):
    class Handler(BaseHTTPRequestHandler):
        server_version = "KazuizhiChatGPTRelay/1"

        def _json(self, code: int, value: dict) -> None:
            raw = json.dumps(value, ensure_ascii=False).encode("utf-8")
            self.send_response(code)
            self.send_header("Content-Type", "application/json; charset=utf-8")
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(raw)

        def _read(self) -> dict:
            length = int(self.headers.get("Content-Length") or 0)
            if length <= 0 or length > MAX_BODY_BYTES:
                raise ValueError("请求大小不正确")
            value = json.loads(self.rfile.read(length).decode("utf-8"))
            if not isinstance(value, dict):
                raise ValueError("请求必须是JSON对象")
            return value

        def do_GET(self):
            if self.path == "/healthz":
                self._json(200, core.health())
                return
            self._json(404, {"ok": False, "error": "not_found"})

        def do_POST(self):
            try:
                body = self._read()
                if self.path == "/v1/poll":
                    result = core.agent_poll(body)
                elif self.path == "/v1/result":
                    result = core.agent_result(body)
                elif self.path == "/v1/controller/enqueue":
                    result = core.controller_enqueue(body)
                elif self.path == "/v1/controller/status":
                    result = core.controller_status(body)
                else:
                    self._json(404, {"ok": False, "error": "not_found"})
                    return
                self._json(200, result)
            except (ValueError, TypeError, KeyError, json.JSONDecodeError) as error:
                self._json(403, {"ok": False, "error": str(error)})

        def log_message(self, fmt, *args):
            # Do not log request bodies or signatures/secrets.
            print(f"{self.address_string()} - {fmt % args}")

    return Handler


def build_core_from_env() -> RelayCore:
    agent_secret = os.environ.get(AGENT_SECRET_ENV) or ""
    controller_secret = os.environ.get(CONTROLLER_SECRET_ENV) or ""
    connector_id = os.environ.get(CONNECTOR_ID_ENV) or ""
    store_path = os.environ.get(STORE_FILE_ENV) or "./data/kazuizhi_chatgpt_relay.json"
    return RelayCore(
        agent_secret=agent_secret,
        controller_secret=controller_secret,
        connector_id=connector_id,
        store_path=store_path,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Kazuizhi ChatGPT Control Cloud Relay")
    parser.add_argument("--host", default=os.environ.get("HOST") or "127.0.0.1")
    parser.add_argument("--port", type=int, default=int(os.environ.get("PORT") or 8787))
    args = parser.parse_args()
    core = build_core_from_env()
    server = ThreadingHTTPServer((args.host, args.port), make_handler(core))
    print(f"Kazuizhi ChatGPT Control Relay listening on {args.host}:{args.port}")
    print("Production must place this service behind HTTPS/TLS termination.")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
