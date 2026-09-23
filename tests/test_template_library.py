import base64
import hashlib
import io
import sqlite3
import sys
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

from docx import Document

from tests import test_api_integration

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "apps" / "backend"))
from core.template_library import TemplateLibrary  # noqa: E402


class TemplateLibraryTests(unittest.TestCase):
    def test_rejects_mismatch_without_records_and_paginates(self):
        with tempfile.TemporaryDirectory() as directory:
            library = TemplateLibrary(Path(directory) / "library.sqlite3")
            with self.assertRaises(ValueError):
                library.remember(b"x", "bad.docx", {"templateSha256": "0" * 64})
            self.assertEqual(library.list()["total"], 0)
            for index in range(3):
                source = str(index).encode()
                library.remember(
                    source,
                    f"sample-{index}.docx",
                    {
                        "templateSha256": hashlib.sha256(source).hexdigest(),
                        "reportType": "full",
                        "schemaVersion": "1",
                    },
                )
            first = library.list(limit=2)
            last = library.list(limit=2, offset=2)
            self.assertTrue(first["hasMore"])
            self.assertFalse(last["hasMore"])
            self.assertEqual(len({item["sha256"] for item in first["items"] + last["items"]}), 3)

    def test_dedup_integrity_and_persistence(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "library.sqlite3"
            library = TemplateLibrary(path)
            source = b"fixture"
            digest = hashlib.sha256(source).hexdigest()
            analysis = {"templateSha256": digest, "reportType": "full", "schemaVersion": "1"}
            library.remember(source, "example.docx", analysis, workspace_id="one")
            library.remember(
                source,
                "example.docx",
                {**analysis, "reportType": "server_only"},
                workspace_id="two",
            )
            restored = TemplateLibrary(path)
            self.assertEqual(restored.list()["total"], 1)
            self.assertEqual(restored.source(digest)[1], source)
            self.assertEqual(len(restored.analyses(digest)), 2)
            self.assertEqual(restored.list(query="missing")["total"], 0)
            with closing(sqlite3.connect(path)) as db, db:
                db.execute("UPDATE templates SET source=?", (b"corrupt",))
            with self.assertRaises(ValueError):
                restored.source(digest)
            with self.assertRaises(ValueError):
                restored.source("../invalid")

    def test_future_schema_is_not_downgraded(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "library.sqlite3"
            with closing(sqlite3.connect(path)) as db, db:
                db.execute("PRAGMA user_version=2")
            with self.assertRaises(ValueError):
                TemplateLibrary(path).list()


class TemplateLibraryApiTests(unittest.TestCase):
    setUp = test_api_integration.ApiIntegrationTests.setUp
    tearDown = test_api_integration.ApiIntegrationTests.tearDown

    def test_analysis_saved_separately_and_reusable(self):
        document = Document()
        document.add_heading("Independent source", 1)
        output = io.BytesIO()
        document.save(output)
        encoded = base64.b64encode(output.getvalue()).decode()
        with patch("api.routes.template_packs_enabled", return_value=True):
            result = self.client.post(
                "/api/template-packs/analyze-template",
                json={
                    "filename": "Independent.docx",
                    "contentBase64": encoded,
                    "reportType": "full",
                },
            )
            self.assertEqual(result.status_code, 200, result.text)
            digest = result.json()["templateSha256"]
            listing = self.client.get("/api/template-packs/library").json()
            self.assertEqual(listing["total"], 1)
            saved = self.client.get(f"/api/template-packs/library/{digest}")
            self.assertEqual(saved.json()["contentBase64"], encoded)
            self.assertEqual(saved.json()["analyses"][0], result.json())
            workspace = self.template_studio.create(
                output.getvalue(),
                report_type="full",
                profile_id="library-test",
                display_name="Library test",
            )
            with self.template_studio.library.connect() as db:
                db.execute("DELETE FROM workspace_sources")
            listing = self.client.get("/api/template-packs/library").json()
            self.assertIn(workspace["workspaceId"], listing["items"][0]["workspaceIds"])
            self.assertTrue(self.template_studio.library.path.is_file())
        with patch("api.routes.template_packs_enabled", return_value=False):
            self.assertEqual(self.client.get("/api/template-packs/library").status_code, 404)
