"""Evaluate an offline Template Studio pilot matrix without enabling integration."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

try:
    from scripts.preflight_template_pilot import preflight_pilot_manifest
    from scripts.validate_template_pilot import FEATURES, PilotIssue, load_manifest
except ModuleNotFoundError:  # Direct execution from the scripts directory.
    from preflight_template_pilot import preflight_pilot_manifest  # type: ignore[no-redef]
    from validate_template_pilot import (  # type: ignore[no-redef]
        FEATURES,
        PilotIssue,
        load_manifest,
    )

REQUIRED_REPORT_TYPES = frozenset({"full", "server_only", "client_only"})


def _add(issues: list[PilotIssue], code: str, path: str, message: str) -> None:
    issues.append(PilotIssue(code, path, message))


def preflight_pilot_matrix(
    pilots: list[tuple[Any, Path]],
) -> tuple[list[PilotIssue], list[list[PilotIssue]]]:
    matrix_issues: list[PilotIssue] = []
    pilot_issues: list[list[PilotIssue]] = []
    valid_manifests: list[dict[str, Any]] = []

    for index, (manifest, evidence_root) in enumerate(pilots):
        current = preflight_pilot_manifest(manifest, evidence_root=evidence_root)
        pilot_issues.append(current)
        if current:
            _add(
                matrix_issues,
                "matrix.pilot_blocked",
                f"pilots[{index}]",
                "Pilot has unresolved manifest or evidence blockers.",
            )
        if isinstance(manifest, dict):
            valid_manifests.append(manifest)

    if len(pilots) < 3:
        _add(
            matrix_issues,
            "matrix.sample_count",
            "pilots",
            "At least three independently verified templates are required.",
        )

    report_types = {
        item.get("reportType")
        for item in valid_manifests
        if isinstance(item.get("reportType"), str)
    }
    missing_types = sorted(REQUIRED_REPORT_TYPES - report_types)
    if missing_types:
        _add(
            matrix_issues,
            "matrix.report_type_coverage",
            "pilots",
            f"Missing required report types: {', '.join(missing_types)}.",
        )

    template_hashes = [
        item.get("identity", {}).get("templateSha256")
        for item in valid_manifests
        if isinstance(item.get("identity"), dict)
    ]
    if len(set(template_hashes)) != len(pilots):
        _add(
            matrix_issues,
            "matrix.template_diversity",
            "pilots",
            "Every pilot must pin a different template SHA-256.",
        )

    structural_hashes = [
        item.get("gates", {}).get("verification", {}).get("structuralSha256")
        for item in valid_manifests
        if isinstance(item.get("gates"), dict)
        and isinstance(item.get("gates", {}).get("verification"), dict)
    ]
    if len(set(structural_hashes)) != len(pilots):
        _add(
            matrix_issues,
            "matrix.structure_diversity",
            "pilots",
            "Every pilot must prove a distinct verified document structure.",
        )

    commits = {
        item.get("gates", {}).get("quality", {}).get("commitSha")
        for item in valid_manifests
        if isinstance(item.get("gates"), dict)
        and isinstance(item.get("gates", {}).get("quality"), dict)
    }
    if len(commits) != 1:
        _add(
            matrix_issues,
            "matrix.quality_baseline",
            "pilots",
            "All pilots must run against the same quality-gated implementation commit.",
        )

    passed_features: set[str] = set()
    for item in valid_manifests:
        gates = item.get("gates", {})
        feature_results = gates.get("features", {}) if isinstance(gates, dict) else {}
        if isinstance(feature_results, dict):
            passed_features.update(
                name for name, value in feature_results.items() if value == "passed"
            )
    missing_features = sorted(set(FEATURES) - passed_features)
    if missing_features:
        _add(
            matrix_issues,
            "matrix.capability_coverage",
            "pilots",
            f"No pilot proves these Word capabilities: {', '.join(missing_features)}.",
        )

    return (
        sorted(set(matrix_issues), key=lambda item: (item.path, item.code, item.message)),
        pilot_issues,
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--pilot",
        action="append",
        nargs=2,
        metavar=("MANIFEST", "EVIDENCE_ROOT"),
        required=True,
        help="Repeat once per pilot manifest and its evidence root.",
    )
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    try:
        pilots = [
            (load_manifest(Path(manifest_path).resolve()), Path(root_path).resolve())
            for manifest_path, root_path in arguments.pilot
        ]
        matrix_issues, pilot_issues = preflight_pilot_matrix(pilots)
    except (OSError, ValueError) as exc:
        print(f"Template pilot matrix preflight failed: {exc}")
        return 2

    report = {
        "schemaVersion": 1,
        "evidenceDerived": True,
        "matrixReady": not matrix_issues,
        "integrationApproved": bool(
            not matrix_issues
            and all(
                isinstance(manifest, dict)
                and manifest.get("status") == "approved"
                and isinstance(manifest.get("approvals"), dict)
                and manifest["approvals"].get("integrationApproved") is True
                for manifest, _root in pilots
            )
        ),
        "pilotCount": len(pilots),
        "pilotIssueCounts": [len(items) for items in pilot_issues],
        "issueCount": len(matrix_issues),
        "issues": [issue.public() for issue in matrix_issues],
        "containsEvidenceContent": False,
        "performsMutation": False,
    }
    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0 if not matrix_issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
