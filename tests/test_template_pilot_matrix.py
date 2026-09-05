from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.preflight_template_pilot_matrix import preflight_pilot_matrix
from tests.test_template_pilot_preflight import _evidence_ready_manifest


class TemplatePilotMatrixTests(unittest.TestCase):
    def _matrix(self, root: Path):
        pilots = []
        for report_type, marker in (
            ("full", "1"),
            ("server_only", "2"),
            ("client_only", "3"),
        ):
            pilot_root = root / report_type
            pilot_root.mkdir(parents=True)
            manifest = _evidence_ready_manifest(
                pilot_root,
                report_type=report_type,
                template_sha=marker * 64,
                structural_sha=str(int(marker) + 3) * 64,
                all_features_passed=True,
            )
            pilots.append((manifest, pilot_root))
        return pilots

    def test_three_distinct_core_templates_are_matrix_ready(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            pilots = self._matrix(Path(temporary))
            matrix_issues, pilot_issues = preflight_pilot_matrix(pilots)

        self.assertEqual([], matrix_issues)
        self.assertTrue(all(not issues for issues in pilot_issues))

    def test_duplicate_structure_and_missing_scope_are_blocked(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            pilots = self._matrix(Path(temporary))
            pilots.pop()
            pilots[1][0]["gates"]["verification"]["structuralSha256"] = pilots[0][0]["gates"][
                "verification"
            ]["structuralSha256"]
            matrix_issues, _pilot_issues = preflight_pilot_matrix(pilots)

        codes = {issue.code for issue in matrix_issues}
        self.assertIn("matrix.sample_count", codes)
        self.assertIn("matrix.report_type_coverage", codes)
        self.assertIn("matrix.structure_diversity", codes)

    def test_matrix_cannot_hide_an_individual_evidence_failure(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            pilots = self._matrix(Path(temporary))
            pilots[0][0]["evidence"][0]["sha256"] = "f" * 64
            matrix_issues, pilot_issues = preflight_pilot_matrix(pilots)

        self.assertIn("matrix.pilot_blocked", {issue.code for issue in matrix_issues})
        self.assertTrue(pilot_issues[0])

    def test_capability_union_must_be_proven(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            pilots = self._matrix(Path(temporary))
            for manifest, _root in pilots:
                manifest["gates"]["features"]["images"] = "not_applicable"
            matrix_issues, _pilot_issues = preflight_pilot_matrix(pilots)

        self.assertIn("matrix.capability_coverage", {issue.code for issue in matrix_issues})


if __name__ == "__main__":
    unittest.main()
