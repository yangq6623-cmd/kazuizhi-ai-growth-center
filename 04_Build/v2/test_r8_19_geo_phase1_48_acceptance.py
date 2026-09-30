"""Explicit acceptance gate for the 48 agreed R8-19 GEO Phase-1 details.

This test is intentionally offline.  It proves the product/runtime contracts,
not that an owner's external OpenAI credential has already completed 50 live
questions.  Live GEO evidence remains a separate field acceptance gate.
"""
from __future__ import annotations

import os
import re
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "05_V2.0.0_Source"


class Gate:
    def __init__(self):
        self.items = {}

    def ok(self, number: int, condition, note: str):
        if not condition:
            raise AssertionError(f"48项验收 #{number} 失败: {note}")
        self.items[number] = note

    def done(self):
        missing = [number for number in range(1, 49) if number not in self.items]
        if missing:
            raise AssertionError(f"48项验收缺失: {missing}")
        print("PASS: R8-19 GEO Phase 1 explicit acceptance = 48 / 48")


def expect_error(fn, contains=""):
    try:
        fn()
    except (ValueError, RuntimeError, PermissionError) as error:
        if contains and contains not in str(error):
            raise AssertionError(f"错误类型不符: {error}")
        return str(error)
    raise AssertionError("预期异常未发生")


def normalized_question(text: str) -> str:
    return re.sub(r"[\W_]+", "", str(text or "").lower(), flags=re.UNICODE)


def main():
    gate = Gate()
    old_local = os.environ.get("LOCALAPPDATA")
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["LOCALAPPDATA"] = tmp
        sys.path.insert(0, str(SRC))
        try:
            from core import geo_validation as geo
            from backend import r8_19_geo_validation_patch as geo_api
            from integrations import geo_openai_search_executor as executor

            ui = (SRC / "web" / "operational-search.js").read_text(encoding="utf-8")
            css = (SRC / "web" / "operational-search.css").read_text(encoding="utf-8")
            direct = (SRC / "web" / "geo.html").read_text(encoding="utf-8")
            decision_ui = (SRC / "web" / "decision_layout_patch.js").read_text(encoding="utf-8")
            r818 = (SRC / "backend" / "r8_18_evidence_ledger_patch.py").read_text(encoding="utf-8")

            # A. GEO 工作区 1-6
            gate.ok(1, "SEO 增长" in ui and "GEO 增长" in ui, "保留同一SEO/GEO业务入口，不新增GEO主侧栏")
            gate.ok(2, "data-growth-tab=\"seo\"" in ui and "data-growth-tab=\"geo\"" in ui, "内部拆分SEO/GEO一级工作区")
            gate.ok(3, "kz-search-growth-workspace" in ui and "localStorage" in ui, "记忆最后工作区")
            gate.ok(4, "changePage('search')" in direct and "data-growth-tab=\"geo\"" in direct, "存在可直达GEO的 /geo.html 路由")
            gate.ok(5, "/api/search-growth" in ui and "search-pack" in ui, "SEO原运行入口保持存在")
            gate.ok(6, "ChatGPT GEO 总控" in ui and ui.index("ChatGPT GEO 总控") < ui.index("GEO第一阶段核心指标"), "GEO首屏第一视觉是ChatGPT总控")

            qset = geo.question_set()
            questions = qset["questions"]

            # B. ChatGPT 总脑控制 7-12
            original_context = geo_api._active_mission_context
            try:
                geo.set_decision({"mission_id": "MISSION-OLD", "daily_test_limit": 4})
                geo_api._active_mission_context = lambda: {
                    "mission_id": "MISSION-CURRENT-001",
                    "mission_title": "当前真实 Mission",
                    "mission_goal": "测试",
                    "source_command_id": "CMD-UPSTREAM-001",
                    "source_decision_pack_id": "DP-UPSTREAM-001",
                }
                effective = geo_api._effective_decision()
            finally:
                geo_api._active_mission_context = original_context
            gate.ok(7, effective.get("mission_id") == "MISSION-CURRENT-001" and effective.get("bound_to_current_mission"), "GEO绑定当前Mission")
            gate.ok(8, bool(effective.get("decision_id")) and effective.get("controller") == "chatgpt", "记录ChatGPT Decision ID")
            gate.ok(9, bool(effective.get("command_id")), "记录Command ID")
            plan = geo.create_plan(limit=50, provider="openai_web_search", test_method="api")
            gate.ok(10, plan["count"] <= int(effective["daily_test_limit"]), "ChatGPT日测试量限制生效")
            selected = geo_api._persist_decision_extras(effective, providers=["openai_web_search"])
            gate.ok(11, selected["test_providers"] == ["openai_web_search"] and selected["provider_selection_controller"] == "chatgpt" and selected["platform_self_polling_allowed"] is False, "测试平台由ChatGPT决定")
            expect_error(lambda: geo_api._normalized_providers(["local_model"]), "unsupported_phase1_geo_provider")
            gate.ok(12, geo.MAX_RETRIES == 2 and "geo_retry_requires_chatgpt_approval" in Path(SRC / "core" / "geo_validation.py").read_text(encoding="utf-8"), "失败重试有限且需ChatGPT批准")

            # C. 固定50问 13-22
            counts = qset["counts"]
            gate.ok(13, counts.get("discovery") == 30 and not any("卡嘴子" in q["question_text"] for q in questions if q["question_type"] == "discovery"), "30题自然发现且不泄露品牌")
            gate.ok(14, counts.get("commercial") == 10, "10题商业推荐")
            gate.ok(15, counts.get("brand") == 10, "10题品牌认知")
            ids = [q["question_id"] for q in questions]
            gate.ok(16, len(ids) == len(set(ids)) == 50 and all(qid.startswith("GEO50-") for qid in ids), "每题永久question_id且唯一")
            gate.ok(17, qset.get("version") == geo.QUESTION_SET_VERSION and bool(qset.get("question_set_hash")), "题库有baseline_version/hash")
            first_hash = qset["question_set_hash"]
            gate.ok(18, geo.bootstrap_question_set(force=True)["question_set_hash"] == first_hash and qset.get("immutable_within_version") is True, "同版本基准不可静默修改")
            gate.ok(19, all(all(key in q for key in ("region", "service", "intent", "question_type")) for q in questions), "region/service/intent/type标签完整")
            gate.ok(20, any(q.get("service") == "个人任务" for q in questions), "个人任务已进入基准")
            normalized = [normalized_question(q["question_text"]) for q in questions]
            gate.ok(21, len(normalized) == len(set(normalized)) == 50, "题库自动阻止规范化重复题")
            gate.ok(22, any(x.get("event_type") in {"question_set_bootstrapped", "question_set_force_ignored"} for x in geo.audit_events(20)), "题库建立/变更写审计日志")

            # D. GEO Runner 23-34
            gate.ok(23, "queued" in geo.TASK_STATES, "支持QUEUED排队")
            gate.ok(24, "running" in geo.TASK_STATES, "支持RUNNING执行中")
            gate.ok(25, "succeeded" in geo.TASK_STATES and state_marker(ui, "succeeded", "已验证"), "支持COMPLETED/已验证成功态")
            gate.ok(26, "authorization_required" in geo.TASK_STATES and "待授权" in ui, "支持AUTH_REQUIRED待授权")
            gate.ok(27, "failed" in geo.TASK_STATES and "is-danger" in css, "支持FAILED红色失败态")
            gate.ok(28, "paused" in geo.TASK_STATES and "pause_task" in Path(SRC / "core" / "geo_validation.py").read_text(encoding="utf-8"), "支持PAUSED且不丢上下文")

            runner_questions = [questions[0]["question_id"], questions[1]["question_id"]]
            runner_plan = geo.create_plan(limit=2, provider="openai_web_search", test_method="api", question_ids=runner_questions)
            tasks = geo.enqueue_plan(runner_plan)["tasks"]
            claimed1 = geo.claim_next_task({"real_external": True, "authorization_ready": True, "provider_ready": True, "provider": "openai_web_search", "test_method": "api", "executor_id": "acceptance"})["task"]
            first_run_id = claimed1.get("run_id")
            gate.ok(29, first_run_id and first_run_id.startswith("GEO-RUN-"), "每次执行生成独立run_id")
            status = executor.status()
            gate.ok(30, all(key in status for key in ("configured", "verified", "ready", "reason")), "Runner执行前有平台可用性/授权预检")
            geo.fail_task(claimed1["task_id"], "simulated_provider_failure")
            claimed2 = geo.claim_next_task({"real_external": True, "authorization_ready": True, "provider_ready": True, "provider": "openai_web_search", "test_method": "api", "executor_id": "acceptance"})["task"]
            gate.ok(31, claimed2["task_id"] != claimed1["task_id"] and claimed2["state"] == "running", "单任务/单平台失败不拖死剩余队列")
            gate.ok(32, all(int(t.get("max_retries") or 0) == 2 for t in tasks), "每任务有限重试次数")
            failed = next(t for t in geo.queue_summary()["tasks"] if t["task_id"] == claimed1["task_id"])
            gate.ok(33, failed.get("failure_reason") == "simulated_provider_failure" and bool(failed.get("failure_code")), "失败保存具体原因和代码")
            receipt = geo.record_result({
                "task_id": claimed2["task_id"],
                "provider": "openai_web_search",
                "model": "gpt-acceptance",
                "model_version": "gpt-acceptance",
                "test_method": "api",
                "raw_answer": "卡嘴子公开信息见 https://kazuizhi.com/seo/acceptance ，另参考 https://example.com/source 。卡嘴子可作为本地服务连接平台了解。",
                "citation_urls": ["https://kazuizhi.com/seo/acceptance", "https://example.com/source"],
                "response_id": "resp_acceptance_001",
                "evidence_ref": "openai-response:resp_acceptance_001",
                "web_search_verified": True,
                "evidence_level": "B",
            })
            completed = next(t for t in geo.queue_summary()["tasks"] if t["task_id"] == claimed2["task_id"])
            gate.ok(34, completed["state"] == "succeeded" and completed.get("evidence_id") == receipt["evidence_id"], "Receipt完成后自动回写任务状态")

            # E. Evidence / Receipt 35-44
            gate.ok(35, receipt["question_text"] == claimed2["question_text"] and receipt["question_id"] == claimed2["question_id"], "证据保存原始问题与question_id")
            gate.ok(36, bool(receipt["raw_answer"]), "保存完整raw_answer")
            gate.ok(37, all(receipt.get(key) for key in ("provider", "model", "model_version")), "保存provider/model/model_version")
            gate.ok(38, bool(receipt.get("tested_at")), "保存tested_at")
            gate.ok(39, len(receipt.get("answer_hash") or "") == 64, "保存answer_hash防静默改写")
            gate.ok(40, len(receipt.get("citation_urls") or []) == 2, "保存citation_urls并保留官网/第三方来源")
            gate.ok(41, receipt["evidence_id"] == receipt["receipt_id"] and receipt["evidence_id"].startswith("GEO-RECEIPT-"), "每条结果唯一evidence_id/receipt_id")
            gate.ok(42, receipt["test_method"] == "api" and {"api", "browser", "manual"}.issubset(geo.TEST_METHODS), "保存API/Browser/Manual测试方式")
            sim_plan = geo.create_plan(limit=1, provider="local_model", test_method="local_simulation", question_ids=[questions[20]["question_id"]])
            sim_task = geo.enqueue_plan(sim_plan)["tasks"][0]
            sim = geo.record_result({"task_id": sim_task["task_id"], "provider": "local_model", "model": "local", "test_method": "local_simulation", "raw_answer": "卡嘴子 https://kazuizhi.com/"})
            gate.ok(43, receipt["evidence_level"] == "B" and receipt["official_truth"] and sim["evidence_level"] == "C" and not sim["official_truth"], "A/B/C证据分级；本地模型只能C且不计正式GEO")
            gate.ok(44, "<details class=\"geo-receipt\">" in ui and "<summary>" in ui and "geo-receipt-body" in ui, "证据详情可从列表展开追溯原始证据")

            # F. 基础结果判定 45-48
            gate.ok(45, receipt["brand_mentioned"] is True, "程序直接判定卡嘴子是否出现")
            gate.ok(46, receipt["brand_cited"] is True, "程序直接判定kazuizhi.com引用")
            gate.ok(47, "https://example.com/source" in receipt["extracted_urls"] and "https://kazuizhi.com/seo/acceptance" in receipt["extracted_urls"], "程序提取全部URL")
            gate.ok(48, receipt["brand_occurrences"] == 2, "程序记录品牌出现次数")

            # Cross-cutting runtime wiring checks.
            if "r8_19_geo_validation_patch" not in r818:
                raise AssertionError("R8-19 HTTP patch is not loaded by packaged runtime")
            if "window.location.href = '/geo.html'" not in decision_ui:
                raise AssertionError("AI Decision Center does not use the stable GEO route")
            gate.done()
        finally:
            sys.path.remove(str(SRC))
            if old_local is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = old_local


def state_marker(source: str, state: str, label: str) -> bool:
    return state in source and label in source


if __name__ == "__main__":
    main()
