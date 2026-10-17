"""R8-19 field gate: GEO Phase 1 must be integrated into the normal platform route.

The normal owner workflow is one left-nav entry: SEO/GEO增长 -> internal SEO增长 /
GEO增长. SEO and GEO run in separate same-origin iframes so a heavy GEO workspace
cannot mutate the legacy SEO document. The owner shell is the single page scroller;
data-heavy tables may keep bounded local scrolling.
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
    geo = (WEB / "geo.html").read_text(encoding="utf-8")
    seo = (WEB / "r8_13_seo_geo.html").read_text(encoding="utf-8")
    final_js = (WEB / "seo-geo-phase1-final.js").read_text(encoding="utf-8")
    final_css = (WEB / "seo-geo-phase1-final.css").read_text(encoding="utf-8")

    require("const PAGE_ID = 'r813-seo-geo'" in bridge, "main SEO/GEO route missing")
    require("SEO/GEO增长" in bridge, "main left-nav label missing")
    require("/r8_13_seo_geo.html?embed=1" in bridge, "existing SEO workspace was removed")
    require("/geo.html?embed=1" in bridge, "integrated GEO iframe route missing")
    require("SEO/GEO增长中心" in seo, "existing SEO page no longer preserved")

    for marker in (
        "关键词机会池", "索引与收录漏斗", "技术SEO健康检查", "内容与页面工厂",
        "站长平台与索引连接", "转化与归因", "今日自动作业流水线",
    ):
        require(marker in seo, f"original SEO section missing from source: {marker}")

    # Field-stability contract: split frames, lazy GEO, one owner-shell page scroller,
    # no ResizeObserver/MutationObserver feedback loop in the bridge.
    require("r813-seo-frame" in bridge and "r813-geo-frame" in bridge, "split SEO/GEO frames missing")
    require("data-r813-workspace=\"seo\"" in bridge, "SEO workspace tab missing")
    require("data-r813-workspace=\"geo\"" in bridge, "GEO workspace tab missing")
    require("src=\"about:blank\"" in bridge and "data-src=\"/geo.html?embed=1\"" in bridge, "GEO iframe is not lazy-loaded")
    require("scrolling=\"no\"" in bridge, "integrated workspaces must use owner-shell single-scroll mode")
    require("seo-geo-phase1-final.css" in bridge and "seo-geo-phase1-final.js" in bridge, "final SEO/GEO UX is not injected into both workspaces")
    require("ResizeObserver" not in bridge, "main SEO/GEO bridge must not auto-resize iframe via ResizeObserver")
    require("MutationObserver" not in bridge, "main SEO/GEO bridge must not observe child DOM for frame height")
    require("ResizeObserver" not in final_js and "MutationObserver" not in final_js, "final SEO/GEO UX must use bounded timer/event sync, not DOM observer feedback loops")
    require("frame.style.height" in final_js and "resizePasses" in final_js, "single-scroll embed needs bounded height synchronization")

    require("KZR813SeoGeoBridge" in bridge, "main route API missing")
    require("openGeo" in bridge and "openSeo" in bridge, "main route cannot switch SEO/GEO explicitly")
    require("kz-search-growth-workspace" in bridge, "last selected SEO/GEO tab is not persisted")
    require("#geo-decision-open" in bridge, "AI decision center GEO action is not bridged back to main platform")
    require("window.location.href = '/geo.html'" not in bridge, "main route still redirects browser to standalone GEO page")

    for marker in (
        "SEO 增长", "GEO 增长", "ChatGPT GEO 总控", "固定 50 问",
        "执行中心 · GEO真实验证", "GEO Evidence / Receipt", "待我处理",
    ):
        require(marker in workspace, f"integrated GEO workspace marker missing: {marker}")

    for marker in (
        "SEO 今日运行进度", "GEO 今日验证进度", "第一轮真实基线",
        "领取问题", "打开外部AI", "获取回答", "保存证据", "ChatGPT判断",
    ):
        require(marker in final_js, f"human progress flow missing: {marker}")

    require("body.geo-direct-embed #search-growth-switch" in final_css, "embedded GEO duplicate inner SEO/GEO switch is not hidden")
    require("geo-human-flow" in final_css, "three-step GEO task flow style missing")
    require("operational-search.js" in geo, "GEO embedded route no longer loads operational-search.js")
    require("geo-direct-embed" in geo, "GEO embedded layout mode missing")

    print("PASS: SEO/GEO main route preserves full SEO, uses single-scroll split frames, human progress flow, and lazy GEO without observer feedback loops")


if __name__ == "__main__":
    main()
