"""Auditable publication guardrails and verified performance learning.

The rule center deliberately separates immutable safety gates from ChatGPT's
operational strategy. Platform-specific values below are conservative internal
limits, not claims about current public platform policy. ChatGPT may optimize
hooks, titles, pacing and timing using verified outcomes, but cannot override
the owner approval gate, truthfulness, account verification or real receipts.
"""

from __future__ import annotations

from collections import Counter, defaultdict

from core.storage import now_iso, read_json, write_json


LEARNING_FILE = "r8/platform_rule_learning.json"
RISKY_TERMS = ("最低价", "全城第一", "保证", "百分百", "100%", "假一赔", "绝对")
PLATFORMS = ("抖音", "快手", "小红书", "视频号", "微博", "B站", "通用")
CHECKPOINTS = {"24h", "72h", "7d"}
METRIC_SOURCES = {"official_api", "platform_export", "manual_verified"}
METRIC_FIELDS = (
    "impressions", "plays", "completions", "likes", "comments", "saves", "shares",
    "dms", "consultations", "orders", "completed_orders",
)

# Conservative internal caps used to keep one executable rule set stable. They
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
        "learning_inputs": ["真实发布回执", "24h真实指标", "72h真实指标", "7d真实指标"],
        "note": "平台运营策略由ChatGPT结合已验证效果数据决定；硬安全规则固定。平台公开规则变化须经验证后再更新内部规则。",
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

    # Once the owner has approved a candidate the video may already have one
    # platform plan and therefore carry a queue/publish status. Approval evidence,
    # not a transient status string, is the fixed gate.
    review = video.get("review") if isinstance(video, dict) else {}
    if (
        not isinstance(video, dict)
        or not video.get("approved_at")
        or not isinstance(review, dict)
        or review.get("decision") != "确认发布"
    ):
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


def _store():
    value = read_json(LEARNING_FILE, {"schema": 2, "receipts": [], "metrics": []})
    if not isinstance(value, dict):
        value = {"schema": 2, "receipts": [], "metrics": []}
    # migrate the v1 items list without losing old verified receipt evidence.
    if "items" in value and "receipts" not in value:
        value["receipts"] = value.get("items") or []
    value.setdefault("receipts", [])
    value.setdefault("metrics", [])
    value["schema"] = 2
    value.pop("items", None)
    return value


def record_outcome(platform, result, metadata=None):
    store = _store()
    receipts = store.setdefault("receipts", [])
    receipts.append({
        "recorded_at": now_iso(),
        "platform": str(platform or "通用"),
        "result": str(result or "unknown"),
        "metadata": metadata if isinstance(metadata, dict) else {},
    })
    store["receipts"] = receipts[-500:]
    write_json(LEARNING_FILE, store)
    return learning_summary(store)


def _number(value, name):
    try:
        number = float(value or 0)
    except (TypeError, ValueError):
        raise ValueError(f"{name}必须是数字") from None
    if number < 0:
        raise ValueError(f"{name}不能小于0")
    return int(number) if number.is_integer() else round(number, 4)


def record_metrics(platform, plan_id, checkpoint, metrics, source, metadata=None):
    checkpoint = str(checkpoint or "").strip()
    source = str(source or "").strip()
    if checkpoint not in CHECKPOINTS:
        raise ValueError("效果复盘时间点必须为24h、72h或7d")
    if source not in METRIC_SOURCES:
        raise ValueError("效果指标必须来自官方接口、平台导出或人工核验")
    if not str(plan_id or "").strip():
        raise ValueError("发布计划ID不能为空")
    raw = metrics if isinstance(metrics, dict) else {}
    values = {name: _number(raw.get(name, 0), name) for name in METRIC_FIELDS}
    store = _store()
    rows = store.setdefault("metrics", [])
    existing = next((
        x for x in rows
        if x.get("plan_id") == str(plan_id) and x.get("checkpoint") == checkpoint
    ), None)
    value = {
        "recorded_at": now_iso(),
        "platform": str(platform or "通用"),
        "plan_id": str(plan_id),
        "checkpoint": checkpoint,
        "source": source,
        "metrics": values,
        "metadata": metadata if isinstance(metadata, dict) else {},
    }
    if existing:
        existing.update(value)
    else:
        rows.append(value)
    store["metrics"] = rows[-1000:]
    write_json(LEARNING_FILE, store)
    return learning_summary(store)


def _safe_rate(numerator, denominator):
    return round(float(numerator) / float(denominator), 5) if denominator else None


def learning_summary(store=None):
    store = store if isinstance(store, dict) else _store()
    receipts = store.get("receipts", []) if isinstance(store, dict) else []
    metrics = store.get("metrics", []) if isinstance(store, dict) else []
    receipt_by_platform = Counter(str(x.get("platform") or "通用") for x in receipts)
    successes = Counter(str(x.get("platform") or "通用") for x in receipts if x.get("result") == "成功")
    effect_by_platform = Counter(str(x.get("platform") or "通用") for x in metrics)
    totals = defaultdict(lambda: {name: 0 for name in METRIC_FIELDS})
    checkpoints = defaultdict(Counter)
    for row in metrics:
        platform = str(row.get("platform") or "通用")
        checkpoints[platform][str(row.get("checkpoint") or "unknown")] += 1
        values = row.get("metrics") if isinstance(row.get("metrics"), dict) else {}
        for name in METRIC_FIELDS:
            totals[platform][name] += float(values.get(name) or 0)

    platforms = sorted(set(receipt_by_platform) | set(effect_by_platform))
    summaries = {}
    for platform in platforms:
        t = totals[platform]
        summaries[platform] = {
            "receipt_samples": receipt_by_platform[platform],
            "verified_successes": successes[platform],
            "effect_samples": effect_by_platform[platform],
            "checkpoints": dict(checkpoints[platform]),
            "totals": {name: int(value) if float(value).is_integer() else round(value, 4) for name, value in t.items()},
            "derived": {
                "play_rate": _safe_rate(t["plays"], t["impressions"]),
                "completion_rate": _safe_rate(t["completions"], t["plays"]),
                "consultation_rate": _safe_rate(t["consultations"], t["plays"]),
                "order_rate": _safe_rate(t["orders"], t["consultations"]),
                "completed_order_rate": _safe_rate(t["completed_orders"], t["orders"]),
            },
        }
    return {
        "samples": len(receipts) + len(metrics),
        "receipt_samples": len(receipts),
        "effect_samples": len(metrics),
        "platforms": summaries,
        "note": "只学习真实发布回执与已核验24h/72h/7d指标；ChatGPT可据此调整运营策略，但不能修改硬安全规则。",
    }
