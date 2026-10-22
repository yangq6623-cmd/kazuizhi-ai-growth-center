"""#859 targeted regression for SEO discovery, GEO reconciliation and batches.

All files live below an isolated LOCALAPPDATA. Public deployment and IndexNow
responses are deterministic test doubles; this test performs no external I/O.
"""
from __future__ import annotations

import os
import shutil
import sys
import tempfile
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SRC))

sandbox = Path(tempfile.mkdtemp(prefix="kazuizhi-859-closure-"))
os.environ["LOCALAPPDATA"] = str(sandbox)
os.environ["KZ_INDEXNOW_KEY"] = "KazuizhiIndexNow859Isolated"


try:
    from core import daily_workforce, geo_validation, seo_geo_autonomy, seo_geo_growth
    from core.storage import write_json
    from integrations import search_engine_submitter, seo_public_deployer

    # Mature ledger: all baseline Opportunities are already bound. A real
    # high-intent, verified-scope Opportunity must appear exactly once today.
    seo_geo_growth.ensure_baseline()
    ledger = seo_geo_growth._load()
    for index, opportunity in enumerate(ledger["opportunities"]):
        opportunity["asset_id"] = f"SEO-OLD-{index:02d}"
        opportunity["status"] = "SUBMITTED"
        ledger["assets"].append({
            "id": opportunity["asset_id"], "opportunity_id": opportunity["id"],
            "keyword": opportunity["keyword"], "region": opportunity["region"],
            "service": opportunity["service"], "stage": "SUBMITTED",
            "slug": f"old-{index:02d}", "submission_receipts": [{"receipt": "old"}],
        })
    seo_geo_growth._save(ledger)

    with ThreadPoolExecutor(max_workers=2) as pool:
        concurrent_plans = list(pool.map(lambda _: seo_geo_growth.plan_today(limit=1), range(2)))
    assert sum(row["count"] for row in concurrent_plans) == 1, concurrent_plans
    plan = next(row for row in concurrent_plans if row["count"] == 1)
    assert plan["discovery"]["created"], plan
    new_asset_id = plan["created"][0]
    planned = next(row for row in seo_geo_growth._load()["assets"] if row["id"] == new_asset_id)
    assert planned["keyword"] == "涟水县空调不制冷上门维修", planned
    assert planned["stage"] == "PLANNED" and not planned["public_url"], planned

    duplicate = seo_geo_growth.plan_today(limit=1)
    assert duplicate["count"] == 0, duplicate
    assert duplicate["discovery"]["reason"] == "daily_incremental_discovery_already_recorded", duplicate

    generated = seo_geo_growth.generate_staging(limit=1)
    assert generated["generated"] == [new_asset_id], generated
    qc = seo_geo_autonomy._local_qc_generated_assets(limit=1)
    assert qc["passed"] == [new_asset_id] and not qc["failed"], qc

    # Exercise the original deployment and submission workers with isolated
    # filesystem/HTTP doubles. The state transitions and receipts are real.
    state = seo_geo_growth._load()
    asset = next(row for row in state["assets"] if row["id"] == new_asset_id)
    asset["publish_approved"] = True
    seo_geo_growth._save(state)
    site_root = sandbox / "isolated-site"
    site_root.mkdir()
    seo_public_deployer.configure({
        "enabled": True, "site_root": str(site_root),
        "public_base_url": "https://kazuizhi.example/",
    })
    original_public_verify = seo_public_deployer._verify_public_url
    seo_public_deployer._verify_public_url = lambda url, expected, canonical, timeout: {
        "ok": True, "status": 200, "content_match": True,
        "canonical_match": True, "schema_valid": True,
        "schema_urls_valid": True, "page_indexable": True,
        "source_tracking_present": True, "mini_program_entry_present": True,
        "mini_program_image_present": True, "robots": {"allowed": True},
        "checked_at": "isolated-test",
    }
    try:
        deployed = seo_public_deployer.deploy_pending(limit=1)
    finally:
        seo_public_deployer._verify_public_url = original_public_verify
    assert [row["asset_id"] for row in deployed["published"]] == [new_asset_id], deployed

    original_key_verify = search_engine_submitter._ensure_indexnow_key_file
    original_indexnow = search_engine_submitter._submit_indexnow
    search_engine_submitter._ensure_indexnow_key_file = lambda key, timeout=8: {
        "ok": True, "status": 200,
        "key_location": "https://kazuizhi.example/seo/test-key.txt",
        "checked_at": "isolated-test",
    }
    search_engine_submitter._submit_indexnow = lambda urls, key, key_location, endpoint, timeout=15: {
        "ok": True, "status": 200, "submitted": len(urls),
        "response": "", "at": "isolated-test",
    }
    try:
        submitted = search_engine_submitter.submit_pending(limit=1)
    finally:
        search_engine_submitter._ensure_indexnow_key_file = original_key_verify
        search_engine_submitter._submit_indexnow = original_indexnow
    assert submitted["submitted_count"] == 1, submitted
    closed = next(row for row in seo_geo_growth._load()["assets"] if row["id"] == new_asset_id)
    assert closed["stage"] == "SUBMITTED" and closed["submission_receipts"], closed

    # One queued historical task has an exact old Receipt, while two others
    # remain safely isolated. Preview is read-only; apply links only the exact
    # match and creates no external request or Evidence.
    task_ids = ["GEO-TASK-859-MATCH", "GEO-TASK-859-MISMATCH", "GEO-TASK-859-MISSING"]
    tasks = []
    for suffix, task_id in enumerate(task_ids, 1):
        tasks.append({
            "task_id": task_id, "question_id": f"GEO50-D{suffix:02d}",
            "state": "queued", "provider": "deepseek_web", "test_method": "browser",
            "expected_platform": "deepseek_web", "run_id": f"RUN-{suffix}",
            "attempt_id": f"ATTEMPT-{suffix}", "started_at": "2026-10-22T10:00:00+08:00",
            "attempts": [{"run_id": f"RUN-{suffix}", "attempt_id": f"ATTEMPT-{suffix}", "result": "RUNNING"}],
        })
    receipts = [{
        "task_id": task_ids[0], "question_id": "GEO50-D01", "provider": "deepseek_web",
        "run_id": "RUN-1", "attempt_id": "ATTEMPT-1", "evidence_id": "GEO-RECEIPT-859-1",
        "receipt_id": "GEO-RECEIPT-859-1", "tested_at": "2026-10-22T10:02:00+08:00",
        "finished_at": "2026-10-22T10:02:30+08:00", "session_url": "https://chat.deepseek.com/a/859",
        "raw_answer": "这是隔离账本中的既有外部回答，长度足够且不会触发任何新的发送。",
        "evidence_level": "A", "official_truth": True,
    }, {
        "task_id": task_ids[1], "question_id": "GEO50-D02", "provider": "deepseek_web",
        "run_id": "OLD-RUN", "attempt_id": "OLD-ATTEMPT", "evidence_id": "GEO-RECEIPT-859-OLD",
        "tested_at": "2026-10-22T09:00:00+08:00", "session_url": "https://chat.deepseek.com/a/old",
        "raw_answer": "这是另一个旧尝试的回答，不能错误关联到当前任务的最新执行尝试。",
    }]
    write_json(geo_validation.QUEUE_PATH, {"tasks": tasks})
    write_json(geo_validation.RECEIPTS_PATH, {"receipts": receipts})
    preview = geo_validation.targeted_receipt_reconciliation(task_ids)
    dispositions = {row["task_id"]: row["disposition"] for row in preview["rows"]}
    assert dispositions[task_ids[0]] == "unique_authoritative_receipt", preview
    assert dispositions[task_ids[1]] == "prior_attempt_without_matching_receipt_hold", preview
    assert dispositions[task_ids[2]] == "prior_attempt_without_matching_receipt_hold", preview
    assert not preview["mutated"] and preview["applicable"] == 1, preview
    applied = geo_validation.targeted_receipt_reconciliation(
        task_ids, apply=True, approved_by=geo_validation.CONTROLLER,
    )
    assert applied["reconciled"] == 1 and applied["new_external_requests"] == 0, applied
    after = {row["task_id"]: row for row in geo_validation._load_queue()["tasks"]}
    assert after[task_ids[0]]["state"] == "succeeded", after[task_ids[0]]
    assert after[task_ids[0]]["evidence_id"] == "GEO-RECEIPT-859-1", after[task_ids[0]]
    assert after[task_ids[1]]["state"] == after[task_ids[2]]["state"] == "queued"
    assert Path(applied["backup_path"]).is_file() is False  # relative to data_root, not cwd
    assert (sandbox / "Kazuizhi_AI_Enterprise_V2.0.0_Beta" / "data" / applied["backup_path"]).is_file(), applied

    # Mission continuation remains tied to real pending Asset revisions. B02
    # and B03 are idempotent, and no-new-work preserves the latest batch ID.
    state = seo_geo_growth._load()
    target = next(row for row in state["assets"] if row["id"] == new_asset_id)
    target["stage"] = "PLANNED"
    target["content_revision_id"] = "REV-1"
    seo_geo_growth._save(state)
    today = datetime.now().astimezone().date().isoformat()
    base = [{
        "id": f"base-{index}", "state": "completed", "schedule_date": today,
        "schedule_source": "daily_workforce", "batch_id": f"R7-{today.replace('-', '')}-B01",
        "batch_number": 1, "mission_id": "MISSION-20260924-DF7DB2", "command_id": "CMD-20261019-073EED",
    } for index in range(20)]
    data = {"items": list(base)}
    b2 = daily_workforce._continuation_batch(data, today, datetime.now().astimezone())
    assert b2["batch_number"] == 2 and len(b2["created"]) == 1, b2
    for row in b2["created"]:
        row["state"] = "completed"
    waiting = daily_workforce._continuation_batch(data, today, datetime.now().astimezone())
    assert waiting["reason"] == "no_new_eligible_work" and waiting["batch_number"] == 2, waiting
    state = seo_geo_growth._load()
    next(row for row in state["assets"] if row["id"] == new_asset_id)["content_revision_id"] = "REV-2"
    seo_geo_growth._save(state)
    b3 = daily_workforce._continuation_batch(data, today, datetime.now().astimezone())
    assert b3["batch_number"] == 3 and len(b3["created"]) == 1, b3

    exporter = (ROOT / "04_Build" / "v2" / "Export-Kazuizhi859Diagnostics.ps1").read_text(encoding="utf-8")
    assert "-Method Get" in exporter and "Protect-Value" in exporter
    assert "RECONCILE_EXACT_TASK_RECEIPTS_ONLY" not in exporter
    for forbidden in ("-Method Post", "Invoke-RestMethod", "retry-failed", "/claim", "/receipt"):
        assert forbidden not in exporter, forbidden

    print("PASS #859: new SEO Asset closed loop, exact GEO receipt reconciliation, B02/B03 evidence-qualified continuation")
finally:
    shutil.rmtree(sandbox, ignore_errors=True)
