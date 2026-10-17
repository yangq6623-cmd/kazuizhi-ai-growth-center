"""Read-only WeChat Mini Program visit analytics connector.

This connector is deliberately separate from the production business-summary
endpoint.  It asks WeChat only for the latest *completed* day's aggregate
visit trend, stores no visitor-level information, and never writes to the
Mini Program.  AppID/AppSecret are protected with the current Windows user's
DPAPI and are never included in logs, status files, or UI responses.
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone

from core.storage import data_root, now_iso, read_json, write_json
from integrations.business_data import _protect, _unprotect


TOKEN_ENDPOINT = "https://api.weixin.qq.com/cgi-bin/token"
DAILY_TREND_ENDPOINT = "https://api.weixin.qq.com/datacube/getweanalysisappiddailyvisittrend"
SECRET_PATH = "integrations/wechat_mini_program.bin"
STATUS_PATH = "integrations/wechat_mini_program_status.json"
SUMMARY_PATH = "business/wechat_mini_program_summary.json"


def _secret_file():
    return data_root() / SECRET_PATH


def _read_config():
    path = _secret_file()
    if not path.exists():
        return {}
    try:
        value = json.loads(_unprotect(path.read_bytes()))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError, TypeError):
        return {}


def _save_config(app_id, app_secret):
    path = _secret_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    value = json.dumps({"app_id": app_id, "app_secret": app_secret}, ensure_ascii=False)
    path.write_bytes(_protect(value))


def _status():
    return read_json(STATUS_PATH, {
        "last_refresh": None, "last_ok": None, "last_error": None,
        "last_error_code": None,
    })


def _save_status(**updates):
    status = _status()
    status.update(updates)
    write_json(STATUS_PATH, status)
    return status


def _friendly_error(code):
    messages = {
        40001: "微信 access_token 无效或已失效，请重新验证 AppID 与 AppSecret。",
        40013: "微信 AppID 格式无效，请核对小程序后台的 AppID。",
        40125: "微信 AppSecret 无效，请在小程序后台重新生成后保存。",
        45009: "微信接口调用频率受限，稍后会自动重试。",
        48001: "当前小程序未获得访问统计接口权限，请由管理员在微信后台核对权限。",
        -1: "微信服务暂时繁忙，系统会在下次刷新时重试。",
    }
    return messages.get(code, "微信访问统计接口返回错误，请在小程序后台核对 AppID、AppSecret、接口权限和服务器网络。")


def _request_json(url, payload=None):
    data = None if payload is None else json.dumps(payload).encode("utf-8")
    request = urllib.request.Request(
        url, data=data, method="POST" if data is not None else "GET",
        headers={"Accept": "application/json", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            if response.status != 200:
                raise ValueError("微信接口返回 HTTP %s" % response.status)
            result = json.load(response)
    except (urllib.error.URLError, urllib.error.HTTPError, TimeoutError, OSError, json.JSONDecodeError):
        raise ValueError("无法连接微信小程序访问统计接口") from None
    if not isinstance(result, dict):
        raise ValueError("微信接口返回格式无效")
    if result.get("errcode") not in (None, 0):
        code = result.get("errcode")
        error = ValueError(_friendly_error(code))
        error.wechat_code = code
        raise error
    return result


def _latest_completed_date():
    cn = timezone(timedelta(hours=8))
    return (datetime.now(cn).date() - timedelta(days=1)).strftime("%Y%m%d")


def _fetch_summary(config):
    query = urllib.parse.urlencode({
        "grant_type": "client_credential", "appid": config["app_id"], "secret": config["app_secret"],
    })
    token = _request_json(TOKEN_ENDPOINT + "?" + query).get("access_token")
    if not isinstance(token, str) or not token:
        raise ValueError("微信未返回可用 access_token")
    ref_date = _latest_completed_date()
    result = _request_json(DAILY_TREND_ENDPOINT + "?access_token=" + urllib.parse.quote(token, safe=""), {
        "begin_date": ref_date, "end_date": ref_date,
    })
    rows = result.get("list")
    if not isinstance(rows, list) or not rows or not isinstance(rows[0], dict):
        raise ValueError("微信暂未返回最近完整日访问数据")
    row = rows[0]
    def number(name):
        value = row.get(name)
        if isinstance(value, bool) or not isinstance(value, (int, float)) or value < 0:
            raise ValueError("微信访问数据字段无效：%s" % name)
        return value
    return {
        "status": "ok", "ref_date": str(row.get("ref_date") or ref_date)[:20],
        "visit_uv": number("visit_uv"), "visit_pv": number("visit_pv"),
        "session_cnt": number("session_cnt"), "visit_uv_new": number("visit_uv_new"),
        "source": "WeChat Mini Program Analytics / daily visit trend / aggregate-only",
    }


def configure_wechat_mini_program(payload):
    app_id = str((payload or {}).get("app_id") or "").strip()
    app_secret = str((payload or {}).get("app_secret") or "").strip()
    if not (10 <= len(app_id) <= 64) or not (16 <= len(app_secret) <= 256):
        raise ValueError("请填写小程序后台的 AppID 与 AppSecret")
    _save_config(app_id, app_secret)
    _save_status(last_refresh=None, last_ok=None, last_error=None, last_error_code=None)
    return refresh_wechat_mini_program(force=True)


def refresh_wechat_mini_program(force=True):
    config = _read_config()
    if not config.get("app_id") or not config.get("app_secret"):
        return wechat_mini_program_status()
    try:
        summary = _fetch_summary(config)
        write_json(SUMMARY_PATH, summary)
        _save_status(last_refresh=now_iso(), last_ok=True, last_error=None, last_error_code=None)
    except ValueError as error:
        _save_status(last_refresh=now_iso(), last_ok=False, last_error=str(error),
                     last_error_code=getattr(error, "wechat_code", None))
        if force:
            raise
    return wechat_mini_program_status()


def test_wechat_mini_program():
    if not _read_config():
        raise ValueError("请先保存小程序 AppID 与 AppSecret")
    return refresh_wechat_mini_program(force=True)


def wechat_mini_program_status():
    config = _read_config()
    status = _status()
    summary = read_json(SUMMARY_PATH, {}) or {}
    configured = bool(config.get("app_id") and config.get("app_secret"))
    connected = bool(configured and status.get("last_ok") and summary.get("status") == "ok")
    return {
        "id": "wechat_mini_program", "configured": configured, "has_credentials": configured,
        "status": "connected" if connected else "error" if configured and status.get("last_error") else "not_configured",
        "status_label": "已验证访问数据" if connected else "需要修复" if configured else "未配置微信统计",
        "last_refresh": status.get("last_refresh"), "last_error": status.get("last_error"),
        "last_error_code": status.get("last_error_code"),
        "summary": summary if connected else {},
        "message": "微信官方最近完整日访问数据已验证。" if connected else
                   status.get("last_error") or "尚未配置微信小程序 AppID 与 AppSecret。",
    }
