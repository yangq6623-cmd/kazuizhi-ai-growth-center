from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "05_V2.0.0_Source" / "web"


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    bridge = (WEB / "r8_13_seo_geo_bridge.js").read_text(encoding="utf-8")
    polish = (WEB / "geo-phase1-ui-polish.js").read_text(encoding="utf-8")
    css = (WEB / "geo-phase1-ui-polish.css").read_text(encoding="utf-8")
    ui = (WEB / "operational-search.js").read_text(encoding="utf-8")

    for marker in ("geo-phase1-ui-polish.css", "geo-phase1-ui-polish.js", "injectGeoPolish"):
        require(marker in bridge, f"integrated bridge missing GEO polish asset: {marker}")

    for marker in (
        "开始网页验证 · 1题",
        "准备10题 · 从第1题开始",
        "本地辅助预检",
        "高级工具",
        "第一轮真实基线",
        "GEO 联动摘要（只读）",
        "进入 GEO 增长",
        "SEO 自治运行",
        "geo-action-feedback",
        "installInteractionRepair",
        "当前已有网页验证任务",
    ):
        require(marker in polish, f"GEO/SEO visual or interaction marker missing: {marker}")

    for marker in (
        ".geo-command-deck",
        ".geo-baseline-progress",
        ".geo-action-feedback",
        ".geo-browser-workbench.is-idle",
        ".geo-browser-workbench.is-active",
        ".legacy-geo-summary",
        ".geo-legacy-queue-notice",
    ):
        require(marker in css, f"GEO B2B polish style missing: {marker}")

    for button_id in (
        "geo-local-one",
        "geo-local-ten",
        "geo-browser-one",
        "geo-browser-ten",
        "geo-browser-submit",
        "geo-run-round",
        "geo-bootstrap",
        "geo-refresh",
    ):
        require(button_id in ui, f"existing GEO control removed by visual upgrade: {button_id}")

    require("prepareBrowserTask(1" in ui and "prepareBrowserTask(10" in ui, "base browser 1/10 task controls lost wiring")
    require("runLocalPrecheck(1" in ui and "runLocalPrecheck(10" in ui, "base local precheck controls lost wiring")
    require("submitBrowserReceipt" in ui, "base browser Evidence/Receipt save action missing")
    require("runApiRound" in ui, "optional API action missing")
    require("event.stopImmediatePropagation()" in polish, "repaired GEO buttons can double-fire old handlers")
    require("'/api/r8-19/geo/local-precheck/run'" in polish, "local precheck repaired click path missing")
    require("'/api/r8-19/geo/browser/prepare'" in polish, "browser prepare repaired click path missing")
    require("'/api/r8-19/geo/browser/receipt'" in polish, "browser receipt repaired click path missing")

    print("PASS: R8-19 GEO workspace has compact B2B layout, visible click feedback and protected browser/local controls; SEO GEO duplicate remains read-only")


if __name__ == "__main__":
    main()
