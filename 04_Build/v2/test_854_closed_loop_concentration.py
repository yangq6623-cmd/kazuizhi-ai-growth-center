"""#854 targeted regression: full ledger, in-day batches, GEO routing and QC truth."""

import os
import shutil
import sys
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SRC))

sandbox = Path(tempfile.mkdtemp(prefix="kazuizhi-854-closed-loop-"))
os.environ["LOCALAPPDATA"] = str(sandbox)

try:
    from core import autonomy, daily_workforce, geo_validation, r7_engine
    from core import r8_22_autonomous_convergence as convergence
    from core import seo_geo_growth
    from core.storage import read_json, write_json

    first = daily_workforce.ensure_daily_workforce()
    assert first["base_planned"] == 20 and first["created"] == first["planned"], first

    store = read_json(r7_engine.JOBS, {"items": []})
    for row in store["items"]:
        if row.get("schedule_source") == "daily_workforce":
            row.update(
                state="completed", progress=100, completed_steps=1,
                mission_id="MISSION-854-TEST", command_id="CMD-854-TEST",
                command_receipt_id="COMMAND-RECEIPT-854",
                priority_class=convergence.CURRENT_PRIORITY,
                execution_receipt={"receipt_id": "LOCAL-" + row["id"], "status": "completed"},
            )
    write_json(r7_engine.JOBS, store)

    original_candidates = daily_workforce._continuation_candidates
    candidate_round = {"number": 2}

    def candidates(_today):
        number = candidate_round["number"]
        return ([{
            "key": f"verified-candidate-{number}",
            "agent": "SEO/GEO 增长员",
            "task_type": "seo_pipeline",
            "title": f"推进隔离测试合格资产第{number}轮",
            "evidence_refs": [f"SEO-ASSET-{number}"],
            "reason": "isolated_verified_candidate",
        }], None)

    daily_workforce._continuation_candidates = candidates
    second = daily_workforce.ensure_daily_workforce()
    assert second["continuation_created"] == 1 and second["batch_number"] == 2, second
    store = read_json(r7_engine.JOBS, {"items": []})
    batch2 = [x for x in store["items"] if x.get("batch_number") == 2]
    assert len(batch2) == 1 and batch2[0]["mission_id"] == "MISSION-854-TEST", batch2
    assert batch2[0]["command_id"] == "CMD-854-TEST", batch2

    # An unfinished batch and the same eligibility fingerprint cannot duplicate.
    duplicate_guard = daily_workforce.ensure_daily_workforce()
    assert duplicate_guard["continuation_created"] == 0, duplicate_guard

    store = read_json(r7_engine.JOBS, {"items": []})
    batch2[0] = next(x for x in store["items"] if x.get("batch_number") == 2)
    batch2[0].update(state="completed", progress=100, completed_steps=1)
    write_json(r7_engine.JOBS, store)
    candidate_round["number"] = 3
    third = daily_workforce.ensure_daily_workforce()
    assert third["continuation_created"] == 1 and third["batch_number"] == 3, third

    # The default list remains a 200-row UI window while Mission metrics read
    # every row in the durable ledger.
    store = read_json(r7_engine.JOBS, {"items": []})
    for index in range(205):
        store["items"].append({
            "id": f"history-{index}", "state": "completed", "mode": "local",
            "mission_id": "MISSION-854-TEST", "command_id": "CMD-854-TEST",
            "result": {"summary": "historical local analysis"},
            "execution_receipt": {"receipt_id": f"LOCAL-HISTORY-{index}"},
        })
    write_json(r7_engine.JOBS, store)
    display = r7_engine.list_jobs()
    assert len(display["items"]) == 200 and display["ledger_count"] == len(store["items"]), display
    metrics = convergence._metrics("CMD-854-TEST", "MISSION-854-TEST")
    expected = sum(
        1 for row in store["items"]
        if row.get("command_id") == "CMD-854-TEST" or row.get("mission_id") == "MISSION-854-TEST"
    )
    assert metrics["tasks"]["total"] == expected > 200, metrics["tasks"]
    assert metrics["tasks"]["count_scope"] == "current_mission_or_command_tasks"
    assert metrics["tasks"]["full_r7_ledger_total"] == len(store["items"])

    # Fast and full GEO snapshots must expose the exact queued tasks and the
    # executor that is allowed to claim each route.
    now = time.time()
    tasks = [
        {"task_id": "GEO-TASK-CLOUD-854", "question_id": "GEO50-D01", "state": "queued",
         "provider": "cloud_auto", "test_method": "api", "expected_platform": "",
         "next_retry_at_epoch": now + 60, "mission_id": "GEO-GROWTH-OPERATING-RETEST-24H"},
        {"task_id": "GEO-TASK-QWEN-854", "question_id": "GEO50-C01", "state": "queued",
         "provider": "qwen_web", "test_method": "browser", "expected_platform": "qwen_web"},
        {"task_id": "GEO-TASK-UNCERTAIN-854", "state": "authorization_required",
         "authorization_reason": "capture_failed: answer timeout", "uncertain_external_submission": True},
    ]
    diagnostic = geo_validation._queue_diagnostics(tasks)
    details = {row["task_id"]: row for row in diagnostic["routing_diagnostics"]["queued_tasks"]}
    assert details["GEO-TASK-CLOUD-854"]["executor"] == "doubao_cloud_api"
    assert details["GEO-TASK-CLOUD-854"]["route_state"] == "retry_backoff"
    assert details["GEO-TASK-QWEN-854"]["executor"] == "chrome_geo_extension:qwen_web"
    assert diagnostic["blockage_diagnostics"]["legacy_technical_requires_review"] == 1
    assert diagnostic["blockage_diagnostics"]["uncertain_external_submission"] == 1
    fast_source = (SRC / "backend" / "r8_20_seo_geo_growth_patch.py").read_text(encoding="utf-8")
    assert "_queue_diagnostics(tasks)" in fast_source

    # A newly enqueued eligible route wakes the existing worker immediately;
    # the worker's provider/auth/cooldown gates remain authoritative.
    geo_validation.QUEUE_WAKE_EVENT.clear()
    wake_result = geo_validation.enqueue_plan({
        "plan_id": "GEO-PLAN-WAKE-854", "decision_id": "DECISION-WAKE-854",
        "command_id": "CMD-854-TEST", "mission_id": "MISSION-854-TEST",
        "provider": "qwen_web", "expected_platform": "qwen_web", "test_method": "browser",
        "questions": [{
            "question_id": "GEO50-C01", "question_text": "涟水空调维修如何选择？",
            "question_type": "commercial", "question_set_version": geo_validation.QUESTION_SET_VERSION,
            "region": "涟水县", "service": "空调维修", "intent": "commercial_compare",
        }],
        "correlation": {"schedule_id": "GEO-SCHEDULE-WAKE-854"},
    })
    assert wake_result["created"] == 1 and geo_validation.QUEUE_WAKE_EVENT.is_set(), wake_result

    # The fixed workforce SEO/GEO rows inspect the real growth ledger and no
    # longer manufacture the repeated generic local draft.
    generic = autonomy.execute_autonomous({
        "task_type": "seo", "title": "核对SEO增长", "schedule_source": "daily_workforce",
    })
    assert generic["draft_id"] is None and generic["seo_asset_id"] is None, generic

    # QC failure remains GENERATED and has an inspectable reason; it never
    # turns into a fake approval or public result.
    write_json(seo_geo_growth.STORE, {
        **seo_geo_growth._empty_state(),
        "assets": [{
            "id": "SEO-854-QC", "stage": "GENERATED", "keyword": "涟水空调维修",
            "created_at": "2026-10-21T00:00:00+08:00", "updated_at": "2026-10-21T00:00:00+08:00",
            "submission_receipts": [], "crawl_evidence": [], "index_evidence": [],
            "rankings": [], "geo_mentions": [], "conversions": [],
        }],
    })
    failed = seo_geo_growth.record_asset_qc_failure("SEO-854-QC", ["正文信息不足", "缺少差异化FAQ"])
    assert failed["stage"] == "GENERATED" and failed["qc_status"] == "failed", failed
    assert failed["qc_reasons"] == ["正文信息不足", "缺少差异化FAQ"], failed

    daily_workforce._continuation_candidates = original_candidates
    print("PASS #854: full-ledger Mission truth, B01/B02/B03 in-day continuation, no duplicate batches, exact GEO routing, and persistent SEO QC reasons")
finally:
    shutil.rmtree(sandbox, ignore_errors=True)
