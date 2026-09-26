"""Release gate for R8-17 desktop Remote Agent integration."""
from __future__ import annotations

import hashlib
import json
import os
import sys
import tempfile
import urllib.parse
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    with tempfile.TemporaryDirectory(prefix="kz-r817-") as temp:
        previous_local = os.environ.get("LOCALAPPDATA")
        previous_profile = os.environ.get("USERPROFILE")
        os.environ["LOCALAPPDATA"] = temp
        os.environ["USERPROFILE"] = temp
        try:
            from integrations import remote_agent
            from integrations import r8_17_remote_deployer_patch as remote_patch
            from integrations import seo_public_deployer as deployer
            from integrations import search_engine_submitter as searcher

            good = {
                "protocol": "kz-remote-agent-v1",
                "auth_scheme": "token-v1",
                "endpoint": "https://kazuizhi.com/kz-remote-v1/agent.ashx/v1",
                "key_id": "desktop-main",
                "shared_secret": "S" * 64,
            }
            validated = remote_agent._validate_pairing(good)
            require(validated["endpoint"].startswith("https://kazuizhi.com/"), "valid pairing endpoint rejected")
            try:
                remote_agent._validate_pairing({**good, "endpoint": "http://kazuizhi.com/kz-remote-v1/agent.ashx/v1"})
                raise AssertionError("HTTP endpoint was accepted")
            except ValueError:
                pass
            try:
                remote_agent._safe_relative_path("../Web.config")
                raise AssertionError("path traversal was accepted")
            except ValueError:
                pass
            try:
                remote_agent._safe_relative_path("bin/tool.dll")
                raise AssertionError("server-code path was accepted")
            except ValueError:
                pass
            require(remote_agent._safe_relative_path("seo/demo/index.html") == "seo/demo/index.html", "managed SEO path rejected")

            # Pairing verification happens before persistence; emulate the already field-tested FINAL5 endpoint.
            secrets = {}
            remote_agent.put_secret = lambda key, value: secrets.__setitem__(key, value)
            remote_agent.get_secret = lambda key: secrets.get(key)
            remote_agent.delete_secret = lambda key: secrets.pop(key, None) is not None

            calls = []
            def fake_credential_request(endpoint, key_id, secret, route, **kwargs):
                calls.append((route, endpoint, key_id, secret))
                if route == "health":
                    return {"ok": True, "protocol": "kz-remote-agent-v1", "auth_scheme": "token-v1", "version": "R8-17.8-FINAL5", "website_ready": True}
                if route == "capabilities":
                    return {"ok": True, "protocol": "kz-remote-agent-v1", "auth_scheme": "token-v1", "version": "R8-17.8-FINAL5"}
                raise AssertionError(f"unexpected route {route}")

            original_credential_request = remote_agent._request_with_credentials
            remote_agent._request_with_credentials = fake_credential_request
            pair_path = Path(temp) / remote_agent.PAIRING_FILENAME
            pair_path.write_text(json.dumps(good), encoding="utf-8")
            imported = remote_agent.import_pairing_file(pair_path, delete_after_success=True)
            require(imported["connected"], "pairing did not connect")
            require(not pair_path.exists(), "local pairing file was not deleted after verified import")
            require(secrets.get(remote_agent.SECRET_KEY) == good["shared_secret"], "secret not transferred to credential vault")
            remote_agent._request_with_credentials = original_credential_request

            state = remote_agent.status(check_live=False)
            require(state["configured"], "stored pairing is not configured")
            require("shared_secret" not in state and "token" not in state, "status leaked secret")
            require(state["secret_exposed"] is False, "secret exposure marker invalid")

            # Verify upload protocol, body hashes and chunk progress without external network.
            upload_calls = []
            payload = ("remote-agent-upload-test-" * 5000).encode("utf-8")
            expected_sha = hashlib.sha256(payload).hexdigest()
            received = bytearray()

            def fake_request(route, *, method="GET", body=b"", content_type="", timeout=15):
                upload_calls.append((route, method, body, content_type))
                form = urllib.parse.parse_qs(body.decode("utf-8"), keep_blank_values=True) if body else {}
                if route == "upload/start":
                    require(form["relative_path"][0] == "seo/test/index.html", "wrong remote path")
                    require(form["sha256"][0] == expected_sha, "wrong start SHA")
                    require(int(form["total_size"][0]) == len(payload), "wrong total size")
                    return {"ok": True, "session_id": "abc123", "max_chunk_bytes": 65536}
                if route == "upload/chunk":
                    chunk = form["data_base64url"][0]
                    padding = "=" * ((4 - len(chunk) % 4) % 4)
                    import base64
                    decoded = base64.urlsafe_b64decode(chunk + padding)
                    require(int(form["offset"][0]) == len(received), "wrong chunk offset")
                    received.extend(decoded)
                    return {"ok": True, "received": len(received), "total": len(payload)}
                if route == "upload/commit":
                    require(bytes(received) == payload, "uploaded bytes changed")
                    return {"ok": True, "job_id": "SEO-TEST", "sha256": expected_sha, "bytes": len(payload)}
                raise AssertionError(f"unexpected upload route {route}")

            original_request = remote_agent._request
            remote_agent._request = fake_request
            receipt = remote_agent.upload_bytes("seo/test/index.html", payload, job_id="SEO-TEST")
            remote_agent._request = original_request
            require(receipt["sha256"] == expected_sha, "commit receipt SHA mismatch")
            require(any(row[0] == "upload/chunk" for row in upload_calls), "chunk upload was not used")

            # R8-17 patches the deployer module.  R8-16 must keep a dynamic
            # module reference rather than capture the former local-IIS status
            # function, otherwise its UI can report contradictory readiness.
            require(deployer.status is remote_patch.status, "R8-17 deployer status patch not installed")
            require(deployer.deploy_pending is remote_patch.deploy_pending, "R8-17 deployer run patch not installed")
            require(searcher.seo_public_deployer is deployer, "R8-16 search submitter did not retain dynamic deployer module")
            require(searcher._ensure_indexnow_key_file.__module__ == remote_patch.__name__, "IndexNow key hosting was not patched for Remote Agent")

            # First paint must not block on an external remote-agent probe. The
            # scheduler still performs that live probe after the local shell is
            # ready, so remote deployment readiness is preserved.
            import run as runtime
            original_auto_import = runtime.auto_import_pairing
            original_activate = runtime.activate_remote_mode_if_ready
            probe_flags = []
            try:
                runtime.auto_import_pairing = lambda: {"ok": True}
                runtime.activate_remote_mode_if_ready = lambda check_live=True: (
                    probe_flags.append(check_live) or {"activated": False}
                )
                runtime._sync_r8_17_remote_agent(check_live=False)
                runtime._sync_r8_17_remote_agent(check_live=True)
                require(probe_flags == [False, True], "startup still performs a blocking remote probe")
            finally:
                runtime.auto_import_pairing = original_auto_import
                runtime.activate_remote_mode_if_ready = original_activate

            # Activate remote mode using a safe mocked live status.
            original_agent_status = remote_patch.remote_agent.status
            remote_patch.remote_agent.status = lambda check_live=True: {
                "configured": True,
                "connected": True,
                "website_ready": True,
                "version": "R8-17.8-FINAL5",
                "endpoint": good["endpoint"],
                "last_health_at": "now",
            }
            activated = remote_patch.activate_remote_mode_if_ready(check_live=True)
            remote_patch.remote_agent.status = original_agent_status
            require(activated["activated"], "remote deploy mode did not activate")
            require(deployer._load().get("mode") == "remote_agent_v1", "remote mode was not persisted")

            print("R8-17 Remote Agent release gate: PASS")
        finally:
            if previous_local is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = previous_local
            if previous_profile is None:
                os.environ.pop("USERPROFILE", None)
            else:
                os.environ["USERPROFILE"] = previous_profile


if __name__ == "__main__":
    main()
