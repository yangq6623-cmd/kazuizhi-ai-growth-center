import importlib.util
import os
import sys
import tempfile
import time
import types
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


# Avoid integrations/__init__.py because this lightweight CI contract does not
# need Android live-mirror dependencies. The Connector modules are loaded under
# their real package names so their imports behave like production.
pkg = types.ModuleType("integrations")
pkg.__path__ = [str(SOURCE / "integrations")]
sys.modules["integrations"] = pkg
control = load_module("integrations.chatgpt_control", SOURCE / "integrations" / "chatgpt_control.py")
setattr(pkg, "chatgpt_control", control)
adapter = load_module("integrations.chatgpt_connector_adapter", SOURCE / "integrations" / "chatgpt_connector_adapter.py")
setattr(pkg, "chatgpt_connector_adapter", adapter)


def signed(connector_id, action, data, secret, nonce=None):
    return adapter.sign_envelope(
        connector_id=connector_id,
        action=action,
        data=data,
        timestamp=int(time.time()),
        nonce=nonce,
        secret=secret,
    )


def main() -> None:
    secret = "connector-test-secret-0123456789-ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    connector_id = "chatgpt-relay-test"
    with tempfile.TemporaryDirectory() as temp:
        previous_local = os.environ.get("LOCALAPPDATA")
        previous_secret = os.environ.get(adapter.SECRET_ENV)
        os.environ["LOCALAPPDATA"] = temp
        os.environ[adapter.SECRET_ENV] = secret
        try:
            initial = adapter.adapter_status()
            assert initial["credential_configured"] is True
            assert initial["verified"] is False

            # Step 1: signed pairing request creates only an unverified challenge.
            begin = signed(
                connector_id,
                "begin_pairing",
                {
                    "proof_source": "signed_relay",
                    "permissions": [
                        "read_missions", "read_execution_status", "create_mission",
                        "start_content_production", "pause_non_financial_mission", "refund",
                    ],
                },
                secret,
                nonce="nonce-begin-001",
            )
            begin_result = adapter.process_envelope(begin, secret=secret)["result"]
            assert begin_result["challenge_id"].startswith("CHALLENGE-")
            assert begin_result["command_id"].startswith("CMD-VERIFY-")
            pending = control.control_status()
            assert pending["verified"] is False
            assert pending["connection_state"] == control.CONNECTED_UNVERIFIED

            # The exact same signed message cannot be replayed.
            try:
                adapter.process_envelope(begin, secret=secret)
            except ValueError as error:
                assert "重放" in str(error)
            else:
                raise AssertionError("replayed pairing request was accepted")

            # Invalid signature cannot complete the connection.
            bad = signed(
                connector_id,
                "complete_pairing",
                {
                    "challenge_id": begin_result["challenge_id"],
                    "command_id": begin_result["command_id"],
                    "receipt_id": "RECEIPT-VERIFY-BAD",
                },
                secret,
                nonce="nonce-bad-001",
            )
            bad["signature"] = "0" * 64
            try:
                adapter.process_envelope(bad, secret=secret)
            except ValueError as error:
                assert "签名" in str(error)
            else:
                raise AssertionError("bad Connector signature was accepted")

            # Step 2: a matching signed Receipt finishes the real round trip.
            complete = signed(
                connector_id,
                "complete_pairing",
                {
                    "challenge_id": begin_result["challenge_id"],
                    "command_id": begin_result["command_id"],
                    "receipt_id": "RECEIPT-VERIFY-001",
                },
                secret,
                nonce="nonce-complete-001",
            )
            verified = adapter.process_envelope(complete, secret=secret)["result"]
            assert verified["verified"] is True
            assert verified["connection_state"] == control.CONNECTED_VERIFIED
            assert verified["connector_id"] == connector_id
            assert "refund" not in verified["permissions"]

            # Step 3: the owner gives the exact business objective used for field acceptance.
            command = control.create_owner_command({
                "objective": "今天重点推广涟水县水电维修，目标是获得真实咨询"
            })
            assert command["status"] == "queued_for_verified_connector"

            pulled = adapter.process_envelope(
                signed(connector_id, "pull_commands", {"limit": 10}, secret, nonce="nonce-pull-001"),
                secret=secret,
            )["result"]["items"]
            assert any(item["command_id"] == command["command_id"] for item in pulled)

            # Step 4: ChatGPT returns a structured non-financial Mission decision.
            decision = {
                "action": "create_mission",
                "region": "涟水县",
                "service": "水电安装维修",
                "title": "涟水县水电维修真实咨询增长",
                "evidence": "老板明确要求今天重点推广涟水县水电维修并以真实咨询为目标",
                "goal": "获得可追溯的真实咨询",
                "reason": "优先围绕已明确区域与服务建立可追溯 Mission，不虚构外部结果",
            }
            applied = adapter.process_envelope(
                signed(
                    connector_id,
                    "apply_decision",
                    {"command_id": command["command_id"], "decision": decision},
                    secret,
                    nonce="nonce-decision-001",
                ),
                secret=secret,
            )["result"]
            receipt = applied["receipt"]
            state = applied["state"]
            assert applied["idempotent"] is False
            assert receipt["command_id"] == command["command_id"]
            assert receipt["receipt_id"].startswith("RECEIPT-")
            assert receipt["mission_id"]
            assert state["active_mission"]["mission_id"] == receipt["mission_id"]
            assert state["active_mission"]["region"] == "涟水县"
            assert state["active_mission"]["service"] == "水电安装维修"
            assert state["ai_employee_role_count"] == 8
            assert "不伪造" in receipt["result"]["employee_truth"]
            assert "不代表这些外部结果已经发生" in receipt["result"]["external_result_truth"]

            # Step 5: retrying the same Command with a NEW valid nonce is idempotent.
            retried = adapter.process_envelope(
                signed(
                    connector_id,
                    "apply_decision",
                    {"command_id": command["command_id"], "decision": decision},
                    secret,
                    nonce="nonce-decision-002",
                ),
                secret=secret,
            )["result"]
            assert retried["idempotent"] is True
            assert retried["receipt"]["receipt_id"] == receipt["receipt_id"]

            # Step 6: the external side can read back the same Mission/Receipt truth.
            readback = adapter.process_envelope(
                signed(connector_id, "read_state", {}, secret, nonce="nonce-read-001"),
                secret=secret,
            )["result"]
            assert readback["control"]["verified"] is True
            assert readback["control"]["last_receipt_id"] == receipt["receipt_id"]
            assert readback["active_mission"]["mission_id"] == receipt["mission_id"]
            assert readback["ai_employee_role_count"] == 8

            # An expired envelope must fail before any action is applied.
            expired = adapter.sign_envelope(
                connector_id=connector_id,
                action="heartbeat",
                data={},
                timestamp=int(time.time()) - adapter.MAX_SKEW_SECONDS - 10,
                nonce="nonce-expired-001",
                secret=secret,
            )
            try:
                adapter.process_envelope(expired, secret=secret)
            except ValueError as error:
                assert "过期" in str(error) or "时间偏差" in str(error)
            else:
                raise AssertionError("expired Connector envelope was accepted")

            assert control.primary_blocker()["code"] == "none"
        finally:
            if previous_local is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = previous_local
            if previous_secret is None:
                os.environ.pop(adapter.SECRET_ENV, None)
            else:
                os.environ[adapter.SECRET_ENV] = previous_secret

    print("PASS: signed ChatGPT Connector -> Command -> Mission -> Receipt -> readback loop verified.")


if __name__ == "__main__":
    main()
