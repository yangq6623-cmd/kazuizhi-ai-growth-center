"""Regional operations strategy for the Kazuizhi autonomous growth loop.

The strategy makes geographic priorities explicit without pretending that a
strategic tier equals market demand, orders, or an opened service area. It uses
only locally stored public research signals and verified aggregate business
snapshots as evidence. R7 may use the output to prioritize non-financial work,
but it never opens a service region or changes payment/settlement settings.
"""

from analytics.business_metrics import build_analytics, current_snapshot
from core.storage import now_iso, write_json
from promotion.content_center import list_keywords


REGION_STRATEGY_PATH = "r7/region_strategy.json"

REGION_POLICY = (
    {
        "id": "lianshui",
        "name": "涟水县",
        "tier": "S",
        "role": "核心样板区",
        "mode": "core",
        "work_share_pct": 50,
        "priority_base": 45,
        "aliases": ("涟水", "涟水县"),
        "objective": "做深本地维修需求、内容、用户转化和服务供给闭环，形成可复制样板。",
    },
    {
        "id": "huaian_main",
        "name": "淮安其他区县",
        "tier": "A",
        "role": "淮安主战区",
        "mode": "main",
        "work_share_pct": 30,
        "priority_base": 35,
        "aliases": ("淮安", "淮安市", "淮阴", "淮阴区", "清江浦", "清江浦区", "洪泽", "洪泽区", "盱眙", "盱眙县", "金湖", "金湖县", "淮安区"),
        "objective": "持续做需求扫描、内容预热、SEO/GEO、本地供给准备，按证据选择下一批重点区县。",
    },
    {
        "id": "jiangsu_expand",
        "name": "江苏其他城市",
        "tier": "B",
        "role": "扩张准备区",
        "mode": "prepare",
        "work_share_pct": 15,
        "priority_base": 25,
        "aliases": ("江苏", "南京", "苏州", "无锡", "常州", "南通", "扬州", "镇江", "泰州", "盐城", "宿迁", "徐州", "连云港"),
        "objective": "建立关键词、用户痛点、竞争观察、师傅供给和本地内容素材储备，不抢跑正式开放。",
    },
    {
        "id": "zhejiang_shanghai_reserve",
        "name": "浙江 / 上海",
        "tier": "C",
        "role": "战略储备区",
        "mode": "reserve",
        "work_share_pct": 5,
        "priority_base": 15,
        "aliases": ("浙江", "杭州", "宁波", "温州", "嘉兴", "湖州", "绍兴", "金华", "台州", "舟山", "衢州", "丽水", "上海"),
        "objective": "低频观察趋势、用户痛点、平台内容和竞争变化，为后续开放做战备储存。",
    },
    {
        "id": "national_reserve",
        "name": "全国其他地区",
        "tier": "D",
        "role": "长期储备",
        "mode": "monitor",
        "work_share_pct": 0,
        "priority_base": 5,
        "aliases": (),
        "objective": "暂不投入日常执行资源，只保留长期机会监测。",
    },
)


def _keyword_signal_counts():
    items = list_keywords().get("items", [])
    terms = [
        str(item.get("keyword") or "")
        for item in items
        if item.get("source") == "historical_public_signal"
    ]
    counts = {}
    for policy in REGION_POLICY:
        aliases = policy["aliases"]
        if not aliases:
            counts[policy["id"]] = 0
            continue
        if policy["id"] == "huaian_main":
            # Do not double-count the core sample area in the broader Huai'an tier.
            counts[policy["id"]] = sum(
                1 for term in terms
                if any(alias in term for alias in aliases) and "涟水" not in term
            )
        elif policy["id"] == "jiangsu_expand":
            counts[policy["id"]] = sum(
                1 for term in terms
                if any(alias in term for alias in aliases)
                and not any(city in term for city in ("淮安", "涟水", "淮阴", "清江浦", "洪泽", "盱眙", "金湖"))
            )
        else:
            counts[policy["id"]] = sum(1 for term in terms if any(alias in term for alias in aliases))
    return counts


def _verified_region_evidence(snapshot, policy):
    mapping = (snapshot or {}).get("by_region") or {}
    if not isinstance(mapping, dict) or not policy["aliases"]:
        return {"available": False, "value": None, "matched_labels": []}
    matched = []
    total = 0
    for label, value in mapping.items():
        text = str(label)
        if policy["id"] == "huaian_main" and "涟水" in text:
            continue
        if any(alias in text for alias in policy["aliases"]):
            matched.append(text)
            if isinstance(value, (int, float)) and not isinstance(value, bool):
                total += value
    return {
        "available": bool(matched),
        "value": total if matched else None,
        "matched_labels": matched[:8],
    }


def _readiness(policy, public_signals, verified, business_verified):
    # This is an operational planning score, not a market-size or revenue score.
    score = int(policy["priority_base"])
    score += min(20, int(public_signals) * 2)
    if verified.get("available"):
        score += 20
    if business_verified:
        score += 10
    if public_signals and verified.get("available"):
        score += 5
    score = min(100, score)
    if public_signals and verified.get("available"):
        confidence = "较高"
    elif public_signals or verified.get("available"):
        confidence = "中等"
    else:
        confidence = "较低"
    return score, confidence


def _recommendation(policy, score, public_signals, verified):
    mode = policy["mode"]
    evidence = public_signals > 0 or verified.get("available")
    if mode == "core":
        return "保持最高运营优先级；持续把需求、关键词、深度内容、短视频、师傅供给和订单转化放在同一个闭环里复盘。"
    if mode == "main":
        if score >= 60 and evidence:
            return "提高重点区县预热与供给准备，优先选择证据最强的区县做下一轮内容、SEO/GEO和师傅招募。"
        return "继续淮安全域需求扫描和内容预热；证据不足的区县不盲目扩大工作量。"
    if mode == "prepare":
        return "以关键词、用户痛点、竞争观察和师傅储备为主；达到准备阈值后再建议进入正式预热。"
    if mode == "reserve":
        return "维持低频战备采集，沉淀平台趋势、用户痛点和高表现内容基因，不提前承诺本地服务。"
    return "只做长期机会监测；没有新的证据时不占用日常运营资源。"


def build_region_strategy(analytics=None):
    analytics = analytics or build_analytics()
    snapshot = current_snapshot() or {}
    business_verified = analytics.get("status") == "verified"
    public_counts = _keyword_signal_counts()
    rows = []
    for policy in REGION_POLICY:
        signals = int(public_counts.get(policy["id"], 0))
        verified = _verified_region_evidence(snapshot, policy)
        score, confidence = _readiness(policy, signals, verified, business_verified)
        rows.append({
            "id": policy["id"],
            "name": policy["name"],
            "tier": policy["tier"],
            "role": policy["role"],
            "mode": policy["mode"],
            "work_share_pct": policy["work_share_pct"],
            "objective": policy["objective"],
            "readiness_score": score,
            "confidence": confidence,
            "public_signal_count": signals,
            "verified_region_aggregate": verified.get("value"),
            "verified_region_labels": verified.get("matched_labels", []),
            "recommendation": _recommendation(policy, score, signals, verified),
        })
    result = {
        "schema": "kazuizhi-region-strategy/v1",
        "generated_at": now_iso(),
        "headline": "淮安为当前主战场，涟水为核心样板；江苏做扩张准备，浙江/上海做战略储备。",
        "resource_policy": {
            "type": "non_financial_work_share",
            "total_pct": sum(row["work_share_pct"] for row in rows),
            "note": "比例表示AI员工非资金运营工作量建议，不代表广告预算、付款或市场份额。",
        },
        "regions": rows,
        "business_data": {
            "status": analytics.get("status"),
            "source": analytics.get("source"),
            "as_of": analytics.get("as_of"),
        },
        "rules": {
            "platform_opening": "R7 只提出区域开放/暂停建议，不自动修改小程序后台区域开放状态。",
            "reserve_regions": "战略储备区只做研究、内容素材和供给准备；未真实开放前不得宣称当地已可下单。",
            "truth": "运营准备度是基于战略优先级与当前可核验证据的计划分数，不代表市场份额、真实订单规模或平台开放状态。",
        },
    }
    write_json(REGION_STRATEGY_PATH, result)
    return result
