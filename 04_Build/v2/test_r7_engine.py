"""Focused checks for first-run R6 migration and audit corruption handling."""

import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "05_V2.0.0_Source"))
from core import r7_engine  # noqa: E402
from core.storage import data_root  # noqa: E402


class R7EngineTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.old = os.environ.get("LOCALAPPDATA")
        os.environ["LOCALAPPDATA"] = self.temp.name

    def tearDown(self):
        if self.old is None:
            os.environ.pop("LOCALAPPDATA", None)
        else:
            os.environ["LOCALAPPDATA"] = self.old
        self.temp.cleanup()

    def test_migration_preserves_r6_and_is_idempotent(self):
        root = data_root()
        old_tasks = root / "operations" / "tasks.json"
        old_tasks.parent.mkdir(parents=True)
        old_tasks.write_bytes(b'{"owner":"R6"}\n')
        marker = r7_engine.migrate_r6()
        backup = root / "r7" / "backup_r6" / "operations" / "tasks.json"
        self.assertEqual(marker["copied"], ["operations/tasks.json"])
        self.assertEqual(backup.read_bytes(), old_tasks.read_bytes())
        old_tasks.write_bytes(b'{"owner":"updated"}\n')
        self.assertEqual(r7_engine.migrate_r6(), marker)
        self.assertEqual(backup.read_bytes(), b'{"owner":"R6"}\n')

    def test_corrupt_audit_blocks_task_changes(self):
        r7_engine.migrate_r6()
        audit = data_root() / "r7" / "audit.json"
        audit.write_text("{broken", encoding="utf-8")
        self.assertEqual(r7_engine.audit_history()["integrity"], "failed")
        with self.assertRaisesRegex(ValueError, "审计记录校验失败"):
            r7_engine.create_job({"title": "must not be created"})
        self.assertFalse((data_root() / "r7" / "jobs.json").exists())


if __name__ == "__main__":
    unittest.main()
