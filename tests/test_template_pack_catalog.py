from __future__ import annotations

import hashlib
import io
import tempfile
import unittest
from pathlib import Path

from docx import Document

from apps.backend.core.template_pack import inspect_template_pack
from apps.backend.core.template_pack_catalog import (
    TemplatePackCatalog,
    TemplatePackCatalogError,
    TemplatePackCatalogRevisionConflict,
    TemplatePackValidationEvidence,
    build_template_pack,
)
from apps.backend.core.template_profiles import COMMON_REQUIREMENTS, REPORT_REQUIREMENTS


def _template_bytes(label: str = "Customer template") -> bytes:
    document = Document()
    document.add_heading(label, level=1)
    output = io.BytesIO()
    document.save(output)
    return output.getvalue()


def _complete_workspace(template: bytes, *, version: str = "1.0.0") -> dict:
    report_type = "summary"
    slots = []
    for index, semantic in enumerate(REPORT_REQUIREMENTS[report_type]):
        requirement = COMMON_REQUIREMENTS[semantic]
        slots.append(
            {
                "id": semantic.replace(".", "_"),
                "semantic": semantic,
                "renderer": requirement.renderer,
                "source": requirement.source,
                "anchor": {"kind": "token", "value": f"{{{{SLOT_{index}}}}}"},
                "repeat": "once",
                "fields": [
                    {"source": field, "target": f"column:{field_index + 1}"}
                    for field_index, field in enumerate(requirement.required_fields)
                ],
            }
        )
    return {
        "workspaceSchemaVersion": "1.0",
        "workspaceId": "a" * 32,
        "profileId": "customer-summary",
        "displayName": "Customer Summary",
        "version": version,
        "reportType": report_type,
        "templateSha256": hashlib.sha256(template).hexdigest(),
        "status": "mapping_complete",
        "slots": slots,
    }


def _evidence() -> TemplatePackValidationEvidence:
    return TemplatePackValidationEvidence(
        fixture_id="summary-baseline-v1",
        fixture_passed=True,
        integrity_passed=True,
        visual_approved=True,
        validator_version="template-studio-test/1.0",
        validated_at="2026-08-26T00:00:00Z",
    )


class TemplatePackBuilderTests(unittest.TestCase):
    def test_build_is_deterministic_and_self_inspecting(self) -> None:
        template = _template_bytes()
        workspace = _complete_workspace(template)

        first = build_template_pack(workspace, template, _evidence())
        second = build_template_pack(workspace, template, _evidence())
        inspection = inspect_template_pack(first)

        self.assertEqual(first, second)
        self.assertTrue(inspection.publishable)
        self.assertEqual(inspection.pack_id, "customer-summary")
        self.assertEqual(inspection.version, "1.0.0")

    def test_build_rejects_incomplete_mapping_and_untrusted_failure(self) -> None:
        template = _template_bytes()
        workspace = _complete_workspace(template)
        workspace["status"] = "mapping_incomplete"
        with self.assertRaisesRegex(TemplatePackCatalogError, "100% mapping"):
            build_template_pack(workspace, template, _evidence())

        workspace["status"] = "mapping_complete"
        failed = TemplatePackValidationEvidence(
            fixture_id="summary-baseline-v1",
            fixture_passed=False,
            integrity_passed=True,
            visual_approved=True,
            validator_version="template-studio-test/1.0",
        )
        with self.assertRaisesRegex(TemplatePackCatalogError, "must pass"):
            build_template_pack(workspace, template, failed)

    def test_build_rejects_changed_template_source(self) -> None:
        template = _template_bytes()
        workspace = _complete_workspace(template)

        with self.assertRaisesRegex(TemplatePackCatalogError, "checksums"):
            build_template_pack(workspace, _template_bytes("Changed"), _evidence())


class TemplatePackCatalogTests(unittest.TestCase):
    def test_install_activate_and_rollback_are_revisioned(self) -> None:
        template = _template_bytes()
        pack_v1 = build_template_pack(_complete_workspace(template), template, _evidence())
        pack_v2 = build_template_pack(
            _complete_workspace(template, version="2.0.0"), template, _evidence()
        )
        with tempfile.TemporaryDirectory() as temporary:
            catalog = TemplatePackCatalog(Path(temporary) / "catalog")

            installed_v1 = catalog.install(pack_v1, expected_revision=0)
            installed_v2 = catalog.install(pack_v2, expected_revision=1)
            activated = catalog.activate("customer-summary", "2.0.0", expected_revision=2)
            rolled_back = catalog.rollback("customer-summary", "1.0.0", expected_revision=3)

            self.assertEqual(installed_v1["revision"], 1)
            self.assertEqual(installed_v2["revision"], 2)
            self.assertEqual(activated["packs"]["customer-summary"]["activeVersion"], "2.0.0")
            self.assertEqual(rolled_back["packs"]["customer-summary"]["activeVersion"], "1.0.0")
            self.assertEqual(rolled_back["audit"][-1]["action"], "pack.rolled_back")
            self.assertFalse(rolled_back["selectionIntegrated"])
            self.assertTrue(rolled_back["legacyRendererUnchanged"])
            self.assertEqual(catalog.pack_bytes("customer-summary", "1.0.0"), pack_v1)

    def test_version_is_immutable_and_stale_revision_is_rejected(self) -> None:
        template = _template_bytes()
        pack = build_template_pack(_complete_workspace(template), template, _evidence())
        with tempfile.TemporaryDirectory() as temporary:
            catalog = TemplatePackCatalog(Path(temporary) / "catalog")
            catalog.install(pack, expected_revision=0)

            with self.assertRaises(TemplatePackCatalogRevisionConflict):
                catalog.activate("customer-summary", "1.0.0", expected_revision=0)

            altered_template = _template_bytes("Altered customer template")
            altered = build_template_pack(
                _complete_workspace(altered_template), altered_template, _evidence()
            )
            with self.assertRaisesRegex(TemplatePackCatalogError, "immutable"):
                catalog.install(altered, expected_revision=1)

    def test_payload_tampering_is_detected_before_selection(self) -> None:
        template = _template_bytes()
        pack = build_template_pack(_complete_workspace(template), template, _evidence())
        with tempfile.TemporaryDirectory() as temporary:
            catalog = TemplatePackCatalog(Path(temporary) / "catalog")
            catalog.install(pack, expected_revision=0)
            payload = Path(temporary) / "catalog" / "packs" / "customer-summary" / "1.0.0.rptpack"
            payload.write_bytes(pack + b"tampered")

            with self.assertRaisesRegex(TemplatePackCatalogError, "checksum"):
                catalog.activate("customer-summary", "1.0.0", expected_revision=1)


if __name__ == "__main__":
    unittest.main()
