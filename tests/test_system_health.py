from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "backend"
sys.path.insert(0, str(BACKEND))

from api.routes import health  # noqa: E402
from core import database as database_module  # noqa: E402
from core.config import (  # noqa: E402
    APP_VERSION,
    DEFAULT_CORS_ORIGINS,
    automatic_backup_enabled,
    automatic_backup_interval_hours,
    automatic_backup_retention,
    cors_origins,
)
from core.database import LATEST_SCHEMA_VERSION, Database, close_db  # noqa: E402


class SystemHealthTests(unittest.TestCase):
    def test_global_database_shutdown_is_idempotent(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Database(Path(directory) / "shutdown.db")
            database.initialize()
            with patch.object(database_module, "_db", database):
                close_db()
                close_db()
                self.assertIsNone(database_module._db)
                self.assertIsNone(database._conn)

    def test_health_reports_shared_app_and_database_versions(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Database(Path(directory) / "health.db")
            database.initialize()
            with patch("api.routes.get_db", return_value=database):
                response = asyncio.run(health())

            self.assertEqual(response["version"], APP_VERSION)
            self.assertEqual(response["databaseSchema"], LATEST_SCHEMA_VERSION)
            database.close()

    def test_cors_defaults_are_local_and_environment_is_deduplicated(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertEqual(cors_origins(), list(DEFAULT_CORS_ORIGINS))
            self.assertNotIn("*", cors_origins())

        with patch.dict(
            os.environ,
            {"AUTO_REPORT_CORS_ORIGINS": "http://team.local:5173/, http://team.local:5173"},
            clear=True,
        ):
            self.assertEqual(cors_origins(), ["http://team.local:5173"])

    def test_automatic_backup_settings_are_bounded_and_can_be_disabled(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertTrue(automatic_backup_enabled())
            self.assertEqual(automatic_backup_interval_hours(), 24)
            self.assertEqual(automatic_backup_retention(), 7)
        with patch.dict(
            os.environ,
            {
                "AUTO_REPORT_AUTO_BACKUP": "0",
                "AUTO_REPORT_AUTO_BACKUP_INTERVAL_HOURS": "9999",
                "AUTO_REPORT_AUTO_BACKUP_RETENTION": "0",
            },
            clear=True,
        ):
            self.assertFalse(automatic_backup_enabled())
            self.assertEqual(automatic_backup_interval_hours(), 24 * 30)
            self.assertEqual(automatic_backup_retention(), 1)


if __name__ == "__main__":
    unittest.main()
