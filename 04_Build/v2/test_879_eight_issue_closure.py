"""Focused #879 closure tests.

Every ledger is created below a temporary LOCALAPPDATA directory.  The test
performs no browser action, public upload, search submission, paid API call or
production mutation.
"""
from __future__ import annotations

import hashlib
import os
import shutil
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))

sandbox = Path(tempfile.mkdtemp(prefix="kazuizhi-879-closure-"))
old_local = os.environ.get("LOCALAPPDATA")
old_profile = os.environ.get("USERPROFILE")
os.environ["LOCALAPPDATA"] = str(sandbox)
os.environ["USERPROFILE"] = str(sandbox)


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


try:
    from core import autonomous_ops
    from core import geo_phase3_seo_bridge as phase3
    from core import r7_engine
    from core import r8_22_autonomous_convergence as convergence
    from core import r8_23_growth_operating_system as growth_os
    from core import seo_geo_growth
    from core import storage
    from integrations import seo_public_deployer as deployer

    opportunity_id = "KW-879-SHARED"
    asset_id = "SEO-0A6FBE492759"
    action_a = "GEO3-A01-brand_visibility_missing"
    action_b = "GEO-GROWTH-2BD2EDC55B2A"
    public_url = "https://example.invalid/seo/shared-879/"

    state = seo_geo_growth._empty_state()
    state["opportunities"] = [{
        "id": opportunity_id, "region": "涟水县", "service": "家电维修",
        "keyword": "涟水家电维修上门", "intent": "交易", "priority": "S",
        "status": "SUBMITTED", "asset_id": asset_id,
    }]
    state["assets"] = [{
        "id": asset_id, "opportunity_id": opportunity_id, "region": "涟水县",
        "service": "家电维修", "keyword": "涟水家电维修上门",
        "intent": "交易", "priority": "S", "page_type": "service",
        "slug": "shared-879", "stage": "SUBMITTED",
        "public_url": public_url, "canonical": public_url,
        "growth_action_id": action_b, "content_revision_id": action_b,
        "prepared_growth_action_id": action_b, "republish_pending": False,
        "content_refresh_events": [{
            "growth_action_id": action_a, "content_revision_id": action_a,
            "deploy_receipt": "REMOTE-DEPLOY-879-A", "public_url": public_url,
        }, {
            "growth_action_id": action_b, "content_revision_id": action_b,
            "deploy_receipt": "REMOTE-DEPLOY-879-B", "public_url": public_url,
        }],
    }]
    seo_geo_growth._save(state)
    plan = {"actions": [{
        "action_id": action_a, "opportunity_id": opportunity_id,
        "job_state": "completed", "question_id": "GEO50-D04",
        "question_text": "测试共享页面", "decision": "修复品牌可见性",
    }]}
    before = seo_geo_growth._load()["assets"][0]
    for _ in range(4):
        result = phase3.prepare_phase3_assets(plan)
        assert result["refreshed"] == [], result
    after = seo_geo_growth._load()["assets"][0]
    assert after["growth_action_id"] == action_b
    assert after["content_revision_id"] == action_b
    assert after["republish_pending"] is False
    assert after["content_refresh_events"] == before["content_refresh_events"]

    # A stale flag after a crash/race is locally reconciled from the exact
    # verified receipt; the test deliberately provides no upload implementation.
    data = seo_geo_growth._load()
    data["assets"][0]["republish_pending"] = True
    seo_geo_growth._save(data)
    receipt = {
        "receipt_id": "REMOTE-DEPLOY-879-B", "asset_id": asset_id,
        "public_url": public_url, "growth_action_id": action_b,
        "content_revision_id": action_b, "created_at": "2026-10-25T20:18:45+08:00",
        "verification": {"ok": True},
    }
    storage.write_json(deployer.RECEIPTS, {
        "schema": "kz.seo-public-deploy-receipts.v1", "items": [receipt],
    })
    live_asset = seo_geo_growth._load()["assets"][0]
    pending, reconciled = deployer.reconcile_exact_revision_duplicates([live_asset])
    assert pending == []
    assert reconciled[0]["external_request_created"] is False
    assert reconciled[0]["receipt"] == receipt["receipt_id"]
    reconciled_asset = seo_geo_growth._load()["assets"][0]
    assert reconciled_asset["republish_pending"] is False
    assert reconciled_asset["content_refresh_events"] == before["content_refresh_events"]

    # A genuinely different revision remains deployable.
    new_revision = dict(reconciled_asset)
    new_revision["content_revision_id"] = "GEO3-A02-new-valid-revision"
    new_revision["growth_action_id"] = "GEO3-A02-new-valid-revision"
    new_revision["republish_pending"] = True
    pending, reconciled = deployer.reconcile_exact_revision_duplicates([new_revision])
    assert [row["content_revision_id"] for row in pending] == ["GEO3-A02-new-valid-revision"]
    assert reconciled == []

    # GET polling must not compile a Plan, bind jobs or emit a Receipt.
    mission_id = "MISSION-20260924-DF7DB2"
    command_id = "CMD-20261019-073EED"
    storage.write_json(convergence.STATE_FILE, {
        **convergence._default_state(), "active_command_id": command_id,
        "active_mission_id": mission_id, "plan": {"plan_id": "PLAN-D37B40F356"},
    })
    storage.write_json(autonomous_ops.OPS_FILE, {
        "schema": 1, "owner_goal": None, "active_mission_id": mission_id,
        "missions": [{"mission_id": mission_id, "command_id": command_id, "state": "active"}],
        "events": [], "updated_at": "2026-10-25T20:00:00+08:00",
    })
    storage.write_json(r7_engine.JOBS, {"items": []})
    storage.write_json("r7/workforce_schedule.json", {"date": "2026-10-25"})
    state_path = storage.data_root() / convergence.STATE_FILE
    before_hash = digest(state_path)

    old_latest = convergence._latest_authorized_command
    old_human = convergence._human_and_deferred
    old_events = convergence.event_stream
    old_ensure = convergence.ensure_command_mission
    old_bind = convergence.bind_current_jobs
    old_phase = convergence.maybe_phase_receipt
    try:
        convergence._latest_authorized_command = lambda: {"command_id": command_id}
        convergence._human_and_deferred = lambda: ([], [])
        convergence.event_stream = lambda limit=40: []
        convergence.ensure_command_mission = lambda: (_ for _ in ()).throw(AssertionError("GET promoted Mission"))
        convergence.bind_current_jobs = lambda: (_ for _ in ()).throw(AssertionError("GET bound jobs"))
        convergence.maybe_phase_receipt = lambda force=False: (_ for _ in ()).throw(AssertionError("GET emitted Receipt"))
        owner = convergence.read_only_snapshot()
    finally:
        convergence._latest_authorized_command = old_latest
        convergence._human_and_deferred = old_human
        convergence.event_stream = old_events
        convergence.ensure_command_mission = old_ensure
        convergence.bind_current_jobs = old_bind
        convergence.maybe_phase_receipt = old_phase
    assert owner["snapshot_mode"] == "read_only_owner_poll"
    assert owner["mission"]["mission_id"] == mission_id
    assert owner["job_binding"]["read_only"] is True
    assert digest(state_path) == before_hash

    owner_js = (SOURCE / "web" / "r8_23_growth_os.js").read_text(encoding="utf-8")
    for marker in (
        "Promise.allSettled", "if(controlRequest)", "refreshQueued=true",
        "latestGrowth", "latestAutonomy", "CONTROL_CACHE_KEY",
        "保留最近成功数据", "请求超时", "尚无可用的成功快照",
    ):
        assert marker in owner_js, marker
    assert "const [growth, autonomy] = await Promise.all([" not in owner_js
    assert "<h3>运营总览暂不可读</h3>" not in owner_js

    backend = (SOURCE / "backend" / "r8_22_autonomy_convergence_patch.py").read_text(encoding="utf-8")
    assert "handler._json_ok(convergence.read_only_snapshot())" in backend

    social_ids = ("douyin", "wechat_channels", "kuaishou", "xiaohongshu", "bilibili", "weibo")
    old_connectors = growth_os._connector_rows
    old_gpu = growth_os.gpu_status
    try:
        growth_os._connector_rows = lambda: {
            item: {"id": item, "software_route_ready": True, "external_verified": False}
            for item in social_ids
        }
        growth_os.gpu_status = lambda: {"ready": False, "rtx3060": False}
        capabilities = {row["id"]: row for row in growth_os.capability_status()}
        social = capabilities["social_distribution"]
        assert social["ready"] is False
        assert social["registered_routes"] == 6
        assert social["authorized_routes"] == 0
        assert social["state"] == "authorization_required"

        growth_os._connector_rows = lambda: {
            item: {
                "id": item, "software_route_ready": True,
                "external_verified": item == "douyin",
            } for item in social_ids
        }
        social = {row["id"]: row for row in growth_os.capability_status()}["social_distribution"]
        assert social["ready"] is True
        assert social["authorized_routes"] == 1
    finally:
        growth_os._connector_rows = old_connectors
        growth_os.gpu_status = old_gpu

    print("PASS: #879 exact-revision deployment, read-only owner polling and authorization truth")
finally:
    if old_local is None:
        os.environ.pop("LOCALAPPDATA", None)
    else:
        os.environ["LOCALAPPDATA"] = old_local
    if old_profile is None:
        os.environ.pop("USERPROFILE", None)
    else:
        os.environ["USERPROFILE"] = old_profile
    shutil.rmtree(sandbox, ignore_errors=True)
