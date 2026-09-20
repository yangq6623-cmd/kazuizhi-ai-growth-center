"""R7/R8 UI interaction and V2.2.1 productization contract audit.

This test prevents visible buttons from shipping without an event path, verifies
that card-like controls and the main click actions have matching feedback/routes,
and protects the V2.2.1 operational workbench from device-state drift or recursive
DOM observers.
"""
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "05_V2.0.0_Source" / "web"
SERVER = ROOT / "05_V2.0.0_Source" / "backend" / "server.py"


class ButtonParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.buttons = []
        self._current = None

    def handle_starttag(self, tag, attrs):
        if tag != "button":
            return
        data = dict(attrs)
        data["text"] = ""
        self.buttons.append(data)
        self._current = data

    def handle_data(self, data):
        if self._current is not None:
            self._current["text"] += data.strip()

    def handle_endtag(self, tag):
        if tag == "button":
            self._current = None


def main():
    html = (WEB / "index.html").read_text(encoding="utf-8")
    scripts = "\n".join(path.read_text(encoding="utf-8") for path in WEB.glob("*.js"))
    persistence_patch = (WEB / "r8_persistence_patch.js").read_text(encoding="utf-8")
    operational = (WEB / "operational.js").read_text(encoding="utf-8")
    device = (WEB / "operational-device.js").read_text(encoding="utf-8")
    productization = (WEB / "operational-productization.js").read_text(encoding="utf-8")
    workbench = (WEB / "operational-workbench.js").read_text(encoding="utf-8")
    search = (WEB / "operational-search.js").read_text(encoding="utf-8")
    server = SERVER.read_text(encoding="utf-8")

    parser = ButtonParser()
    parser.feed(html)
    failures = []

    for button in parser.buttons:
        classes = set((button.get("class") or "").split())
        button_id = button.get("id")
        label = button.get("text") or button_id or "unnamed"
        if "nav" in classes:
            bound = "document.querySelectorAll('.nav')" in scripts
        elif "go-page" in classes:
            bound = "document.querySelectorAll('.go-page')" in scripts
        elif "data-generator" in button:
            bound = "[data-generator]" in scripts
        elif "data-task-filter" in button:
            bound = "[data-task-filter]" in scripts
        else:
            bound = bool(button_id) and f"$('" + button_id + "').addEventListener('click'" in scripts
        if not bound:
            failures.append(f"Visible button has no click binding: {label!r} id={button_id!r} class={button.get('class')!r}")

    dynamic_contracts = {
        ".r7-action": "R7 task action buttons",
        ".keyword-item": "keyword selection buttons",
        ".history-item": "promotion history buttons",
        "[data-task-index]": "task status selectors",
        ".ai-role-action": "AI collaboration cards",
        ".r7-agent-action": "AI employee cards",
        ".integration-card-action": "integration status cards",
        "bindInteractiveCard": "dashboard/review/analytics summary cards",
        "bindR7OverviewActions": "R7 workflow/exception/migration overview cards",
        "ensureBridgePanel": "bidirectional operations bridge panel",
        "renderDashboardBridge": "dashboard bridge state cards",
    }
    for token, label in dynamic_contracts.items():
        if token not in scripts:
            failures.append(f"Missing dynamic interaction binding: {label} ({token})")

    visible_feedback = (
        "今日任务、AI 员工和完成进度已刷新",
        "公开需求信号已刷新；真实客户数据仍以接入状态为准",
        "任务状态已更新",
        "任务已进入自动执行队列",
        "已记录为平台人工待处理",
        "系统体检已完成",
        "已打开自动任务与 AI 员工",
        "真实经营数据尚未实时接入",
        "双向运营桥已连接",
        "当前未连接云端桥，已保持本地自主运行",
        "资金操作按安全策略永久禁止自动执行",
        "正在查看",
    )
    for text in visible_feedback:
        if text not in scripts:
            failures.append(f"Missing visible feedback message: {text}")

    for text in ("全自动", "平台人工待处理", "执行成果：", "自动待执行", "自动执行中"):
        if text not in scripts:
            failures.append(f"Autonomous UI copy missing: {text}")

    required_routes = (
        "/api/daily-review/generate",
        "/api/business-metrics/import",
        "/api/promotion/keywords",
        "/api/promotion/seo-content",
        "/api/promotion/geo-plan",
        "/api/promotion/ad-copy",
        "/api/promotion/video-script",
        "/api/operations/tasks",
        "/api/operations/tasks/update",
        "/api/operations/calendar/generate",
        "/api/insights/competition",
        "/api/integrations/ai/configure",
        "/api/integrations/ai/test",
        "/api/ai/command",
        "/api/system/diagnostics",
        "/api/bridge/status",
        "/api/bridge/commands",
        "/api/bridge/configure",
        "/api/bridge/disable",
        "/api/bridge/sync",
        "/api/bridge/report",
        "/api/r7/jobs",
        "/api/r7/jobs/command",
        "/api/memory",
        "/api/operation-summary",
        "/api/tomorrow-plan",
    )
    for route in required_routes:
        if route not in server:
            failures.append(f"Frontend action has no backend route: {route}")

    # A broad child-list observer previously refreshed business persistence after
    # every text update, including its own button label changes. That recursive
    # request loop made the otherwise loaded dashboard appear frozen.
    for token in ("refreshScheduled", "refreshRunning", "record.addedNodes", "inputWasAdded"):
        if token not in persistence_patch:
            failures.append(f"Business persistence loop guard missing: {token}")
    if "new MutationObserver(() =>" in persistence_patch:
        failures.append("Business persistence must not observe every page mutation")

    # V2.2.1: one truthful device state contract must drive both the device page
    # and the health page. The old top-level device.status check was incompatible
    # with the actual /api/r8/device/status payload.
    if "device.status==='online'" in operational:
        failures.append("Operational health still relies on obsolete top-level device.status")
    for token in ("deviceSnapshot", "primary_device_id", "operational:device-status"):
        if token not in operational:
            failures.append(f"Unified operational device state missing: {token}")

    # Continuous mirroring must recover from short ADB drops without clearing the
    # last good frame, and it must stop when the user leaves the device page.
    for token in ("FAILURE_LIMIT=3", "recoverDevice", "lastSuccessAt", "自动重试", "已保留上一帧", "deviceCenterDeactivate=()=>stop(true)"):
        if token not in device:
            failures.append(f"V2.2.1 device recovery contract missing: {token}")

    # Productization must use explicit events, not a new all-page MutationObserver.
    if "MutationObserver" in productization or "MutationObserver" in workbench:
        failures.append("V2.2.1 productization must not add broad DOM observers")
    for token in ("owner-todo", "待我处理", "health-action", "operational:refreshed"):
        if token not in productization and token not in operational:
            failures.append(f"V2.2.1 owner/health workbench missing: {token}")
    for token in ("account-workbench", "conversion-workbench", "search-summary"):
        if token not in workbench:
            failures.append(f"V2.2.1 business workbench missing: {token}")
    if "operational:search-updated" not in search:
        failures.append("SEO/GEO workbench is not synchronized after search updates")

    if failures:
        raise SystemExit("\n".join(failures))

    print(f"PASS: {len(parser.buttons)} static buttons have interaction paths")
    print(f"PASS: {len(dynamic_contracts)} dynamic interaction families are bound")
    print(f"PASS: {len(required_routes)} action routes exist in backend")
    print("PASS: V2.2.1 device recovery, owner todo, health, account, conversion and SEO/GEO workbench contracts")


if __name__ == "__main__":
    main()
