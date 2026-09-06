from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.check_template_studio_merge import (
    ChangedPath,
    forbidden_tracked_violations,
    parse_name_status_z,
    protected_diff_violations,
    repository_violations,
    static_contract_violations,
)

ROOT = Path(__file__).resolve().parents[1]


class TemplateStudioMergeGateTests(unittest.TestCase):
    def test_current_repository_passes_static_and_tracked_artifact_contract(self) -> None:
        self.assertEqual([], repository_violations(ROOT))

    def test_default_templates_and_legacy_renderer_are_protected(self) -> None:
        changes = [
            ChangedPath("M", "apps/backend/templates/full/report_full_default.docx"),
            ChangedPath("M", "apps/backend/core/report_generator.py"),
            ChangedPath("A", "apps/backend/core/template_pack.py"),
        ]
        self.assertEqual(
            [
                "M\tapps/backend/core/report_generator.py",
                "M\tapps/backend/templates/full/report_full_default.docx",
            ],
            protected_diff_violations(changes),
        )

    def test_rename_checks_both_old_and_new_paths(self) -> None:
        payload = (
            b"R100\0apps/backend/templates/full/old.docx\0"
            b"apps/backend/templates/full/new.docx\0A\0docs/note.md\0"
        )
        self.assertEqual(
            [
                ChangedPath("R100", "apps/backend/templates/full/old.docx"),
                ChangedPath("R100", "apps/backend/templates/full/new.docx"),
                ChangedPath("A", "docs/note.md"),
            ],
            parse_name_status_z(payload),
        )
        self.assertEqual(2, len(protected_diff_violations(parse_name_status_z(payload))))

    def test_runtime_and_customer_artifacts_are_rejected_when_tracked(self) -> None:
        self.assertEqual(
            [
                ".env",
                "apps/backend/data/template_studio/catalog/index.json",
                "artifacts/customer.generated.docx",
                "logs/backend.log",
            ],
            forbidden_tracked_violations(
                [
                    "docs/README.md",
                    "apps/backend/data/template_studio/catalog/index.json",
                    "logs/backend.log",
                    ".env",
                    "artifacts/customer.generated.docx",
                ]
            ),
        )

    def test_static_contract_detects_hidden_studio_and_runtime_import(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / ".env.example").write_text(
                "AUTO_REPORT_TEMPLATE_PACKS=0\n",
                encoding="utf-8",
            )
            config = root / "apps/backend/core/config.py"
            config.parent.mkdir(parents=True)
            config.write_text('os.getenv("AUTO_REPORT_TEMPLATE_PACKS", "0")\n', encoding="utf-8")
            for relative in (
                "apps/backend/core/report_generator.py",
                "apps/backend/core/report_orchestrator.py",
                "apps/backend/core/report_snapshot.py",
            ):
                path = root / relative
                path.write_text(
                    "from core.template_pack import inspect_template_pack\n", encoding="utf-8"
                )
            app = root / "apps/frontend/src/App.jsx"
            app.parent.mkdir(parents=True)
            app.write_text(
                "const enabled = import.meta.env.VITE_TEMPLATE_STUDIO;\n", encoding="utf-8"
            )
            sidebar = root / "apps/frontend/src/components/layout/Sidebar.jsx"
            sidebar.parent.mkdir(parents=True, exist_ok=True)
            sidebar.write_text("const sidebar = [];\n", encoding="utf-8")
            violations = static_contract_violations(root)
        self.assertEqual(8, len(violations))
        self.assertTrue(any("AUTO_REPORT_TEMPLATE_PACKS=1" in item for item in violations))
        self.assertTrue(any("available (1)" in item for item in violations))
        self.assertTrue(any("build flag" in item for item in violations))
        self.assertTrue(any("isolated Template Studio route" in item for item in violations))
        self.assertTrue(any("sidebar" in item for item in violations))
        self.assertEqual(3, sum("Legacy module" in item for item in violations))


if __name__ == "__main__":
    unittest.main()
