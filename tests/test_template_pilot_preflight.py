from __future__ import annotations

import copy
import hashlib
import json
import tempfile
import unittest
from pathlib import Path
from typing import Any

from scripts.preflight_template_pilot import preflight_pilot_manifest
from tests.test_template_pilot import SHA_A, SHA_B, SHA_D, _ready_manifest


def _write_record(
    root: Path,
    manifest: dict[str, Any],
    kind: str,
    record: dict[str, Any],
) -> None:
    encoded = json.dumps(record, sort_keys=True, separators=(",", ":")).encode()
    item = next(entry for entry in manifest["evidence"] if entry["kind"] == kind)
    (root / item["path"]).write_bytes(encoded)
    item["sha256"] = hashlib.sha256(encoded).hexdigest()


def _evidence_ready_manifest(
    root: Path,
    *,
    report_type: str = "full",
    template_sha: str = SHA_B,
    structural_sha: str = SHA_D,
    all_features_passed: bool = False,
) -> dict[str, Any]:
    manifest = _ready_manifest(root)
    manifest["reportType"] = report_type
    manifest["identity"]["packId"] = f"synthetic-{report_type.replace('_', '-')}"
    manifest["identity"]["templateSha256"] = template_sha
    manifest["gates"]["baseline"]["templateSha256"] = template_sha
    manifest["gates"]["verification"]["templateSha256"] = template_sha
    manifest["gates"]["baseline"]["structuralSha256"] = structural_sha
    manifest["gates"]["verification"]["structuralSha256"] = structural_sha
    if report_type == "server_only":
        manifest["fixture"].update({"serverCount": 50, "clientCount": 0})
    elif report_type == "client_only":
        manifest["fixture"].update({"serverCount": 0, "clientCount": 50})
    if all_features_passed:
        manifest["gates"]["features"] = {
            feature: "passed" for feature in manifest["gates"]["features"]
        }
    identity = manifest["identity"]
    fixture = manifest["fixture"]
    gates = manifest["gates"]
    common = {
        "fixtureId": fixture["fixtureId"],
        "reportType": manifest["reportType"],
        "templateSha256": identity["templateSha256"],
        "workspaceHash": identity["workspaceHash"],
        "structuralSha256": gates["baseline"]["structuralSha256"],
        "fixturePassed": True,
        "integrityPassed": True,
    }
    records = {
        "mapping": {
            "workspaceHash": identity["workspaceHash"],
            "revision": identity["workspaceRevision"],
            "coveragePercent": 100,
            "missingSemantics": [],
        },
        "baseline-validation": {
            **common,
            "runId": gates["baseline"]["runId"],
            "artifactSha256": gates["baseline"]["artifactSha256"],
            "structuralPassed": False,
            "issues": [{"code": "structural.baseline_missing"}],
        },
        "verification-validation": {
            **common,
            "runId": gates["verification"]["runId"],
            "artifactSha256": gates["verification"]["artifactSha256"],
            "structuralPassed": True,
            "baselineSha256": gates["baseline"]["structuralSha256"],
            "issues": [],
        },
        "golden-diff": {
            "artifactSha256": gates["verification"]["artifactSha256"],
            "unexpectedDiffCount": 0,
        },
        "feature-checklist": {"features": gates["features"]},
        "visual-review": {
            "approved": True,
            "reviewer": gates["visual"]["reviewer"],
            "artifactSha256": gates["visual"]["artifactSha256"],
        },
        "benchmark": {
            "reportType": manifest["reportType"],
            "trials": [
                {
                    "status": "passed",
                    "assetCount": gates["benchmark"]["targetAssetCount"],
                    "totalSeconds": 2.5 if index == 9 else 2.0,
                    "observedPeakRssMiB": 128.0 if index == 9 else 96.0,
                    "legacyRendererUsed": False,
                }
                for index in range(10)
            ],
        },
        "recovery": gates["recovery"],
        "quality-gate": gates["quality"],
    }
    for kind, record in records.items():
        _write_record(root, manifest, kind, record)
    return manifest


class TemplatePilotPreflightTests(unittest.TestCase):
    def test_verified_records_derive_ready_state(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = _evidence_ready_manifest(root)
            issues = preflight_pilot_manifest(manifest, evidence_root=root)

        self.assertEqual([], issues)

    def test_mapping_claim_cannot_hide_incomplete_record(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = _evidence_ready_manifest(root)
            _write_record(
                root,
                manifest,
                "mapping",
                {
                    "workspaceHash": manifest["identity"]["workspaceHash"],
                    "revision": manifest["identity"]["workspaceRevision"],
                    "coveragePercent": 98,
                    "missingSemantics": ["asset.investigation"],
                },
            )
            issues = preflight_pilot_manifest(manifest, evidence_root=root)

        self.assertIn("record.mapping_incomplete", {issue.code for issue in issues})

    def test_verification_must_bind_to_baseline_and_workspace(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = _evidence_ready_manifest(root)
            record = {
                "fixtureId": manifest["fixture"]["fixtureId"],
                "reportType": manifest["reportType"],
                "runId": manifest["gates"]["verification"]["runId"],
                "templateSha256": manifest["identity"]["templateSha256"],
                "workspaceHash": SHA_A,
                "artifactSha256": manifest["gates"]["verification"]["artifactSha256"],
                "structuralSha256": manifest["gates"]["verification"]["structuralSha256"],
                "fixturePassed": True,
                "integrityPassed": True,
                "structuralPassed": True,
                "baselineSha256": SHA_B,
                "issues": [],
            }
            _write_record(root, manifest, "verification-validation", record)
            issues = preflight_pilot_manifest(manifest, evidence_root=root)

        codes = {issue.code for issue in issues}
        self.assertIn("record.validation_identity", codes)
        self.assertIn("record.baseline_binding", codes)

    def test_raw_benchmark_failure_and_legacy_use_are_blockers(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = _evidence_ready_manifest(root)
            trials = [
                {
                    "status": "passed",
                    "assetCount": 1000,
                    "totalSeconds": 2.0,
                    "observedPeakRssMiB": 128.0,
                    "legacyRendererUsed": False,
                }
                for _ in range(10)
            ]
            trials[3]["status"] = "failed"
            trials[4]["legacyRendererUsed"] = True
            _write_record(
                root,
                manifest,
                "benchmark",
                {"reportType": "full", "trials": trials},
            )
            issues = preflight_pilot_manifest(manifest, evidence_root=root)

        codes = {issue.code for issue in issues}
        self.assertIn("record.benchmark_failed", codes)
        self.assertIn("record.benchmark_trials", codes)

    def test_duplicate_or_non_finite_evidence_json_is_unreadable(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for payload in (
                b'{"coveragePercent":100,"coveragePercent":100}',
                b'{"coveragePercent":NaN}',
            ):
                manifest = _evidence_ready_manifest(root)
                item = next(entry for entry in manifest["evidence"] if entry["kind"] == "mapping")
                (root / item["path"]).write_bytes(payload)
                item["sha256"] = hashlib.sha256(payload).hexdigest()
                issues = preflight_pilot_manifest(manifest, evidence_root=root)
                self.assertIn("record.unreadable", {issue.code for issue in issues})

    def test_manifest_errors_do_not_make_preflight_crash(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            manifest = _evidence_ready_manifest(root)
            malformed = copy.deepcopy(manifest)
            malformed["gates"]["benchmark"]["targetAssetCount"] = None
            issues = preflight_pilot_manifest(malformed, evidence_root=root)

        self.assertIn("benchmark.scale", {issue.code for issue in issues})


if __name__ == "__main__":
    unittest.main()
