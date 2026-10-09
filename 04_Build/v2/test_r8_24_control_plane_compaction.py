"""Regression gate for the real #774 local-service starvation failure."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "05_V2.0.0_Source"
STARTUP = SRC / "web" / "r8_12_startup_coordinator.js"
CONTROL_PATCH = SRC / "backend" / "async_control_bus_patch.py"
RUN = SRC / "run.py"


def main():
    previous = os.environ.get("LOCALAPPDATA")
    # Keep the test root inside the checkout. Windows Store sandbox path
    # virtualization can make the process-wide default temp directory unwritable.
    with tempfile.TemporaryDirectory(dir=ROOT / "04_Build" / "v2") as temporary:
        os.environ["LOCALAPPDATA"] = temporary
        sys.path.insert(0, str(SRC))
        try:
            from core import r8_22_autonomous_convergence as convergence
            from core.storage import data_root, write_json

            heavy_rows = [
                {
                    "id": f"GEO-{index:04d}",
                    "question_text": "现场真实机会" * 40,
                    "decision": "保留真实证据边界" * 30,
                }
                for index in range(180)
            ]
            status = {
                "enabled": True,
                "mode": "autonomous",
                "last_run_at": "2026-10-09T20:44:32+08:00",
                "human_item_count": 1,
                "today": {"completed": 131, "failed": 0},
                "policy": {"auto_technical_audit": True},
                "r8_20_growth": {
                    "state": "running",
                    "summary": {"signals": 156, "opportunities": 131},
                    "opportunities": heavy_rows,
                },
                "runtime_health": {"state": "healthy"},
                "geo_growth_os": {
                    "state": "running",
                    "enabled": True,
                    "mission": "持续提高真实 GEO 曝光",
                    "formal_ab_completed": 2,
                    "formal_ab_target": 50,
                    "summary": {"signals": 156, "opportunities": 131},
                    "opportunities": heavy_rows,
                },
                "connector_routes": {"rows": heavy_rows},
            }
            receipts = [
                {
                    "receipt_id": f"PHASE-{index:04d}",
                    "kind": "r8_22_phase_receipt",
                    "created_at": "2026-10-09T20:44:32+08:00",
                    "command_id": "CMD-OWNER",
                    "mission_id": "MISSION-OWNER",
                    "metrics": {
                        "tasks": {"total": 200, "completed": 200, "failed": 0},
                        "seo_geo": status,
                    },
                    "human_blockers": 1,
                    "deferred_channels": 6,
                    "truth_note": "正式 A/B 只认真实 Evidence。",
                }
                for index in range(36)
            ]
            write_json(convergence.STATE_FILE, {
                "schema": 1,
                "active_command_id": "CMD-OWNER",
                "active_mission_id": "MISSION-OWNER",
                "plan": None,
                "phase_receipts": receipts,
                "last_phase_receipt_at": "2026-10-09T20:44:32+08:00",
                "updated_at": "2026-10-09T20:44:32+08:00",
            })
            path = data_root() / convergence.STATE_FILE
            legacy_size = path.stat().st_size
            assert legacy_size > 4_000_000, legacy_size

            state = convergence._load_state()
            compact_size = path.stat().st_size
            assert compact_size < legacy_size * 0.08, (legacy_size, compact_size)
            assert len(state["phase_receipts"]) == 36
            receipt = state["phase_receipts"][-1]
            seo_geo = receipt["metrics"]["seo_geo"]
            assert seo_geo["snapshot_mode"] == "phase_receipt_compact_v1"
            assert seo_geo["geo_growth_os"]["formal_ab_completed"] == 2
            assert seo_geo["geo_growth_os"]["formal_ab_target"] == 50
            serialized = json.dumps(state, ensure_ascii=False)
            assert "question_text" not in serialized
            assert "connector_routes" not in serialized

            # The compact format is stable and must not rewrite on every poll.
            mtime = path.stat().st_mtime_ns
            convergence._load_state()
            assert path.stat().st_mtime_ns == mtime

            startup = STARTUP.read_text(encoding="utf-8")
            assert "primeScriptSources(SCRIPT_SEQUENCE, SCRIPT_TIMEOUT_MS)" in startup
            control_patch = CONTROL_PATCH.read_text(encoding="utf-8")
            assert "start_background_agent" not in control_patch
            run_source = RUN.read_text(encoding="utf-8")
            bind_at = run_source.index("server = create_server(args.port)")
            agent_at = run_source.index("start_background_agent()")
            assert agent_at > bind_at
            print(
                "PASS: legacy control-plane receipts compact on first read, preserve 2/50 truth, "
                "remain stable, reduce cold-start traffic, and defer the control-bus agent until port ownership"
            )
        finally:
            if sys.path and sys.path[0] == str(SRC):
                sys.path.pop(0)
            if previous is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = previous


if __name__ == "__main__":
    main()
