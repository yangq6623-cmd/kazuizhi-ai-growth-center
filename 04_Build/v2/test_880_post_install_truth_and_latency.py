"""#880 post-install focused regressions.

Uses a synthetic LOCALAPPDATA only.  No browser action, production publication,
external AI request, search submission, paid API call or production mutation.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
import threading
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))

sandbox = Path(tempfile.mkdtemp(prefix="kazuizhi-880-post-install-"))
old_local = os.environ.get("LOCALAPPDATA")
old_profile = os.environ.get("USERPROFILE")
os.environ["LOCALAPPDATA"] = str(sandbox)
os.environ["USERPROFILE"] = str(sandbox)

try:
    from core import r7_engine
    from core import r8_22_autonomous_convergence as convergence
    from core import r8_23_growth_operating_system as growth_os
    from core import storage

    mission_id = "MISSION-20260924-DF7DB2"
    command_id = "CMD-20261019-073EED"
    storage.write_json(r7_engine.JOBS, {"items": [
        {"id": "mission-job", "mission_id": mission_id, "state": "completed", "execution_receipt": {"id": "R1"}},
        {"id": "command-job", "command_id": command_id, "state": "queued"},
        {"id": "historical-job", "mission_id": "MISSION-HISTORICAL", "state": "completed", "execution_receipt": {"id": "R2"}},
    ]})
    metrics = convergence._metrics(command_id, mission_id, include_seo_geo=False)
    tasks = metrics["tasks"]
    assert tasks["count_scope"] == "current_mission_or_command_tasks", tasks
    assert tasks["total"] == 2, tasks
    assert tasks["completed"] == 1, tasks
    assert tasks["queued"] == 1, tasks
    assert tasks["full_r7_ledger_total"] == 3, tasks

    old_connectors = growth_os._connector_rows
    old_gpu = growth_os.gpu_status
    calls = {"connectors": 0, "gpu": 0}

    def connectors_one():
        calls["connectors"] += 1
        return {}

    def gpu_one():
        calls["gpu"] += 1
        time.sleep(0.03)
        return {"detected": True, "ready": True, "rtx3060": True, "gpus": ["RTX 3060"]}

    try:
        growth_os._connector_rows = connectors_one
        growth_os.gpu_status = gpu_one
        growth_os._CAPABILITY_CACHE.update(at=0.0, key=None, rows=None)

        first = growth_os.capability_status(force=True)
        second = growth_os.capability_status()
        assert first == second
        assert calls == {"connectors": 1, "gpu": 1}, calls

        # A changed probe identity invalidates the cache.  This preserves focused
        # tests and runtime hot replacements without waiting for the TTL.
        def connectors_two():
            calls["connectors"] += 1
            return {}

        growth_os._connector_rows = connectors_two
        growth_os.capability_status()
        assert calls["connectors"] == 2, calls

        # Concurrent owner panels share one expensive readiness calculation.
        growth_os._CAPABILITY_CACHE.update(at=0.0, key=None, rows=None)
        calls.update(connectors=0, gpu=0)
        growth_os._connector_rows = connectors_one
        results = []
        failures = []

        def worker():
            try:
                results.append(growth_os.capability_status())
            except Exception as error:  # pragma: no cover - assertion reports below
                failures.append(error)

        threads = [threading.Thread(target=worker) for _ in range(8)]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=5)
        assert not failures, failures
        assert len(results) == 8, len(results)
        assert calls == {"connectors": 1, "gpu": 1}, calls
    finally:
        growth_os._connector_rows = old_connectors
        growth_os.gpu_status = old_gpu
        growth_os._CAPABILITY_CACHE.update(at=0.0, key=None, rows=None)

    print("PASS: #880 Mission scope truth and single-flight capability snapshot")
finally:
    if old_local is None:
        os.environ.pop("LOCALAPPDATA", None)
    else:
        os.environ["LOCALAPPDATA"] = old_local
    if old_profile is None:
        os.environ.pop("USERPROFILE", None)
    else:
        os.environ["USERPROFILE"] = old_profile
    shutil.rmtree(sandbox, ignore_errors=True)
