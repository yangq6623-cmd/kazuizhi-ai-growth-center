"""R8-12 regression: durable account -> route -> plan -> dry-run -> recovery."""
from __future__ import annotations

import copy
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))


def check_account_registry():
    from core import account_registry as registry

    store = {}
    original_read, original_write = registry.read_json, registry.write_json
    original_status = registry.r8_control.control_status
    try:
        registry.read_json = lambda path, default=None: copy.deepcopy(store.get(path, default))
        registry.write_json = lambda path, value: store.__setitem__(path, copy.deepcopy(value)) or value
        state = {
            "devices": [{"device_id": "ELE-AL00", "label": "ELE-AL00", "connection": "connected", "health": "normal", "probe_source": "adb"}],
            "accounts": [{
                "account_id": "LEGACY-DY-1", "platform": "douyin", "platform_name": "抖音",
                "alias": "卡嘴子本地服务维修", "login_status": "authorized",
                "login_verified_at": "2026-09-24T10:00:00+08:00", "region": "涟水县",
                "service_category": "水电安装维修", "device_id": "ELE-AL00",
            }],
        }
        registry.r8_control.control_status = lambda: copy.deepcopy(state)
        first = registry.migrate_legacy_assets()
        assert first["summary"]["accounts"] == 1
        account = first["accounts"][0]
        account_id = account["account_id"]
        assert account_id.startswith("ACC-DY-")
        assert account["auth_status"] == "connected"
        assert account["service_scope"]["all_local_services"] is True
        assert account["preferred_device_id"] == "DEV-ELE-AL00"

        # A stale old UI/probe cannot downgrade the durable connected identity.
        state["accounts"][0]["login_status"] = "not_verified"
        state["accounts"][0]["service_category"] = "家电安装维修"
        second = registry.migrate_legacy_assets()
        assert second["accounts"][0]["account_id"] == account_id
        assert second["accounts"][0]["auth_status"] == "connected"
        assert second["accounts"][0]["service_scope"]["all_local_services"] is True

        # Authorization expiry changes authorization only, never account identity.
        expired = registry.set_auth_state(account_id, "needs_authorization", method="oauth")
        assert expired["account_id"] == account_id
        assert expired["auth_status"] == "needs_authorization"

        # Restore the same identity after a partial/empty registry corruption.
        store[registry.REGISTRY_PATH]["accounts"] = []
        recovered = registry.recover_assets_if_degraded()
        assert recovered["restored"] is True
        after = registry.snapshot(skip_migration=True)
        assert after["accounts"][0]["account_id"] == account_id
    finally:
        registry.read_json, registry.write_json = original_read, original_write
        registry.r8_control.control_status = original_status


def check_router():
    from integrations import account_router as router

    original_snapshot, original_provider = router.snapshot, router.provider_status
    try:
        base_account = {
            "account_id": "ACC-DY-001", "platform": "douyin", "display_name": "卡嘴子本地服务维修",
            "auth_status": "connected", "authorized_scopes": [],
            "service_scope": {"all_local_services": True, "services": []},
            "region_scope": {"all_regions": False, "regions": ["涟水县"]},
            "preferred_device_id": "DEV-ELE-AL00", "updated_at": "2026-09-24T10:00:00+08:00",
        }
        device = {"device_id": "DEV-ELE-AL00", "legacy_device_id": "ELE-AL00", "connection": "connected", "health": "normal"}
        router.snapshot = lambda: {"accounts": [copy.deepcopy(base_account)], "devices": [copy.deepcopy(device)]}
        router.provider_status = lambda platform: {"platform": platform, "configured": False}
        routed = router.route_account(platform="抖音", region="涟水县", service="家电安装维修")
        assert routed["status"] == "ready" and routed["route_kind"] == "real_device"
        assert routed["account_id"] == "ACC-DY-001"

        # Official API is only preferred after a real publish scope was recorded.
        api_account = copy.deepcopy(base_account)
        api_account["authorized_scopes"] = ["user_video_publish"]
        router.snapshot = lambda: {"accounts": [copy.deepcopy(api_account)], "devices": []}
        router.provider_status = lambda platform: {"platform": platform, "configured": True}
        routed = router.route_account(platform="douyin", region="涟水县", service="水电安装维修")
        assert routed["route_kind"] == "official_api"

        # Configured app without real publish scope is not enough to claim API readiness.
        no_scope = copy.deepcopy(base_account)
        router.snapshot = lambda: {"accounts": [copy.deepcopy(no_scope)], "devices": []}
        routed = router.route_account(platform="douyin", region="涟水县", service="水电安装维修")
        assert routed["status"] == "device_offline"
    finally:
        router.snapshot, router.provider_status = original_snapshot, original_provider


def check_publish_planner():
    from promotion import content_factory as cf
    from promotion import publish_orchestrator as planner

    state = {
        "campaigns": [{"id": "KZ-001", "region": "涟水县", "service": "水电安装维修", "title": "涟水水电维修怎么发布需求", "goal": "真实咨询"}],
        "videos": [{
            "id": "VIDEO-001", "campaign_id": "KZ-001", "status": "已授权发布",
            "approved_at": "2026-09-24T10:00:00+08:00", "review": {"decision": "确认发布"},
            "target_platforms": ["抖音"], "production_plan": {"titles": ["涟水水电维修需求这样发"], "target_platforms": ["抖音"]},
            "caption_direction": "说明问题后提交需求", "cta": "通过小程序提交需求",
        }],
        "publication_plans": [], "receipts": [],
    }
    original_load, original_save = cf._load, cf._save
    original_route, original_queue = planner.route_account, planner.publish_dry_run_queue.queue_plan
    try:
        cf._load = lambda: copy.deepcopy(state)
        def save(value):
            state.clear(); state.update(copy.deepcopy(value)); return value
        cf._save = save
        planner.route_account = lambda **kwargs: {
            "status": "ready", "owner_status": "已连接", "route_kind": "real_device",
            "account_id": "ACC-DY-001", "device_id": "DEV-ELE-AL00",
            "account": {"account_id": "ACC-DY-001", "platform": "douyin"},
            "device": {"device_id": "DEV-ELE-AL00", "legacy_device_id": "ELE-AL00", "connection": "connected", "health": "normal"},
        }
        planner.publish_dry_run_queue.queue_plan = lambda plan, route, video: {"queued": True, "task": {"task_id": f"DRYRUN-{plan['id']}"}, "publishes_content": False}
        first = planner.run_publish_planning(limit=10)
        assert first["processed"] == 1
        assert len(state["publication_plans"]) == 1
        plan = state["publication_plans"][0]
        assert plan["account_id"] == "ACC-DY-001"
        assert plan["route_kind"] == "real_device"
        assert plan["device_asset_id"] == "DEV-ELE-AL00"
        assert plan["status"] == "等待最佳时间"

        second = planner.run_publish_planning(limit=10)
        assert second["processed"] == 1
        assert len(state["publication_plans"]) == 1, "scheduler retry created a duplicate plan"
    finally:
        cf._load, cf._save = original_load, original_save
        planner.route_account, planner.publish_dry_run_queue.queue_plan = original_route, original_queue


def check_dry_run():
    from integrations import publish_dry_run_queue as queue

    runtime = {"devices": {}}
    original_read, original_write = queue.read_json, queue.write_json
    original_scan = queue.android_device.scan_and_sync
    original_audit = getattr(queue.android_device, "_append_audit", None)
    try:
        queue.read_json = lambda path, default=None: copy.deepcopy(runtime)
        def write(path, value):
            runtime.clear(); runtime.update(copy.deepcopy(value)); return value
        queue.write_json = write
        queue.android_device.scan_and_sync = lambda: {"devices": [{"device_id": "ELE-AL00", "connected": True}]}
        queue.android_device._append_audit = lambda event: None
        plan = {"id": "PLAN-001", "video_id": "VIDEO-001", "campaign_id": "KZ-001", "account_id": "ACC-DY-001", "platform_code": "douyin", "device_asset_id": "DEV-ELE-AL00"}
        route = {
            "status": "ready", "route_kind": "real_device", "account_id": "ACC-DY-001",
            "account": {"account_id": "ACC-DY-001", "platform": "douyin"},
            "device": {"device_id": "DEV-ELE-AL00", "legacy_device_id": "ELE-AL00", "connection": "connected"},
        }
        result = queue.queue_plan(plan, route, {"id": "VIDEO-001", "campaign_id": "KZ-001"})
        assert result["queued"] is True
        task = runtime["devices"]["ELE-AL00"]["current_task"]
        assert task["account_asset_id"] == "ACC-DY-001"
        assert task["device_asset_id"] == "DEV-ELE-AL00"
        assert task["adb_device_id"] == "ELE-AL00"
        assert task["final_publish_allowed"] is False and task["publishes_content"] is False
    finally:
        queue.read_json, queue.write_json = original_read, original_write
        queue.android_device.scan_and_sync = original_scan
        if original_audit is not None: queue.android_device._append_audit = original_audit


def check_runtime_recovery():
    from core import runtime_integrity as integrity
    from promotion import content_factory as cf

    store = {}
    with tempfile.TemporaryDirectory() as tmp:
        final_mp4 = Path(tmp) / "FINAL.mp4"; final_mp4.write_bytes(b"truthful-local-media")
        factory = {
            "active_campaign_id": "KZ-001",
            "campaigns": [{"id": "KZ-001", "region": "涟水县", "service": "水电安装维修"}],
            "videos": [{
                "id": "VIDEO-001", "campaign_id": "KZ-001", "status": "等待最佳时间",
                "approved_at": "2026-09-24T10:00:00+08:00", "review": {"decision": "确认发布"},
                "candidates": [{"id": "CUT-001", "local_path": str(final_mp4), "exists": True}],
            }],
            "publication_plans": [{"id": "PLAN-001", "campaign_id": "KZ-001", "video_id": "VIDEO-001", "account_id": "ACC-DY-001", "status": "等待最佳时间"}],
            "receipts": [],
        }
        ops = {"active_mission_id": "MISSION-OLD", "missions": [{"mission_id": "MISSION-OLD", "growth_id": "KZ-001", "state": "active"}]}
        original_read, original_write = integrity.read_json, integrity.write_json
        original_load, original_save = cf._load, cf._save
        try:
            def read(path, default=None):
                if path == "ops/autonomous_ops.json": return copy.deepcopy(ops)
                return copy.deepcopy(store.get(path, default))
            def write(path, value):
                if path == "ops/autonomous_ops.json":
                    ops.clear(); ops.update(copy.deepcopy(value))
                else: store[path] = copy.deepcopy(value)
                return value
            integrity.read_json, integrity.write_json = read, write
            cf._load = lambda: copy.deepcopy(factory)
            def save(value): factory.clear(); factory.update(copy.deepcopy(value)); return value
            cf._save = save
            saved = integrity.checkpoint_runtime("test")
            assert saved["saved"] is True

            # Simulate an upgrade producing the same Growth with a new Mission ID
            # while losing video/plan children.
            factory["videos"] = []; factory["publication_plans"] = []
            ops["missions"] = [{"mission_id": "MISSION-DRIFT", "growth_id": "KZ-001", "state": "active"}]
            ops["active_mission_id"] = "MISSION-DRIFT"
            recovered = integrity.recover_runtime_if_degraded()
            assert recovered["restored"] is True
            assert any(x["id"] == "VIDEO-001" for x in factory["videos"])
            assert any(x["id"] == "PLAN-001" for x in factory["publication_plans"])
            assert ops["active_mission_id"] == "MISSION-OLD"
        finally:
            integrity.read_json, integrity.write_json = original_read, original_write
            cf._load, cf._save = original_load, original_save


def main():
    check_account_registry()
    check_router()
    check_publish_planner()
    check_dry_run()
    check_runtime_recovery()
    print("R8-12 account/publish runtime regression passed: durable identity, route, idempotent plan, truthful dry-run and partial recovery.")


if __name__ == "__main__":
    main()
