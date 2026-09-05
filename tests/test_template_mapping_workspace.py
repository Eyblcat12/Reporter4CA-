from __future__ import annotations

import base64
import copy
import io
import json
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from pathlib import Path

from docx import Document

from apps.backend.core.template_mapping_workspace import (
    TemplateMappingRevisionConflict,
    TemplateMappingWorkspaceError,
    TemplateMappingWorkspaceIndexChanged,
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

    def test_anchor_cannot_be_reused_by_another_semantic(self) -> None:
        workspace = create_mapping_workspace(
            _analysis(), profile_id="customer-full", display_name="Customer Full"
        )
        workspace = _approve(workspace, "report.title", 0)
        original = copy.deepcopy(workspace)

        with self.assertRaisesRegex(TemplateMappingWorkspaceError, "already mapped"):
            approve_semantic_mapping(
                workspace,
                semantic="overview",
                anchor={"kind": "content_control", "value": "REPORTER_SLOT_0"},
                expected_revision=workspace["revision"],
            )

        self.assertEqual(workspace, original)

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

    def test_concurrent_mapping_commands_allow_one_revision_winner(self) -> None:
        source = _template_bytes("{{REPORT_TITLE}}", "{{OVERVIEW}}")
        with tempfile.TemporaryDirectory() as temporary:
            service = TemplateStudioService(Path(temporary) / "studio")
            workspace = service.create(
                source,
                report_type="server_only",
                profile_id="concurrent-server",
                display_name="Concurrent Server",
            )

            def approve(semantic: str, token: str) -> str:
                try:
                    service.approve(
                        workspace["workspaceId"],
                        semantic=semantic,
                        anchor={"kind": "token", "value": token},
                        fields=[],
                        expected_revision=workspace["revision"],
                    )
                    return "updated"
                except TemplateMappingRevisionConflict:
                    return "conflict"

            with ThreadPoolExecutor(max_workers=2) as executor:
                outcomes = list(
                    executor.map(
                        lambda command: approve(*command),
                        (
                            ("report.title", "{{REPORT_TITLE}}"),
                            ("overview", "{{OVERVIEW}}"),
                        ),
                    )
                )

            self.assertCountEqual(outcomes, ["updated", "conflict"])
            persisted = service.get(workspace["workspaceId"])
            self.assertEqual(persisted["revision"], 2)
            self.assertEqual(len(persisted["slots"]), 1)

    def test_rename_clone_archive_and_restore_are_revisioned_and_non_destructive(self) -> None:
        source = _template_bytes("{{REPORT_TITLE}}", "{{OVERVIEW}}")
        with tempfile.TemporaryDirectory() as temporary:
            service = TemplateStudioService(Path(temporary) / "studio")
            workspace = service.create(
                source,
                report_type="server_only",
                profile_id="lifecycle-server",
                display_name="Lifecycle Server",
            )
            mapped = service.approve(
                workspace["workspaceId"],
                semantic="report.title",
                anchor={"kind": "token", "value": "{{REPORT_TITLE}}"},
                fields=[],
                expected_revision=workspace["revision"],
            )
            renamed = service.rename(
                workspace["workspaceId"],
                display_name="Lifecycle Server Renamed",
                expected_revision=mapped["revision"],
            )

            self.assertEqual(renamed["revision"], 3)
            self.assertEqual(renamed["displayName"], "Lifecycle Server Renamed")
            self.assertEqual(renamed["audit"][-1]["action"], "workspace.renamed")
            with self.assertRaises(TemplateMappingRevisionConflict):
                service.rename(
                    workspace["workspaceId"],
                    display_name="Stale Rename",
                    expected_revision=mapped["revision"],
                )

            cloned = service.clone(
                workspace["workspaceId"],
                profile_id="lifecycle-server-copy",
                display_name="Lifecycle Server Copy",
                version="0.2.0",
                expected_revision=renamed["revision"],
            )
            self.assertNotEqual(cloned["workspaceId"], workspace["workspaceId"])
            self.assertEqual(cloned["revision"], 1)
            self.assertFalse(cloned["archived"])
            self.assertEqual(cloned["slots"], renamed["slots"])
            self.assertEqual(cloned["templateSha256"], renamed["templateSha256"])
            self.assertEqual(cloned["audit"][0]["action"], "workspace.cloned")
            self.assertEqual(cloned["audit"][0]["sourceWorkspaceId"], workspace["workspaceId"])

            archived = service.set_archived(
                workspace["workspaceId"],
                archived=True,
                expected_revision=renamed["revision"],
            )
            self.assertTrue(archived["archived"])
            self.assertEqual(archived["revision"], 4)
            self.assertEqual(archived["audit"][-1]["action"], "workspace.archived")
            with self.assertRaisesRegex(TemplateMappingWorkspaceError, "read-only"):
                service.approve(
                    workspace["workspaceId"],
                    semantic="overview",
                    anchor={"kind": "token", "value": "{{OVERVIEW}}"},
                    fields=[],
                    expected_revision=archived["revision"],
                )

            archived_index = service.list_workspaces(archived=True)
            active_index = service.list_workspaces(archived=False)
            self.assertEqual(
                [item["workspaceId"] for item in archived_index["items"]],
                [workspace["workspaceId"]],
            )
            self.assertEqual(
                [item["workspaceId"] for item in active_index["items"]],
                [cloned["workspaceId"]],
            )

            restored = service.set_archived(
                workspace["workspaceId"],
                archived=False,
                expected_revision=archived["revision"],
            )
            self.assertFalse(restored["archived"])
            self.assertEqual(restored["revision"], 5)
            self.assertEqual(restored["audit"][-1]["action"], "workspace.restored")

    def test_workspace_index_returns_metadata_only_in_deterministic_order(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            service = TemplateStudioService(Path(temporary) / "studio")
            older = create_mapping_workspace(
                _analysis("full"),
                profile_id="older-full",
                display_name="Older Full",
                now=datetime(2026, 1, 1, 0, 0, 0, tzinfo=timezone.utc),
            )
            newer = create_mapping_workspace(
                _analysis("server_only"),
                profile_id="newer-server",
                display_name="Newer Server",
                now=datetime(2026, 1, 1, 0, 0, 0, 500000, tzinfo=timezone.utc),
            )
            service.workspaces.save(older)
            service.workspaces.save(newer)

            result = service.list_workspaces()

            self.assertEqual(
                [item["workspaceId"] for item in result["items"]],
                [newer["workspaceId"], older["workspaceId"]],
            )
            self.assertEqual(
                set(result["items"][0]),
                {
                    "workspaceId",
                    "profileId",
                    "displayName",
                    "version",
                    "reportType",
                    "status",
                    "archived",
                    "revision",
                    "coveragePercent",
                    "mappedCount",
                    "requiredCount",
                    "missingCount",
                    "createdAt",
                    "updatedAt",
                },
            )
            self.assertNotIn("analysis", result["items"][0])
            self.assertNotIn("slots", result["items"][0])
            self.assertNotIn("audit", result["items"][0])
            self.assertNotIn("templateSha256", result["items"][0])
            self.assertEqual(result["items"][0]["mappedCount"], 0)
            self.assertEqual(
                result["items"][0]["requiredCount"],
                len(REPORT_REQUIREMENTS["server_only"]),
            )
            self.assertFalse(result["hasMore"])
            self.assertIsNone(result["nextCursor"])

    def test_workspace_index_filters_status_and_report_type(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            service = TemplateStudioService(Path(temporary) / "studio")
            full = create_mapping_workspace(
                _analysis("full"), profile_id="full-draft", display_name="Full Draft"
            )
            server = create_mapping_workspace(
                _analysis("server_only"),
                profile_id="server-draft",
                display_name="Server Draft",
            )
            server = _approve(server, "report.title", 0)
            service.workspaces.save(full)
            service.workspaces.save(server)

            by_status = service.list_workspaces(status="mapping_incomplete")
            by_type = service.list_workspaces(report_type="full")
            by_query = service.list_workspaces(q="SERVER-DRAFT")
            combined = service.list_workspaces(status="mapping_incomplete", report_type="full")

            self.assertEqual(
                [item["workspaceId"] for item in by_status["items"]], [server["workspaceId"]]
            )
            self.assertEqual(
                [item["workspaceId"] for item in by_type["items"]], [full["workspaceId"]]
            )
            self.assertEqual(
                [item["workspaceId"] for item in by_query["items"]], [server["workspaceId"]]
            )
            self.assertEqual(by_query["items"][0]["mappedCount"], 1)
            self.assertEqual(
                by_query["items"][0]["missingCount"],
                len(REPORT_REQUIREMENTS["server_only"]) - 1,
            )
            self.assertEqual(combined["items"], [])

    def test_workspace_index_cursor_pages_without_duplicates(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            service = TemplateStudioService(Path(temporary) / "studio")
            workspaces = [
                create_mapping_workspace(
                    _analysis("client_only"),
                    profile_id=f"client-{index}",
                    display_name=f"Client {index}",
                    now=datetime(2026, 1, 1, tzinfo=timezone.utc),
                )
                for index in range(3)
            ]
            for workspace in workspaces:
                service.workspaces.save(workspace)

            expected = sorted(workspace["workspaceId"] for workspace in workspaces)
            first = service.list_workspaces(report_type="client_only", limit=2)
            second = service.list_workspaces(
                report_type="client_only", cursor=first["nextCursor"], limit=2
            )

            actual = [item["workspaceId"] for item in first["items"] + second["items"]]
            self.assertEqual(actual, expected)
            self.assertTrue(first["hasMore"])
            self.assertIsNotNone(first["nextCursor"])
            self.assertFalse(second["hasMore"])
            self.assertIsNone(second["nextCursor"])
            with self.assertRaisesRegex(TemplateMappingWorkspaceError, "filters"):
                service.list_workspaces(status="analyzed", cursor=first["nextCursor"])
            padded = first["nextCursor"] + "=" * (-len(first["nextCursor"]) % 4)
            cursor_payload = json.loads(base64.urlsafe_b64decode(padded))
            cursor_payload["unexpected"] = True
            cursor_with_extra_key = (
                base64.urlsafe_b64encode(json.dumps(cursor_payload).encode("utf-8"))
                .decode("ascii")
                .rstrip("=")
            )
            with self.assertRaisesRegex(TemplateMappingWorkspaceError, "cursor"):
                service.list_workspaces(cursor=cursor_with_extra_key)

            changed = create_mapping_workspace(
                _analysis("client_only"),
                profile_id="client-added",
                display_name="Client Added",
            )
            service.workspaces.save(changed)
            with self.assertRaisesRegex(TemplateMappingWorkspaceIndexChanged, "changed"):
                service.list_workspaces(
                    report_type="client_only",
                    cursor=first["nextCursor"],
                    limit=2,
                )

    def test_workspace_index_skips_corrupt_workspace_and_rejects_bad_arguments(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            service = TemplateStudioService(Path(temporary) / "studio")
            valid = create_mapping_workspace(
                _analysis(), profile_id="valid-full", display_name="Valid Full"
            )
            service.workspaces.save(valid)
            corrupt_path = service.workspaces.root / f"{'f' * 32}.json"
            corrupt_path.write_text("{not-json", encoding="utf-8")

            result = service.list_workspaces()

            self.assertEqual(
                [item["workspaceId"] for item in result["items"]], [valid["workspaceId"]]
            )
            self.assertEqual(result["skippedCorrupt"], 1)
            with self.assertRaisesRegex(TemplateMappingWorkspaceError, "status filter"):
                service.list_workspaces(status="unknown")
            with self.assertRaisesRegex(TemplateMappingWorkspaceError, "report type filter"):
                service.list_workspaces(report_type="unknown")
            with self.assertRaisesRegex(TemplateMappingWorkspaceError, "between 1 and"):
                service.list_workspaces(limit=0)
            with self.assertRaisesRegex(TemplateMappingWorkspaceError, "cursor"):
                service.list_workspaces(cursor="not-a-cursor")
            with self.assertRaisesRegex(TemplateMappingWorkspaceError, "cannot exceed"):
                service.list_workspaces(q="x" * 101)


if __name__ == "__main__":
    unittest.main()
