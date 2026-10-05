"""Release gate: keep the R8-23 Final #40 complete workbench intact.

This guard protects the user-facing baseline: the full left navigation and
each workspace must remain available. Recovery-only UI layers are forbidden
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
INDEX = SRC / "web" / "index.html"
TRUTH_PATCH = SRC / "core" / "r8_20_growth_truth_patch.py"
GEO_HTML = SRC / "web" / "geo.html"
GEO_AUTONOMY = SRC / "web" / "geo-autonomy.js"
GEO_FIELD_FIX = SRC / "web" / "geo-phase1-field-fix.js"
GEO_POLISH = SRC / "web" / "geo-phase1-ui-polish.js"
GEO_PHASE2 = SRC / "web" / "geo-phase2-analysis.js"
GEO_PHASE3 = SRC / "web" / "geo-phase3.js"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> None:
    run = text(RUN)
    workbench = text(WORKBENCH)
    coordinator = text(COORDINATOR)
    seo_bridge = text(SEO_BRIDGE)
    growth_os = text(GROWTH_OS)
    index = text(INDEX)
    truth_patch = text(TRUTH_PATCH)
    geo_html = text(GEO_HTML)
    geo_autonomy = text(GEO_AUTONOMY)
    geo_field_fix = text(GEO_FIELD_FIX)
    geo_polish = text(GEO_POLISH)
    geo_phase2 = text(GEO_PHASE2)
    geo_phase3 = text(GEO_PHASE3)

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

    # The owner shell cannot flash a legacy R7 menu while the coordinator is
    # still loading. The complete workbench navigation is present in the
    # first HTML paint, and old buttons remain hidden compatibility routes.
    assert '<body class="r810-workbench">' in index
    assert 'r8-23-shell-preflight' in index
    for marker in ("老板总控", "AI决策中心", "内容创导", "执行中心", "待我处理", "经营结果", "SEO/GEO增长", "自进化中心"):
        assert marker in index, marker
    assert "function bindNavigation(nav)" in workbench
    assert "r810Bound" in workbench

    # A slow SEO/GEO report may update metrics later, but must never replace
    # the owner workbench with an unavailable-state panel.
    for marker in ("latestSeo", "seoRequest", "SEO/GEO overview refresh deferred"):
        assert marker in growth_os, marker
    assert "const [growth, autonomy, seo] = await Promise.all" not in growth_os

    # GEO direct workspace: every stage must be loaded and Phase-1 button
    # ownership must stay single-source. The field-fix capture handler owns the
    # real 1/10 browser/local/receipt actions; the polish layer is visual only.
    assert 'geo-phase1-field-fix.js' in geo_html
    assert 'geo-phase2-analysis.js' in geo_html
    assert 'geo-phase3.js' in geo_html
    assert "window.__KZ_R819_GEO_FIELD_FIX__" in geo_field_fix
    assert "dataset.kzGeoInteractionRepair='1'" in geo_html
    assert "installInteractionRepair" in geo_polish

    # Autonomous stage controls must allow 1 -> 3 -> 10 -> 50 escalation after
    # a completed stage enters monitoring. A generic enabled flag may not lock
    # the next stage, and rapid conflicting mutations are globally serialized.
    for marker in (
        "geo-auto-stage-1", "geo-auto-stage-3", "geo-auto-stage-10", "geo-auto-stage-50",
        "geo-auto-pause", "geo-auto-resume", "geo-auto-retry", "geo-auto-refresh",
        "state === 'running'", "actionBusy", "monitoring:'监控中'", "stale_recovery",
    ):
        assert marker in geo_autonomy, marker
    assert "Boolean(data.enabled) && !Boolean(data.paused)" not in geo_autonomy

    # Phase-2 buttons retain their semantic disabled state after a failed
    # ChatGPT call and clipboard copy has a desktop-browser fallback.
    for marker in (
        "geo2-refresh", "geo2-copy", "geo2-chatgpt", "writeClipboard",
        "document.execCommand('copy')", "await loadChatGPT()",
    ):
        assert marker in geo_phase2, marker

    # Phase-3 is now reachable from the direct GEO page. All mutation buttons
    # share one busy lock, and the final state is refreshed from the backend so
    # a successful render cannot be accidentally re-enabled by a finally block.
    for marker in (
        "geo3-plan", "geo3-run", "geo3-refresh", "withBusy", "actionBusy",
        "await load()", "'/api/r8-19/geo/phase3/plan'", "'/api/r8-19/geo/phase3/run'",
    ):
        assert marker in geo_phase3, marker
    assert "finally{busy(button,false);}" not in geo_phase3

    # These later recovery shells are intentionally excluded from the Final #40
    # baseline because they changed the user-visible navigation and page scope.
    forbidden = ("r8_23_3_candidate_patch", "r8_23_4_runtime_route_recovery_patch", "r8_23_5_full_recovery_patch")
    for marker in forbidden:
        assert marker not in run, marker
        assert marker not in truth_patch, marker

    print("PASS: R8-23 Final #40 keeps the complete workbench and GEO button/stage controls remain reachable, serialized, and truth-safe")


if __name__ == "__main__":
    main()
