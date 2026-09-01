"""Derive Template Studio pilot readiness from checksum-verified evidence records."""

from __future__ import annotations

import argparse
import json
import math
from pathlib import Path, PurePosixPath
from typing import Any

try:
    from scripts.validate_template_pilot import (
        MAX_EVIDENCE_BYTES,
        PilotIssue,
        _file_sha256,
        _reject_duplicate_pairs,
        _reject_non_finite,
        _validate_json_complexity,
        load_manifest,
        validate_pilot_manifest,
    )
except ModuleNotFoundError:  # Direct execution from the scripts directory.
    from validate_template_pilot import (  # type: ignore[no-redef]
        MAX_EVIDENCE_BYTES,
        PilotIssue,
        _file_sha256,
        _reject_duplicate_pairs,
        _reject_non_finite,
        _validate_json_complexity,
        load_manifest,
        validate_pilot_manifest,
    )


def _add(issues: list[PilotIssue], code: str, path: str, message: str) -> None:
    issues.append(PilotIssue(code, path, message))


def _read_records(manifest: dict[str, Any], evidence_root: Path) -> dict[str, dict[str, Any]]:
    resolved_root = evidence_root.resolve()
    records: dict[str, dict[str, Any]] = {}
    for item in manifest.get("evidence", []):
        if not isinstance(item, dict) or not isinstance(item.get("path"), str):
            continue
        logical = PurePosixPath(item["path"])
        candidate = (resolved_root / Path(*logical.parts)).resolve()
        try:
            candidate.relative_to(resolved_root)
        except ValueError:
            continue
        if (
            not candidate.is_file()
            or candidate.stat().st_size > min(MAX_EVIDENCE_BYTES, 5 * 1024 * 1024)
            or _file_sha256(candidate) != item.get("sha256")
        ):
            continue
        try:
            value = json.loads(
                candidate.read_text(encoding="utf-8"),
                object_pairs_hook=_reject_duplicate_pairs,
                parse_constant=_reject_non_finite,
            )
            _validate_json_complexity(value)
        except (UnicodeDecodeError, json.JSONDecodeError, RecursionError, ValueError):
            continue
        if isinstance(value, dict) and isinstance(item.get("kind"), str):
            records[item["kind"]] = value
    return records


def _equal(
    issues: list[PilotIssue],
    actual: Any,
    expected: Any,
    path: str,
    code: str,
) -> None:
    if actual != expected:
        _add(issues, code, path, "Evidence record does not match the pinned manifest value.")


def preflight_pilot_manifest(
    manifest: Any,
    *,
    evidence_root: Path,
) -> list[PilotIssue]:
    issues = list(validate_pilot_manifest(manifest, evidence_root=evidence_root))
    if not isinstance(manifest, dict):
        return issues
    records = _read_records(manifest, evidence_root)
    for kind in (
        item.get("kind") for item in manifest.get("evidence", []) if isinstance(item, dict)
    ):
        if isinstance(kind, str) and kind not in records:
            _add(
                issues,
                "record.unreadable",
                f"evidence.{kind}",
                "Evidence record is not readable JSON with the pinned checksum.",
            )

    identity = manifest.get("identity", {})
    fixture = manifest.get("fixture", {})
    gates = manifest.get("gates", {})

    mapping = records.get("mapping", {})
    _equal(
        issues,
        mapping.get("workspaceHash"),
        identity.get("workspaceHash"),
        "evidence.mapping.workspaceHash",
        "record.mapping_identity",
    )
    _equal(
        issues,
        mapping.get("revision"),
        identity.get("workspaceRevision"),
        "evidence.mapping.revision",
        "record.mapping_identity",
    )
    _equal(
        issues,
        mapping.get("coveragePercent"),
        100,
        "evidence.mapping.coveragePercent",
        "record.mapping_incomplete",
    )
    _equal(
        issues,
        mapping.get("missingSemantics"),
        [],
        "evidence.mapping.missingSemantics",
        "record.mapping_incomplete",
    )

    for kind, gate_name, structural_expected in (
        ("baseline-validation", "baseline", False),
        ("verification-validation", "verification", True),
    ):
        record = records.get(kind, {})
        gate = gates.get(gate_name, {})
        for field in (
            "runId",
            "templateSha256",
            "workspaceHash",
            "artifactSha256",
            "structuralSha256",
        ):
            _equal(
                issues,
                record.get(field),
                gate.get(field),
                f"evidence.{kind}.{field}",
                "record.validation_identity",
            )
        _equal(
            issues,
            record.get("fixtureId"),
            fixture.get("fixtureId"),
            f"evidence.{kind}.fixtureId",
            "record.fixture_identity",
        )
        _equal(
            issues,
            record.get("reportType"),
            manifest.get("reportType"),
            f"evidence.{kind}.reportType",
            "record.report_type",
        )
        _equal(
            issues,
            record.get("fixturePassed"),
            True,
            f"evidence.{kind}.fixturePassed",
            "record.validation_failed",
        )
        _equal(
            issues,
            record.get("integrityPassed"),
            True,
            f"evidence.{kind}.integrityPassed",
            "record.validation_failed",
        )
        _equal(
            issues,
            record.get("structuralPassed"),
            structural_expected,
            f"evidence.{kind}.structuralPassed",
            "record.validation_structure",
        )
    baseline = records.get("baseline-validation", {})
    verification = records.get("verification-validation", {})
    _equal(
        issues,
        verification.get("baselineSha256"),
        baseline.get("structuralSha256"),
        "evidence.verification-validation.baselineSha256",
        "record.baseline_binding",
    )
    if verification.get("issues") not in ([], None):
        _add(
            issues,
            "record.validation_issues",
            "evidence.verification-validation.issues",
            "Verification record contains unresolved issues.",
        )

    golden = records.get("golden-diff", {})
    _equal(
        issues,
        golden.get("unexpectedDiffCount"),
        0,
        "evidence.golden-diff.unexpectedDiffCount",
        "record.golden_diff",
    )
    _equal(
        issues,
        golden.get("artifactSha256"),
        gates.get("verification", {}).get("artifactSha256"),
        "evidence.golden-diff.artifactSha256",
        "record.golden_identity",
    )

    feature_record = records.get("feature-checklist", {})
    _equal(
        issues,
        feature_record.get("features"),
        gates.get("features"),
        "evidence.feature-checklist.features",
        "record.feature_mismatch",
    )

    visual = records.get("visual-review", {})
    _equal(
        issues,
        visual.get("approved"),
        True,
        "evidence.visual-review.approved",
        "record.visual_review",
    )
    _equal(
        issues,
        visual.get("reviewer"),
        gates.get("visual", {}).get("reviewer"),
        "evidence.visual-review.reviewer",
        "record.visual_identity",
    )
    _equal(
        issues,
        visual.get("artifactSha256"),
        gates.get("visual", {}).get("artifactSha256"),
        "evidence.visual-review.artifactSha256",
        "record.visual_identity",
    )

    benchmark = records.get("benchmark", {})
    trials = benchmark.get("trials") if isinstance(benchmark.get("trials"), list) else []
    passed_trials = [
        trial for trial in trials if isinstance(trial, dict) and trial.get("status") == "passed"
    ]
    durations = [
        float(item["totalSeconds"])
        for item in passed_trials
        if not isinstance(item.get("totalSeconds"), bool)
        and isinstance(item.get("totalSeconds"), (int, float))
        and math.isfinite(item["totalSeconds"])
        and item["totalSeconds"] >= 0
    ]
    peaks = [
        float(item["observedPeakRssMiB"])
        for item in passed_trials
        if not isinstance(item.get("observedPeakRssMiB"), bool)
        and isinstance(item.get("observedPeakRssMiB"), (int, float))
        and math.isfinite(item["observedPeakRssMiB"])
        and item["observedPeakRssMiB"] >= 0
    ]
    targets = [
        item["assetCount"]
        for item in passed_trials
        if not isinstance(item.get("assetCount"), bool)
        and isinstance(item.get("assetCount"), int)
        and item["assetCount"] >= 0
    ]
    manifest_benchmark = gates.get("benchmark", {})
    _equal(
        issues,
        benchmark.get("reportType"),
        manifest.get("reportType"),
        "evidence.benchmark.reportType",
        "record.benchmark_type",
    )
    _equal(
        issues,
        len(passed_trials),
        manifest_benchmark.get("trials"),
        "evidence.benchmark.trials",
        "record.benchmark_trials",
    )
    if (
        len(durations) != len(passed_trials)
        or len(peaks) != len(passed_trials)
        or len(targets) != len(passed_trials)
    ):
        _add(
            issues,
            "record.benchmark_metrics",
            "evidence.benchmark.trials",
            "Every passed trial must contain finite non-negative timing, memory and scale metrics.",
        )
    if len(passed_trials) != len(trials) or any(
        item.get("legacyRendererUsed") is not False for item in passed_trials
    ):
        _add(
            issues,
            "record.benchmark_failed",
            "evidence.benchmark.trials",
            "Every benchmark trial must pass without Legacy Renderer.",
        )
    target_asset_count = manifest_benchmark.get("targetAssetCount")
    if isinstance(target_asset_count, bool) or not isinstance(target_asset_count, int):
        target_asset_count = 0
    if targets and max(targets) < target_asset_count:
        _add(
            issues,
            "record.benchmark_scale",
            "evidence.benchmark.trials",
            "Benchmark record does not cover the declared scale.",
        )
    if durations:
        ordered = sorted(durations)
        p50 = ordered[round((len(ordered) - 1) * 0.50)]
        p95 = ordered[round((len(ordered) - 1) * 0.95)]
        expected_p50 = manifest_benchmark.get("p50Seconds")
        expected_p95 = manifest_benchmark.get("p95Seconds")
        if (
            not isinstance(expected_p50, (int, float))
            or isinstance(expected_p50, bool)
            or not math.isfinite(expected_p50)
            or not isinstance(expected_p95, (int, float))
            or isinstance(expected_p95, bool)
            or not math.isfinite(expected_p95)
            or abs(p50 - float(expected_p50)) > 1e-6
            or abs(p95 - float(expected_p95)) > 1e-6
        ):
            _add(
                issues,
                "record.benchmark_percentile",
                "evidence.benchmark",
                "Benchmark percentiles are not derived from the pinned trials.",
            )
    if peaks:
        expected_peak = manifest_benchmark.get("peakRssMiB")
        if (
            not isinstance(expected_peak, (int, float))
            or isinstance(expected_peak, bool)
            or not math.isfinite(expected_peak)
            or abs(max(peaks) - float(expected_peak)) > 1e-6
        ):
            _add(
                issues,
                "record.benchmark_memory",
                "evidence.benchmark",
                "Peak RSS is not derived from the pinned trials.",
            )

    for kind, expected in (
        ("recovery", gates.get("recovery", {})),
        ("quality-gate", gates.get("quality", {})),
    ):
        record = records.get(kind, {})
        for key, value in expected.items():
            _equal(issues, record.get(key), value, f"evidence.{kind}.{key}", f"record.{kind}")

    return sorted(set(issues), key=lambda item: (item.path, item.code, item.message))


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--evidence-root", required=True, type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    try:
        manifest = load_manifest(arguments.manifest.resolve())
        issues = preflight_pilot_manifest(manifest, evidence_root=arguments.evidence_root.resolve())
    except (OSError, ValueError) as exc:
        print(f"Template pilot preflight failed: {exc}")
        return 2
    report = {
        "schemaVersion": 1,
        "evidenceDerived": True,
        "schemaValid": not any(
            issue.code.startswith(("schema.", "type.", "field.")) for issue in issues
        ),
        "evidenceReady": not issues,
        "integrationApproved": bool(
            not issues
            and isinstance(manifest.get("approvals"), dict)
            and manifest["approvals"].get("integrationApproved") is True
        ),
        "ready": not issues,
        "issueCount": len(issues),
        "issues": [issue.public() for issue in issues],
        "containsEvidenceContent": False,
    }
    encoded = json.dumps(report, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    if arguments.output:
        arguments.output.parent.mkdir(parents=True, exist_ok=True)
        arguments.output.write_text(encoded, encoding="utf-8")
    print(encoded, end="")
    return 0 if not issues else 1


if __name__ == "__main__":
    raise SystemExit(main())
