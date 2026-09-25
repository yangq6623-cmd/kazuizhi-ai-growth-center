"""Regression gate: R8-14 autonomy must see R8-17 runtime deployer patches."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))


def require(condition, message):
    if not condition:
        raise AssertionError(message)


def main():
    with tempfile.TemporaryDirectory(prefix="kz-r817-autonomy-") as temp:
        previous_local = os.environ.get("LOCALAPPDATA")
        previous_profile = os.environ.get("USERPROFILE")
        os.environ["LOCALAPPDATA"] = temp
        os.environ["USERPROFILE"] = temp
        try:
            from core import seo_geo_autonomy as autonomy
            from integrations import seo_public_deployer as deployer
            from integrations import search_engine_submitter as searcher

            require(
                autonomy.seo_public_deployer is deployer,
                "autonomy is not resolving the live seo_public_deployer module",
            )
            require(
                autonomy.search_engine_submitter is searcher,
                "autonomy is not resolving the live search_engine_submitter module",
            )

            original_deploy_status = deployer.status
            original_search_status = searcher.status
            try:
                deployer.status = lambda: {
                    "configured": True,
                    "enabled": True,
                    "ready": True,
                    "mode": "remote_agent_v1",
                    "reason": "",
                    "remote_agent": {
                        "connected": True,
                        "version": "R8-17.8-FINAL5",
                    },
                }
                searcher.status = lambda: {
                    "connectors": {
                        "indexnow": {"configured": True, "ready": True}
                    },
                    "ready_engines": ["indexnow"],
                }
                readiness = autonomy._external_readiness({"technical": {}})
                require(
                    readiness["publish_connector_ready"] is True,
                    "autonomy ignored the live R8-17 Remote Agent deployer status",
                )
                require(
                    readiness["publish_connector"]["mode"] == "remote_agent_v1",
                    "autonomy fell back to the stale R8-15 local-IIS connector",
                )
                require(
                    "indexnow" in readiness["ready_search_connectors"],
                    "autonomy did not resolve the live search submitter status",
                )
            finally:
                deployer.status = original_deploy_status
                searcher.status = original_search_status

            print("R8-17 autonomy Remote Agent bridge regression: PASS")
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
