"""R7 Block A acceptance: stability, durable user data, migration and identity."""

import importlib
import json
import os
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SOURCE = ROOT / "05_V2.0.0_Source"
sys.path.insert(0, str(SOURCE))

from analytics import operation_summary  # noqa: E402
from core import r7_engine  # noqa: E402
from core.storage import data_root, read_json, write_json  # noqa: E402
from core.version import BUILD_ID  # noqa: E402
from memory import memory_store  # noqa: E402
from operations import workspace  # noqa: E402
from planning import tomorrow_plan  # noqa: E402
from promotion import content_center  # noqa: E402


class R7BlockAAcceptance(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old_localappdata = os.environ.get("LOCALAPPDATA")
        os.environ["LOCALAPPDATA"] = self.temp.name

    def tearDown(self):
        if self.old_localappdata is None:
            os.environ.pop("LOCALAPPDATA", None)
        else:
            os.environ["LOCALAPPDATA"] = self.old_localappdata
        self.temp.cleanup()

    def test_real_user_data_survives_restart_style_reload(self):
        r7_engine.migrate_r6()

        task = workspace.add_task({"title": "R7-A 持久化任务", "priority": "high", "category": "验收"})
        content_center.add_keyword({"keyword": "涟水空调维修验收词", "region": "涟水", "category": "家电维修"})
        content_center.generate_seo({
            "region": "涟水", "service": "家电维修", "keyword": "涟水空调维修验收词",
            "audience": "本地用户", "evidence": "",
        })
        operation_summary.save_summary(["完成 R7-A 数据持久化验收"])
        memory_store.remember("验收事实", "R7-A 持久化测试已写入", "自动化验收")

        job = r7_engine.create_job({"kind": "manual_task", "title": "R7-A 非资金自动任务闭环"})
        self.assertEqual(job["state"], "queued")
        self.assertEqual(job["approved_by"], "autonomy_policy")
        r7_engine.run_due_jobs()
        saved_before_reload = next(x for x in r7_engine.list_jobs()["items"] if x["id"] == job["id"])
        self.assertEqual(saved_before_reload["state"], "completed")
        self.assertEqual(saved_before_reload["progress"], 100)

        importlib.reload(workspace)
        importlib.reload(content_center)
        importlib.reload(operation_summary)
        importlib.reload(tomorrow_plan)
        importlib.reload(memory_store)
        importlib.reload(r7_engine)

        self.assertTrue(any(x["id"] == task["id"] for x in workspace.list_tasks()["items"]))
        self.assertTrue(any(x["keyword"] == "涟水空调维修验收词" for x in content_center.list_keywords()["items"]))
        self.assertTrue(any(x["kind"] == "SEO内容草稿" for x in content_center.history()["items"]))
        self.assertIn("完成 R7-A 数据持久化验收", operation_summary.build_summary()["completed_items"])
        self.assertTrue(any(x["statement"] == "R7-A 持久化测试已写入" for x in memory_store.get_memory()["entries"]))
        saved_job = next(x for x in r7_engine.list_jobs()["items"] if x["id"] == job["id"])
        self.assertEqual(saved_job["state"], "completed")
        self.assertEqual(saved_job["progress"], 100)
        self.assertIsNotNone(saved_job["result"])
        self.assertEqual(r7_engine.audit_history()["integrity"], "verified")

    def test_r6_migration_snapshots_every_existing_user_namespace(self):
        seeded = {
            "operations/tasks.json": {"items": [{"title": "old task"}]},
            "operations/promotion_calendar.json": {"items": [{"theme": "old calendar"}]},
            "promotion/keywords.json": {"items": [{"keyword": "old keyword"}]},
            "promotion/history.json": {"items": [{"kind": "old draft"}]},
            "summaries/today.json": {"completed_items": ["old summary"]},
            "plans/latest_plan.json": {"tasks": [{"title": "old plan"}]},
            "memory/learning_memory.json": {"entries": [{"statement": "old memory"}]},
            "memory/experiments.json": {"experiments": [{"name": "old experiment"}]},
            "integrations/config.json": {"base_url": "http://old.invalid"},
            "records/review_history.json": {"items": [{"kind": "old review"}]},
            "analytics/business_snapshot.json": {"source": "old snapshot"},
        }
        for relative, payload in seeded.items():
            write_json(relative, payload)

        marker = r7_engine.migrate_r6()
        self.assertEqual(marker["result"], "complete")
        self.assertEqual(marker["mode"], "full_copy_before_write")
        self.assertEqual(set(marker["copied"]), set(seeded))

        backup_root = data_root() / "r7" / "backup_r6"
        for relative, payload in seeded.items():
            self.assertEqual(json.loads((backup_root / relative).read_text(encoding="utf-8")), payload)

        write_json("promotion/keywords.json", {"items": [{"keyword": "new value"}]})
        self.assertEqual(r7_engine.migrate_r6(), marker)
        self.assertEqual(
            json.loads((backup_root / "promotion/keywords.json").read_text(encoding="utf-8")),
            seeded["promotion/keywords.json"],
        )

    def test_interrupted_local_job_is_requeued_automatically_on_restart(self):
        r7_engine.migrate_r6()
        job = r7_engine.create_job({"kind": "diagnostics", "title": "中断恢复测试"})
        self.assertEqual(job["state"], "queued")
        jobs = read_json("r7/jobs.json", {"items": []})
        saved = next(x for x in jobs["items"] if x["id"] == job["id"])
        saved["state"] = "running"
        write_json("r7/jobs.json", jobs)

        r7_engine.recover_interrupted()
        recovered = next(x for x in r7_engine.list_jobs()["items"] if x["id"] == job["id"])
        self.assertEqual(recovered["state"], "queued")
        self.assertIn("程序中断", recovered["error"])
        self.assertEqual(recovered["approved_by"], "autonomy_policy")
        self.assertEqual(r7_engine.audit_history()["integrity"], "verified")
        self.assertTrue(any(x["kind"] == "job_requeued_after_interrupt" for x in r7_engine.audit_history()["events"]))

    def test_atomic_json_write_leaves_valid_file_and_no_temp_residue(self):
        for index in range(30):
            write_json("stability/repeated.json", {"index": index, "payload": "数据" * 100})
        path = data_root() / "stability" / "repeated.json"
        self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["index"], 29)
        self.assertFalse(list(path.parent.glob(".*.tmp")))

    def test_frontend_backend_build_identity_is_one_value(self):
        app = (SOURCE / "web" / "app.js").read_text(encoding="utf-8")
        index = (SOURCE / "web" / "index.html").read_text(encoding="utf-8")
        web_version = (SOURCE / "web" / "WEB_VERSION.txt").read_text(encoding="utf-8")
        spec = (ROOT / "04_Build" / "kazuizhi_v2.0.0.spec").read_text(encoding="utf-8")
        self.assertIn(BUILD_ID, app)
        self.assertIn(BUILD_ID, index)
        self.assertIn(BUILD_ID, web_version)
        self.assertIn(BUILD_ID, spec)


if __name__ == "__main__":
    unittest.main()
