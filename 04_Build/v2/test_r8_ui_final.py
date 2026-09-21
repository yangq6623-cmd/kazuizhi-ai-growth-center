"""Regression gate for the visibly distinct R8 V2.2.1 Productized UI Final layer."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "05_V2.0.0_Source" / "web"
DOCS = ROOT / "docs"


def read(path):
    return path.read_text(encoding="utf-8")


def require(text, tokens, label, failures):
    for token in tokens:
        if token not in text:
            failures.append(f"{label} missing: {token}")


def main():
    failures = []
    loader = read(WEB / "operational-productization.js")
    final_js = read(WEB / "operational-ui-final.js")
    final_css = read(WEB / "operational-ui-final.css")
    hotfix_js = read(WEB / "operational-ui-hotfix-341.js")
    hotfix_css = read(WEB / "operational-ui-hotfix-341.css")
    user_guide = read(DOCS / "R8_OPERATIONAL_USER_GUIDE.md")
    test_report = read(DOCS / "R8_OPERATIONAL_TEST_REPORT.md")

    require(loader, [
        "loadUiFinal",
        "operational-ui-final.css",
        "operational-ui-final.js",
        "data-r8-ui-final",
        "loadUiHotfix341",
        "operational-ui-hotfix-341.js",
    ], "UI final loader", failures)

    require(final_js, [
        "r8-ui-final",
        "final-current-campaign",
        "final-new-campaign",
        "继续当前战役",
        "final-task-hero",
        "final-content-grid",
        "final-execution-details",
        "final-materials-details",
        "本地素材可选，缺素材不会阻塞生产",
        "final-account-status",
        "真实连接状态 · 只读",
        "待平台登录验证",
        "经营数据待接入",
        "final-health-summary",
        "系统总体状态",
    ], "UI final behavior", failures)

    require(hotfix_js, [
        "经营数据待接入",
        "创建新的增长战役",
        "/api/bridge/status",
        "ChatGPT 总控已连接",
        "ChatGPT 总控未连接",
        "约每 60 秒同步一次",
        "operational-ui-hotfix-341.css",
    ], "#341 acceptance hotfix", failures)

    require(final_css, [
        "body.r8-ui-final",
        ".final-current-campaign",
        ".final-new-campaign",
        ".final-task-hero",
        ".final-content-grid",
        ".final-execution-details",
        ".final-materials-details",
        ".final-account-status",
        ".final-health-summary",
    ], "UI final visual system", failures)

    require(hotfix_css, [
        ".hotfix-planning-truth",
        ".hotfix-planning-truth.is-connected",
        ".hotfix-planning-truth.is-blocked",
    ], "#341 hotfix visual states", failures)

    if "MutationObserver" in final_js or "MutationObserver" in hotfix_js:
        failures.append("UI final must use explicit operational events, not global MutationObserver polling")

    require(user_guide, [
        "本地素材是可选增强",
        "不上传照片或视频也不会阻塞生产",
        "开始 AI 自动生产",
        "账号发布资格是只读真实状态",
    ], "R8 productized user guide", failures)

    require(test_report, [
        "0 本地素材也能创建视频任务",
        "CI / 隔离环境能够证明什么",
        "仍需要用户电脑现场验收",
        "未审核不发布",
    ], "R8 truthful acceptance report", failures)

    stale_claims = [
        "没有本地真实素材不能创建视频任务",
        "必须先登记真实存在的本地素材",
    ]
    for claim in stale_claims:
        if claim in user_guide or claim in test_report:
            failures.append(f"stale zero-material rule remains in release docs: {claim}")

    if failures:
        raise SystemExit("\n".join(failures))
    print("PASS: R8 V2.2.1 Productized UI Final + #341 truth hotfix are release-consistent")


if __name__ == "__main__":
    main()
