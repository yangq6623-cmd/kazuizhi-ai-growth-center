"""#857 targeted regression for truthful continuation, GEO claim gates and SEO revisions."""

import os
import shutil
import sys
import tempfile
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SRC))

sandbox = Path(tempfile.mkdtemp(prefix="kazuizhi-857-closure-"))
os.environ["LOCALAPPDATA"] = str(sandbox)

try:
    from core import daily_workforce, geo_validation, r7_engine, seo_geo_autonomy, seo_geo_growth
    from core.storage import read_json, write_json

    # Completed B02/B03 remains the last real batch while the system waits for
    # a new evidence-qualified opportunity.  It must never fall back to B01.
    today = datetime.now().astimezone().date().isoformat()
    base = []
    for index in range(20):
        base.append({
            "id": f"base-{index}", "state": "completed", "schedule_date": today,
            "schedule_source": "daily_workforce", "batch_id": f"R7-{today.replace('-', '')}-B01",
            "batch_number": 1, "mission_id": "MISSION-857", "command_id": "CMD-857",
        })
    b2 = {
        "id": "continuation-b2", "state": "completed", "schedule_date": today,
        "schedule_source": "daily_workforce_continuation",
        "batch_id": f"R7-{today.replace('-', '')}-B02", "batch_number": 2,
        "idempotency_key": f"daily_continuation:{today}:already-used",
        "mission_id": "MISSION-857", "command_id": "CMD-857",
    }
    original_candidates = daily_workforce._continuation_candidates
    daily_workforce._continuation_candidates = lambda _today: ([], 1790000000.0)
    wait = daily_workforce._continuation_batch({"items": [b2, *base]}, today, datetime.now().astimezone())
    assert wait["reason"] == "no_new_eligible_work", wait
    assert wait["batch_number"] == 2 and wait["batch_id"].endswith("B02"), wait
    assert wait["batch_state"] == "completed_waiting_eligibility", wait
    daily_workforce._continuation_candidates = original_candidates

    # The diagnostic and atomic claim paths share the same fail-closed rule.
    blocked_task = {
        "task_id": "GEO-TASK-BLOCKED-857", "question_id": "GEO50-D01",
        "state": "queued", "provider": "deepseek_web", "test_method": "browser",
        "expected_platform": "deepseek_web", "started_at": "2026-10-21T12:00:00+08:00",
        "run_id": "GEO-RUN-OLD", "attempt_id": "GEO-ATTEMPT-OLD", "attempts": [{"result": "RUNNING"}],
    }
    write_json(geo_validation.QUEUE_PATH, {"tasks": [blocked_task]})
    diagnostic = geo_validation._queue_diagnostics([blocked_task])
    detail = diagnostic["routing_diagnostics"]["queued_tasks"][0]
    assert detail["route_state"] == "blocked_by_safety_gate", detail
    assert detail["claim_blocker"] == "prior_external_attempt_requires_reconciliation", detail
    blocked_claim = geo_validation.claim_next_task({
        "real_external": True, "authorization_ready": True, "provider_ready": True,
        "provider": "deepseek_web", "test_method": "browser", "executor_id": "browser-857",
        "strict_provider": True, "fresh_only": True,
    })
    assert blocked_claim["reason"] == "queue_blocked", blocked_claim
    assert blocked_claim["blocked"][0]["task_id"] == "GEO-TASK-BLOCKED-857", blocked_claim

    fresh_task = {
        "task_id": "GEO-TASK-FRESH-857", "question_id": "GEO50-D02",
        "state": "queued", "provider": "deepseek_web", "test_method": "browser",
        "expected_platform": "deepseek_web", "started_at": "", "run_id": "", "attempt_id": "",
        "retry_count": 0, "attempts": [],
    }
    write_json(geo_validation.QUEUE_PATH, {"tasks": [fresh_task]})
    fresh_claim = geo_validation.claim_next_task({
        "real_external": True, "authorization_ready": True, "provider_ready": True,
        "provider": "deepseek_web", "test_method": "browser", "executor_id": "browser-857",
        "strict_provider": True, "fresh_only": True,
    })
    assert fresh_claim["task"]["task_id"] == "GEO-TASK-FRESH-857", fresh_claim
    assert fresh_claim["task"]["state"] == "running", fresh_claim

    # A controller-approved retry remains executable; an unapproved historical
    # replay never becomes claimable merely because its state says queued.
    retryable = dict(fresh_task, task_id="GEO-TASK-RETRY-857", state="failed", max_retries=2,
                     retry_count=0, started_at="", run_id="", attempt_id="", attempts=[])
    write_json(geo_validation.QUEUE_PATH, {"tasks": [retryable]})
    approved = geo_validation.retry_task("GEO-TASK-RETRY-857", approved_by=geo_validation.CONTROLLER)
    assert approved["retry_approved_by"] == geo_validation.CONTROLLER, approved
    retry_claim = geo_validation.claim_next_task({
        "real_external": True, "authorization_ready": True, "provider_ready": True,
        "provider": "deepseek_web", "test_method": "browser", "executor_id": "browser-857",
        "strict_provider": True, "fresh_only": True,
    })
    assert retry_claim["task"]["task_id"] == "GEO-TASK-RETRY-857", retry_claim

    # Existing Asset revisions are not counted as newly generated Assets.  This
    # reconstructs #856 data using the immutable legacy refresh audit event.
    date = "2026-10-21"
    ledger = seo_geo_growth._empty_state()
    ledger["assets"] = [
        {"id": "SEO-NEW-857", "generated_at": date + "T09:00:00+08:00"},
        {"id": "SEO-UPDATED-857", "generated_at": date + "T10:00:00+08:00"},
    ]
    ledger["audit"] = [{
        "at": date + "T10:01:00+08:00", "kind": "legacy_public_pages_rebuilt",
        "detail": {"asset_ids": ["SEO-UPDATED-857"]},
    }]
    breakdown = seo_geo_growth._daily_generation_breakdown(ledger, date)
    assert breakdown["new_asset_ids"] == ["SEO-NEW-857"], breakdown
    assert breakdown["updated_asset_ids"] == ["SEO-UPDATED-857"], breakdown

    # A real legacy rebuild keeps the immutable first-generation time and
    # creates revision metadata without changing the public/submitted stage.
    original_generated_at = "2026-10-18T09:30:00+08:00"
    live_state = seo_geo_growth._load()
    live_state["assets"] = [{
        "id": "SEO-REVISION-857", "slug": "revision-857",
        "region": "涟水县", "service": "家电维修",
        "keyword": "涟水县空调上门维修", "stage": "SUBMITTED",
        "generated_at": original_generated_at,
        "created_at": "2026-10-18T09:00:00+08:00",
        "published_at": "2026-10-18T10:00:00+08:00",
        "public_template_version": "r8-13",
        "canonical": "https://kazuizhi.com/seo/revision-857/",
        "public_url": "https://kazuizhi.com/seo/revision-857/",
        "submission_receipts": [{"at": "2026-10-18T10:05:00+08:00", "receipt": "historic"}],
    }]
    seo_geo_growth._save(live_state)
    revision = seo_geo_growth.refresh_legacy_staging(limit=1)
    assert revision["refreshed"] == ["SEO-REVISION-857"], revision
    revised = seo_geo_growth._load()["assets"][0]
    assert revised["generated_at"] == original_generated_at, revised
    assert revised["stage"] == "SUBMITTED" and revised["republish_pending"], revised
    assert str(revised.get("last_staging_refresh_at") or ""), revised
    assert str(revised.get("content_revision_id") or "").startswith("SEO-REV-"), revised
    assert revised["submission_receipts"] == [{"at": "2026-10-18T10:05:00+08:00", "receipt": "historic"}]

    validation = seo_geo_autonomy.validation_status({"unattended_validation": {
        "started_at": "2026-10-01T00:00:00+00:00", "failure_cycles": 0,
        "progress_events": 1, "cycle_count": 10, "success_cycles": 10,
    }})
    assert validation["acceptance_scope"] == "historical_process_lifetime", validation
    assert validation["independent_candidate_qualified"] is False, validation

    ui = (SRC / "web" / "r8_13_seo_geo.html").read_text(encoding="utf-8")
    assert "新Asset生成" in ui and "旧Asset修订" in ui
    assert "不能证明 #856/#857 连续24小时在线" in ui
    assert "事件比仅用于发现埋点口径差异" in ui

    print("PASS #857: exact GEO safety blocker, approved retry, persistent B02/B03 identity, revision-vs-new SEO counts, and candidate-window truth")
finally:
    shutil.rmtree(sandbox, ignore_errors=True)
