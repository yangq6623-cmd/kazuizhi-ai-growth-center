import importlib.util
import os
import sys
import tempfile
import types
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))


def load_module(name: str, path: Path):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {path}")
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    return module


pkg = types.ModuleType("integrations")
pkg.__path__ = [str(SOURCE / "integrations")]
sys.modules["integrations"] = pkg
control = load_module("integrations.chatgpt_control", SOURCE / "integrations" / "chatgpt_control.py")
setattr(pkg, "chatgpt_control", control)
bus = load_module("integrations.async_control_bus", SOURCE / "integrations" / "async_control_bus.py")
setattr(pkg, "async_control_bus", bus)


def pack(command_id="CMD-BUS-001", decision_pack_id="DP-BUS-001"):
    now = datetime.now().astimezone()
    return {
        "schema": "kz.decision-pack.v1",
        "command_id": command_id,
        "decision_pack_id": decision_pack_id,
        "issued_at": now.isoformat(timespec="seconds"),
        "valid_until": (now + timedelta(hours=72)).isoformat(timespec="seconds"),
        "source": "chatgpt_personal_chat",
        "decision": {
            "action": "create_mission",
            "region": "涟水县",
            "service": "水电安装维修",
            "title": "涟水县水电维修真实咨询增长",
            "evidence": "老板明确要求重点推广涟水县水电维修并以真实咨询为目标",
            "goal": "获得可追溯的真实咨询",
            "reason": "普通 ChatGPT 一次性形成高层经营决策，本机负责持续执行",
        },
        "autonomy": {
            "allowed": ["content_production", "asset_routing", "technical_qc", "seo_content", "business_monitoring"],
            "human_gates": ["final_video_review", "captcha", "face", "money"],
        },
    }


class FakePrivateBus:
    def __init__(self, payload):
        self.payload = payload
        self.writes = {}

    def ensure_private_repo(self):
        return {"private": True}

    def list_commands(self):
        return [{"name": "CMD-BUS-REMOTE-001.json", "path": "commands/CMD-BUS-REMOTE-001.json"}]

    def read_json(self, path):
        assert path.startswith("commands/")
        return self.payload

    def write_json(self, path, payload, message):
        self.writes[path] = {"payload": payload, "message": message}
        return {"ok": True}


def main() -> None:
    with tempfile.TemporaryDirectory() as temp:
        old_local = os.environ.get("LOCALAPPDATA")
        old_values = {name: os.environ.get(name) for name in (
            "KZ_CONTROL_BUS_REPO", "KZ_CONTROL_BUS_TOKEN", "KZ_CONTROL_BUS_ENABLED"
        )}
        os.environ["LOCALAPPDATA"] = temp
        for name in old_values:
            os.environ.pop(name, None)
        try:
            initial = bus.status()
            assert initial["available"] is True
            assert initial["configured"] is False
            assert initial["local_autonomy"] == "RUNNING"
            assert initial["site_tools_role"] == "optional_realtime_helper"
            assert initial["work_codex_role"] == "engineering_only"
            assert control.control_status()["verified"] is False

            created = bus.process_decision_pack(pack(), source_path="commands/CMD-BUS-001.json")
            assert created["idempotent"] is False
            receipt = created["receipt"]
            assert receipt["status"] == "completed"
            assert receipt["receipt_id"].startswith("RECEIPT-BUS-")
            assert receipt["mission_id"]
            assert receipt["result"]["active_mission"]["region"] == "涟水县"
            assert control.control_status()["verified"] is False, "async bus must not fabricate realtime ChatGPT verification"

            duplicate = bus.process_decision_pack(pack(), source_path="commands/CMD-BUS-001.json")
            assert duplicate["idempotent"] is True
            assert duplicate["receipt"]["receipt_id"] == receipt["receipt_id"]

            changed = pack()
            changed["decision"]["goal"] = "篡改后的目标"
            try:
                bus.process_decision_pack(changed, source_path="commands/CMD-BUS-001.json")
            except ValueError as error:
                assert "重放" in str(error) or "篡改" in str(error)
            else:
                raise AssertionError("changed payload reused the same command id")

            forbidden = pack("CMD-BUS-FORBIDDEN", "DP-BUS-FORBIDDEN")
            forbidden["autonomy"]["allowed"] = ["approve_publish"]
            try:
                bus.validate_decision_pack(forbidden)
            except ValueError as error:
                assert "未授权" in str(error) or "禁止" in str(error)
            else:
                raise AssertionError("final publication capability was accepted")

            remote_payload = pack("CMD-BUS-REMOTE-001", "DP-BUS-REMOTE-001")
            fake = FakePrivateBus(remote_payload)
            synced = bus.sync_once(client=fake)
            assert synced["synced"] is True
            assert "receipts/CMD-BUS-REMOTE-001.json" in fake.writes
            assert "state/system_health.json" in fake.writes
            assert fake.writes["state/system_health.json"]["payload"]["local_autonomy"] == "RUNNING"

            public_client = object.__new__(bus.GitHubControlBusClient)
            public_client.repo = "owner/public"
            public_client.branch = "main"
            public_client.token = "x"
            public_client._request = lambda *args, **kwargs: {"private": False}
            try:
                public_client.ensure_private_repo()
            except ValueError as error:
                assert "PRIVATE" in str(error)
            else:
                raise AssertionError("public repository was accepted as control bus")
        finally:
            if old_local is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = old_local
            for name, value in old_values.items():
                if value is None:
                    os.environ.pop(name, None)
                else:
                    os.environ[name] = value

    print("PASS: normal ChatGPT async Decision Pack -> private control bus -> Mission -> Receipt works without realtime Site Tools.")


if __name__ == "__main__":
    main()
