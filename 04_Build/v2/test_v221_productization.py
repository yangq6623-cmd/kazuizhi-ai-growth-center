"""V2.2.1 productization regression contract.

The goal is not pixel-perfect testing. It prevents the known R8 UI/UX issues
from silently returning: inconsistent device state, background mirror polling,
technical-first navigation, unsupported owner controls, skeleton workbenches,
unverifiable business metrics, duplicate primary actions, and dead buttons.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "05_V2.0.0_Source" / "web"
INTEGRATIONS = ROOT / "05_V2.0.0_Source" / "integrations"


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
    main_js = read(WEB / "main-productization.js")
    main_css = read(WEB / "main-productization.css")
    forms = read(WEB / "forms.js")
    b3 = read(INTEGRATIONS / "android_device_b3.py")

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
        "health-normal",
        "health-config",
        "health-human",
        "loadFinalization",
        "operational-finalization.js",
        "loadUiPolish",
        "operational-ui-polish.css",
        "operational-ui-polish.js",
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
    print("PASS: V2.2.1 productization regression contract")


if __name__ == "__main__":
    main()
