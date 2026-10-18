"""Regression gate for R8-19 GEO Phase 1.

The gate verifies the product contract rather than external network availability:
- ChatGPT remains the controller.
- GEO50 is a versioned 30/10/10 baseline and discovery prompts are unbranded.
- local models never count as official GEO evidence.
- A/B evidence requires a real external proof contract.
- retry/authorization states remain explicit and failed tasks cannot reset retries by replanning.
- the Operational UI exposes the independent GEO workspace without replacing SEO.
- the executive Decision Center surfaces today's ChatGPT GEO decision without a ninth AI employee.
"""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "05_V2.0.0_Source"


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def expect_error(fn, contains=""):
    try:
        fn()
    except (ValueError, RuntimeError, PermissionError) as error:
        if contains:
            check(contains in str(error), f"wrong error: {error}")
        return
    raise AssertionError("expected error was not raised")


def main():
    old_local = os.environ.get("LOCALAPPDATA")
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["LOCALAPPDATA"] = tmp
        sys.path.insert(0, str(SRC))
        try:
            from core import geo_validation as geo
            from integrations import geo_openai_search_executor as executor
            from backend import r8_19_geo_validation_patch as geo_api

            qset = geo.question_set()
            questions = qset["questions"]
            check(qset["version"] == "GEO50-V2-20260930", "wrong GEO50 version")
            check(len(questions) == 50, "GEO50 must contain exactly 50 questions")
            counts = qset["counts"]
            check(counts == {"discovery": 30, "commercial": 10, "brand": 10}, "GEO50 30/10/10 split broken")
            check(len({item["question_id"] for item in questions}) == 50, "duplicate GEO50 question IDs")
            check(len({item["question_text"] for item in questions}) == 50, "duplicate GEO50 question text")
            check(not any("卡嘴子" in item["question_text"] for item in questions if item["question_type"] == "discovery"), "discovery baseline leaks brand name")
            check(any(item["service"] == "个人任务" for item in questions), "personal-task GEO coverage missing")
            first_hash = qset["question_set_hash"]
            check(geo.bootstrap_question_set(force=True)["question_set_hash"] == first_hash, "same-version force changed immutable baseline")

            decision = geo.set_decision({
                "mission_id": "MISSION-GEO-TEST",
                "mission_title": "涟水县 GEO 第一轮基线验证",
                "daily_test_limit": 3,
            })
            check(decision["controller"] == "chatgpt", "ChatGPT is not the GEO controller")
            check(decision["decision_id"] and decision["command_id"], "Decision/Command IDs missing")

            plan = geo.create_plan(limit=10, provider="openai_web_search", test_method="api")
            check(plan["count"] == 3, "ChatGPT daily limit was bypassed")
            check(plan["decision_id"] == decision["decision_id"], "Decision ID did not propagate")
            check(plan["command_id"] == decision["command_id"], "Command ID did not propagate")
            check(plan["mission_id"] == "MISSION-GEO-TEST", "Mission ID did not propagate")
            geo.enqueue_plan(plan)
            active_ids={item["question_id"] for item in plan["questions"]}
            check(not active_ids.intersection(set(geo_api._eligible_question_ids())), "active GEO questions were offered for duplicate replanning")

            expect_error(
                lambda: geo.create_plan(limit=1, provider="local_model", test_method="api"),
                "local_model_cannot_be_official_geo_executor",
            )

            claim = geo.claim_next_task({"real_external": False, "provider": "local_model", "test_method": "local_simulation"})
            check(claim["task"]["state"] == "authorization_required", "missing external executor was not surfaced as authorization required")
            task_id = claim["task"]["task_id"]
            geo.retry_task(task_id, approved_by="chatgpt")
            claim = geo.claim_next_task({"real_external": False})
            check(claim["task"]["state"] == "authorization_required", "retry did not return to truthful auth gate")
            geo.retry_task(task_id, approved_by="chatgpt")
            claim = geo.claim_next_task({"real_external": False})
            check(claim["task"]["state"] == "authorization_required", "second retry did not preserve auth gate")
            expect_error(lambda: geo.retry_task(task_id, approved_by="chatgpt"), "retry_limit")
            expect_error(lambda: geo.retry_task(task_id, approved_by="local_model"))

            # A failed question cannot bypass its retry counter by creating a fresh plan.
            failed_question = questions[45]["question_id"]
            failed_plan = geo.create_plan(limit=1, provider="openai_web_search", test_method="api", question_ids=[failed_question])
            failed_task = geo.enqueue_plan(failed_plan)["tasks"][0]
            geo.fail_task(failed_task["task_id"], "simulated_provider_failure")
            expect_error(
                lambda: geo_api._eligible_question_ids([failed_question]),
                "failed_question_requires_chatgpt_retry",
            )
            check(failed_question not in geo_api._eligible_question_ids(), "failed question leaked back into automatic planning")

            # C-level local simulation remains useful internally but never changes official GEO.
            sim_question = questions[20]["question_id"]
            sim_plan = geo.create_plan(limit=1, provider="local_model", test_method="local_simulation", question_ids=[sim_question])
            sim_task = geo.enqueue_plan(sim_plan)["tasks"][0]
            sim_receipt = geo.record_result({
                "task_id": sim_task["task_id"],
                "provider": "local_model",
                "model": "local-test",
                "test_method": "local_simulation",
                "raw_answer": "模拟分析提到了卡嘴子 https://kazuizhi.com/，但这不是外部证据。",
            })
            check(sim_receipt["evidence_level"] == "C" and not sim_receipt["official_truth"], "local simulation counted as official GEO")

            # B-level external API result requires verified web search + proof reference.
            official_question = questions[30]["question_id"]
            official_plan = geo.create_plan(limit=1, provider="openai_web_search", test_method="api", question_ids=[official_question])
            official_task = geo.enqueue_plan(official_plan)["tasks"][0]
            geo.claim_next_task({
                "real_external": True,
                "authorization_ready": True,
                "provider_ready": True,
                "provider": "openai_web_search",
                "test_method": "api",
                "executor_id": "test-executor",
            })
            # Direct receipt ingestion is supported for a separately authenticated external/manual executor.
            receipt = geo.record_result({
                "task_id": official_task["task_id"],
                "provider": "openai_web_search",
                "model": "gpt-test",
                "test_method": "api",
                "raw_answer": "公开搜索结果中提到了卡嘴子，并引用 https://kazuizhi.com/seo/example 。",
                "citation_urls": ["https://kazuizhi.com/seo/example"],
                "response_id": "resp_test_001",
                "evidence_ref": "openai-response:resp_test_001",
                "web_search_verified": True,
                "evidence_level": "B",
            })
            check(receipt["official_truth"] and receipt["evidence_level"] == "B", "verified web-search receipt did not count as B evidence")
            check(receipt["brand_mentioned"] and receipt["brand_occurrences"] == 1, "deterministic brand mention failed")
            check(receipt["brand_cited"], "official-domain citation failed")
            check("https://kazuizhi.com/seo/example" in receipt["extracted_urls"], "URL extraction failed")

            snapshot = geo.dashboard()
            check(snapshot["controller"] == "chatgpt", "dashboard controller drifted")
            check(snapshot["simulation"]["count"] >= 1 and not snapshot["simulation"]["counts_in_official_metrics"], "simulation leaked into official dashboard")
            check(snapshot["official"]["tested"] >= 1, "official evidence missing from dashboard")
            check(snapshot["evidence_policy"]["local_model_counts_as_official"] is False, "local model truth gate disabled")
            check("geo_score" in snapshot["phase2_reserved"], "Phase 2 boundary missing")
            check("gap_engine" in snapshot["phase3_reserved"], "Phase 3 boundary missing")

            sample = {
                "id": "resp_sample",
                "model": "gpt-sample",
                "output": [
                    {"type": "web_search_call", "id": "ws_1"},
                    {"type": "message", "content": [{
                        "type": "output_text",
                        "text": "sample answer",
                        "annotations": [{"type": "url_citation", "url": "https://example.com/source", "title": "source"}],
                    }]},
                ],
            }
            text, urls, used = executor._extract_response(sample)
            check(text == "sample answer" and used, "OpenAI web_search proof parser failed")
            check(urls == ["https://example.com/source"], "OpenAI citation parser failed")
            check(executor._official_responses_endpoint("https://api.openai.com/v1/responses") == "https://api.openai.com/v1/responses", "official endpoint rejected")
            expect_error(lambda: executor._official_responses_endpoint("https://example.com/v1/responses"), "官方 OpenAI")

            ui = (SRC / "web" / "operational-search.js").read_text(encoding="utf-8")
            css = (SRC / "web" / "operational-search.css").read_text(encoding="utf-8")
            decision_ui = (SRC / "web" / "decision_layout_patch.js").read_text(encoding="utf-8")
            for marker in ("SEO 增长", "GEO 增长", "ChatGPT GEO 总控", "执行本轮 GEO 测试", "固定 50 问", "GEO Evidence / Receipt", "待我处理"):
                check(marker in ui, f"GEO workspace marker missing: {marker}")
            for marker in ("is-running", "is-success", "is-waiting", "is-danger", "font-variant-numeric:tabular-nums"):
                check(marker in css, f"GEO B2B UI semantic marker missing: {marker}")
            for marker in ("今日 GEO 决策 · ChatGPT 总脑", "geo-decision-progress", "geo-decision-blockers", "下一决策条件", "kz-search-growth-workspace"):
                check(marker in decision_ui, f"AI Decision Center GEO bridge missing: {marker}")
            check("/api/search-growth" in ui and "search-pack" in ui, "existing SEO workspace behavior was removed")
            check("第九" not in decision_ui and "9 个员工" not in decision_ui, "GEO was incorrectly added as a ninth AI employee")

            print("PASS: R8-19 GEO Phase 1 truth gates, baseline, runner contracts and decision/workspace UI are intact")
        finally:
            sys.path.remove(str(SRC))
            if old_local is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = old_local


if __name__ == "__main__":
    main()
