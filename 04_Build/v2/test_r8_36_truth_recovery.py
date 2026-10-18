"""Release gate for owner-facing truth convergence and worker recovery."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))
TEST_LOCALAPPDATA = tempfile.TemporaryDirectory(prefix=".kz-r836-", dir=ROOT)
os.environ["LOCALAPPDATA"] = TEST_LOCALAPPDATA.name


def _replace(obj, name, value, originals):
    originals.append((obj, name, getattr(obj, name)))
    setattr(obj, name, value)


def main():
    from ai_center import daily_review
    from backend import kz_local_control_patch as local_control
    from backend import r8_13_seo_geo_patch as seo_geo
    from core import geo_domestic_matrix, geo_validation, phase1_acceptance
    from promotion import ai_production_center, search_growth

    originals = []
    try:
        _replace(geo_validation, "dashboard", lambda: {
            "official": {"tested": 50, "mentioned": 25, "mention_rate": 50.0},
            "question_set": {"total": 50, "questions": []},
        }, originals)
        _replace(geo_validation, "receipts", lambda limit=200: [], originals)
        _replace(geo_validation, "question_set", lambda: {"questions": []}, originals)
        _replace(geo_validation, "queue_summary", lambda: {"tasks": []}, originals)
        _replace(geo_domestic_matrix, "snapshot", lambda *args, **kwargs: {
            "activated": True,
            "version": "CN-GEO50-V1-20261011",
            "completed": 50,
            "evidence_complete": 50,
            "mentioned": 3,
            "recommended": 0,
            "cited": 0,
            "mention_rate": 6.0,
            "recommendation_rate": 0.0,
            "citation_rate": 0.0,
            "platform_mismatch_evidence": 30,
            "retest_coverage": {"24h": {"complete": 2, "remaining": 48}},
        }, originals)
        overlaid = seo_geo._overlay_formal_geo_truth({"geo": {"questions": 50}})
        geo = overlaid["geo"]
        assert geo["tested_questions"] == 50 and geo["mentioned"] == 3, geo
        assert geo["mention_rate"] == 6.0, geo
        assert geo["truth_source"] == "r8-26-cn-geo50-domestic-matrix", geo
        assert geo["platform_mismatch_evidence"] == 30, geo
        assert geo["mismatched_evidence_counts_in_metrics"] is False, geo

        class DeadThread:
            @staticmethod
            def is_alive():
                return False

        local_control._EXECUTOR_THREAD = DeadThread()
        _replace(local_control, "_has_pending_candidate_tasks", lambda: True, originals)
        _replace(local_control._quality_ai_runtime_patch, "_comfyui_ready", lambda: {"ok": True}, originals)
        _replace(local_control, "_start_comfy_worker", lambda: True, originals)
        resumed = local_control.ensure_pending_candidate_worker()
        assert resumed == {"pending": True, "started": True, "reason": "resumed_after_health_check"}, resumed

        _replace(phase1_acceptance, "status", lambda: {
            "status": "in_progress",
            "uptime_percent": 99.1,
            "max_gap_seconds": 1330,
            "progress_percent": 77.0,
            "thresholds": {"uptime_percent": 99.5, "max_silent_gap_seconds": 900},
            "checks": {"uptime_pass": False, "silent_gap_pass": False, "duration_complete": False},
        }, originals)
        _replace(ai_production_center, "dashboard", lambda: {
            "tasks": [{"status": "待本地执行器"}, {"status": "已完成"}],
        }, originals)
        _replace(search_growth, "status", lambda: {
            "latest_audit": {"blockers": ["首页缺少 canonical"]},
        }, originals)
        issues = daily_review.verified_operational_issues()
        joined = "\n".join(issues)
        assert "在线率" in joined and "最大静默" in joined, joined
        assert "1 项待执行" in joined and "技术SEO仍有 1 项" in joined, joined
    finally:
        local_control._EXECUTOR_THREAD = None
        for obj, name, value in reversed(originals):
            setattr(obj, name, value)

    build_info = (SOURCE / "web" / "build_info.js").read_text(encoding="utf-8")
    r7_js = (SOURCE / "web" / "r7.js").read_text(encoding="utf-8")
    decision_js = (SOURCE / "web" / "decision_center.js").read_text(encoding="utf-8")
    integrations_js = (SOURCE / "web" / "integrations.js").read_text(encoding="utf-8")
    workflow = (ROOT / ".github" / "workflows" / "build_v2_enterprise_beta.yml").read_text(encoding="utf-8")
    assert "/api/r7/jobs" in build_info and "priority=1" in build_info
    assert "AbortController" in r7_js and "未取得完整状态" in r7_js
    assert "AbortController" in decision_js and "未完成读取" in decision_js
    assert "manifest?.installed" in integrations_js and "packaged_by_github_actions" in integrations_js
    assert "test_r8_36_truth_recovery.py" in workflow and "$manifest.installed.github_run" in workflow
    print("PASS: domestic GEO truth, bounded UI reads, worker recovery and operational exceptions converge")


if __name__ == "__main__":
    main()
