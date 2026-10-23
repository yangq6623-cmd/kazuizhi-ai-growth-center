"""#862 isolated regression for control-bus truth and large R7 owner reads.

Synthetic LOCALAPPDATA only. No browser action, external Decision Pack,
production ledger mutation, publishing, search submission or paid API call.
"""
from __future__ import annotations

import json
import os
import sys
import tempfile
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))

from core import r7_engine  # noqa: E402
from integrations import async_control_bus as bus  # noqa: E402
from integrations import bridge  # noqa: E402


def decision_pack(command_id: str) -> dict:
    now = datetime.now().astimezone()
    return {
        "schema": "kz.decision-pack.v1",
        "command_id": command_id,
        "decision_pack_id": "DP-" + command_id.removeprefix("CMD-"),
        "issued_at": now.isoformat(timespec="seconds"),
        "valid_until": (now + timedelta(hours=2)).isoformat(timespec="seconds"),
        "decision": {
            "action": "create_mission",
            "region": "涟水县",
            "service": "水电安装维修",
            "title": "隔离环境控制总线测试",
            "evidence": "仅验证本地安全链路，不产生任何外部动作",
            "goal": "验证 Decision Pack 与 Receipt 身份一致",
            "reason": "隔离环境验证低风险 Decision Pack 幂等与回执时间语义",
        },
        "autonomy": {"allowed": ["technical_qc", "data_collection"]},
    }


class SuccessfulBus:
    def __init__(self, payload: dict):
        self.payload = payload
        self.writes = {}

    def ensure_private_repo(self):
        return {"private": True}

    def list_commands(self):
        return [{"name": "one.json", "path": "commands/one.json"}]

    def read_json(self, _path):
        return self.payload

    def write_json(self, path, payload, _message):
        self.writes[path] = payload
        return {"ok": True}


class FailedBus(SuccessfulBus):
    def ensure_private_repo(self):
        raise RuntimeError("isolated_transport_failure")


def write_large_r7_ledger() -> None:
    path = r7_engine.data_root() / r7_engine.JOBS
    path.parent.mkdir(parents=True, exist_ok=True)
    items = []
    for index in range(1205):
        items.append({
            "id": f"R7-SYNTH-{index:05d}",
            "title": f"隔离读取任务 {index}",
            "state": "completed" if index % 3 else "queued",
            "mode": "local",
            "progress": 100 if index % 3 else 0,
            "created_at": "2026-10-23T00:00:00+08:00",
            "updated_at": "2026-10-23T00:00:00+08:00",
        })
    path.write_text(json.dumps({"schema": 1, "items": items}, ensure_ascii=False), encoding="utf-8")


def main() -> None:
    previous = os.environ.get("LOCALAPPDATA")
    with tempfile.TemporaryDirectory(prefix="kz-862-") as temp:
        os.environ["LOCALAPPDATA"] = temp
        try:
            payload = decision_pack("CMD-ISOLATED-862")
            first = bus.sync_once(SuccessfulBus(payload))
            assert first["synced"] is True
            successful = bus.status()
            assert successful["last_success_at"]
            assert successful["last_attempt_at"]
            last_success = successful["last_success_at"]

            failed = bus.sync_once(FailedBus(payload))
            assert failed["synced"] is False
            after_failure = bus.status()
            assert after_failure["last_success_at"] == last_success
            assert after_failure["last_attempt_at"]
            assert "isolated_transport_failure" in after_failure["last_error"]

            inbox = Path(temp) / "bridge" / "inbox"
            inbox.mkdir(parents=True)
            (inbox / "CMD-PENDING-862.json").write_text(json.dumps({
                "id": "CMD-PENDING-862", "kind": "manual_task",
                "title": "只读检查，不自动导入", "due_at": "",
            }, ensure_ascii=False), encoding="utf-8")
            preview = bridge._pending_preview(Path(temp) / "bridge")
            assert preview == [{
                "command_id": "CMD-PENDING-862", "source_file": "CMD-PENDING-862.json",
                "kind": "manual_task", "title": "只读检查，不自动导入",
                "due_at": "", "status": "pending_import",
            }]
            assert bridge.list_bridge_commands()["count"] == 0, "preview must not import"

            write_large_r7_ledger()
            started = time.perf_counter()
            with ThreadPoolExecutor(max_workers=8) as pool:
                snapshots = list(pool.map(lambda _i: r7_engine.ui_snapshot(), range(64)))
            elapsed = time.perf_counter() - started
            assert elapsed < 15, f"64 concurrent snapshots took {elapsed:.2f}s"
            assert all(row["jobs"]["ledger_count"] == 1205 for row in snapshots)
            assert all(len(row["jobs"]["items"]) == 200 for row in snapshots)
            assert all(row["engine"]["ledger_total"] == 1205 for row in snapshots)
            assert all(row["audit"]["integrity"] == "verified" for row in snapshots)

            r7_js = (SOURCE / "web" / "r7.js").read_text(encoding="utf-8")
            bridge_js = (SOURCE / "web" / "r7_bridge_usability_patch.js").read_text(encoding="utf-8")
            assert "await r7Api('/api/r7/ui-snapshot')" in r7_js
            assert "Promise.all([r7Api('/api/r7/jobs')" not in r7_js
            assert "只读查看" in bridge_js
            command_block = bridge_js.split("if (action === 'commands')", 1)[1].split("if (action === 'offline')", 1)[0]
            assert "syncWithRecovery" not in command_block
        finally:
            if previous is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = previous

    print("PASS: async sync timestamps, read-only pending preview and 1205-row concurrent R7 snapshot are truthful and bounded.")


if __name__ == "__main__":
    main()
