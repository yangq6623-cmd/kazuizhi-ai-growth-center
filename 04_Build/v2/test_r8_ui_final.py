"""Regression gate for the visibly distinct R8 V2.2.1 Productized UI + #349 usability layer."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "05_V2.0.0_Source" / "web"
SRC = ROOT / "05_V2.0.0_Source"
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
    forms = read(WEB / "forms.js")
    final_js = read(WEB / "operational-ui-final.js")
    final_css = read(WEB / "operational-ui-final.css")
    hotfix_js = read(WEB / "operational-ui-hotfix-341.js")
    hotfix_css = read(WEB / "operational-ui-hotfix-341.css")
    usability_js = read(WEB / "operational-usability-349.js")
    usability_css = read(WEB / "operational-usability-349.css")
    autonomous_js = read(WEB / "autonomous-ops.js")
    autonomous_css = read(WEB / "autonomous-ops.css")
    autonomous_core = read(SRC / "core" / "autonomous_ops.py")
    autonomous_backend = read(SRC / "backend" / "autonomous_ops_patch.py")
    mission_feedback = read(SRC / "core" / "decision_center_mission_patch.py")
    watchdog = read(SRC / "promotion" / "chatgpt_handoff_watchdog.py")
    runtime = read(SRC / "run.py")
    user_guide = read(DOCS / "R8_OPERATIONAL_USER_GUIDE.md")
    test_report = read(DOCS / "R8_OPERATIONAL_TEST_REPORT.md")

    require(loader, [
        "loadUiFinal",
        "operational-ui-final.css",
        "operational-ui-final.js",
        "data-r8-ui-final",
        "loadUiHotfix341",
        "operational-ui-hotfix-341.js",
        "loadAutonomousOps",
        "autonomous-ops.js",
        "autonomous-ops.css",
    ], "UI final loader", failures)

    require(forms, [
        "data-autonomous-ops",
        "autonomous-ops.css",
        "autonomous-ops.js",
        "自治运营主线",
    ], "R7 boss Mission loader", failures)

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
        "operational-usability-349.js",
        "请求已写入ChatGPT同步桥",
        "当前不能证明ChatGPT已接收",
        "operational-ui-hotfix-341.css",
    ], "truthful planning hotfix", failures)
    if "/api/bridge/status" in hotfix_js or "ChatGPT 总控已连接" in hotfix_js:
        failures.append("UI must not equate writable bridge status with ChatGPT acknowledgement")

    require(usability_js, [
        "r8-usability-349",
        "今天要什么结果、现在卡在哪里",
        "data-final-ui-new-campaign",
        "把照片、视频或音频直接拖到这里",
        "input.multiple=true",
        "去连接手机",
        "usability-account-flow",
        "其余按钮暂不可用",
        "usability-human",
        "usability-auto",
        "usability-build",
    ], "#349 field usability", failures)
    require(usability_css, [
        ".usability-account-flow",
        ".usability-material-drop",
        ".usability-device-hint",
        "button:disabled",
        ".usability-human",
        ".usability-auto",
        ".usability-build",
    ], "#349 visual states", failures)

    require(autonomous_js, [
        "卡嘴子自治运营主线",
        "老板总控",
        "执行中心",
        "老板经营目标",
        "当前 Mission 时间线",
        "/api/autonomous-ops",
        "/api/autonomous-ops/goal",
        "真实平台回执",
    ], "shared Mission UI", failures)
    require(autonomous_css, [
        ".mission-command-strip",
        ".mission-state.running",
        ".mission-state.human",
        ".mission-state.danger",
        ".mission-timeline",
        ".mission-goal-editor",
    ], "shared Mission visual system", failures)
    require(autonomous_core, [
        "MISSION-",
        "sync_from_runtime",
        "autostart=True",
        "mission_context_for_growth",
        "feedback_for_r7",
        "老板目标 → ChatGPT总决策 → R7分析 → Mission → R8执行",
        "真实平台回执",
        "L4",
    ], "autonomous operations core", failures)
    require(autonomous_backend, [
        "/api/autonomous-ops",
        "/api/autonomous-ops/goal",
        "mission_context",
        "r7_context",
        "apply_chatgpt_qc",
        "record_receipt",
    ], "autonomous operations backend bridge", failures)
    require(mission_feedback, [
        "mission_feedback",
        "R8真实执行结果",
        "feedback_for_r7",
    ], "R8 to R7 feedback bridge", failures)

    require(watchdog, [
        "RETRY_AFTER_SECONDS = 300",
        "MAX_RETRIES = 3",
        "bridge_unavailable",
        "waiting_response",
        "retry_exhausted",
        "export_decision_handoff",
        "异常待处理",
    ], "ChatGPT handoff watchdog", failures)
    if "writable sync folder is not the same thing" not in watchdog.lower():
        failures.append("watchdog must explicitly separate bridge availability from ChatGPT receipt")
    require(runtime, [
        "from promotion.chatgpt_handoff_watchdog import sync_chatgpt_handoffs",
        "sync_chatgpt_handoffs()",
        "sync_chatgpt_handoffs(force=True)",
        "decision_center_mission_patch",
        "autonomous_ops_patch",
        "sync_autonomous_ops(autostart=True)",
        "sync_autonomous_ops(autostart=False)",
    ], "runtime autonomous loop wiring", failures)

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
    ], "planning status visual states", failures)

    for name, source in (("final", final_js), ("hotfix", hotfix_js), ("usability", usability_js), ("autonomous", autonomous_js)):
        if "MutationObserver" in source:
            failures.append(f"{name} UI must use explicit events, not global MutationObserver polling")

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
    print("PASS: R8 Productized UI + #349 usability + unified autonomous Mission continuity")


if __name__ == "__main__":
    main()
