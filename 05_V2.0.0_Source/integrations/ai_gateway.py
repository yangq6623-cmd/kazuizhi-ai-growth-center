"""Direct, auditable AI gateway for the Kazuizhi autonomous Mission loop.

The legacy filesystem bridge stays as an offline/fallback transport. When an
OpenAI API credential is configured, this gateway sends pending R8 planning and
post-render QC requests directly to ChatGPT and applies only locally validated
structured results. It never approves publication, never performs financial
operations and never treats a transport write as proof of model processing.
"""
from __future__ import annotations

import base64
import ctypes
import json
import os
import re
import urllib.error
import urllib.request
from ctypes import wintypes

from core.storage import now_iso, read_json, write_json
from promotion import content_factory as cf

CONFIG_PATH = "integrations/ai_gateway.json"
STATE_PATH = "integrations/ai_gateway_state.json"
DEFAULT_ENDPOINT = "https://api.openai.com/v1/responses"
DEFAULT_MODEL = "gpt-5.6"
MAX_ERROR = 500


class _DATA_BLOB(ctypes.Structure):
    _fields_ = [("cbData", wintypes.DWORD), ("pbData", ctypes.POINTER(ctypes.c_byte))]


def _config():
    value = read_json(CONFIG_PATH, {})
    return value if isinstance(value, dict) else {}


def _state():
    value = read_json(STATE_PATH, {})
    return value if isinstance(value, dict) else {}


def _save_state(**values):
    current = _state()
    current.update(values, updated_at=now_iso())
    write_json(STATE_PATH, current)
    return current


def _protect_windows(secret):
    if os.name != "nt":
        raise ValueError("当前系统不支持安全保存API密钥，请使用OPENAI_API_KEY环境变量")
    raw = secret.encode("utf-8")
    buffer = ctypes.create_string_buffer(raw)
    incoming = _DATA_BLOB(len(raw), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
    outgoing = _DATA_BLOB()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    if not crypt32.CryptProtectData(ctypes.byref(incoming), "Kazuizhi AI Gateway", None, None, None, 0, ctypes.byref(outgoing)):
        raise OSError("Windows DPAPI 加密失败")
    try:
        protected = ctypes.string_at(outgoing.pbData, outgoing.cbData)
        return base64.b64encode(protected).decode("ascii")
    finally:
        kernel32.LocalFree(outgoing.pbData)


def _unprotect_windows(encoded):
    if os.name != "nt" or not encoded:
        return ""
    protected = base64.b64decode(encoded.encode("ascii"))
    buffer = ctypes.create_string_buffer(protected)
    incoming = _DATA_BLOB(len(protected), ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)))
    outgoing = _DATA_BLOB()
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    if not crypt32.CryptUnprotectData(ctypes.byref(incoming), None, None, None, None, 0, ctypes.byref(outgoing)):
        return ""
    try:
        return ctypes.string_at(outgoing.pbData, outgoing.cbData).decode("utf-8")
    finally:
        kernel32.LocalFree(outgoing.pbData)


def _api_key():
    environment = str(os.environ.get("OPENAI_API_KEY") or "").strip()
    if environment:
        return environment, "environment"
    saved = _config()
    secret = _unprotect_windows(str(saved.get("protected_api_key") or ""))
    return (secret, "windows_dpapi") if secret else ("", "none")


def gateway_status():
    config = _config()
    state = _state()
    key, source = _api_key()
    configured = bool(key)
    last_success = state.get("last_success_at")
    last_error = state.get("last_error")
    if configured and last_success and not last_error:
        label = "AI大脑在线"
        status = "ready"
    elif configured:
        label = "已配置，等待验证"
        status = "configured"
    else:
        label = "需要一次配置"
        status = "not_configured"
    return {
        "id": "chatgpt_ai_gateway",
        "provider": "OpenAI",
        "status": status,
        "status_label": label,
        "configured": configured,
        "credential_source": source,
        "model": str(os.environ.get("KAZUIZHI_OPENAI_MODEL") or config.get("model") or DEFAULT_MODEL),
        "endpoint": DEFAULT_ENDPOINT,
        "last_success_at": last_success,
        "last_error": last_error,
        "last_kind": state.get("last_kind"),
        "truth_rule": "只有真实API返回且通过本地结构校验才算ChatGPT已处理；API密钥不会返回给网页。",
    }


def configure_gateway(payload):
    values = payload if isinstance(payload, dict) else {}
    key = str(values.get("api_key") or "").strip()
    if not key.startswith("sk-") or len(key) < 20:
        raise ValueError("请输入有效的 OpenAI API Key")
    model = str(values.get("model") or DEFAULT_MODEL).strip()[:80]
    if not re.fullmatch(r"[A-Za-z0-9._:-]{2,80}", model):
        raise ValueError("模型名称格式不正确")
    config = {
        "provider": "openai",
        "enabled": True,
        "model": model,
        "endpoint": DEFAULT_ENDPOINT,
        "protected_api_key": _protect_windows(key),
        "configured_at": now_iso(),
    }
    write_json(CONFIG_PATH, config)
    _save_state(last_error=None)
    return gateway_status()


def clear_gateway():
    write_json(CONFIG_PATH, {"provider": "openai", "enabled": False, "model": DEFAULT_MODEL})
    _save_state(last_error=None, last_success_at=None)
    return gateway_status()


def _extract_text(response):
    direct = response.get("output_text") if isinstance(response, dict) else None
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    texts = []
    for item in response.get("output", []) if isinstance(response, dict) else []:
        for content in item.get("content", []) if isinstance(item, dict) else []:
            if isinstance(content, dict) and content.get("type") in {"output_text", "text"}:
                text = content.get("text")
                if isinstance(text, str) and text.strip():
                    texts.append(text.strip())
    return "\n".join(texts).strip()


def _parse_json_text(text):
    value = str(text or "").strip()
    if value.startswith("```"):
        value = re.sub(r"^```(?:json)?\s*", "", value, flags=re.I)
        value = re.sub(r"\s*```$", "", value)
    try:
        parsed = json.loads(value)
    except json.JSONDecodeError as error:
        raise ValueError("ChatGPT返回的内容不是有效JSON") from error
    if not isinstance(parsed, dict):
        raise ValueError("ChatGPT结构化返回必须是JSON对象")
    return parsed


def _http_transport(payload, api_key):
    request = urllib.request.Request(
        DEFAULT_ENDPOINT,
        data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as error:
        detail = error.read().decode("utf-8", errors="replace")[:MAX_ERROR]
        raise ValueError(f"OpenAI API HTTP {error.code}: {detail}") from error
    except urllib.error.URLError as error:
        raise ValueError(f"OpenAI API连接失败: {error.reason}") from error


def _call(kind, request_item, transport=None):
    key, _ = _api_key()
    if not key:
        raise ValueError("AI Gateway 尚未配置 OpenAI API Key")
    model = gateway_status()["model"]
    if kind == "content_production":
        contract = (
            "只返回一个JSON对象，不要Markdown。顶层必须含kind='content_production'、video_id、campaign_id、production_plan。"
            "production_plan必须符合kazuizhi-content-production/v1：schema,version,campaign_id,objective,target_platforms,topic,"
            "pain_point,titles,script,storyboard,voice,subtitle,cover,cta,output,qc,material_policy。storyboard至少1项；"
            "没有真实维修证据时不得把AI画面写成真实案例，required_real镜头可降级为info_card。老板最终审核不可绕过。"
        )
    else:
        contract = (
            "只返回一个JSON对象，不要Markdown。顶层必须含kind='content_qc'、video_id、candidate_id、decision、score、"
            "reasons、shot_feedback。decision只能是pass或rework。不得替老板执行最终发布审核。"
        )
    prompt = (
        "你是卡嘴子自治运营系统的唯一ChatGPT总决策大脑。根据下面真实Mission/R7/R8上下文完成当前任务。"
        "不得伪造平台回执、咨询、订单、维修现场或素材权利。" + contract + "\n\nREQUEST_JSON:\n" +
        json.dumps(request_item, ensure_ascii=False, separators=(",", ":"))
    )
    payload = {"model": model, "input": prompt, "max_output_tokens": 7000}
    raw = (transport or _http_transport)(payload, key)
    parsed = _parse_json_text(_extract_text(raw))
    if str(parsed.get("kind") or kind) != kind:
        raise ValueError("ChatGPT返回kind与当前任务不一致")
    return parsed


def _recover_retry_exhausted():
    data = cf._load()
    changed = False
    for video in data.get("videos", []):
        handoff = video.get("chatgpt_handoff") if isinstance(video.get("chatgpt_handoff"), dict) else {}
        if video.get("status") != "异常待处理" or handoff.get("phase") != "retry_exhausted":
            continue
        kind = handoff.get("kind")
        video["status"] = "等待ChatGPT质检" if kind == "content_qc" else "等待ChatGPT策划"
        video["bottleneck"] = "AI Gateway已配置，正在恢复直接ChatGPT调用"
        video["auto_action"] = "跳过已失效的无限文件桥等待，改由AI Gateway直接处理"
        handoff["phase"] = "gateway_recovering"
        handoff["updated_at"] = now_iso()
        changed = True
    if changed:
        cf._save(data)
    return changed


def run_once(limit=2, transport=None):
    status = gateway_status()
    if not status.get("configured"):
        return {"processed": 0, "status": status, "reason": "not_configured"}
    _recover_retry_exhausted()
    processed = 0
    errors = []

    planning = cf.pending_chatgpt_handoff(limit=max(1, int(limit or 1))).get("items", [])
    for item in planning:
        if processed >= limit:
            break
        try:
            result = _call("content_production", item, transport=transport)
            plan = result.get("production_plan") if isinstance(result.get("production_plan"), dict) else result
            cf.apply_chatgpt_plan({
                "video_id": item.get("video_id"),
                "campaign_id": item.get("campaign_id"),
                "production_plan": plan,
            })
            processed += 1
            _save_state(last_success_at=now_iso(), last_error=None, last_kind="content_production")
        except (OSError, ValueError, TypeError, KeyError) as error:
            message = str(error)[:MAX_ERROR]
            errors.append({"kind": "content_production", "video_id": item.get("video_id"), "error": message})
            _save_state(last_error=message, last_kind="content_production")
            try:
                cf.update_runtime_state(
                    item.get("video_id"),
                    bottleneck="AI Gateway暂时调用失败，保留同步桥作为备用通道",
                    auto_action="系统稍后自动重试；不会重复创建任务",
                    last_error=message,
                )
            except (OSError, ValueError):
                pass
            break

    if processed < limit:
        qc_reader = getattr(cf, "pending_chatgpt_qc_handoff", None)
        qc_items = qc_reader(limit=limit - processed).get("items", []) if callable(qc_reader) else []
        for item in qc_items:
            if processed >= limit:
                break
            try:
                result = _call("content_qc", item, transport=transport)
                cf.apply_chatgpt_qc({
                    "video_id": item.get("video_id"),
                    "candidate_id": item.get("candidate_id"),
                    "decision": result.get("decision"),
                    "score": result.get("score"),
                    "reasons": result.get("reasons") or [],
                    "shot_feedback": result.get("shot_feedback") or [],
                })
                processed += 1
                _save_state(last_success_at=now_iso(), last_error=None, last_kind="content_qc")
            except (OSError, ValueError, TypeError, KeyError) as error:
                message = str(error)[:MAX_ERROR]
                errors.append({"kind": "content_qc", "video_id": item.get("video_id"), "error": message})
                _save_state(last_error=message, last_kind="content_qc")
                break

    return {"processed": processed, "errors": errors, "status": gateway_status()}
