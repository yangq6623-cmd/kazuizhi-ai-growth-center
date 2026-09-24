from pathlib import Path
import json
import sys

ROOT = Path(__file__).resolve().parents[2] / "05_V2.0.0_Source"
sys.path.insert(0, str(ROOT))

from core import account_registry as registry
from integrations import account_router
from integrations.oauth_adapters import provider_status
from integrations.credential_vault import status as vault_status


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

    print("R8-12 unified account center regression passed")


if __name__ == "__main__":
    main()
