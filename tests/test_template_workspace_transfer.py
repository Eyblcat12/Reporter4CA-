from __future__ import annotations

import hashlib
import io
import json
import tempfile
import unittest
import zipfile
from pathlib import Path

from docx import Document

from apps.backend.core.template_mapping_workspace import TemplateStudioService
from apps.backend.core.template_workspace_transfer import (
    TemplateWorkspaceTransferError,
    export_template_workspace,
    inspect_template_workspace_archive,
)


class TemplateWorkspaceTransferTests(unittest.TestCase):
    def test_export_is_deterministic_and_import_gets_new_identity(self) -> None:
        source = _template_bytes("{{REPORT_TITLE}}", "{{OVERVIEW}}")
        with tempfile.TemporaryDirectory() as temporary:
            service = TemplateStudioService(Path(temporary) / "studio")
            created = service.create(
                source,
                report_type="server_only",
                profile_id="portable-server",
                display_name="Portable Server",
            )
            mapped = service.approve(
                created["workspaceId"],
                semantic="report.title",
                anchor={"kind": "token", "value": "{{REPORT_TITLE}}"},
                fields=[],
                expected_revision=created["revision"],
            )

            first = export_template_workspace(mapped, service.source_bytes(created["workspaceId"]))
            second = export_template_workspace(mapped, service.source_bytes(created["workspaceId"]))
            inspected = inspect_template_workspace_archive(first, actor="team-import")
            saved = service.import_draft(inspected.workspace, inspected.template_bytes)

            self.assertEqual(first, second)
            self.assertNotEqual(saved["workspaceId"], mapped["workspaceId"])
            self.assertEqual(saved["revision"], 1)
            self.assertEqual(saved["profileId"], mapped["profileId"])
            self.assertEqual(saved["slots"], mapped["slots"])
            self.assertEqual(saved["templateSha256"], mapped["templateSha256"])
            self.assertEqual(saved["audit"][0]["action"], "workspace.imported")
            self.assertEqual(saved["audit"][0]["actor"], "team-import")
            self.assertEqual(
                saved["audit"][0]["sourceWorkspaceId"],
                mapped["workspaceId"],
            )
            self.assertEqual(service.source_bytes(saved["workspaceId"]), source)

    def test_checksum_tampering_and_unsupported_members_are_rejected(self) -> None:
        source = _template_bytes("{{REPORT_TITLE}}")
        with tempfile.TemporaryDirectory() as temporary:
            service = TemplateStudioService(Path(temporary) / "studio")
            workspace = service.create(
                source,
                report_type="server_only",
                profile_id="portable-tamper",
                display_name="Portable Tamper",
            )
            archive = export_template_workspace(workspace, source)

        tampered = _rewrite_archive(archive, {"template.docx": source + b"changed"})
        with self.assertRaisesRegex(TemplateWorkspaceTransferError, "Checksum mismatch"):
            inspect_template_workspace_archive(tampered)

        unsafe = _rewrite_archive(archive, {"../outside.txt": b"unsafe"})
        with self.assertRaisesRegex(TemplateWorkspaceTransferError, "exactly three"):
            inspect_template_workspace_archive(unsafe)

    def test_manifest_unknown_fields_and_workspace_hash_tampering_are_rejected(self) -> None:
        source = _template_bytes("{{REPORT_TITLE}}")
        with tempfile.TemporaryDirectory() as temporary:
            service = TemplateStudioService(Path(temporary) / "studio")
            workspace = service.create(
                source,
                report_type="server_only",
                profile_id="portable-manifest",
                display_name="Portable Manifest",
            )
            archive = export_template_workspace(workspace, source)

        manifest = _json_member(archive, "manifest.json")
        manifest["unexpected"] = True
        unknown_manifest = _rewrite_archive(
            archive,
            {"manifest.json": _canonical_json(manifest)},
        )
        with self.assertRaisesRegex(TemplateWorkspaceTransferError, "manifest fields"):
            inspect_template_workspace_archive(unknown_manifest)

        workspace_payload = _json_member(archive, "workspace.json")
        workspace_payload["displayName"] = "Tampered"
        tampered_workspace = _rewrite_archive(
            archive,
            {"workspace.json": _canonical_json(workspace_payload)},
            refresh_manifest_checksums=True,
        )
        with self.assertRaisesRegex(TemplateWorkspaceTransferError, "workspace checksum"):
            inspect_template_workspace_archive(tampered_workspace)


def _template_bytes(*tokens: str) -> bytes:
    document = Document()
    for token in tokens:
        document.add_paragraph(token)
    output = io.BytesIO()
    document.save(output)
    return output.getvalue()


def _json_member(data: bytes, name: str) -> dict:
    with zipfile.ZipFile(io.BytesIO(data)) as archive:
        return json.loads(archive.read(name).decode("utf-8"))


def _canonical_json(value: dict) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _rewrite_archive(
    data: bytes,
    replacements: dict[str, bytes],
    *,
    refresh_manifest_checksums: bool = False,
) -> bytes:
    with zipfile.ZipFile(io.BytesIO(data)) as source:
        payloads = {info.filename: source.read(info) for info in source.infolist()}
    payloads.update(replacements)
    if refresh_manifest_checksums:
        manifest = json.loads(payloads["manifest.json"].decode("utf-8"))
        manifest["checksums"] = {
            "workspace.json": hashlib.sha256(payloads["workspace.json"]).hexdigest(),
            "template.docx": hashlib.sha256(payloads["template.docx"]).hexdigest(),
        }
        payloads["manifest.json"] = _canonical_json(manifest)
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED) as archive:
        for name, payload in payloads.items():
            archive.writestr(name, payload)
    return output.getvalue()


if __name__ == "__main__":
    unittest.main()
