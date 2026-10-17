"""Dynamic GPT director policy for the local content factory.

The owner UI stays simple. The director decides shot count and per-shot candidate
budget from the actual content, duration, pace and quality policy. Nothing in
this layer fixes a video to five shots or fixes every shot to three candidates.
"""
from __future__ import annotations

import re

from backend import ai_gateway_patch as _ai
from core.storage import read_json, write_json

POLICY_FILE = "r8/production_policy.json"
DEFAULT_POLICY = {
    "mode": "assisted",
    "quality": "high",
    "max_shots": 40,
}


def load_policy():
    data = read_json(POLICY_FILE, DEFAULT_POLICY)
    if not isinstance(data, dict):
        data = dict(DEFAULT_POLICY)
    result = dict(DEFAULT_POLICY)
    result.update({k: v for k, v in data.items() if k in result})
    if result["mode"] not in {"auto", "assisted", "manual"}:
        result["mode"] = "assisted"
    if result["quality"] not in {"fast", "standard", "high", "premium"}:
        result["quality"] = "high"
    try:
        result["max_shots"] = max(8, min(int(result.get("max_shots") or 40), 40))
    except (TypeError, ValueError):
        result["max_shots"] = 40
    return result


def save_policy(payload):
    current = load_policy()
    mode = str(payload.get("mode") or current["mode"]).strip()
    quality = str(payload.get("quality") or current["quality"]).strip()
    if mode not in {"auto", "assisted", "manual"}:
        raise ValueError("生产方式不正确")
    if quality not in {"fast", "standard", "high", "premium"}:
        raise ValueError("质量等级不正确")
    current.update({"mode": mode, "quality": quality})
    write_json(POLICY_FILE, current)
    return current


def _suggested_range(text):
    match = re.search(r"(?:目标时长|视频时长|时长)[:：]?\s*(\d{1,3})\s*秒", text or "")
    seconds = int(match.group(1)) if match else 30
    if seconds <= 15:
        return "3-7"
    if seconds <= 30:
        return "5-12"
    if seconds <= 60:
        return "8-24"
    if seconds <= 90:
        return "12-32"
    return "16-40"


def augment_director_payload(payload):
    """Append a dynamic production contract to AI-director requests only."""
    if not isinstance(payload, dict):
        return payload
    messages = payload.get("messages")
    if not isinstance(messages, list):
        return payload
    combined = "\n".join(str(m.get("content") or "") for m in messages if isinstance(m, dict))
    if "AI导演" not in combined and "director_summary" not in combined and "镜头" not in combined:
        return payload

    policy = load_policy()
    mode_text = {"auto": "全自动", "assisted": "用户提供内容+AI辅助", "manual": "人工细调"}[policy["mode"]]
    quality_text = {"fast": "快速测试", "standard": "标准", "high": "高质量", "premium": "精品"}[policy["quality"]]
    hint = _suggested_range(combined)
    instruction = (
        "\n\n【动态导演生产合同】\n"
        f"生产方式：{mode_text}；质量等级：{quality_text}。\n"
        "镜头总数不得写死。请根据视频总时长、文案密度、语速、内容类型、节奏和镜头语言自动决定。"
        f"当前时长对应的经验参考区间约为 {hint} 个镜头，但这不是硬规则。"
        f"安全上限为 {policy['max_shots']} 个镜头。\n"
        "每个镜头必须输出 importance 字段（S/A/B）和 candidate_count（1/2/3）。"
        "关键钩子、人物正脸、核心动作、关键结果可给2-3个候选；普通主镜头1-2个；过渡/B-roll通常1个。"
        "不要为了凑数量切镜头，也不要让所有镜头统一生成3个候选。\n"
        "必须尽量保持人物、服装、声音、场景、道具和视觉风格连续，并把连续性要求写入 consistency_locks。"
        "输出仍必须是原接口要求的合法JSON，不要输出解释文字。"
    )
    cloned = dict(payload)
    cloned_messages = []
    for item in messages:
        cloned_messages.append(dict(item) if isinstance(item, dict) else item)
    if cloned_messages and isinstance(cloned_messages[-1], dict):
        cloned_messages[-1]["content"] = str(cloned_messages[-1].get("content") or "") + instruction
    cloned["messages"] = cloned_messages
    return cloned


_original_proxy = _ai._proxy_local_chat


def _dynamic_proxy(payload):
    return _original_proxy(augment_director_payload(payload))


_ai._proxy_local_chat = _dynamic_proxy
