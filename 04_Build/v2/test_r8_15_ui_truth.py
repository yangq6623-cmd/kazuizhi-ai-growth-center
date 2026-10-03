from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
WEB = SOURCE / "web"
BACKEND = SOURCE / "backend"


def require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"R8-15 UI truth missing {label}: {needle}")


build_info = (WEB / "build_info.js").read_text(encoding="utf-8")
startup = (WEB / "r8_12_startup_coordinator.js").read_text(encoding="utf-8")
truth = (WEB / "r8_10_truth_convergence.js").read_text(encoding="utf-8")
ui_truth = (WEB / "r8_15_ui_truth_patch.js").read_text(encoding="utf-8")
seo_ui = (WEB / "r8_13_seo_geo.html").read_text(encoding="utf-8")
autonomy_ui = (WEB / "r8_14_seo_geo_autonomy_ui.js").read_text(encoding="utf-8")
seo_bridge = (BACKEND / "r8_13_seo_geo_patch.py").read_text(encoding="utf-8")
web_version = (WEB / "WEB_VERSION.txt").read_text(encoding="utf-8")

for needle, label in (
    ('phase: "R8-15"', "current web phase"),
    ('runNumber: "__GITHUB_RUN_NUMBER__"', "GitHub run provenance"),
    ('commit: "__GITHUB_SHA__"', "GitHub commit provenance"),
    ('V2.2.2 Autonomous Mission Core', "visible release version"),
):
    require(build_info, needle, label)

require(startup, "/r8_15_ui_truth_patch.js", "R8-15 truth patch loader")
require(startup, "refreshTodayLabel", "live date refresh")
require(startup, "60000", "minute-level date/release refresh")
require(truth, "自治闭环工程就绪度", "non-business engineering readiness label")
require(truth, "非业务KPI", "engineering metric disclaimer")

for needle, label in (
    ("/api/content-factory", "Mission attention source"),
    ("/api/r8-14/seo-geo/autonomy", "SEO/GEO owner-attention source"),
    ("待我处理：${items.length}", "global owner attention aggregation"),
    ("账号 / 授权 / 公网", "owner attention category label"),
    ("R8-15", "current phase fallback"),
    ("本地已就绪", "local SEO evidence label"),
    ("不等于公网已发布", "local-vs-public SEO truth boundary"),
    ("待公网验证", "public verification pending label"),
    ("当前安装构建", "dynamic evolution build identity"),
):
    require(ui_truth, needle, label)

for needle, label in (
    ("今日增量", "today-vs-total separation"),
    ("累计真值", "cumulative truth ledger"),
    ("本周公开页面目标", "explicit public-page goal"),
    ("未测试时显示“未开始”", "GEO zero-denominator truth"),
    ("HTTP 200 不再等同于“移动端/速度正常”", "performance truth boundary"),
    ("Canonical覆盖", "canonical coverage evidence"),
    ("Schema覆盖", "schema coverage evidence"),
    ("性能测速", "independent performance evidence"),
    ("下一步", "asset next-action visibility"),
    ("今日作业记录只代表当日增量", "daily-run semantics"),
    ("经营数据待接入", "conversion source disclaimer"),
):
    require(seo_ui, needle, label)

for needle, label in (
    ("today_generated", "today generated evidence metric"),
    ("today_qc_passed", "today QC evidence metric"),
    ("canonical_files", "canonical file evidence"),
    ("schema_files", "schema file evidence"),
    ('measurement_state', "GEO measurement-state truth"),
    ("本地文件、Title、Description、Canonical、Schema 只代表本地证据", "local evidence disclaimer"),
):
    require(seo_bridge, needle, label)

for needle, label in (
    ("真实公开页面", "public count truth label"),
    ("真实提交URL", "submitted URL truth label"),
    ("SEO/GEO 待人工处理", "SEO-specific owner attention"),
    ("去站长平台授权", "precise search authorization action"),
    ("查看公网部署条件", "precise public deployment action"),
):
    require(autonomy_ui, needle, label)

require(web_version, "R8 Phase: R8-15", "web phase manifest")
require(web_version, "Public URL HTTP / Content / Canonical / Schema / Robots Verification", "public verification manifest")

print("PASS: R8-15 visible truth, SEO/GEO daily-vs-total metrics, GEO zero-denominator handling, technical evidence semantics and precise blockers are converged")
