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
relay = load_module("integrations.chatgpt_relay_agent", SOURCE / "integrations" / "chatgpt_relay_agent.py")
setattr(pkg, "chatgpt_relay_agent", relay)


class FakeResponse:
    def __init__(self, value):
        self.raw = json.dumps(value, ensure_ascii=False).encode("utf-8")
    def read(self, size=-1):
        return self.raw if size < 0 else self.raw[:size]
    def close(self):
        return None


def main() -> None:
    secret = "relay-agent-test-secret-0123456789-ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    connector_id = "chatgpt-outbound-relay-test"
    with tempfile.TemporaryDirectory() as temp:
        prior_local = os.environ.get("LOCALAPPDATA")
        prior_secret = os.environ.get(adapter.SECRET_ENV)
        prior_url = os.environ.get(relay.RELAY_URL_ENV)
        prior_id = os.environ.get(relay.CONNECTOR_ID_ENV)
        os.environ["LOCALAPPDATA"] = temp
        os.environ[adapter.SECRET_ENV] = secret
        os.environ[relay.RELAY_URL_ENV] = "https://relay.example.test"
        os.environ[relay.CONNECTOR_ID_ENV] = connector_id
        try:
            config = relay.relay_config_status()
            assert config["configured"] is True
            assert config["transport"] == "outbound_https_poll"
            assert config["inbound_port_exposed"] is False

            captured_results = []
            phase = {"name": "begin"}

            def server_message(kind, data, nonce):
                return relay._sign_message({
                    "protocol": relay.PROTOCOL,
                    "kind": kind,
                    "connector_id": connector_id,
                    "timestamp": int(time.time()),
                    "nonce": nonce,
                    "data": data,
                }, secret=secret)

            def opener(request, timeout=12):
                body = json.loads(request.data.decode("utf-8"))
                # The desktop signs every outbound message and never sends the
                # shared secret itself.
                assert body.get("signature")
                assert secret not in request.data.decode("utf-8")
                if request.full_url.endswith("/v1/poll"):
                    if phase["name"] == "begin":
                        envelope = adapter.sign_envelope(
                            connector_id=connector_id,
                            action="begin_pairing",
                            data={"proof_source": "signed_relay"},
                            nonce="relay-envelope-begin-001",
                            secret=secret,
                        )
                        return FakeResponse(server_message("poll_response", {"envelopes": [envelope]}, "relay-response-001"))
                    if phase["name"] == "complete":
                        first = captured_results[0]["processed"][0]["result"]
                        envelope = adapter.sign_envelope(
                            connector_id=connector_id,
                            action="complete_pairing",
                            data={
                                "challenge_id": first["challenge_id"],
                                "command_id": first["command_id"],
                                "receipt_id": "RECEIPT-RELAY-VERIFY-001",
                            },
                            nonce="relay-envelope-complete-001",
                            secret=secret,
                        )
                        return FakeResponse(server_message("poll_response", {"envelopes": [envelope]}, "relay-response-002"))
                    return FakeResponse(server_message("poll_response", {"envelopes": []}, "relay-response-003"))

                if request.full_url.endswith("/v1/result"):
                    captured_results.append(body["data"])
                    nonce = f"relay-ack-{len(captured_results):03d}"
                    return FakeResponse(server_message("result_ack", {"accepted": True}, nonce))
                raise AssertionError(f"unexpected relay URL: {request.full_url}")

            # First outbound poll receives the challenge envelope but MUST remain
            # unverified until a matching receipt returns in the next cycle.
            first = relay.poll_once(secret=secret, opener=opener)
            assert first["ok"] is True
            assert first["processed"] == 1
            assert control.control_status()["verified"] is False
            assert control.control_status()["connection_state"] == control.CONNECTED_UNVERIFIED
            assert captured_results[0]["processed"][0]["action"] == "begin_pairing"

            phase["name"] = "complete"
            second = relay.poll_once(secret=secret, opener=opener)
            assert second["ok"] is True
            assert control.control_status()["verified"] is True
            assert control.control_status()["connection_state"] == control.CONNECTED_VERIFIED
            assert control.control_status()["last_receipt_id"] == "RECEIPT-RELAY-VERIFY-001"

            # Replay of a relay response nonce is rejected even if its HMAC is valid.
            replay = server_message("poll_response", {"envelopes": []}, "relay-replay-001")
            relay._verify_message(replay, connector_id=connector_id, secret=secret)
            try:
                relay._verify_message(replay, connector_id=connector_id, secret=secret)
            except ValueError as error:
                assert "重放" in str(error)
            else:
                raise AssertionError("replayed relay response was accepted")

            # Insecure non-local HTTP transport is refused before any network call.
            try:
                relay.poll_once(relay_url="http://public.example.test", connector_id=connector_id, secret=secret, opener=opener)
            except ValueError as error:
                assert "HTTPS" in str(error)
            else:
                raise AssertionError("insecure public relay URL was accepted")
        finally:
            for key, value in [
                ("LOCALAPPDATA", prior_local),
                (adapter.SECRET_ENV, prior_secret),
                (relay.RELAY_URL_ENV, prior_url),
                (relay.CONNECTOR_ID_ENV, prior_id),
            ]:
                if value is None:
                    os.environ.pop(key, None)
                else:
                    os.environ[key] = value

    print("PASS: outbound-only ChatGPT Relay Agent pairing, signatures and replay protection verified.")


if __name__ == "__main__":
    main()
