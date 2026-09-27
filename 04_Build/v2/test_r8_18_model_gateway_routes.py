"""Regression gate: R7 only exposes verified model-connection routes."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "05_V2.0.0_Source"


class FakeResponse:
    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False

    def read(self):
        return b'{"object":"list","data":[{"id":"qwen-local"}]}'


def check(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    old_local = os.environ.get("LOCALAPPDATA")
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["LOCALAPPDATA"] = tmp
        sys.path.insert(0, str(SRC))
        try:
            from integrations import ai_gateway, manager

            before = manager.model_routes()
            check(before["default"] == "local_rules", "unconfigured model displaced local safety route")
            check(len(before["routes"]) == 1, "unconfigured model appeared as usable")

            ai_gateway.configure_gateway({
                "route": "local", "provider": "ollama", "model": "qwen-local",
                "endpoint": "http://127.0.0.1:11434/v1/chat/completions", "set_active": True,
            })
            waiting = manager.model_routes()
            check(waiting["default"] == "local_rules", "untested local model displaced safety route")

            with patch("urllib.request.urlopen", lambda *_args, **_kwargs: FakeResponse()):
                ai_gateway.test_gateway("local")
            ready = manager.model_routes()
            check(ready["default"] == "model_local", "verified local model did not become active route")
            check(any(item["id"] == "model_local" for item in ready["routes"]), "verified local route missing")
            print("PASS: model route uses only verified local/cloud endpoints and keeps offline fallback")
        finally:
            sys.path.remove(str(SRC))
            if old_local is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = old_local


if __name__ == "__main__":
    main()
