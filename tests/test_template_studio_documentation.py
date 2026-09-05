from __future__ import annotations

import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADMIN_GUIDE = ROOT / "docs" / "TEMPLATE_ADMIN_GUIDE.md"
ROLLBACK_RUNBOOK = ROOT / "docs" / "TEMPLATE_STUDIO_MIGRATION_ROLLBACK.md"
ROUTES = ROOT / "apps" / "backend" / "api" / "routes.py"


class TemplateStudioDocumentationTests(unittest.TestCase):
    def test_operator_documents_exist_and_are_linked_from_indexes(self) -> None:
        self.assertTrue(ADMIN_GUIDE.is_file())
        self.assertTrue(ROLLBACK_RUNBOOK.is_file())
        combined_indexes = "\n".join(
            (ROOT / path).read_text(encoding="utf-8")
            for path in ("README.md", "docs/README.md", "docs/TEMPLATE_STUDIO_STATUS.md")
        )
        self.assertIn("TEMPLATE_ADMIN_GUIDE.md", combined_indexes)
        self.assertIn("TEMPLATE_STUDIO_MIGRATION_ROLLBACK.md", combined_indexes)

    def test_docs_preserve_default_off_and_legacy_renderer_contract(self) -> None:
        text = "\n".join(
            path.read_text(encoding="utf-8")
            for path in (ADMIN_GUIDE, ROLLBACK_RUNBOOK, ROOT / "docs" / "TEMPLATE_PACKS.md")
        )
        self.assertIn("AUTO_REPORT_TEMPLATE_PACKS=0", text)
        self.assertIn("Legacy Renderer", text)
        self.assertIn("selectionIntegrated: false", text)
        self.assertRegex(text, r"(?i)(không|not).*?(dropdown|Generate)")
        env = (ROOT / ".env.example").read_text(encoding="utf-8")
        self.assertRegex(env, r"(?m)^AUTO_REPORT_TEMPLATE_PACKS=0$")

    def test_documented_concrete_template_pack_endpoints_exist(self) -> None:
        route_text = ROUTES.read_text(encoding="utf-8")
        documented = ADMIN_GUIDE.read_text(encoding="utf-8") + ROLLBACK_RUNBOOK.read_text(
            encoding="utf-8"
        )
        endpoints = set(re.findall(r"/api(/template-packs/[A-Za-z0-9_{}./-]+)", documented))
        self.assertGreaterEqual(len(endpoints), 7)
        normalized_routes = route_text.replace("workspace_id", "workspace_id").replace(
            "pack_id", "pack_id"
        )
        for endpoint in endpoints:
            route_path = endpoint.removeprefix("/template-packs")
            self.assertIn(
                f'"/template-packs{route_path}"',
                normalized_routes,
                msg=f"Documented endpoint is not declared by the API: /api{endpoint}",
            )

    def test_rollback_runbook_requires_integrity_and_recovery_controls(self) -> None:
        text = ROLLBACK_RUNBOOK.read_text(encoding="utf-8").lower()
        for required in (
            "preflight",
            "dry-run",
            "sha-256",
            "expectedrevision",
            "confirmation token",
            "checkpoint",
            "scripts/check.ps1",
            "auto_report_template_packs=0",
        ):
            self.assertIn(required, text)


if __name__ == "__main__":
    unittest.main()
