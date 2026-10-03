"""Offline release gate for R8-23.3 Candidate field fixes."""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "05_V2.0.0_Source"
CORE = SRC / "core" / "r8_23_3_candidate.py"
PATCH = SRC / "backend" / "r8_23_3_candidate_patch.py"
UI = SRC / "web" / "r8_23_3_candidate.js"
TRUTH_PATCH = SRC / "core" / "r8_20_growth_truth_patch.py"
WEB_VERSION = SRC / "web" / "WEB_VERSION.txt"


def main():
    old_local = os.environ.get("LOCALAPPDATA")
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["LOCALAPPDATA"] = tmp
        sys.path.insert(0, str(SRC))
        try:
            from core import r8_23_3_candidate as candidate

            release = candidate.release_manifest()
            assert release["phase"] == "R8-23.3 Candidate"
            assert release["runtime_identity"] == "KZ-ENTERPRISE-V2.2.2-R8-AUTONOMOUS-20260922"
            assert release["funds_policy"] == "human_only"
            assert "formal_external_evidence" in release["truth_policy"]

            # Field regression: an old accepted Command must not become unusable merely
            # because its original created_at is >24h old while the real controller has
            # continued producing recent convergence/phase receipts.
            now = datetime.now().astimezone()
            old_command = (now - timedelta(days=7)).isoformat()
            fresh_receipt = (now - timedelta(minutes=2)).isoformat()
            original_active = candidate._active_link
            original_pending = candidate._pending_link
            original_state = candidate._state
            original_mission = candidate._mission
            try:
                candidate._active_link = lambda: {
                    "command_id": "CMD-ACTIVE", "status": "completed", "created_at": old_command,
                    "mission_id": "MISSION-ACTIVE", "objective": "持续SEO/GEO增长",
                }
                candidate._pending_link = lambda active_command_id=None: {
                    "command_id": "CMD-PENDING", "status": "queued_for_verified_connector",
                    "created_at": now.isoformat(),
                }
                candidate._state = lambda: {
                    "active_command_id": "CMD-ACTIVE",
                    "active_mission_id": "MISSION-ACTIVE",
                    "last_phase_receipt_at": fresh_receipt,
                    "updated_at": fresh_receipt,
                    "plan": {"plan_id": "PLAN-ACTIVE", "command_id": "CMD-ACTIVE", "mission_id": "MISSION-ACTIVE"},
                }
                candidate._mission = lambda: {
                    "mission_id": "MISSION-ACTIVE", "command_id": "CMD-ACTIVE",
                    "command_status": "completed", "command_objective": "持续SEO/GEO增长",
                }
                truth = candidate.single_truth()
                assert truth["active_command_id"] == "CMD-ACTIVE"
                assert truth["pending_command_id"] == "CMD-PENDING"
                assert truth["consistent"] is True
                lease = candidate.controller_lease()
                assert lease["valid"] is True
                assert lease["remaining_minutes"] > 0
                pack = candidate.decision_pack()
                assert pack["valid"] is True
                assert pack["command_id"] == "CMD-ACTIVE"
                assert pack["plan_id"] == "PLAN-ACTIVE"
                assert "human_only" == release["funds_policy"]
                assert "真实外部A/B Evidence" in candidate.snapshot()["formal_geo_rule"]
            finally:
                candidate._active_link = original_active
                candidate._pending_link = original_pending
                candidate._state = original_state
                candidate._mission = original_mission

            core = CORE.read_text(encoding="utf-8")
            patch = PATCH.read_text(encoding="utf-8")
            ui = UI.read_text(encoding="utf-8")
            truth_patch = TRUTH_PATCH.read_text(encoding="utf-8")
            web_version = WEB_VERSION.read_text(encoding="utf-8")

            for marker in (
                "controller_lease", "active_command_id", "pending_command_id",
                "execution_stalled", "attention_summary", "DUE_JOB_EXECUTION_STALL",
                "SEO/GEO关键语义节点", "正式GEO成绩只认真实外部AI/浏览器A/B Evidence",
            ):
                assert marker in core, marker
            for marker in (
                "/api/r8-23-3/candidate", "/api/version", "/api/readiness", "/api/health",
                "kz-r8233-booting", "r8_23_3_candidate.js", "pilot.decision_pack = candidate.decision_pack",
            ):
                assert marker in patch, marker
            for marker in (
                "dedupeNavigation", "foldLegacyLedger", "foldGeoAdvanced",
                "waiting_external_validation", "待确认Command", "bootHandshake",
            ):
                assert marker in ui, marker
            assert "r8_23_3_candidate_patch" in truth_patch
            assert "R8-23.3 Candidate Runtime Execution & UI Convergence" in web_version
            assert "Runtime Build: KZ-ENTERPRISE-V2.2.2-R8-AUTONOMOUS-20260922" in web_version

            print("PASS: R8-23.3 restores due execution with a rolling verified control lease, separates active/pending Command truth, exposes explicit blockers, and prevents legacy first-paint/duplicate owner UI without weakening formal Evidence or finance gates")
        finally:
            if sys.path and sys.path[0] == str(SRC):
                sys.path.pop(0)
            if old_local is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = old_local


if __name__ == "__main__":
    main()
