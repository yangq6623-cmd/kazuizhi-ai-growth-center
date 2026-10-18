"""Release gate for GEO -> SEO revision -> receipt -> retest continuity."""
from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))


def main():
    previous = os.environ.get("LOCALAPPDATA")
    with tempfile.TemporaryDirectory(prefix=".kz-r834-", dir=ROOT) as temp:
        os.environ["LOCALAPPDATA"] = temp
        try:
            from core import geo_growth_orchestrator as orchestrator
            from core import geo_phase3_seo_bridge as bridge
            from core import geo_validation as geo
            from core import seo_geo_growth as growth
            from integrations import geo_cloud_executor
            from integrations import seo_public_deployer as deployer

            opportunity = bridge.upsert_opportunity({
                "region": "涟水县",
                "service": "水电安装维修",
                "keyword": "涟水县水电安装维修本地服务",
                "intent": "GEO缺口修复",
                "priority": "S",
                "source_ref": "SIGNAL-BASE",
            })
            first = bridge.prepare_phase3_assets({"actions": [{
                "action_id": "ROUND-1",
                "job_state": "completed",
                "opportunity_id": opportunity["id"],
                "question_id": "Q-1",
                "question_text": "涟水水电维修怎么找？",
                "decision": "补强本地服务事实与正式入口",
            }]})
            assert first["qc_passed"], first
            asset_id = first["states"][0]["asset_id"]
            growth.record_asset_stage(asset_id, "PUBLISHED", {
                "public_url": "https://kazuizhi.com/seo/closed-loop/",
                "publish_approved": True,
            })

            second = bridge.prepare_phase3_assets({"actions": [{
                "action_id": "ROUND-2",
                "job_state": "completed",
                "opportunity_id": opportunity["id"],
                "question_id": "GEO50-D01",
                "question_text": "涟水水电维修服务能力是否充足？",
                "decision": "补强服务范围、检测报价和订单留痕说明",
                "region": "涟水县",
                "service": "水电安装维修",
                "keyword": "涟水县水电安装维修本地服务",
            }]})
            assert second["refreshed"] == [asset_id], second
            revised = next(row for row in growth.dashboard()["assets"] if row.get("id") == asset_id)
            assert revised["stage"] == "PUBLISHED", revised
            assert revised["republish_pending"] is True, revised
            assert revised["content_revision_id"] == "ROUND-2", revised
            assert revised["public_template_version"] == growth.PUBLIC_TEMPLATE_VERSION, revised
            page = Path(revised["staging_path"]).read_text(encoding="utf-8")
            assert 'data-kz-role="growth-revision"' in page
            assert "涟水水电维修服务能力是否充足" in page
            assert "检测报价和订单留痕" in page

            site_root = Path(temp) / "site"
            site_root.mkdir(parents=True)
            deployer.configure({
                "site_root": str(site_root),
                "public_base_url": "https://kazuizhi.com/",
                "enabled": True,
                "verify_http": True,
            })
            original_verify = deployer._verify_public_url
            deployer._verify_public_url = lambda url, expected, canonical, timeout: {
                "ok": True,
                "status": 200,
                "url": url,
                "canonical_match": True,
                "schema_valid": True,
                "page_indexable": True,
            }
            try:
                deployed = deployer.deploy_pending(limit=5)
            finally:
                deployer._verify_public_url = original_verify
            assert deployed["attempted"] == 1, deployed
            assert deployed["published"][0]["republished"] is True, deployed
            assert deployed["published"][0]["growth_action_id"] == "ROUND-2", deployed

            published = next(row for row in growth.dashboard()["assets"] if row.get("id") == asset_id)
            assert published["stage"] == "PUBLISHED", published
            assert published["republish_pending"] is False, published
            assert published["last_republished_at"], published
            event = published["content_refresh_events"][-1]
            assert event["growth_action_id"] == "ROUND-2", event
            assert event["deploy_receipt"], event

            # The same completed action must not regenerate/re-publish on each
            # autonomous loop after its first verified public receipt.
            event_count = len(published["content_refresh_events"])
            repeated = bridge.prepare_phase3_assets({"actions": [{
                "action_id": "ROUND-2",
                "job_state": "completed",
                "opportunity_id": opportunity["id"],
                "question_id": "GEO50-D01",
                "question_text": "涟水水电维修服务能力是否充足？",
                "decision": "补强服务范围、检测报价和订单留痕说明",
            }]})
            assert repeated["refreshed"] == [], repeated
            stable = next(row for row in growth.dashboard()["assets"] if row.get("id") == asset_id)
            assert stable["republish_pending"] is False, stable
            assert len(stable["content_refresh_events"]) == event_count, stable

            # Preserve a duplicate deployment Receipt as audit history, but
            # never let it replace the first public exposure of this revision.
            duplicate_event = dict(event)
            duplicate_event["at"] = (
                datetime.fromisoformat(event["at"].replace("Z", "+00:00")) + timedelta(hours=5)
            ).isoformat()
            duplicate_event["deploy_receipt"] = f'{event["deploy_receipt"]}-DUPLICATE'
            published["content_refresh_events"].append(duplicate_event)

            item = {
                "id": "ROUND-2",
                "signal_id": "SIGNAL-2",
                "question_id": "GEO50-D01",
                "question_text": "涟水水电维修服务能力是否充足？",
                "decision": "补强服务范围、检测报价和订单留痕说明",
                "baseline_signal": {"brand_mentioned": False, "brand_recommended": False, "service_match": False},
                "seo_opportunity_id": opportunity["id"],
                "job_id": "",
                "job_state": "completed",
                "asset_id": asset_id,
                "asset_stage": "PUBLISHED",
                "public_url": published["public_url"],
                "published_at": "",
                "retest_due_at_epoch": 0,
                "retest_task_id": "",
                "state": "waiting_publish",
                "created_at": "2026-01-01T00:00:00+08:00",
                "updated_at": "2026-01-01T00:00:00+08:00",
            }
            data = {"opportunities": [item], "technical_blockers": [], "history": []}
            assets = {asset_id: published}
            orchestrator._sync_item(data, item, {}, {opportunity["id"]: opportunity}, assets)
            assert item["state"] == "waiting_retest", item
            assert item["published_at"] == event["at"], item
            assert item["publication_receipt_id"] == event["deploy_receipt"], item
            assert item["retest_due_at_epoch"] > 0, item
            assert [slot["window"] for slot in item["retest_schedule"]] == ["24h", "72h", "7d"], item

            # A fresh verified publication must not be tested early, even if a
            # stale caller tries to push the old slot into the past.
            item["retest_schedule"][0]["due_at_epoch"] = 0
            geo.bootstrap_question_set(force=True)
            orchestrator._sync_item(data, item, {}, {opportunity["id"]: opportunity}, assets)
            first_slot = item["retest_schedule"][0]
            assert not first_slot["task_id"], item
            assert first_slot["due_at_epoch"] >= orchestrator._iso_epoch(item["published_at"]) + 86400, item

            # Once the verified publication really is older than 24h, only a
            # real external task is queued. Its receipt closes the review and
            # makes the next round eligible.
            elapsed_at = (datetime.now(timezone.utc) - timedelta(hours=25)).isoformat()
            for refresh_event in published["content_refresh_events"]:
                if refresh_event.get("growth_action_id") == "ROUND-2":
                    refresh_event["at"] = elapsed_at
            item["retest_schedule"] = []
            orchestrator._sync_item(data, item, {}, {opportunity["id"]: opportunity}, assets)
            first_slot = item["retest_schedule"][0]
            assert first_slot["task_id"], item
            claimed = geo.claim_next_task({
                "provider": geo_cloud_executor.PROVIDER,
                "real_external": True,
                "authorization_ready": True,
                "provider_ready": True,
                "test_method": "api",
                "executor_id": "r834-test-executor",
            })
            task = claimed.get("task") or claimed
            assert task.get("task_id"), (claimed, geo.queue_summary())
            assert task["task_id"] == first_slot["task_id"], task
            receipt = geo.record_result({
                "task_id": task["task_id"],
                "provider": geo_cloud_executor.PROVIDER,
                "test_method": "api",
                "raw_answer": "可以先查看本地公开服务页，再根据真实检测和报价选择师傅。",
                "model": "r834-test-model",
            })
            orchestrator._sync_item(data, item, {}, {opportunity["id"]: opportunity}, assets)
            assert item["state"] == "completed", item
            assert item["retest_coverage"]["completed"] == 1, item
            assert item["retest_coverage"]["windows"]["24h"] == "completed", item
            next_round = orchestrator._create_from_signal(data, receipt)
            assert next_round and next_round["id"] != item["id"], (next_round, data)
            assert next_round["seo_opportunity_id"] == item["seo_opportunity_id"], next_round

            duplicate_data = {"opportunities": [
                {"id": "OLD", "seo_opportunity_id": opportunity["id"], "state": "waiting_content_update", "signal_id": "S1", "created_at": "2026-01-01"},
                {"id": "NEW", "seo_opportunity_id": opportunity["id"], "state": "waiting_content_update", "signal_id": "S2", "created_at": "2026-01-02"},
                {"id": "DONE", "seo_opportunity_id": opportunity["id"], "state": "completed", "signal_id": "S0", "created_at": "2025-12-31"},
            ], "history": []}
            assert orchestrator._coalesce_active_opportunities(duplicate_data) == 1
            old = next(row for row in duplicate_data["opportunities"] if row["id"] == "OLD")
            new = next(row for row in duplicate_data["opportunities"] if row["id"] == "NEW")
            assert old["state"] == "superseded" and old["superseded_by"] == "NEW", old
            assert "S1" in new["coalesced_signal_ids"], new
        finally:
            if previous is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = previous

    print("PASS: GEO/SEO revision, verified republish, retest handoff and backlog coalescing")


if __name__ == "__main__":
    main()
