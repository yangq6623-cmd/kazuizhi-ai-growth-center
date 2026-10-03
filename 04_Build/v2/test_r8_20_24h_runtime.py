"""Accelerated 24-hour-equivalent resilience gate for the R8-20 desktop runtime.

A real 24-hour field soak still requires the owner's Windows PC.  This test
executes the equivalent 15-second scheduler heartbeat count (5,760 cycles),
injects recoverable failures, and statically gates the production entrypoint's
sleep prevention, worker isolation, fail-soft loops and bounded restart policy.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "05_V2.0.0_Source"


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    old_local = os.environ.get("LOCALAPPDATA")
    with tempfile.TemporaryDirectory(prefix="kz-r820-24h-") as temp:
        os.environ["LOCALAPPDATA"] = temp
        sys.path.insert(0, str(SRC))
        try:
            from core import runtime_resilience
            from core.storage import read_json

            started = runtime_resilience.start_process(keep_awake=False)
            require(started["process"]["running"], "runtime health did not enter running state")

            # 24 h / 15 s = 5,760 scheduler cycles.  Inject isolated failures;
            # the next successful heartbeat must recover instead of poisoning
            # the long-running worker state.
            failure_ticks = {101, 2001, 5001}
            for tick in range(5760):
                if tick in failure_ticks:
                    runtime_resilience.heartbeat(
                        "scheduler_core", ok=False,
                        error=TypeError(f"injected-{tick}"), detail=f"tick={tick}",
                    )
                else:
                    runtime_resilience.heartbeat("scheduler_core", ok=True, detail=f"tick={tick}")
                if tick % 4 == 0:
                    runtime_resilience.heartbeat("content_execution", ok=True, detail=f"cycle={tick // 4}")
                if tick % 20 == 0:
                    runtime_resilience.heartbeat("video_worker", ok=True, detail=f"cycle={tick // 20}")

            runtime_resilience.set_worker_enabled("chatgpt_relay", False, "not configured in synthetic soak")
            health = runtime_resilience.snapshot()
            scheduler = health["workers"]["scheduler_core"]
            require(scheduler["cycles"] == 5760, "24h-equivalent scheduler cycle count is wrong")
            require(scheduler["failures"] == len(failure_ticks), "injected failures were not counted")
            require(scheduler["consecutive_failures"] == 0, "worker did not recover after an isolated failure")
            require(scheduler["state"] == "healthy", "recovered scheduler is still marked unhealthy")
            require(health["workers"]["chatgpt_relay"]["state"] == "disabled", "optional relay incorrectly degrades runtime")
            require(health["health"] == "healthy", "24h-equivalent health did not converge to healthy")

            stopped = runtime_resilience.stop_process()
            require(not stopped["process"]["running"], "runtime health did not persist clean shutdown")
            persisted = read_json(runtime_resilience.STORE, {})
            require(not (persisted.get("process") or {}).get("running"), "persisted runtime state still says running")
            require((persisted.get("workers") or {}).get("scheduler_core", {}).get("cycles") == 5760,
                    "heartbeat counters were not durably persisted")
        finally:
            sys.path.remove(str(SRC))
            if old_local is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = old_local

    run_source = (SRC / "run.py").read_text(encoding="utf-8")
    patch_source = (SRC / "backend" / "r8_20_seo_geo_growth_patch.py").read_text(encoding="utf-8")
    storage_source = (SRC / "core" / "storage.py").read_text(encoding="utf-8")
    ai_source = (SRC / "integrations" / "ai_gateway.py").read_text(encoding="utf-8")
    relay_source = (SRC / "integrations" / "chatgpt_relay_agent.py").read_text(encoding="utf-8")

    require("SetThreadExecutionState" in run_source, "Windows sleep prevention is missing")
    require("start_content_execution_worker" in run_source, "slow AI/content work is not isolated from scheduler ticks")
    require("runtime_heartbeat" in run_source and "runtime_start_process" in run_source,
            "production entrypoint is not wired to runtime heartbeats")
    require("_run_main_with_recovery" in run_source and "MAX_PROCESS_RESTARTS_10_MIN" in run_source,
            "bounded process-level recovery is missing")
    require(run_source.count("except Exception as error") >= 7,
            "one or more long-running workers can still die on an ordinary unexpected exception")
    require("/api/r8-20/runtime-health" in patch_source, "runtime-health API is not exposed")
    require("os.replace" in storage_source and "os.fsync" in storage_source,
            "durable state writes are no longer atomic/fsynced")
    require("timeout=90" in ai_source and "timeout=15" in ai_source,
            "AI model calls/health probes are not timeout-bounded")
    require("timeout: int = 12" in relay_source,
            "ChatGPT relay network calls are not timeout-bounded")

    print("PASS: 5,760-cycle 24h-equivalent runtime soak + sleep prevention + isolated fail-soft workers + bounded restart/IO gates")


if __name__ == "__main__":
    main()
