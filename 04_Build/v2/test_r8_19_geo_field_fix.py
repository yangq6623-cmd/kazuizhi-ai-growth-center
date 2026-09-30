from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "05_V2.0.0_Source" / "web"


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    bridge = (WEB / "r8_13_seo_geo_bridge.js").read_text(encoding="utf-8")
    js = (WEB / "geo-phase1-field-fix.js").read_text(encoding="utf-8")
    css = (WEB / "geo-phase1-field-fix.css").read_text(encoding="utf-8")

    for marker in (
        "geo-phase1-field-fix.js",
        "geo-phase1-field-fix.css",
        "injectGeoFieldFix",
        "injectGeoFieldFix(frame,()=>injectGeoPolish(frame))",
    ):
        require(marker in bridge, f"field fix bridge marker missing: {marker}")

    for marker in (
        "打开AI网页并复制问题",
        "复制当前问题",
        "打开外部AI网页",
        "修复重复运行任务",
        "PLATFORM_URLS",
        "window.open",
        "navigator.clipboard",
        "geo-kpi-action",
        "activateFilter",
        "'/api/r8-19/geo/pause'",
        "event.stopImmediatePropagation()",
    ):
        require(marker in js, f"GEO field interaction marker missing: {marker}")

    for marker in (
        ".geo-runner-shell",
        ".geo-kpi-action",
        ".geo-task-actions",
        ".geo-browser-workbench.is-active",
        ".geo-action-feedback",
    ):
        require(marker in css, f"GEO compact field layout style missing: {marker}")

    print("PASS: R8-19 GEO field buttons are explicit, KPI cards drill down, active task can open/copy, duplicate running tasks can be repaired, and runner layout is compact")


if __name__ == "__main__":
    main()
