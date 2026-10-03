"""Offline release gate for R8-23.2 Runtime Truth & Closed-Loop Acceptance."""
from __future__ import annotations

import json
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "05_V2.0.0_Source"
CORE = SRC / "core" / "r8_23_2_runtime_truth.py"
PATCH = SRC / "backend" / "r8_23_2_runtime_truth_patch.py"
UI = SRC / "web" / "r8_23_2_runtime_truth.js"
MANIFEST = SRC / "core" / "release_manifest.json"
TRUTH_PATCH = SRC / "core" / "r8_20_growth_truth_patch.py"
WORKFLOW = ROOT / ".github" / "workflows" / "build_r8_20_seo_geo_growth.yml"
SCOPE = ROOT / "04_Build" / "v2" / "R8_23_2_RUNTIME_TRUTH_CLOSED_LOOP_SCOPE.md"


def main():
    old_local = os.environ.get("LOCALAPPDATA")
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["LOCALAPPDATA"] = tmp
        sys.path.insert(0, str(SRC))
        try:
            from core import r8_23_2_runtime_truth as truth

            identity = truth.release_identity()
            assert identity["release"] == "R8-23.2 Pilot RC1"
            assert identity["phase"] == "Runtime Truth & Closed-Loop Acceptance"
            assert identity["api_contract"] == "r8-23.2/v1"
            assert identity["complete"] is True

            # Model policy is task-based, not a fake fixed percentage.
            local = truth.model_route_for("batch_tagging", local_ready=True, doubao_ready=True)
            seo = truth.model_route_for("seo_semantic_qc", local_ready=True, doubao_ready=True)
            geo = truth.model_route_for("geo_gap_analysis", local_ready=True, doubao_ready=True)
            assert local["primary"] == "local_model" and local["required"] is False
            assert seo["primary"] == "doubao_cloud" and seo["required"] is True
            assert geo["primary"] == "doubao_cloud" and geo["required"] is True
            assert "geo_gap_analysis" in truth.DOUBAO_REQUIRED_STAGES
            assert "seo_semantic_qc" in truth.DOUBAO_REQUIRED_STAGES

            # ChatGPT issues a bounded Decision Pack; local scheduler can execute
            # already-authorized low-risk work inside the lease.
            control = {
                "consistent": True,
                "command_id": "CMD-R8232",
                "mission_id": "MISSION-R8232",
                "plan_id": "PLAN-R8232",
                "mission": {"goal": "7x24推广卡嘴子"},
                "plan": {"objective": "7x24推广卡嘴子"},
            }
            pack = truth.ensure_decision_pack(control)
            assert pack["controller"] == "ChatGPT sole strategic controller"
            assert pack["executor"] == "deterministic local scheduler/workers"
            assert pack["ttl_hours"] == 24
            assert pack["external_policy"]["funds"] == "permanently_human_only"
            assert set(pack["allowed_business_engines"]) == {"repair_services", "personal_tasks"}
            assert len(pack["allowed_ai_employees"]) == 8

            # Local completion cannot silently become external success.
            local_receipt = truth.receipt_truth({
                "state": "completed",
                "execution_receipt": {"receipt_id": "LOCAL-1"},
                "result": {"summary": "done"},
            })
            assert local_receipt["state"] == "LOCAL_EXECUTED"
            assert local_receipt["formal_external"] is False
            public_receipt = truth.receipt_truth({
                "state": "completed",
                "result": {"verified_public": True, "public_url": "https://example.com/a"},
            })
            assert public_receipt["state"] == "PUBLISHED"
            assert public_receipt["formal_external"] is True

            assert truth.TRUTH_STATES[:6] == ("CONFIGURED", "INVOKED", "GENERATED", "QC_PASSED", "PUBLISHED", "SUBMITTED")
            assert truth.TRUTH_STATES[-1] == "BUSINESS_ORDER"

            manifest = json.loads(MANIFEST.read_text(encoding="utf-8"))
            assert manifest["business_scope"].endswith("no money/amount/revenue/profit/ROI automation")
            assert manifest["field_acceptance"]["24h"] == "pending_real_field_run"
            assert manifest["field_acceptance"]["72h"] == "pending_real_fault_recovery_run"
            assert manifest["field_acceptance"]["7d"] == "pending_real_production_run"

            core = CORE.read_text(encoding="utf-8")
            patch = PATCH.read_text(encoding="utf-8")
            ui = UI.read_text(encoding="utf-8")
            truth_patch = TRUTH_PATCH.read_text(encoding="utf-8")
            workflow = WORKFLOW.read_text(encoding="utf-8")
            scope = SCOPE.read_text(encoding="utf-8")

            for marker in (
                "release_identity", "canonical_control", "ensure_decision_pack", "model_route_for",
                "govern_queue", "duplicate_suppressed", "stale_running_recovered", "receipt_truth",
                "human_pending", "readiness", "DOUBAO_REQUIRED_STAGES",
            ):
                assert marker in core, marker
            for marker in (
                "/api/health", "/api/runtime-health", "/api/version", "/api/readiness",
                "/api/r8-23-2/runtime-truth", "/api/r8-23-2/decision-pack",
                "/api/r8-23-2/model-routing", "r8_23_2_runtime_truth.js",
            ):
                assert marker in patch, marker
            for marker in ("当前 Command", "控制租约", "真正需要老板", "Receipt / Evidence", "计划等待"):
                assert marker in ui, marker
            assert "r8_23_2_runtime_truth_patch" in truth_patch
            assert "test_r8_23_2_runtime_truth.py" in workflow
            for marker in (
                "19 engineering work packages", "24h", "72h", "7-day",
                "Doubao", "single active Command", "one real social platform",
            ):
                assert marker in scope, marker

            print("PASS: R8-23.2 locks runtime identity/control truth, Decision Pack lease, queue recovery, truthful evidence states and local+Doubao SEO/GEO routing")
        finally:
            if sys.path and sys.path[0] == str(SRC):
                sys.path.pop(0)
            if old_local is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = old_local


if __name__ == "__main__":
    main()
