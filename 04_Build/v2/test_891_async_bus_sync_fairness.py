"""Isolated sync contract: no imports, credentials, network or production ledger."""
import ast
import json
from pathlib import Path


SOURCE = Path(__file__).resolve().parents[2] / "05_V2.0.0_Source" / "integrations" / "async_control_bus.py"
root = ast.parse(SOURCE.read_text(encoding="utf-8"), filename=str(SOURCE))
function = next(node for node in root.body if isinstance(node, ast.FunctionDef) and node.name == "sync_once")


class Client:
    def __init__(self, fail_health=False, fail_receipt_once=False):
        self.fail_health = fail_health
        self.fail_receipt_once = fail_receipt_once
        self.receipts = []

    def ensure_private_repo(self):
        return {"private": True}

    def list_commands(self):
        return [{"name": f"CMD-{i:03}.json", "path": f"commands/CMD-{i:03}.json"} for i in range(21)]

    def read_json(self, path):
        return {"command_id": path.split("/")[-1][:-5]}

    def write_json(self, path, payload, message):
        if self.fail_health and path == "state/system_health.json":
            raise OSError("offline")
        if path.startswith("receipts/"):
            if self.fail_receipt_once:
                self.fail_receipt_once = False
                raise OSError("offline before receipt acknowledgement")
            self.receipts.append(path)
        return {"ok": True}


def verify(fail_health=False, fail_receipt_once=False):
    ledger = {}
    client = Client(fail_health, fail_receipt_once)
    applied = set()

    def process(payload, source_path):
        identifier = payload["command_id"]
        duplicate = identifier in applied
        if not duplicate:
            ledger["last_command_id"] = identifier
            applied.add(identifier)
        return {"idempotent": duplicate, "receipt": {
            "command_id": identifier, "receipt_id": "RECEIPT-" + identifier, "status": "completed"
        }}

    scope = {
        "GitHubControlBusClient": Client,
        "_client_from_config": lambda: client,
        "STATE_FILE": "state", "MAX_COMMANDS_PER_SYNC": 20,
        "read_json": lambda _path, _default: dict(ledger),
        "write_json": lambda _path, value: ledger.clear() or ledger.update(value),
        "process_decision_pack": process,
        "now_iso": lambda: "2026-11-01T00:00:00+08:00",
        "status": lambda: dict(ledger),
        "json": json,
    }
    exec(compile(ast.Module(body=[function], type_ignores=[]), str(SOURCE), "exec"), scope)
    result = scope["sync_once"](client)
    if fail_receipt_once:
        assert not result["synced"]
        assert "last_processed_command_path" not in ledger, "Cursor advanced before receipt acknowledgement"
        retry = scope["sync_once"](client)
        assert retry["synced"]
        assert "receipts/CMD-000.json" in client.receipts
        assert retry["processed"][0]["idempotent"] is True, "External failure reapplied a local Command"
    elif fail_health:
        assert not result["synced"]
        assert "last_success_at" not in ledger, "Failed remote state write was falsely marked successful"
    else:
        assert result["synced"]
        assert "receipts/CMD-000.json" in client.receipts, "Oldest pending command was starved"
        scope["sync_once"](client)
        assert "receipts/CMD-020.json" in client.receipts, "Next cycle did not continue the backlog"
        assert ledger["last_command_id"] == "CMD-020", "Last applied Command was overwritten by stale state"


verify()
verify(fail_health=True)
verify(fail_receipt_once=True)
print("PASS: bounded command backlog progresses, state truth preserved on remote failure")
