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
COLLAB = SRC / "integrations" / "seo_geo_model_collaboration.py"
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
            from integrations import seo_geo_model_collaboration as collab

            identity = truth.release_identity()
            assert identity["release"] == "R8-23.2 Pilot RC1"
            assert identity["phase"] == "Runtime Truth & Closed-Loop Acceptance"
            assert identity["api_contract"] == "r8-23.2/v1"
            assert identity["complete"] is True

            local = truth.model_route_for("batch_tagging", local_ready=True, doubao_ready=True)
            seo = truth.model_route_for("seo_semantic_qc", local_ready=True, doubao_ready=True)
            geo = truth.model_route_for("geo_gap_analysis", local_ready=True, doubao_ready=True)
            assert local["primary"] == "local_model" and local["required"] is False
            assert seo["primary"] == "doubao_cloud" and seo["required"] is True
            assert geo["primary"] == "doubao_cloud" and geo["required"] is True
            assert "geo_gap_analysis" in truth.DOUBAO_REQUIRED_STAGES
            assert "seo_semantic_qc" in truth.DOUBAO_REQUIRED_STAGES

            # Prove the Doubao collaboration code sends a real OpenAI-compatible
            # request for an SEO/GEO stage rather than only displaying a route.
            original_status = collab.status
            original_key = collab._cloud_key
            original_profile = collab.ai_gateway._profile
            original_validate = collab.ai_gateway._validate_endpoint
            try:
                collab.status = lambda: {
                    "ready": True, "model": "doubao-test", "label": "豆包测试路由",
                    "evidence_level": "C_auxiliary",
                }
                collab._cloud_key = lambda: ("test-key", "test")
                collab.ai_gateway._profile = lambda route: {
                    "endpoint": "https://example.invalid/v1/chat/completions",
                    "protocol": "chat_completions", "model": "doubao-test",
                }
                collab.ai_gateway._validate_endpoint = lambda endpoint, route: endpoint
                captured = {}

                def transport(body, headers, endpoint, protocol):
                    captured.update(body=body, headers=headers, endpoint=endpoint, protocol=protocol)
                    return {
                        "id": "resp-doubao-ci", "model": "doubao-test",
                        "choices": [{"message": {"content": '{"summary":"SEO复核完成","findings":["意图明确"],"actions":["补FAQ"],"quality_score":88,"risks":[]}'}}],
                    }

                answer = collab._request("seo_semantic_qc", {"assets": [{"title": "涟水维修"}]}, transport=transport)
                assert captured["protocol"] == "chat_completions"
                assert captured["headers"]["Authorization"] == "Bearer test-key"
                assert "SEO复核完成" in answer["raw_text"]
                assert answer["response_id"] == "resp-doubao-ci"
            finally:
                collab.status = original_status
                collab._cloud_key = original_key
                collab.ai_gateway._profile = original_profile
                collab.ai_gateway._validate_endpoint = original_validate

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
            assert manifest["baseline"]["github_run"] == "#76"

            core = CORE.read_text(encoding="utf-8")
            patch = PATCH.read_text(encoding="utf-8")
            collaboration = COLLAB.read_text(encoding="utf-8")
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
                "/api/r8-23-2/model-routing", "/api/r8-23-2/doubao-collaboration",
                "model_collaboration.run_cycle", "r8_23_2_runtime_truth.js",
            ):
                assert marker in patch, marker
            for marker in ("REQUIRED_STAGES", "seo_semantic_qc", "geo_gap_analysis", "C_auxiliary", "run_cycle", "Authorization"):
                assert marker in collaboration, marker
            for marker in ("当前 Command", "控制租约", "真正需要老板", "Receipt / Evidence", "计划等待"):
                assert marker in ui, marker
            assert "__KZ_R8232_RUNTIME_TRUTH_UI_LOADED__" in ui
            assert "r8_23_2_runtime_truth_patch" in truth_patch
            assert "test_r8_23_2_runtime_truth.py" in workflow
            for marker in (
                "19 engineering work packages", "24h", "72h", "7-day",
                "Doubao", "single active Command", "One real social platform",
            ):
                assert marker in scope, marker

            print("PASS: R8-23.2 locks runtime/control truth and performs real Doubao SEO/GEO collaboration without weakening Evidence gates")
        finally:
            if sys.path and sys.path[0] == str(SRC):
                sys.path.pop(0)
            if old_local is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = old_local


if __name__ == "__main__":
    main()
