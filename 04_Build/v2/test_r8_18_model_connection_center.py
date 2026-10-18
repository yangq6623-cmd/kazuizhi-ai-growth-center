"""Regression gate for the cloud/local model connection centre.

This test never contacts a cloud service or launches a local model.  It proves
that a local OpenAI-compatible route needs no API key, is restricted to this
computer, and receives a real model-list health check before it is marked ready.
"""
from __future__ import annotations

import io
import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "05_V2.0.0_Source"


def check(condition, message):
    if not condition:
        raise AssertionError(message)


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return b'{"object":"list","data":[{"id":"qwen-local"}]}'


def main():
    old_local = os.environ.get("LOCALAPPDATA")
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["LOCALAPPDATA"] = tmp
        sys.path.insert(0, str(SRC))
        try:
            from integrations import ai_gateway

            ai_gateway.configure_gateway({
                "route": "local", "provider": "ollama", "model": "qwen-local",
                "endpoint": "http://127.0.0.1:11434/v1/chat/completions", "set_active": True,
            })
            before = ai_gateway.gateway_status()
            local = before["routes"]["local"]
            check(local["configured"] and not local["requires_api_key"], "local runtime unexpectedly requires an API key")
            check(before["active_route"] == "local", "local runtime was not selected as active route")

            seen = {}

            def fake_open(request, timeout):
                seen["url"] = request.full_url
                seen["authorization"] = request.get_header("Authorization")
                seen["timeout"] = timeout
                return FakeResponse()

            with patch("urllib.request.urlopen", fake_open):
                ready = ai_gateway.test_gateway("local")
            check(ready["routes"]["local"]["verified"], "successful local health check was not recorded")
            check(seen["url"] == "http://127.0.0.1:11434/v1/models", "local health check used the wrong endpoint")
            check(not seen["authorization"], "local runtime sent a nonexistent API key")

            try:
                ai_gateway.configure_gateway({"route": "local", "model": "qwen-local", "endpoint": "http://remote.example/v1/chat/completions"})
            except ValueError as error:
                check("本地模型只允许" in str(error), "remote local-runtime endpoint produced the wrong error")
            else:
                raise AssertionError("local runtime accepted a remote endpoint")

            try:
                ai_gateway.configure_gateway({"route": "cloud", "model": "example-cloud", "endpoint": "https://api.example/v1/responses"})
            except ValueError as error:
                check("API 密钥" in str(error), "cloud route without key produced the wrong error")
            else:
                raise AssertionError("cloud runtime accepted an empty API key")
            print("PASS: R8-18 model centre separates local/cloud routes and keeps local runtime on localhost")
        finally:
            sys.path.remove(str(SRC))
            if old_local is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = old_local


if __name__ == "__main__":
    main()
