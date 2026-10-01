"""Offline acceptance gate for R8-19 unattended GEO cloud scanning."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "05_V2.0.0_Source"


def main():
    old_local = os.environ.get("LOCALAPPDATA")
    old_key = os.environ.get("OPENAI_API_KEY")
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["LOCALAPPDATA"] = tmp
        os.environ["OPENAI_API_KEY"] = "test-cloud-key"
        sys.path.insert(0, str(SRC))
        try:
            from core import geo_autonomy
            from core import geo_validation as geo
            from core.storage import write_json
            from integrations import ai_gateway
            from integrations import geo_cloud_executor

            geo.bootstrap_question_set(force=True)
            write_json(
                ai_gateway.CONFIG_PATH,
                {
                    "schema": "kazuizhi-model-routing/v1",
                    "active_route": "cloud",
                    "fallback_enabled": True,
                    "profiles": {
                        "cloud": {
                            "provider": "豆包mini",
                            "label": "豆包mini",
                            "endpoint": "https://ark.cn-beijing.volces.com/api/v3/chat/completions",
                            # Field regression: an old UI may have saved Responses;
                            # the endpoint suffix must still select Chat Completions.
                            "protocol": "responses",
                            "model": "doubao-seed-2-0-mini-260428",
                            "protected_api_key": "",
                        },
                        "local": {
                            "provider": "ollama",
                            "label": "Ollama（本机）",
                            "endpoint": "http://127.0.0.1:11434/v1/chat/completions",
                            "protocol": "chat_completions",
                            "model": "",
                            "protected_api_key": "",
                        },
                    },
                },
            )
            write_json(
                ai_gateway.STATE_PATH,
                {"routes": {"cloud": {"last_test_at": "2026-10-02T10:00:00", "last_error": ""}}},
            )

            executor_status = geo_cloud_executor.status()
            assert executor_status["ready"] is True
            assert executor_status["protocol"] == "chat_completions"
            assert executor_status["model"] == "doubao-seed-2-0-mini-260428"
            assert executor_status["evidence_level"] == "C"
            assert executor_status["official_truth"] is False

            # Prevent the real daemon from racing this deterministic test. The
            # controller logic below is still exactly the production start/run path.
            geo_autonomy.start_worker = lambda: {"started": False, "reason": "test_stub"}

            # Upgrade-safety regression: #19/#22 could persist enabled=True,
            # target=50. A staged build must not inherit that old unattended
            # state and immediately continue all 50 questions after upgrade.
            write_json(
                geo_autonomy.STORE,
                {"schema": "kz.geo-autonomy.v1", "enabled": True, "paused": False, "target": 50},
            )
            migrated = geo_autonomy.status()
            assert migrated["schema"] == "kz.geo-autonomy.v2"
            assert migrated["state"] == "idle"
            assert migrated["enabled"] is False
            assert migrated["target"] == 1
            assert migrated["queue"]["queued"] == 0

            # Field regression: real users may already have browser/manual tasks
            # queued from earlier validation. A new cloud staged run must preserve
            # those tasks but must not be blocked behind them.
            legacy_plan = geo.create_and_enqueue_plan(
                limit=1,
                provider="browser_external_ai",
                test_method="browser",
                question_ids=["GEO50-B10"],
            )
            legacy_task_id = legacy_plan["tasks"][0]["task_id"]

            started = geo_autonomy.start(target=3)
            assert started["state"] == "running"
            assert started["target"] == 3
            assert started["acceptance_targets"] == [1, 3, 10, 50]
            assert started["queue"]["queued"] == 3

            calls = []

            def fake_transport(body, headers, endpoint, protocol):
                calls.append({"body": body, "endpoint": endpoint, "protocol": protocol, "authorization": headers.get("Authorization")})
                question = body["messages"][-1]["content"] if protocol == "chat_completions" else body["input"]
                return {
                    "id": f"doubao-test-{len(calls)}",
                    "model": "doubao-seed-2-0-mini-260428",
                    "choices": [{"message": {"content": f"测试回答 {len(calls)}：{question[-24:]}"}}],
                }

            for expected in (1, 2, 3):
                result = geo_autonomy.run_once(transport=fake_transport)
                assert result["ok"] is True
                assert result.get("receipt")
                receipt = result["receipt"]
                assert receipt["evidence_level"] == "C"
                assert receipt["official_truth"] is False
                assert receipt["provider"] == geo_cloud_executor.PROVIDER
                assert receipt["web_search_verified"] is False
                current = geo_autonomy.status()
                assert current["cloud_completed"] == expected
                assert current["formal_ab_completed"] == 0
                assert current["phase2_analyzed"] == 0
                assert current["truth_consistent"] is True

            final = geo_autonomy.status()
            assert final["state"] == "completed"
            assert final["cloud_completed"] == 3
            assert final["formal_ab_completed"] == 0
            assert final["phase2_analyzed"] == 0
            assert len(calls) == 3
            assert all(item["protocol"] == "chat_completions" for item in calls)
            assert all(item["authorization"] == "Bearer test-cloud-key" for item in calls)
            preserved = next(item for item in geo.queue_summary()["tasks"] if item.get("task_id") == legacy_task_id)
            assert preserved["state"] == "queued"
            assert preserved["provider"] == "browser_external_ai"

            receipts = [item for item in geo.receipts(100) if item.get("provider") == geo_cloud_executor.PROVIDER]
            assert len(receipts) == 3
            assert all(item.get("evidence_level") == "C" for item in receipts)
            assert all(not item.get("official_truth") for item in receipts)
            assert geo.dashboard()["official"]["tested"] == 0
            assert geo.dashboard()["simulation"]["count"] >= 3

            # Truth convergence regression: add one real A-level browser receipt.
            # The autonomy card, Phase-1 dashboard and Phase-2 analysis must all
            # report the same formal count instead of showing 1/50 in one place
            # and 0/50 in another.
            formal_plan = geo.create_and_enqueue_plan(
                limit=1,
                provider="chatgpt_web",
                test_method="browser",
                question_ids=["GEO50-B01"],
            )
            formal_task = formal_plan["tasks"][0]
            formal_receipt = geo.record_result({
                "task_id": formal_task["task_id"],
                "provider": "chatgpt_web",
                "test_method": "browser",
                "raw_answer": "卡嘴子是本地服务连接平台，可通过 https://kazuizhi.com/ 了解服务。",
                "session_url": "https://chatgpt.com/share/test-geo-formal",
                "citation_urls": ["https://kazuizhi.com/"],
            })
            assert formal_receipt["evidence_level"] == "A"
            assert formal_receipt["official_truth"] is True
            converged = geo_autonomy.status()
            assert geo.dashboard()["official"]["tested"] == 1
            assert converged["formal_ab_completed"] == 1
            assert converged["phase2_analyzed"] == 1
            assert converged["truth_consistent"] is True

            # Staged acceptance must be cumulative: after the 3-question gate,
            # switching to target 10 creates only the missing questions and the
            # owner-facing queue count is scoped to the active stage.
            stage10 = geo_autonomy.start(target=10)
            assert stage10["target"] == 10
            assert stage10["cloud_completed"] == 3
            assert stage10["queue"]["queued"] == 7
            assert stage10["queue"]["scope_target"] == 10

            ui = (SRC / "web" / "geo-autonomy.js").read_text(encoding="utf-8")
            for marker in ("测试1题", "测试到3题", "测试到10题", "启动剩余至50题"):
                assert marker in ui
            assert "Phase 2 已分析" in ui
            assert "正式 A/B Evidence" in ui
            assert "C 级辅助" in ui
            assert "旧队列" in ui
            bridge = (SRC / "backend" / "r8_14_seo_geo_autonomy_patch.py").read_text(encoding="utf-8")
            for route in (
                "/api/r8-19/geo/autonomy",
                "/api/r8-19/geo/autonomy/start",
                "/api/r8-19/geo/autonomy/pause",
                "/api/r8-19/geo/autonomy/resume",
                "/api/r8-19/geo/autonomy/retry-failed",
            ):
                assert route in bridge
            assert "geo-autonomy.js" in bridge

            print("PASS: R8-19 staged GEO 1/3/10/50 + queued-browser coexistence + safe legacy migration + unified truth counts")
        finally:
            sys.path.remove(str(SRC))
            if old_local is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = old_local
            if old_key is None:
                os.environ.pop("OPENAI_API_KEY", None)
            else:
                os.environ["OPENAI_API_KEY"] = old_key


if __name__ == "__main__":
    main()
