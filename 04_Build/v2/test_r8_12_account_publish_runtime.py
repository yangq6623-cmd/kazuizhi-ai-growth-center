"""R8-23 regression: durable account -> PC browser QR route -> receipt-gated plan."""
from __future__ import annotations

import copy
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))


def check_mobile_retirement():
    from core import account_registry as registry

    store = {}
    original_read, original_write = registry.read_json, registry.write_json
    try:
        registry.read_json = lambda path, default=None: copy.deepcopy(store.get(path, default))
        registry.write_json = lambda path, value: store.__setitem__(path, copy.deepcopy(value)) or value
        store[registry.REGISTRY_PATH] = {
            "schema": registry.SCHEMA,
            "accounts": [{"account_id": "ACC-DY-001", "preferred_device_id": "DEV-OLD", "auth": {"status": "connected", "method": "real_device_verified"}}],
        }
        store[registry.DEVICE_PATH] = {"schema": registry.DEVICE_SCHEMA, "devices": [{"device_id": "DEV-OLD"}]}
        result = registry.retire_mobile_runtime()
        assert result["retired"] is True and result["removed_device_bindings"] == 1
        snapshot = registry.snapshot(skip_migration=True)
        assert snapshot["devices"] == []
        account = snapshot["accounts"][0]
        assert account["preferred_device_id"] is None
        assert account["auth_method"] == "desktop_browser_qr_required"
        assert snapshot["summary"]["mobile_runtime_retired"] is True
    finally:
        registry.read_json, registry.write_json = original_read, original_write


def check_router():
    from integrations import account_router as router

    original_snapshot, original_provider, original_browser, original_environment = router.snapshot, router.provider_status, router.browser_session_ready, router.routing_allowed
    try:
        account = {
            "account_id": "ACC-DY-001", "platform": "douyin", "display_name": "卡嘴子本地服务维修",
            "auth_status": "connected", "authorized_scopes": [],
            "service_scope": {"all_local_services": True, "services": []},
            "region_scope": {"all_regions": False, "regions": ["涟水县"]},
        }
        router.snapshot = lambda: {"accounts": [copy.deepcopy(account)], "devices": []}
        router.provider_status = lambda platform: {"platform": platform, "configured": False}
        router.routing_allowed = lambda account_id: {"allowed": True, "risk_level": "low"}
        router.browser_session_ready = lambda account_id: False
        waiting = router.route_account(platform="抖音", region="涟水县", service="家电安装维修")
        assert waiting["status"] == "needs_browser_login" and waiting["route_kind"] == "desktop_browser_qr"
        router.browser_session_ready = lambda account_id: True
        ready = router.route_account(platform="douyin", region="涟水县", service="水电安装维修")
        assert ready["status"] == "ready" and ready["route_kind"] == "desktop_browser" and ready["device"] is None
        api_account = copy.deepcopy(account); api_account["authorized_scopes"] = ["user_video_publish"]
        router.snapshot = lambda: {"accounts": [api_account], "devices": []}
        router.provider_status = lambda platform: {"platform": platform, "configured": True}
        assert router.route_account(platform="douyin")["route_kind"] == "official_api"
    finally:
        router.snapshot, router.provider_status, router.browser_session_ready, router.routing_allowed = original_snapshot, original_provider, original_browser, original_environment


def check_publish_planner():
    from promotion import content_factory as cf
    from promotion import publish_orchestrator as planner

    state = {"campaigns": [{"id": "KZ-001", "region": "涟水县", "service": "水电安装维修", "title": "本地服务"}], "videos": [{"id": "VIDEO-001", "campaign_id": "KZ-001", "approved_at": "2026-09-24T10:00:00+08:00", "review": {"decision": "确认发布"}, "target_platforms": ["抖音"], "production_plan": {"titles": ["涟水水电维修需求这样发"], "target_platforms": ["抖音"]}, "caption_direction": "说明问题后提交需求", "cta": "通过小程序提交需求"}], "publication_plans": [], "receipts": []}
    original_load, original_save, original_route = cf._load, cf._save, planner.route_account
    try:
        cf._load = lambda: copy.deepcopy(state)
        def save(value): state.clear(); state.update(copy.deepcopy(value)); return value
        cf._save = save
        planner.route_account = lambda **kwargs: {"status": "needs_browser_login", "owner_status": "需PC扫码登录", "route_kind": "desktop_browser_qr", "account_id": "ACC-DY-001", "account": {"account_id": "ACC-DY-001", "platform": "douyin"}}
        first = planner.run_publish_planning(limit=10)
        assert first["processed"] == 1 and len(state["publication_plans"]) == 1
        plan = state["publication_plans"][0]
        assert plan["status"] == "等待PC扫码登录" and plan["device_asset_id"] is None
        planner.route_account = lambda **kwargs: {"status": "ready", "owner_status": "已连接", "route_kind": "desktop_browser", "account_id": "ACC-DY-001", "account": {"account_id": "ACC-DY-001", "platform": "douyin"}}
        second = planner.run_publish_planning(limit=10)
        assert second["processed"] == 1 and len(state["publication_plans"]) == 1
        assert state["publication_plans"][0]["status"] == "等待最佳时间"
    finally:
        cf._load, cf._save, planner.route_account = original_load, original_save, original_route


def main():
    check_mobile_retirement(); check_router(); check_publish_planner()
    print("R8-23 PC browser QR runtime regression passed: no phone/ADB route, durable identity, receipt-gated plan.")


if __name__ == "__main__":
    main()
