from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "backend"
sys.path.insert(0, str(BACKEND))

from core import database as database_module  # noqa: E402
from core.database import LATEST_SCHEMA_VERSION, Database, file_sha256  # noqa: E402


class DatabaseMigrationCheckpointTests(unittest.TestCase):
    @staticmethod
    def _baseline(path: Path) -> None:
        database = Database(path)
        database.initialize()
        database.save_preset(name="Before migration", settings={"stable": True})
        database.close()

    def test_failed_migration_restores_the_complete_pre_migration_database(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reporter.db"
            self._baseline(path)

            def migration_ten(conn: sqlite3.Connection) -> None:
                conn.execute("CREATE TABLE migration_probe(value TEXT)")
                conn.execute("INSERT INTO migration_probe(value) VALUES('partial')")

            def migration_eleven(conn: sqlite3.Connection) -> None:
                conn.execute("CREATE TABLE migration_failure(value TEXT)")
                raise RuntimeError("planned migration failure")

            migrations = (
                *database_module._MIGRATIONS,
                (10, "probe", migration_ten),
                (11, "fail", migration_eleven),
            )
            database = Database(path)
            with patch.object(database_module, "_MIGRATIONS", migrations):
                with self.assertRaisesRegex(RuntimeError, "planned migration failure"):
                    database.initialize()

            self.assertEqual(database.schema_version, LATEST_SCHEMA_VERSION)
            tables = {
                row[0]
                for row in database._get_conn().execute(
                    "SELECT name FROM sqlite_master WHERE type='table'"
                )
            }
            self.assertNotIn("migration_probe", tables)
            self.assertNotIn("migration_failure", tables)
            self.assertEqual(database.list_presets()[0]["name"], "Before migration")

            checkpoints = list((path.parent / "migration-backups").glob("*.db"))
            self.assertEqual(len(checkpoints), 1)
            checksum = checkpoints[0].with_suffix(".db.sha256").read_text(encoding="ascii")
            self.assertTrue(checksum.startswith(file_sha256(checkpoints[0])))
            database.close()

    def test_successful_migrations_are_atomic_and_keep_three_checkpoints(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "reporter.db"
            self._baseline(path)
            database = Database(path)

            for index in range(5):
                checkpoint = database._create_migration_checkpoint(9 + index, 10 + index)
                self.assertTrue(checkpoint.is_file())

            checkpoint_dir = path.parent / "migration-backups"
            self.assertEqual(len(list(checkpoint_dir.glob("*.db"))), 3)
            self.assertEqual(len(list(checkpoint_dir.glob("*.db.sha256"))), 3)
            database.close()


if __name__ == "__main__":
    unittest.main()
