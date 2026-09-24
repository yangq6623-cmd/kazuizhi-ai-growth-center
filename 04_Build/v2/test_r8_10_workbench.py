from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "05_V2.0.0_Source" / "web"


def read(name: str) -> str:
    return (WEB / name).read_text(encoding="utf-8")


def require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"missing {label}: {needle}")


def forbid(text: str, needle: str, label: str) -> None:
    if needle in text:
        raise AssertionError(f"forbidden {label}: {needle}")


def main() -> None:
    js = read("r8_10_workbench.js")
    css = read("r8_10_workbench.css")
    memory = read("memory.js")
    startup = read("r8_12_startup_coordinator.js")
    truth = read("r8_10_truth_convergence.js")
    operational_workbench = read("operational-workbench.js")
    product = read("main-productization.js")

    # The workbench remains an overlay over the proven #397 runtime, but R8-12.1
    # now sequences all owner overlays through one deterministic startup owner.
    require(memory, "/r8_10_workbench.css", "R8-10 stylesheet loader")
    require(memory, "/r8_12_startup_coordinator.js", "R8-12.1 startup coordinator loader")
    require(startup, "/r8_10_workbench.js", "R8-10 coordinated script loader")
    require(startup, "/r8_10_truth_convergence.js", "coordinated truth convergence loader")
    require(startup, "r810:workbench-ready", "explicit workbench-ready dispatch")
    require(startup, "kz:app-ready", "single app-ready dispatch")
    require(startup, "forceInitialDashboardOnce", "deterministic initial owner route")
    require(startup, "dedupeGeneratedSingletons", "generated UI singleton guard")
    require(js, "基于 #397 稳定底座", "rollback baseline copy")

    # Exactly the six owner-facing primary destinations agreed for R8-10.
    for label in ("老板总控", "AI决策中心", "执行中心", "待我处理", "经营结果", "自进化中心"):
        require(js, label, f"primary navigation {label}")
    for label in ("系统状态与连接", "历史与审计", "高级设置"):
        require(js, label, f"secondary navigation {label}")

    # R7/R8 remain internal capabilities; the owner gets one embedded execution center.
    require(js, "不再出现第二套工作台", "single-workbench product copy")
    require(js, "switchExecutionPage", "embedded R8 execution navigation")
    require(css, "#operational-open-window{display:none", "hide second-workbench window action")

    # Legacy operational.html must never become a second top-level workbench.
    require(operational_workbench, "window.top===window.self&&isLegacyOperationalPage()", "standalone legacy shell guard")
    require(operational_workbench, "window.location.replace('/index.html')", "legacy shell redirect to unified workbench")
    require(operational_workbench, "r810-embedded-operational", "embedded execution mode")
    require(operational_workbench, ".sidebar,body.r810-embedded-operational main>header", "hide legacy sidebar and header inside execution center")
    require(operational_workbench, "window.frameElement", "single-shell iframe sizing contract")
    require(operational_workbench, "ResizeObserver", "embedded workbench auto-height contract")
    require(operational_workbench, "scrolling','no", "no nested execution scrollbar")

    # #398 shell cleanup remains finite/event-driven. During cold start the new
    # coordinator temporarily bounds legacy MutationObservers instead of letting
    # independent global observers race and duplicate owner cards.
    require(product, "lockSingleShell", "single-shell nav lock")
    require(product, "button.nav,.nav-group,details.nav-more,.operational-entry", "legacy nav catch-all")
    require(product, "setInterval", "finite late-navigation convergence")
    require(product, "operational:refreshed", "explicit operational refresh event")
    require(product, "r810:workbench-ready", "explicit workbench ready event")
    forbid(product, "MutationObserver", "unbounded productization mutation watcher")
    require(startup, "FiniteStartupObserver", "bounded legacy observer startup policy")
    require(product, "r810-legacy-route", "legacy navigation hidden class")
    forbid(product, "function addOperationalEntry", "legacy second-workbench entry creator")
    forbid(product, "function simplifyNavigation", "legacy nav-more rebuild")

    # Old 'AI brain one-time config' is not allowed in owner-facing navigation anymore.
    require(product, "hideLegacyBrainEntry", "legacy AI brain entry cleanup")
    require(product, "AI大脑", "legacy AI brain text detector")
    require(product, "一次配置", "legacy one-time config text detector")
    require(product, "r810-legacy-brain-entry", "legacy AI brain hidden marker")

    # Mission identity truth: KZ growth IDs are not mislabeled as Mission IDs.
    require(product, "normalizeMissionIdentity", "mission/growth identity normalization")
    require(product, "Growth ID / 当前增长任务", "growth ID label")
    require(product, "当前 Mission", "Mission label")

    # Connection truth: no writable bridge/API state is allowed to impersonate ChatGPT control.
    require(js, "/api/chatgpt-control/status", "explicit ChatGPT control status contract")
    require(js, "文件夹可写、运营桥在线或备用 API 已配置，都不能单独证明 ChatGPT 已连接", "connection truth warning")
    require(js, "未验证连接", "unverified default state")
    require(js, "备用 AI 接口（可选）", "optional backup AI copy")
    require(js, "默认关闭", "backup AI default-off policy")

    # Owner connection page now defaults to a simple four-life-line summary; technical details are opt-in.
    require(product, "ensureConnectionOwnerSummary", "owner connection summary")
    for label in ("ChatGPT 总控", "本地自治执行", "经营数据", "当前异常"):
        require(product, label, f"owner connection summary {label}")
    require(product, "查看高级技术详情", "technical detail opt-in")
    require(product, "data-r810-technical", "technical detail gating")

    # Boss command remains safely unavailable until a verified round-trip connector exists.
    require(js, "r810-send-command", "owner command control")
    require(js, "button.disabled=!verified", "verified-connector command gate")
    require(js, "/api/chatgpt-control/commands", "future command transport contract")

    # Human attention and evolution are truthful views, not pretend automation.
    require(js, "human_items", "real human action source")
    require(js, "不会虚构软件缺陷", "self-evolution truth boundary")
    require(js, "创建开发任务", "DEV-MISSION control")
    require(js, "disabled title=", "disabled DEV-MISSION reason")

    # Four field-acceptance truth fixes must be continuously enforced on the owner UI.
    require(truth, "action_center?.human_items", "single current-Mission owner attention source")
    require(truth, "自治闭环成熟度", "dynamic closed-loop maturity label")
    require(truth, "当前首要阻塞", "dynamic current blocker")
    require(truth, "今日例行任务完成度", "daily routine progress label")
    require(truth, "例行任务 100% 不代表当前 Mission 已完成", "Mission progress separation")
    require(truth, "审核通过，进入发布队列", "truthful publish authorization label")
    require(truth, "URL / Post ID / Receipt 不算发布成功", "real publish receipt gate")
    require(truth, "patchEmbeddedExecution", "embedded execution truth convergence")

    # Business visualization must explicitly keep missing dimensions empty rather than fabricate scores.
    require(js, "经营转化漏斗", "business funnel")
    require(js, "服务经营雷达", "service radar")
    require(js, "区域 × 服务机会", "region-service opportunity view")
    require(js, "不会用估算数字代替", "no fabricated funnel data")
    require(js, "#398 不用虚构分数填充雷达图", "no fabricated radar data")

    # UI quality baseline: disabled controls must explain why, and core shell is responsive.
    require(js, "auditDisabledButtons", "disabled button audit")
    require(css, "button:disabled", "disabled visual state")
    require(css, "@media(max-width:760px)", "responsive shell")

    print("PASS: R8-10 single-shell and R8-12.1 deterministic startup contracts verified.")


if __name__ == "__main__":
    main()
