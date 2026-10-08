from __future__ import annotations

import os
import tempfile
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))
os.environ["LOCALAPPDATA"] = tempfile.mkdtemp(prefix="kz-r814-seo-")

from core.seo_geo_autonomy import configure, run_once, status  # noqa: E402
from core.seo_geo_growth import dashboard, plan_today  # noqa: E402


def main():
    observe = configure({"mode": "observe", "enabled": True})
    assert observe["mode"] == "observe"
    result = run_once(force=True)
    assert result["local_cycle"]["reason"] == "observe_mode"

    assisted = configure({"mode": "assisted"})
    assert assisted["mode"] == "assisted"
    result = run_once(force=True)
    assert result["mode"] == "assisted"
    snap = dashboard()
    assert len(snap.get("assets", [])) > 0
    # After today's first run, a newly PLANNED asset must not wait until
    # tomorrow. The normal 5-minute autonomy pass drains ready local stages
    # without planning beyond the daily quota.
    extra = plan_today(limit=1)
    assert extra["count"] == 1
    follow = run_once(force=False)
    assert (follow["local_cycle"].get("carryover_generation") or {}).get("count") == 1, follow
    # Deterministic local QC may advance GENERATED pages but must not fabricate public success.
    assert all(a.get("stage") not in {"PUBLISHED", "SUBMITTED", "CRAWLED", "INDEXED", "RANKED", "MENTIONED", "CITED", "CONVERTED"} for a in snap.get("assets", []))

    autonomous = configure({"mode": "autonomous"})
    assert autonomous["mode"] == "autonomous"
    result = run_once(force=True)
    assert result["external_readiness"]["publish_connector_ready"] is False
    state = status()
    keys = {x.get("key") for x in state["human_items"]}
    assert "seo_public_deploy_connector" in keys
    assert "seo_search_connector" in keys
    assert state["human_item_count"] >= 2
    assert state["policy"]["never_fake_publication"] is True
    assert state["policy"]["never_fake_indexing"] is True
    assert state["policy"]["never_fake_geo_visibility"] is True
    validation = state["unattended_validation"]
    assert validation["state"] in {"collecting", "passed", "needs_review"}, validation
    assert validation["cycle_count"] >= 1 and validation["target_hours"] == 24, validation
    assert "24小时验收" in validation["truth"]
    assert all("授权至少一个搜索站长平台" != x.get("title") for x in state["human_items"])

    # Simulate public deployment and search-submit exceptions in the same
    # autonomous cycle. Neither failure may abort the other stage or produce
    # a fake PUBLISHED/SUBMITTED receipt.
    from core import seo_geo_autonomy as worker
    old_ready = worker._external_readiness
    old_deploy = worker.seo_public_deployer.deploy_pending
    old_indexnow = worker.search_engine_submitter.initialize_indexnow
    old_submit = worker.search_engine_submitter.submit_pending
    try:
        worker._external_readiness = lambda snap: {
            "publish_connector_ready": True,
            "publish_connector_reason": "",
            "ready_search_connectors": ["indexnow"],
        }
        def raising_public(**kwargs):
            raise OSError("synthetic_public_deploy_failure")
        def raising_submit(**kwargs):
            raise OSError("synthetic_search_submit_failure")
        worker.seo_public_deployer.deploy_pending = raising_public
        worker.search_engine_submitter.initialize_indexnow = lambda: {"ready": True}
        worker.search_engine_submitter.submit_pending = raising_submit
        recovered = worker.run_once(force=True)
        assert recovered["public_deploy"]["reason"] == "public_deploy_worker_error", recovered
        assert recovered["search_submit"]["reason"] == "search_submit_worker_error", recovered
        assert recovered["counts"]["public_pages"] >= 0
        assert recovered["search_submit"]["submitted_count"] == 0
    finally:
        worker._external_readiness = old_ready
        worker.seo_public_deployer.deploy_pending = old_deploy
        worker.search_engine_submitter.initialize_indexnow = old_indexnow
        worker.search_engine_submitter.submit_pending = old_submit

    ui = (SOURCE / "web" / "r8_14_seo_geo_autonomy_ui.js").read_text(encoding="utf-8")
    for marker in ("观察模式", "半自动", "自治模式", "待人工处理", "/api/r8-14/seo-geo/autonomy"):
        assert marker in ui, marker
    for marker in ("r814-feedback", "kz-r813-focus", "刷新失败：", "自治状态已刷新"):
        assert marker in ui, marker

    print("PASS: R8-14 SEO/GEO autonomy modes, local-first execution and external truth gates verified.")


if __name__ == "__main__":
    main()
