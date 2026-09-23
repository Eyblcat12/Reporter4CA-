"""Validation contract for manually normalized Template Pack profiles.

This module is intentionally independent from the production report generator.
It describes what a future profile renderer may consume, but importing or
validating a profile cannot change the legacy template workflow.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Any

PROFILE_SCHEMA_VERSION = "1.0"
PROFILE_STATUSES = frozenset(
    {
        "draft",
        "analyzed",
        "mapping_incomplete",
        "mapping_complete",
        "test_failed",
        "test_passed",
        "published",
    }
)
ANCHOR_KINDS = frozenset({"content_control", "bookmark", "token"})
REPEAT_MODES = frozenset({"once", "per_asset", "per_finding", "per_ioc", "per_timeline_event"})
_IDENTIFIER_PATTERN = re.compile(r"^[a-z0-9][a-z0-9._-]{1,127}$")
_SHA256_PATTERN = re.compile(r"^[0-9a-f]{64}$")
_TOKEN_PATTERN = re.compile(r"^\{\{[A-Z][A-Z0-9_]{1,126}\}\}$")


@dataclass(frozen=True)
class SemanticRequirement:
    renderer: str
    source: str
    required_fields: tuple[str, ...] = ()


COMMON_REQUIREMENTS = {
    "report.title": SemanticRequirement("text", "metadata.title"),
    "overview": SemanticRequirement("rich_text", "analysis.overview"),
    "investigation": SemanticRequirement("finding_sections", "analysis.findings"),
    "remediation": SemanticRequirement(
        "remediation_table",
        "analysis.affected_assets",
        ("hostname", "ip", "status"),
    ),
    "ioc": SemanticRequirement("ioc_table", "analysis.iocs", ("type", "value")),
    "recommendations": SemanticRequirement("rich_text", "analysis.recommendations"),
    "inventory.server": SemanticRequirement(
        "asset_table", "assets.servers", ("hostname", "ip", "os")
    ),
    "inventory.client": SemanticRequirement(
        "asset_table", "assets.clients", ("hostname", "ip", "os")
    ),
    "results.server": SemanticRequirement(
        "result_table", "analysis.server_results", ("hostname", "result")
    ),
    "results.client": SemanticRequirement(
        "result_table", "analysis.client_results", ("hostname", "result")
    ),
    "results.summary": SemanticRequirement("summary_table", "analysis.summary"),
    "findings": SemanticRequirement("finding_table", "analysis.findings"),
    "incident.info": SemanticRequirement("field_group", "incident.info"),
    "executive_summary": SemanticRequirement("rich_text", "incident.executive_summary"),
    "affected_assets": SemanticRequirement(
        "asset_table", "incident.affected_assets", ("hostname", "ip")
    ),
    "timeline": SemanticRequirement(
        "timeline_table", "incident.timeline", ("timestamp", "event", "evidence")
    ),
    "mitre": SemanticRequirement(
        "mitre_table", "incident.mitre", ("technique_id", "technique", "tactic")
    ),
    "response": SemanticRequirement("response_sections", "incident.response"),
    "lessons": SemanticRequirement("rich_text", "incident.lessons_learned"),
}

REPORT_REQUIREMENTS: dict[str, tuple[str, ...]] = {
    "full": (
        "report.title",
        "overview",
        "inventory.server",
        "inventory.client",
        "results.server",
        "results.client",
        "investigation",
        "remediation",
        "ioc",
        "recommendations",
    ),
    "server_only": (
        "report.title",
        "overview",
        "inventory.server",
        "results.server",
        "investigation",
        "remediation",
        "ioc",
        "recommendations",
    ),
    "client_only": (
        "report.title",
        "overview",
        "inventory.client",
        "results.client",
        "investigation",
        "remediation",
        "ioc",
        "recommendations",
    ),
    "summary": (
        "report.title",
        "overview",
        "results.summary",
        "findings",
        "recommendations",
    ),
    "technical": (
        "report.title",
        "overview",
        "inventory.server",
        "inventory.client",
        "findings",
        "investigation",
        "remediation",
        "ioc",
        "recommendations",
    ),
    "incident_response": (
        "report.title",
        "incident.info",
        "executive_summary",
        "affected_assets",
        "timeline",
        "findings",
        "ioc",
        "mitre",
        "response",
        "lessons",
        "recommendations",
    ),
}


@dataclass(frozen=True)
class ProfileIssue:
    code: str
    path: str
    message: str

    def public(self) -> dict[str, str]:
        return {"code": self.code, "path": self.path, "message": self.message}


@dataclass(frozen=True)
class ProfileValidationResult:
    profile_id: str
    report_type: str
    structural_valid: bool
    mapping_complete: bool
    coverage_percent: float
    publishable: bool
    mapped_semantics: tuple[str, ...]
    missing_semantics: tuple[str, ...]
    errors: tuple[ProfileIssue, ...]
    warnings: tuple[ProfileIssue, ...]

    def public(self) -> dict[str, Any]:
        return {
            "profileId": self.profile_id,
            "reportType": self.report_type,
            "structuralValid": self.structural_valid,
            "mappingComplete": self.mapping_complete,
            "coveragePercent": self.coverage_percent,
            "publishable": self.publishable,
            "mappedSemantics": list(self.mapped_semantics),
            "missingSemantics": list(self.missing_semantics),
            "errors": [issue.public() for issue in self.errors],
            "warnings": [issue.public() for issue in self.warnings],
        }


def validate_template_profile(profile: Any) -> ProfileValidationResult:
    """Validate structure, semantic coverage and publication evidence.

    A required semantic counts as mapped only when its renderer, source and
    required field mappings match the canonical contract.  This makes the 100%
    gate measurable instead of relying on a user-entered percentage.
    """

    errors: list[ProfileIssue] = []
    warnings: list[ProfileIssue] = []
    if not isinstance(profile, dict):
        issue = ProfileIssue("profile.type", "$", "Profile must be a JSON object.")
        return ProfileValidationResult("", "", False, False, 0.0, False, (), (), (issue,), ())

    profile_id = _text(profile.get("profileId"))
    report_type = _text(profile.get("reportType"))
    status = _text(profile.get("status"))
    schema_version = _text(profile.get("schemaVersion"))

    if not _IDENTIFIER_PATTERN.fullmatch(profile_id):
        errors.append(
            ProfileIssue(
                "profile.id",
                "profileId",
                "profileId must be a lowercase stable identifier (2-128 characters).",
            )
        )
    if schema_version != PROFILE_SCHEMA_VERSION:
        errors.append(
            ProfileIssue(
                "profile.schema_version",
                "schemaVersion",
                f"schemaVersion must be {PROFILE_SCHEMA_VERSION}.",
            )
        )
    if report_type not in REPORT_REQUIREMENTS:
        errors.append(ProfileIssue("profile.report_type", "reportType", "Unsupported report type."))
    if status not in PROFILE_STATUSES:
        errors.append(ProfileIssue("profile.status", "status", "Unsupported profile status."))
    if not _text(profile.get("displayName")):
        errors.append(
            ProfileIssue("profile.display_name", "displayName", "displayName is required.")
        )
    if not _text(profile.get("version")):
        errors.append(ProfileIssue("profile.version", "version", "version is required."))

    slots = profile.get("slots")
    if not isinstance(slots, list):
        errors.append(ProfileIssue("slots.type", "slots", "slots must be an array."))
        slots = []

    slot_ids: set[str] = set()
    anchor_keys: set[tuple[str, str]] = set()
    valid_semantics: set[str] = set()
    for index, raw_slot in enumerate(slots):
        path = f"slots[{index}]"
        if not isinstance(raw_slot, dict):
            errors.append(ProfileIssue("slot.type", path, "Slot must be an object."))
            continue
        slot_id = _text(raw_slot.get("id"))
        semantic = _text(raw_slot.get("semantic"))
        requirement = COMMON_REQUIREMENTS.get(semantic)
        if not _IDENTIFIER_PATTERN.fullmatch(slot_id):
            errors.append(ProfileIssue("slot.id", f"{path}.id", "Invalid stable slot identifier."))
        elif slot_id in slot_ids:
            errors.append(ProfileIssue("slot.id_duplicate", f"{path}.id", "Duplicate slot id."))
        else:
            slot_ids.add(slot_id)

        if requirement is None:
            errors.append(
                ProfileIssue("slot.semantic", f"{path}.semantic", "Unknown semantic block.")
            )
            continue

        repeat = _text(raw_slot.get("repeat", "once"))
        if repeat not in REPEAT_MODES:
            errors.append(ProfileIssue("slot.repeat", f"{path}.repeat", "Invalid repeat mode."))

        anchor_valid = _validate_anchor(raw_slot.get("anchor"), path, anchor_keys, errors)
        renderer_valid = _text(raw_slot.get("renderer")) == requirement.renderer
        source_valid = _text(raw_slot.get("source")) == requirement.source
        if not renderer_valid:
            errors.append(
                ProfileIssue(
                    "slot.renderer",
                    f"{path}.renderer",
                    f"Semantic {semantic} requires renderer {requirement.renderer}.",
                )
            )
        if not source_valid:
            errors.append(
                ProfileIssue(
                    "slot.source",
                    f"{path}.source",
                    f"Semantic {semantic} requires source {requirement.source}.",
                )
            )

        mapped_fields = _validate_fields(raw_slot.get("fields", []), requirement, path, errors)
        if anchor_valid and renderer_valid and source_valid and mapped_fields:
            valid_semantics.add(semantic)

    required = REPORT_REQUIREMENTS.get(report_type, ())
    missing = tuple(semantic for semantic in required if semantic not in valid_semantics)
    mapped = tuple(semantic for semantic in required if semantic in valid_semantics)
    coverage = round((len(mapped) / len(required) * 100) if required else 0.0, 2)
    mapping_complete = bool(required) and not missing
    for semantic in missing:
        warnings.append(
            ProfileIssue(
                "mapping.missing",
                "slots",
                f"Required semantic block is not completely mapped: {semantic}.",
            )
        )

    validation = profile.get("validation")
    evidence_ok = False
    if isinstance(validation, dict):
        evidence_ok = all(
            validation.get(field) is True
            for field in ("fixturePassed", "integrityPassed", "visualApproved")
        )
    if not evidence_ok:
        warnings.append(
            ProfileIssue(
                "validation.incomplete",
                "validation",
                "Fixture, integrity and visual validation must all pass before publication.",
            )
        )

    template_sha256 = _text(profile.get("templateSha256")).lower()
    if status == "published" and not _SHA256_PATTERN.fullmatch(template_sha256):
        errors.append(
            ProfileIssue(
                "profile.template_checksum",
                "templateSha256",
                "A published profile requires a lowercase SHA-256 template checksum.",
            )
        )

    structural_valid = not errors
    publishable = (
        structural_valid
        and mapping_complete
        and coverage == 100.0
        and evidence_ok
        and status == "published"
    )
    return ProfileValidationResult(
        profile_id,
        report_type,
        structural_valid,
        mapping_complete,
        coverage,
        publishable,
        mapped,
        missing,
        tuple(errors),
        tuple(warnings),
    )


def _validate_anchor(
    raw_anchor: Any,
    slot_path: str,
    anchor_keys: set[tuple[str, str]],
    errors: list[ProfileIssue],
) -> bool:
    path = f"{slot_path}.anchor"
    if not isinstance(raw_anchor, dict):
        errors.append(ProfileIssue("anchor.type", path, "Anchor must be an object."))
        return False
    kind = _text(raw_anchor.get("kind"))
    value = _text(raw_anchor.get("value"))
    valid = True
    if kind not in ANCHOR_KINDS:
        errors.append(ProfileIssue("anchor.kind", f"{path}.kind", "Unsupported anchor kind."))
        valid = False
    if not value or len(value) > 128:
        errors.append(ProfileIssue("anchor.value", f"{path}.value", "Invalid anchor value."))
        valid = False
    elif kind == "token" and not _TOKEN_PATTERN.fullmatch(value):
        errors.append(
            ProfileIssue(
                "anchor.token",
                f"{path}.value",
                "Token anchors must use the {{UPPER_SNAKE_CASE}} form.",
            )
        )
        valid = False
    key = (kind, value)
    if key in anchor_keys:
        errors.append(ProfileIssue("anchor.duplicate", path, "Duplicate anchor target."))
        valid = False
    elif kind and value:
        anchor_keys.add(key)
    return valid


def _validate_fields(
    raw_fields: Any,
    requirement: SemanticRequirement,
    slot_path: str,
    errors: list[ProfileIssue],
) -> bool:
    if not isinstance(raw_fields, list):
        errors.append(
            ProfileIssue("fields.type", f"{slot_path}.fields", "fields must be an array.")
        )
        return False
    sources: set[str] = set()
    targets: set[str] = set()
    for index, raw_field in enumerate(raw_fields):
        path = f"{slot_path}.fields[{index}]"
        if not isinstance(raw_field, dict):
            errors.append(ProfileIssue("field.type", path, "Field mapping must be an object."))
            continue
        source = _text(raw_field.get("source"))
        target = _text(raw_field.get("target"))
        if not source or not target:
            errors.append(
                ProfileIssue("field.mapping", path, "Both source and target are required.")
            )
            continue
        if source in sources:
            errors.append(
                ProfileIssue("field.source_duplicate", f"{path}.source", "Duplicate field source.")
            )
        if target in targets:
            errors.append(
                ProfileIssue("field.target_duplicate", f"{path}.target", "Duplicate field target.")
            )
        sources.add(source)
        targets.add(target)
    missing = [field for field in requirement.required_fields if field not in sources]
    if missing:
        errors.append(
            ProfileIssue(
                "fields.required_missing",
                f"{slot_path}.fields",
                f"Missing required field mappings: {', '.join(missing)}.",
            )
        )
    expected_targets = {
        f"column:{index}" for index in range(1, len(requirement.required_fields) + 1)
    }
    columns_valid = targets == expected_targets
    if not columns_valid:
        errors.append(
            ProfileIssue(
                "fields.columns_noncontiguous",
                f"{slot_path}.fields",
                "Table columns must be contiguous from column:1 with no unmapped columns.",
            )
        )
    return not missing and columns_valid


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""
