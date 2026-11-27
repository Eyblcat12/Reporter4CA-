"""Reporter Pro backend tests.

On a user's machine ``apps/backend/data/`` holds the real ``reporter.db`` with
customer report history. Tests must use a throw-away ``Database`` instead.
Opening the real one used to go unnoticed: one test reached it through
``get_db()``, and the suite's exit then checkpointed the user's WAL. The guard
below makes any test that opens an SQLite file under that folder fail at once.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path
from urllib.parse import unquote, urlsplit

REAL_DATA_DIR = (Path(__file__).resolve().parents[1] / "apps" / "backend" / "data").resolve()
_TESTS_DIR = Path(__file__).resolve().parent


def _calling_test() -> str:
    frame = sys._getframe(2)
    while frame is not None:
        filename = Path(frame.f_code.co_filename)
        if filename.parent == _TESTS_DIR and filename.name.startswith("test_"):
            return f"{filename.stem}.{frame.f_code.co_name}:{frame.f_lineno}"
        frame = frame.f_back
    return "outside a test function"


def _database_path(database: object) -> Path | None:
    try:
        target = os.fsdecode(os.fspath(database))
    except TypeError:
        return None
    if target.startswith("file:"):
        target = unquote(urlsplit(target).path)
        # file:///C:/... on Windows
        if len(target) > 2 and target[0] == "/" and target[2] == ":":
            target = target[1:]
    if target in ("", ":memory:"):
        return None
    try:
        return Path(target).resolve()
    except (OSError, ValueError):
        return None


def _refuse_real_database(event: str, args: tuple) -> None:
    if event != "sqlite3.connect" or not args:
        return
    path = _database_path(args[0])
    if path is not None and (path == REAL_DATA_DIR or REAL_DATA_DIR in path.parents):
        message = (
            f"A test tried to open the real Reporter Pro database folder ({path}) "
            f"from {_calling_test()}. Use a temporary core.database.Database instead."
        )
        # API handlers can wrap this error (e.g. into HTTP 500), so also say it here.
        sys.stderr.write(f"[tests] {message}\n")
        raise RuntimeError(message)


sys.addaudithook(_refuse_real_database)
