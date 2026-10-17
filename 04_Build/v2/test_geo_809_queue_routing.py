"""#809 queue routing regression (read-only and no historical replay).

Run: python 04_Build/v2/test_geo_809_queue_routing.py
"""
import importlib
import pathlib
import sys
import tempfile
import unittest
from unittest.mock import patch

ROOT = pathlib.Path(__file__).resolve().parents[2] / "05_V2.0.0_Source"
sys.path.insert(0, str(ROOT))
geo = importlib.import_module("core.geo_validation")


class RoutingTests(unittest.TestCase):
    def test_cloud_auto_api_tasks_are_not_chrome_claimable(self):
        samples = {
            "tasks": [
                {"task_id": "api-1", "state": "queued", "provider": "cloud_auto",
                 "test_method": "api", "expected_platform": ""},
                {"task_id": "old-1", "state": "authorization_required",
                 "provider": "doubao_web", "test_method": "browser",
                 "authorization_reason": "capture_failed:agent_response_timeout"},
                {"task_id": "browser-1", "state": "queued", "provider": "doubao_web",
                 "test_method": "browser", "expected_platform": "doubao_web"},
            ]
        }
        with patch.object(geo, "_load_queue", return_value=samples):
            result = geo.queue_summary()
        diagnostics = result["routing_diagnostics"]
        self.assertEqual(diagnostics["unbound_cloud_auto_api"], 1)
        self.assertEqual(diagnostics["unbound_cloud_auto_task_ids"], ["api-1"])
        self.assertFalse(diagnostics["browser_agent_can_claim_unbound_api"])
        self.assertFalse(diagnostics["mutated"])
        self.assertEqual(result["authorization_required"], 1)
        self.assertEqual(result["queued"], 2)
        self.assertEqual(len(diagnostics["queued_by_route"]), 2)


if __name__ == "__main__":
    unittest.main()
