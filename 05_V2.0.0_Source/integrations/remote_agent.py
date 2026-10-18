"""R8-17 desktop client for the lightweight production Remote Agent.

The full AI runtime stays on the owner's PC. The production server exposes only
an authenticated execution endpoint. Pairing secrets are never written to normal
JSON state: on Windows they are stored through the existing DPAPI vault.
"""
from __future__ import annotations

import base64
import hashlib
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from copy import deepcopy
from pathlib import Path
from urllib.parse import urlsplit

from core.storage import now_iso, read_json, write_json
from integrations.credential_vault import delete_secret, get_secret, put_secret

STORE = "r8_17/remote_agent.json"
SCHEMA = "kz.remote-agent-client.v1"
SECRET_KEY = "remote_agent.shared_secret"
PAIRING_FILENAME = "Kazuizhi_RemoteAgent_PAIRING_DELETE_AFTER_IMPORT.json"
EXPECTED_PROTOCOL = "kz-remote-agent-v1"
EXPECTED_AUTH_SCHEME = "token-v1"
EXPECTED_HOST = "kazuizhi.com"
EXPECTED_PATH = "/kz-remote-v1/agent.ashx/v1"
DEFAULT = {
    "schema": SCHEMA,
    "configured": False,
    "protocol": EXPECTED_PROTOCOL,
    "auth_scheme": EXPECTED_AUTH_SCHEME,
    "endpoint": "https://kazuizhi.com/kz-remote-v1/agent.ashx/v1",
    "key_id": "",
    "imported_at": "",
    "imported_from": "",
    "last_health_at": "",
    "last_health": {},
    "last_error": "",
    "updated_at": "",
}


def _load() -> dict:
    data = read_json(STORE, deepcopy(DEFAULT))
    if not isinstance(data, dict) or data.get("schema") != SCHEMA:
        data = deepcopy(DEFAULT)
    for key, value in DEFAULT.items():
        data.setdefault(key, deepcopy(value))
    return data


def _save(data: dict) -> dict:
    data["schema"] = SCHEMA
    data["updated_at"] = now_iso()
    write_json(STORE, data)
    return data


def _secret() -> str:
    try:
        return str(get_secret(SECRET_KEY) or "").strip()
    except (OSError, RuntimeError, ValueError):
        return ""


def _validate_endpoint(value: str) -> str:
    raw = str(value or "").strip().rstrip("/")
    parts = urlsplit(raw)
    if parts.scheme.lower() != "https":
        raise ValueError("Remote Agent endpoint 必须使用 HTTPS")
    if parts.username or parts.password or parts.query or parts.fragment:
        raise ValueError("Remote Agent endpoint 不能包含账号、查询参数或片段")
    if not parts.hostname or parts.hostname.lower() != EXPECTED_HOST:
        raise ValueError("Remote Agent endpoint 必须是 kazuizhi.com")
    if (parts.path or "").rstrip("/") != EXPECTED_PATH:
        raise ValueError("Remote Agent endpoint 路径与 R8-17 FINAL5 不匹配")
    return f"https://{EXPECTED_HOST}{EXPECTED_PATH}"


def _validate_pairing(payload: dict) -> dict:
    if not isinstance(payload, dict):
        raise ValueError("配对文件格式无效")
    protocol = str(payload.get("protocol") or "").strip()
    auth_scheme = str(payload.get("auth_scheme") or EXPECTED_AUTH_SCHEME).strip()
    endpoint = _validate_endpoint(payload.get("endpoint"))
    key_id = str(payload.get("key_id") or "").strip()
    secret = str(payload.get("shared_secret") or "").strip()
    if protocol != EXPECTED_PROTOCOL:
        raise ValueError("配对协议不是 kz-remote-agent-v1")
    if auth_scheme != EXPECTED_AUTH_SCHEME:
        raise ValueError("配对认证协议不是 token-v1")
    if not key_id or len(key_id) > 120:
        raise ValueError("配对 key_id 无效")
    if len(secret) < 32 or len(secret) > 256:
        raise ValueError("配对密钥长度无效")
    return {
        "protocol": protocol,
        "auth_scheme": auth_scheme,
        "endpoint": endpoint,
        "key_id": key_id,
        "shared_secret": secret,
    }


def _headers(key_id: str, secret: str, body: bytes = b"") -> dict:
    return {
        "X-KZ-Key": key_id,
        "X-KZ-Agent-Token": secret,
        "X-KZ-Timestamp": str(int(time.time())),
        "X-KZ-Nonce": uuid.uuid4().hex,
        "X-KZ-Body-SHA256": hashlib.sha256(body or b"").hexdigest(),
        "User-Agent": "Kazuizhi-R8-17-Desktop/1.0",
        "Accept": "application/json",
    }


def _decode_response(response) -> dict:
    raw = response.read(256 * 1024).decode("utf-8", errors="replace")
    if not raw:
        return {}
    try:
        payload = json.loads(raw)
    except (TypeError, ValueError, json.JSONDecodeError) as error:
        raise RuntimeError("Remote Agent 返回了非 JSON 响应") from error
    if not isinstance(payload, dict):
        raise RuntimeError("Remote Agent 返回格式无效")
    return payload


def _request_with_credentials(
    endpoint: str,
    key_id: str,
    secret: str,
    route: str,
    *,
    method: str = "GET",
    body: bytes = b"",
    content_type: str = "",
    timeout: int = 15,
) -> dict:
    base = _validate_endpoint(endpoint)
    path = str(route or "").strip().lstrip("/")
    if not path or any(part == ".." for part in path.split("/")):
        raise ValueError("Remote Agent route 无效")
    url = f"{base}/{path}"
    headers = _headers(key_id, secret, body)
    if content_type:
        headers["Content-Type"] = content_type
    request = urllib.request.Request(
        url,
        data=body if method.upper() in {"POST", "PUT"} else None,
        headers=headers,
        method=method.upper(),
    )
    try:
        with urllib.request.urlopen(request, timeout=max(3, min(60, int(timeout)))) as response:  # nosec B310 - endpoint is strictly validated HTTPS kazuizhi.com
            code = int(getattr(response, "status", 200) or 200)
            payload = _decode_response(response)
        if not 200 <= code < 300 or payload.get("ok") is False:
            raise RuntimeError(f"Remote Agent 请求失败 HTTP {code}")
        return payload
    except urllib.error.HTTPError as error:
        try:
            raw = error.read(64 * 1024).decode("utf-8", errors="replace")
            payload = json.loads(raw) if raw else {}
        except (OSError, ValueError, json.JSONDecodeError):
            payload = {}
        reason = str(payload.get("error") or f"HTTP {int(error.code)}")
        raise RuntimeError(f"Remote Agent 拒绝请求：{reason}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"Remote Agent 网络不可达：{error.reason}") from error


def _request(route: str, *, method: str = "GET", body: bytes = b"", content_type: str = "", timeout: int = 15) -> dict:
    data = _load()
    secret = _secret()
    if not data.get("configured") or not secret:
        raise RuntimeError("Remote Agent 尚未完成配对")
    return _request_with_credentials(
        str(data.get("endpoint") or ""),
        str(data.get("key_id") or ""),
        secret,
        route,
        method=method,
        body=body,
        content_type=content_type,
        timeout=timeout,
    )


def _candidate_pairing_paths() -> list[Path]:
    home = Path.home()
    candidates = [home / "Desktop" / PAIRING_FILENAME, home / "Downloads" / PAIRING_FILENAME]
    onedrive = str(os.environ.get("OneDrive") or "").strip()
    if onedrive:
        candidates.append(Path(onedrive) / "Desktop" / PAIRING_FILENAME)
    userprofile = str(os.environ.get("USERPROFILE") or "").strip()
    if userprofile:
        root = Path(userprofile)
        candidates.extend([root / "Desktop" / PAIRING_FILENAME, root / "Downloads" / PAIRING_FILENAME])
    unique = []
    seen = set()
    for path in candidates:
        key = str(path).lower()
        if key not in seen:
            seen.add(key)
            unique.append(path)
    return unique


def pairing_candidates() -> list[str]:
    return [str(path) for path in _candidate_pairing_paths() if path.is_file()]


def import_pairing(payload: dict, *, source_name: str = "manual", delete_path: Path | None = None) -> dict:
    pair = _validate_pairing(payload)
    # Prove credentials before persisting or deleting the source file.
    health_reply = _request_with_credentials(pair["endpoint"], pair["key_id"], pair["shared_secret"], "health", timeout=20)
    if not health_reply.get("ok") or health_reply.get("protocol") != EXPECTED_PROTOCOL:
        raise RuntimeError("Remote Agent 健康检查没有通过")
    caps = _request_with_credentials(pair["endpoint"], pair["key_id"], pair["shared_secret"], "capabilities", timeout=20)
    if not caps.get("ok") or caps.get("auth_scheme") != EXPECTED_AUTH_SCHEME:
        raise RuntimeError("Remote Agent capabilities 验证没有通过")

    put_secret(SECRET_KEY, pair["shared_secret"])
    data = _load()
    data.update({
        "configured": True,
        "protocol": pair["protocol"],
        "auth_scheme": pair["auth_scheme"],
        "endpoint": pair["endpoint"],
        "key_id": pair["key_id"],
        "imported_at": now_iso(),
        "imported_from": str(source_name or "manual")[:160],
        "last_health_at": now_iso(),
        "last_health": {
            "ok": True,
            "version": health_reply.get("version"),
            "protocol": health_reply.get("protocol"),
            "auth_scheme": health_reply.get("auth_scheme"),
            "website_ready": bool(health_reply.get("website_ready")),
        },
        "last_error": "",
    })
    _save(data)

    deleted = False
    if delete_path is not None:
        try:
            delete_path.unlink()
            deleted = True
        except OSError:
            deleted = False
    return {
        "ok": True,
        "connected": True,
        "version": health_reply.get("version"),
        "endpoint": pair["endpoint"],
        "pairing_file_deleted_locally": deleted,
        "truth": "配对密钥已转存到本机 Windows DPAPI；状态接口不会返回密钥。",
    }


def import_pairing_file(path: str | Path, *, delete_after_success: bool = True) -> dict:
    source = Path(path).expanduser()
    if not source.is_file():
        raise ValueError("配对文件不存在")
    if source.name != PAIRING_FILENAME:
        raise ValueError("配对文件名不匹配")
    try:
        payload = json.loads(source.read_text(encoding="utf-8-sig"))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        raise ValueError("配对文件 JSON 无效") from error
    return import_pairing(payload, source_name=source.name, delete_path=source if delete_after_success else None)


def auto_import_pairing() -> dict:
    existing = status(check_live=False)
    if existing.get("configured") and _secret():
        return {"ok": True, "skipped": True, "reason": "already_configured"}
    candidates = [path for path in _candidate_pairing_paths() if path.is_file()]
    if not candidates:
        return {"ok": False, "skipped": True, "reason": "pairing_file_not_found"}
    last_error = ""
    for path in candidates:
        try:
            return import_pairing_file(path, delete_after_success=True)
        except (OSError, ValueError, RuntimeError) as error:
            last_error = str(error)
    return {"ok": False, "skipped": False, "reason": last_error or "pairing_import_failed"}


def health(*, timeout: int = 12) -> dict:
    return _request("health", timeout=timeout)


def capabilities(*, timeout: int = 12) -> dict:
    return _request("capabilities", timeout=timeout)


def selftest(*, timeout: int = 20) -> dict:
    return _request("selftest", timeout=timeout)


def status(*, check_live: bool = True) -> dict:
    data = _load()
    secret_present = bool(_secret())
    configured = bool(data.get("configured") and data.get("key_id") and secret_present)
    connected = False
    live = deepcopy(data.get("last_health") or {})
    error = str(data.get("last_error") or "")
    if configured and check_live:
        try:
            reply = health(timeout=8)
            connected = bool(reply.get("ok"))
            live = {
                "ok": connected,
                "version": reply.get("version"),
                "protocol": reply.get("protocol"),
                "auth_scheme": reply.get("auth_scheme"),
                "website_ready": bool(reply.get("website_ready")),
            }
            error = ""
        except (OSError, ValueError, RuntimeError) as exc:
            connected = False
            error = str(exc)
        data["last_health_at"] = now_iso()
        data["last_health"] = live
        data["last_error"] = error
        _save(data)
    elif configured:
        connected = bool(live.get("ok"))
    return {
        "configured": configured,
        "connected": connected,
        "protocol": data.get("protocol"),
        "auth_scheme": data.get("auth_scheme"),
        "endpoint": data.get("endpoint"),
        "key_id": data.get("key_id"),
        "secret_present": secret_present,
        "secret_exposed": False,
        "last_health_at": data.get("last_health_at") or "",
        "version": live.get("version"),
        "website_ready": bool(live.get("website_ready")),
        "last_error": error,
        "pairing_file_detected": bool(pairing_candidates()),
        "truth": "Remote Agent 只表示远程执行通道可用；发布、提交、收录和排名仍分别要求真实回执。",
    }


def _safe_relative_path(value: str) -> str:
    raw = str(value or "").replace("\\", "/").strip().lstrip("/")
    if not raw or ".." in raw.split("/") or ":" in raw:
        raise ValueError("远程发布路径无效")
    parts = [part for part in raw.split("/") if part]
    if len(parts) == 1:
        if parts[0].lower() not in {"sitemap.xml", "robots.txt"}:
            raise ValueError("根目录只允许 sitemap.xml / robots.txt")
    elif parts[0].lower() not in {"seo", "downloads", "apk", "public"}:
        raise ValueError("远程发布目录不在允许范围")
    blocked = {"web.config", "global.asax", ".htaccess"}
    if any(part.lower() in blocked for part in parts):
        raise ValueError("禁止发布服务器配置文件")
    return "/".join(parts)


def _form(payload: dict) -> bytes:
    return urllib.parse.urlencode(payload).encode("utf-8")


def upload_bytes(relative_path: str, content: bytes, *, job_id: str = "") -> dict:
    relative = _safe_relative_path(relative_path)
    raw = bytes(content)
    sha256 = hashlib.sha256(raw).hexdigest()
    clean_job = "".join(ch if ch.isalnum() or ch in {"-", "_"} else "-" for ch in str(job_id or "").strip())[:96]
    if not clean_job:
        clean_job = f"R817-{uuid.uuid4().hex[:20]}"
    start_body = _form({"job_id": clean_job, "relative_path": relative, "total_size": len(raw), "sha256": sha256})
    started = _request("upload/start", method="POST", body=start_body, content_type="application/x-www-form-urlencoded", timeout=20)
    session_id = str(started.get("session_id") or "")
    if not session_id:
        raise RuntimeError("Remote Agent 未返回上传 session_id")
    max_chunk = int(started.get("max_chunk_bytes") or 512 * 1024)
    chunk_size = max(32 * 1024, min(max_chunk, 384 * 1024))
    offset = 0
    while offset < len(raw):
        chunk = raw[offset: offset + chunk_size]
        encoded = base64.urlsafe_b64encode(chunk).decode("ascii").rstrip("=")
        body = _form({"session_id": session_id, "offset": offset, "data_base64url": encoded})
        reply = _request("upload/chunk", method="POST", body=body, content_type="application/x-www-form-urlencoded", timeout=30)
        new_offset = int(reply.get("received") or 0)
        if new_offset <= offset or new_offset > len(raw):
            raise RuntimeError("Remote Agent 分块上传进度异常")
        offset = new_offset
    commit_body = _form({"session_id": session_id})
    receipt_data = _request("upload/commit", method="POST", body=commit_body, content_type="application/x-www-form-urlencoded", timeout=30)
    if not receipt_data.get("ok") or str(receipt_data.get("sha256") or "").lower() != sha256:
        raise RuntimeError("Remote Agent 发布回执 SHA-256 不匹配")
    return receipt_data


def upload_file(relative_path: str, source: str | Path, *, job_id: str = "") -> dict:
    path = Path(source)
    if not path.is_file():
        raise ValueError("待发布文件不存在")
    return upload_bytes(relative_path, path.read_bytes(), job_id=job_id)


def receipt(receipt_id: str) -> dict:
    value = str(receipt_id or "").strip()
    if not value or not all(ch.isalnum() or ch in {"-", "_"} for ch in value):
        raise ValueError("receipt_id 无效")
    route = "receipt?" + urllib.parse.urlencode({"id": value})
    return _request(route, timeout=12)


def rollback(job_id: str, relative_path: str) -> dict:
    body = _form({"job_id": str(job_id or "").strip(), "relative_path": _safe_relative_path(relative_path)})
    return _request("rollback", method="POST", body=body, content_type="application/x-www-form-urlencoded", timeout=20)


def disconnect() -> dict:
    delete_secret(SECRET_KEY)
    _save(deepcopy(DEFAULT))
    return status(check_live=False)
