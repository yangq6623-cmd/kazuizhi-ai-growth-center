"""#818 isolated GEO ledger regressions: no account/browser, no production writes."""
import sys
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "05_V2.0.0_Source"))
from core import geo_growth_orchestrator as growth
from backend.r8_20_seo_geo_growth_patch import _geo_fast_ui_compact, _geo_fast_health_overview


class LedgerIntegrity(TestCase):
    def test_superseded_history_retained_deduplicated_and_failed_not_verified(self):
        first = {"id": "old", "state": "superseded",
                 "retest_schedule": [{"window": "24h", "task_id": "t1", "signal_id": "c1"}]}
        repeated = {"id": "old2", "state": "superseded",
                    "retest_schedule": [{"window": "24h", "task_id": "t1", "signal_id": "c1"}]}
        bad = {"id": "now", "state": "completed",
               "retest_schedule": [{"window": "24h", "task_id": "t2", "signal_id": "c2"}]}
        receipts = [
            {"task_id": "t1", "evidence_level": "C", "official_truth": False, "evidence_id": "c1"},
            {"task_id": "t2", "evidence_level": "C", "official_truth": False, "evidence_id": "c2"},
        ]
        tasks = [{"task_id": "t1", "state": "succeeded"}, {"task_id": "t2", "state": "failed"}]
        result = growth._retest_archive_summary([first, repeated, bad], receipts, tasks)
        self.assertEqual(result["24h"]["linked_distinct"], 2)
        self.assertEqual(result["24h"]["confirmed_c_receipts"], 1)
        self.assertEqual(result["24h"]["duplicate_links"], 1)
        self.assertEqual(result["24h"]["superseded_links"], 2)
        self.assertEqual(growth._retest_summary([first, repeated, bad])["24h"]["scheduled"], 1)
        self.assertEqual(result["72h"]["confirmed_c_receipts"], 0)

    def test_blocked_timeout_is_not_mislabeled_as_login_or_requeued(self):
        tasks = [
            *[{"state": "authorization_required",
                "authorization_reason": "capture_failed:agent_response_timeout"}
              for _ in range(71)],
            *[{"state": "authorization_required",
                "authorization_reason": "capture_failed:signal timed out"}
              for _ in range(2)],
            {"state": "authorization_required", "authorization_reason": "login_required"},
        ]
        with patch.object(growth, "read_json_snapshot", return_value={"tasks": tasks}):
            result = growth._geo_task_blockage_snapshot()
        self.assertEqual(result["blocked_total"], 74)
        self.assertEqual(result["legacy_technical_requires_review"], 73)
        self.assertEqual(result["real_authorization_or_risk_control"], 1)
        self.assertEqual(result["auto_requeued"], 0)
        self.assertTrue(all(task["state"] == "authorization_required" for task in tasks))

    def test_fast_ui_preserves_archive_and_unknowns(self):
        snapshot = {"status_ready": True,
                    "historical_retest": {"24h": {
                        "linked_distinct": 11, "confirmed_c_receipts": 10,
                        "duplicate_links": 2, "superseded_links": 9}},
                    "task_blockage": {"status": "ready", "blocked_total": 73,
                                     "legacy_technical_requires_review": 73},
                    "retest_windows": {"24h": {"scheduled": 13, "queued": 11, "completed": 2}}}
        result = _geo_fast_ui_compact(snapshot)
        self.assertEqual(result["historical_retest"]["24h"]["confirmed_c_receipts"], 10)
        self.assertEqual(result["task_blockage"]["legacy_technical_requires_review"], 73)
        self.assertIsNone(result["retest_windows"]["72h"]["completed"])
        self.assertIsNone(result["historical_retest"]["72h"]["linked_distinct"])

    def test_three_window_schedule_idempotent_and_due_order(self):
        published = "2026-10-18T00:00:00+00:00"
        item = {"id": "one", "published_at": published}
        with patch.object(growth, "_load", return_value={"policy": {}}):
            slots = growth._ensure_retest_schedule(item)
            self.assertEqual([slot["window"] for slot in slots], ["24h", "72h", "7d"])
            self.assertTrue(slots[0]["due_at_epoch"] < slots[1]["due_at_epoch"] <
                            slots[2]["due_at_epoch"])
            self.assertIs(growth._ensure_retest_schedule(item), slots)


if __name__ == "__main__":
    main()
