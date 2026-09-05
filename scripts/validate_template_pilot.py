"""Validate a Template Studio pilot evidence manifest without exposing evidence content."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from dataclasses import dataclass
from pathlib import Path, PurePosixPath
from typing import Any

MAX_MANIFEST_BYTES = 1024 * 1024
MAX_EVIDENCE_BYTES = 100 * 1024 * 1024
REPORT_TYPES = frozenset(
    {"full", "server_only", "client_only", "summary", "technical", "incident_response"}
)
STATUSES = frozenset({"draft", "ready", "approved", "rejected"})
REQUIRED_EVIDENCE = frozenset(
    {
        "mapping",
        "baseline-validation",
        "verification-validation",
        "golden-diff",
        "visual-review",
        "benchmark",
        "recovery",
        "quality-gate",
        "feature-checklist",
    }
)
HEX64 = re.compile(r"^[0-9a-f]{64}$")
SAFE_ID = re.compile(r"^[a-z0-9][a-z0-9._-]{2,127}$")
SEMVER = re.compile(r"^(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)\.(0|[1-9][0-9]*)(?:-[0-9A-Za-z.-]+)?$")
FEATURES = (
    "splitRunToken",
    "bookmarkAnchor",
    "contentControlAnchor",
    "headerFooter",
    "tocFields",
    "numbering",
    "horizontalMergedCells",
    "verticalMergedCells",
    "pageBreaks",
    "sectionBreaks",
    "images",
    "relationships",
)


@dataclass(frozen=True, slots=True)
class PilotIssue:
    code: str
    path: str
    message: str

    def public(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "message": self.message}


def _issue(issues: list[PilotIssue], code: str, path: str, message: str) -> None:
    issues.append(PilotIssue(code, path, message))


def _object(
    value: Any,
    path: str,
    required: set[str],
    issues: list[PilotIssue],
) -> dict[str, Any]:
    if not isinstance(value, dict):
        _issue(issues, "type.object", path, "Must be an object.")
        return {}
    missing = sorted(required - set(value))
    unknown = sorted(set(value) - required)
    for key in missing:
        _issue(issues, "field.missing", f"{path}.{key}", "Required field is missing.")
    for key in unknown:
        _issue(issues, "field.unknown", f"{path}.{key}", "Unknown field is not allowed.")
    return value


def _text(value: Any, path: str, issues: list[PilotIssue]) -> str:
    if not isinstance(value, str) or not value.strip() or len(value) > 256:
        _issue(issues, "type.text", path, "Must be non-empty text up to 256 characters.")
        return ""
    return value.strip()


def _hex(value: Any, path: str, issues: list[PilotIssue]) -> str:
    if not isinstance(value, str) or not HEX64.fullmatch(value):
        _issue(issues, "hash.invalid", path, "Must be a lowercase SHA-256 value.")
        return ""
    return value


def _passed_gate(
    gates: dict[str, Any],
    name: str,
    required: set[str],
    issues: list[PilotIssue],
) -> dict[str, Any]:
    gate = _object(gates.get(name), f"gates.{name}", required, issues)
    if gate.get("passed") is not True:
        _issue(issues, "gate.not_passed", f"gates.{name}.passed", "Gate must pass.")
    return gate


def validate_pilot_manifest(
    manifest: Any,
    *,
    evidence_root: Path | None = None,
) -> list[PilotIssue]:
    issues: list[PilotIssue] = []
    root = _object(
        manifest,
        "$",
        {
            "schemaVersion",
            "pilotId",
            "status",
            "reportType",
            "identity",
            "fixture",
            "gates",
            "approvals",
            "evidence",
        },
        issues,
    )
    if root.get("schemaVersion") != "1.0":
        _issue(
            issues, "schema.unsupported", "schemaVersion", "Only schema version 1.0 is supported."
        )
    pilot_id = root.get("pilotId")
    if not isinstance(pilot_id, str) or not SAFE_ID.fullmatch(pilot_id):
        _issue(issues, "pilot_id.invalid", "pilotId", "Use a stable lowercase pilot identifier.")
    status = root.get("status")
    if status not in STATUSES:
        _issue(issues, "status.invalid", "status", "Pilot status is unsupported.")
    elif status not in {"ready", "approved"}:
        _issue(
            issues,
            "status.not_ready",
            "status",
            "Only ready or approved pilots can pass readiness.",
        )
    report_type = root.get("reportType")
    if report_type not in REPORT_TYPES:
        _issue(issues, "report_type.invalid", "reportType", "Report type is unsupported.")

    identity = _object(
        root.get("identity"),
        "identity",
        {
            "packId",
            "packVersion",
            "packSha256",
            "templateSha256",
            "workspaceHash",
            "workspaceRevision",
        },
        issues,
    )
    pack_id = _text(identity.get("packId"), "identity.packId", issues)
    if pack_id and not SAFE_ID.fullmatch(pack_id):
        _issue(issues, "pack_id.invalid", "identity.packId", "Pack ID is invalid.")
    pack_version = _text(identity.get("packVersion"), "identity.packVersion", issues)
    if pack_version and not SEMVER.fullmatch(pack_version):
        _issue(
            issues,
            "pack_version.invalid",
            "identity.packVersion",
            "Pack version must be semantic versioning.",
        )
    pack_sha = _hex(identity.get("packSha256"), "identity.packSha256", issues)
    template_sha = _hex(identity.get("templateSha256"), "identity.templateSha256", issues)
    workspace_hash = _hex(identity.get("workspaceHash"), "identity.workspaceHash", issues)
    revision = identity.get("workspaceRevision")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        _issue(
            issues, "revision.invalid", "identity.workspaceRevision", "Must be a positive integer."
        )

    fixture = _object(
        root.get("fixture"),
        "fixture",
        {
            "fixtureId",
            "sourceSha256",
            "assetCount",
            "serverCount",
            "clientCount",
            "sanitized",
            "containsCustomerData",
        },
        issues,
    )
    _text(fixture.get("fixtureId"), "fixture.fixtureId", issues)
    _hex(fixture.get("sourceSha256"), "fixture.sourceSha256", issues)
    counts: dict[str, int] = {}
    for name in ("assetCount", "serverCount", "clientCount"):
        value = fixture.get(name)
        if isinstance(value, bool) or not isinstance(value, int) or value < 0:
            _issue(issues, "count.invalid", f"fixture.{name}", "Must be a non-negative integer.")
        else:
            counts[name] = value
    if counts.get("assetCount") != counts.get("serverCount", 0) + counts.get("clientCount", 0):
        _issue(
            issues,
            "fixture.count_mismatch",
            "fixture",
            "Server and client counts must equal assets.",
        )
    if report_type == "server_only" and counts.get("clientCount", 0):
        _issue(
            issues,
            "fixture.scope_mismatch",
            "fixture.clientCount",
            "Server pilot cannot contain clients.",
        )
    if report_type == "client_only" and counts.get("serverCount", 0):
        _issue(
            issues,
            "fixture.scope_mismatch",
            "fixture.serverCount",
            "Client pilot cannot contain servers.",
        )
    if fixture.get("sanitized") is not True or fixture.get("containsCustomerData") is not False:
        _issue(
            issues,
            "fixture.privacy",
            "fixture",
            "Pilot fixture must be sanitized and customer-data free.",
        )

    gates = _object(
        root.get("gates"),
        "gates",
        {
            "mapping",
            "baseline",
            "verification",
            "golden",
            "integrity",
            "features",
            "visual",
            "benchmark",
            "recovery",
            "quality",
        },
        issues,
    )
    mapping = _passed_gate(gates, "mapping", {"passed", "coveragePercent"}, issues)
    if mapping.get("coveragePercent") != 100:
        _issue(
            issues,
            "mapping.incomplete",
            "gates.mapping.coveragePercent",
            "Mapping must be exactly 100%.",
        )
    validation_identity_fields = {
        "runId",
        "templateSha256",
        "workspaceHash",
        "artifactSha256",
        "structuralSha256",
    }
    baseline = _object(
        gates.get("baseline"),
        "gates.baseline",
        validation_identity_fields
        | {"fixturePassed", "integrityPassed", "structuralPassed", "baselineApproved"},
        issues,
    )
    if baseline.get("fixturePassed") is not True or baseline.get("integrityPassed") is not True:
        _issue(
            issues,
            "baseline.content",
            "gates.baseline",
            "Baseline fixture and integrity must pass.",
        )
    if baseline.get("structuralPassed") is not False:
        _issue(
            issues,
            "baseline.first_run",
            "gates.baseline.structuralPassed",
            "First run must record the expected missing-baseline result.",
        )
    if baseline.get("baselineApproved") is not True:
        _issue(
            issues,
            "baseline.not_approved",
            "gates.baseline.baselineApproved",
            "The exact baseline artifact must be approved.",
        )
    verification = _object(
        gates.get("verification"),
        "gates.verification",
        validation_identity_fields | {"fixturePassed", "integrityPassed", "structuralPassed"},
        issues,
    )
    if any(
        verification.get(field) is not True
        for field in ("fixturePassed", "integrityPassed", "structuralPassed")
    ):
        _issue(
            issues,
            "verification.not_passed",
            "gates.verification",
            "Second validation must pass fixture, integrity and structure.",
        )
    for name, gate in (("baseline", baseline), ("verification", verification)):
        _text(gate.get("runId"), f"gates.{name}.runId", issues)
        for field in ("templateSha256", "workspaceHash", "artifactSha256", "structuralSha256"):
            _hex(gate.get(field), f"gates.{name}.{field}", issues)
        if (
            gate.get("templateSha256") != template_sha
            or gate.get("workspaceHash") != workspace_hash
        ):
            _issue(
                issues,
                "validation.identity_mismatch",
                f"gates.{name}",
                "Validation is not bound to the pilot identity.",
            )
    if baseline.get("runId") == verification.get("runId"):
        _issue(
            issues,
            "validation.run_reused",
            "gates.verification.runId",
            "Verification must be a distinct second run.",
        )
    if baseline.get("structuralSha256") != verification.get("structuralSha256"):
        _issue(
            issues,
            "validation.structural_drift",
            "gates.verification.structuralSha256",
            "Second run differs from baseline.",
        )

    golden = _passed_gate(gates, "golden", {"passed", "unexpectedDiffCount"}, issues)
    if golden.get("unexpectedDiffCount") != 0:
        _issue(
            issues,
            "golden.unexpected_diff",
            "gates.golden.unexpectedDiffCount",
            "Unexpected diff count must be zero.",
        )
    _passed_gate(gates, "integrity", {"passed"}, issues)
    features = _object(
        gates.get("features"),
        "gates.features",
        set(FEATURES),
        issues,
    )
    for name in FEATURES:
        if features.get(name) not in {"passed", "not_applicable"}:
            _issue(
                issues,
                "feature.not_assessed",
                f"gates.features.{name}",
                "Feature must be passed or explicitly not applicable.",
            )
    visual = _passed_gate(gates, "visual", {"passed", "reviewer", "artifactSha256"}, issues)
    _text(visual.get("reviewer"), "gates.visual.reviewer", issues)
    _hex(visual.get("artifactSha256"), "gates.visual.artifactSha256", issues)
    if visual.get("artifactSha256") != verification.get("artifactSha256"):
        _issue(
            issues,
            "visual.artifact_mismatch",
            "gates.visual.artifactSha256",
            "Visual review must reference the verification artifact.",
        )
    benchmark = _passed_gate(
        gates,
        "benchmark",
        {
            "passed",
            "outcome",
            "trials",
            "targetAssetCount",
            "p50Seconds",
            "p95Seconds",
            "peakRssMiB",
            "resourceLimited",
            "legacyRendererUsed",
        },
        issues,
    )
    if benchmark.get("outcome") != "passed":
        _issue(
            issues,
            "benchmark.outcome",
            "gates.benchmark.outcome",
            "Benchmark outcome must be passed.",
        )
    if benchmark.get("resourceLimited") is not False:
        _issue(
            issues,
            "benchmark.resource_limited",
            "gates.benchmark.resourceLimited",
            "Resource-limited runs cannot approve a pilot.",
        )
    if benchmark.get("legacyRendererUsed") is not False:
        _issue(
            issues,
            "benchmark.renderer",
            "gates.benchmark.legacyRendererUsed",
            "Template Pack benchmark cannot use Legacy Renderer.",
        )
    if not isinstance(benchmark.get("trials"), int) or benchmark.get("trials", 0) < 10:
        _issue(
            issues,
            "benchmark.samples",
            "gates.benchmark.trials",
            "At least 10 compatible trials are required.",
        )
    if not isinstance(benchmark.get("targetAssetCount"), int) or benchmark.get(
        "targetAssetCount", -1
    ) < counts.get("assetCount", 0):
        _issue(
            issues,
            "benchmark.scale",
            "gates.benchmark.targetAssetCount",
            "Benchmark scale must cover the pilot fixture.",
        )
    for name in ("p50Seconds", "p95Seconds", "peakRssMiB"):
        value = benchmark.get(name)
        if (
            isinstance(value, bool)
            or not isinstance(value, (int, float))
            or not math.isfinite(value)
            or value < 0
        ):
            _issue(
                issues,
                "benchmark.metric",
                f"gates.benchmark.{name}",
                "Metric must be non-negative.",
            )
    if (
        isinstance(benchmark.get("p50Seconds"), (int, float))
        and isinstance(benchmark.get("p95Seconds"), (int, float))
        and benchmark["p95Seconds"] < benchmark["p50Seconds"]
    ):
        _issue(
            issues, "benchmark.percentile", "gates.benchmark.p95Seconds", "P95 cannot be below P50."
        )
    _passed_gate(gates, "recovery", {"passed", "dryRunPassed", "rollbackPassed"}, issues)
    if (
        gates.get("recovery", {}).get("dryRunPassed") is not True
        or gates.get("recovery", {}).get("rollbackPassed") is not True
    ):
        _issue(
            issues, "recovery.incomplete", "gates.recovery", "Dry-run and rollback must both pass."
        )
    quality = _passed_gate(
        gates,
        "quality",
        {"passed", "commitSha", "backendTests", "frontendTests", "productionBuildPassed"},
        issues,
    )
    commit_sha = quality.get("commitSha")
    if not isinstance(commit_sha, str) or not re.fullmatch(r"[0-9a-f]{7,40}", commit_sha):
        _issue(issues, "quality.commit", "gates.quality.commitSha", "Commit SHA is invalid.")
    for name in ("backendTests", "frontendTests"):
        value = quality.get(name)
        if isinstance(value, bool) or not isinstance(value, int) or value < 1:
            _issue(
                issues,
                "quality.tests",
                f"gates.quality.{name}",
                "Passing test count must be positive.",
            )
    if quality.get("productionBuildPassed") is not True:
        _issue(
            issues,
            "quality.build",
            "gates.quality.productionBuildPassed",
            "Production build must pass.",
        )

    approvals = _object(
        root.get("approvals"),
        "approvals",
        {"author", "reviewer", "publisher", "integrationApproved"},
        issues,
    )
    author = _text(approvals.get("author"), "approvals.author", issues)
    reviewer = _text(approvals.get("reviewer"), "approvals.reviewer", issues)
    _text(approvals.get("publisher"), "approvals.publisher", issues)
    if author and reviewer and author.casefold() == reviewer.casefold():
        _issue(
            issues, "approval.separation", "approvals.reviewer", "Reviewer must differ from author."
        )
    if status == "approved" and approvals.get("integrationApproved") is not True:
        _issue(
            issues,
            "approval.integration",
            "approvals.integrationApproved",
            "Explicit opt-in approval is required.",
        )

    evidence = root.get("evidence")
    if not isinstance(evidence, list) or not evidence:
        _issue(issues, "evidence.missing", "evidence", "Evidence records are required.")
        evidence = []
    seen: set[str] = set()
    resolved_root = evidence_root.resolve() if evidence_root is not None else None
    for index, raw in enumerate(evidence):
        item = _object(raw, f"evidence[{index}]", {"kind", "path", "sha256"}, issues)
        kind = item.get("kind")
        if kind not in REQUIRED_EVIDENCE or kind in seen:
            _issue(
                issues,
                "evidence.kind",
                f"evidence[{index}].kind",
                "Evidence kind is invalid or duplicated.",
            )
        elif isinstance(kind, str):
            seen.add(kind)
        relative = item.get("path")
        expected = _hex(item.get("sha256"), f"evidence[{index}].sha256", issues)
        if not isinstance(relative, str):
            _issue(
                issues,
                "evidence.path",
                f"evidence[{index}].path",
                "Evidence path must be relative text.",
            )
            continue
        logical = PurePosixPath(relative)
        if logical.is_absolute() or ".." in logical.parts or ":" in relative or "\\" in relative:
            _issue(issues, "evidence.path", f"evidence[{index}].path", "Unsafe evidence path.")
            continue
        if resolved_root is not None:
            candidate = (resolved_root / Path(*logical.parts)).resolve()
            try:
                candidate.relative_to(resolved_root)
            except ValueError:
                _issue(
                    issues,
                    "evidence.path",
                    f"evidence[{index}].path",
                    "Evidence path escapes its root.",
                )
                continue
            if not candidate.is_file():
                _issue(
                    issues,
                    "evidence.file_missing",
                    f"evidence[{index}].path",
                    "Evidence file is missing.",
                )
            elif candidate.stat().st_size > MAX_EVIDENCE_BYTES:
                _issue(
                    issues,
                    "evidence.file_large",
                    f"evidence[{index}].path",
                    "Evidence file exceeds the 100 MiB verification limit.",
                )
            elif expected and _file_sha256(candidate) != expected:
                _issue(
                    issues,
                    "evidence.hash_mismatch",
                    f"evidence[{index}].sha256",
                    "Evidence checksum does not match.",
                )
    for kind in sorted(REQUIRED_EVIDENCE - seen):
        _issue(issues, "evidence.required", "evidence", f"Missing required evidence kind: {kind}.")
    if status in {"ready", "approved"} and resolved_root is None:
        _issue(
            issues,
            "evidence.not_verified",
            "evidence",
            "Ready pilots require --evidence-root checksum verification.",
        )
    if not pack_sha:
        _issue(issues, "identity.incomplete", "identity", "Pack identity is incomplete.")
    return sorted(issues, key=lambda item: (item.path, item.code, item.message))


def _file_sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        while chunk := handle.read(1024 * 1024):
            digest.update(chunk)
    return digest.hexdigest()


def _reject_duplicate_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError("Pilot manifest contains duplicate JSON fields.")
        result[key] = value
    return result


def _reject_non_finite(_value: str) -> Any:
    raise ValueError("Pilot manifest contains a non-finite number.")


def _validate_json_complexity(value: Any) -> None:
    stack: list[tuple[Any, int]] = [(value, 1)]
    nodes = 0
    while stack:
        current, depth = stack.pop()
        nodes += 1
        if depth > 64 or nodes > 20_000:
            raise ValueError("Pilot manifest JSON exceeds the complexity limit.")
        if isinstance(current, dict):
            stack.extend((item, depth + 1) for item in current.values())
        elif isinstance(current, list):
            stack.extend((item, depth + 1) for item in current)


def load_manifest(path: Path) -> Any:
    if not path.is_file():
        raise ValueError("Pilot manifest does not exist.")
    if path.stat().st_size > MAX_MANIFEST_BYTES:
        raise ValueError("Pilot manifest exceeds the 1 MiB limit.")
    try:
        value = json.loads(
            path.read_text(encoding="utf-8"),
            object_pairs_hook=_reject_duplicate_pairs,
            parse_constant=_reject_non_finite,
        )
        _validate_json_complexity(value)
        return value
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError("Pilot manifest is not valid UTF-8 JSON.") from exc


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path)
    parser.add_argument("--evidence-root", type=Path)
    parser.add_argument("--output", type=Path)
    arguments = parser.parse_args()
    try:
        manifest = load_manifest(arguments.manifest.resolve())
        issues = validate_pilot_manifest(
            manifest,
            evidence_root=arguments.evidence_root.resolve() if arguments.evidence_root else None,
        )
    except (OSError, ValueError) as exc:
        print(f"Template pilot validation failed: {exc}")
        return 2
    report = {
        "schemaVersion": 1,
        "schemaValid": not any(
            issue.code.startswith(("schema.", "type.", "field.")) for issue in issues
        ),
        "evidenceReady": not issues,
        "integrationApproved": bool(
            isinstance(manifest, dict)
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
