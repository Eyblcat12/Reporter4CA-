from __future__ import annotations

import os
import sys
import tempfile
import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "backend"
sys.path.insert(0, str(BACKEND))

from core.database import Database  # noqa: E402
from core.scheduled_backup import ScheduledBackupManager  # noqa: E402
from core.workspace_backup import inspect_workspace_backup  # noqa: E402


class ScheduledBackupTests(unittest.TestCase):
    def test_creates_only_when_due_and_archive_passes_dry_run(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = Database(root / "reporter.db")
            database.initialize()
            templates = root / "templates"
            backup_dir = root / "backups"
            clock = [datetime(2026, 8, 17, 2, 0, tzinfo=timezone.utc)]
            manager = ScheduledBackupManager(
                lambda: database,
                templates,
                backup_dir,
                interval_hours=24,
                retention=3,
                now=lambda: clock[0],
            )

            created = manager.run_if_due()
            self.assertTrue(created["created"])
            archive = Path(created["path"])
            self.assertTrue(archive.is_file())
            preview = inspect_workspace_backup(archive, database, templates)
            self.assertTrue(preview["valid"])

            skipped = manager.run_if_due()
            self.assertEqual(skipped["reason"], "not_due")
            self.assertEqual(list(backup_dir.glob("reporter-pro-auto-*.zip")), [archive])
            database.close()

    def test_retention_removes_only_old_owned_archives(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = Database(root / "reporter.db")
            database.initialize()
            backup_dir = root / "backups"
            templates = root / "templates"
            clock = [datetime(2026, 8, 1, tzinfo=timezone.utc)]
            manager = ScheduledBackupManager(
                lambda: database,
                templates,
                backup_dir,
                interval_hours=1,
                retention=2,
                now=lambda: clock[0],
            )
            manual = backup_dir / "team-manual.zip"
            backup_dir.mkdir(parents=True)
            manual.write_bytes(b"manual")

            first = Path(manager.run_if_due()["path"])
            os.utime(first, (clock[0].timestamp(), clock[0].timestamp()))
            clock[0] += timedelta(hours=2)
            second = Path(manager.run_if_due()["path"])
            os.utime(second, (clock[0].timestamp(), clock[0].timestamp()))
            clock[0] += timedelta(hours=2)
            third_result = manager.run_if_due()

            self.assertTrue(third_result["created"])
            self.assertIn(first.name, third_result["removed"])
            self.assertFalse(first.exists())
            self.assertTrue(second.exists())
            self.assertTrue(manual.exists())
            self.assertEqual(len(list(backup_dir.glob("reporter-pro-auto-*.zip"))), 2)
            database.close()

    def test_disabled_scheduler_does_not_touch_the_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            manager = ScheduledBackupManager(
                lambda: None,
                root / "templates",
                root / "backups",
                enabled=False,
            )
            self.assertEqual(manager.run_if_due(), {"created": False, "reason": "disabled"})
            self.assertFalse((root / "backups").exists())


if __name__ == "__main__":
    unittest.main()
