"""Honest integration status, encrypted AI credentials and self diagnostics."""

import base64
import ctypes
import json
import os
import urllib.error
import urllib.request
from ctypes import wintypes
from urllib.parse import urlsplit

from analytics.business_metrics import build_analytics
from core.storage import data_root, now_iso, read_json, write_json
from integrations.bridge import bridge_status


CONFIG_PATH = "integrations/config.json"
SECRET_PATH = "integrations/ai_key.bin"


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
        ctypes.byref(incoming), None, None, None, None, 1,
        ctypes.byref(outgoing),
    ):
        raise OSError(f"Windows 无法加密 AI 密钥 ({ctypes.get_last_error()})")
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
        ctypes.byref(incoming), None, None, None, None, 1, ctypes.byref(outgoing),
    ):
        return ""
    try:
        return ctypes.string_at(outgoing.pbData, outgoing.cbData).decode("utf-8")
    finally:
        ctypes.windll.kernel32.LocalFree(outgoing.pbData)


def _read_key():
    path = _secret_file()
    if not path.exists():
        return os.environ.get("KAZUIZHI_AI_API_KEY", "").strip()
    try:
        return _unprotect(path.read_bytes()).strip()
    except (OSError, ValueError):
        return ""


def _save_key(value):
    path = _secret_file()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(_protect(value))


def _config():
    return read_json(CONFIG_PATH, {
        "provider": "openai_compatible", "base_url": "https://api.openai.com/v1",
        "model": "", "last_test": None,
    })


def _clean_url(value):
    value = str(value or "").strip().rstrip("/")
    parsed = urlsplit(value)
    local = parsed.hostname in {"127.0.0.1", "localhost"}
    if not parsed.scheme or not parsed.netloc or (parsed.scheme != "https" and not (local and parsed.scheme == "http")):
        raise ValueError("AI 服务地址必须使用 HTTPS；本机服务可使用 127.0.0.1 HTTP")
    return value


def save_ai_config(payload):
    config = _config()
    config["provider"] = "openai_compatible"
    config["base_url"] = _clean_url(payload.get("base_url") or config.get("base_url"))
    model = str(payload.get("model") or "").strip()[:120]
    if not model:
        raise ValueError("请填写模型名称")
    config["model"] = model
    if payload.get("clear_key"):
        try:
            _secret_file().unlink()
        except FileNotFoundError:
            pass
    key = str(payload.get("api_key") or "").strip()
    if key:
        if len(key) < 8 or len(key) > 500:
            raise ValueError("AI 密钥长度不正确")
        _save_key(key)
    elif not _read_key():
        raise ValueError("请填写 API 密钥")
    config["last_test"] = None
    write_json(CONFIG_PATH, config)
    return integration_status()


def _ai_status():
    config = _config()
    has_key = bool(_read_key())
    configured = bool(config.get("base_url") and config.get("model") and has_key)
    return {
        "id": "external_ai", "name": "外部大模型", "configured": configured,
        "status": "connected" if configured and (config.get("last_test") or {}).get("ok") else "configured" if configured else "not_configured",
        "status_label": "连接已验证" if configured and (config.get("last_test") or {}).get("ok") else "等待连接测试" if configured else "未配置",
        "provider": config.get("provider"), "base_url": config.get("base_url", ""),
        "model": config.get("model", ""), "has_key": has_key,
        "last_test": config.get("last_test"),
        "message": "已配置模型，需运行连接测试。" if configured and not (config.get("last_test") or {}).get("ok") else
                   "已通过真实端点测试。" if configured else
                   "本地规则能力可用，但外部大模型尚未接入。",
    }


def integration_status():
    analytics = build_analytics()
    ai = _ai_status()
    bridge = bridge_status()
    business_ready = analytics.get("status") == "verified"
    return {
        "generated_at": now_iso(), "external_ai": ai, "bridge": bridge,
        "items": [
            {"id": "local_engine", "name": "本地智能引擎", "status": "ready", "status_label": "可用", "message": "复盘、分析、任务和内容模板可在离线状态运行。"},
            ai,
            {"id": "business_data", "name": "经营数据", "status": "ready" if business_ready else "not_connected", "status_label": "已验证" if business_ready else "未接入", "message": analytics.get("message", "真实经营数据尚未接入。")},
            bridge,
            {"id": "publishing", "name": "内容发布", "status": "manual", "status_label": "人工审核", "message": "系统只生成草稿，不会自动对外发布。"},
            {"id": "finance", "name": "资金操作", "status": "blocked", "status_label": "永久禁止", "message": "付款、退款、提现、改价和结算必须由人工处理。"},
        ],
    }


def model_routes():
    """Expose only usable model routes; never imply ChatGPT web access."""
    ai = _ai_status()
    routes = [{"id": "local_rules", "label": "本地规则引擎", "status": "ready",
               "uses_external_data": False, "purpose": "离线复盘、任务和内容草稿"}]
    if ai["status"] == "connected":
        routes.append({"id": "external_compatible", "label": ai["model"],
                       "status": "ready", "uses_external_data": True,
                       "purpose": "经用户主动提交的 AI 建议"})
    return {"default": "local_rules", "routes": routes,
            "external_status": ai["status"],
            "note": "ChatGPT 网页会话不是本机连接；双向运营桥用于交换结构化运营状态和待审批计划。"}


def _request_json(url, *, method="GET", payload=None, key="", timeout=12):
    headers = {"Accept": "application/json", "User-Agent": "Kazuizhi-AI-Growth-Center/2.0"}
    data = None
    if key:
        headers["Authorization"] = f"Bearer {key}"
    if payload is not None:
        headers["Content-Type"] = "application/json"
        data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            return json.load(response)
    except urllib.error.HTTPError as error:
        raise ValueError(f"AI 服务返回 {error.code}，请检查密钥、地址和模型") from None
    except (urllib.error.URLError, TimeoutError, OSError):
        raise ValueError("无法连接 AI 服务，请检查网络和服务地址") from None


def test_ai_connection():
    config = _config()
    key = _read_key()
    if not config.get("model") or not key:
        raise ValueError("请先填写模型名称和 API 密钥")
    _request_json(_clean_url(config.get("base_url")) + "/models", key=key)
    config["last_test"] = {"ok": True, "tested_at": now_iso(), "message": "连接和鉴权测试通过"}
    write_json(CONFIG_PATH, config)
    return integration_status()


def ask_ai(payload):
    prompt = str(payload.get("prompt") or "").strip()
    if not prompt or len(prompt) > 2000:
        raise ValueError("请输入 1-2000 个字的问题")
    config = _config()
    key = _read_key()
    if not config.get("model") or not key:
        raise ValueError("外部大模型尚未配置")
    response = _request_json(
        _clean_url(config.get("base_url")) + "/chat/completions", method="POST", key=key,
        payload={"model": config["model"], "temperature": 0.2, "messages": [
            {"role": "system", "content": "你是卡嘴子AI运营助手。只基于用户提供和已验证数据给出可审核建议，不编造订单、收入、客户、排名或效果，不自动执行任务。"},
            {"role": "user", "content": prompt},
        ]},
    )
    try:
        content = response["choices"][0]["message"]["content"]
    except (KeyError, IndexError, TypeError):
        raise ValueError("AI 服务返回了无法识别的结果") from None
    return {"content": str(content), "model": config["model"], "execution": "proposal_only", "created_at": now_iso()}


def system_diagnostics():
    checks = []
    try:
        root = data_root()
        probe = root / ".health-check"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        checks.append({"id": "storage", "name": "本机数据保存", "status": "pass", "message": "可写入并读取"})
    except OSError:
        checks.append({"id": "storage", "name": "本机数据保存", "status": "fail", "message": "无法写入数据目录"})
    ai = _ai_status()
    bridge = bridge_status()
    checks.extend([
        {"id": "web", "name": "管理界面", "status": "pass", "message": "前后端构建标识一致"},
        {"id": "local_ai", "name": "本地智能引擎", "status": "pass", "message": "离线复盘、内容和任务能力可用"},
        {"id": "bridge", "name": "双向运营桥", "status": "pass" if bridge["status"] == "connected" else "attention", "message": bridge["status_label"] + " · " + bridge["operating_mode_label"]},
        {"id": "external_ai", "name": "外部大模型", "status": "pass" if ai["status"] == "connected" else "attention", "message": ai["status_label"]},
        {"id": "business", "name": "经营数据", "status": "pass" if build_analytics().get("status") == "verified" else "attention", "message": "已验证" if build_analytics().get("status") == "verified" else "待接入真实数据"},
        {"id": "safety", "name": "发布与资金安全", "status": "pass", "message": "发布需审核，资金操作已禁止"},
    ])
    return {"status": "healthy" if not any(x["status"] == "fail" for x in checks) else "degraded",
            "checked_at": now_iso(), "checks": checks,
            "summary": {"passed": sum(x["status"] == "pass" for x in checks), "attention": sum(x["status"] == "attention" for x in checks), "failed": sum(x["status"] == "fail" for x in checks)}}


def control_center():
    integrations = integration_status()
    external = integrations["external_ai"]
    bridge = integrations["bridge"]
    return {
        "generated_at": now_iso(), "mode": bridge["operating_mode"],
        "headline": "双向运营桥已连接，本地自主运行也保持可用" if bridge["status"] == "connected" else "本地自主运行正常；可配置双向运营桥接收云端计划",
        "roles": [
            {"name": "数据分析 AI", "purpose": "检查数据和发现问题", "status": "ready"},
            {"name": "战略规划 AI", "purpose": "把问题转换为优先级和计划", "status": "ready"},
            {"name": "内容增长 AI", "purpose": "生成可审核的内容草稿", "status": "ready"},
            {"name": "经营优化 AI", "purpose": "根据真实结果复盘优化", "status": "waiting_data" if build_analytics().get("status") != "verified" else "ready"},
        ],
        "loop": ["本机扫描", "自动上报", "AI分析", "计划回传", "本机审批/执行", "结果回执", "复盘优化"],
        "bridge": bridge, "external_ai": external,
        "truth": "双向桥、外部 AI 和经营数据只有在真实验证后才显示已连接；云端指令不能绕过本机审批和资金安全边界。",
    }
