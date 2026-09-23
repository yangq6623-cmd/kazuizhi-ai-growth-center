import os
import sys
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))

from integrations import async_control_bus as bus
from integrations import channel_registry
from core import mission_ledger


class FakePrivateBus:
    def __init__(self):
        self.writes = {}

    def ensure_private_repo(self):
        return {"private": True}

    def write_json(self, path, payload, message):
        self.writes[path] = {"payload": payload, "message": message}
        return {"ok": True}


def decision_pack():
    now = datetime.now().astimezone()
    return {
        "schema": "kz.decision-pack.v1",
        "command_id": "CMD-R811-BACKBONE-001",
        "decision_pack_id": "DP-R811-BACKBONE-001",
        "issued_at": now.isoformat(timespec="seconds"),
        "valid_until": (now + timedelta(hours=24)).isoformat(timespec="seconds"),
        "source": "chatgpt_personal_chat",
        "decision": {
            "action": "create_mission",
            "region": "涟水县",
            "service": "水电安装维修",
            "title": "R8-11 全链路 Mission 验证",
            "evidence": "验证 Command 到 Mission、执行、渠道和回流账本的可追溯性",
            "goal": "形成可追溯的真实推广闭环",
            "reason": "R8-11 主链测试",
        },
        "autonomy": {
            "allowed": ["content_production", "asset_routing", "technical_qc", "seo_content", "geo_content", "data_collection", "business_monitoring"],
            "human_gates": ["final_video_review", "manual_verification", "money"],
        },
    }


def main():
    with tempfile.TemporaryDirectory() as temp:
        old_local = os.environ.get("LOCALAPPDATA")
        old_env = {name: os.environ.get(name) for name in ("KZ_CONTROL_BUS_REPO", "KZ_CONTROL_BUS_TOKEN", "KZ_CONTROL_BUS_ENABLED")}
        os.environ["LOCALAPPDATA"] = temp
        for name in old_env:
            os.environ.pop(name, None)
        try:
            result = bus.process_decision_pack(decision_pack(), source_path="commands/CMD-R811-BACKBONE-001.json")
            receipt = result["receipt"]
            assert receipt["status"] == "completed"
            assert receipt["mission_id"]

            ledger = mission_ledger.snapshot()
            active = ledger["active_mission"]
            assert ledger["schema"] == "kz.mission-ledger.v1"
            assert active["mission_id"] == receipt["mission_id"]
            assert active["growth_id"]
            assert active["command"]["command_id"] == "CMD-R811-BACKBONE-001"
            assert active["command"]["decision_pack_id"] == "DP-R811-BACKBONE-001"
            assert active["children"]["video_ids"], "Mission must expose its real execution child"
            assert active["verified_publications"] == 0
            assert active["latest_platform_receipt"] is None
            assert "真实" in active["truth"]

            registry = channel_registry.snapshot()
            ids = {row["id"] for row in registry["channels"]}
            for required in ("douyin", "wechat_channels", "xiaohongshu", "kuaishou", "baidu_search", "maps_local", "forum", "website", "mini_program"):
                assert required in ids
            assert registry["summary"]["paid_token_required"] == 0
            assert registry["policy"]["no_paid_third_party_token_required"] is True
            assert all(row["paid_token_required"] is False for row in registry["channels"])
            douyin = next(row for row in registry["channels"] if row["id"] == "douyin")
            assert douyin["software_route_ready"] is True
            assert douyin["execution"] == "ADB real-device serial execution"
            assert douyin["external_verified"] is False, "software routing must not impersonate real account/device verification"

            fake = FakePrivateBus()
            backflow = mission_ledger.export_to_control_bus(client=fake)
            assert backflow["exported"] is True
            assert "state/mission_ledger.json" in fake.writes
            assert "state/channel_registry.json" in fake.writes
            mission_path = f"state/missions/{receipt['mission_id']}.json"
            assert mission_path in fake.writes
            exported = fake.writes[mission_path]["payload"]
            assert exported["command"]["command_id"] == "CMD-R811-BACKBONE-001"
            assert exported["verified_publications"] == 0
            assert exported["next_action"]
        finally:
            if old_local is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = old_local
            for name, value in old_env.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

    print("PASS: R8-11 Command -> Mission ledger -> channel registry -> private Control Bus backflow works without paid third-party tokens.")


if __name__ == "__main__":
    main()
