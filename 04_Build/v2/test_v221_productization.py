"""V2.2.1 productization regression contract.

The goal is not pixel-perfect testing. It prevents the known R8 UI/UX issues
from silently returning: inconsistent device state, background mirror polling,
technical-first navigation, unsupported owner controls, skeleton workbenches,
unverifiable business metrics, duplicate primary actions, dead buttons, split
Growth IDs, user-written verification state, and manual media classification.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "05_V2.0.0_Source"
WEB = SRC / "web"
INTEGRATIONS = SRC / "integrations"


def read(path):
    return path.read_text(encoding="utf-8")


def require(text, tokens, label, failures):
    for token in tokens:
        if token not in text:
            failures.append(f"{label} missing: {token}")


def main():
    failures = []
    operational = read(WEB / "operational.js")
    device = read(WEB / "operational-device.js")
    product = read(WEB / "operational-productization.js")
    final = read(WEB / "operational-finalization.js")
    final_css = read(WEB / "operational-finalization.css")
    ui_polish = read(WEB / "operational-ui-polish.js")
    ui_polish_css = read(WEB / "operational-ui-polish.css")
    deep_ui = read(WEB / "operational-deep-productization.js")
    deep_css = read(WEB / "operational-deep-productization.css")
    workbench = read(WEB / "operational-workbench.js")
    main_js = read(WEB / "main-productization.js")
    main_css = read(WEB / "main-productization.css")
    forms = read(WEB / "forms.js")
    b3 = read(INTEGRATIONS / "android_device_b3.py")
    deep_backend = read(SRC / "backend" / "deep_productization_patch.py")
    growth_chain = read(SRC / "backend" / "growth_chain_patch.py")
    asset_intake = read(SRC / "promotion" / "asset_intake.py")
    run = read(SRC / "run.py")

    require(operational, [
        "deviceSnapshot",
        "x&&x.connected",
        "deviceCenterDeactivate",
        "syncOperationalDeviceStatus",
        "window.changeOperationalPage",
    ], "unified operational device state", failures)
    if "device.status==='online'" in operational or 'device.status === \'online\'' in operational:
        failures.append("health page must not use a nonexistent top-level device.status online flag")

    require(device, [
        "FAILURE_LIMIT=3",
        "RECOVERY_RETRIES=3",
        "recoverDevice",
        "最后成功",
        "window.deviceCenterDeactivate=()=>stop(true)",
    ], "device recovery", failures)

    require(product, [
        "待我处理",
        "action_center",
        "health-normal",
        "health-config",
        "health-human",
        "loadFinalization",
        "operational-finalization.js",
        "loadUiPolish",
        "operational-ui-polish.css",
        "operational-ui-polish.js",
        "loadDeepProductization",
        "operational-deep-productization.js",
        "operational-deep-productization.css",
    ], "productization layer", failures)

    require(final, [
        "下一步",
        "增长ID",
        "数据来源",
        "更新时间",
        "content-flow-summary",
        "平台 → 终端 → 账号",
        "线索工作台",
        "负责人",
        "最近联系",
        "AI引用",
        "显示正常项",
        "未接入",
        "data-final-device-action",
    ], "final operational UX", failures)
    if "MutationObserver" in final:
        failures.append("final operational UX must not add a global DOM MutationObserver")

    require(final_css, [
        ".page-next-step",
        ".context-strip",
        ".flow-stages",
        ".device-business-context",
        ".crm-table",
        ".ops-table",
        ".health-filter-bar",
    ], "final operational visual system", failures)

    require(ui_polish, [
        "ui-owner-todo",
        "action_center",
        "ACTIVE_VIDEO_STATES",
        "创建战役并自动开始",
        "本地素材投递箱",
        "不上传也能正常生产",
        "开始 AI 自动生产",
        "setButtonState",
        "请先创建或选择增长战役",
        "quietSamePageStep",
        "ui-engine-strip",
    ], "R8 UI polish behavior", failures)
    if "MutationObserver" in ui_polish:
        failures.append("R8 UI polish must use explicit events, not a global DOM MutationObserver")
    require(ui_polish_css, [
        ".ui-owner-todo",
        ".campaign-main",
        ".campaign-side",
        ".content-workspace",
        ".content-review",
        ".optional-materials",
        "button:disabled",
        ".ui-engine-strip",
    ], "R8 UI polish visual system", failures)

    require(deep_backend, [
        "active_campaign_id",
        "ACTIVE_VIDEO_STATES",
        "该增长战役已有生产任务",
        "action_center",
        "human_count",
        "sync_accounts_from_control",
        "r8_social_control",
        "不能人工选择",
        "/api/content-factory/active-campaign",
    ], "deep productization backend", failures)
    require(growth_chain, [
        "growth_case_linked",
        "内容工厂增长ID已与R8咨询/归因账本统一",
        "conversion_summary",
        "metric_snapshots",
        "source_system",
        "growth_id",
    ], "unified Growth ID conversion bridge", failures)
    require(asset_intake, [
        "infer_kind",
        "VIDEO_EXTENSIONS",
        "IMAGE_EXTENSIONS",
        "AUDIO_EXTENSIONS",
        "auto_classified",
    ], "automatic material classification", failures)
    require(deep_ui, [
        "activeGrowthId",
        "setActiveGrowthId",
        "renderUnifiedOwnerActions",
        "action_center",
        "activeVideo",
        "当前任务：",
        "uploadFiles",
        "input.multiple=true",
        "无需手工分类",
        "submitRealAccount",
        "/api/r8/social/account",
        "真实连接状态",
        "不能通过下拉框自行标记",
        "更多设备控制",
        "待接入 / 50",
    ], "deep productization UI", failures)
    if "localStorage" in deep_ui:
        failures.append("global Growth ID must come from durable backend state, not localStorage")
    if "MutationObserver" in deep_ui:
        failures.append("deep productization must use explicit events, not a global DOM MutationObserver")
    require(deep_css, [
        ".deep-task-lock",
        ".deep-drop-zone",
        ".deep-account-truth",
        ".deep-device-more",
        ".deep-system-link",
    ], "deep productization visual system", failures)
    require(workbench, [
        "conversion_summary",
        "当前增长ID",
        "真实咨询 / 线索",
        "真实验证通过",
        "不会让用户手工勾选",
    ], "truthful conversion/account workbench", failures)
    require(run, ["deep_productization_patch", "growth_chain_patch"], "deep productization runtime install", failures)

    require(main_js, [
        "真实运营工作台",
        "更多运营工具",
        "r8-gate-details",
        "系统验收明细",
        "R8真实运营数据",
    ], "main console productization", failures)
    if "MutationObserver" in main_js:
        failures.append("main productization must use finite retries/events, not MutationObserver")
    require(main_css, [".operational-entry", ".nav-more", ".r8-gate-details"], "main console styles", failures)
    require(forms, ["main-productization.css", "main-productization.js"], "main productization loader", failures)

    required_actions = {
        "recents": "187",
        "volume_up": "24",
        "volume_down": "25",
        "rotate_left": "3",
        "rotate_right": "1",
    }
    for action, code in required_actions.items():
        if action not in b3 or code not in b3:
            failures.append(f"owner device control is not implemented: {action}")
        if action not in final:
            failures.append(f"owner device control is not exposed in UI: {action}")
    require(b3, ["OWNER_KEYEVENTS", "OWNER_ROTATIONS", "_require_owner_ready", "_audit_owner_control"], "audited owner controls", failures)

    # Never fake CRM/search results when external business data is absent.
    require(final, [
        "不生成虚构客户记录",
        "只记录真实验证结果",
        "未验证",
    ], "truthful empty-state contract", failures)

    if failures:
        raise SystemExit("\n".join(failures))
    print("PASS: V2.2.1 deep productization regression contract")


if __name__ == "__main__":
    main()
