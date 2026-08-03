from __future__ import annotations

import json
import sqlite3
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path

from docx import Document


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "backend"
sys.path.insert(0, str(BACKEND))

from core.database import Database  # noqa: E402
from core.workspace_backup import create_workspace_backup  # noqa: E402


class WorkspaceBackupTests(unittest.TestCase):
    def test_backup_contains_consistent_database_templates_and_manifest(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            database = Database(root / "data" / "reporter.db")
            database.initialize()

            template_dir = root / "templates"
            template_path = template_dir / "summary" / "summary.docx"
            template_path.parent.mkdir(parents=True)
            document = Document()
            document.add_heading("Summary", level=1)
            document.save(template_path)
            (template_dir / "~$summary.docx").write_bytes(b"word-lock")

            template_id = database.add_template(
                name="Summary",
                filename="summary.docx",
                file_path=str(template_path),
                report_type="summary",
            )
            preset_id = database.save_preset(
                name="Team preset",
                settings={"organization": "Example"},
                template_id=template_id,
            )
            database.add_report(
                title="Assessment",
                report_type="summary",
                row_count=3,
                preset_id=preset_id,
                template_id=template_id,
            )

            output = root / "backup.zip"
            manifest = create_workspace_backup(
                database,
                template_dir,
                output,
                app_version="test-version",
            )

            self.assertTrue(output.exists())
            self.assertEqual(manifest["schemaVersion"], 1)
            self.assertEqual(manifest["appVersion"], "test-version")
            self.assertEqual(manifest["database"]["schemaVersion"], 9)
            self.assertEqual(
                manifest["database"]["records"],
                {"templates": 1, "presets": 1, "report_history": 1},
            )
            self.assertEqual(len(manifest["templates"]), 1)

            with zipfile.ZipFile(output) as archive:
                names = set(archive.namelist())
                self.assertEqual(
                    names,
                    {"database/reporter.db", "templates/summary/summary.docx", "manifest.json"},
                )
                archived_manifest = json.loads(archive.read("manifest.json"))
                self.assertEqual(archived_manifest, manifest)

                snapshot = root / "snapshot.db"
                snapshot.write_bytes(archive.read("database/reporter.db"))
                connection = sqlite3.connect(snapshot)
                try:
                    self.assertEqual(
                        connection.execute("SELECT name FROM presets").fetchone()[0],
                        "Team preset",
                    )
                finally:
                    connection.close()

            database.close()


if __name__ == "__main__":
    unittest.main()
