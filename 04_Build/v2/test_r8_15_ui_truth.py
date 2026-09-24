from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "05_V2.0.0_Source" / "web"


def require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"R8-15 UI truth missing {label}: {needle}")


build_info = (WEB / "build_info.js").read_text(encoding="utf-8")
startup = (WEB / "r8_12_startup_coordinator.js").read_text(encoding="utf-8")
truth = (WEB / "r8_10_truth_convergence.js").read_text(encoding="utf-8")
ui_truth = (WEB / "r8_15_ui_truth_patch.js").read_text(encoding="utf-8")
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

require(web_version, "R8 Phase: R8-15", "web phase manifest")
require(web_version, "Public URL HTTP / Content / Canonical / Schema / Robots Verification", "public verification manifest")

print("PASS: R8-15 visible release identity, live date, global owner attention and local/public SEO truth are converged")
