import importlib.util
import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))

# Load only the connector module under test. Importing the integrations package
# also imports Android live-mirror dependencies that are irrelevant to this
# contract test and are intentionally not installed in the lightweight CI job.
MODULE_PATH = SOURCE / "integrations" / "chatgpt_control.py"
spec = importlib.util.spec_from_file_location("r8_10_chatgpt_control_under_test", MODULE_PATH)
if spec is None or spec.loader is None:
    raise RuntimeError("cannot load chatgpt_control.py")
control = importlib.util.module_from_spec(spec)
spec.loader.exec_module(control)


def main() -> None:
    with tempfile.TemporaryDirectory() as temp:
        previous = os.environ.get("LOCALAPPDATA")
        os.environ["LOCALAPPDATA"] = temp
        try:
            status = control.control_status()
            assert status["verified"] is False
            assert status["connection_state"] == control.DISCONNECTED
            assert status["status"] == "unverified"
            assert status["status_label"] == "未验证连接"
            assert status["permissions"] == []
            blocker = control.primary_blocker()
            assert blocker["code"] == "chatgpt_not_verified"

            # A local owner action must never be reported as delivered to
            # ChatGPT before a real connector round trip exists.
            try:
                control.create_owner_command({"objective": "推广涟水县水电维修"})
            except ValueError as error:
                assert "尚未完成真实双向验证" in str(error)
            else:
                raise AssertionError("unverified connector accepted owner command")

            # Neither a local bridge nor a fake proof source may elevate state.
            try:
                control.record_verified_roundtrip(
                    connector_id="test",
                    proof_source="local_folder",
                    challenge_id="challenge",
                    command_id="CMD-TEST",
                    receipt_id="RECEIPT-TEST",
                )
            except ValueError:
                pass
            else:
                raise AssertionError("local folder was accepted as ChatGPT proof")

            # A real adapter proof writes a matching verification Command + Receipt.
            verified = control.record_verified_roundtrip(
                connector_id="connector-test",
                proof_source="chatgpt_app",
                challenge_id="challenge-test",
                command_id="CMD-ROUNDTRIP",
                receipt_id="RECEIPT-ROUNDTRIP",
                permissions=["read_missions", "create_mission", "refund"],
            )
            assert verified["verified"] is True
            assert verified["connection_state"] == control.CONNECTED_VERIFIED
            assert verified["status_label"] == "已验证连接"
            assert "read_missions" in verified["permissions"]
            assert "create_mission" in verified["permissions"]
            assert "refund" not in verified["permissions"]
            commands = control.recent_commands()
            receipts = control.recent_receipts()
            assert commands[0]["command_id"] == "CMD-ROUNDTRIP"
            assert receipts[0]["receipt_id"] == "RECEIPT-ROUNDTRIP"
            assert receipts[0]["command_id"] == commands[0]["command_id"]

            # Owner objective creates a real Command and moves the single state
            # source to WAITING_RESPONSE until an execution Receipt comes back.
            command = control.create_owner_command({"objective": "推广涟水县水电维修"})
            assert command["command_id"].startswith("CMD-")
            assert command["status"] == "queued_for_verified_connector"
            waiting = control.control_status()
            assert waiting["verified"] is True
            assert waiting["connection_state"] == control.WAITING_RESPONSE
            assert waiting["last_command_id"] == command["command_id"]

            accepted = control.acknowledge_command(command["command_id"], mission_id="MISSION-TEST-001")
            assert accepted["status"] == "accepted"
            assert accepted["mission_id"] == "MISSION-TEST-001"

            receipt = control.record_command_receipt(
                command["command_id"],
                {"mission_created": True, "employee_tasks_started": 8},
                mission_id="MISSION-TEST-001",
            )
            assert receipt["receipt_id"].startswith("RECEIPT-")
            assert receipt["command_id"] == command["command_id"]
            assert receipt["mission_id"] == "MISSION-TEST-001"
            final = control.control_status()
            assert final["verified"] is True
            assert final["connection_state"] == control.CONNECTED_VERIFIED
            assert final["last_receipt_id"] == receipt["receipt_id"]
            assert control.primary_blocker()["code"] == "none"

            # A verified state cannot be fabricated without valid proof.
            control.mark_unverified("测试连接失效")
            try:
                control.set_runtime_state(control.CONNECTED_VERIFIED)
            except ValueError:
                pass
            else:
                raise AssertionError("CONNECTED_VERIFIED was fabricated without proof")

            reset = control.control_status()
            assert reset["verified"] is False
            assert reset["connection_state"] == control.DISCONNECTED
            assert reset["permissions"] == []
        finally:
            if previous is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = previous

    print("PASS: R8-10 ChatGPT single truth state and Command -> Receipt contract verified.")


if __name__ == "__main__":
    main()
