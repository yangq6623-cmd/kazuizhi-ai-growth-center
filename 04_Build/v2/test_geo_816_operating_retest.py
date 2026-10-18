"""Isolated regression; no real browser sends, API calls or production state."""
import sys
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch
from copy import deepcopy

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '05_V2.0.0_Source'))
from core import geo_autonomy as auto, geo_validation as geo
from integrations import geo_cloud_executor as cloud
from core import geo_growth_orchestrator as growth
from backend.r8_20_seo_geo_growth_patch import _geo_fast_ui_compact


class OperatingRetest(TestCase):
    def run_controller(self, tasks):
        state = {**auto.DEFAULT, 'enabled': True, 'target': 50,
                 'cycle_started_at': '2026-10-01T00:00:00+00:00',
                 'next_cycle_at_epoch': 9999999999}
        with patch.object(auto, '_load', return_value=state), \
             patch.object(auto, '_save'), \
             patch.object(geo, '_load_queue', return_value={'tasks': tasks}), \
             patch.object(auto, '_materialize'), \
             patch.object(auto, '_completed_for_target', return_value=50), \
             patch.object(cloud, 'run_once', return_value={'ok': True, 'skipped': True}) as execute:
            result = auto.run_once()
            return result, execute.call_args

    def test_operating_windows_bypass_baseline_cooldown(self):
        for window in ('24H', '72H', '7D'):
            task = dict(task_id='new', state='queued', provider='cloud_auto',
                        test_method='api', mission_id='GEO-GROWTH-OPERATING-RETEST-' + window)
            _, call = self.run_controller([task])
            self.assertEqual(call.kwargs['task_ids'], ['new'])

    def test_failed_blocked_browser_and_backoff_are_preserved(self):
        base = dict(task_id='old', state='queued', provider='cloud_auto',
                    test_method='api', mission_id='GEO-GROWTH-OPERATING-RETEST-24H')
        for change in ({'state': 'authorization_required'}, {'state': 'failed'},
                       {'provider': 'doubao_web', 'test_method': 'browser'},
                       {'next_retry_at_epoch': 9999999999}, {'mission_id': 'baseline'}):
            result, call = self.run_controller([{**base, **change}])
            self.assertIsNone(call)
            self.assertEqual(result['reason'], 'waiting_next_monitor_cycle')

    def test_scoped_claim_cannot_consume_unrelated_queue(self):
        tasks = [dict(task_id='browser', state='queued', expected_platform=''),
                 dict(task_id='api', state='queued', expected_platform='')]
        with patch.object(geo, '_load_queue', return_value={'tasks': tasks}), \
             patch.object(geo, '_save_queue'), patch.object(geo, '_audit'):
            result = geo.claim_next_task(dict(provider='cloud_auto', test_method='api',
                real_external=True, authorization_ready=True, provider_ready=True,
                allowed_task_ids=['api']))
        self.assertEqual(result['task']['task_id'], 'api')
        self.assertEqual(tasks[0]['state'], 'queued')

    def test_compact_preserves_three_window_counts(self):
        windows = {label: {'scheduled': 13, 'queued': 10, 'completed': 2}
                   for label in ('24h', '72h', '7d')}
        self.assertEqual(_geo_fast_ui_compact({'status_ready': True,
            'retest_windows': windows})['retest_windows'], windows)

    def test_compact_preserves_per_opportunity_coverage_and_missing_values(self):
        coverage = {'completed': 1, 'target': 3, 'windows': {
            '24h': 'completed', '72h': 'scheduled', '7d': 'scheduled'}}
        result = _geo_fast_ui_compact({'status_ready': True, 'opportunities': [
            {'id': 'one', 'retest_coverage': coverage}, {'id': 'unknown'}]})
        self.assertEqual(result['opportunities'][0]['retest_coverage'], coverage)
        self.assertNotIn('retest_coverage', result['opportunities'][1])
        self.assertIsNone(result['retest_windows']['24h']['completed'])


class FieldLedgerTruth(TestCase):
    def test_legacy_timeout_classification_is_readonly_not_login(self):
        tasks = [
            dict(task_id=f"legacy-{i}", state="authorization_required",
                 authorization_reason=("capture_failed:agent_response_timeout" if i < 71
                                       else "capture_failed:signal timed out"),
                 started_at="2026-10-17T01:00:00+08:00")
            for i in range(73)
        ]
        tasks.append(dict(task_id="true-login", state="authorization_required",
                          authorization_reason="login_required"))
        prior = deepcopy(tasks)
        report = geo.classify_blocked_tasks(tasks)
        self.assertEqual(report["legacy_technical_requires_review"], 73)
        self.assertEqual(report["real_authorization_or_risk_control"], 1)
        self.assertEqual(report["blocked_total"], 74)
        self.assertEqual(report["uncertain_external_submission"], 73)
        self.assertFalse(report["mutated"])
        self.assertEqual(tasks, prior)

    def test_superseded_retest_is_retained_once_and_failed_receipt_rejected(self):
        receipt = lambda task, signal: dict(task_id=task, evidence_id=signal,
                                             evidence_level="C", official_truth=False,
                                             provider="cloud_auto")
        slot = lambda task, signal: dict(window="24h", task_id=task, signal_id=signal)
        rows = [
            dict(id="a", state="completed", retest_schedule=[slot("t1", "r1")]),
            dict(id="a-copy", state="superseded", retest_schedule=[slot("t1", "r1")]),
            dict(id="b", state="superseded", retest_schedule=[slot("t2", "r2")]),
        ]
        tasks = [dict(task_id="t1", state="succeeded"),
                 dict(task_id="t2", state="failed")]
        receipts = [receipt("t1", "r1"), receipt("t2", "r2")]
        saved = deepcopy((rows, tasks, receipts))
        result = growth._historical_retest_truth(rows, tasks, receipts)["windows"]["24h"]
        self.assertEqual(result["unique_task_refs"], 2)
        self.assertEqual(result["duplicated_opportunity_refs"], 1)
        self.assertEqual(result["superseded_refs"], 2)
        self.assertEqual(result["valid_c_receipts"], 1)
        self.assertEqual(result["failed_with_receipt"], 1)
        current = growth._retest_summary(rows, tasks=tasks, receipts=receipts)["24h"]
        self.assertEqual((current["scheduled"], current["completed"]), (1, 1))
        self.assertEqual((rows, tasks, receipts), saved)

    def test_scoped_window_task_never_claims_another_opportunity(self):
        row = lambda label: {"id": label, "question_id": "GEO50-D01",
                             "published_at": "2026-10-18T12:00:00+08:00"}
        def fake_create(**kwargs):
            return {"tasks": [{"task_id": "new-"+kwargs["mission_id"]}]}
        with patch.object(geo, "queue_summary", return_value={"tasks": []}), \
             patch.object(geo, "create_and_enqueue_plan", side_effect=fake_create) as create:
            a = growth._ensure_retest_task(row("opp-a"), {"window": "24h"})
            b = growth._ensure_retest_task(row("opp-b"), {"window": "24h"})
        self.assertNotEqual(a, b)
        self.assertIn("opp-a", a)
        self.assertIn("opp-b", b)
        self.assertEqual(create.call_count, 2)

    def test_unscoped_queued_legacy_followup_is_not_resent(self):
        row = {"id": "opp-new", "question_id": "GEO50-D01",
               "published_at": "2026-10-18T12:00:00+08:00"}
        legacy = {"provider": "cloud_auto", "question_id": "GEO50-D01",
                  "mission_id": "GEO-GROWTH-OPERATING-RETEST-24H",
                  "state": "queued", "created_at": "2026-10-18T12:01:00+08:00"}
        with patch.object(geo, "queue_summary", return_value={"tasks": [legacy]}), \
             patch.object(geo, "create_and_enqueue_plan") as create:
            with self.assertRaisesRegex(ValueError, "legacy_unscoped"):
                growth._ensure_retest_task(row, {"window": "24h"})
            create.assert_not_called()

    def test_failed_task_does_not_complete_operating_window(self):
        item = {"id": "opp", "state": "waiting_retest", "asset_stage": "PUBLISHED",
                "created_at": "2026-10-16T12:00:00+08:00",
                "published_at": "2026-10-17T12:00:00+08:00",
                "question_id": "GEO50-D01",
                "public_url": "https://example.org/seo/fixture/",
                "retest_schedule": [
                    {"window": "24h", "task_id": "failed-t", "due_at_epoch": 9999999999,
                     "signal_id": ""},
                    {"window": "72h", "task_id": "", "due_at_epoch": 9999999999,
                     "signal_id": ""},
                    {"window": "7d", "task_id": "", "due_at_epoch": 9999999999,
                     "signal_id": ""},
                ]}
        with patch.object(growth, "_latest_aux_for_task") as fresh, \
             patch.object(growth, "_clear_blocker"):
            growth._sync_item({"technical_blockers": []}, item, {}, {}, {},
                              task_by_id={"failed-t": {"state": "failed"}})
            fresh.assert_not_called()
        self.assertFalse(item.get("after_signal_id"))
        self.assertEqual(item["retest_coverage"]["windows"]["24h"], "blocked")

    def test_72h_and_7d_are_due_after_24h_operating_decision(self):
        item = {"id": "opp", "state": "completed", "asset_stage": "PUBLISHED",
                "created_at": "2026-10-10T12:00:00+08:00",
                "published_at": "2026-10-11T12:00:00+08:00",
                "question_id": "GEO50-D01", "after_signal_id": "r1",
                "public_url": "https://example.org/seo/fixture/",
                "retest_schedule": [
                    {"window": "24h", "task_id": "t1", "due_at_epoch": 1,
                     "signal_id": "r1", "completed_at": "2026-10-12T12:00:00+08:00"},
                    {"window": "72h", "task_id": "", "due_at_epoch": 1, "signal_id": ""},
                    {"window": "7d", "task_id": "", "due_at_epoch": 1, "signal_id": ""},
                ]}
        called = []
        def enqueue(_item, slot):
            called.append(slot["window"])
            slot["task_id"] = "t-"+slot["window"]
        with patch.object(growth, "_ensure_retest_task", side_effect=enqueue), \
             patch.object(growth, "_clear_blocker"), \
             patch.object(growth, "_record_history"):
            growth._sync_item({"technical_blockers": []}, item, {}, {}, {},
                              task_by_id={"t1": {"state": "succeeded"}})
        self.assertEqual(called, ["72h", "7d"])
        self.assertEqual(item["state"], "completed")


if __name__ == '__main__':
    main()
