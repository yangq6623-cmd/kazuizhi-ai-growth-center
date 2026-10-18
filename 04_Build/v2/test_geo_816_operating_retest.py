"""Isolated regression; no real browser sends, API calls or production state."""
import sys
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / '05_V2.0.0_Source'))
from core import geo_autonomy as auto, geo_validation as geo
from integrations import geo_cloud_executor as cloud
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


if __name__ == '__main__':
    main()
