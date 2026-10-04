"""Regression gate: stale model-route verification must not look live."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SRC = ROOT / "05_V2.0.0_Source"


def main():
    previous = os.environ.get("LOCALAPPDATA")
    with tempfile.TemporaryDirectory() as tmp:
        os.environ["LOCALAPPDATA"] = tmp
        sys.path.insert(0, str(SRC))
        try:
            from integrations import ai_gateway, geo_local_precheck

            original_route = ai_gateway._route_status
            original_probe = geo_local_precheck._local_service_available
            try:
                ai_gateway._route_status = lambda route: {
                    "configured": True, "verified": True, "provider": "custom",
                    "model": "kazuizhi-auto", "endpoint": "http://127.0.0.1:17777/v1/chat/completions",
                    "last_error": None,
                }
                geo_local_precheck._local_service_available = lambda endpoint: False
                offline = geo_local_precheck.status()
                assert offline["ready"] is False
                assert offline["verified"] is False
                assert "未运行" in offline["reason"]

                geo_local_precheck._local_service_available = lambda endpoint: True
                online = geo_local_precheck.status()
                assert online["ready"] is True
                assert online["verified"] is True
            finally:
                ai_gateway._route_status = original_route
                geo_local_precheck._local_service_available = original_probe
        finally:
            sys.path.remove(str(SRC))
            if previous is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = previous
    print("PASS: GEO local precheck rejects stale local-router verification")


if __name__ == "__main__":
    main()
