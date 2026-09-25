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
            from integrations import remote_agent
            from integrations import r8_17_iis_static_compat as iis_compat
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
            require(
                remote_agent.upload_file is iis_compat.upload_file,
                "R8-17 IIS compatibility upload shim is not installed",
            )

            # Verify that a managed SEO index page is mirrored to default.htm,
            # while unrelated uploads remain single-write. This is a pure unit
            # test: no production credentials or network calls are used.
            calls = []
            original_upload = iis_compat._ORIGINAL_UPLOAD_FILE
            try:
                def fake_upload(relative_path, source, *, job_id=""):
                    calls.append((str(relative_path), str(job_id)))
                    return {
                        "ok": True,
                        "job_id": str(job_id),
                        "sha256": "a" * 64,
                    }

                iis_compat._ORIGINAL_UPLOAD_FILE = fake_upload
                sample = Path(temp) / "index.html"
                sample.write_text("<html>ok</html>", encoding="utf-8")
                reply = iis_compat.upload_file(
                    "seo/test-page/index.html",
                    sample,
                    job_id="SEO-TEST",
                )
                require(
                    [row[0] for row in calls] == [
                        "seo/test-page/index.html",
                        "seo/test-page/default.htm",
                    ],
                    "SEO index.html was not mirrored to IIS default.htm",
                )
                require(
                    (reply.get("iis_default_document_mirror") or {}).get("relative_path")
                    == "seo/test-page/default.htm",
                    "IIS mirror receipt was not exposed",
                )

                calls.clear()
                iis_compat.upload_file("downloads/test.zip", sample, job_id="DL-TEST")
                require(
                    [row[0] for row in calls] == ["downloads/test.zip"],
                    "non-SEO upload was incorrectly mirrored",
                )
            finally:
                iis_compat._ORIGINAL_UPLOAD_FILE = original_upload

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

            print("R8-17 autonomy Remote Agent bridge + IIS static compatibility regression: PASS")
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
