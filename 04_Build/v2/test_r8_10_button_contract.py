from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "05_V2.0.0_Source" / "web"
JS = (WEB / "r8_10_workbench.js").read_text(encoding="utf-8")
CSS = (WEB / "r8_10_workbench.css").read_text(encoding="utf-8")
INDEX = (WEB / "index.html").read_text(encoding="utf-8")
APP = (WEB / "app.js").read_text(encoding="utf-8")
OPERATIONAL = (WEB / "operational.html").read_text(encoding="utf-8")
OPERATIONAL_JS = (WEB / "operational.js").read_text(encoding="utf-8")


def require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"missing {label}: {needle}")


def main() -> None:
    # Six primary buttons must route to an existing owner-facing page, a page
    # created by the legacy R7/R8 shell, or a synthetic R8-10 page.
    routes = {
        "老板总控": "dashboard",
        "AI决策中心": "workflow",
        "执行中心": "operational-hub",
        "待我处理": "r810-attention",
        "经营结果": "analytics",
        "自进化中心": "r810-evolution",
    }
    for label, target in routes.items():
        require(JS, f"label:'{label}'", f"primary button {label}")
        require(JS, f"target:'{target}'", f"route target {target}")
        if target.startswith("r810-"):
            require(JS, f"ensureProxyPage('{target}'", f"synthetic page {target}")
        elif target == "operational-hub":
            require(APP, "section.id='operational-hub'", "dynamically created execution page")
            require(APP, "button.dataset.page='operational-hub'", "execution navigation proxy")
        else:
            require(INDEX, f'id="{target}"', f"existing page {target}")

    # Decision sub-tabs must use real existing R7 pages and route through the
    # same openRoute() function rather than creating inert buttons.
    for target in ("workflow", "insights", "review", "plan", "memory"):
        require(INDEX, f'id="{target}"', f"decision page {target}")
    require(JS, "tabs.querySelectorAll('button').forEach(btn=>btn.addEventListener('click',()=>openRoute(btn.dataset.target)))", "decision tab click handler")

    # Execution tabs are embedded R8 routes. Their labels must map to page IDs
    # that exist in operational.html, and every click goes through the iframe
    # changeOperationalPage() bridge.
    execution = ("dashboard", "content", "search", "accounts", "device", "conversion", "health")
    for target in execution:
        require(OPERATIONAL, f'id="{target}"', f"embedded execution page {target}")
    require(JS, "changeOperationalPage?.(page)", "embedded execution click bridge")
    require(JS, "data-execution-page", "execution button target attribute")

    # Publish review wording must be truthful at the source, not dependent on a
    # late presentation patch. Approval authorizes queue entry only; it does not
    # claim that an external platform publication has happened.
    require(OPERATIONAL_JS, "审核通过，进入发布队列", "truthful publish authorization button")
    require(OPERATIONAL_JS, "没有真实平台 URL / Post ID / Receipt 不算发布成功", "real publication receipt truth gate")
    if ">通过并发布</button>" in OPERATIONAL_JS:
        raise AssertionError("misleading source button still says 通过并发布")

    # Owner command is intentionally gated by verified ChatGPT control state.
    # Disabled must be visibly disabled and must explain why.
    require(JS, "button.disabled=!verified", "owner command verification gate")
    require(JS, "当前 ChatGPT Control Connector 尚未完成双向验证", "owner command disabled reason")
    require(CSS, "button:disabled", "disabled button appearance")
    require(JS, "auditDisabledButtons", "generic disabled reason audit")

    # Self-evolution cannot expose an inert or pretend working button.
    require(JS, "id=\"r810-dev-mission-disabled\" disabled", "DEV-MISSION disabled state")
    require(JS, "自动创建 DEV-MISSION 的后端写入接口将在自进化阶段接入", "DEV-MISSION disabled reason")

    # Human-attention action buttons must route back into the actual execution
    # pages or legacy R7 pages, rather than being visual-only controls.
    require(JS, "data-attention-page", "human attention action target")
    require(JS, "switchExecutionPage(page", "human attention execution routing")
    require(JS, "else openRoute(page)", "human attention R7 routing")

    # Mission-bar buttons must both carry a route and have an actual handler.
    require(JS, "data-r810-route=\"workflow\"", "mission AI decision button")
    require(JS, "data-r810-route=\"operational-hub\"", "mission pipeline button")
    require(JS, "bar.querySelectorAll('[data-r810-route]').forEach", "mission button click handler")

    # No standalone second-workbench button is allowed in the owner-facing UI.
    require(CSS, "#operational-open-window{display:none!important}", "hide second workbench entry")

    print("PASS: R8-10 owner-facing buttons and navigation routes are wired or explicitly disabled with reasons.")


if __name__ == "__main__":
    main()
