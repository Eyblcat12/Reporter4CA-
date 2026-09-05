from __future__ import annotations

import hashlib
import json
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "backend"
FIXTURE_ROOT = ROOT / "tests" / "fixtures" / "template_studio" / "synthetic_templates"
sys.path.insert(0, str(BACKEND))

from core.template_mapping_workspace import TemplateStudioService  # noqa: E402
from core.template_pack import inspect_template_pack  # noqa: E402
from core.template_pack_catalog import build_template_pack  # noqa: E402
from core.template_pack_preview import (  # noqa: E402
    preview_template_pack,
    promote_template_pack_preview,
)
from core.template_pack_validation import (  # noqa: E402
    approve_template_pack_validation,
    run_template_pack_validation,
)
from core.template_profile_analyzer import analyze_profile_template  # noqa: E402
from core.template_profiles import REPORT_REQUIREMENTS  # noqa: E402

from tests.test_profile_renderer import _complete_workspace, _prepared  # noqa: E402
from tests.test_template_pack_validation import _payload  # noqa: E402


class SyntheticTemplatePilotTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.manifest = json.loads((FIXTURE_ROOT / "manifest.json").read_text("utf-8"))

    def test_fixture_manifest_checksums_and_report_type_coverage(self) -> None:
        self.assertEqual(set(self.manifest["fixtures"]), {"full", "server_only", "client_only"})
        for fixture in self.manifest["fixtures"].values():
            payload = (FIXTURE_ROOT / fixture["file"]).read_bytes()
            self.assertEqual(hashlib.sha256(payload).hexdigest(), fixture["sha256"])
            self.assertEqual(len(payload), fixture["sizeBytes"])

    def test_each_distinct_template_completes_the_real_pack_pipeline(self) -> None:
        anchor_kinds: dict[str, set[str]] = {}
        for report_type, fixture in self.manifest["fixtures"].items():
            with self.subTest(report_type=report_type), tempfile.TemporaryDirectory() as temporary:
                template = (FIXTURE_ROOT / fixture["file"]).read_bytes()
                anchors = fixture["anchors"]
                analysis = analyze_profile_template(template, report_type)
                discovered = {
                    (kind, anchor["value"])
                    for key, kind in (
                        ("contentControls", "content_control"),
                        ("bookmarks", "bookmark"),
                    )
                    for anchor in analysis["facts"][key]
                }
                discovered.update(("token", value) for value in analysis["facts"]["tokens"])
                expected = {(anchor["kind"], anchor["value"]) for anchor in anchors.values()}

                self.assertEqual(set(anchors), set(REPORT_REQUIREMENTS[report_type]))
                self.assertTrue(expected.issubset(discovered))
                self.assertEqual(analysis["facts"]["anchorConflicts"], [])
                self.assertEqual(analysis["mapping"]["coveragePercent"], 0.0)
                anchor_kinds[report_type] = {anchor["kind"] for anchor in anchors.values()}

                service = TemplateStudioService(Path(temporary) / "studio")
                workspace = _complete_workspace(service, template, report_type, anchors)
                self.assertEqual(workspace["coveragePercent"], 100.0)
                prepared = _prepared(report_type, template, _payload())
                baseline = run_template_pack_validation(
                    workspace,
                    template,
                    prepared,
                    fixture_id=f"synthetic-{report_type}-v1",
                    structural_baseline=None,
                )
                verified = run_template_pack_validation(
                    workspace,
                    template,
                    prepared,
                    fixture_id=f"synthetic-{report_type}-v1",
                    structural_baseline=baseline.structural_snapshot,
                )
                self.assertTrue(verified.ready_for_visual_review)
                evidence = approve_template_pack_validation(
                    verified,
                    reviewer="synthetic-pilot",
                    artifact_sha256=verified.artifact_sha256,
                    reviewed_at="2026-09-04T00:00:00+00:00",
                )
                pack = build_template_pack(workspace, template, evidence)
                inspection = inspect_template_pack(pack)
                self.assertTrue(inspection.publishable)
                preview = preview_template_pack(pack, prepared)
                promoted = promote_template_pack_preview(preview, pack, prepared)
                self.assertEqual(promoted.artifact_bytes, preview.artifact_bytes)
                self.assertEqual(
                    preview.manifest["renderedSemantics"],
                    list(REPORT_REQUIREMENTS[report_type]),
                )
                self.assertFalse(preview.manifest["legacyRendererUsed"])

        self.assertEqual(anchor_kinds["full"], {"token", "bookmark", "content_control"})
        self.assertEqual(anchor_kinds["server_only"], {"token", "bookmark", "content_control"})
        self.assertEqual(anchor_kinds["client_only"], {"token", "bookmark", "content_control"})


if __name__ == "__main__":
    unittest.main()
