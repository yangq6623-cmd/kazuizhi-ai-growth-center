"""Release gate: keep the R8-23 workbench intact and require R8-24 GEO Growth OS.

The guard protects the complete owner shell while ensuring the direct GEO page
has one autonomous operating surface above the evidence/developer tools.
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
GEO_GROWTH_UI = SRC / "web" / "geo-growth-os.js"
GEO_GROWTH_CORE = SRC / "core" / "geo_growth_orchestrator.py"
GEO_PUBLISH_BRIDGE = SRC / "core" / "geo_growth_publish_bridge.py"
GEO_JOB_PATCH = SRC / "core" / "geo_phase3_job_patch.py"
R8_20_PATCH = SRC / "backend" / "r8_20_seo_geo_growth_patch.py"


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
    geo_growth_ui = text(GEO_GROWTH_UI)
    geo_growth_core = text(GEO_GROWTH_CORE)
    geo_publish_bridge = text(GEO_PUBLISH_BRIDGE)
    geo_job_patch = text(GEO_JOB_PATCH)
    r8_20_patch = text(R8_20_PATCH)

    assert "r8_20_seo_geo_growth_patch" in run
    assert "R8-20 compatibility patch" in truth_patch
    for marker in ("r8_22_autonomy_convergence_patch", "r8_23_growth_os_patch"):
        assert marker in truth_patch, marker

    for marker in ("老板总控", "AI决策中心", "执行中心", "待我处理", "经营结果", "自进化中心"):
        assert marker in workbench, marker
    for marker in ("内容创导", "SEO/GEO增长"):
        assert marker in coordinator or marker in seo_bridge, marker
    for marker in ("系统状态与连接", "历史与审计", "高级设置"):
        assert marker in workbench, marker

    assert '<body class="r810-workbench">' in index
    assert 'r8-23-shell-preflight' in index
    for marker in ("老板总控", "AI决策中心", "内容创导", "执行中心", "待我处理", "经营结果", "SEO/GEO增长", "自进化中心"):
        assert marker in index, marker
    assert "function bindNavigation(nav)" in workbench
    assert "r810Bound" in workbench

    for marker in ("latestSeo", "seoRequest", "SEO/GEO overview refresh deferred"):
        assert marker in growth_os, marker
    assert "const [growth, autonomy, seo] = await Promise.all" not in growth_os

    # Existing evidence and staged acceptance tools remain reachable in the
    # advanced section, with Phase-1 action ownership kept single-source.
    assert 'geo-phase1-field-fix.js' in geo_html
    assert 'geo-phase2-analysis.js' in geo_html
    assert 'geo-phase3.js' in geo_html
    assert 'geo-growth-os.js' in geo_html
    assert "window.__KZ_R819_GEO_FIELD_FIX__" in geo_field_fix
    assert "dataset.kzGeoInteractionRepair='1'" in geo_html
    assert "installInteractionRepair" in geo_polish

    for marker in (
        "geo-auto-stage-1", "geo-auto-stage-3", "geo-auto-stage-10", "geo-auto-stage-50",
        "geo-auto-pause", "geo-auto-resume", "geo-auto-retry", "geo-auto-refresh",
        "state === 'running'", "actionBusy", "monitoring:'监控中'", "stale_recovery",
    ):
        assert marker in geo_autonomy, marker
    assert "Boolean(data.enabled) && !Boolean(data.paused)" not in geo_autonomy

    for marker in (
        "geo2-refresh", "geo2-copy", "geo2-chatgpt", "writeClipboard",
        "document.execCommand('copy')", "await loadChatGPT()",
    ):
        assert marker in geo_phase2, marker

    for marker in (
        "geo3-plan", "geo3-run", "geo3-refresh", "withBusy", "actionBusy",
        "await load()", "'/api/r8-19/geo/phase3/plan'", "'/api/r8-19/geo/phase3/run'",
    ):
        assert marker in geo_phase3, marker
    assert "finally{busy(button,false);}" not in geo_phase3

    # R8-24 owner surface: normal use is one autonomous workbench; staged
    # 1/3/10/50 and manual evidence tools are demoted into an advanced details
    # area rather than deleted. R8-24.1 also protects the toolbar from button
    # overlap on normal Windows widths and makes the running state explicit.
    for marker in (
        "GEO 自动增长工作台", "geo-os-start", "geo-os-pause", "geo-os-resume",
        "geo-os-run", "geo-os-retry", "geo-growth-advanced", "GEO 机会池与自动执行",
        "OpenAI API：禁用", "新增付费依赖：0", "正常推广无需人工审核",
        "/api/r8-24/geo-growth", "/api/r8-24/geo-growth/start",
        "geo-os-toolbar", "geo-os-actions", "geo-os-runtime-card", "repeat(auto-fit",
        "自动运营已启动", "publish_connector", "发布通道：",
    ):
        assert marker in geo_growth_ui or marker in geo_html, marker
    assert "geo-os-controls .geo-os-runtime" not in geo_growth_ui

    # C-level operating signals may drive work, but formal A/B truth remains
    # separate. The local controller is the 7x24 executor; it must not require
    # OpenAI API or a human approval step for ordinary non-financial GEO work.
    for marker in (
        '"openai_api": False', '"new_paid_dependencies": False',
        '"human_review_required": False', '"signal_level": "C"',
        '"official_truth": False', "geo_analysis.analyze_receipt", "upsert_opportunity",
        "r7_engine.create_job", "prepare_phase3_assets", "create_and_enqueue_plan",
        "GEO-GROWTH-OPERATING-RETEST", "formal_ab_unchanged",
    ):
        assert marker in geo_growth_core, marker
    assert '"evidence_level": "A"' not in geo_growth_core
    assert '"evidence_level": "B"' not in geo_growth_core

    # R8-24.1: QC_PASSED is not a terminal success. The existing guarded public
    # deployer must be called by the GEO loop, and missing configuration must
    # become a visible technical blocker while other work continues.
    for marker in (
        "seo_public_deployer", "deploy_pending", "publish_connector_not_ready",
        "public_publish_verification_failed", "public_publish_deferred",
        "QC_PASSED 不等于 PUBLISHED", "publish_bridge", "waiting_retest",
        "geo_growth._sync_all", "main_loop_continues",
    ):
        assert marker in geo_publish_bridge, marker
    assert "geo_growth_publish_bridge" in r8_20_patch

    # Scheduler/API integration is automatic and uses the existing R8-20 lane.
    for marker in (
        "geo_growth_orchestrator as geo_growth", "geo_growth.run_once(force=force)",
        '"/api/r8-24/geo-growth"', '"/api/r8-24/geo-growth/start"',
        '"/api/r8-24/geo-growth/pause"', '"/api/r8-24/geo-growth/resume"',
        '"/api/r8-24/geo-growth/run"', '"/api/r8-24/geo-growth/retry"',
        "geo-growth-os.js", "_kz_r8_24_geo_growth_os",
    ):
        assert marker in r8_20_patch, marker

    # The employee layer must be truth-neutral because R8-24 can be sourced by
    # either formal evidence or a C-level operating signal.
    assert "带证据等级标记的GEO缺口信号" in geo_job_patch
    assert "不会升级原始证据等级" in geo_job_patch

    forbidden = ("r8_23_3_candidate_patch", "r8_23_4_runtime_route_recovery_patch", "r8_23_5_full_recovery_patch")
    for marker in forbidden:
        assert marker not in run, marker
        assert marker not in truth_patch, marker

    print("PASS: R8-24.1 keeps the complete workbench, fixes GEO layout, and truthfully advances QC_PASSED assets through the guarded public publish bridge")


if __name__ == "__main__":
    main()
