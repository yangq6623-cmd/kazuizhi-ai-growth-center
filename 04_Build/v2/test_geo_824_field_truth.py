"""#824 field regressions: synthetic/read-only, no external sends or production writes."""
import sys
from pathlib import Path
from unittest import TestCase, main
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "05_V2.0.0_Source"))

from backend.r8_20_seo_geo_growth_patch import _geo_fast_ui_compact
from core import geo_growth_orchestrator as geo_growth
from core import seo_geo_growth


class FieldTruth(TestCase):
    def test_new_publication_rebases_only_untouched_future_windows(self):
        published = "2026-10-18T17:04:07+08:00"
        base = geo_growth._iso_epoch(published)
        old = base - 4 * 60 * 60
        item = {
            "published_at": published,
            "retest_schedule": [
                {"window": "24h", "due_at_epoch": old + 24 * 60 * 60,
                 "task_id": "", "signal_id": "", "completed_at": ""},
                {"window": "72h", "due_at_epoch": old + 72 * 60 * 60,
                 "task_id": "existing-task", "signal_id": "", "completed_at": ""},
                {"window": "7d", "due_at_epoch": old + 7 * 24 * 60 * 60,
                 "task_id": "done-task", "signal_id": "done-receipt",
                 "completed_at": "2026-10-18T12:00:00+08:00"},
            ],
        }
        with patch.object(geo_growth, "_load", return_value={"policy": {}}), \
             patch.object(geo_growth, "now_iso", return_value="2026-10-18T19:00:00+08:00"):
            slots = geo_growth._ensure_retest_schedule(item)
        self.assertEqual(slots[0]["due_at_epoch"], base + 24 * 60 * 60)
        self.assertEqual(slots[0]["schedule_basis_published_at"], published)
        self.assertEqual(slots[1]["due_at_epoch"], old + 72 * 60 * 60)
        self.assertEqual(slots[1]["task_id"], "existing-task")
        self.assertEqual(slots[2]["signal_id"], "done-receipt")

    def test_fast_ui_exposes_bounded_schedule_provenance(self):
        item = {
            "id": "opp", "published_at": "2026-10-18T17:04:07+08:00",
            "publication_receipt_id": "DEPLOY-1",
            "retest_schedule": [
                {"window": "24h", "due_at_epoch": 123.0, "task_id": "",
                 "signal_id": "", "completed_at": "", "private": "omit"},
            ],
        }
        result = _geo_fast_ui_compact({"status_ready": True, "opportunities": [item]})
        row = result["opportunities"][0]
        self.assertEqual(row["published_at"], item["published_at"])
        self.assertEqual(row["publication_receipt_id"], "DEPLOY-1")
        self.assertEqual(row["retest_schedule"][0]["due_at_epoch"], 123.0)
        self.assertNotIn("private", row["retest_schedule"][0])

    def test_daily_run_reconciles_all_four_daily_deltas(self):
        data = {
            "assets": [
                {"created_at": "2026-10-18T09:00:00+08:00",
                 "generated_at": "2026-10-18T09:01:00+08:00",
                 "published_at": "2026-10-18T10:00:00+08:00",
                 "submission_receipts": [{"at": "2026-10-18T10:02:00+08:00"}]},
                {"created_at": "2026-10-18T11:00:00+08:00",
                 "generated_at": "2026-10-18T11:01:00+08:00",
                 "submission_receipts": []},
            ],
            "daily_runs": [{"date": "2026-10-18", "planned": 0, "generated": 0,
                            "published": 0, "submitted": 0}],
        }
        row = seo_geo_growth._reconciled_daily_runs(data)[0]
        self.assertEqual((row["planned"], row["generated"], row["published"], row["submitted"]),
                         (2, 2, 1, 1))

    def test_scope_copy_and_stale_disabled_title_repairs_are_present(self):
        web = ROOT / "05_V2.0.0_Source" / "web"
        owner = (web / "r8_23_growth_os.js").read_text(encoding="utf-8")
        execution = (web / "operational-workbench.js").read_text(encoding="utf-8")
        workbench = (web / "r8_10_workbench.js").read_text(encoding="utf-8")
        geo = (web / "geo-growth-os.js").read_text(encoding="utf-8")
        self.assertIn("当前正式 Evidence ${Number(formalCompleted||0)}/50", owner)
        self.assertIn("本机路由调用 ${formalCalls} 次", owner)
        self.assertIn("社媒/内容平台发布", execution)
        self.assertIn("不含 SEO 公网 URL", execution)
        self.assertIn('button:not(:disabled)[data-kz-disabled-title="1"]', workbench)
        self.assertIn("公网时间", geo)
        self.assertIn("已到期待调度", geo)


if __name__ == "__main__":
    main()
