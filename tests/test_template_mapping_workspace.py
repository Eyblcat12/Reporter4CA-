from __future__ import annotations

import copy
import io
import json
import tempfile
import unittest
from pathlib import Path

from docx import Document

from apps.backend.core.template_mapping_workspace import (
    TemplateMappingRevisionConflict,
    TemplateMappingWorkspaceError,
    TemplateMappingWorkspaceStore,
    TemplateStudioService,
    approve_semantic_mapping,
    create_mapping_workspace,
    remove_semantic_mapping,
    workspace_profile,
)
from apps.backend.core.template_profiles import (
    COMMON_REQUIREMENTS,
    PROFILE_SCHEMA_VERSION,
    REPORT_REQUIREMENTS,
    validate_template_profile,
)


def _analysis(report_type: str = "full") -> dict:
    controls = [
        {"value": f"REPORTER_SLOT_{index}", "occurrences": 1}
        for index, _ in enumerate(REPORT_REQUIREMENTS[report_type])
    ]
    return {
        "schemaVersion": PROFILE_SCHEMA_VERSION,
        "reportType": report_type,
        "templateSha256": "a" * 64,
        "facts": {
            "contentControls": controls,
            "bookmarks": [],
            "tokens": [],
            "tokenOccurrences": {},
            "anchorConflicts": [],
        },
        "mapping": {
            "coveragePercent": 0.0,
            "approvedCount": 0,
            "requiredCount": len(controls),
            "checklist": [],
        },
    }


def _fields(semantic: str) -> list[dict[str, str]]:
    requirement = COMMON_REQUIREMENTS[semantic]
    return [
        {"source": field, "target": f"column:{index}"}
        for index, field in enumerate(requirement.required_fields, 1)
    ]


def _approve(workspace: dict, semantic: str, index: int) -> dict:
    return approve_semantic_mapping(
        workspace,
        semantic=semantic,
        anchor={"kind": "content_control", "value": f"REPORTER_SLOT_{index}"},
        fields=_fields(semantic),
        expected_revision=workspace["revision"],
        actor="template-admin",
    )


def _template_bytes(*tokens: str) -> bytes:
    document = Document()
    for token in tokens:
        document.add_paragraph(token)
    output = io.BytesIO()
    document.save(output)
    return output.getvalue()


class TemplateMappingWorkspaceTests(unittest.TestCase):
    def test_create_is_zero_coverage_and_does_not_mutate_analysis(self) -> None:
        analysis = _analysis("server_only")
        original = copy.deepcopy(analysis)

        workspace = create_mapping_workspace(
            analysis,
            profile_id="customer-server-report",
            display_name="Customer Server Report",
        )

        self.assertEqual(analysis, original)
        self.assertEqual(workspace["coveragePercent"], 0.0)
        self.assertEqual(workspace["status"], "analyzed")
        self.assertEqual(workspace["revision"], 1)
        self.assertEqual(workspace["missingSemantics"], list(REPORT_REQUIREMENTS["server_only"]))
        self.assertEqual(workspace["audit"][0]["action"], "workspace.created")

    def test_approve_mapping_advances_revision_coverage_and_audit(self) -> None:
        workspace = create_mapping_workspace(
            _analysis(), profile_id="customer-full", display_name="Customer Full"
        )

        updated = _approve(workspace, "report.title", 0)

        self.assertEqual(workspace["revision"], 1)
        self.assertEqual(updated["revision"], 2)
        self.assertEqual(updated["coveragePercent"], 10.0)
        self.assertEqual(updated["status"], "mapping_incomplete")
        self.assertEqual(updated["audit"][-1]["action"], "mapping.approved")
        self.assertEqual(updated["audit"][-1]["semantic"], "report.title")

    def test_stale_revision_is_rejected_without_changing_workspace(self) -> None:
        workspace = create_mapping_workspace(
            _analysis(), profile_id="customer-full", display_name="Customer Full"
        )
        original = copy.deepcopy(workspace)

        with self.assertRaises(TemplateMappingRevisionConflict):
            approve_semantic_mapping(
                workspace,
                semantic="report.title",
                anchor={"kind": "content_control", "value": "REPORTER_SLOT_0"},
                expected_revision=0,
            )

        self.assertEqual(workspace, original)

    def test_anchor_must_exist_once_in_analyzed_template(self) -> None:
        analysis = _analysis()
        analysis["facts"]["contentControls"][0]["occurrences"] = 2
        workspace = create_mapping_workspace(
            analysis, profile_id="customer-full", display_name="Customer Full"
        )

        with self.assertRaisesRegex(TemplateMappingWorkspaceError, "ambiguous"):
            _approve(workspace, "report.title", 0)
        with self.assertRaisesRegex(TemplateMappingWorkspaceError, "not found"):
            approve_semantic_mapping(
                workspace,
                semantic="report.title",
                anchor={"kind": "bookmark", "value": "UNKNOWN"},
                expected_revision=1,
            )

    def test_required_fields_must_be_complete_and_unique(self) -> None:
        workspace = create_mapping_workspace(
            _analysis(), profile_id="customer-full", display_name="Customer Full"
        )
        server_index = REPORT_REQUIREMENTS["full"].index("inventory.server")

        with self.assertRaisesRegex(TemplateMappingWorkspaceError, "Missing required"):
            approve_semantic_mapping(
                workspace,
                semantic="inventory.server",
                anchor={
                    "kind": "content_control",
                    "value": f"REPORTER_SLOT_{server_index}",
                },
                fields=[{"source": "hostname", "target": "column:1"}],
                expected_revision=1,
            )

    def test_complete_mapping_reaches_one_hundred_but_is_not_publishable(self) -> None:
        workspace = create_mapping_workspace(
            _analysis(), profile_id="customer-full", display_name="Customer Full"
        )
        for index, semantic in enumerate(REPORT_REQUIREMENTS["full"]):
            workspace = _approve(workspace, semantic, index)

        result = validate_template_profile(workspace_profile(workspace))

        self.assertEqual(workspace["coveragePercent"], 100.0)
        self.assertEqual(workspace["status"], "mapping_complete")
        self.assertEqual(workspace["missingSemantics"], [])
        self.assertTrue(result.mapping_complete)
        self.assertFalse(result.publishable)

    def test_remove_mapping_returns_semantic_to_missing_state(self) -> None:
        workspace = create_mapping_workspace(
            _analysis(), profile_id="customer-full", display_name="Customer Full"
        )
        workspace = _approve(workspace, "report.title", 0)

        workspace = remove_semantic_mapping(
            workspace,
            semantic="report.title",
            expected_revision=workspace["revision"],
        )

        self.assertEqual(workspace["coveragePercent"], 0.0)
        self.assertIn("report.title", workspace["missingSemantics"])
        self.assertEqual(workspace["audit"][-1]["action"], "mapping.removed")

    def test_atomic_store_roundtrip_and_tamper_detection(self) -> None:
        workspace = create_mapping_workspace(
            _analysis(), profile_id="customer-full", display_name="Customer Full"
        )
        with tempfile.TemporaryDirectory() as temporary:
            store = TemplateMappingWorkspaceStore(Path(temporary) / "drafts")
            path = store.save(workspace)

            loaded = store.load(workspace["workspaceId"])

            self.assertEqual(loaded, workspace)
            self.assertEqual(list(path.parent.glob("*.tmp")), [])
            tampered = json.loads(path.read_text(encoding="utf-8"))
            tampered["displayName"] = "Tampered"
            path.write_text(json.dumps(tampered), encoding="utf-8")
            with self.assertRaisesRegex(TemplateMappingWorkspaceError, "checksum"):
                store.load(workspace["workspaceId"])

    def test_studio_service_pins_source_and_serializes_revision_updates(self) -> None:
        source = _template_bytes("{{REPORT_TITLE}}", "{{OVERVIEW}}")
        with tempfile.TemporaryDirectory() as temporary:
            service = TemplateStudioService(Path(temporary) / "studio")
            workspace = service.create(
                source,
                report_type="server_only",
                profile_id="customer-server",
                display_name="Customer Server",
            )

            updated = service.approve(
                workspace["workspaceId"],
                semantic="report.title",
                anchor={"kind": "token", "value": "{{REPORT_TITLE}}"},
                fields=[],
                expected_revision=workspace["revision"],
            )

            self.assertEqual(service.source_bytes(workspace["workspaceId"]), source)
            self.assertEqual(updated["revision"], 2)
            with self.assertRaises(TemplateMappingRevisionConflict):
                service.approve(
                    workspace["workspaceId"],
                    semantic="overview",
                    anchor={"kind": "token", "value": "{{OVERVIEW}}"},
                    fields=[],
                    expected_revision=workspace["revision"],
                )


if __name__ == "__main__":
    unittest.main()
