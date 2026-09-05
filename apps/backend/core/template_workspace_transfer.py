"""Portable, data-only transfer archives for Template Studio mapping drafts."""

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
from .template_mapping_workspace import (
    TemplateMappingWorkspaceError,
    clone_mapping_workspace,
    validate_mapping_workspace_document,
)

DRAFT_FORMAT_VERSION = "1.0"
DRAFT_KIND = "reporter-template-workspace-draft"
MAX_DRAFT_ARCHIVE_SIZE = 30 * 1024 * 1024
MAX_DRAFT_UNCOMPRESSED_SIZE = 55 * 1024 * 1024
MAX_DRAFT_JSON_SIZE = 5 * 1024 * 1024
MAX_DRAFT_COMPRESSION_RATIO = 200
REQUIRED_DRAFT_MEMBERS = frozenset({"manifest.json", "workspace.json", "template.docx"})


class TemplateWorkspaceTransferError(ValueError):
    """Raised when a portable draft is unsafe, corrupt or incompatible."""


@dataclass(frozen=True)
class ImportedTemplateWorkspace:
    workspace: dict[str, Any]
    template_bytes: bytes
    archive_sha256: str


def export_template_workspace(workspace: dict[str, Any], template_bytes: bytes) -> bytes:
    """Build a deterministic draft archive without local paths or executable content."""

    try:
        validated = validate_mapping_workspace_document(workspace)
    except TemplateMappingWorkspaceError as exc:
        raise TemplateWorkspaceTransferError(str(exc)) from exc
    if validated.get("status") in {"test_passed", "published"}:
        raise TemplateWorkspaceTransferError("Only authoring drafts can be exported.")
    _validate_template_source(validated, template_bytes)
    workspace_payload = _canonical_json(validated)
    if len(workspace_payload) > MAX_DRAFT_JSON_SIZE:
        raise TemplateWorkspaceTransferError("Workspace metadata exceeds the 5 MiB limit.")
    payloads = {
        "workspace.json": workspace_payload,
        "template.docx": template_bytes,
    }
    manifest = {
        "formatVersion": DRAFT_FORMAT_VERSION,
        "kind": DRAFT_KIND,
        "sourceWorkspaceId": validated["workspaceId"],
        "sourceRevision": validated["revision"],
        "checksums": {
            name: hashlib.sha256(payload).hexdigest() for name, payload in payloads.items()
        },
    }
    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        _write_deterministic(archive, "manifest.json", _canonical_json(manifest))
        _write_deterministic(archive, "workspace.json", workspace_payload)
        _write_deterministic(archive, "template.docx", template_bytes)
    data = output.getvalue()
    if len(data) > MAX_DRAFT_ARCHIVE_SIZE:
        raise TemplateWorkspaceTransferError("Draft archive exceeds the 30 MiB limit.")
    # Self-inspect before returning bytes to a user or teammate.
    inspect_template_workspace_archive(data)
    return data


def inspect_template_workspace_archive(
    data: bytes,
    *,
    actor: str = "local-user",
) -> ImportedTemplateWorkspace:
    """Inspect and normalize a draft archive without extracting or persisting it."""

    if not data:
        raise TemplateWorkspaceTransferError("Draft archive is empty.")
    if len(data) > MAX_DRAFT_ARCHIVE_SIZE:
        raise TemplateWorkspaceTransferError("Draft archive exceeds the 30 MiB limit.")
    if not data.startswith(b"PK"):
        raise TemplateWorkspaceTransferError("Draft archive is not a ZIP archive.")
    try:
        with zipfile.ZipFile(io.BytesIO(data)) as archive:
            members = _validate_archive(archive)
            manifest = _read_json(archive, members["manifest.json"], "manifest.json")
            workspace = _read_json(archive, members["workspace.json"], "workspace.json")
            template_bytes = archive.read(members["template.docx"])
    except (zipfile.BadZipFile, RuntimeError) as exc:
        raise TemplateWorkspaceTransferError("Draft ZIP is invalid.") from exc

    _validate_manifest(manifest)
    payloads = {
        "workspace.json": _canonical_json(workspace),
        "template.docx": template_bytes,
    }
    checksums = manifest["checksums"]
    for name, payload in payloads.items():
        if checksums.get(name) != hashlib.sha256(payload).hexdigest():
            raise TemplateWorkspaceTransferError(f"Checksum mismatch for {name}.")
    try:
        validated = validate_mapping_workspace_document(workspace)
    except TemplateMappingWorkspaceError as exc:
        raise TemplateWorkspaceTransferError(str(exc)) from exc
    if validated.get("status") in {"test_passed", "published"}:
        raise TemplateWorkspaceTransferError("Only authoring drafts can be imported.")
    if (
        manifest["sourceWorkspaceId"] != validated["workspaceId"]
        or manifest["sourceRevision"] != validated["revision"]
    ):
        raise TemplateWorkspaceTransferError("Draft manifest identity does not match workspace.")
    _validate_template_source(validated, template_bytes)
    try:
        imported = clone_mapping_workspace(
            validated,
            profile_id=validated["profileId"],
            display_name=validated["displayName"],
            version=validated["version"],
            expected_revision=validated["revision"],
            actor=actor,
        )
    except TemplateMappingWorkspaceError as exc:
        raise TemplateWorkspaceTransferError(str(exc)) from exc
    imported["audit"][0]["action"] = "workspace.imported"
    imported["workspaceHash"] = _workspace_hash(imported)
    return ImportedTemplateWorkspace(
        workspace=imported,
        template_bytes=template_bytes,
        archive_sha256=hashlib.sha256(data).hexdigest(),
    )


def _validate_template_source(workspace: dict[str, Any], template_bytes: bytes) -> None:
    if hashlib.sha256(template_bytes).hexdigest() != workspace.get("templateSha256"):
        raise TemplateWorkspaceTransferError("Workspace and template checksums do not match.")
    try:
        validate_docx_bytes(template_bytes)
    except ValueError as exc:
        raise TemplateWorkspaceTransferError(f"Draft template is invalid: {exc}") from exc


def _validate_archive(archive: zipfile.ZipFile) -> dict[str, zipfile.ZipInfo]:
    infos = archive.infolist()
    if len(infos) != len(REQUIRED_DRAFT_MEMBERS):
        raise TemplateWorkspaceTransferError("Draft archive must contain exactly three files.")
    members: dict[str, zipfile.ZipInfo] = {}
    expanded_size = 0
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
            raise TemplateWorkspaceTransferError(f"Unsafe draft member: {name!r}.")
        if name in members:
            raise TemplateWorkspaceTransferError(f"Duplicate draft member: {name}.")
        if info.flag_bits & 0x1:
            raise TemplateWorkspaceTransferError("Encrypted draft members are not supported.")
        unix_mode = (info.external_attr >> 16) & 0xFFFF
        if unix_mode and stat.S_ISLNK(unix_mode):
            raise TemplateWorkspaceTransferError("Symbolic links are not allowed in drafts.")
        expanded_size += info.file_size
        if expanded_size > MAX_DRAFT_UNCOMPRESSED_SIZE:
            raise TemplateWorkspaceTransferError("Draft expands beyond the 55 MiB limit.")
        if info.compress_size == 0 and info.file_size > 0:
            raise TemplateWorkspaceTransferError(f"Invalid compression metadata for {name}.")
        if info.compress_size and info.file_size / info.compress_size > MAX_DRAFT_COMPRESSION_RATIO:
            raise TemplateWorkspaceTransferError(f"Suspicious compression ratio for {name}.")
        members[name] = info
    actual = frozenset(members)
    if actual != REQUIRED_DRAFT_MEMBERS:
        missing = sorted(REQUIRED_DRAFT_MEMBERS - actual)
        extra = sorted(actual - REQUIRED_DRAFT_MEMBERS)
        detail = ", ".join(
            [*(f"missing {name}" for name in missing), *(f"extra {name}" for name in extra)]
        )
        raise TemplateWorkspaceTransferError(f"Unsupported draft contents: {detail}.")
    if members["workspace.json"].file_size > MAX_DRAFT_JSON_SIZE:
        raise TemplateWorkspaceTransferError("Workspace metadata exceeds the 5 MiB limit.")
    return members


def _validate_manifest(manifest: dict[str, Any]) -> None:
    expected = {
        "formatVersion",
        "kind",
        "sourceWorkspaceId",
        "sourceRevision",
        "checksums",
    }
    if set(manifest) != expected:
        raise TemplateWorkspaceTransferError("Draft manifest fields are invalid.")
    if manifest.get("formatVersion") != DRAFT_FORMAT_VERSION or manifest.get("kind") != DRAFT_KIND:
        raise TemplateWorkspaceTransferError("Draft format is not supported.")
    source_workspace_id = manifest.get("sourceWorkspaceId")
    source_revision = manifest.get("sourceRevision")
    if not isinstance(source_workspace_id, str) or len(source_workspace_id) != 32:
        raise TemplateWorkspaceTransferError("Draft source workspace identifier is invalid.")
    if (
        isinstance(source_revision, bool)
        or not isinstance(source_revision, int)
        or source_revision < 1
    ):
        raise TemplateWorkspaceTransferError("Draft source revision is invalid.")
    checksums = manifest.get("checksums")
    if not isinstance(checksums, dict) or set(checksums) != {"workspace.json", "template.docx"}:
        raise TemplateWorkspaceTransferError("Draft manifest checksums are invalid.")
    if any(
        not isinstance(value, str)
        or len(value) != 64
        or any(character not in "0123456789abcdef" for character in value)
        for value in checksums.values()
    ):
        raise TemplateWorkspaceTransferError("Draft manifest checksum is invalid.")


def _read_json(
    archive: zipfile.ZipFile,
    info: zipfile.ZipInfo,
    name: str,
) -> dict[str, Any]:
    try:
        value = json.loads(archive.read(info).decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, KeyError) as exc:
        raise TemplateWorkspaceTransferError(f"{name} is not valid UTF-8 JSON.") from exc
    if not isinstance(value, dict):
        raise TemplateWorkspaceTransferError(f"{name} must contain a JSON object.")
    return value


def _write_deterministic(archive: zipfile.ZipFile, name: str, payload: bytes) -> None:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o600 << 16
    archive.writestr(info, payload)


def _canonical_json(value: dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def _workspace_hash(workspace: dict[str, Any]) -> str:
    value = {key: item for key, item in workspace.items() if key != "workspaceHash"}
    return hashlib.sha256(_canonical_json(value)).hexdigest()
