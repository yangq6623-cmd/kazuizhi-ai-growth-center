from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "05_V2.0.0_Source" / "web"


def read(name: str) -> str:
    return (WEB / name).read_text(encoding="utf-8")


def require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"missing {label}: {needle}")


def main() -> None:
    js = read("r8_10_workbench.js")
    css = read("r8_10_workbench.css")
    memory = read("memory.js")

    # The workbench is an overlay over the proven #397 runtime, not a second app.
    require(memory, "/r8_10_workbench.css", "R8-10 stylesheet loader")
    require(memory, "/r8_10_workbench.js", "R8-10 script loader")
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

    # Connection truth: no writable bridge/API state is allowed to impersonate ChatGPT control.
    require(js, "/api/chatgpt-control/status", "explicit ChatGPT control status contract")
    require(js, "文件夹可写、运营桥在线或备用 API 已配置，都不能单独证明 ChatGPT 已连接", "connection truth warning")
    require(js, "未验证连接", "unverified default state")
    require(js, "备用 AI 接口（可选）", "optional backup AI copy")
    require(js, "默认关闭", "backup AI default-off policy")

    # Boss command remains safely unavailable until a verified round-trip connector exists.
    require(js, "r810-send-command", "owner command control")
    require(js, "button.disabled=!verified", "verified-connector command gate")
    require(js, "/api/chatgpt-control/commands", "future command transport contract")

    # Human attention and evolution are truthful views, not pretend automation.
    require(js, "human_items", "real human action source")
    require(js, "不会虚构软件缺陷", "self-evolution truth boundary")
    require(js, "创建开发任务", "DEV-MISSION control")
    require(js, "disabled title=", "disabled DEV-MISSION reason")

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

    print("PASS: R8-10 unified workbench navigation, UI truth, connection gating and visual shell verified.")


if __name__ == "__main__":
    main()
