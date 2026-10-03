from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WEB = ROOT / "05_V2.0.0_Source" / "web"
STARTUP = WEB / "r8_12_startup_coordinator.js"
MANAGER = WEB / "r7_manager_patch.js"
WORKBENCH = WEB / "r8_10_workbench.js"
TRUTH = WEB / "r8_10_truth_convergence.js"


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    startup = STARTUP.read_text(encoding="utf-8")
    manager = MANAGER.read_text(encoding="utf-8")
    workbench = WORKBENCH.read_text(encoding="utf-8")
    truth = TRUTH.read_text(encoding="utf-8")

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

    # A browser primitive must never be replaced globally during startup. The #58
    # candidate used a fake MutationObserver while modules loaded; that can leave
    # modules with inconsistent observer semantics and hide real feedback loops.
    require("window.MutationObserver =" not in startup, "startup still monkeypatches the native MutationObserver")
    require("FiniteStartupObserver" not in startup, "finite fake observer policy is still present")
    require("yieldToBrowser" in startup, "owner-shell modules no longer yield to the browser between loads")
    require("__KZ_OWNER_HEARTBEAT_TIMER__" in startup, "runtime heartbeat for responsiveness checks is missing")

    # The owner workbench itself previously observed the whole body for childList
    # changes, while its callback rewrote textContent/innerHTML. textContent is a
    # childList mutation, so the observer could schedule itself forever.
    require("new MutationObserver" not in workbench, "owner workbench still installs a document-wide mutation feedback observer")
    require("scheduleMaintenance" in workbench, "owner workbench no longer has bounded event-driven maintenance")
    require("setText" in workbench, "owner workbench no longer avoids unchanged text writes")
    require("dataset.r810Built" in workbench, "owner workbench can rebuild large owner pages repeatedly")

    # Truth convergence previously watched the entire document including
    # characterData while converge() changed textContent itself. That creates a
    # self-sustaining mutation -> convergence -> mutation loop. Keep it bounded.
    require("new MutationObserver" not in truth, "truth convergence still installs a mutation feedback observer")
    require("characterData:true" not in truth.replace(" ", ""), "truth convergence still watches characterData")
    require("__KZ_R810_TRUTH_CONVERGENCE__" in truth, "truth convergence has no singleton guard")
    require("if(running)" in truth or "if (running)" in truth, "truth convergence has no reentrancy guard")
    require("setText" in truth, "truth convergence no longer avoids unchanged text writes")
    require("setInterval(()=>scheduleConvergence(0),30000)" in truth.replace(" ", ""), "truth convergence safety refresh is not bounded to low frequency")

    print("PASS: owner-shell startup is fail-soft, native-observer safe, and both workbench/truth layers are bounded without DOM mutation feedback loops")


if __name__ == "__main__":
    main()
