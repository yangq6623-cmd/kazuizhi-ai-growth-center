"""Regression: R8 migration must not nest the immutable R7 backup."""

import os
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "05_V2.0.0_Source"))

from core import r7_engine, r8_migration  # noqa: E402
from core.storage import data_root  # noqa: E402


class R8MigrationBackupNestingTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=ROOT, ignore_cleanup_errors=True)
        self.old_local = os.environ.get("LOCALAPPDATA")
        os.environ["LOCALAPPDATA"] = self.temp.name

    def tearDown(self):
        if self.old_local is None:
            os.environ.pop("LOCALAPPDATA", None)
        else:
            os.environ["LOCALAPPDATA"] = self.old_local
        self.temp.cleanup()

    def test_r8_snapshot_excludes_r7_migration_backup(self):
        root = data_root()
        active = root / "operations" / "tasks.json"
        active.parent.mkdir(parents=True)
        active.write_text('{"items":[{"title":"preserve me"}]}', encoding="utf-8")

        r7_engine.migrate_r6()
        r7_backup = root / "r7" / "backup_r6" / "operations" / "tasks.json"
        self.assertTrue(r7_backup.is_file())

        marker = r8_migration.migrate_to_v2_2()
        self.assertEqual(marker["result"], "complete")
        self.assertIn("operations/tasks.json", marker["copied"])
        self.assertFalse(any(item.startswith("r7/backup_r6/") for item in marker["copied"]))
        self.assertFalse((root / "r8" / "backup_pre_v2_2" / "r7" / "backup_r6").exists())
        self.assertEqual(
            (root / "r8" / "backup_pre_v2_2" / "operations" / "tasks.json").read_bytes(),
            active.read_bytes(),
        )

        # The completed marker must make every later restart a no-op.
        self.assertEqual(r8_migration.migrate_to_v2_2(), marker)


if __name__ == "__main__":
    unittest.main()
