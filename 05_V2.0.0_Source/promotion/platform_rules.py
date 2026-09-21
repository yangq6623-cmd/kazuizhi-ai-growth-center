"""Auditable publication guardrails for the R8 content factory.

The rule center deliberately separates immutable safety gates from ChatGPT's
operational strategy.  Platform-specific values below are conservative internal
limits, not claims about current public platform policy.  ChatGPT may optimize
hooks, titles, pacing and timing, but cannot override the owner approval gate,
truthfulness, verified-account requirement or real publication receipts.
"""

from __future__ import annotations

from collections import Counter

from core.storage import now_iso, read_json, write_json


LEARNING_FILE = "r8/platform_rule_learning.json"
RISKY_TERMS = ("最低价", "全城第一", "保证", "百分百", "100%", "假一赔", "绝对")
PLATFORMS = ("抖音", "快手", "小红书", "视频号", "微博", "B站", "通用")

# Conservative internal caps used to keep one executable rule set stable.  They
# can be revised only after verified policy review; they are not represented as
# official limits published by the platforms.
INTERNAL_CAPS = {
    "抖音": {"title": 55, "caption": 1000, "daily_publish": 3},
    "快手": {"title": 55, "caption": 1000, "daily_publish": 3},
    "小红书": {"title": 60, "caption": 1000, "daily_publish": 3},
    "视频号": {"title": 60, "caption": 1000, "daily_publish": 3},
    "微博": {"title": 70, "caption": 1000, "daily_publish": 3},
    "B站": {"title": 80, "caption": 1000, "daily_publish": 3},
    "通用": {"title": 60, "caption": 1000, "daily_publish": 3},
}


def snapshot():
    return {
        "schema": "kazuizhi-platform-rule-center/v1",
        "policy_source": "internal_verified_guardrails",
        "hard_rules": [
            "必须存在老板最终审核记录，不能绕过人工发布门禁",
            "发布账号必须真实登录并验证可发布",
            "真实案例/维修过程不得由AI生成画面冒充",
            "绝对化、无法验证的宣传承诺直接阻断",
            "成功发布必须回收真实平台内容ID和URL",
        ],
        "strategy_owner": "ChatGPT",
        "strategy_fields": ["hook", "title", "caption", "cover", "pacing", "schedule_hint", "cta"],
        "internal_caps": INTERNAL_CAPS,
        "note": "平台运营策略由ChatGPT结合实际数据决定；硬安全规则固定。平台公开规则变化须经验证后再更新内部规则。",
    }


def _adaptation(video, platform):
    plan = video.get("production_plan") if isinstance(video, dict) else None
    mapping = (plan or {}).get("platform_adaptation")
    if not isinstance(mapping, dict):
        return {}
    value = mapping.get(platform) or mapping.get("通用") or {}
    return value if isinstance(value, dict) else {}


def suggested_publish_fields(video, platform):
    adaptation = _adaptation(video, platform)
    plan = video.get("production_plan") if isinstance(video, dict) else {}
    titles = (plan or {}).get("titles") or []
    return {
        "title": str(adaptation.get("title") or (titles[0] if titles else "")).strip(),
        "caption": str(adaptation.get("caption") or video.get("caption_direction") or "").strip(),
        "scheduled_for": str(adaptation.get("schedule_hint") or "由ChatGPT结合账号状态与真实历史效果选择").strip(),
        "hook": str(adaptation.get("hook") or "").strip(),
        "cover_title": str(adaptation.get("cover_title") or "").strip(),
        "pacing": str(adaptation.get("pacing") or "").strip(),
        "source": "chatgpt_platform_adaptation" if adaptation else "generic_plan_fallback",
    }


def evaluate(video, account, title, caption):
    platform = str((account or {}).get("platform") or "通用").strip()
    caps = INTERNAL_CAPS.get(platform, INTERNAL_CAPS["通用"])
    title = str(title or "").strip()
    caption = str(caption or "").strip()
    hard_issues = []
    warnings = []

    if not isinstance(video, dict) or video.get("status") != "已授权发布" or not video.get("approved_at"):
        hard_issues.append("未通过老板最终审核")
    if not isinstance(account, dict) or account.get("connection_status") != "已验证可发布":
        hard_issues.append("账号尚未验证可发布")
    if not title:
        hard_issues.append("平台标题为空")
    if len(title) > int(caps["title"]):
        hard_issues.append(f"平台标题超过内部安全上限 {caps['title']} 字")
    if len(caption) > int(caps["caption"]):
        hard_issues.append(f"平台配文超过内部安全上限 {caps['caption']} 字")

    combined = (title + " " + caption).lower()
    if any(term.lower() in combined for term in RISKY_TERMS):
        hard_issues.append("文案包含绝对化或无法验证的宣传承诺")

    plan = video.get("production_plan") if isinstance(video, dict) else None
    target_platforms = (plan or {}).get("target_platforms") or []
    if target_platforms and "通用" not in target_platforms and platform not in target_platforms:
        warnings.append("该平台不在ChatGPT当前生产合同的目标平台内，建议先重新做平台适配")

    required_real = {
        str(shot.get("shot_id")): bool(shot.get("required_real"))
        for shot in ((plan or {}).get("storyboard") or []) if isinstance(shot, dict)
    }
    latest = next((x for x in reversed(video.get("candidates") or []) if x.get("exists")), None)
    for source in (latest or {}).get("source_summary") or []:
        shot_id = str(source.get("shot_id") or "")
        if required_real.get(shot_id) and source.get("source") == "ai_generated":
            hard_issues.append(f"镜头 {shot_id} 要求真实素材，却被AI生成素材替代")

    return {
        "passed": not hard_issues,
        "platform": platform,
        "hard_issues": hard_issues,
        "warnings": warnings,
        "internal_caps": caps,
        "checked_at": now_iso(),
        "strategy": suggested_publish_fields(video, platform),
    }


def record_outcome(platform, result, metadata=None):
    store = read_json(LEARNING_FILE, {"schema": 1, "items": []})
    if not isinstance(store, dict):
        store = {"schema": 1, "items": []}
    items = store.setdefault("items", [])
    items.append({
        "recorded_at": now_iso(),
        "platform": str(platform or "通用"),
        "result": str(result or "unknown"),
        "metadata": metadata if isinstance(metadata, dict) else {},
    })
    store["items"] = items[-500:]
    write_json(LEARNING_FILE, store)
    return learning_summary(store)


def learning_summary(store=None):
    store = store if isinstance(store, dict) else read_json(LEARNING_FILE, {"items": []})
    items = store.get("items", []) if isinstance(store, dict) else []
    by_platform = Counter(str(x.get("platform") or "通用") for x in items)
    successes = Counter(str(x.get("platform") or "通用") for x in items if x.get("result") == "成功")
    return {
        "samples": len(items),
        "platforms": {
            platform: {
                "samples": by_platform[platform],
                "verified_successes": successes[platform],
            }
            for platform in sorted(by_platform)
        },
        "note": "当前只学习真实发布回执；曝光、咨询、订单等效果数据接入后再扩展策略学习。",
    }
