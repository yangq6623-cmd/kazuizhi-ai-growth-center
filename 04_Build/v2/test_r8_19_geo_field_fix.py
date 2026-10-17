from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "05_V2.0.0_Source" / "web"


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    geo = (WEB / "geo.html").read_text(encoding="utf-8")
    js = (WEB / "geo-phase1-field-fix.js").read_text(encoding="utf-8")
    css = (WEB / "geo-phase1-field-fix.css").read_text(encoding="utf-8")

    for marker in ("geo-phase1-field-fix.js", "geo-phase1-field-fix.css"):
        require(marker in geo, f"embedded GEO workspace missing field-fix asset: {marker}")

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

    # Field fix used to observe the whole GEO subtree with attributes:true while
    # syncUi itself changed classes/attributes/DOM, causing a self-triggering
    # MutationObserver loop and freezing Chrome as soon as GEO was opened.
    require("new MutationObserver" not in js, "GEO field fix reintroduced a self-triggering MutationObserver")
    require("setInterval" in js and "document.hidden" in js, "safe low-frequency visible-only UI sync missing")
    require("setButtonText" in js, "idempotent compare-before-write button updates missing")

    for marker in (
        ".geo-runner-shell",
        ".geo-kpi-action",
        ".geo-task-actions",
        ".geo-browser-workbench.is-active",
        ".geo-action-feedback",
    ):
        require(marker in css, f"GEO compact field layout style missing: {marker}")

    print("PASS: embedded GEO field controls are explicit and use bounded event/timer sync without mutation feedback loops")


if __name__ == "__main__":
    main()
