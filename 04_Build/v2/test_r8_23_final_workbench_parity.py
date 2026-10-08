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
R8_FINAL_CENTER = SRC / "web" / "r8_final_center.js"
INDEX = SRC / "web" / "index.html"
TRUTH_PATCH = SRC / "core" / "r8_20_growth_truth_patch.py"
GEO_HTML = SRC / "web" / "geo.html"
GEO_AUTONOMY = SRC / "web" / "geo-autonomy.js"
GEO_FIELD_FIX = SRC / "web" / "geo-phase1-field-fix.js"
GEO_POLISH = SRC / "web" / "geo-phase1-ui-polish.js"
GEO_PHASE2 = SRC / "web" / "geo-phase2-analysis.js"
GEO_PHASE3 = SRC / "web" / "geo-phase3.js"
GEO_GROWTH_UI = SRC / "web" / "geo-growth-os.js"
OPERATIONAL_SEARCH = SRC / "web" / "operational-search.js"
CONNECTOR_MATRIX = SRC / "web" / "seo-geo-connector-matrix.js"
GEO_GROWTH_CORE = SRC / "core" / "geo_growth_orchestrator.py"
GEO_PUBLISH_BRIDGE = SRC / "core" / "geo_growth_publish_bridge.py"
BUILD_INFO = SRC / "web" / "build_info.js"
STORAGE = SRC / "core" / "storage.py"
GEO_JOB_PATCH = SRC / "core" / "geo_phase3_job_patch.py"
R8_20_PATCH = SRC / "backend" / "r8_20_seo_geo_growth_patch.py"
SERVER = SRC / "backend" / "server.py"
R8_13_PATCH = SRC / "backend" / "r8_13_seo_geo_patch.py"
R8_14_PATCH = SRC / "backend" / "r8_14_seo_geo_autonomy_patch.py"


def text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def main() -> None:
    run = text(RUN)
    workbench = text(WORKBENCH)
    coordinator = text(COORDINATOR)
    seo_bridge = text(SEO_BRIDGE)
    growth_os = text(GROWTH_OS)
    r8_final_center = text(R8_FINAL_CENTER)
    index = text(INDEX)
    truth_patch = text(TRUTH_PATCH)
    geo_html = text(GEO_HTML)
    geo_autonomy = text(GEO_AUTONOMY)
    geo_field_fix = text(GEO_FIELD_FIX)
    geo_polish = text(GEO_POLISH)
    geo_phase2 = text(GEO_PHASE2)
    geo_phase3 = text(GEO_PHASE3)
    geo_growth_ui = text(GEO_GROWTH_UI)
    operational_search = text(OPERATIONAL_SEARCH)
    connector_matrix = text(CONNECTOR_MATRIX)
    geo_growth_core = text(GEO_GROWTH_CORE)
    geo_publish_bridge = text(GEO_PUBLISH_BRIDGE)
    build_info = text(BUILD_INFO)
    storage = text(STORAGE)
    geo_job_patch = text(GEO_JOB_PATCH)
    r8_20_patch = text(R8_20_PATCH)
    server = text(SERVER)
    r8_13_patch = text(R8_13_PATCH)
    r8_14_patch = text(R8_14_PATCH)

    assert "r8_20_seo_geo_growth_patch" in run
    for marker in ("SCHEDULER_STARTUP_GRACE_SECONDS = 12", "CONTENT_STARTUP_GRACE_SECONDS = 25", "VIDEO_STARTUP_GRACE_SECONDS = 35", "HEAVY_CONTROL_STARTUP_GRACE_SECONDS = 45", "next_heavy_at = time.monotonic()"):
        assert marker in run, marker
    for marker in ("request_queue_size = 64", "daemon_threads = True"):
        assert marker in server, marker
    for marker in ("_SNAPSHOT_REFRESH_PENDING", "threading.Timer", "_kick_snapshot_refresh(delay_seconds=2.0)"):
        assert marker in r8_13_patch, marker
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
    assert "build_info.js" in index and index.index("build_info.js") < index.index("app.js")
    for marker in ('<script defer src="build_info.js"', '<script defer src="app.js"', '<script defer src="r8_12_startup_coordinator.js"', '<script defer src="r8_13_route_bootstrap.js"'):
        assert marker in index, marker
    assert 'phase: "R8-24"' in build_info
    assert "V2.2.2 R8-24 GEO Growth OS" in build_info
    assert 'r8-23-shell-preflight' in index
    for marker in ("老板总控", "AI决策中心", "内容创导", "执行中心", "待我处理", "经营结果", "SEO/GEO增长", "自进化中心"):
        assert marker in index, marker
    assert "function bindNavigation(nav)" in workbench
    assert "r810Bound" in workbench
    for marker in ("enforceSingleActivePage", "main > .page", "dataset.kzActivePage"):
        assert marker in workbench, marker
    for marker in ("installInitialRouteOwnership", "lockInitialDashboardOnce", "kzHomeOwner", "kzInitialRouteUserChosen"):
        assert marker in coordinator, marker
    assert "forceInitialDashboardOnce" not in coordinator
    assert "late openPage('dashboard')" in coordinator

    for marker in ("latestSeo", "seoRequest", "SEO/GEO overview refresh deferred"):
        assert marker in growth_os, marker
    seo_page = text(SRC / "web" / "r8_13_seo_geo.html")
    for marker in ("SEO自动增长主流水线", "RevenueOS经营反馈", "flow-bottleneck", "revenue-feedback"):
        assert marker in seo_page, marker
    for marker in ("24小时无人值守验收", "connector-summary", "360搜索站长平台", "豆包搜索 / 豆包浏览器", "抖音搜索 / 抖音浏览器", "不计SUBMITTED", "搜索提交渠道", "AI / 内容生态监测与发布", "新增付费模型：0", "SEO/GEO实时刷新延后", "probeServiceHealth", "loadBusy", "loadPending", "LAST_GOOD_KEY", "restoreLastGood", "persistLastGood", "build_info.js?probe="):
        assert marker in seo_page, marker
    submitter_source = text(SRC / "integrations" / "search_engine_submitter.py")
    for marker in ("RETRY_BACKOFF_MINUTES", "_record_failure", "_retry_blocked", "automation_summary", "monitoring_channels", "channel_groups", "cost_policy", "reuse_existing_api", "publish_authorized"):
        assert marker in submitter_source, marker
    for marker in (
        "主页工作流 · 从目标到结果", "全项目执行能力总览", "OWNER_PROJECTS",
        "GEO 自动增长", "SEO 搜索增长", "内容生产", "视频 / 视觉生产",
        "发布与分发", "本地增长 / 小程序", "转化与经营结果", "总控复盘 / 自进化",
        "data-kz23-target", "能力就绪", "部分待连接", "最近执行",
    ):
        assert marker in growth_os, marker
    assert "const [growth, autonomy, seo] = await Promise.all" not in growth_os
    forms = text(SRC / "web" / "forms.js")
    assert forms.count("if (window.__KZ_R812_STARTUP_COORDINATOR__) return;") >= 6
    for marker in ("AbortController", "cache:'no-store'", "decision:", "/decision_center.js", "/r8_13_seo_geo_bridge.js", "lazyPromises.delete(name)", "seo_geo: [", "sourceCache", "sourcePromises", "primeScriptSources", "prefetchWorkspaceDocuments"):
        assert marker in coordinator, marker
    startup = text(SRC / "web" / "r8_12_startup_coordinator.js")
    for marker in ("KZStartupDiagnostics", "KZRetryFailedStartupModules", "KZClearStartupModuleFailure", "r812-startup-diagnostics", "auto_retry_", "kz:startup-module-recovered", "POST_READY_SEQUENCE", "loadPostReadyModules", "POST_READY_DELAY_MS = 5000", "POST_READY_TIMEOUT_MS = 45000"):
        assert marker in startup, marker
    truth_patch = text(SRC / "web" / "r8_15_ui_truth_patch.js")
    for marker in ("refreshBusy", "AbortController", "scheduleRefresh(1800)", "30000"):
        assert marker in truth_patch, marker
    seo_bridge_backend = text(SRC / "backend" / "r8_13_seo_geo_patch.py")
    for marker in ("_SNAPSHOT_STORE", "_load_last_good_payload", "snapshot_saved_at", "deliberately read-only", "_fast_dashboard_response", "_kick_snapshot_refresh", "_SNAPSHOT_REFRESH_LOCK", "_fast_health_payload", "data_root() / _SNAPSHOT_STORE"):
        assert marker in seo_bridge_backend, marker
    route_bootstrap = text(SRC / "web" / "r8_13_route_bootstrap.js")
    for marker in ("route_recovery", "30000", "clearFailure", "KZLoadOwnerWorkspace", "KZClearStartupModuleFailure"):
        assert marker in route_bootstrap, marker
    assert "button.disabled = active" not in route_bootstrap
    assert 'data-src="/r8_13_seo_geo.html?embed=1"' in seo_bridge
    assert "loadWorkspaceIfNeeded(target)" in seo_bridge
    for marker in ("frameAtWantedLocation", "workspaceDomReady", "kzLoading", "kzLoadAttempts", "frame.dataset.kzLoaded='0'", "reload='+Date.now()", "9000", "<5"):
        assert marker in seo_bridge, marker
    render_workspace = seo_bridge[seo_bridge.index("function renderWorkspace(name)"):]
    assert render_workspace.index("desiredWorkspace=target;") < render_workspace.index("loadWorkspaceIfNeeded(target);")
    for marker in ("_UNATTENDED_CLOUD_STARTUP_DELAY_SECONDS = 12", "threading.Timer", "_schedule_unattended_cloud_scan", "protect_geo_first_open"):
        assert marker in r8_14_patch, marker
    for marker in ("geo-direct-fallback", "GEO 工作台正在加载", "body:has(#search-growth-switch)"):
        assert marker in geo_html, marker
    assert geo_html.index('<script src="geo-growth-os.js"></script>') < geo_html.index('<script defer src="operational-search.js"></script>')
    for marker in ("ensureGeoCoreInFrame", "parent-recovery", "data-kz-parent-geo-core-recovery", "[350,900,1800,3200,5200]"):
        assert marker in seo_bridge, marker
    assert "frame.dataset.kzLoaded='1';\n    frame.src=wanted;" not in seo_bridge
    for marker in ("Promise.allSettled", "GEO 主界面已先恢复", "KZ_GEO_TIMEOUT"):
        assert marker in operational_search, marker
    assert "Promise.all([json('/api/r8-19/geo')" not in operational_search
    for marker in ("requestJson", "连接路由检查超时", "主界面不会等待此检查", "showError"):
        assert marker in connector_matrix, marker
    for marker in ("foldLegacyHomepage", "kz-r8-24-legacy-home", "历史基础面板 · 默认收起"):
        assert marker in growth_os, marker
    for marker in ("MISSION CONTROL LEDGER", "四类 AI 协作状态", "告诉ChatGPT 你希望什么经营结果发生"):
        assert marker in growth_os, marker
    assert "R8 增长总控" not in r8_final_center
    for marker in ("Single-home rule", "r810-legacy-route", "不作为主页", "r8-final-legacy-page"):
        assert marker in r8_final_center, marker

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
    assert geo_growth_ui.count("async function load(){") == 1
    assert geo_growth_ui.count("const rows=data.opportunities||[];") == 1
    for marker in ("GEO 自动增长数据等待超时", "__KZ_GEO_GROWTH_OS_BOOT__", "正在恢复 GEO 运行状态", "blank 720px iframe", "GEO Growth OS boot retry", "pollTimer", "/api/r8-24/geo-growth/fast", "timeoutMs:4000", "状态快照暂未返回"):
        assert marker in geo_growth_ui, marker
    for marker in ("recoverGeoWorkbench", "connector", "window.__KZ_GEO_GROWTH_OS_BOOT__?.()", "window.searchGrowthActivate?.()"):
        assert marker in geo_html, marker

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
        "data-geo-filter", "data-geo-advance", "geo-os-blocker-retry",
    ):
        assert marker in geo_growth_ui or marker in geo_html, marker
    assert "geo-os-controls .geo-os-runtime" not in geo_growth_ui
    assert "typeof window.__KZ_GEO_GROWTH_OS_BOOT__ === 'function'" in geo_growth_ui
    assert "stale-sentinel" in geo_growth_ui
    assert "#692 正在恢复 GEO 工作台组件" in geo_html

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
    assert "read_only_status_no_sync" in geo_growth_core
    assert "deferred_requeued" in geo_growth_core
    assert "_clear_blocker" in geo_growth_core
    assert "def arm_unattended()" in geo_growth_core
    assert '"execution": "deferred_to_scheduler"' in geo_growth_core
    assert "def fast_status()" in geo_growth_core
    fast_status_block = geo_growth_core[geo_growth_core.index("def fast_status()"):geo_growth_core.index("def status()")]
    assert '"status_mode": "fast_snapshot"' in fast_status_block
    # Check executable call patterns, not explanatory docstring text.
    assert "= geo_autonomy.status()" not in fast_status_block
    assert "return geo_autonomy.status()" not in fast_status_block
    assert "= geo.dashboard()" not in fast_status_block
    assert "return geo.dashboard()" not in fast_status_block
    assert "geo_analysis.refresh(" not in fast_status_block
    assert "_JSON_IO_LOCK = threading.RLock()" in storage
    assert "for attempt in range(8)" in storage

    # R8-24.1: QC_PASSED is not a terminal success. The existing guarded public
    # deployer must be called by the GEO loop, and missing configuration must
    # become a visible technical blocker while other work continues.
    for marker in (
        "seo_public_deployer", "deploy_pending", "publish_connector_not_ready",
        "public_publish_verification_failed", "public_publish_deferred",
        "QC_PASSED 不等于 PUBLISHED", "publish_bridge",
        "geo_growth._sync_all", "main_loop_continues", "_LOOP_LOCK",
    ):
        assert marker in geo_publish_bridge, marker
    assert "waiting_retest" in geo_growth_core
    assert "geo_growth_publish_bridge" in r8_20_patch

    # Scheduler/API integration is automatic and uses the existing R8-20 lane.
    for marker in (
        "geo_growth_orchestrator as geo_growth", "geo_growth.run_once(force=force)",
        "_GEO_GROWTH_AUTO_START_DELAY_SECONDS = 20", "threading.Timer",
        "_schedule_geo_growth_auto_start", "_ensure_geo_growth_auto_running",
        "geo_growth.arm_unattended()", "owner_paused", "protect_first_paint_then_auto_start",
        '"/api/r8-24/geo-growth"', '"/api/r8-24/geo-growth/start"',
        '"/api/r8-24/geo-growth/pause"', '"/api/r8-24/geo-growth/resume"',
        '"/api/r8-24/geo-growth/run"', '"/api/r8-24/geo-growth/retry"',
        "geo-growth-os.js", "_kz_r8_24_geo_growth_os",
        '"/api/r8-24/geo-growth/fast"', "geo_growth.fast_status()",
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
