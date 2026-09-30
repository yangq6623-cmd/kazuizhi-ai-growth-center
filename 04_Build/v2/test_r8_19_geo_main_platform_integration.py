"""R8-19 field gate: GEO Phase 1 must be integrated into the normal platform route.

A standalone /geo.html page is retained only as a backup/debug route. It is not
sufficient for Phase-1 field acceptance. The normal owner workflow is:
left nav SEO/GEO增长 -> internal SEO增长/GEO增长 -> GEO controls/evidence.
The existing SEO workspace must remain complete after integration.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "05_V2.0.0_Source" / "web"


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    bridge = (WEB / "r8_13_seo_geo_bridge.js").read_text(encoding="utf-8")
    workspace = (WEB / "operational-search.js").read_text(encoding="utf-8")
    backup = (WEB / "geo.html").read_text(encoding="utf-8")
    seo = (WEB / "r8_13_seo_geo.html").read_text(encoding="utf-8")

    # Main platform route remains the only left-nav entry and preserves old SEO.
    require("const PAGE_ID = 'r813-seo-geo'" in bridge, "main SEO/GEO route missing")
    require("SEO/GEO增长" in bridge, "main left-nav label missing")
    require("/r8_13_seo_geo.html?embed=1" in bridge, "existing SEO workspace was removed")
    require("SEO/GEO增长中心" in seo, "existing SEO page no longer preserved")

    # Full original SEO contract: the GEO merge must not collapse the old page to only its upper cards.
    for marker in (
        "关键词机会池", "索引与收录漏斗", "技术SEO健康检查", "内容与页面工厂",
        "站长平台与索引连接", "转化与归因", "今日自动作业流水线",
    ):
        require(marker in seo, f"original SEO section missing from source: {marker}")

    # The embedded frame must keep measuring dynamic content after the tabs are injected.
    require("doc.body?.scrollHeight" in bridge, "SEO iframe no longer measures body height")
    require("doc.getElementById('search')?.scrollHeight" in bridge, "integrated search host height is not measured")
    require("seo-growth-pane" in bridge, "SEO pane height is not measured")
    require("geo-growth-pane" in bridge, "GEO pane height is not measured")
    require("MutationObserver" in bridge, "dynamic SEO/GEO height changes are not observed")
    require("ResizeObserver" in bridge, "SEO/GEO frame resize observer missing")
    require("scheduleResize" in bridge, "delayed resize stabilization missing")

    # The new GEO workspace is injected into that normal route, not opened as a separate browser.
    require("ensureSearchHost" in bridge, "main route does not prepare integrated search host")
    require("/operational-search.css" in bridge, "GEO workspace CSS not integrated into main route")
    require("/operational-search.js" in bridge, "GEO workspace JS not integrated into main route")
    require("KZR813SeoGeoBridge" in bridge, "main route API missing")
    require("openGeo" in bridge and "openSeo" in bridge, "main route cannot switch SEO/GEO explicitly")
    require("kz-search-growth-workspace" in bridge, "last selected SEO/GEO tab is not persisted")
    require("#geo-decision-open" in bridge, "AI decision center GEO action is not bridged back to main platform")
    require("window.location.href = '/geo.html'" not in bridge, "main route still redirects to standalone GEO page")

    # Visible inner workspace contract.
    for marker in (
        "SEO 增长", "GEO 增长", "ChatGPT GEO 总控", "固定 50 问",
        "执行中心 · GEO真实验证", "GEO Evidence / Receipt", "待我处理",
    ):
        require(marker in workspace, f"integrated GEO workspace marker missing: {marker}")

    # Backup/debug route stays available but is not the normal navigation path.
    require("operational-search.js" in backup, "backup /geo.html route no longer works")

    print("PASS: GEO is merged into the normal route and the complete legacy SEO workspace is preserved")


if __name__ == "__main__":
    main()
