"""Offline acceptance gate for GEO Phase 3 gap/action/retest truth semantics."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "05_V2.0.0_Source"


def main():
    old_local = os.environ.get("LOCALAPPDATA")
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["LOCALAPPDATA"] = tmp
        sys.path.insert(0, str(SRC))
        try:
            # Load additive bridges before the Phase-3 controller, matching the
            # production backend import order.
            from core import geo_phase2_latest_truth_patch  # noqa: F401
            from core import geo_phase3_job_patch  # noqa: F401
            from core import geo_phase3_seo_bridge  # noqa: F401
            from core import geo_analysis
            from core import geo_validation as geo
            from core import geo_phase3
            from core import r7_engine
            from core import seo_geo_growth

            geo.bootstrap_question_set(force=True)
            baseline = geo.create_and_enqueue_plan(
                limit=1,
                provider="doubao_web",
                test_method="browser",
                question_ids=["GEO50-D01"],
            )["tasks"][0]
            receipt = geo.record_result({
                "task_id": baseline["task_id"],
                "provider": "doubao_web",
                "test_method": "browser",
                "raw_answer": "可以通过本地生活平台或熟人渠道寻找水电维修师傅。",
                "session_url": "https://www.doubao.com/chat/phase3-baseline",
            })
            assert receipt["evidence_level"] == "A" and receipt["official_truth"] is True
            analysed = geo_analysis.refresh(geo.receipts(100))
            assert analysed["summary"]["tested"] == 1
            assert analysed["summary"]["gaps"]

            # No hidden autonomy: without a verified ChatGPT Command the plan
            # remains waiting until the owner explicitly approves this non-financial round.
            geo_phase3.active_authorization = lambda mission_id=None: None
            plan = geo_phase3.plan(force=True)
            assert plan["status"] == "waiting_authorization"
            assert plan["actions"]
            assert plan["baseline_formal_count"] == 1

            run = geo_phase3.run_once(owner_approved=True)
            assert run["skipped"] is False
            current = geo_phase3.status()["plan"]
            assert current["authorization_mode"] == "owner_explicit"
            assert current["actions"][0]["job_id"]
            assert current["actions"][0]["opportunity_id"]

            # The Phase-3 job must carry the real evidence-derived context into
            # the existing AI employee engine instead of falling back to a generic prompt.
            jobs = {item["id"]: item for item in r7_engine.list_jobs()["items"]}
            job = jobs[current["actions"][0]["job_id"]]
            assert job["schedule_source"] == "geo_phase3_owner"
            assert (job.get("context") or {}).get("geo_question_id") == "GEO50-D01"
            assert job["state"] == "completed"
            assert (job.get("result") or {}).get("geo_gap_code")

            opportunities = seo_geo_growth.dashboard().get("opportunities") or []
            assert any(item.get("id") == current["actions"][0]["opportunity_id"] for item in opportunities)

            # Force only the offline test to queue a retest before public deploy.
            # Production UI never exposes this bypass: real use waits for PUBLISHED.
            geo_phase3.sync(force_retest=True)
            current = geo_phase3.status()["plan"]
            retest_task = current["actions"][0]["retest_task_id"]
            assert retest_task
            after = geo.record_result({
                "task_id": retest_task,
                "provider": "doubao_web",
                "test_method": "browser",
                "raw_answer": "在涟水县找水电维修师傅时，可以了解卡嘴子本地服务连接平台，官网 https://kazuizhi.com/ 提供服务范围和需求发布信息。",
                "session_url": "https://www.doubao.com/chat/phase3-retest",
                "citation_urls": ["https://kazuizhi.com/"],
            })
            assert after["evidence_level"] == "A" and after["official_truth"] is True
            # Phase-2 current metrics must still say one tested question, while
            # retaining the two historical A receipts as baseline + retest.
            refreshed = geo_analysis.refresh(geo.receipts(100))
            assert refreshed["summary"]["tested"] == 1
            assert refreshed["official_history_count"] == 2
            assert refreshed["retest_count"] == 1

            final = geo_phase3.sync()
            final_plan = final["plan"]
            assert final_plan["status"] == "completed"
            assert final_plan["before_after"]
            assert final_plan["before_after"][0]["delta"] > 0
            assert final_plan["outcome"] == "improved"

            # Cloud C-level observations remain excluded from the formal score.
            assert geo.dashboard()["official"]["tested"] == 1

            print("PASS: Phase2 latest truth + GEO Phase3 gap -> authorized AI job -> SEO opportunity -> real A/B retest -> Before/After")
        finally:
            sys.path.remove(str(SRC))
            if old_local is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = old_local


if __name__ == "__main__":
    main()
