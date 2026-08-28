from __future__ import annotations

import io
import os
import tempfile
import unittest
from datetime import datetime, timezone
from pathlib import Path

from docx import Document

from apps.backend.core.template_mapping_workspace import (
    TemplateMappingWorkspaceError,
    TemplateStudioService,
    set_mapping_workspace_archived,
)
from apps.backend.core.template_workspace_retention import (
    TemplateWorkspaceRetention,
    TemplateWorkspaceRetentionError,
)


class TemplateWorkspaceRetentionTests(unittest.TestCase):
    def test_preview_quarantine_and_restore_are_non_destructive(self) -> None:
        fixed_now = datetime(2026, 8, 28, tzinfo=timezone.utc)
        old_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temporary:
            service = TemplateStudioService(Path(temporary) / "studio")
            workspace, source_path = _old_archived_workspace(service, old_time)
            retention = TemplateWorkspaceRetention(
                service,
                secret=b"retention-test-secret" * 2,
                now=lambda: fixed_now,
            )

            preview = retention.preview(retention_days=90)

            self.assertTrue(preview["dryRun"])
            self.assertFalse(preview["blocked"])
            self.assertEqual(preview["candidateWorkspaceCount"], 1)
            self.assertEqual(preview["candidateSourceCount"], 1)
            self.assertIsNotNone(preview["confirmationToken"])
            self.assertFalse(preview["permanentDelete"])
            self.assertTrue(source_path.exists())
            self.assertEqual(
                service.get(workspace["workspaceId"])["workspaceId"], workspace["workspaceId"]
            )

            applied = retention.apply(preview["confirmationToken"])

            self.assertTrue(applied["recoverable"])
            self.assertFalse(applied["permanentDelete"])
            self.assertFalse(source_path.exists())
            with self.assertRaisesRegex(TemplateMappingWorkspaceError, "not found"):
                service.get(workspace["workspaceId"])

            restored = retention.restore(applied["quarantineId"])

            self.assertTrue(restored["restored"])
            self.assertEqual(
                service.get(workspace["workspaceId"])["workspaceId"], workspace["workspaceId"]
            )
            self.assertTrue(source_path.exists())
            with self.assertRaisesRegex(TemplateWorkspaceRetentionError, "already restored"):
                retention.restore(applied["quarantineId"])

    def test_changed_plan_and_tampered_token_are_rejected_without_moves(self) -> None:
        fixed_now = datetime(2026, 8, 28, tzinfo=timezone.utc)
        old_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temporary:
            service = TemplateStudioService(Path(temporary) / "studio")
            workspace, source_path = _old_archived_workspace(service, old_time)
            retention = TemplateWorkspaceRetention(
                service,
                secret=b"retention-test-secret" * 2,
                now=lambda: fixed_now,
            )
            preview = retention.preview(retention_days=90)

            with self.assertRaisesRegex(TemplateWorkspaceRetentionError, "Invalid"):
                retention.apply(preview["confirmationToken"] + "tampered")

            service.create(
                _template_bytes("{{REPORT_TITLE}}"),
                report_type="server_only",
                profile_id="newer-server",
                display_name="Newer Server",
            )
            with self.assertRaisesRegex(TemplateWorkspaceRetentionError, "changed"):
                retention.apply(preview["confirmationToken"])

            self.assertTrue(source_path.exists())
            self.assertEqual(
                service.get(workspace["workspaceId"])["workspaceId"], workspace["workspaceId"]
            )

    def test_corrupt_workspace_blocks_cleanup_and_pack_source_is_protected(self) -> None:
        fixed_now = datetime(2026, 8, 28, tzinfo=timezone.utc)
        old_time = datetime(2026, 1, 1, tzinfo=timezone.utc)
        with tempfile.TemporaryDirectory() as temporary:
            service = TemplateStudioService(Path(temporary) / "studio")
            workspace, source_path = _old_archived_workspace(service, old_time)
            retention = TemplateWorkspaceRetention(
                service,
                secret=b"retention-test-secret" * 2,
                now=lambda: fixed_now,
            )

            protected = retention.preview(
                retention_days=90,
                protected_source_hashes={workspace["templateSha256"]},
            )
            self.assertEqual(protected["candidateWorkspaceCount"], 1)
            self.assertEqual(protected["candidateSourceCount"], 0)

            corrupt = service.workspaces.root / f"{'f' * 32}.json"
            corrupt.write_text("{broken", encoding="utf-8")
            blocked = retention.preview(retention_days=90)
            self.assertTrue(blocked["blocked"])
            self.assertIsNone(blocked["confirmationToken"])
            self.assertTrue(source_path.exists())


def _old_archived_workspace(
    service: TemplateStudioService,
    old_time: datetime,
) -> tuple[dict, Path]:
    workspace = service.create(
        _template_bytes("{{REPORT_TITLE}}"),
        report_type="server_only",
        profile_id="retention-server",
        display_name="Retention Server",
    )
    archived = set_mapping_workspace_archived(
        workspace,
        archived=True,
        expected_revision=workspace["revision"],
        now=old_time,
    )
    service.workspaces.save(archived)
    source_path = service.sources / f"{workspace['templateSha256']}.docx"
    old_epoch = old_time.timestamp()
    os.utime(source_path, (old_epoch, old_epoch))
    return archived, source_path


def _template_bytes(*tokens: str) -> bytes:
    document = Document()
    for token in tokens:
        document.add_paragraph(token)
    output = io.BytesIO()
    document.save(output)
    return output.getvalue()


if __name__ == "__main__":
    unittest.main()
