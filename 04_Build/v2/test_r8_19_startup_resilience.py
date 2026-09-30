from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "05_V2.0.0_Source" / "web"
STARTUP = WEB / "r8_12_startup_coordinator.js"
MANAGER = WEB / "r7_manager_patch.js"


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    startup = STARTUP.read_text(encoding="utf-8")
    manager = MANAGER.read_text(encoding="utf-8")

    require(MANAGER.exists(), "AI employee manager patch is missing from packaged web source")
    require("Loaded after r7.js" in manager, "manager patch no longer documents the required r7.js ordering")
    require("'/r7_manager_patch.js'" in startup, "startup coordinator does not load AI employee manager patch")
    require(
        startup.index("'/r7_manager_patch.js'") < startup.index("'/r8_10_workbench.js'"),
        "AI employee manager must load after static r7.js and before the R8 owner-shell workbench",
    )
    require("SCRIPT_TIMEOUT_MS" in startup, "startup script loading has no timeout and can hang the UI")
    require("loadScriptFailSoft" in startup, "owner-shell module loading is still fail-hard")
    require("failed_modules" in startup and "degraded" in startup, "startup degradation state is not exposed")
    require("kz:startup-module-failed" in startup, "startup module failures are not surfaced as recoverable events")
    require(
        "state.phase = state.failed_modules.length ? 'degraded' : 'ready'" in startup,
        "a single module failure can still prevent the owner shell from reaching a usable state",
    )
    require("emit('kz:app-ready'" in startup, "degraded startup no longer emits the app-ready event")
    require("R8-19" in startup, "startup release fallback regressed to a stale R8 identity")

    print("PASS: AI employee manager loads before owner shell; individual module failures degrade instead of freezing the app")


if __name__ == "__main__":
    main()
