"""Private asynchronous owner-control bus for Kazuizhi R8-10.

Normal operations no longer require ChatGPT Site Tools to stay online. The
owner's normal ChatGPT session may write a Decision Pack to a dedicated PRIVATE
GitHub repository. This local agent polls that repository, validates the pack,
applies only a narrow non-financial Mission decision, and writes a truthful
Receipt back.

This transport is asynchronous and must never be reported as a live ChatGPT
connection. Site Tools remains an optional real-time helper. Work/Codex remain
engineering tools only.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import threading
from datetime import datetime
from urllib.error import HTTPError, URLError
from urllib.parse import quote
from urllib.request import Request, urlopen

from core.storage import now_iso, read_json, write_json

STATE_FILE = "r8_10/async_control_bus_state.json"
RECEIPTS_FILE = "r8_10/async_control_bus_receipts.json"
SCHEMA = "kz.decision-pack.v1"
TRANSPORT = "github_private_control_bus"
DEFAULT_BRANCH = "main"
DEFAULT_POLL_SECONDS = 60
MAX_RECEIPTS = 1000
MAX_COMMANDS_PER_SYNC = 20

SAFE_AUTONOMY_ACTIONS = {
    "content_production", "asset_routing", "title_adjustment", "schedule_adjustment",
    "seo_content", "geo_content", "technical_qc", "retry_failed_subjob",
    "data_collection", "business_monitoring",
}
FORBIDDEN_WORDS = {
    "refund", "payment", "withdrawal", "settlement", "recharge", "finance",
    "commission", "compensation", "subsidy", "approve_publish", "final_publish",
    "verify_account", "captcha", "face_verification", "delete_important_data",
}
ALLOWED_DECISIONS = {"create_mission", "continue", "stop"}

_AGENT_THREAD = None
_AGENT_STOP = threading.Event()


def _truthy(value) -> bool:
    return str(value or "").strip().lower() in {"1", "true", "yes", "on", "enabled"}


def _config() -> dict:
    repo = str(os.environ.get("KZ_CONTROL_BUS_REPO") or "").strip()
    branch = str(os.environ.get("KZ_CONTROL_BUS_BRANCH") or DEFAULT_BRANCH).strip() or DEFAULT_BRANCH
    token = str(os.environ.get("KZ_CONTROL_BUS_TOKEN") or "").strip()
    try:
        poll_seconds = max(30, min(900, int(os.environ.get("KZ_CONTROL_BUS_POLL_SECONDS") or DEFAULT_POLL_SECONDS)))
    except ValueError:
        poll_seconds = DEFAULT_POLL_SECONDS
    explicit = os.environ.get("KZ_CONTROL_BUS_ENABLED")
    enabled = _truthy(explicit) if explicit is not None else bool(repo and token)
    return {
        "repo": repo, "branch": branch, "token": token, "poll_seconds": poll_seconds,
        "configured": bool(repo and token), "enabled": bool(enabled and repo and token),
    }


def _clean(value, label: str, limit: int, required: bool = True) -> str:
    text = str(value or "").strip()
    if required and not text:
        raise ValueError(f"{label}不能为空")
    if len(text) > limit:
        raise ValueError(f"{label}长度不能超过{limit}个字符")
    return text


def _load_receipts() -> list[dict]:
    rows = read_json(RECEIPTS_FILE, [])
    return [x for x in rows if isinstance(x, dict)] if isinstance(rows, list) else []


def _save_receipt(item: dict) -> dict:
    rows = [x for x in _load_receipts() if x.get("command_id") != item.get("command_id")]
    rows.append(item)
    write_json(RECEIPTS_FILE, rows[-MAX_RECEIPTS:])
    return item


def recent_receipts(limit: int = 50) -> list[dict]:
    size = min(200, max(1, int(limit or 50)))
    return _load_receipts()[-size:][::-1]


def _receipt_for(command_id: str) -> dict | None:
    target = str(command_id or "").strip()
    return next((x for x in reversed(_load_receipts()) if x.get("command_id") == target), None)


def _payload_hash(payload: dict) -> str:
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def _parse_time(value) -> datetime:
    text = str(value or "").strip()
    if not text:
        raise ValueError("Decision Pack 时间不能为空")
    if text.endswith("Z"):
        text = text[:-1] + "+00:00"
    parsed = datetime.fromisoformat(text)
    return parsed if parsed.tzinfo is not None else parsed.astimezone()


def validate_decision_pack(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("Decision Pack 格式不正确")
    if payload.get("schema") != SCHEMA:
        raise ValueError("Decision Pack schema 不受支持")
    command_id = _clean(payload.get("command_id"), "command_id", 180)
    decision_pack_id = _clean(payload.get("decision_pack_id"), "decision_pack_id", 180)
    if not command_id.startswith("CMD-") or not decision_pack_id.startswith("DP-"):
        raise ValueError("Decision Pack ID 格式不正确")
    issued_at = _parse_time(payload.get("issued_at"))
    valid_until = _parse_time(payload.get("valid_until"))
    if valid_until <= issued_at:
        raise ValueError("Decision Pack 有效期不正确")
    decision = payload.get("decision")
    if not isinstance(decision, dict):
        raise ValueError("decision 必须是对象")
    action = _clean(decision.get("action"), "decision.action", 40)
    if action not in ALLOWED_DECISIONS:
        raise ValueError("只允许 create_mission、continue 或 stop")

    autonomy = payload.get("autonomy") if isinstance(payload.get("autonomy"), dict) else {}
    allowed = autonomy.get("allowed") if isinstance(autonomy.get("allowed"), list) else []
    normalized = []
    for value in allowed:
        item = str(value or "").strip()
        if not item:
            continue
        if item not in SAFE_AUTONOMY_ACTIONS:
            raise ValueError(f"Decision Pack 包含未授权自治动作：{item}")
        if item not in normalized:
            normalized.append(item)

    serialized = json.dumps(payload, ensure_ascii=False).lower()
    if any(word in serialized for word in FORBIDDEN_WORDS):
        raise ValueError("Decision Pack 包含资金、账号验证、最终发布或其他禁止能力")
    return {
        "command_id": command_id, "decision_pack_id": decision_pack_id,
        "issued_at": issued_at, "valid_until": valid_until, "decision": decision,
        "autonomy_allowed": normalized, "payload_hash": _payload_hash(payload),
    }


def _mission_payload(validated: dict) -> dict:
    decision = validated["decision"]
    action = decision["action"]
    reason = _clean(decision.get("reason") or "普通 ChatGPT 对老板目标形成的异步 Decision Pack", "decision.reason", 500)
    if action == "create_mission":
        return {
            "action": action,
            "region": _clean(decision.get("region"), "decision.region", 40),
            "service": _clean(decision.get("service"), "decision.service", 60),
            "title": _clean(decision.get("title"), "decision.title", 120),
            "evidence": _clean(decision.get("evidence"), "decision.evidence", 500),
            "goal": _clean(decision.get("goal") or "获得可追溯的真实咨询或订单", "decision.goal", 160),
            "reason": reason,
        }
    return {
        "action": action,
        "mission_id": _clean(decision.get("mission_id"), "decision.mission_id", 120),
        "reason": reason,
    }


def process_decision_pack(payload: dict, *, source_path: str = "local-test") -> dict:
    validated = validate_decision_pack(payload)
    existing = _receipt_for(validated["command_id"])
    if existing:
        if existing.get("payload_hash") != validated["payload_hash"]:
            raise ValueError("同一 command_id 的 Decision Pack 内容发生变化，拒绝重放/篡改")
        return {"idempotent": True, "receipt": existing}

    if validated["valid_until"] < datetime.now().astimezone():
        receipt = {
            "receipt_id": f"RECEIPT-BUS-{validated['command_id'][4:]}",
            "command_id": validated["command_id"], "decision_pack_id": validated["decision_pack_id"],
            "kind": "async_control_bus_receipt", "status": "expired", "transport": TRANSPORT,
            "source_path": source_path, "payload_hash": validated["payload_hash"], "created_at": now_iso(),
            "result": {"applied": False, "reason": "Decision Pack 已过有效期"},
            "truth_rule": "异步控制总线回执只证明本地是否接受并执行该决策，不代表平台发布、SEO收录、咨询或订单成功。",
        }
        _save_receipt(receipt)
        return {"idempotent": False, "receipt": receipt}

    from core.autonomous_mission_decisions import apply_chatgpt_mission_decision
    from core.autonomous_ops import snapshot

    result = apply_chatgpt_mission_decision(_mission_payload(validated))
    ops = snapshot(sync=False)
    active = ops.get("active_mission") or {}
    receipt = {
        "receipt_id": f"RECEIPT-BUS-{validated['command_id'][4:]}",
        "command_id": validated["command_id"], "decision_pack_id": validated["decision_pack_id"],
        "kind": "async_control_bus_receipt", "status": "completed", "transport": TRANSPORT,
        "source_path": source_path, "payload_hash": validated["payload_hash"],
        "mission_id": result.get("mission_id") or active.get("mission_id"), "created_at": now_iso(),
        "autonomy_allowed": validated["autonomy_allowed"],
        "result": {"applied": True, "decision": result, "active_mission": active},
        "truth_rule": "该回执只证明 Decision Pack 已进入本地 Mission 链；没有真实外部回执时不得声称已发布、已收录、已产生咨询或订单。",
    }
    _save_receipt(receipt)
    state = read_json(STATE_FILE, {})
    state = state if isinstance(state, dict) else {}
    state.update({
        "last_decision_pack_id": validated["decision_pack_id"], "last_command_id": validated["command_id"],
        "last_receipt_id": receipt["receipt_id"], "last_applied_at": receipt["created_at"],
        "last_error": None, "autonomy_state": "RUNNING",
    })
    write_json(STATE_FILE, state)
    return {"idempotent": False, "receipt": receipt}


class GitHubControlBusClient:
    def __init__(self, repo: str, branch: str, token: str):
        self.repo = _clean(repo, "KZ_CONTROL_BUS_REPO", 200)
        self.branch = _clean(branch or DEFAULT_BRANCH, "KZ_CONTROL_BUS_BRANCH", 120)
        self.token = _clean(token, "KZ_CONTROL_BUS_TOKEN", 500)

    def _request(self, method: str, url: str, payload=None):
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8") if payload is not None else None
        request = Request(url, data=data, method=method)
        request.add_header("Accept", "application/vnd.github+json")
        request.add_header("Authorization", f"Bearer {self.token}")
        request.add_header("X-GitHub-Api-Version", "2022-11-28")
        request.add_header("User-Agent", "Kazuizhi-Control-Bus/1.0")
        if data is not None:
            request.add_header("Content-Type", "application/json")
        try:
            with urlopen(request, timeout=15) as response:
                raw = response.read()
                return json.loads(raw.decode("utf-8")) if raw else {}
        except HTTPError as error:
            detail = error.read().decode("utf-8", errors="replace")[:800]
            raise RuntimeError(f"GitHub Control Bus HTTP {error.code}: {detail}") from error
        except URLError as error:
            raise RuntimeError(f"GitHub Control Bus 网络不可用：{error.reason}") from error

    def ensure_private_repo(self) -> dict:
        meta = self._request("GET", f"https://api.github.com/repos/{self.repo}")
        if meta.get("private") is not True:
            raise ValueError("控制总线必须使用独立的 PRIVATE GitHub 仓库；公共源码仓库禁止作为运营控制总线")
        return meta

    def list_commands(self) -> list[dict]:
        url = f"https://api.github.com/repos/{self.repo}/contents/commands?ref={quote(self.branch, safe='')}"
        try:
            rows = self._request("GET", url)
        except RuntimeError as error:
            if "HTTP 404" in str(error):
                return []
            raise
        return [x for x in rows if isinstance(x, dict) and str(x.get("name") or "").lower().endswith(".json")] if isinstance(rows, list) else []

    def read_json(self, path: str) -> dict:
        clean_path = quote(str(path or "").strip(), safe="/")
        url = f"https://api.github.com/repos/{self.repo}/contents/{clean_path}?ref={quote(self.branch, safe='')}"
        item = self._request("GET", url)
        encoded = str(item.get("content") or "").replace("\n", "")
        if item.get("encoding") != "base64" or not encoded:
            raise ValueError(f"控制总线文件不可读取：{path}")
        return json.loads(base64.b64decode(encoded).decode("utf-8"))

    def write_json(self, path: str, payload: dict, message: str) -> dict:
        clean_path = quote(str(path or "").strip(), safe="/")
        url = f"https://api.github.com/repos/{self.repo}/contents/{clean_path}"
        sha = None
        try:
            existing = self._request("GET", f"{url}?ref={quote(self.branch, safe='')}")
            sha = existing.get("sha") if isinstance(existing, dict) else None
        except RuntimeError as error:
            if "HTTP 404" not in str(error):
                raise
        body = {
            "message": str(message or "KZ control bus update")[:200], "branch": self.branch,
            "content": base64.b64encode(json.dumps(payload, ensure_ascii=False, indent=2).encode("utf-8")).decode("ascii"),
        }
        if sha:
            body["sha"] = sha
        return self._request("PUT", url, body)


def _client_from_config() -> GitHubControlBusClient | None:
    config = _config()
    return GitHubControlBusClient(config["repo"], config["branch"], config["token"]) if config["enabled"] else None


def status() -> dict:
    config = _config()
    state = read_json(STATE_FILE, {})
    state = state if isinstance(state, dict) else {}
    return {
        "available": True, "role": "primary_async_owner_control", "transport": TRANSPORT,
        "configured": config["configured"], "enabled": config["enabled"], "repo": config["repo"] or None,
        "branch": config["branch"], "poll_seconds": config["poll_seconds"], "private_repo_required": True,
        "local_autonomy": state.get("autonomy_state") or "RUNNING", "last_sync_at": state.get("last_sync_at"),
        "last_decision_pack_id": state.get("last_decision_pack_id"), "last_command_id": state.get("last_command_id"),
        "last_receipt_id": state.get("last_receipt_id"), "last_applied_at": state.get("last_applied_at"),
        "last_error": state.get("last_error"), "site_tools_role": "optional_realtime_helper",
        "work_codex_role": "engineering_only",
        "truth_rule": "控制总线同步成功不等于实时 ChatGPT 已连接；它只证明私有异步 Decision Pack/Receipt 通道可用。",
    }


def sync_once(client: GitHubControlBusClient | None = None) -> dict:
    current = client or _client_from_config()
    if current is None:
        return {"synced": False, "configured": False, "reason": "control_bus_not_configured", "status": status()}
    state = read_json(STATE_FILE, {})
    state = state if isinstance(state, dict) else {}
    try:
        current.ensure_private_repo()
        commands = sorted(current.list_commands(), key=lambda x: str(x.get("name") or ""))[-MAX_COMMANDS_PER_SYNC:]
        processed = []
        for item in commands:
            path = str(item.get("path") or f"commands/{item.get('name')}")
            result = process_decision_pack(current.read_json(path), source_path=path)
            receipt = result["receipt"]
            current.write_json(f"receipts/{receipt['command_id']}.json", receipt, f"{receipt['receipt_id']}: {receipt['status']}")
            processed.append({"command_id": receipt["command_id"], "receipt_id": receipt["receipt_id"], "status": receipt["status"], "idempotent": result["idempotent"]})
        state.update({"last_sync_at": now_iso(), "last_error": None, "autonomy_state": "RUNNING", "processed_last_sync": len(processed)})
        write_json(STATE_FILE, state)
        current.write_json("state/system_health.json", {
            "schema": "kz.control-bus-state.v1", "updated_at": state["last_sync_at"], "local_autonomy": "RUNNING",
            "last_decision_pack_id": state.get("last_decision_pack_id"), "last_command_id": state.get("last_command_id"),
            "last_receipt_id": state.get("last_receipt_id"),
            "truth_rule": "无真实平台回执时，不得把内容生产或本地执行写成外部推广成功。",
        }, "KZ control bus state sync")
        return {"synced": True, "configured": True, "processed": processed, "status": status()}
    except (OSError, RuntimeError, TypeError, ValueError, KeyError, json.JSONDecodeError) as error:
        state.update({"last_sync_at": now_iso(), "last_error": str(error)[:800], "autonomy_state": "RUNNING"})
        write_json(STATE_FILE, state)
        return {"synced": False, "configured": True, "reason": "sync_failed", "error": str(error), "status": status()}


def _agent_loop():
    while not _AGENT_STOP.is_set():
        sync_once()
        _AGENT_STOP.wait(_config()["poll_seconds"])


def start_background_agent() -> bool:
    global _AGENT_THREAD
    if not _config()["enabled"]:
        return False
    if _AGENT_THREAD is not None and _AGENT_THREAD.is_alive():
        return True
    _AGENT_STOP.clear()
    _AGENT_THREAD = threading.Thread(target=_agent_loop, name="kz-control-bus", daemon=True)
    _AGENT_THREAD.start()
    return True


def stop_background_agent() -> None:
    _AGENT_STOP.set()
