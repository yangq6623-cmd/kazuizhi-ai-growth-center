from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "05_V2.0.0_Source" / "web"


def require(text: str, needle: str, label: str) -> None:
    if needle not in text:
        raise AssertionError(f"missing {label}: {needle}")


def forbid(text: str, needle: str, label: str) -> None:
    if needle in text:
        raise AssertionError(f"forbidden {label}: {needle}")


def main() -> None:
    async_ui = (WEB / "kz_async_control_ui.js").read_text(encoding="utf-8")
    workbench = (WEB / "r8_10_workbench.js").read_text(encoding="utf-8")

    # Owner-facing product truth: ordinary ChatGPT + private async bus is the
    # daily control path; realtime ChatGPT is an optional helper, not a red
    # global failure state.
    for text in (
        "日常主控",
        "私有异步控制总线",
        "日常 AI 主控",
        "实时 ChatGPT 通道（可选）",
        "未连接 · 不影响日常自治",
        "本地自治已经与实时 ChatGPT 解耦",
        "Work / Codex",
    ):
        require(async_ui, text, f"primary-control copy {text}")

    # The two channels must be read independently and never conflated.
    require(async_ui, "/api/async-control-bus/status", "async control bus status endpoint")
    require(async_ui, "/api/chatgpt-control/status", "optional realtime ChatGPT endpoint")
    require(async_ui, "Decision Pack", "Decision Pack daily-control semantics")
    require(async_ui, "Receipt", "truthful async receipt semantics")

    # Realtime direct command remains strictly gated on a verified round trip.
    require(async_ui, "实时辅助指令（可选）", "optional realtime command label")
    require(async_ui, "实时下达目标", "realtime command button label")
    require(workbench, "button.disabled=!verified", "verified realtime command gate")
    require(workbench, "/api/chatgpt-control/commands", "verified realtime command endpoint")

    # Do not turn an absent optional realtime channel into the primary alarm.
    forbid(async_ui, "AI自治：正常 · 实时ChatGPT：离线", "legacy realtime-first mission pill")

    print("PASS: async Control Bus is owner-facing daily control; local autonomy remains primary and realtime ChatGPT is optional.")


if __name__ == "__main__":
    main()
