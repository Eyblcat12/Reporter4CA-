from __future__ import annotations

import sqlite3
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from docx import Document
from fastapi import HTTPException


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "backend"
sys.path.insert(0, str(BACKEND))

from api import routes  # noqa: E402
from api.models import UploadTemplateRequest  # noqa: E402
from core.database import Database  # noqa: E402
from core.template_analyzer import analyze_template  # noqa: E402


class TemplateCategoryTests(unittest.TestCase):
    def test_bundled_server_and_client_templates_have_only_required_prototypes(self) -> None:
        expected = {
            "server_only": ["inventory_server", "summary_server", "detail"],
            "client_only": ["inventory_client", "summary_client", "detail"],
        }
        for category, prototypes in expected.items():
            path = BACKEND / "templates" / category / f"report_{category}_default.docx"
            self.assertTrue(path.exists(), f"Missing bundled template: {path}")
            analysis = analyze_template(path, category)
            self.assertEqual(analysis["template_mode"], "full")
            self.assertEqual(analysis["prototype_tables"], prototypes)
            self.assertEqual(analysis["compatibility"]["status"], "compatible_with_warnings")
            self.assertEqual(analysis["compatibility"]["errors"], [])

    def test_bundled_summary_and_technical_templates_have_expected_structure(self) -> None:
        expected = {
            "summary": ["Tổng quan", "Kết quả và phân tích tổng hợp", "Kết luận và khuyến nghị"],
            "technical": ["Tổng quan", "Phân tích chi tiết", "Kết luận và khuyến nghị"],
        }
        for category, expected_headings in expected.items():
            path = BACKEND / "templates" / category / f"report_{category}_default.docx"
            self.assertTrue(path.exists(), f"Missing bundled template: {path}")
            document = Document(path)
            heading_1 = [
                paragraph.text
                for paragraph in document.paragraphs
                if paragraph.style.name == "Heading 1"
            ]
            self.assertEqual(heading_1, expected_headings)

    def test_existing_database_is_migrated_with_report_type(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            db_path = Path(directory) / "legacy.db"
            connection = sqlite3.connect(db_path)
            connection.execute("CREATE TABLE templates (id TEXT PRIMARY KEY, name TEXT)")
            connection.commit()
            connection.close()

            database = Database(db_path)
            database.initialize()
            columns = {
                row[1]
                for row in database._get_conn().execute("PRAGMA table_info(templates)").fetchall()
            }
            self.assertIn("report_type", columns)
            self.assertEqual(database.schema_version, 9)
            migrations = database._get_conn().execute(
                "SELECT version, name FROM schema_migrations ORDER BY version"
            ).fetchall()
            self.assertEqual(
                [tuple(row) for row in migrations],
                [
                    (1, "template_report_type"),
                    (2, "query_indexes"),
                    (3, "report_execution_metrics"),
                    (4, "template_compatibility"),
                    (5, "template_versions"),
                    (6, "detection_rules"),
                    (7, "detection_rule_versions"),
                    (8, "relocated_template_paths"),
                    (9, "report_job_history"),
                ],
            )
            database.close()

    def test_relocated_template_paths_are_repaired_without_deleting_files(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            current_templates = root / "apps" / "backend" / "templates"
            current_templates.mkdir(parents=True)
            current_file = current_templates / "report_template.docx"
            current_file.write_bytes(b"template")
            old_file = root / "reporter-backend" / "templates" / current_file.name

            db_path = root / "legacy-path.db"
            database = Database(db_path)
            with patch("core.database._TEMPLATE_DIR", current_templates):
                database.initialize()
                template_id = database.add_template(
                    name="Legacy",
                    filename=current_file.name,
                    file_path=str(old_file),
                )
                database._execute_commit(
                    "DELETE FROM schema_migrations WHERE version = 8"
                )
                database.close()

                migrated = Database(db_path)
                migrated.initialize()
                template = migrated.get_template(template_id)

            self.assertEqual(Path(template["file_path"]), current_file.resolve())
            self.assertTrue(current_file.exists())
            migrated.close()

    def test_defaults_are_independent_for_each_report_type(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            database = Database(Path(directory) / "templates.db")
            database.initialize()
            full_id = database.add_template(
                name="Full", filename="full.docx", file_path="full.docx", report_type="full"
            )
            server_id = database.add_template(
                name="Server", filename="server.docx", file_path="server.docx", report_type="server_only"
            )
            database.set_default_template(full_id)
            database.set_default_template(server_id)

            self.assertEqual(database.get_default_template("full")["id"], full_id)
            self.assertEqual(database.get_default_template("server_only")["id"], server_id)
            database.close()

    def test_upload_model_accepts_report_type_alias(self) -> None:
        request = UploadTemplateRequest(
            filename="ir.docx",
            contentBase64="placeholder",
            reportType="incident_response",
            isDefault=True,
        )
        self.assertEqual(request.report_type.value, "incident_response")
        self.assertTrue(request.is_default)

    def test_managed_template_path_rejects_database_paths_outside_template_root(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            template_root = root / "templates"
            managed = template_root / "summary" / "managed.docx"
            outside = root / "outside.docx"
            with patch.object(routes, "TEMPLATES_DIR", template_root):
                self.assertEqual(routes._managed_template_path(managed), managed.resolve())
                with self.assertRaises(HTTPException) as context:
                    routes._managed_template_path(outside)
                self.assertEqual(context.exception.status_code, 409)


if __name__ == "__main__":
    unittest.main()
