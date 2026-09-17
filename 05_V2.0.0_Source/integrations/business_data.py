"""Live read-only Kazuizhi production business data connector.

The production endpoint is fixed and GET-only. The connector stores only the dedicated
read-only key locally (DPAPI on Windows), validates the returned aggregate schema, and
persists only aggregate data. Raw personal/order rows are never accepted or stored.
"""

import base64
import ctypes
import json
import os
import urllib.error
import urllib.request
from ctypes import wintypes
from datetime import datetime, timezone

from core.storage import data_root, now_iso, read_json, write_json


ENDPOINT = "https://kazuizhi.com/ai-business-summary.ashx"
SECRET_PATH = "integrations/business_readonly_key.bin"
STATUS_PATH = "integrations/business_source.json"
REMOTE_SUMMARY_PATH = "business/remote_summary.json"
REFRESH_SECONDS = 300
FORBIDDEN_PARTS = (
    "phone", "mobile", "address", "openid", "unionid", "id_card", "identity",
    "password", "secret", "token", "adminkey", "admin_key", "bank", "card_no",
)


class DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_char))]


def _secret_file():
    return data_root() / SECRET_PATH


def _protect(value):
    raw = value.encode("utf-8")
    if os.name != "nt":
        return base64.b64encode(raw)
    buffer = ctypes.create_string_buffer(raw, len(raw))
    incoming = DATA_BLOB(len(raw), buffer)
    outgoing = DATA_BLOB()
    crypt32 = ctypes.WinDLL("crypt32.dll", use_last_error=True)
    crypt32.CryptProtectData.argtypes = [ctypes.POINTER(DATA_BLOB), wintypes.LPCWSTR,
        ctypes.POINTER(DATA_BLOB), ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD,
        ctypes.POINTER(DATA_BLOB)]
    crypt32.CryptProtectData.restype = wintypes.BOOL
    if not crypt32.CryptProtectData(
        ctypes.byref(incoming), None, None, None, None, 1, ctypes.byref(outgoing)
    ):
        raise OSError("Windows 无法加密经营数据只读密钥 (%s)" % ctypes.get_last_error())
    try:
        return ctypes.string_at(outgoing.pbData, outgoing.cbData)
    finally:
        ctypes.windll.kernel32.LocalFree(outgoing.pbData)


def _unprotect(raw):
    if os.name != "nt":
        return base64.b64decode(raw).decode("utf-8")
    buffer = ctypes.create_string_buffer(raw, len(raw))
    incoming = DATA_BLOB(len(raw), buffer)
    outgoing = DATA_BLOB()
    crypt32 = ctypes.WinDLL("crypt32.dll", use_last_error=True)
    crypt32.CryptUnprotectData.argtypes = [ctypes.POINTER(DATA_BLOB), ctypes.c_void_p,
        ctypes.POINTER(DATA_BLOB), ctypes.c_void_p, ctypes.c_void_p, wintypes.DWORD,
        ctypes.POINTER(DATA_BLOB)]
    crypt32.CryptUnprotectData.restype = wintypes.BOOL
    if not crypt32.CryptUnprotectData(
        ctypes.byref(incoming), None, None, None, None, 1, ctypes.byref(outgoing)
    ):
        return ""
    try:
        return ctypes.string_at(outgoing.pbData, outgoing.cbData).decode("utf-8")
    finally:
        ctypes.windll.kernel32.LocalFree(outgoing.pbData)


def _read_key():
    path = _secret_file()
    if not path.exists():
        return os.environ.get("KAZUIZHI_BUSINESS_READONLY_KEY", "").strip()
    try:
        return _unprotect(path.read_bytes()).strip()
    except (OSError, ValueError):
        return ""


def _save_key(value):
    path = _secret_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_protect(value))


def _status_config():
    return read_json(STATUS_PATH, {
        "endpoint": ENDPOINT,
        "last_refresh": None,
        "last_ok": None,
        "last_error": None,
    })


def _save_status(**updates):
    status = _status_config()
    status.update(updates)
    status["endpoint"] = ENDPOINT
    write_json(STATUS_PATH, status)
    return status


def _safe_number(value, name):
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
        raise ValueError("经营数据字段 %s 必须是非负数字" % name)
    return value


def _safe_object(value, name):
    if value is None:
        return {}
    if not isinstance(value, dict):
        raise ValueError("经营数据字段 %s 格式不正确" % name)
    return value


def _reject_sensitive(value, path="root"):
    if isinstance(value, dict):
        for key, item in value.items():
            lower = str(key).lower()
            if any(part in lower for part in FORBIDDEN_PARTS):
                raise ValueError("服务器经营汇总包含不允许的敏感字段：%s" % path)
            _reject_sensitive(item, path + "." + str(key))
    elif isinstance(value, list):
        for index, item in enumerate(value):
            _reject_sensitive(item, "%s[%d]" % (path, index))


def _counter_map(rows, name):
    if rows is None:
        return None
    if not isinstance(rows, list):
        raise ValueError("经营数据字段 %s 格式不正确" % name)
    result = {}
    for row in rows[:50]:
        if not isinstance(row, dict):
            continue
        label = str(row.get("name") or "").strip()
        if not label or len(label) > 80:
            continue
        if any(part in label.lower() for part in FORBIDDEN_PARTS):
            continue
        count = _safe_number(row.get("count"), name + ".count")
        if count is not None:
            result[label] = count
    return result or None


def validate_remote_summary(payload):
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        raise ValueError("服务器只读经营接口返回无效")
    _reject_sensitive(payload)
    source = str(payload.get("source") or "").strip()
    as_of = str(payload.get("as_of") or "").strip()
    quality = _safe_object(payload.get("data_quality"), "data_quality")
    if not source or not as_of:
        raise ValueError("服务器经营数据缺少 source 或 as_of")
    if quality.get("read_only") is not True or quality.get("write_operations") not in (0, 0.0):
        raise ValueError("服务器经营接口未通过只读安全校验")
    if quality.get("contains_personal_data") is not False:
        raise ValueError("服务器经营接口未通过个人数据安全校验")
    users = _safe_object(payload.get("users"), "users")
    orders = _safe_object(payload.get("orders"), "orders")
    technicians = _safe_object(payload.get("technicians"), "technicians")
    partners = _safe_object(payload.get("partners"), "partners")
    promotion = _safe_object(payload.get("promotion"), "promotion")
    funnel = _safe_object(payload.get("funnel"), "funnel")
    mini_program = _safe_object(payload.get("mini_program"), "mini_program")
    clean = {
        "ok": True,
        "source": source[:160],
        "as_of": as_of[:100],
        "window": payload.get("window") if isinstance(payload.get("window"), dict) else {},
        "users": {key: _safe_number(users.get(key), "users." + key) for key in ("total", "new_today")},
        "orders": {key: _safe_number(orders.get(key), "orders." + key) for key in ("total", "today", "open", "completed", "cancelled", "refunded", "closed")},
        "technicians": {key: _safe_number(technicians.get(key), "technicians." + key) for key in ("total", "approved", "pending_review", "active")},
        "partners": {key: _safe_number(partners.get(key), "partners." + key) for key in ("total", "approved", "pending_review", "active")},
        "regions": payload.get("regions") if isinstance(payload.get("regions"), list) else [],
        "services": payload.get("services") if isinstance(payload.get("services"), list) else [],
        "promotion": {key: _safe_number(promotion.get(key), "promotion." + key) for key in ("event_records", "partner_attributed_orders")},
        "funnel": {key: _safe_number(funnel.get(key), "funnel." + key) for key in ("mini_program_visits", "repair_requests", "leads")},
        "mini_program": {
            "status": str(mini_program.get("status") or "")[:40],
            "ref_date": str(mini_program.get("ref_date") or "")[:20],
            "visit_uv": _safe_number(mini_program.get("visit_uv"), "mini_program.visit_uv"),
            "visit_pv": _safe_number(mini_program.get("visit_pv"), "mini_program.visit_pv"),
            "session_cnt": _safe_number(mini_program.get("session_cnt"), "mini_program.session_cnt"),
            "visit_uv_new": _safe_number(mini_program.get("visit_uv_new"), "mini_program.visit_uv_new"),
        },
        "data_quality": {
            "verified": bool(quality.get("verified")),
            "read_only": True,
            "write_operations": 0,
            "required_documents_present": _safe_number(quality.get("required_documents_present"), "data_quality.required_documents_present"),
            "required_documents_total": _safe_number(quality.get("required_documents_total"), "data_quality.required_documents_total"),
            "missing_documents": [str(x)[:100] for x in (quality.get("missing_documents") or [])[:20]],
            "contains_personal_data": False,
        },
    }
    return clean


def snapshot_from_remote(summary):
    """Map only semantically compatible aggregates into the existing R7 analytics schema."""
    return {
        "source": summary["source"],
        "as_of": summary["as_of"],
        "window": "服务器汇总：今日业务 + 累计状态；小程序访问为微信最近完整日UV",
        "mini_program_visits": (summary.get("funnel") or {}).get("mini_program_visits"),
        "repair_requests": (summary.get("funnel") or {}).get("repair_requests"),
        "leads": (summary.get("funnel") or {}).get("leads"),
        "new_users": summary["users"].get("new_today"),
        "new_orders": summary["orders"].get("today"),
        "approved_technicians": summary["technicians"].get("approved"),
        "active_technicians": summary["technicians"].get("active"),
        "active_leaders": summary["partners"].get("active"),
        "by_region": _counter_map(summary.get("regions"), "regions"),
        "by_skill": _counter_map(summary.get("services"), "services"),
    }


def _request_remote(key, timeout=20):
    request = urllib.request.Request(
        ENDPOINT,
        headers={
            "Accept": "application/json",
            "User-Agent": "Kazuizhi-AI-Growth-Center/2.0",
            "X-AI-Readonly-Key": key,
        },
        method="GET",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                raise ValueError("经营数据接口返回 HTTP %s" % response.status)
            return json.load(response)
    except urllib.error.HTTPError as error:
        if error.code == 401:
            raise ValueError("经营数据只读密钥验证失败") from None
        raise ValueError("经营数据接口返回 HTTP %s" % error.code) from None
    except (urllib.error.URLError, TimeoutError, OSError, json.JSONDecodeError):
        raise ValueError("无法连接卡嘴子真实经营数据接口") from None


def refresh_business_source(force=True):
    key = _read_key()
    if not key:
        return business_source_status()
    try:
        clean = validate_remote_summary(_request_remote(key))
        write_json(REMOTE_SUMMARY_PATH, clean)
        from analytics.business_metrics import import_snapshot
        analytics = import_snapshot(snapshot_from_remote(clean))
        _save_status(last_refresh=now_iso(), last_ok=True, last_error=None, remote_as_of=clean.get("as_of"))
        return business_source_status(analytics=analytics)
    except ValueError as error:
        _save_status(last_refresh=now_iso(), last_ok=False, last_error=str(error))
        if force:
            raise
        return business_source_status()


def _seconds_since(value):
    if not value:
        return None
    try:
        then = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if then.tzinfo is None:
            then = then.replace(tzinfo=timezone.utc)
        return max(0, (datetime.now(timezone.utc) - then.astimezone(timezone.utc)).total_seconds())
    except (ValueError, TypeError):
        return None


def refresh_if_due():
    if not _read_key():
        return business_source_status()
    status = _status_config()
    age = _seconds_since(status.get("last_refresh"))
    if age is None or age >= REFRESH_SECONDS:
        return refresh_business_source(force=False)
    return business_source_status()


def configure_business_source(payload):
    key = str((payload or {}).get("key") or "").strip()
    if len(key) < 32 or len(key) > 500:
        raise ValueError("请粘贴服务器生成的经营数据只读密钥")
    _save_key(key)
    _save_status(last_refresh=None, last_ok=None, last_error=None)
    return refresh_business_source(force=True)


def test_business_source():
    if not _read_key():
        raise ValueError("请先保存经营数据只读密钥")
    return refresh_business_source(force=True)


def business_source_status(analytics=None):
    status = _status_config()
    key_present = bool(_read_key())
    remote = read_json(REMOTE_SUMMARY_PATH, None) or {}
    quality = remote.get("data_quality") if isinstance(remote, dict) else {}
    connected = bool(key_present and status.get("last_ok") and remote.get("source") and remote.get("as_of"))
    return {
        "id": "business_source",
        "endpoint": ENDPOINT,
        "configured": key_present,
        "has_key": key_present,
        "status": "connected" if connected else "configured" if key_present else "not_configured",
        "status_label": "已验证接入" if connected else "等待验证" if key_present else "未配置只读密钥",
        "last_refresh": status.get("last_refresh"),
        "last_error": status.get("last_error"),
        "remote_as_of": remote.get("as_of"),
        "source": remote.get("source"),
        "data_quality": quality or {},
        "summary": {
            "users": remote.get("users") or {},
            "orders": remote.get("orders") or {},
            "technicians": remote.get("technicians") or {},
            "partners": remote.get("partners") or {},
            "promotion": remote.get("promotion") or {},
            "funnel": remote.get("funnel") or {},
            "mini_program": remote.get("mini_program") or {},
        },
        "message": "生产经营数据只读接口已验证；R7 每 5 分钟自动刷新。" if connected else
                   status.get("last_error") or ("密钥已保存，等待连接验证。" if key_present else "服务器接口已部署；粘贴一次只读密钥即可接入。"),
        "analytics_status": (analytics or {}).get("status") if isinstance(analytics, dict) else None,
    }
