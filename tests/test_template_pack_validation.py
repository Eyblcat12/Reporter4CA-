from __future__ import annotations

import copy
import io
import sys
import tempfile
import unittest
from pathlib import Path

from docx import Document

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "backend"
sys.path.insert(0, str(BACKEND))

from core.profile_renderer import (  # noqa: E402
    ProfileRenderCancelled,
    ProfileRendererError,
    render_profile_document,
)
from core.template_mapping_workspace import TemplateStudioService  # noqa: E402
from core.template_pack import TemplatePackError, inspect_template_pack  # noqa: E402
from core.template_pack_catalog import (  # noqa: E402
    build_template_pack,
    build_template_pack_candidate,
)
from core.template_pack_validation import (  # noqa: E402
    TemplatePackValidationError,
    approve_template_pack_validation,
    run_template_pack_validation,
)
from core.template_profiles import REPORT_REQUIREMENTS  # noqa: E402

from tests.test_profile_renderer import _complete_workspace, _prepared, _template_for  # noqa: E402


class TemplatePackValidationTests(unittest.TestCase):
    def test_candidate_is_non_publishable_and_rejected_by_normal_renderer(self) -> None:
        template, anchors = _template_for("summary")
        with tempfile.TemporaryDirectory() as temporary:
            service = TemplateStudioService(Path(temporary) / "studio")
            workspace = _complete_workspace(service, template, "summary", anchors)
            candidate = build_template_pack_candidate(workspace, template)
        inspection = inspect_template_pack(candidate, require_publishable=False)
        prepared = _prepared("summary", template, _payload())

        self.assertFalse(inspection.publishable)
        self.assertEqual(inspection.profile["status"], "mapping_complete")
        with self.assertRaises(TemplatePackError):
            inspect_template_pack(candidate)
        with self.assertRaisesRegex(ProfileRendererError, "not publishable"):
            render_profile_document(candidate, prepared)

    def test_all_report_types_establish_and_match_structural_baseline(self) -> None:
        for report_type in REPORT_REQUIREMENTS:
            with self.subTest(report_type=report_type), tempfile.TemporaryDirectory() as temporary:
                template, anchors = _template_for(
                    report_type, mixed_anchors=report_type == "summary"
                )
                service = TemplateStudioService(Path(temporary) / "studio")
                workspace = _complete_workspace(service, template, report_type, anchors)
                prepared = _prepared(report_type, template, _payload())

                initial = run_template_pack_validation(
                    workspace,
                    template,
                    prepared,
                    fixture_id=f"{report_type}-fixture-v1",
                    structural_baseline=None,
                )
                verified = run_template_pack_validation(
                    workspace,
                    template,
                    prepared,
                    fixture_id=f"{report_type}-fixture-v1",
                    structural_baseline=initial.structural_snapshot,
                )

                self.assertTrue(initial.fixture_passed)
                self.assertTrue(initial.integrity_passed)
                self.assertFalse(initial.structural_passed)
                self.assertTrue(verified.ready_for_visual_review)
                self.assertEqual(verified.issues, ())
                self.assertEqual(verified.structural_sha256, initial.structural_sha256)
                self.assertEqual(
                    verified.manifest["renderedSemantics"], list(REPORT_REQUIREMENTS[report_type])
                )

    def test_reviewed_run_issues_extended_evidence_and_builds_publishable_pack(self) -> None:
        template, anchors = _template_for("summary")
        with tempfile.TemporaryDirectory() as temporary:
            service = TemplateStudioService(Path(temporary) / "studio")
            workspace = _complete_workspace(service, template, "summary", anchors)
            prepared = _prepared("summary", template, _payload())
            initial = run_template_pack_validation(
                workspace,
                template,
                prepared,
                fixture_id="summary-reviewed-v1",
                structural_baseline=None,
            )
            verified = run_template_pack_validation(
                workspace,
                template,
                prepared,
                fixture_id="summary-reviewed-v1",
                structural_baseline=initial.structural_snapshot,
            )
            evidence = approve_template_pack_validation(
                verified,
                reviewer="template-admin@example.test",
                artifact_sha256=verified.artifact_sha256,
                reviewed_at="2026-08-30T00:00:00+00:00",
            )
            published = build_template_pack(workspace, template, evidence)

        inspection = inspect_template_pack(published)
        public_evidence = inspection.profile["validation"]
        self.assertTrue(inspection.publishable)
        self.assertEqual(public_evidence["validationRunId"], verified.run_id)
        self.assertEqual(public_evidence["artifactSha256"], verified.artifact_sha256)
        self.assertEqual(public_evidence["structuralSha256"], verified.structural_sha256)
        self.assertEqual(public_evidence["reviewedBy"], "template-admin@example.test")

    def test_structural_diff_is_readable_and_traces_tagged_table_semantic(self) -> None:
        template, anchors = _template_for("summary")
        with tempfile.TemporaryDirectory() as temporary:
            service = TemplateStudioService(Path(temporary) / "studio")
            workspace = _complete_workspace(service, template, "summary", anchors)
            prepared = _prepared("summary", template, _payload())
            initial = run_template_pack_validation(
                workspace,
                template,
                prepared,
                fixture_id="summary-diff-v1",
                structural_baseline=None,
            )
            changed = copy.deepcopy(initial.structural_snapshot)
            tagged = next(table for table in changed["tables"] if table["semantic"])
            tagged["contentSha256"] = "0" * 64
            failed = run_template_pack_validation(
                workspace,
                template,
                prepared,
                fixture_id="summary-diff-v1",
                structural_baseline=changed,
            )

        difference = next(issue for issue in failed.issues if issue.code == "structural.changed")
        self.assertFalse(failed.structural_passed)
        self.assertTrue(difference.semantic)
        self.assertIn("tables", difference.path)
        self.assertIn("contentSha256", difference.path)

    def test_unmapped_token_blocks_integrity_and_visual_approval(self) -> None:
        template, anchors = _template_for("summary")
        document = Document(io.BytesIO(template))
        document.add_paragraph("{{UNMAPPED_CUSTOMER_TOKEN}}")
        output = io.BytesIO()
        document.save(output)
        changed_template = output.getvalue()
        with tempfile.TemporaryDirectory() as temporary:
            service = TemplateStudioService(Path(temporary) / "studio")
            workspace = _complete_workspace(service, changed_template, "summary", anchors)
            prepared = _prepared("summary", changed_template, _payload())
            run = run_template_pack_validation(
                workspace,
                changed_template,
                prepared,
                fixture_id="summary-unmapped-token-v1",
                structural_baseline=None,
            )

        self.assertFalse(run.integrity_passed)
        self.assertIn("integrity.anchor_remaining", {issue.code for issue in run.issues})
        with self.assertRaisesRegex(TemplatePackValidationError, "unresolved"):
            approve_template_pack_validation(
                run,
                reviewer="template-admin",
                artifact_sha256=run.artifact_sha256,
            )

    def test_approval_is_bound_to_exact_artifact_and_validation_is_cancellable(self) -> None:
        template, anchors = _template_for("summary")
        with tempfile.TemporaryDirectory() as temporary:
            service = TemplateStudioService(Path(temporary) / "studio")
            workspace = _complete_workspace(service, template, "summary", anchors)
            prepared = _prepared("summary", template, _payload())
            initial = run_template_pack_validation(
                workspace,
                template,
                prepared,
                fixture_id="summary-checksum-v1",
                structural_baseline=None,
            )
            verified = run_template_pack_validation(
                workspace,
                template,
                prepared,
                fixture_id="summary-checksum-v1",
                structural_baseline=initial.structural_snapshot,
            )
            with self.assertRaisesRegex(TemplatePackValidationError, "checksum"):
                approve_template_pack_validation(
                    verified,
                    reviewer="template-admin",
                    artifact_sha256="0" * 64,
                )
            with self.assertRaises(ProfileRenderCancelled):
                run_template_pack_validation(
                    workspace,
                    template,
                    prepared,
                    fixture_id="summary-cancel-v1",
                    structural_baseline=initial.structural_snapshot,
                    check_cancelled=lambda: True,
                )


def _payload() -> dict:
    finding = {
        "name": "Proxy tool detected",
        "ruleId": "proxy-tool",
        "severity": "medium",
        "classification": "anomaly",
        "evidence": [{"field": "notes", "value": "ngrok.exe"}],
        "remediation": "Validate and remove unauthorized tooling.",
        "description": "Trace the execution and validate business authorization.",
    }
    server = {
        "hostname": "SRV-VAL-001",
        "ip": "10.20.0.1",
        "os": "Windows Server 2022",
        "result": "Detected suspicious proxy tooling",
        "assessment": {"classification": "anomaly", "label": "Ghi nhận dấu hiệu bất thường"},
        "findings": [finding],
        "iocs": [{"type": "domain", "value": "validation.example.invalid"}],
    }
    client = {
        "hostname": "PC-VAL-001",
        "ip": "10.20.1.1",
        "os": "Windows 11",
        "result": "No anomaly detected",
        "assessment": {"classification": "clean", "label": "Không phát hiện dấu hiệu bất thường"},
        "findings": [],
    }
    return {
        "servers": [server],
        "clients": [client],
        "metadata": {
            "recommendations": ["Review the affected endpoint."],
            "incident": {
                "incident_id": "IR-VALIDATION-001",
                "severity": "medium",
                "status": "contained",
                "detected_at": "2026-08-30T00:00:00Z",
                "executive_summary": "Validated evidence-backed incident.",
                "affected_assets": [server],
                "timeline": [
                    {
                        "timestamp": "2026-08-30T00:00:00Z",
                        "event": "Alert received",
                        "evidence": "EDR-VALIDATION-001",
                    }
                ],
                "iocs": [{"type": "domain", "value": "validation.example.invalid"}],
                "mitre": [
                    {
                        "technique_id": "T1090",
                        "technique": "Proxy",
                        "tactic": "Command and Control",
                    }
                ],
                "containment": ["Isolated affected host"],
                "eradication": ["Removed unauthorized proxy tooling"],
                "recovery": ["Restored service and monitored"],
                "lessons_learned": "Improve proxy-tool detection coverage.",
            },
        },
    }


if __name__ == "__main__":
    unittest.main()
