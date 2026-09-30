"""Browser-first GEO validation for no-API operation.

The browser path is the default Phase-1 execution mode when the owner does not
want paid APIs. It supports manual execution today and future ChatGPT Work /
browser-agent execution through the same contract. Only real external AI web
sessions may produce A-level Evidence / Receipt.
"""
from __future__ import annotations

import hashlib
import urllib.parse

from core import geo_validation as geo
from core.storage import now_iso

EXECUTOR_ID = "external_ai_browser"
PROVIDER = "browser_external_ai"

PLATFORMS = {
    "chatgpt_web": "ChatGPT 网页版",
    "gemini_web": "Gemini 网页版",
    "copilot_web": "Copilot 网页版",
    "qwen_web": "通义千问网页版",
    "deepseek_web": "DeepSeek 网页版",
    "doubao_web": "豆包网页版",
    "custom_web": "其他真实外部 AI 网页",
}


def status():
    return {
        "id": EXECUTOR_ID,
        "provider": PROVIDER,
        "mode": "browser",
        "test_method": "browser",
        "requires_api": False,
        "ready": True,
        "manual_supported": True,
        "work_handoff_supported": True,
        "platforms": [{"id": key, "label": value} for key, value in PLATFORMS.items()],
        "reason": "无需API。可由人工或后续ChatGPT Work在真实外部AI网页执行；遇到登录/验证码时进入待我处理。",
        "truth_rule": "只有真实外部AI网页会话的原始回答和外部页面证据才能写入A级GEO Evidence；本地模型结果不计正式成绩。",
    }


def _external_https_url(value: str) -> str:
    raw = str(value or "").strip()
    parsed = urllib.parse.urlsplit(raw)
    host = (parsed.hostname or "").lower()
    if parsed.scheme.lower() != "https" or not host:
        raise ValueError("browser_geo_receipt_requires_external_https_url")
    if host in {"127.0.0.1", "localhost", "::1"} or host.endswith(".local"):
        raise ValueError("browser_geo_receipt_cannot_use_local_url")
    return raw


def contract(task, platform="custom_web"):
    task = dict(task or {})
    platform = str(platform or "custom_web").strip()
    if platform not in PLATFORMS:
        platform = "custom_web"
    return {
        "schema": "kazuizhi-geo-browser-contract/v1",
        "executor_id": EXECUTOR_ID,
        "platform": platform,
        "platform_label": PLATFORMS[platform],
        "task_id": task.get("task_id"),
        "run_id": task.get("run_id"),
        "question_id": task.get("question_id"),
        "question_text": task.get("question_text"),
        "instructions": [
            "在真实外部AI网页版提交原始问题，不添加品牌提示或诱导词。",
            "保存完整原始回答，不对回答内容进行润色或改写。",
            "保存真实外部页面URL；如有引用链接一并保留。",
            "如遇登录、验证码、OAuth或账号权限问题，停止当前任务并进入待我处理。",
        ],
        "required_receipt_fields": ["task_id", "platform", "session_url", "raw_answer"],
        "optional_receipt_fields": ["citation_urls", "model", "model_version", "screenshot_path", "evidence_ref", "tested_at"],
        "api_required": False,
        "future_work_handoff": True,
    }


def record_browser_result(payload):
    values = dict(payload or {})
    task_id = str(values.get("task_id") or "").strip()
    if not task_id:
        raise ValueError("task_id_required")
    platform = str(values.get("platform") or values.get("provider") or "custom_web").strip()
    if platform not in PLATFORMS:
        platform = "custom_web"
    session_url = _external_https_url(values.get("session_url"))
    raw_answer = str(values.get("raw_answer") or "").strip()
    if not raw_answer:
        raise ValueError("browser_geo_receipt_requires_raw_answer")
    citation_urls = values.get("citation_urls") or []
    if isinstance(citation_urls, str):
        citation_urls = [item.strip() for item in citation_urls.splitlines() if item.strip()]
    proof_seed = f"{task_id}|{platform}|{session_url}|{values.get('tested_at') or ''}"
    evidence_ref = str(values.get("evidence_ref") or "").strip() or (
        "browser-session:" + hashlib.sha256(proof_seed.encode("utf-8")).hexdigest()[:20]
    )
    return geo.record_result(
        {
            "task_id": task_id,
            "provider": platform,
            "model": str(values.get("model") or PLATFORMS[platform]),
            "model_version": str(values.get("model_version") or "web-product"),
            "test_method": "browser",
            "raw_answer": raw_answer,
            "citation_urls": citation_urls,
            "session_url": session_url,
            "screenshot_path": str(values.get("screenshot_path") or ""),
            "evidence_ref": evidence_ref,
            "tested_at": str(values.get("tested_at") or now_iso()),
            "evidence_level": "A",
        }
    )
