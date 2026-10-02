"""Offline release gate for the 38-item R8-20 SEO/GEO operating-loop scope."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "05_V2.0.0_Source"
WEB = SRC / "web" / "seo-geo-growth-intelligence.js"


def main():
    old_local = os.environ.get("LOCALAPPDATA")
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["LOCALAPPDATA"] = tmp
        sys.path.insert(0, str(SRC))
        try:
            from core import geo_analysis
            from core import geo_validation as geo
            from core import seo_geo_growth
            from core import seo_geo_growth_intelligence as growth

            # 38 locked development items must be represented by executable code capabilities.
            features = growth.feature_registry()
            assert len(features) == 38
            assert [x["id"] for x in features] == list(range(1, 39))
            assert all(x["code_state"] == "implemented" for x in features)

            # Seed truthful SEO assets without claiming public search success.
            seo_geo_growth.ensure_baseline()
            seo_geo_growth.plan_today(limit=3)
            seo_geo_growth.generate_staging(limit=3)
            seo_dash = seo_geo_growth.dashboard()
            assert seo_dash["assets"]
            asset = seo_dash["assets"][0]
            source_id = growth.source_tracking_id(asset)
            assert source_id.startswith("KZSRC-")

            # 1-6: crawl/index/rank/impression/click/CTR all require evidence.
            try:
                growth.record_search_observation({"kind": "indexed", "asset_id": asset["id"], "engine": "test"})
                raise AssertionError("index observation without evidence must fail")
            except ValueError:
                pass
            growth.record_search_observation({"kind": "crawled", "asset_id": asset["id"], "engine": "test", "evidence": "crawler-log-1"})
            growth.record_search_observation({"kind": "indexed", "asset_id": asset["id"], "engine": "test", "evidence": "index-proof-1"})
            growth.record_search_observation({"kind": "ranked", "asset_id": asset["id"], "engine": "test", "keyword": asset["keyword"], "rank": 8, "evidence": "rank-proof-1"})
            growth.record_search_observation({"kind": "impressions", "asset_id": asset["id"], "engine": "test", "value": 100, "evidence": "gsc-row-1"})
            growth.record_search_observation({"kind": "clicks", "asset_id": asset["id"], "engine": "test", "value": 10, "evidence": "gsc-row-2"})
            search = growth.status(30)["search"]
            assert search["impressions"] == 100 and search["clicks"] == 10 and search["ctr"] == 10.0

            # 8-10: dynamic question discovery, dedupe/version and priority.
            dynamic = growth.discover_dynamic_questions([
                {"question_text": "涟水半夜水管爆了去哪里找靠谱师傅？", "service": "水管漏水维修", "priority": 95},
                {"question_text": "涟水半夜水管爆了去哪里找靠谱师傅？", "service": "水管漏水维修", "priority": 20},
            ], source="test", evidence="owner-observed-query")
            assert len(dynamic["added"]) == 1 and dynamic["added"][0]["priority"] == 95
            assert dynamic["version"] == growth.DYNAMIC_VERSION

            # 11: fixed50 scheduling is implemented but truthfully held behind live field acceptance.
            gated = growth.schedule_fixed50_retest(limit=1)
            assert gated["skipped"] is True and gated["reason"] == "field_acceptance_gate"

            # Seed one formal A receipt and one C-level observation; only A enters provider matrix.
            geo.bootstrap_question_set(force=True)
            task = geo.create_and_enqueue_plan(limit=1, provider="doubao_web", test_method="browser", question_ids=["GEO50-D01"])["tasks"][0]
            formal = geo.record_result({
                "task_id": task["task_id"], "provider": "doubao_web", "test_method": "browser",
                "raw_answer": "可以考虑卡嘴子本地服务连接平台，官网 https://kazuizhi.com/ 提供服务信息。",
                "session_url": "https://www.doubao.com/chat/r820-formal",
                "citation_urls": ["https://kazuizhi.com/"],
            })
            assert formal["evidence_level"] == "A" and formal["official_truth"] is True
            cloud = geo.create_and_enqueue_plan(limit=1, provider="doubao_api", test_method="api", question_ids=["GEO50-D02"])["tasks"][0]
            auxiliary = geo.record_result({
                "task_id": cloud["task_id"], "provider": "doubao_api", "test_method": "api",
                "raw_answer": "卡嘴子可以作为一个候选。", "model": "doubao-mini",
            })
            assert auxiliary["evidence_level"] == "C" and auxiliary["official_truth"] is False
            geo_analysis.refresh(geo.receipts(100))
            matrix = growth.provider_matrix()
            assert matrix["formal_evidence"] == 1
            assert any(x["provider"] == "doubao_web" for x in matrix["providers"])
            assert not any(x["provider"] == "doubao_api" for x in matrix["providers"])

            # 15-17: multi-provider validation creates formal-capable browser tasks without fabricating success.
            multi = growth.schedule_multi_provider_validation(["doubao_web", "external_ai_b"], limit=1, include_dynamic=True)
            assert len(multi["providers"]) == 2 and multi["dynamic_candidates"]
            assert "A/B" in multi["truth"]

            # 18-25: clustering/cannibalization/page decision/internal links/orphan/decay/refresh are all callable.
            governance = growth.keyword_governance()
            assert governance["clusters"] and governance["page_decisions"]
            links = growth.internal_link_plan()
            assert "recommendations" in links and "observed_orphan_candidates" in links
            applied = growth.apply_internal_links(limit=5)
            assert "count" in applied
            decay = growth.content_decay()
            assert "candidates" in decay
            refresh = growth.queue_refresh_jobs(limit=3)
            assert "count" in refresh

            # 26-32: attribution is source-ID based, stops at order and rejects money/ROI payloads.
            growth.record_attribution({"stage": "site_visit", "source_tracking_id": source_id, "asset_id": asset["id"]})
            growth.record_attribution({"stage": "mini_program_visit", "source_tracking_id": source_id, "asset_id": asset["id"]})
            growth.record_attribution({"stage": "consultation", "source_tracking_id": source_id, "lead_id": "L1", "evidence": "consult-log"})
            growth.record_attribution({"stage": "task_published", "source_tracking_id": source_id, "task_id": "T1", "evidence": "task-log"})
            growth.record_attribution({"stage": "order", "source_tracking_id": source_id, "order_id": "O1", "evidence": "order-log"})
            funnel = growth.attribution_funnel(30)
            assert [funnel[k] for k in ("site_visit", "mini_program_visit", "consultation", "task_published", "order")] == [1,1,1,1,1]
            for forbidden in ({"stage":"order","source_tracking_id":source_id,"order_id":"O2","evidence":"x","amount":99}, {"stage":"order","source_tracking_id":source_id,"order_id":"O2","evidence":"x","roi":2.0}):
                try:
                    growth.record_attribution(forbidden)
                    raise AssertionError("money metrics must be rejected")
                except ValueError:
                    pass
            priorities = growth.controller_priorities()
            assert priorities["actions"] and "金额" not in priorities["truth"]

            # 33: real-vitals ingest needs source + evidence; absent provider remains explicitly waiting.
            technical_before = growth.technical_seo_status()
            assert technical_before["web_vitals_state"] == "waiting_real_provider"
            growth.ingest_web_vitals({"url":"https://kazuizhi.com/", "source":"pagespeed-real-export", "evidence":"psi-receipt", "lcp_ms":1800, "inp_ms":140, "cls":0.04})
            technical_after = growth.technical_seo_status()
            assert technical_after["web_vitals_state"] == "measured"

            # 34: source-gap actions come only from observed formal evidence and never auto-spam.
            sources = growth.third_party_source_gaps()
            assert all(x.get("auto_post") is False for x in sources.get("actions") or [])

            # 35-36/38: connector health, breaker, dead-letter and budget guards.
            growth.record_connector_health("doubao", False, "timeout")
            growth.record_connector_health("doubao", False, "timeout")
            health = growth.record_connector_health("doubao", False, "timeout")
            assert health["breaker_open"] is True
            failure = growth.register_failure("provider_call", {"provider":"doubao"}, "timeout", retry_count=2, max_retries=2)
            assert failure["state"] == "dead_letter"
            budget = growth.consume_budget("oversized", 999)
            assert budget["allowed"] is False

            # 37: backup/restore is explicit and confined to SEO/GEO state files.
            backup = growth.create_backup("ci")
            assert backup["backup_id"] and growth.STORE in backup["files"]
            try:
                growth.restore_backup(backup["backup_id"], confirm=False)
                raise AssertionError("restore must require confirm")
            except PermissionError:
                pass
            restored = growth.restore_backup(backup["backup_id"], confirm=True)
            assert growth.STORE in restored["restored"]

            # 7/12/13/14 + owner one-glance dashboard.
            growth.capture_trend_snapshot(force=True)
            for window in (7, 30, 90):
                trend = growth.trends(window)
                assert trend["window_days"] == window and trend["points"]
            final = growth.status(30)
            assert final["feature_count"] == 38
            assert final["policy"]["money_metrics_disabled"] is True
            assert final["controller"]["controller"] == "chatgpt"

            ui = WEB.read_text(encoding="utf-8")
            for marker in ("SEO 走势图", "GEO 走势图", "近7天", "近30天", "近90天", "业务结果漏斗", "ChatGPT 总脑趋势结论", "多AI正式 Evidence 矩阵"):
                assert marker in ui, marker
            for forbidden in ("成交金额", "收入", "ROI金额"):
                assert forbidden not in ui, forbidden

            print("PASS: R8-20 all 38 SEO/GEO growth upgrades + trend dashboard + truth/operations gates")
        finally:
            sys.path.remove(str(SRC))
            if old_local is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = old_local


if __name__ == "__main__":
    main()
