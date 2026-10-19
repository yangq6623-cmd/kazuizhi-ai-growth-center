"""#840 isolated regression: owner keyword -> R7 draft -> SEO Asset/QC.

Never performs public deployment, submits URLs, or reads user production files.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

SRC = Path(__file__).resolve().parents[2] / "05_V2.0.0_Source"


def main():
    old_home = os.environ.get("LOCALAPPDATA")
    with tempfile.TemporaryDirectory(prefix="kz-840-seo-") as tmp:
        os.environ["LOCALAPPDATA"] = tmp
        sys.path.insert(0, str(SRC))
        try:
            from core import autonomy, seo_geo_growth as seo, seo_geo_autonomy, r7_engine
            from core.storage import read_json, write_json
            from promotion import content_center
            from core import r8_22_autonomous_convergence as control

            cmd = "CMD-20261019-073EED"
            mission = "MISSION-20260924-DF7DB2"
            keyword = "涟水县空调不制冷上门维修"
            job = {
                "id": "job-840-owner-increment",
                "kind": "manual_task",
                "title": "SEO增量内容验证 · " + keyword,
                "task_type": "seo", "agent": "SEO/GEO 增长员",
                "schedule_source": "owner_seo_incremental",
                "seo_keyword": keyword,
                "seo_region": "涟水县",
                "command_id": cmd, "mission_id": mission,
                "owner_requested_publication": True,
                "risk": "non_financial",
            }

            before = seo._load()
            assert before["assets"] == []
            result = autonomy.execute_autonomous(job)
            assert result["draft_id"], result
            assert result["seo_asset_id"] and result["seo_keyword"] == keyword, result
            state = seo._load()
            assert len(state["assets"]) == 1 and len(state["opportunities"]) == 1
            asset = state["assets"][0]
            assert asset["owner_command_id"] == cmd and asset["mission_id"] == mission
            assert asset["owner_draft_id"] == result["draft_id"]
            assert asset["stage"] == "PLANNED" and asset["publish_approved"]
            assert asset["public_url"] == "" and asset["submission_receipts"] == []

            drafts = content_center.history()["items"]
            assert len(drafts) == 1 and drafts[0]["id"] == result["draft_id"]
            assert drafts[0]["input"]["keyword"] == keyword
            assert keyword in drafts[0]["output"]["title"]

            # Idempotency: old receipts stay untouched; a repeated local
            # execution must neither multiply drafts nor plan another Asset.
            again = autonomy.execute_autonomous(job)
            assert again["draft_id"] == result["draft_id"]
            assert again["seo_asset_id"] == result["seo_asset_id"]
            assert len(content_center.history()["items"]) == 1
            assert len(seo._load()["assets"]) == 1

            # Existing background SEO modules, not the R7 draft step, stage
            # the page and apply deterministic QC. No external side effects.
            generated = seo.generate_staging(limit=3)
            assert generated["count"] == 1, generated
            staged = seo._load()["assets"][0]
            assert staged["stage"] == "GENERATED"
            page = Path(staged["staging_path"])
            assert page.is_file() and keyword in page.read_text(encoding="utf-8")
            qc = seo_geo_autonomy._local_qc_generated_assets(limit=3)
            assert result["seo_asset_id"] in qc["passed"], qc
            assert seo._load()["assets"][0]["stage"] == "QC_PASSED"
            summary = seo.dashboard()["summary"]
            assert summary["public_pages"] == summary["submitted_urls"] == 0
            assert not seo._load()["submission_events"]

            # A near-duplicate search intent must select an uncovered keyword
            # BEFORE generating the content, so the draft and asset agree.
            selection = seo.select_owner_seo_incremental_keyword("涟水空调不制冷哪里找人修？")
            assert selection["reason"] == "selected", selection
            assert selection["keyword"] != keyword and "洗衣机" in selection["keyword"]
            next_job = dict(job, id="job-840-other-command", command_id="CMD-OTHER",
                            seo_keyword="涟水空调不制冷哪里找人修？")
            other = autonomy.execute_autonomous(next_job)
            assert other["seo_asset_id"] != result["seo_asset_id"]
            assert other["seo_keyword"] == selection["keyword"]
            other_draft = next(x for x in content_center.history()["items"] if x["id"] == other["draft_id"])
            assert other_draft["input"]["keyword"] == other["seo_keyword"]

            # Unsupported area/service words cannot silently pass into an
            # authorized public pipeline or fallback to a generic template.
            unsafe = dict(job, id="job-840-out-of-scope", command_id="CMD-UNSAFE",
                          seo_keyword="涟水县股票投资推荐")
            stopped = autonomy.execute_autonomous(unsafe)
            assert stopped["seo_asset_id"] is None
            assert stopped["seo_asset_reason"] == "service_not_in_verified_brand_scope"
            assert len(content_center.history()["items"]) == 2
            assert len(seo._load()["assets"]) == 2

            # Upgrade compatibility: #839 already completed a *generic*
            # draft without SEO Asset. One distinct continuation, no replay
            # or rewrite of its immutable existing local execution result.
            objective = ("继续现有 Mission MISSION-20260924-DF7DB2，执行SEO增量验证。"
                         "目标关键词优先选择“涟水县空调不制冷上门维修”。"
                         "按现有授权执行QC、官网发布、搜索提交。")
            old_job = dict(job, id="job-839-preserved", state="completed",
                           idempotency_key="r8_22_owner_seo_incremental:CMD-LEGACY",
                           command_id="CMD-LEGACY", result={"draft_id": "OLD-DRAFT",
                                                            "summary": "旧泛化草稿"},
                           execution_receipt={"receipt_id": "OLD-LOCAL-RECEIPT"})
            write_json(r7_engine.JOBS, {"schema": 1, "items": [old_job]})
            m = {"command_id": "CMD-LEGACY", "mission_id": mission, "command_objective": objective}
            p = {"plan_id": "PLAN-LEGACY", "lanes": [{"id": "seo"}]}
            followup = control.ensure_owner_seo_incremental_task(m, p)
            assert followup["id"] and not followup["existing"], followup
            again = control.ensure_owner_seo_incremental_task(m, p)
            assert again["id"] == followup["id"] and again["existing"]
            jobs = r7_engine._store()["items"]
            assert len(jobs) == 2
            saved_old = next(x for x in jobs if x["id"] == "job-839-preserved")
            assert saved_old["execution_receipt"]["receipt_id"] == "OLD-LOCAL-RECEIPT"
            new = next(x for x in jobs if x["id"] == followup["id"])
            assert new["seo_keyword"] == keyword
            assert new["state"] == "queued" and new["owner_requested_publication"]
            print("PASS #840: owner keyword, one asset, deterministic QC, no fake publish, duplicate protection, #839 safe continuation")
        finally:
            if sys.path and sys.path[0] == str(SRC):
                sys.path.pop(0)
            if old_home is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = old_home


if __name__ == "__main__":
    main()
