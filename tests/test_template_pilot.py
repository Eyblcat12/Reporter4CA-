from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_template_pilot import (
    REQUIRED_EVIDENCE,
    load_manifest,
    validate_pilot_manifest,
)

ROOT = Path(__file__).resolve().parents[1]
SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64
SHA_D = "d" * 64


def _ready_manifest(evidence_root: Path) -> dict:
    evidence = []
    for kind in sorted(REQUIRED_EVIDENCE):
        path = f"evidence/{kind}.json"
        payload = json.dumps({"kind": kind, "synthetic": True}, sort_keys=True).encode()
        target = evidence_root / path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(payload)
        evidence.append({"kind": kind, "path": path, "sha256": hashlib.sha256(payload).hexdigest()})
    return {
        "schemaVersion": "1.0",
        "pilotId": "synthetic-full-v1",
        "status": "ready",
        "reportType": "full",
        "identity": {
            "packId": "synthetic-full",
            "packVersion": "1.0.0",
            "packSha256": SHA_A,
            "templateSha256": SHA_B,
            "workspaceHash": SHA_C,
            "workspaceRevision": 7,
        },
        "fixture": {
            "fixtureId": "mixed-50",
            "sourceSha256": SHA_D,
            "assetCount": 50,
            "serverCount": 22,
            "clientCount": 28,
            "sanitized": True,
            "containsCustomerData": False,
        },
        "gates": {
            "mapping": {"passed": True, "coveragePercent": 100},
            "baseline": {
                "runId": "baseline-run",
                "templateSha256": SHA_B,
                "workspaceHash": SHA_C,
                "artifactSha256": SHA_A,
                "structuralSha256": SHA_D,
                "fixturePassed": True,
                "integrityPassed": True,
                "structuralPassed": False,
                "baselineApproved": True,
            },
            "verification": {
                "runId": "verification-run",
                "templateSha256": SHA_B,
                "workspaceHash": SHA_C,
                "artifactSha256": SHA_B,
                "structuralSha256": SHA_D,
                "fixturePassed": True,
                "integrityPassed": True,
                "structuralPassed": True,
            },
            "golden": {"passed": True, "unexpectedDiffCount": 0},
            "integrity": {"passed": True},
            "features": {
                "splitRunToken": "passed",
                "bookmarkAnchor": "passed",
                "contentControlAnchor": "passed",
                "headerFooter": "passed",
                "tocFields": "passed",
                "numbering": "passed",
                "horizontalMergedCells": "not_applicable",
                "verticalMergedCells": "not_applicable",
                "pageBreaks": "passed",
                "sectionBreaks": "passed",
                "images": "not_applicable",
                "relationships": "passed",
            },
            "visual": {"passed": True, "reviewer": "reviewer-a", "artifactSha256": SHA_B},
            "benchmark": {
                "passed": True,
                "outcome": "passed",
                "trials": 10,
                "targetAssetCount": 1000,
                "p50Seconds": 2.0,
                "p95Seconds": 2.5,
                "peakRssMiB": 128.0,
                "resourceLimited": False,
                "legacyRendererUsed": False,
            },
            "recovery": {"passed": True, "dryRunPassed": True, "rollbackPassed": True},
            "quality": {
                "passed": True,
                "commitSha": "ffcc0fa",
                "backendTests": 354,
                "frontendTests": 51,
                "productionBuildPassed": True,
            },
        },
        "approvals": {
            "author": "author-a",
            "reviewer": "reviewer-a",
            "publisher": "publisher-a",
            "integrationApproved": True,
        },
        "evidence": evidence,
    }


class TemplatePilotManifestTests(unittest.TestCase):
    def test_complete_synthetic_manifest_is_ready_only_with_verified_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = _ready_manifest(root)
            self.assertEqual([], validate_pilot_manifest(manifest, evidence_root=root))
            unverified = validate_pilot_manifest(manifest)

        self.assertIn("evidence.not_verified", {issue.code for issue in unverified})

    def test_ready_does_not_claim_integration_approval(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = _ready_manifest(root)
            manifest["approvals"]["integrationApproved"] = False
            self.assertEqual([], validate_pilot_manifest(manifest, evidence_root=root))
            manifest["status"] = "approved"
            issues = validate_pilot_manifest(manifest, evidence_root=root)

        self.assertIn("approval.integration", {issue.code for issue in issues})

    def test_draft_or_first_run_claim_cannot_be_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = _ready_manifest(root)
            manifest["status"] = "draft"
            manifest["gates"]["baseline"]["structuralPassed"] = True
            manifest["gates"]["verification"]["runId"] = "baseline-run"
            issues = validate_pilot_manifest(manifest, evidence_root=root)

        codes = {issue.code for issue in issues}
        self.assertIn("status.not_ready", codes)
        self.assertIn("baseline.first_run", codes)
        self.assertIn("validation.run_reused", codes)

    def test_tampered_evidence_unsafe_path_and_role_collision_are_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = _ready_manifest(root)
            manifest["approvals"]["reviewer"] = manifest["approvals"]["author"]
            manifest["evidence"][0]["path"] = "../outside.json"
            (root / manifest["evidence"][1]["path"]).write_text("tampered", encoding="utf-8")
            issues = validate_pilot_manifest(manifest, evidence_root=root)

        codes = {issue.code for issue in issues}
        self.assertIn("approval.separation", codes)
        self.assertIn("evidence.path", codes)
        self.assertIn("evidence.hash_mismatch", codes)

    def test_resource_limited_or_legacy_benchmark_cannot_pass(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = _ready_manifest(root)
            broken = copy.deepcopy(manifest)
            broken["gates"]["benchmark"].update(
                {"resourceLimited": True, "legacyRendererUsed": True, "p95Seconds": 1.0}
            )
            issues = validate_pilot_manifest(broken, evidence_root=root)

        codes = {issue.code for issue in issues}
        self.assertIn("benchmark.resource_limited", codes)
        self.assertIn("benchmark.renderer", codes)
        self.assertIn("benchmark.percentile", codes)

    def test_committed_schema_is_closed_and_versioned(self) -> None:
        path = (
            ROOT / "apps" / "backend" / "config" / "template_pilot" / "pilot-manifest.schema.json"
        )
        schema = json.loads(path.read_text(encoding="utf-8"))
        self.assertEqual("https://json-schema.org/draft/2020-12/schema", schema["$schema"])
        self.assertIn("1.0", schema["$id"])
        self.assertFalse(schema["additionalProperties"])

    def test_loader_rejects_duplicate_fields_and_non_finite_numbers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            duplicate = root / "duplicate.json"
            duplicate.write_text('{"schemaVersion":"1.0","schemaVersion":"1.0"}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "duplicate"):
                load_manifest(duplicate)
            non_finite = root / "nan.json"
            non_finite.write_text('{"metric":NaN}', encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "non-finite"):
                load_manifest(non_finite)


if __name__ == "__main__":
    unittest.main()
