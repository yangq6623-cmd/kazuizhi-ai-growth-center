from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"


def main():
    bridge = (SOURCE / "web" / "r8_13_seo_geo_bridge.js").read_text(encoding="utf-8")
    startup = (SOURCE / "web" / "r8_12_startup_coordinator.js").read_text(encoding="utf-8")
    workbench = (SOURCE / "web" / "r8_10_workbench.js").read_text(encoding="utf-8")

    # SEO must be lazy: loading the owner dashboard must not create the heavy iframe.
    assert "ensureNav();" in bridge
    assert "ensurePage();\n  ensureNav();" not in bridge
    assert "ensurePage(true);" in bridge
    assert "Deliberately do not create the SEO iframe during application startup" in bridge

    # The old feedback loop caused iframe height -> ResizeObserver -> height+20 -> repeat.
    assert "ResizeObserver" not in bridge
    assert "+20" not in bridge.replace("2020", "")
    assert "MAX_FRAME_HEIGHT" in bridge
    assert "Math.abs(desired - current) >= 8" in bridge
    assert "installFiniteFrameResize" in bridge

    # Exactly one SEO iframe id and one SEO nav target are used.
    assert "const FRAME_ID = 'r813-seo-geo-frame'" in bridge
    assert "primary.querySelector('[data-target=\"r813-seo-geo\"]')" in bridge
    assert "if (createFrame && !page.querySelector(`#${FRAME_ID}`))" in bridge

    # Main navigation remains owned by the workbench and SEO is injected as one extra route.
    for label in (
        "老板总控", "AI决策中心", "执行中心", "待我处理", "经营结果",
        "自进化中心", "系统状态与连接", "历史与审计", "高级设置",
    ):
        assert label in workbench
    assert "nav.querySelectorAll('.r810-nav-button').forEach" in workbench
    assert "/r8_13_seo_geo_bridge.js" in startup

    # Browser syntax gate handles syntax; this gate protects runtime architecture invariants.
    print("PASS: R8-18 SEO lazy loading and finite iframe resize keep owner navigation responsive.")


if __name__ == "__main__":
    main()

