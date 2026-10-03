"""Release gate: keep the R8-23 Final #40 complete workbench intact.

This guard protects the user-facing baseline: the full left navigation and
each workspace must remain available.  Recovery-only UI layers are forbidden
because they replace the workbench shell instead of repairing it.
"""
from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "05_V2.0.0_Source"
RUN = SRC / "run.py"
WORKBENCH = SRC / "web" / "r8_10_workbench.js"
COORDINATOR = SRC / "web" / "r8_12_startup_coordinator.js"
SEO_BRIDGE = SRC / "web" / "r8_13_seo_geo_bridge.js"
GROWTH_OS = SRC / "web" / "r8_23_growth_os.js"
TRUTH_PATCH = SRC / "core" / "r8_20_growth_truth_patch.py"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> None:
    run = text(RUN)
    workbench = text(WORKBENCH)
    coordinator = text(COORDINATOR)
    seo_bridge = text(SEO_BRIDGE)
    growth_os = text(GROWTH_OS)
    truth_patch = text(TRUTH_PATCH)

    # The actual entrypoint must preserve the original final release chain.
    assert "r8_20_seo_geo_growth_patch" in run
    assert "R8-20 compatibility patch" in truth_patch
    for marker in ("r8_22_autonomy_convergence_patch", "r8_23_growth_os_patch"):
        assert marker in truth_patch, marker

    # Screenshot-level user contract: these are real navigation labels/pages,
    # not a simplified recovery dashboard.
    for marker in ("老板总控", "AI决策中心", "执行中心", "待我处理", "经营结果", "自进化中心"):
        assert marker in workbench, marker
    for marker in ("内容创导", "SEO/GEO增长"):
        assert marker in coordinator or marker in seo_bridge, marker
    for marker in ("系统状态与连接", "历史与审计", "高级设置"):
        assert marker in workbench, marker

    # A slow SEO/GEO report may update metrics later, but must never replace
    # the owner workbench with an unavailable-state panel.
    for marker in ("latestSeo", "seoRequest", "SEO/GEO overview refresh deferred"):
        assert marker in growth_os, marker
    assert "const [growth, autonomy, seo] = await Promise.all" not in growth_os

    # These later recovery shells are intentionally excluded from the Final #40
    # baseline because they changed the user-visible navigation and page scope.
    forbidden = ("r8_23_3_candidate_patch", "r8_23_4_runtime_route_recovery_patch", "r8_23_5_full_recovery_patch")
    for marker in forbidden:
        assert marker not in run, marker
        assert marker not in truth_patch, marker

    print("PASS: R8-23 Final #40 keeps the complete workbench and isolates slow SEO/GEO refreshes from the owner cockpit")


if __name__ == "__main__":
    main()
