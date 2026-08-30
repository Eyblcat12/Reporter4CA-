from __future__ import annotations

import io
import sys
import unittest
from dataclasses import replace
from pathlib import Path

from docx import Document

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "backend"
sys.path.insert(0, str(BACKEND))

from core.profile_renderer import ProfileRenderCancelled  # noqa: E402
from core.template_pack_preview import (  # noqa: E402
    TemplatePackPreviewCache,
    TemplatePackPreviewError,
    preview_template_pack,
    promote_template_pack_preview,
)
from core.template_profiles import REPORT_REQUIREMENTS  # noqa: E402

from tests.test_profile_renderer import _prepared, _published_pack, _template_for  # noqa: E402
from tests.test_template_pack_validation import _payload  # noqa: E402


class TemplatePackPreviewTests(unittest.TestCase):
    def test_all_report_types_preview_with_pack_and_snapshot_identity(self) -> None:
        for report_type in REPORT_REQUIREMENTS:
            with self.subTest(report_type=report_type):
                template, anchors = _template_for(report_type)
                pack = _published_pack(template, report_type, anchors)
                prepared = _prepared(report_type, template, _payload())

                preview = preview_template_pack(pack, prepared)

                self.assertEqual(preview.identity.pack_version, "0.1.0")
                self.assertEqual(preview.identity.content_signature, prepared.content_signature)
                self.assertEqual(
                    preview.manifest["renderedSemantics"], list(REPORT_REQUIREMENTS[report_type])
                )
                self.assertFalse(preview.manifest["legacyRendererUsed"])
                self.assertTrue(preview.artifact_bytes.startswith(b"PK"))
                self.assertTrue(preview.structure_diff)

    def test_cache_reuses_only_complete_identity_and_is_bounded(self) -> None:
        template, anchors = _template_for("summary")
        pack = _published_pack(template, "summary", anchors)
        first_snapshot = _prepared("summary", template, _payload())
        changed_payload = _payload()
        changed_payload["metadata"]["recommendations"] = ["Different recommendation"]
        second_snapshot = _prepared("summary", template, changed_payload)
        cache = TemplatePackPreviewCache(max_entries=1)

        first = preview_template_pack(pack, first_snapshot, cache=cache)
        reused = preview_template_pack(pack, first_snapshot, cache=cache)
        changed = preview_template_pack(pack, second_snapshot, cache=cache)

        self.assertFalse(first.cache_hit)
        self.assertTrue(reused.cache_hit)
        self.assertEqual(reused.artifact_sha256, first.artifact_sha256)
        self.assertNotEqual(changed.identity.cache_key, first.identity.cache_key)
        self.assertEqual(cache.entry_count, 1)

    def test_same_version_with_changed_pack_bytes_cannot_reuse_preview(self) -> None:
        first_template, first_anchors = _template_for("summary")
        first_pack = _published_pack(first_template, "summary", first_anchors)
        first_snapshot = _prepared("summary", first_template, _payload())
        cache = TemplatePackPreviewCache()
        first = preview_template_pack(first_pack, first_snapshot, cache=cache)

        changed_document = Document(io.BytesIO(first_template))
        changed_document.add_paragraph("Customer-specific static appendix")
        output = io.BytesIO()
        changed_document.save(output)
        changed_template = output.getvalue()
        changed_pack = _published_pack(changed_template, "summary", first_anchors)
        changed_snapshot = _prepared("summary", changed_template, _payload())
        changed = preview_template_pack(changed_pack, changed_snapshot, cache=cache)

        self.assertEqual(first.identity.pack_version, changed.identity.pack_version)
        self.assertNotEqual(first.identity.pack_sha256, changed.identity.pack_sha256)
        self.assertNotEqual(first.preview_id, changed.preview_id)
        self.assertFalse(changed.cache_hit)

    def test_generate_promotion_is_byte_for_byte_and_rejects_stale_snapshot(self) -> None:
        template, anchors = _template_for("summary")
        pack = _published_pack(template, "summary", anchors)
        prepared = _prepared("summary", template, _payload())
        preview = preview_template_pack(pack, prepared)

        promoted = promote_template_pack_preview(preview, pack, prepared)

        self.assertEqual(promoted.artifact_bytes, preview.artifact_bytes)
        self.assertEqual(promoted.artifact_sha256, preview.artifact_sha256)
        changed_payload = _payload()
        changed_payload["metadata"]["recommendations"] = ["Changed after preview"]
        changed = _prepared("summary", template, changed_payload)
        with self.assertRaisesRegex(TemplatePackPreviewError, "stale"):
            promote_template_pack_preview(preview, pack, changed)

    def test_promotion_rejects_corrupt_artifact(self) -> None:
        template, anchors = _template_for("summary")
        pack = _published_pack(template, "summary", anchors)
        prepared = _prepared("summary", template, _payload())
        preview = preview_template_pack(pack, prepared)
        corrupted = replace(preview, artifact_bytes=preview.artifact_bytes + b"changed")

        with self.assertRaisesRegex(TemplatePackPreviewError, "checksum"):
            promote_template_pack_preview(corrupted, pack, prepared)

    def test_preview_progress_and_cancellation_are_cooperative(self) -> None:
        template, anchors = _template_for("summary")
        pack = _published_pack(template, "summary", anchors)
        prepared = _prepared("summary", template, _payload())
        progress: list[int] = []

        preview_template_pack(
            pack,
            prepared,
            on_progress=lambda percent, _stage: progress.append(percent),
        )

        self.assertEqual(progress[-1], 100)
        self.assertEqual(progress, sorted(progress))
        with self.assertRaises(ProfileRenderCancelled):
            preview_template_pack(pack, prepared, check_cancelled=lambda: True)


if __name__ == "__main__":
    unittest.main()
