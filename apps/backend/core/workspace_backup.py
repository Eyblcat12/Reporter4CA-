"""Create portable, local-first Reporter Pro workspace backups."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.database import Database


BACKUP_SCHEMA_VERSION = 1


def create_workspace_backup(
    database: Database,
    templates_dir: Path | str,
    output_path: Path | str,
    *,
    app_version: str = "2.0.0",
) -> dict[str, Any]:
    """Write a database/template backup archive and return its manifest."""
    template_root = Path(templates_dir).resolve()
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    template_files = sorted(
        (
            path
            for path in template_root.rglob("*.docx")
            if path.is_file() and not path.name.startswith("~$")
        ),
        key=lambda path: path.relative_to(template_root).as_posix().lower(),
    ) if template_root.exists() else []

    with tempfile.TemporaryDirectory(prefix="reporter-pro-backup-") as directory:
        snapshot_path = Path(directory) / "reporter.db"
        database.backup_to(snapshot_path)

        manifest: dict[str, Any] = {
            "schemaVersion": BACKUP_SCHEMA_VERSION,
            "app": "Reporter Pro",
            "appVersion": app_version,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "database": {
                "path": "database/reporter.db",
                "schemaVersion": database.schema_version,
                "size": snapshot_path.stat().st_size,
                "sha256": _sha256(snapshot_path),
                "records": _database_counts(snapshot_path),
            },
            "templates": [
                {
                    "path": f"templates/{path.relative_to(template_root).as_posix()}",
                    "size": path.stat().st_size,
                    "sha256": _sha256(path),
                }
                for path in template_files
            ],
            "includesGeneratedReports": False,
            "notes": [
                "Generated reports and environment files are intentionally excluded.",
                "The database may contain saved connection settings; protect this archive.",
            ],
        }

        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(snapshot_path, "database/reporter.db")
            for path in template_files:
                relative = path.relative_to(template_root).as_posix()
                archive.write(path, f"templates/{relative}")
            archive.writestr(
                "manifest.json",
                json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"),
            )

    return manifest


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _database_counts(path: Path) -> dict[str, int]:
    counts: dict[str, int] = {}
    connection = sqlite3.connect(str(path))
    try:
        for table in ("templates", "presets", "report_history"):
            exists = connection.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?",
                (table,),
            ).fetchone()
            counts[table] = (
                int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0])
                if exists
                else 0
            )
    finally:
        connection.close()
    return counts
