"""The test package refuses to open the app's real data folder."""

from __future__ import annotations

import io
import sqlite3
import tempfile
import unittest
from contextlib import redirect_stderr
from pathlib import Path
from urllib.parse import quote

from tests import REAL_DATA_DIR


class RealDataGuardTests(unittest.TestCase):
    def test_opening_a_database_in_the_real_data_folder_fails(self) -> None:
        # The folder below does not exist: if the guard were missing, connect
        # would fail with OperationalError and create nothing.
        probe = REAL_DATA_DIR / "__test_guard_probe__" / "reporter.db"
        targets = (
            str(probe),
            probe,
            f"file:{probe.as_posix()}?mode=ro",
            f"file:///{quote(probe.as_posix(), safe='/:')}?mode=ro",
        )
        for target in targets:
            with self.subTest(target=str(target)):
                warning = io.StringIO()
                with (
                    redirect_stderr(warning),
                    self.assertRaisesRegex(RuntimeError, "real Reporter Pro database"),
                ):
                    sqlite3.connect(target, uri=str(target).startswith("file:"))
                # The warning names the test, even if an API handler wraps the error.
                self.assertIn(
                    "from test_real_data_guard.test_opening_a_database", warning.getvalue()
                )
        self.assertFalse(probe.parent.exists())

    def test_temporary_and_in_memory_databases_still_open(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            connection = sqlite3.connect(Path(temporary) / "reporter.db")
            connection.close()
        sqlite3.connect(":memory:").close()


if __name__ == "__main__":
    unittest.main()
