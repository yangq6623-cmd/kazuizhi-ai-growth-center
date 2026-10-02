"""R8-20 compatibility patch for the final Phase-2 analysis snapshot shape."""
from __future__ import annotations

from copy import deepcopy

from core import geo_analysis, geo_validation
from core import seo_geo_growth_intelligence as growth

_ORIGINAL_CONTROLLER_PRIORITIES = growth.controller_priorities


def _snapshot():
    snap = geo_analysis.snapshot()
    if int((snap.get("summary") or {}).get("tested") or 0) != int((geo_validation.dashboard().get("official") or {}).get("tested") or 0):
        snap = geo_analysis.refresh(geo_validation.receipts(1000))
    return snap


def provider_matrix():
    snap = _snapshot()
    summary = snap.get("summary") or {}
    return {
        "formal_evidence": int(summary.get("tested") or 0),
        "providers": deepcopy(summary.get("provider_comparison") or []),
        "truth": "仅统计最新正式A/B Evidence；C级辅助结果不进入矩阵",
    }


def third_party_source_gaps():
    snap = _snapshot()
    summary = snap.get("summary") or {}
    source_rows = list(summary.get("source_domains") or [])
    domains = [x for x in source_rows if not x.get("official_domain")]
    official_domain_seen = any(x.get("official_domain") for x in source_rows)
    actions = []
    for row in domains[:20]:
        actions.append({
            "domain": row.get("domain"),
            "question_count": row.get("question_count"),
            "action": "研究该真实来源为何被AI引用；仅通过合法公开资料/合作/资料完善增加可信可引用信息",
            "auto_post": False,
        })
    if not official_domain_seen:
        actions.insert(0, {"domain": "kazuizhi.com", "action": "优先完善官网事实页、FAQ、服务区域和可引用结构", "auto_post": False})
    return {
        "observed_third_party_domains": domains[:30],
        "actions": actions[:30],
        "truth": "不自动批量发垃圾外链/论坛；只依据真实引用来源生成合规建设任务",
    }


def controller_priorities():
    result = dict(_ORIGINAL_CONTROLLER_PRIORITIES())
    result["truth"] = "优先级只依据真实搜索、咨询、任务和订单信号。"
    return result


growth.provider_matrix = provider_matrix
growth.third_party_source_gaps = third_party_source_gaps
growth.controller_priorities = controller_priorities

# R8-22 is an additive control-plane closure, not a replacement for the
# R8-20/R8-21 SEO/GEO stack.  Importing it here guarantees that the real
# desktop entrypoint activates Command->Mission->Plan convergence before
# run.py captures scheduler function references.
from backend import r8_22_autonomy_convergence_patch as _r8_22_autonomy_convergence_patch  # noqa: E402,F401
