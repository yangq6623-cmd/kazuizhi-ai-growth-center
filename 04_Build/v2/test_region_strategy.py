import json
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SRC))

sandbox = Path(tempfile.mkdtemp(prefix="kazuizhi-region-strategy-"))
os.environ["LOCALAPPDATA"] = str(sandbox)
report_path = sandbox / "public_signals.json"
os.environ["KAZUIZHI_AI_REPORT_PATH"] = str(report_path)

try:
    report_path.write_text(json.dumps({
        "keywords": [
            "涟水空调维修避坑", "涟水水电维修", "淮阴区家电维修",
            "清江浦上门维修", "南京本地维修", "上海租房维修",
        ]
    }, ensure_ascii=False), encoding="utf-8")

    from analytics.business_metrics import import_snapshot
    from core.decision_center import refresh_decision_center
    from core.region_strategy import build_region_strategy

    import_snapshot({
        "source": "test-readonly-aggregate",
        "as_of": "2026-09-18 09:30:00",
        "window": "today",
        "by_region": {"涟水县": 12, "淮阴区": 5, "清江浦区": 4, "南京市": 2},
        "mini_program_visits": 20,
        "repair_requests": 4,
        "new_orders": 2,
    })

    strategy = build_region_strategy()
    if strategy.get("schema") != "kazuizhi-region-strategy/v1":
        raise AssertionError(f"Unexpected region schema: {strategy.get('schema')}")
    rows = strategy.get("regions", [])
    by_tier = {row.get("tier"): row for row in rows}
    for tier in ("S", "A", "B", "C", "D"):
        if tier not in by_tier:
            raise AssertionError(f"Missing regional strategy tier: {tier}")
    if by_tier["S"].get("name") != "涟水县" or by_tier["S"].get("work_share_pct") != 50:
        raise AssertionError(f"Core sample region policy mismatch: {by_tier['S']}")
    if by_tier["A"].get("work_share_pct") != 30 or by_tier["B"].get("work_share_pct") != 15 or by_tier["C"].get("work_share_pct") != 5:
        raise AssertionError("Regional work-share policy must remain 50/30/15/5")
    if strategy.get("resource_policy", {}).get("total_pct") != 100:
        raise AssertionError("Regional non-financial work share must total 100%")
    if by_tier["S"].get("public_signal_count", 0) < 2:
        raise AssertionError("Lianshui public research signals were not recognized")
    if by_tier["A"].get("verified_region_aggregate") != 9:
        raise AssertionError(f"Huai'an non-Lianshui aggregate mismatch: {by_tier['A']}")
    if "不自动修改" not in strategy.get("rules", {}).get("platform_opening", ""):
        raise AssertionError("Region-open safety boundary missing")
    if "不代表市场份额" not in strategy.get("rules", {}).get("truth", ""):
        raise AssertionError("Regional readiness truth boundary missing")

    decision = refresh_decision_center()
    if decision.get("region_strategy", {}).get("schema") != "kazuizhi-region-strategy/v1":
        raise AssertionError("Decision center did not include regional strategy")
    if not any("区域" in str(item.get("action")) for item in decision.get("manager_decisions", [])):
        raise AssertionError("R7 manager did not surface a regional allocation decision")
    if "跨区域" not in decision.get("chatgpt_handoff", {}).get("purpose", ""):
        raise AssertionError("ChatGPT handoff is not region-aware")

    ui = (SRC / "web" / "region_strategy.js").read_text(encoding="utf-8")
    for token in ("区域作战中心 V1", "S 涟水 · 核心样板", "A 淮安 · 主战区", "B 江苏 · 扩张准备", "C 浙江/上海 · 战略储备", "更新区域判断", "运营准备度"):
        if token not in ui:
            raise AssertionError(f"Regional UI contract missing: {token}")
    forms = (SRC / "web" / "forms.js").read_text(encoding="utf-8")
    if "region_strategy.js" not in forms:
        raise AssertionError("Regional strategy UI is not loaded by the dashboard")

    print("PASS: regional command center, 50/30/15/5 work allocation, evidence scoring, region-open guardrail and ChatGPT region-aware handoff")
finally:
    shutil.rmtree(sandbox, ignore_errors=True)
