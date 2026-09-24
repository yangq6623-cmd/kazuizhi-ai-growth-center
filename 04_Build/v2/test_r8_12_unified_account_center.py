from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[2] / "05_V2.0.0_Source"
sys.path.insert(0, str(ROOT))

from core import account_registry as registry
from core import runtime_integrity as integrity
from integrations import account_router
from integrations.oauth_adapters import provider_status
from integrations.credential_vault import status as vault_status


def check_owner_runtime_contract():
    run_text = (ROOT / "run.py").read_text(encoding="utf-8")
    assert "r8_12_account_center_patch" in run_text, "R8-12 backend patch is not installed by the real runtime entry point"

    bridge = (ROOT / "web" / "r8_12_account_center_bridge.js").read_text(encoding="utf-8")
    hotfix = (ROOT / "web" / "r8_11_execution_tab_hotfix.js").read_text(encoding="utf-8")
    assert "window.addEventListener('click'" in bridge, "R8-12 account route must capture on window before the R8-11 document capture handler"
    assert "button.dataset.executionPage==='accounts'" in bridge
    assert "/r8_12_account_center.html?embed=1" in bridge
    assert "stopImmediatePropagation" in bridge
    assert "document.addEventListener('click'" in hotfix, "test contract changed: R8-11 execution router is expected to capture on document"

    memory = (ROOT / "web" / "memory.js").read_text(encoding="utf-8")
    coordinator = (ROOT / "web" / "r8_12_startup_coordinator.js").read_text(encoding="utf-8")
    assert "/r8_12_startup_coordinator.js" in memory, "owner overlays must load through the single R8-12.1 startup coordinator"
    assert "/r8_10_workbench.js" not in memory, "memory.js must not race the coordinator with a direct R8-10 loader"
    assert "/r8_10_truth_convergence.js" not in memory, "truth convergence must be sequenced by the coordinator"
    for token in (
        "SCRIPT_SEQUENCE",
        "/r8_10_workbench.js",
        "/r8_10_truth_convergence.js",
        "/r8_11_backbone_ui.js",
        "/r8_12_account_center_bridge.js",
        "FiniteStartupObserver",
        "dedupeGeneratedSingletons",
        "forceInitialDashboardOnce",
        "r810:workbench-ready",
        "kz:app-ready",
    ):
        assert token in coordinator, f"startup convergence contract missing: {token}"


def check_same_growth_mission_identity_guard():
    identity_store = {
        integrity.CHECKPOINT_PATH: {
            "schema": integrity.SCHEMA,
            "saved_at": "2026-09-24T12:00:00+08:00",
            "mission_id": "MISSION-STABLE-001",
            "growth_id": "KZ-STABLE-001",
            "mission": {"mission_id": "MISSION-STABLE-001", "growth_id": "KZ-STABLE-001"},
            "campaigns": [],
            "videos": [],
            "publication_plans": [],
            "receipts": [],
        }
    }

    def fake_read(path, default=None):
        value = identity_store.get(path, default)
        return json.loads(json.dumps(value, ensure_ascii=False)) if value is not None else None

    def fake_write(path, value):
        identity_store[path] = json.loads(json.dumps(value, ensure_ascii=False))
        return value

    original_read, original_write, original_bundle = integrity.read_json, integrity.write_json, integrity._bundle
    try:
        integrity.read_json = fake_read
        integrity.write_json = fake_write
        integrity._bundle = lambda: {
            "schema": integrity.SCHEMA,
            "saved_at": "2026-09-24T12:01:00+08:00",
            "mission_id": "MISSION-DRIFT-999",
            "growth_id": "KZ-STABLE-001",
            "mission": {"mission_id": "MISSION-DRIFT-999", "growth_id": "KZ-STABLE-001"},
            "campaigns": [],
            "videos": [],
            "publication_plans": [],
            "receipts": [],
        }
        result = integrity.checkpoint_runtime("cold_start")
        assert result["saved"] is False
        assert result["reason"] == "same_growth_mission_identity_drift"
        assert identity_store[integrity.CHECKPOINT_PATH]["mission_id"] == "MISSION-STABLE-001"
        audit = identity_store.get(integrity.AUDIT_PATH, {})
        assert audit.get("events", [])[0]["kind"] == "mission_identity_drift_blocked"
    finally:
        integrity.read_json, integrity.write_json, integrity._bundle = original_read, original_write, original_bundle

    integrity_text = (ROOT / "core" / "runtime_integrity.py").read_text(encoding="utf-8")
    assert "deduped_same_growth_missions" in integrity_text
    assert "mission_identity_drift_blocked" in integrity_text


def main():
    store = {}

    def fake_read(path, default=None):
        value = store.get(path, default)
        return json.loads(json.dumps(value, ensure_ascii=False)) if value is not None else None

    def fake_write(path, value):
        store[path] = json.loads(json.dumps(value, ensure_ascii=False))
        return value

    registry.read_json = fake_read
    registry.write_json = fake_write
    registry.r8_control.control_status = lambda: {
        "devices": [{
            "device_id": "ELE-AL00",
            "label": "ELE-AL00",
            "connection": "connected",
            "health": "normal",
            "probe_source": "adb",
            "last_seen_at": "2026-09-24T12:00:00+08:00",
        }],
        "accounts": [{
            "account_id": "douyin:ELE-AL00:1",
            "platform": "douyin",
            "platform_name": "抖音",
            "device_id": "ELE-AL00",
            "alias": "卡嘴子本地服务维修",
            "label": "卡嘴子本地服务维修",
            "login_status": "authorized",
            "login_verified_at": "2026-09-24T12:00:00+08:00",
            "region": "涟水县",
            "service_category": "水电安装维修",
        }],
    }

    snap = registry.migrate_legacy_assets()
    assert snap["summary"]["accounts"] == 1
    assert snap["summary"]["connected_accounts"] == 1
    account = snap["accounts"][0]
    assert account["account_id"].startswith("ACC-DY-")
    assert account["account_id"] != "douyin:ELE-AL00:1"
    assert "douyin:ELE-AL00:1" in account["legacy_account_ids"]
    assert account["service_scope"]["all_local_services"] is True
    assert account["region_scope"]["regions"] == ["涟水县"]
    assert account["preferred_device_id"] == "DEV-ELE-AL00"

    raw = store[registry.REGISTRY_PATH]
    serialized = json.dumps(raw, ensure_ascii=False).lower()
    for forbidden in ("access_token", "refresh_token", "client_secret", "password"):
        assert forbidden not in serialized

    account_router.snapshot = lambda: snap
    route = account_router.route_account(platform="douyin", region="涟水县", service="家电安装维修")
    assert route["status"] == "ready"
    assert route["account"]["account_id"] == account["account_id"]
    assert route["device"]["device_id"] == "DEV-ELE-AL00"

    oauth = provider_status("douyin")
    assert "configured" in oauth
    assert oauth["truth"].startswith("未申请或未配置官方应用凭据")
    vault = vault_status()
    assert vault["secrets_in_registry"] is False
    assert vault["secrets_in_github"] is False

    check_owner_runtime_contract()
    check_same_growth_mission_identity_guard()
    print("R8-12 unified account center + startup convergence regression passed")


if __name__ == "__main__":
    main()
