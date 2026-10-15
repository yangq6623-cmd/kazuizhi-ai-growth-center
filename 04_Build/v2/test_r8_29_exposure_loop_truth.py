"""Release gate for the owner-command and exposure-loop truth fixes."""
from __future__ import annotations

import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))


def main():
    previous = os.environ.get("LOCALAPPDATA")
    with tempfile.TemporaryDirectory(prefix=".kz-r829-", dir=ROOT) as temp:
        os.environ["LOCALAPPDATA"] = temp
        try:
            from core import command_execution
            from core import geo_growth_orchestrator as growth
            from integrations import chatgpt_control as control
            from promotion import content_center

            control.record_verified_roundtrip(
                connector_id="test-local-owner",
                proof_source="chatgpt_app",
                challenge_id="challenge-r829",
                command_id="verification-r829",
                receipt_id="verification-receipt-r829",
            )
            command = control.create_owner_command({
                "objective": "启动真实曝光闭环，只把新发布或实质更新且有回执的页面计为完成。",
            })
            assert command["status"] == "accepted", command
            assert command["accepted_at"], command
            assert command["acceptance_source"] == "verified_local_owner_workbench", command
            link = next(row for row in command_execution.command_links() if row.get("command_id") == command["command_id"])
            assert command_execution._authorized(link) is True, link

            stale = {
                "created_at": "2026-10-13T09:00:00+08:00",
                "published_at": "2026-10-06T09:00:00+08:00",
                "public_url": "https://kazuizhi.com/seo/old/",
                "state": "waiting_content_update",
            }
            fresh = {
                "created_at": "2026-10-13T09:00:00+08:00",
                "published_at": "2026-10-13T10:00:00+08:00",
                "public_url": "https://kazuizhi.com/seo/new/",
                "state": "waiting_retest",
            }
            assert growth._has_verified_publication(stale) is False
            assert growth._has_verified_publication(fresh) is True
            counts = growth._state_counts([stale, fresh])
            assert counts["waiting_publish"] == 1, counts
            assert counts["published_or_waiting_retest"] == 1, counts

            history = growth._daily_history([stale, fresh])
            today = next(row for row in history if row["date"] == "2026-10-13")
            assert today["new_opportunities"] == 2, today
            assert today["verified_publications"] == 1, today
            assert today["published_urls"] == ["https://kazuizhi.com/seo/new/"], today
            assert content_center.HISTORY_RETENTION >= 365, content_center.HISTORY_RETENTION
        finally:
            if previous is None:
                os.environ.pop("LOCALAPPDATA", None)
            else:
                os.environ["LOCALAPPDATA"] = previous

    print("R8-29 exposure loop truth gate passed")


if __name__ == "__main__":
    main()
