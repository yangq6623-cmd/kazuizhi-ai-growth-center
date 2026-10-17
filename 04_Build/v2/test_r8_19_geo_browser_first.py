"""R8-19 browser-first GEO regression gate.

Proves that paid APIs are optional, real external browser evidence can count as
A-level truth, and the local model remains C-level auxiliary analysis only.
"""
from __future__ import annotations

import json
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
        if contains and contains not in str(error):
            raise AssertionError(f"wrong error: {error}")
        return
    raise AssertionError("expected error was not raised")


def main():
    old_local = os.environ.get("LOCALAPPDATA")
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["LOCALAPPDATA"] = tmp
        sys.path.insert(0, str(SRC))
        try:
            from core import geo_validation as geo
            from backend import r8_19_geo_validation_patch as api
            from integrations import ai_gateway, geo_browser_validation, geo_local_precheck

            browser = geo_browser_validation.status()
            check(browser["ready"] and browser["requires_api"] is False, "browser GEO unexpectedly requires API")
            check(api.DEFAULT_PROVIDER == "browser_external_ai" and api.DEFAULT_TEST_METHOD == "browser", "browser is not the default GEO mode")
            effective = api._effective_decision()
            check(effective["test_providers"][0] == "browser_external_ai", "legacy decision did not migrate to browser-first")
            check(effective["api_required"] is False and effective["browser_first"] is True, "decision still treats API as mandatory")

            questions = geo.question_set()["questions"]
            plan = geo.create_plan(limit=1, provider="browser_external_ai", test_method="browser", question_ids=[questions[0]["question_id"]])
            task = geo.enqueue_plan(plan)["tasks"][0]
            claimed = geo.claim_next_task({
                "real_external": True,
                "authorization_ready": True,
                "provider_ready": True,
                "provider": "deepseek_web",
                "test_method": "browser",
                "executor_id": geo_browser_validation.EXECUTOR_ID,
            })["task"]
            check(claimed["task_id"] == task["task_id"] and claimed["run_id"].startswith("GEO-RUN-"), "browser task was not truthfully claimed")
            receipt = geo_browser_validation.record_browser_result({
                "task_id": task["task_id"],
                "platform": "deepseek_web",
                "session_url": "https://chat.deepseek.com/a/chat/s/test-session",
                "raw_answer": "在公开回答中可以了解卡嘴子，官网信息见 https://kazuizhi.com/ 。",
                "citation_urls": ["https://kazuizhi.com/"],
            })
            check(receipt["official_truth"] and receipt["evidence_level"] == "A", "real browser result did not become A-level evidence")
            check(receipt["test_method"] == "browser" and receipt["session_url"].startswith("https://"), "browser proof fields missing")
            expect_error(lambda: geo_browser_validation._external_https_url("http://127.0.0.1:8876/geo.html"), "cannot_use_local_url")

            original_route_status = ai_gateway._route_status
            original_profile = ai_gateway._profile
            original_api_key = ai_gateway._api_key
            original_transport = ai_gateway._http_transport
            try:
                ai_gateway._route_status = lambda route: {
                    "configured": True, "verified": True, "provider": "ollama", "model": "qwen-local",
                    "endpoint": "http://127.0.0.1:11434/v1/chat/completions", "last_error": None,
                }
                ai_gateway._profile = lambda route: {
                    "provider": "ollama", "model": "qwen-local", "endpoint": "http://127.0.0.1:11434/v1/chat/completions",
                    "protocol": "chat_completions",
                }
                ai_gateway._api_key = lambda route: ("", "none")
                ai_gateway._http_transport = lambda payload, key, profile: {
                    "choices": [{"message": {"content": json.dumps({
                        "answer": "本地预检回答",
                        "likely_visibility": "low",
                        "content_gaps": ["本地品牌公开资料不足"],
                        "keywords": ["涟水维修"],
                        "notes": "仅本地预检",
                    }, ensure_ascii=False)}}]
                }
                local_result = geo_local_precheck.run(limit=1, question_ids=[questions[1]["question_id"]])
            finally:
                ai_gateway._route_status = original_route_status
                ai_gateway._profile = original_profile
                ai_gateway._api_key = original_api_key
                ai_gateway._http_transport = original_transport
            local_item = local_result["results"][0]
            check(local_item["evidence_level"] == "C" and local_item["official_truth"] is False, "local precheck leaked into official GEO")

            snapshot = api._dashboard_with_executor()
            check(snapshot["execution_modes"]["default"] == "browser", "dashboard no longer advertises browser-first mode")
            check(snapshot["execution_modes"]["api"]["requires_api"] is True, "optional API mode metadata broken")
            check(snapshot["execution_modes"]["local_precheck"]["official_truth"] is False, "local-precheck truth label broken")

            ui = (SRC / "web" / "operational-search.js").read_text(encoding="utf-8")
            for marker in (
                "本地预检1题", "网页真实验证1题", "保存真实网页 Evidence / Receipt",
                "API执行本轮 GEO 测试（可选）", "API未配置不是阻塞", "ChatGPT Work",
            ):
                check(marker in ui, f"browser-first GEO UI marker missing: {marker}")

            print("PASS: R8-19 GEO browser-first no-API mode, A-level browser evidence and C-level local precheck are intact")
        finally:
            sys.path.remove(str(SRC))
            if old_local is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = old_local


if __name__ == "__main__":
    main()
