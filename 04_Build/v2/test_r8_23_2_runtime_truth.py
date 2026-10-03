"""Offline release gate for R8-23.2 Pilot runtime truth and model policy."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "05_V2.0.0_Source"
CORE = SRC / "core" / "r8_23_2_runtime_truth.py"
SAFETY = SRC / "core" / "r8_23_2_runtime_safety.py"
PATCH = SRC / "backend" / "r8_23_2_runtime_truth_patch.py"
SAFETY_PATCH = SRC / "backend" / "r8_23_2_runtime_safety_patch.py"
ROUTER = SRC / "integrations" / "model_policy_router.py"
UI = SRC / "web" / "r8_23_2_pilot.js"
TRUTH_PATCH = SRC / "core" / "r8_20_growth_truth_patch.py"


def main():
    old_local = os.environ.get("LOCALAPPDATA")
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["LOCALAPPDATA"] = tmp
        sys.path.insert(0, str(SRC))
        try:
            from core import r8_23_2_runtime_truth as truth
            from core import r8_23_2_runtime_safety as safety

            release = truth.release_manifest()
            assert release["phase"] == "R8-23.2 Pilot"
            assert release["runtime_identity"] == "KZ-ENTERPRISE-V2.2.2-R8-AUTONOMOUS-20260922"
            assert release["funds_policy"] == "human_only"
            assert release["outcome_scope"].endswith("order")

            general = truth.model_route("general")
            assert general["route"][0] == "local_model"
            assert general["doubao_required"] is False

            for kind in ("seo_keyword_intent", "seo_semantic_qc", "geo_gap_analysis", "geo_content_enhancement"):
                route = truth.model_route(kind)
                assert route["route"] == ["local_model", "doubao_cloud"]
                assert route["doubao_required"] is True
                assert "C-level" in route["formal_evidence_rule"]

            low_quality = truth.model_route("general", local_quality=65)
            assert low_quality["doubao_required"] is True
            medium = truth.model_route("general", local_quality=80)
            assert "local_model_retry" in medium["route"]

            receipt = truth.receipt_state({"configured": True, "invoked": True, "public_url": "https://example.test/a"})
            assert receipt["highest_stage"] == "invoked"
            assert receipt["external_proof_present"] is True
            assert "外部成功" in receipt["truth"]

            attention = truth.attention_policy([
                {"title": "等待ChatGPT生成SEO计划"},
                {"title": "抖音账号待登录"},
                {"title": "需要验证码"},
                {"title": "退款处理"},
            ])
            assert len(attention["auto_resolvable"]) == 1
            assert len(attention["deferred"]) == 1
            assert len(attention["human"]) == 2

            semantics = safety.metric_semantics()
            assert semantics["windows"] == ["today", "7d", "30d", "all_time"]
            assert semantics["state_order"][0] == "configured"
            assert semantics["state_order"][-1] == "external_verified"
            pilot = safety.social_pilot()
            assert pilot["strategy"] == "one_real_platform_first_then_copy"
            assert pilot["multi_platform_autonomy"] is False

            core = CORE.read_text(encoding="utf-8")
            safety_core = SAFETY.read_text(encoding="utf-8")
            patch = PATCH.read_text(encoding="utf-8")
            safety_patch = SAFETY_PATCH.read_text(encoding="utf-8")
            router = ROUTER.read_text(encoding="utf-8")
            ui = UI.read_text(encoding="utf-8")
            truth_patch = TRUTH_PATCH.read_text(encoding="utf-8")

            for marker in ("single_truth", "decision_pack", "queue_diagnostics", "readiness", "SEO_GEO_DOUABO_REQUIRED", "RECEIPT_STAGES"):
                assert marker in core, marker
            for marker in ("duplicate_job", "recover_stale_running_jobs", "task_integrity", "social_pilot", "metric_semantics"):
                assert marker in safety_core, marker
            for marker in ("/api/health", "/api/runtime-health", "/api/version", "/api/readiness", "/api/r8-23-2/pilot", "_install_control_lease", "_install_model_execution_policy", "r8_23_2_pilot.js"):
                assert marker in patch, marker
            for marker in ("idempotent_reuse", "r8_23_2_recovery", "/api/r8-23-2/task-integrity", "/api/r8-23-2/social-pilot", "/api/r8-23-2/metric-semantics"):
                assert marker in safety_patch, marker
            for marker in ("local", "cloud", "required_cloud_missing", "formal_evidence", "C_auxiliary"):
                assert marker in router, marker
            for marker in ("R8-23.2 Pilot · 运行真值", "SEO/GEO关键节点豆包必经", "24h / 72h / 7天"):
                assert marker in ui, marker
            assert "r8_23_2_runtime_truth_patch" in truth_patch
            assert "r8_23_2_runtime_safety_patch" in truth_patch

            print("PASS: R8-23.2 adds single runtime truth, Decision Pack lease, queue explainability, idempotency/recovery, one-platform social pilot, local-first execution and mandatory Doubao participation on critical SEO/GEO steps without weakening Evidence gates")
        finally:
            if sys.path and sys.path[0] == str(SRC):
                sys.path.pop(0)
            if old_local is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = old_local


if __name__ == "__main__":
    main()
