"""R7 UI interaction contract audit.

This test prevents visible buttons from shipping without an event path and verifies
that the main click actions have matching backend routes. It is intentionally
standard-library only so it can run in every Windows build.
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
    }
    for token, label in dynamic_contracts.items():
        if token not in scripts:
            failures.append(f"Missing dynamic interaction binding: {label} ({token})")

    visible_feedback = (
        "R7 状态已刷新",
        "客户需求信号已刷新",
        "任务状态已更新",
        "任务已创建，等待人工审批",
        "系统体检已完成",
    )
    for text in visible_feedback:
        if text not in scripts:
            failures.append(f"Missing visible feedback message: {text}")

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
        "/api/r7/jobs",
        "/api/r7/jobs/command",
        "/api/memory",
        "/api/operation-summary",
        "/api/tomorrow-plan",
    )
    for route in required_routes:
        if route not in server:
            failures.append(f"Frontend action has no backend route: {route}")

    if failures:
        raise SystemExit("\n".join(failures))

    print(f"PASS: {len(parser.buttons)} static buttons have interaction paths")
    print(f"PASS: {len(dynamic_contracts)} dynamic interaction families are bound")
    print(f"PASS: {len(required_routes)} action routes exist in backend")


if __name__ == "__main__":
    main()
