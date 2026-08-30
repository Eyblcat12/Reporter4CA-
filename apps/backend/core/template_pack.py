"""Read-only inspection for Reporter Pro Template Pack archives.

Version 1 packs are deliberately data-only.  They cannot contain Python,
executables or plugins, and this module never extracts files or activates a
renderer.  Installation and rendering will be separate, feature-gated phases.
"""

from __future__ import annotations

import hashlib
import io
import json
import stat
import zipfile
from dataclasses import dataclass
from pathlib import PurePosixPath
from typing import Any

from .template_analyzer import validate_docx_bytes
from .template_profiles import ProfileValidationResult, validate_template_profile

PACK_FORMAT_VERSION = "1.0"
MAX_PACK_SIZE = 25 * 1024 * 1024
MAX_PACK_ENTRIES = 16
MAX_UNCOMPRESSED_SIZE = 100 * 1024 * 1024
MAX_COMPRESSION_RATIO = 200
REQUIRED_MEMBERS = frozenset(
    {"manifest.json", "layout.json", "mapping.json", "validation.json", "template.docx"}
)


class TemplatePackError(ValueError):
    """Raised when an archive is unsafe, malformed or not publication-ready."""


@dataclass(frozen=True)
class TemplatePackInspection:
    pack_id: str
    version: str
    template_sha256: str
    profile: dict[str, Any]
    validation: ProfileValidationResult
    template_bytes: bytes

    @property
    def publishable(self) -> bool:
        return self.validation.publishable

    def public(self) -> dict[str, Any]:
        return {
            "packId": self.pack_id,
            "version": self.version,
            "templateSha256": self.template_sha256,
            "publishable": self.publishable,
            "profile": self.validation.public(),
        }


def inspect_template_pack(
    data: bytes,
    *,
    require_publishable: bool = True,
) -> TemplatePackInspection:
    """Inspect an in-memory pack without extracting or installing it."""

    if not data:
        raise TemplatePackError("Template Pack is empty.")
    if len(data) > MAX_PACK_SIZE:
        raise TemplatePackError("Template Pack exceeds the 25 MiB archive limit.")
    if not data.startswith(b"PK"):
        raise TemplatePackError("Template Pack is not a ZIP archive.")

    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members = _validate_archive(archive)
            manifest = _read_json(archive, "manifest.json")
            layout = _read_json(archive, "layout.json")
            mapping = _read_json(archive, "mapping.json")
            evidence = _read_json(archive, "validation.json")
            template_bytes = archive.read(members["template.docx"])
    except (zipfile.BadZipFile, RuntimeError) as exc:
        raise TemplatePackError("Template Pack ZIP is invalid.") from exc

    _validate_manifest(manifest)
    _validate_pack_documents(layout, mapping, evidence)
    pack_id = _required_text(manifest, "packId", "manifest.json")
    version = _required_text(manifest, "version", "manifest.json")
    checksums = manifest.get("checksums")
    if not isinstance(checksums, dict):
        raise TemplatePackError("manifest.json checksums must be an object.")

    payloads = {
        "template.docx": template_bytes,
        "layout.json": _canonical_json_bytes(layout),
        "mapping.json": _canonical_json_bytes(mapping),
        "validation.json": _canonical_json_bytes(evidence),
    }
    for name, payload in payloads.items():
        expected = checksums.get(name)
        actual = hashlib.sha256(payload).hexdigest()
        if expected != actual:
            raise TemplatePackError(f"Checksum mismatch for {name}.")

    validate_docx_bytes(template_bytes)
    _validate_docx_package(template_bytes)
    profile = _combine_profile(
        layout, mapping, evidence, hashlib.sha256(template_bytes).hexdigest()
    )
    if profile.get("profileId") != pack_id:
        raise TemplatePackError("Pack and profile identifiers do not match.")
    if profile.get("version") != version:
        raise TemplatePackError("Pack and profile versions do not match.")

    result = validate_template_profile(profile)
    if require_publishable and not result.publishable:
        reasons = [issue.message for issue in (*result.errors, *result.warnings)]
        detail = reasons[0] if reasons else "Profile did not pass the publication gate."
        raise TemplatePackError(f"Template Pack is not publishable: {detail}")
    return TemplatePackInspection(
        pack_id,
        version,
        payloads_sha256(template_bytes),
        profile,
        result,
        template_bytes,
    )


def payloads_sha256(payload: bytes) -> str:
    """Return a stable lowercase SHA-256 digest for a pack payload."""

    return hashlib.sha256(payload).hexdigest()


def _validate_archive(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    infos = archive.infolist()
    if len(infos) > MAX_PACK_ENTRIES:
        raise TemplatePackError("Template Pack contains too many files.")
    members: dict[str, zipfile.ZipInfo] = {}
    total = 0
    for info in infos:
        name = info.filename
        path = PurePosixPath(name)
        if (
            not name
            or "\\" in name
            or path.is_absolute()
            or ".." in path.parts
            or ":" in name
            or info.is_dir()
        ):
            raise TemplatePackError(f"Unsafe archive member: {name!r}.")
        if name in members:
            raise TemplatePackError(f"Duplicate archive member: {name}.")
        if info.flag_bits & 0x1:
            raise TemplatePackError(f"Encrypted archive members are not supported: {name}.")
        unix_mode = (info.external_attr >> 16) & 0xFFFF
        if unix_mode and stat.S_ISLNK(unix_mode):
            raise TemplatePackError(f"Symbolic links are not allowed: {name}.")
        total += info.file_size
        if total > MAX_UNCOMPRESSED_SIZE:
            raise TemplatePackError("Template Pack expands beyond the 100 MiB safety limit.")
        if info.compress_size == 0 and info.file_size > 0:
            raise TemplatePackError(f"Invalid compression metadata for {name}.")
        if info.compress_size and info.file_size / info.compress_size > MAX_COMPRESSION_RATIO:
            raise TemplatePackError(f"Suspicious compression ratio for {name}.")
        members[name] = info

    actual = frozenset(members)
    missing = sorted(REQUIRED_MEMBERS - actual)
    extra = sorted(actual - REQUIRED_MEMBERS)
    if missing:
        raise TemplatePackError(f"Template Pack is missing: {', '.join(missing)}.")
    if extra:
        raise TemplatePackError(f"Template Pack contains unsupported files: {', '.join(extra)}.")
    return members


def _read_json(archive: zipfile.ZipFile, name: str) -> dict[str, Any]:
    try:
        value = json.loads(archive.read(name).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError) as exc:
        raise TemplatePackError(f"{name} is not valid UTF-8 JSON.") from exc
    if not isinstance(value, dict):
        raise TemplatePackError(f"{name} must contain a JSON object.")
    return value


def _canonical_json_bytes(value: dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _validate_manifest(manifest: dict[str, Any]) -> None:
    _reject_unknown_keys(
        manifest,
        {"formatVersion", "packId", "version", "checksums"},
        "manifest.json",
    )
    if manifest.get("formatVersion") != PACK_FORMAT_VERSION:
        raise TemplatePackError(f"Template Pack formatVersion must be {PACK_FORMAT_VERSION}.")
    _required_text(manifest, "packId", "manifest.json")
    _required_text(manifest, "version", "manifest.json")
    checksums = manifest.get("checksums")
    if isinstance(checksums, dict):
        expected = {"template.docx", "layout.json", "mapping.json", "validation.json"}
        _reject_unknown_keys(checksums, expected, "manifest.json checksums")
        missing = sorted(expected - set(checksums))
        if missing:
            raise TemplatePackError(f"manifest.json checksums is missing: {', '.join(missing)}.")


def _validate_pack_documents(
    layout: dict[str, Any],
    mapping: dict[str, Any],
    evidence: dict[str, Any],
) -> None:
    _reject_unknown_keys(
        layout,
        {"schemaVersion", "profileId", "displayName", "version", "reportType", "status", "slots"},
        "layout.json",
    )
    raw_layout_slots = layout.get("slots")
    if isinstance(raw_layout_slots, list):
        if len(raw_layout_slots) > 256:
            raise TemplatePackError("layout.json contains too many slots.")
        for index, slot in enumerate(raw_layout_slots):
            if isinstance(slot, dict):
                _reject_unknown_keys(
                    slot,
                    {"id", "semantic", "renderer", "anchor", "repeat"},
                    f"layout.json slots[{index}]",
                )
                anchor = slot.get("anchor")
                if isinstance(anchor, dict):
                    _reject_unknown_keys(
                        anchor,
                        {"kind", "value"},
                        f"layout.json slots[{index}].anchor",
                    )

    _reject_unknown_keys(mapping, {"profileId", "slots"}, "mapping.json")
    raw_mapping_slots = mapping.get("slots")
    if isinstance(raw_mapping_slots, list):
        if len(raw_mapping_slots) > 256:
            raise TemplatePackError("mapping.json contains too many slots.")
        for index, slot in enumerate(raw_mapping_slots):
            if not isinstance(slot, dict):
                continue
            _reject_unknown_keys(
                slot,
                {"id", "source", "fields"},
                f"mapping.json slots[{index}]",
            )
            fields = slot.get("fields")
            if isinstance(fields, list):
                if len(fields) > 64:
                    raise TemplatePackError(f"mapping.json slot {index} contains too many fields.")
                for field_index, field in enumerate(fields):
                    if isinstance(field, dict):
                        _reject_unknown_keys(
                            field,
                            {"source", "target"},
                            f"mapping.json slots[{index}].fields[{field_index}]",
                        )

    _reject_unknown_keys(
        evidence,
        {
            "fixturePassed",
            "integrityPassed",
            "visualApproved",
            "fixtureId",
            "validatedAt",
            "validatorVersion",
            "validationRunId",
            "artifactSha256",
            "structuralSha256",
            "reviewedBy",
            "reviewedAt",
        },
        "validation.json",
    )


def _reject_unknown_keys(value: dict[str, Any], allowed: set[str], source: str) -> None:
    unknown = sorted(set(value) - allowed)
    if unknown:
        raise TemplatePackError(f"{source} contains unsupported fields: {', '.join(unknown)}.")


def _required_text(value: dict[str, Any], key: str, source: str) -> str:
    result = value.get(key)
    if not isinstance(result, str) or not result.strip():
        raise TemplatePackError(f"{source} requires a non-empty {key}.")
    return result.strip()


def _combine_profile(
    layout: dict[str, Any],
    mapping: dict[str, Any],
    evidence: dict[str, Any],
    template_sha256: str,
) -> dict[str, Any]:
    profile = dict(layout)
    raw_slots = layout.get("slots")
    raw_mappings = mapping.get("slots")
    if not isinstance(raw_slots, list) or not isinstance(raw_mappings, list):
        raise TemplatePackError("layout.json and mapping.json slots must be arrays.")
    if mapping.get("profileId") != layout.get("profileId"):
        raise TemplatePackError("layout.json and mapping.json profileId values do not match.")

    mappings: dict[str, dict[str, Any]] = {}
    for raw_mapping in raw_mappings:
        if not isinstance(raw_mapping, dict):
            raise TemplatePackError("mapping.json contains a non-object slot mapping.")
        slot_id = raw_mapping.get("id")
        if not isinstance(slot_id, str) or not slot_id:
            raise TemplatePackError("Every mapping slot requires an id.")
        if slot_id in mappings:
            raise TemplatePackError(f"Duplicate mapping for slot {slot_id}.")
        mappings[slot_id] = raw_mapping

    combined_slots: list[dict[str, Any]] = []
    layout_slot_ids: set[str] = set()
    for raw_slot in raw_slots:
        if not isinstance(raw_slot, dict):
            raise TemplatePackError("layout.json contains a non-object slot.")
        slot_id = raw_slot.get("id")
        if not isinstance(slot_id, str) or not slot_id:
            raise TemplatePackError("Every layout slot requires an id.")
        layout_slot_ids.add(slot_id)
        slot = dict(raw_slot)
        slot_mapping = mappings.get(slot_id, {})
        slot["source"] = slot_mapping.get("source")
        slot["fields"] = slot_mapping.get("fields", [])
        combined_slots.append(slot)
    orphaned = sorted(set(mappings) - layout_slot_ids)
    if orphaned:
        raise TemplatePackError(f"Mappings reference unknown slots: {', '.join(orphaned)}.")

    profile["slots"] = combined_slots
    profile["validation"] = evidence
    profile["templateSha256"] = template_sha256
    return profile


def _validate_docx_package(data: bytes) -> None:
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as document:
            names = set(document.namelist())
    except zipfile.BadZipFile as exc:
        raise TemplatePackError("template.docx is not a valid Office ZIP package.") from exc
    required = {"[Content_Types].xml", "word/document.xml"}
    if not required.issubset(names):
        raise TemplatePackError("template.docx is missing required Word document parts.")
