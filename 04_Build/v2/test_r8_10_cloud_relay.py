import importlib.util
import json
import os
import sys
import tempfile
import time
import types
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
CLOUD = ROOT / "06_Cloud_Relay" / "kz_chatgpt_control_relay.py"
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
adapter = load_module("integrations.chatgpt_connector_adapter", SOURCE / "integrations" / "chatgpt_connector_adapter.py")
setattr(pkg, "chatgpt_connector_adapter", adapter)
cloud = load_module("kz_chatgpt_control_relay", CLOUD)


def agent_message(connector_id, kind, data, secret, nonce):
    return cloud._sign_full({
        "protocol": cloud.RELAY_PROTOCOL,
        "kind": kind,
        "connector_id": connector_id,
        "timestamp": int(time.time()),
        "nonce": nonce,
        "data": data,
    }, cloud._secret(secret, "agent_secret"))


def controller_message(connector_id, kind, data, secret, nonce):
    return cloud.sign_controller_message(
        connector_id=connector_id,
        kind=kind,
        data=data,
        controller_secret=secret,
        timestamp=int(time.time()),
        nonce=nonce,
    )


def run_cycle(core, *, connector_id, agent_secret, controller_secret, action, data,
              idempotency_key, suffix):
    queued = core.controller_enqueue(controller_message(
        connector_id,
        "enqueue",
        {"action": action, "data": data, "idempotency_key": idempotency_key},
        controller_secret,
        f"controller-enqueue-{suffix}",
    ))
    job = queued["data"]["job"]
    assert job["status"] == "queued"

    poll = core.agent_poll(agent_message(
        connector_id,
        "poll",
        {"state": {}},
        agent_secret,
        f"agent-poll-{suffix}",
    ))
    cloud._verify_full(poll, cloud._secret(agent_secret, "agent_secret"))
    envelopes = poll["data"]["envelopes"]
    assert len(envelopes) == 1
    local_result = adapter.process_envelope(envelopes[0], secret=agent_secret)
    assert local_result["action"] == action

    ack = core.agent_result(agent_message(
        connector_id,
        "result",
        {"poll_nonce": poll["nonce"], "processed": [local_result], "state": {}},
        agent_secret,
        f"agent-result-{suffix}",
    ))
    cloud._verify_full(ack, cloud._secret(agent_secret, "agent_secret"))
    assert ack["kind"] == "result_ack"

    status = core.controller_status(controller_message(
        connector_id,
        "status",
        {"job_id": job["job_id"]},
        controller_secret,
        f"controller-status-{suffix}",
    ))
    cloud._verify_full(status, cloud._secret(controller_secret, "controller_secret"))
    stored = status["data"]["jobs"][0]
    assert stored["status"] == "completed"
    assert stored["result"]["action"] == action
    return stored["result"], job


def main() -> None:
    agent_secret = "cloud-relay-agent-secret-0123456789-ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    controller_secret = "cloud-relay-controller-secret-0123456789-ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    connector_id = "kazuizhi-chatgpt-cloud-e2e"

    with tempfile.TemporaryDirectory() as temp:
        prior_local = os.environ.get("LOCALAPPDATA")
        prior_secret = os.environ.get(adapter.SECRET_ENV)
        os.environ["LOCALAPPDATA"] = temp
        os.environ[adapter.SECRET_ENV] = agent_secret
        try:
            core = cloud.RelayCore(
                agent_secret=agent_secret,
                controller_secret=controller_secret,
                connector_id=connector_id,
                store_path=Path(temp) / "relay-store.json",
            )

            # Controller authentication and nonce replay protection are separate
            # from the Windows agent trust zone.
            replay = controller_message(
                connector_id, "status", {}, controller_secret, "controller-replay-001"
            )
            first_status = core.controller_status(replay)
            assert first_status["data"]["last_agent_seen"] is None
            try:
                core.controller_status(replay)
            except ValueError as error:
                assert "重放" in str(error)
            else:
                raise AssertionError("controller replay was accepted")

            bad_controller = controller_message(
                connector_id,
                "status",
                {},
                "wrong-controller-secret-0123456789-ABCDEFGHIJKLMNOPQRSTUVWXYZ",
                "controller-wrong-signature",
            )
            try:
                core.controller_status(bad_controller)
            except ValueError as error:
                assert "签名" in str(error)
            else:
                raise AssertionError("wrong controller secret was accepted")

            # 1. Cloud controller asks the Windows client to create a pairing challenge.
            begin, begin_job = run_cycle(
                core,
                connector_id=connector_id,
                agent_secret=agent_secret,
                controller_secret=controller_secret,
                action="begin_pairing",
                data={
                    "proof_source": "signed_relay",
                    "permissions": [
                        "read_missions", "read_execution_status", "create_mission",
                        "start_content_production", "pause_non_financial_mission", "refund",
                    ],
                },
                idempotency_key="pairing-begin-001",
                suffix="pairing-begin",
            )
            challenge = begin["result"]
            assert challenge["challenge_id"].startswith("CHALLENGE-")
            assert control.control_status()["verified"] is False

            # 2. Only after the cloud side has received the challenge does it return
            # a matching signed Receipt. This is the actual round-trip proof.
            complete, _ = run_cycle(
                core,
                connector_id=connector_id,
                agent_secret=agent_secret,
                controller_secret=controller_secret,
                action="complete_pairing",
                data={
                    "challenge_id": challenge["challenge_id"],
                    "command_id": challenge["command_id"],
                    "receipt_id": "RECEIPT-CLOUD-PAIR-001",
                },
                idempotency_key="pairing-complete-001",
                suffix="pairing-complete",
            )
            assert complete["result"]["verified"] is True
            assert control.control_status()["connection_state"] == control.CONNECTED_VERIFIED
            assert "refund" not in control.control_status()["permissions"]

            # 3. Exact owner field-acceptance objective enters the canonical local queue.
            command = control.create_owner_command({
                "objective": "今天重点推广涟水县水电维修，目标是获得真实咨询"
            })
            assert command["status"] == "queued_for_verified_connector"

            pulled, _ = run_cycle(
                core,
                connector_id=connector_id,
                agent_secret=agent_secret,
                controller_secret=controller_secret,
                action="pull_commands",
                data={"limit": 10},
                idempotency_key="pull-owner-objective-001",
                suffix="pull-objective",
            )
            owner_items = pulled["result"]["items"]
            owner_command = next(x for x in owner_items if x["command_id"] == command["command_id"])
            assert "涟水县水电维修" in owner_command["objective"]

            # 4. ChatGPT-side decision returns through cloud relay and becomes one
            # shared R7/R8 Mission. No external publish/inquiry/order is fabricated.
            decision = {
                "action": "create_mission",
                "region": "涟水县",
                "service": "水电安装维修",
                "title": "涟水县水电维修真实咨询增长",
                "evidence": "老板明确要求今天重点推广涟水县水电维修并以真实咨询为目标",
                "goal": "获得可追溯的真实咨询",
                "reason": "围绕明确区域与服务建立可追溯 Mission，后续外部结果必须等待真实回执",
            }
            applied, _ = run_cycle(
                core,
                connector_id=connector_id,
                agent_secret=agent_secret,
                controller_secret=controller_secret,
                action="apply_decision",
                data={"command_id": command["command_id"], "decision": decision},
                idempotency_key="apply-owner-objective-001",
                suffix="apply-decision",
            )
            applied_result = applied["result"]
            receipt = applied_result["receipt"]
            state = applied_result["state"]
            assert receipt["command_id"] == command["command_id"]
            assert receipt["mission_id"]
            assert state["active_mission"]["mission_id"] == receipt["mission_id"]
            assert state["active_mission"]["region"] == "涟水县"
            assert state["active_mission"]["service"] == "水电安装维修"
            assert state["ai_employee_role_count"] == 8
            assert "不代表这些外部结果已经发生" in receipt["result"]["external_result_truth"]

            # Relay queue idempotency is independent of local Command idempotency.
            duplicate_1 = core.controller_enqueue(controller_message(
                connector_id,
                "enqueue",
                {"action": "read_state", "data": {}, "idempotency_key": "relay-idempotent-read-001"},
                controller_secret,
                "controller-idem-001",
            ))
            duplicate_2 = core.controller_enqueue(controller_message(
                connector_id,
                "enqueue",
                {"action": "read_state", "data": {}, "idempotency_key": "relay-idempotent-read-001"},
                controller_secret,
                "controller-idem-002",
            ))
            assert duplicate_1["data"]["job"]["job_id"] == duplicate_2["data"]["job"]["job_id"]
            assert duplicate_2["data"]["idempotent"] is True

            # Finish the queued readback and prove cloud can read the same Mission.
            poll = core.agent_poll(agent_message(
                connector_id, "poll", {"state": {}}, agent_secret, "agent-poll-readback"
            ))
            envelopes = poll["data"]["envelopes"]
            assert len(envelopes) == 1
            readback_local = adapter.process_envelope(envelopes[0], secret=agent_secret)
            core.agent_result(agent_message(
                connector_id,
                "result",
                {"poll_nonce": poll["nonce"], "processed": [readback_local], "state": {}},
                agent_secret,
                "agent-result-readback",
            ))
            readback = readback_local["result"]
            assert readback["control"]["verified"] is True
            assert readback["active_mission"]["mission_id"] == receipt["mission_id"]
            assert readback["control"]["last_receipt_id"] == receipt["receipt_id"]

            health = core.health()
            assert health["last_agent_seen"]
            assert health["secrets_exposed"] is False
            assert health["completed"] >= 5
        finally:
            if prior_local is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = prior_local
            if prior_secret is None:
                os.environ.pop(adapter.SECRET_ENV, None)
            else:
                os.environ[adapter.SECRET_ENV] = prior_secret

    print("PASS: cloud controller -> signed relay -> Windows Connector -> Mission -> Receipt -> cloud readback verified.")


if __name__ == "__main__":
    main()
