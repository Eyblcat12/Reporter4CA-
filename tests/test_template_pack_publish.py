from __future__ import annotations

import sys
import tempfile
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "backend"
sys.path.insert(0, str(BACKEND))

from core.template_mapping_workspace import TemplateStudioService  # noqa: E402
from core.template_pack_catalog import (  # noqa: E402
    TemplatePackCatalog,
    TemplatePackCatalogRevisionConflict,
)
from core.template_pack_publish import (  # noqa: E402
    TemplatePackPublishConflict,
    TemplatePackPublishError,
    TemplatePackPublishService,
)

from tests.test_profile_renderer import _complete_workspace, _prepared, _template_for  # noqa: E402
from tests.test_template_pack_validation import _payload  # noqa: E402


class TemplatePackPublishTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        root = Path(self.temporary.name)
        self.studio = TemplateStudioService(root / "studio")
        self.catalog = TemplatePackCatalog(root / "catalog")
        self.publisher = TemplatePackPublishService(
            root / "validation",
            self.studio,
            self.catalog,
        )
        self.template, anchors = _template_for("summary")
        self.workspace = _complete_workspace(self.studio, self.template, "summary", anchors)
        self.prepared = _prepared("summary", self.template, _payload())

    def tearDown(self) -> None:
        self.temporary.cleanup()

    def test_two_pass_review_publishes_exact_artifact(self) -> None:
        baseline = self.publisher.validate(
            self.workspace["workspaceId"],
            self.prepared,
            fixture_id="summary-api-v1",
            expected_workspace_revision=self.workspace["revision"],
        )
        self.assertEqual(baseline["state"], "baseline_candidate")
        approved = self.publisher.approve_baseline(
            self.workspace["workspaceId"],
            baseline["runId"],
            expected_workspace_revision=self.workspace["revision"],
            reviewer="template-admin@example.test",
            artifact_sha256=baseline["validation"]["artifactSha256"],
        )
        self.assertEqual(approved["state"], "baseline_approved")
        repeated = self.publisher.validate(
            self.workspace["workspaceId"],
            self.prepared,
            fixture_id="summary-api-v1",
            expected_workspace_revision=self.workspace["revision"],
        )
        self.assertEqual(repeated["state"], "baseline_approved")

        verified = self.publisher.validate(
            self.workspace["workspaceId"],
            self.prepared,
            fixture_id="summary-api-v1",
            expected_workspace_revision=self.workspace["revision"],
            baseline_run_id=baseline["runId"],
        )
        self.assertTrue(verified["validation"]["readyForVisualReview"])
        published = self.publisher.publish(
            self.workspace["workspaceId"],
            verified["runId"],
            expected_workspace_revision=self.workspace["revision"],
            expected_catalog_revision=0,
            reviewer="template-admin@example.test",
            artifact_sha256=verified["validation"]["artifactSha256"],
        )

        profile_id = self.workspace["profileId"]
        version = self.workspace["version"]
        self.assertIn(version, published["catalog"]["packs"][profile_id]["versions"])
        self.assertFalse(published["selectionIntegrated"])
        self.assertTrue(published["legacyRendererUnchanged"])

    def test_unapproved_baseline_and_stale_workspace_are_rejected(self) -> None:
        baseline = self.publisher.validate(
            self.workspace["workspaceId"],
            self.prepared,
            fixture_id="summary-stale-v1",
            expected_workspace_revision=self.workspace["revision"],
        )
        with self.assertRaisesRegex(TemplatePackPublishError, "not been reviewed"):
            self.publisher.validate(
                self.workspace["workspaceId"],
                self.prepared,
                fixture_id="summary-stale-v1",
                expected_workspace_revision=self.workspace["revision"],
                baseline_run_id=baseline["runId"],
            )
        with self.assertRaises(TemplatePackPublishConflict):
            self.publisher.approve_baseline(
                self.workspace["workspaceId"],
                baseline["runId"],
                expected_workspace_revision=self.workspace["revision"] + 1,
                reviewer="reviewer",
                artifact_sha256=baseline["validation"]["artifactSha256"],
            )

    def test_tampered_artifact_and_wrong_checksum_are_rejected(self) -> None:
        baseline = self.publisher.validate(
            self.workspace["workspaceId"],
            self.prepared,
            fixture_id="summary-tamper-v1",
            expected_workspace_revision=self.workspace["revision"],
        )
        with self.assertRaisesRegex(TemplatePackPublishError, "does not match"):
            self.publisher.approve_baseline(
                self.workspace["workspaceId"],
                baseline["runId"],
                expected_workspace_revision=self.workspace["revision"],
                reviewer="reviewer",
                artifact_sha256="0" * 64,
            )

        artifact = self.publisher.runs_root / baseline["runId"] / "artifact.docx"
        artifact.write_bytes(b"tampered")
        with self.assertRaisesRegex(TemplatePackPublishError, "checksum is invalid"):
            self.publisher.approve_baseline(
                self.workspace["workspaceId"],
                baseline["runId"],
                expected_workspace_revision=self.workspace["revision"],
                reviewer="reviewer",
                artifact_sha256=baseline["validation"]["artifactSha256"],
            )

    def test_catalog_install_rolls_back_new_payload_when_index_write_fails(self) -> None:
        baseline = self.publisher.validate(
            self.workspace["workspaceId"],
            self.prepared,
            fixture_id="summary-rollback-v1",
            expected_workspace_revision=self.workspace["revision"],
        )
        self.publisher.approve_baseline(
            self.workspace["workspaceId"],
            baseline["runId"],
            expected_workspace_revision=self.workspace["revision"],
            reviewer="reviewer",
            artifact_sha256=baseline["validation"]["artifactSha256"],
        )
        verified = self.publisher.validate(
            self.workspace["workspaceId"],
            self.prepared,
            fixture_id="summary-rollback-v1",
            expected_workspace_revision=self.workspace["revision"],
            baseline_run_id=baseline["runId"],
        )
        with patch.object(self.catalog, "_save", side_effect=OSError("disk full")):
            with self.assertRaises(OSError):
                self.publisher.publish(
                    self.workspace["workspaceId"],
                    verified["runId"],
                    expected_workspace_revision=self.workspace["revision"],
                    expected_catalog_revision=0,
                    reviewer="reviewer",
                    artifact_sha256=verified["validation"]["artifactSha256"],
                )
        payload = self.catalog._pack_path(self.workspace["profileId"], self.workspace["version"])
        self.assertFalse(payload.exists())
        self.assertEqual(self.catalog.snapshot()["revision"], 0)

    def test_catalog_revision_conflict_does_not_install_payload(self) -> None:
        baseline = self.publisher.validate(
            self.workspace["workspaceId"],
            self.prepared,
            fixture_id="summary-catalog-stale-v1",
            expected_workspace_revision=self.workspace["revision"],
        )
        self.publisher.approve_baseline(
            self.workspace["workspaceId"],
            baseline["runId"],
            expected_workspace_revision=self.workspace["revision"],
            reviewer="reviewer",
            artifact_sha256=baseline["validation"]["artifactSha256"],
        )
        verified = self.publisher.validate(
            self.workspace["workspaceId"],
            self.prepared,
            fixture_id="summary-catalog-stale-v1",
            expected_workspace_revision=self.workspace["revision"],
            baseline_run_id=baseline["runId"],
        )
        with self.assertRaises(TemplatePackCatalogRevisionConflict):
            self.publisher.publish(
                self.workspace["workspaceId"],
                verified["runId"],
                expected_workspace_revision=self.workspace["revision"],
                expected_catalog_revision=1,
                reviewer="reviewer",
                artifact_sha256=verified["validation"]["artifactSha256"],
            )
        self.assertEqual(self.catalog.snapshot()["packs"], {})

    def test_concurrent_publish_of_same_run_has_exactly_one_catalog_commit(self) -> None:
        baseline = self.publisher.validate(
            self.workspace["workspaceId"],
            self.prepared,
            fixture_id="summary-concurrent-publish-v1",
            expected_workspace_revision=self.workspace["revision"],
        )
        self.publisher.approve_baseline(
            self.workspace["workspaceId"],
            baseline["runId"],
            expected_workspace_revision=self.workspace["revision"],
            reviewer="reviewer",
            artifact_sha256=baseline["validation"]["artifactSha256"],
        )
        verified = self.publisher.validate(
            self.workspace["workspaceId"],
            self.prepared,
            fixture_id="summary-concurrent-publish-v1",
            expected_workspace_revision=self.workspace["revision"],
            baseline_run_id=baseline["runId"],
        )

        def publish() -> str:
            try:
                self.publisher.publish(
                    self.workspace["workspaceId"],
                    verified["runId"],
                    expected_workspace_revision=self.workspace["revision"],
                    expected_catalog_revision=0,
                    reviewer="reviewer",
                    artifact_sha256=verified["validation"]["artifactSha256"],
                )
            except TemplatePackCatalogRevisionConflict:
                return "conflict"
            return "published"

        with ThreadPoolExecutor(max_workers=2) as executor:
            outcomes = list(executor.map(lambda _: publish(), range(2)))

        self.assertEqual(sorted(outcomes), ["conflict", "published"])
        snapshot = self.catalog.snapshot()
        self.assertEqual(snapshot["revision"], 1)
        self.assertEqual(len(snapshot["audit"]), 1)


if __name__ == "__main__":
    unittest.main()
