"""Optional ChatGPT total-brain analysis for GEO Phase 2.

This module interprets the deterministic analysis pack only. It never creates
or changes GEO evidence, never changes scores, and never executes tasks.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request

from core import geo_analysis
from core import storage
from integrations import ai_gateway

ANALYSIS_PATH = "geo_validation/chatgpt_analysis.json"
MAX_RESPONSE_BYTES = 512 * 1024

SCHEMA = {
    "type": "object",
    "properties": {
        "executive_summary": {"type": "string"},
        "key_findings": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "title": {"type": "string"},
                    "detail": {"type": "string"},
                    "evidence_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["title", "detail", "evidence_ids"],
                "additionalProperties": False,
            },
        },
        "comparison": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "dimension": {"type": "string"},
                    "observation": {"type": "string"},
                    "evidence_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["dimension", "observation", "evidence_ids"],
                "additionalProperties": False,
            },
        },
        "gap_priorities": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "gap_code": {"type": "string"},
                    "reason": {"type": "string"},
                    "evidence_ids": {"type": "array", "items": {"type": "string"}},
                },
                "required": ["gap_code", "reason", "evidence_ids"],
                "additionalProperties": False,
            },
        },
        "candidate_actions": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "action": {"type": "string"},
                    "why": {"type": "string"},
                    "scope": {"type": "string"},
                },
                "required": ["action", "why", "scope"],
                "additionalProperties": False,
            },
        },
        "decision_condition": {"type": "string"},
        "uncertainties": {"type": "array", "items": {"type": "string"}},
    },
    "required": [
        "executive_summary",
        "key_findings",
        "comparison",
        "gap_priorities",
        "candidate_actions",
        "decision_condition",
        "uncertainties",
    ],
    "additionalProperties": False,
}


def _endpoint(value):
    raw = str(value or "").strip()
    parsed = urllib.parse.urlsplit(raw)
    if parsed.scheme.lower() != "https":
        raise ValueError("ChatGPT总脑分析只允许HTTPS云端Responses接口")
    if not parsed.hostname:
        raise ValueError("云端Responses接口地址无效")
    path = (parsed.path or "").rstrip("/")
    if path != "/v1/responses":
        raise ValueError("ChatGPT总脑分析要求 /v1/responses 端点")
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise ValueError("Responses接口地址不能包含账号、查询参数或片段")
    return raw


def status():
    route = ai_gateway._route_status("cloud")
    profile = ai_gateway._profile("cloud")
    key, source = ai_gateway._api_key("cloud")
    model = str(profile.get("model") or "").strip()
    endpoint = str(profile.get("endpoint") or "").strip()
    valid = False
    reason = ""
    try:
        _endpoint(endpoint)
        valid = True
    except ValueError as error:
        reason = str(error)
    ready = bool(route.get("configured") and route.get("verified") and key and model and valid)
    if not ready and not reason:
        reason = "云端模型尚未完成连接验证"
    saved = storage.read_json(ANALYSIS_PATH, {})
    return {
        "ready": ready,
        "model": model,
        "endpoint": endpoint if valid else "",
        "credential_source": source,
        "reason": reason,
        "saved_at": saved.get("generated_at") if isinstance(saved, dict) else "",
        "response_id": saved.get("response_id") if isinstance(saved, dict) else "",
    }


def _output_text(payload):
    direct = payload.get("output_text") if isinstance(payload, dict) else None
    if isinstance(direct, str) and direct.strip():
        return direct.strip()
    chunks = []
    for item in payload.get("output", []) if isinstance(payload, dict) else []:
        if not isinstance(item, dict) or item.get("type") != "message":
            continue
        for content in item.get("content", []) if isinstance(item.get("content"), list) else []:
            if isinstance(content, dict) and content.get("type") in {"output_text", "text"}:
                value = content.get("text")
                if isinstance(value, str) and value.strip():
                    chunks.append(value.strip())
    return "\n".join(chunks).strip()


def run():
    current = status()
    if not current.get("ready"):
        raise PermissionError(current.get("reason") or "ChatGPT总脑分析接口未就绪")
    pack = geo_analysis.analysis_pack()
    if not pack.get("question_results"):
        raise ValueError("暂无A/B级GEO Evidence，暂时不能进行总脑分析")
    profile = ai_gateway._profile("cloud")
    api_key, _ = ai_gateway._api_key("cloud")
    endpoint = _endpoint(profile.get("endpoint"))
    input_text = (
        "你是卡嘴子AI增长中心的总控分析大脑。下面的数据已经由确定性规则从真实A/B GEO Evidence中提取。"
        "你的任务是解释事实、比较问题类型、指出缺口，并给出候选行动供老板审核。"
        "严禁修改Evidence、重新计算正式指标、把候选行动直接视为已批准任务。"
        "所有结论必须能够追溯到提供的evidence_id；没有证据就明确写不确定。\n\n"
        + json.dumps(pack, ensure_ascii=False, separators=(",", ":"))
    )
    body = {
        "model": current["model"],
        "input": input_text,
        "store": False,
        "temperature": 0.2,
        "max_output_tokens": 2400,
        "text": {"format": {"type": "json_schema", "name": "geo_phase2_analysis", "strict": True, "schema": SCHEMA}},
    }
    request = urllib.request.Request(
        endpoint,
        data=json.dumps(body, ensure_ascii=False).encode("utf-8"),
        headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json", "Accept": "application/json", "User-Agent": "Kazuizhi-R8-19-GEO-Phase2/1.0"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=90) as response:
            raw = response.read(MAX_RESPONSE_BYTES + 1)
        if len(raw) > MAX_RESPONSE_BYTES:
            raise RuntimeError("ChatGPT总脑分析响应超过安全大小限制")
        payload = json.loads(raw.decode("utf-8") or "{}")
    except urllib.error.HTTPError as error:
        detail = error.read(64 * 1024).decode("utf-8", errors="replace")[:800]
        raise RuntimeError(f"ChatGPT总脑分析 HTTP {error.code}: {detail}") from error
    except urllib.error.URLError as error:
        raise RuntimeError(f"ChatGPT总脑分析网络不可达: {error.reason}") from error
    except (ValueError, json.JSONDecodeError) as error:
        raise RuntimeError("ChatGPT总脑分析返回非有效JSON") from error

    text = _output_text(payload)
    if not text:
        raise RuntimeError("ChatGPT总脑分析未返回结构化文本")
    try:
        analysis = json.loads(text)
    except json.JSONDecodeError as error:
        raise RuntimeError("ChatGPT总脑分析输出不是有效JSON") from error
    if not isinstance(analysis, dict):
        raise RuntimeError("ChatGPT总脑分析输出结构无效")

    saved = {
        "analysis_version": "GEO-CHATGPT-ADVISORY-V1-20261001",
        "generated_at": storage.now_iso(),
        "response_id": str(payload.get("id") or ""),
        "model": str(payload.get("model") or current["model"]),
        "source_analysis_version": pack.get("analysis_version"),
        "official_evidence_count": len(pack.get("question_results") or []),
        "controller": "chatgpt",
        "advisory_only": True,
        "analysis": analysis,
    }
    storage.write_json(ANALYSIS_PATH, saved)
    return saved


def snapshot():
    return storage.read_json(ANALYSIS_PATH, {}) or {}
