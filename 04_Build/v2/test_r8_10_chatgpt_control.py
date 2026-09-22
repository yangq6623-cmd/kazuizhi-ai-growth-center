import os
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
os.sys.path.insert(0, str(SOURCE))

from integrations import chatgpt_control as control  # noqa: E402


def main() -> None:
    with tempfile.TemporaryDirectory() as temp:
        previous = os.environ.get("LOCALAPPDATA")
        os.environ["LOCALAPPDATA"] = temp
        try:
            status = control.control_status()
            assert status["verified"] is False
            assert status["status"] == "unverified"
            assert status["status_label"] == "未验证连接"
            assert status["permissions"] == []

            # A local owner action must never be reported as delivered to
            # ChatGPT before a real connector round trip exists.
            try:
                control.create_owner_command({"objective": "推广涟水县水电维修"})
            except ValueError as error:
                assert "尚未完成真实双向验证" in str(error)
            else:
                raise AssertionError("unverified connector accepted owner command")

            # Bad proof sources cannot elevate the connection state.
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

            verified = control.record_verified_roundtrip(
                connector_id="connector-test",
                proof_source="chatgpt_app",
                challenge_id="challenge-test",
                command_id="CMD-ROUNDTRIP",
                receipt_id="RECEIPT-ROUNDTRIP",
                permissions=["read_missions", "create_mission", "refund"],
            )
            assert verified["verified"] is True
            assert verified["status_label"] == "已验证连接"
            assert "read_missions" in verified["permissions"]
            assert "create_mission" in verified["permissions"]
            assert "refund" not in verified["permissions"]

            command = control.create_owner_command({"objective": "推广涟水县水电维修"})
            assert command["command_id"].startswith("CMD-")
            assert command["status"] == "queued_for_verified_connector"

            reset = control.mark_unverified("测试完成")
            assert reset["verified"] is False
            assert reset["permissions"] == []
        finally:
            if previous is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = previous

    print("PASS: R8-10 ChatGPT control connector truth contract verified.")


if __name__ == "__main__":
    main()
