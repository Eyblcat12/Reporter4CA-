"""Draft mapping workspace for the experimental Template Studio.

The workspace is a pure, revisioned domain model.  It is not imported by the
Legacy Renderer and it cannot publish or render a Template Pack.  Persistence is
opt-in through ``TemplateMappingWorkspaceStore`` and uses atomic JSON writes.
"""

from __future__ import annotations

import base64
import binascii
import copy
import hashlib
import json
import os
import re
import tempfile
import threading
import unicodedata
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .template_profile_analyzer import analyze_profile_template
from .template_profiles import (
    ANCHOR_KINDS,
    COMMON_REQUIREMENTS,
    PROFILE_SCHEMA_VERSION,
    PROFILE_STATUSES,
    REPORT_REQUIREMENTS,
    validate_template_profile,
)

WORKSPACE_SCHEMA_VERSION = "1.0"
MAX_AUDIT_EVENTS = 500
WORKSPACE_LIST_DEFAULT_LIMIT = 20
WORKSPACE_LIST_MAX_LIMIT = 100
WORKSPACE_CURSOR_MAX_LENGTH = 512
WORKSPACE_QUERY_MAX_LENGTH = 100
WORKSPACE_STATUSES = PROFILE_STATUSES
_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._-]{1,127}$")
_COLUMN_TARGET = re.compile(r"^column:[1-9][0-9]{0,2}$")
_WORKSPACE_ID = re.compile(r"^[0-9a-f]{32}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_CURSOR_VERSION = 1


class TemplateMappingWorkspaceError(ValueError):
    """Raised when a draft mapping command violates the workspace contract."""


class TemplateMappingRevisionConflict(TemplateMappingWorkspaceError):
    """Raised when a command was based on an outdated workspace revision."""


class TemplateMappingWorkspaceIndexChanged(TemplateMappingWorkspaceError):
    """Raised when cursor pagination no longer matches the workspace collection."""


def create_mapping_workspace(
    analysis: dict[str, Any],
    *,
    profile_id: str,
    display_name: str,
    version: str = "0.1.0",
    actor: str = "local-user",
    now: datetime | None = None,
) -> dict[str, Any]:
    """Create a zero-coverage draft from an immutable analyzer snapshot."""

    if not _IDENTIFIER.fullmatch(profile_id):
        raise TemplateMappingWorkspaceError("Invalid profile identifier.")
    if not display_name.strip():
        raise TemplateMappingWorkspaceError("Display name is required.")
    if analysis.get("schemaVersion") != PROFILE_SCHEMA_VERSION:
        raise TemplateMappingWorkspaceError("Unsupported analysis schema version.")
    report_type = analysis.get("reportType")
    if report_type not in REPORT_REQUIREMENTS:
        raise TemplateMappingWorkspaceError("Unsupported report type.")
    template_sha256 = analysis.get("templateSha256")
    if not isinstance(template_sha256, str) or not _SHA256.fullmatch(template_sha256):
        raise TemplateMappingWorkspaceError("Analysis requires a valid template checksum.")
    facts = analysis.get("facts")
    if not isinstance(facts, dict):
        raise TemplateMappingWorkspaceError("Analysis facts are required.")

    timestamp = _timestamp(now)
    workspace = {
        "workspaceSchemaVersion": WORKSPACE_SCHEMA_VERSION,
        "workspaceId": uuid.uuid4().hex,
        "profileId": profile_id,
        "displayName": display_name.strip(),
        "version": version.strip() or "0.1.0",
        "reportType": report_type,
        "templateSha256": template_sha256,
        "analysis": copy.deepcopy(analysis),
        "revision": 1,
        "status": "analyzed",
        "archived": False,
        "slots": [],
        "coveragePercent": 0.0,
        "missingSemantics": list(REPORT_REQUIREMENTS[report_type]),
        "createdAt": timestamp,
        "updatedAt": timestamp,
        "audit": [
            {
                "revision": 1,
                "action": "workspace.created",
                "semantic": "",
                "actor": _safe_actor(actor),
                "timestamp": timestamp,
            }
        ],
    }
    workspace["workspaceHash"] = _workspace_hash(workspace)
    return workspace


def approve_semantic_mapping(
    workspace: dict[str, Any],
    *,
    semantic: str,
    anchor: dict[str, str],
    fields: list[dict[str, str]] | None = None,
    expected_revision: int,
    actor: str = "local-user",
    now: datetime | None = None,
) -> dict[str, Any]:
    """Approve one semantic mapping with optimistic concurrency protection."""

    draft = _checked_copy(workspace, expected_revision)
    report_type = draft["reportType"]
    if semantic not in REPORT_REQUIREMENTS[report_type]:
        raise TemplateMappingWorkspaceError(
            f"Semantic {semantic!r} is not required by report type {report_type!r}."
        )
    requirement = COMMON_REQUIREMENTS[semantic]
    validated_anchor = _validate_discovered_anchor(draft["analysis"], anchor)
    for existing_slot in draft["slots"]:
        if existing_slot.get("semantic") == semantic:
            continue
        if existing_slot.get("anchor") == validated_anchor:
            raise TemplateMappingWorkspaceError(
                "Anchor is already mapped to semantic "
                f"{existing_slot.get('semantic', 'unknown')!r}."
            )
    validated_fields = _validate_field_mapping(requirement.required_fields, fields or [])
    slot = {
        "id": semantic.replace(".", "_"),
        "semantic": semantic,
        "renderer": requirement.renderer,
        "source": requirement.source,
        "anchor": validated_anchor,
        "repeat": "once",
        "fields": validated_fields,
    }
    existing = [item for item in draft["slots"] if item.get("semantic") != semantic]
    existing.append(slot)
    draft["slots"] = existing
    return _advance(draft, "mapping.approved", semantic, actor, now)


def remove_semantic_mapping(
    workspace: dict[str, Any],
    *,
    semantic: str,
    expected_revision: int,
    actor: str = "local-user",
    now: datetime | None = None,
) -> dict[str, Any]:
    """Return one approved semantic to the unmapped state."""

    draft = _checked_copy(workspace, expected_revision)
    retained = [item for item in draft["slots"] if item.get("semantic") != semantic]
    if len(retained) == len(draft["slots"]):
        raise TemplateMappingWorkspaceError(f"Semantic {semantic!r} is not mapped.")
    draft["slots"] = retained
    return _advance(draft, "mapping.removed", semantic, actor, now)


def rename_mapping_workspace(
    workspace: dict[str, Any],
    *,
    display_name: str,
    expected_revision: int,
    actor: str = "local-user",
    now: datetime | None = None,
) -> dict[str, Any]:
    """Rename one active draft without changing its profile identity or mappings."""

    draft = _checked_copy(workspace, expected_revision)
    normalized = _normalized_workspace_text(display_name, max_length=200)
    if not normalized:
        raise TemplateMappingWorkspaceError("Display name is required.")
    if normalized == draft["displayName"]:
        raise TemplateMappingWorkspaceError("Workspace display name is unchanged.")
    draft["displayName"] = normalized
    return _advance(draft, "workspace.renamed", "", actor, now)


def set_mapping_workspace_archived(
    workspace: dict[str, Any],
    *,
    archived: bool,
    expected_revision: int,
    actor: str = "local-user",
    now: datetime | None = None,
) -> dict[str, Any]:
    """Archive or restore a draft while retaining all authoring data."""

    draft = _checked_lifecycle_copy(workspace, expected_revision)
    if not isinstance(archived, bool):
        raise TemplateMappingWorkspaceError("Workspace archived state must be boolean.")
    current = draft.get("archived", False)
    if current is archived:
        state = "archived" if archived else "active"
        raise TemplateMappingWorkspaceError(f"Workspace is already {state}.")
    draft["archived"] = archived
    action = "workspace.archived" if archived else "workspace.restored"
    return _advance(draft, action, "", actor, now)


def clone_mapping_workspace(
    workspace: dict[str, Any],
    *,
    profile_id: str,
    display_name: str,
    version: str,
    expected_revision: int,
    actor: str = "local-user",
    now: datetime | None = None,
) -> dict[str, Any]:
    """Create a new active draft from an immutable snapshot of another draft."""

    source = _checked_lifecycle_copy(workspace, expected_revision)
    if not _IDENTIFIER.fullmatch(profile_id):
        raise TemplateMappingWorkspaceError("Invalid profile identifier.")
    normalized_name = _normalized_workspace_text(display_name, max_length=200)
    normalized_version = _normalized_workspace_text(version, max_length=64)
    if not normalized_name:
        raise TemplateMappingWorkspaceError("Display name is required.")
    if not normalized_version:
        raise TemplateMappingWorkspaceError("Version is required.")
    timestamp = _timestamp(now)
    cloned = copy.deepcopy(source)
    cloned.update(
        {
            "workspaceId": uuid.uuid4().hex,
            "profileId": profile_id,
            "displayName": normalized_name,
            "version": normalized_version,
            "revision": 1,
            "archived": False,
            "createdAt": timestamp,
            "updatedAt": timestamp,
            "audit": [
                {
                    "revision": 1,
                    "action": "workspace.cloned",
                    "semantic": "",
                    "actor": _safe_actor(actor),
                    "timestamp": timestamp,
                    "sourceWorkspaceId": source["workspaceId"],
                    "sourceRevision": source["revision"],
                }
            ],
        }
    )
    cloned["workspaceHash"] = _workspace_hash(cloned)
    return cloned


def workspace_profile(workspace: dict[str, Any]) -> dict[str, Any]:
    """Build the validator input without granting publication evidence."""

    return {
        "schemaVersion": PROFILE_SCHEMA_VERSION,
        "profileId": workspace["profileId"],
        "displayName": workspace["displayName"],
        "version": workspace["version"],
        "reportType": workspace["reportType"],
        "status": workspace["status"],
        "templateSha256": workspace["templateSha256"],
        "slots": copy.deepcopy(workspace["slots"]),
        "validation": {
            "fixturePassed": False,
            "integrityPassed": False,
            "visualApproved": False,
        },
    }


def validate_mapping_workspace_document(workspace: dict[str, Any]) -> dict[str, Any]:
    """Validate one portable workspace document before it can enter local storage."""

    if not isinstance(workspace, dict):
        raise TemplateMappingWorkspaceError("Mapping workspace must be a JSON object.")
    expected_hash = workspace.get("workspaceHash")
    if not isinstance(expected_hash, str) or expected_hash != _workspace_hash(workspace):
        raise TemplateMappingWorkspaceError("Mapping workspace checksum is invalid.")
    _workspace_summary(workspace)
    analysis = workspace.get("analysis")
    if not isinstance(analysis, dict):
        raise TemplateMappingWorkspaceError("Mapping workspace analysis is invalid.")
    if analysis.get("schemaVersion") != PROFILE_SCHEMA_VERSION:
        raise TemplateMappingWorkspaceError("Mapping workspace analysis schema is invalid.")
    if analysis.get("reportType") != workspace.get("reportType"):
        raise TemplateMappingWorkspaceError("Mapping workspace analysis report type changed.")
    if analysis.get("templateSha256") != workspace.get("templateSha256"):
        raise TemplateMappingWorkspaceError("Mapping workspace template checksum changed.")
    validation = validate_template_profile(workspace_profile(workspace))
    if validation.errors:
        raise TemplateMappingWorkspaceError(validation.errors[0].message)
    if workspace.get("coveragePercent") != validation.coverage_percent:
        raise TemplateMappingWorkspaceError("Mapping workspace coverage is inconsistent.")
    if workspace.get("missingSemantics") != list(validation.missing_semantics):
        raise TemplateMappingWorkspaceError("Mapping workspace missing semantics are inconsistent.")
    expected_status = "mapping_complete" if validation.mapping_complete else None
    if expected_status and workspace.get("status") != expected_status:
        raise TemplateMappingWorkspaceError("Mapping workspace status is inconsistent.")
    if not expected_status and workspace.get("status") not in {"analyzed", "mapping_incomplete"}:
        raise TemplateMappingWorkspaceError("Mapping workspace status is inconsistent.")
    return copy.deepcopy(workspace)


class TemplateMappingWorkspaceStore:
    """Small local store with atomic writes and no production DB dependency."""

    def __init__(self, root: Path):
        self.root = root.resolve()

    def save(self, workspace: dict[str, Any]) -> Path:
        workspace_id = _workspace_id(workspace)
        self.root.mkdir(parents=True, exist_ok=True)
        target = self.root / f"{workspace_id}.json"
        payload = json.dumps(workspace, ensure_ascii=False, sort_keys=True, indent=2).encode(
            "utf-8"
        )
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{workspace_id}-",
            suffix=".tmp",
            dir=self.root,
        )
        temporary = Path(temporary_name)
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)
        return target

    def load(self, workspace_id: str) -> dict[str, Any]:
        if not _WORKSPACE_ID.fullmatch(workspace_id):
            raise TemplateMappingWorkspaceError("Invalid workspace identifier.")
        path = self.root / f"{workspace_id}.json"
        try:
            value = json.loads(path.read_text(encoding="utf-8"))
        except FileNotFoundError as exc:
            raise TemplateMappingWorkspaceError("Mapping workspace was not found.") from exc
        except json.JSONDecodeError as exc:
            raise TemplateMappingWorkspaceError("Mapping workspace is corrupt.") from exc
        if not isinstance(value, dict) or value.get("workspaceId") != workspace_id:
            raise TemplateMappingWorkspaceError("Mapping workspace identity is invalid.")
        expected_hash = value.get("workspaceHash")
        if expected_hash != _workspace_hash(value):
            raise TemplateMappingWorkspaceError("Mapping workspace checksum is invalid.")
        return value

    def list_summaries(self) -> tuple[list[dict[str, Any]], int, str]:
        """Return safe metadata summaries while isolating corrupt workspace files."""

        if not self.root.exists():
            return [], 0, hashlib.sha256(b"").hexdigest()
        summaries: list[dict[str, Any]] = []
        skipped_corrupt = 0
        fingerprint_parts: list[str] = []
        try:
            candidates = sorted(self.root.glob("*.json"), key=lambda item: item.name)
        except OSError as exc:
            raise TemplateMappingWorkspaceError("Mapping workspace index is unavailable.") from exc
        for path in candidates:
            workspace_id = path.stem
            if not _WORKSPACE_ID.fullmatch(workspace_id) or path.is_symlink() or not path.is_file():
                skipped_corrupt += 1
                fingerprint_parts.append(_workspace_file_fingerprint(path, "unsupported"))
                continue
            try:
                workspace = self.load(workspace_id)
                summaries.append(_workspace_summary(workspace))
                fingerprint_parts.append(f"{workspace_id}:{workspace['workspaceHash']}")
            except (ValueError, TypeError, OSError, RecursionError, OverflowError):
                skipped_corrupt += 1
                fingerprint_parts.append(_workspace_file_fingerprint(path, "corrupt"))

        # Stable two-pass sorting gives updatedAt DESC, then workspaceId ASC.
        summaries.sort(key=lambda item: item["workspaceId"])
        summaries.sort(key=lambda item: item["updatedAt"], reverse=True)
        collection_fingerprint = hashlib.sha256(
            "\n".join(sorted(fingerprint_parts)).encode("utf-8")
        ).hexdigest()
        return summaries, skipped_corrupt, collection_fingerprint


class TemplateStudioService:
    """Coordinate immutable DOCX sources and revisioned mapping workspaces."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.workspaces = TemplateMappingWorkspaceStore(self.root / "workspaces")
        self.sources = self.root / "sources"
        self._guard = threading.Lock()
        self._locks: dict[str, threading.RLock] = {}

    def create(
        self,
        template_bytes: bytes,
        *,
        report_type: str,
        profile_id: str,
        display_name: str,
        version: str = "0.1.0",
        actor: str = "local-user",
    ) -> dict[str, Any]:
        analysis = analyze_profile_template(template_bytes, report_type)
        workspace = create_mapping_workspace(
            analysis,
            profile_id=profile_id,
            display_name=display_name,
            version=version,
            actor=actor,
        )
        self._save_source(template_bytes, workspace["templateSha256"])
        self.workspaces.save(workspace)
        return workspace

    def get(self, workspace_id: str) -> dict[str, Any]:
        return self.workspaces.load(workspace_id)

    def list_workspaces(
        self,
        *,
        status: str | None = None,
        report_type: str | None = None,
        archived: bool | None = None,
        q: str | None = None,
        cursor: str | None = None,
        limit: int = WORKSPACE_LIST_DEFAULT_LIMIT,
    ) -> dict[str, Any]:
        """List metadata-only workspace summaries with stable cursor pagination."""

        normalized_status = _workspace_status_filter(status)
        normalized_report_type = _workspace_report_type_filter(report_type)
        normalized_archived = _workspace_archived_filter(archived)
        normalized_query = _workspace_query(q)
        normalized_limit = _workspace_list_limit(limit)
        summaries, skipped_corrupt, collection_fingerprint = self.workspaces.list_summaries()
        cursor_key = _decode_workspace_cursor(
            cursor,
            status=normalized_status,
            report_type=normalized_report_type,
            archived=normalized_archived,
            query=normalized_query,
            collection_fingerprint=collection_fingerprint,
        )
        filtered = [
            item
            for item in summaries
            if (normalized_status is None or item["status"] == normalized_status)
            and (normalized_report_type is None or item["reportType"] == normalized_report_type)
            and (normalized_archived is None or item["archived"] is normalized_archived)
            and (
                normalized_query is None
                or normalized_query in item["displayName"].casefold()
                or normalized_query in item["profileId"].casefold()
            )
            and (cursor_key is None or _is_after_workspace_cursor(item, cursor_key))
        ]
        page = filtered[:normalized_limit]
        has_more = len(filtered) > normalized_limit
        next_cursor = (
            _encode_workspace_cursor(
                page[-1],
                status=normalized_status,
                report_type=normalized_report_type,
                archived=normalized_archived,
                query=normalized_query,
                collection_fingerprint=collection_fingerprint,
            )
            if has_more and page
            else None
        )
        return {
            "items": page,
            "nextCursor": next_cursor,
            "hasMore": has_more,
            "skippedCorrupt": skipped_corrupt,
            "collectionFingerprint": collection_fingerprint,
        }

    def approve(
        self,
        workspace_id: str,
        *,
        semantic: str,
        anchor: dict[str, str],
        fields: list[dict[str, str]],
        expected_revision: int,
        actor: str = "local-user",
    ) -> dict[str, Any]:
        with self._lock_for(workspace_id):
            workspace = self.workspaces.load(workspace_id)
            updated = approve_semantic_mapping(
                workspace,
                semantic=semantic,
                anchor=anchor,
                fields=fields,
                expected_revision=expected_revision,
                actor=actor,
            )
            self.workspaces.save(updated)
            return updated

    def remove(
        self,
        workspace_id: str,
        *,
        semantic: str,
        expected_revision: int,
        actor: str = "local-user",
    ) -> dict[str, Any]:
        with self._lock_for(workspace_id):
            workspace = self.workspaces.load(workspace_id)
            updated = remove_semantic_mapping(
                workspace,
                semantic=semantic,
                expected_revision=expected_revision,
                actor=actor,
            )
            self.workspaces.save(updated)
            return updated

    def rename(
        self,
        workspace_id: str,
        *,
        display_name: str,
        expected_revision: int,
        actor: str = "local-user",
    ) -> dict[str, Any]:
        with self._lock_for(workspace_id):
            workspace = self.workspaces.load(workspace_id)
            updated = rename_mapping_workspace(
                workspace,
                display_name=display_name,
                expected_revision=expected_revision,
                actor=actor,
            )
            self.workspaces.save(updated)
            return updated

    def clone(
        self,
        workspace_id: str,
        *,
        profile_id: str,
        display_name: str,
        version: str,
        expected_revision: int,
        actor: str = "local-user",
    ) -> dict[str, Any]:
        with self._lock_for(workspace_id):
            workspace = self.workspaces.load(workspace_id)
            # Verify the content-addressed source before another workspace refers to it.
            self.source_bytes(workspace_id)
            cloned = clone_mapping_workspace(
                workspace,
                profile_id=profile_id,
                display_name=display_name,
                version=version,
                expected_revision=expected_revision,
                actor=actor,
            )
            self.workspaces.save(cloned)
            return cloned

    def set_archived(
        self,
        workspace_id: str,
        *,
        archived: bool,
        expected_revision: int,
        actor: str = "local-user",
    ) -> dict[str, Any]:
        with self._lock_for(workspace_id):
            workspace = self.workspaces.load(workspace_id)
            updated = set_mapping_workspace_archived(
                workspace,
                archived=archived,
                expected_revision=expected_revision,
                actor=actor,
            )
            self.workspaces.save(updated)
            return updated

    def import_draft(
        self,
        workspace: dict[str, Any],
        template_bytes: bytes,
    ) -> dict[str, Any]:
        """Persist a validated portable draft under its newly assigned identity."""

        validated = validate_mapping_workspace_document(workspace)
        workspace_id = validated["workspaceId"]
        with self._lock_for(workspace_id):
            try:
                self.workspaces.load(workspace_id)
            except TemplateMappingWorkspaceError as exc:
                if "not found" not in str(exc).lower():
                    raise
            else:
                raise TemplateMappingWorkspaceError("Imported workspace identifier already exists.")
            self._save_source(template_bytes, validated["templateSha256"])
            self.workspaces.save(validated)
            return validated

    def source_bytes(self, workspace_id: str) -> bytes:
        workspace = self.workspaces.load(workspace_id)
        path = self.sources / f"{workspace['templateSha256']}.docx"
        try:
            data = path.read_bytes()
        except FileNotFoundError as exc:
            raise TemplateMappingWorkspaceError("Template Studio source is missing.") from exc
        if hashlib.sha256(data).hexdigest() != workspace["templateSha256"]:
            raise TemplateMappingWorkspaceError("Template Studio source checksum is invalid.")
        return data

    def _save_source(self, data: bytes, expected_sha256: str) -> Path:
        if hashlib.sha256(data).hexdigest() != expected_sha256:
            raise TemplateMappingWorkspaceError("Template source checksum changed during analysis.")
        self.sources.mkdir(parents=True, exist_ok=True)
        target = self.sources / f"{expected_sha256}.docx"
        if target.exists():
            existing = target.read_bytes()
            if existing != data:
                raise TemplateMappingWorkspaceError("Template source hash collision detected.")
            return target
        _atomic_write(target, data)
        return target

    def _lock_for(self, workspace_id: str) -> threading.RLock:
        with self._guard:
            return self._locks.setdefault(workspace_id, threading.RLock())


def _checked_lifecycle_copy(workspace: dict[str, Any], expected_revision: int) -> dict[str, Any]:
    if workspace.get("workspaceSchemaVersion") != WORKSPACE_SCHEMA_VERSION:
        raise TemplateMappingWorkspaceError("Unsupported mapping workspace schema.")
    if workspace.get("revision") != expected_revision:
        raise TemplateMappingRevisionConflict(
            f"Workspace revision changed; expected {expected_revision}, "
            f"current {workspace.get('revision')}."
        )
    if workspace.get("status") in {"test_passed", "published"}:
        raise TemplateMappingWorkspaceError("Published or tested mappings are immutable.")
    return copy.deepcopy(workspace)


def _checked_copy(workspace: dict[str, Any], expected_revision: int) -> dict[str, Any]:
    draft = _checked_lifecycle_copy(workspace, expected_revision)
    if draft.get("archived", False):
        raise TemplateMappingWorkspaceError("Archived mappings are read-only until restored.")
    return draft


def _validate_discovered_anchor(analysis: dict[str, Any], anchor: dict[str, str]) -> dict[str, str]:
    if not isinstance(anchor, dict):
        raise TemplateMappingWorkspaceError("Anchor must be an object.")
    kind = anchor.get("kind", "")
    value = anchor.get("value", "")
    if kind not in ANCHOR_KINDS or not isinstance(value, str) or not value.strip():
        raise TemplateMappingWorkspaceError("Anchor kind or value is invalid.")
    value = value.strip()
    facts = analysis.get("facts", {})
    occurrences = 0
    if kind == "content_control":
        occurrences = sum(
            int(item.get("occurrences", 1))
            for item in facts.get("contentControls", [])
            if item.get("value") == value
        )
    elif kind == "bookmark":
        occurrences = sum(
            int(item.get("occurrences", 1))
            for item in facts.get("bookmarks", [])
            if item.get("value") == value
        )
    else:
        occurrences = int(facts.get("tokenOccurrences", {}).get(value, 0))
    if occurrences == 0:
        raise TemplateMappingWorkspaceError("Anchor was not found in the analyzed template.")
    if occurrences != 1:
        raise TemplateMappingWorkspaceError("Anchor is ambiguous and must occur exactly once.")
    return {"kind": kind, "value": value}


def _validate_field_mapping(
    required_fields: tuple[str, ...], fields: list[dict[str, str]]
) -> list[dict[str, str]]:
    if not required_fields:
        if fields:
            raise TemplateMappingWorkspaceError("This semantic does not accept table fields.")
        return []
    if not isinstance(fields, list):
        raise TemplateMappingWorkspaceError("Field mappings must be an array.")
    sources: set[str] = set()
    targets: set[str] = set()
    normalized: list[dict[str, str]] = []
    for field in fields:
        if not isinstance(field, dict):
            raise TemplateMappingWorkspaceError("Each field mapping must be an object.")
        source = field.get("source", "")
        target = field.get("target", "")
        if source not in required_fields:
            raise TemplateMappingWorkspaceError(f"Unsupported field source: {source!r}.")
        if not isinstance(target, str) or not _COLUMN_TARGET.fullmatch(target):
            raise TemplateMappingWorkspaceError("Field targets must use column:<number>.")
        if source in sources or target in targets:
            raise TemplateMappingWorkspaceError("Field sources and targets must be unique.")
        sources.add(source)
        targets.add(target)
        normalized.append({"source": source, "target": target})
    missing = set(required_fields) - sources
    if missing:
        raise TemplateMappingWorkspaceError(
            f"Missing required field mappings: {', '.join(sorted(missing))}."
        )
    return normalized


def _advance(
    workspace: dict[str, Any],
    action: str,
    semantic: str,
    actor: str,
    now: datetime | None,
) -> dict[str, Any]:
    workspace["revision"] += 1
    result = validate_template_profile(workspace_profile(workspace))
    workspace["coveragePercent"] = result.coverage_percent
    workspace["missingSemantics"] = list(result.missing_semantics)
    workspace["status"] = "mapping_complete" if result.mapping_complete else "mapping_incomplete"
    timestamp = _timestamp(now)
    workspace["updatedAt"] = timestamp
    workspace["audit"] = [
        *workspace.get("audit", []),
        {
            "revision": workspace["revision"],
            "action": action,
            "semantic": semantic,
            "actor": _safe_actor(actor),
            "timestamp": timestamp,
        },
    ][-MAX_AUDIT_EVENTS:]
    workspace["workspaceHash"] = _workspace_hash(workspace)
    return workspace


def _workspace_hash(workspace: dict[str, Any]) -> str:
    value = {key: item for key, item in workspace.items() if key != "workspaceHash"}
    payload = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _atomic_write(target: Path, payload: bytes) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    descriptor, temporary_name = tempfile.mkstemp(
        prefix=f".{target.stem}-",
        suffix=".tmp",
        dir=target.parent,
    )
    temporary = Path(temporary_name)
    try:
        with os.fdopen(descriptor, "wb") as handle:
            handle.write(payload)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, target)
    finally:
        temporary.unlink(missing_ok=True)


def _workspace_id(workspace: dict[str, Any]) -> str:
    workspace_id = workspace.get("workspaceId")
    if not isinstance(workspace_id, str) or not _WORKSPACE_ID.fullmatch(workspace_id):
        raise TemplateMappingWorkspaceError("Invalid workspace identifier.")
    return workspace_id


def _workspace_summary(workspace: dict[str, Any]) -> dict[str, Any]:
    """Validate and project one persisted workspace without returning authoring payloads."""

    if workspace.get("workspaceSchemaVersion") != WORKSPACE_SCHEMA_VERSION:
        raise TemplateMappingWorkspaceError("Unsupported mapping workspace schema.")
    workspace_id = _workspace_id(workspace)
    profile_id = workspace.get("profileId")
    display_name = workspace.get("displayName")
    version = workspace.get("version")
    report_type = workspace.get("reportType")
    status = workspace.get("status")
    archived = workspace.get("archived", False)
    revision = workspace.get("revision")
    slots = workspace.get("slots")
    if not isinstance(profile_id, str) or not _IDENTIFIER.fullmatch(profile_id):
        raise TemplateMappingWorkspaceError("Mapping workspace profile identifier is invalid.")
    if not isinstance(display_name, str):
        raise TemplateMappingWorkspaceError("Mapping workspace display name is invalid.")
    normalized_display_name = _normalized_workspace_text(display_name, max_length=200)
    if not normalized_display_name:
        raise TemplateMappingWorkspaceError("Mapping workspace display name is invalid.")
    if not isinstance(version, str) or not version.strip():
        raise TemplateMappingWorkspaceError("Mapping workspace version is invalid.")
    if report_type not in REPORT_REQUIREMENTS:
        raise TemplateMappingWorkspaceError("Mapping workspace report type is invalid.")
    if status not in WORKSPACE_STATUSES:
        raise TemplateMappingWorkspaceError("Mapping workspace status is invalid.")
    if not isinstance(archived, bool):
        raise TemplateMappingWorkspaceError("Mapping workspace archived state is invalid.")
    if isinstance(revision, bool) or not isinstance(revision, int) or revision < 1:
        raise TemplateMappingWorkspaceError("Mapping workspace revision is invalid.")
    if not isinstance(slots, list):
        raise TemplateMappingWorkspaceError("Mapping workspace slots are invalid.")
    required_semantics = REPORT_REQUIREMENTS[report_type]
    mapped_semantics: set[str] = set()
    for slot in slots:
        semantic = slot.get("semantic") if isinstance(slot, dict) else None
        if semantic not in required_semantics or semantic in mapped_semantics:
            raise TemplateMappingWorkspaceError("Mapping workspace slots are invalid.")
        mapped_semantics.add(semantic)
    mapped_count = len(mapped_semantics)
    required_count = len(required_semantics)
    missing_count = required_count - mapped_count
    coverage = round((mapped_count / required_count) * 100.0, 2) if required_count else 100.0
    return {
        "workspaceId": workspace_id,
        "profileId": profile_id,
        "displayName": normalized_display_name,
        "version": version.strip(),
        "reportType": report_type,
        "status": status,
        "archived": archived,
        "revision": revision,
        "coveragePercent": coverage,
        "mappedCount": mapped_count,
        "requiredCount": required_count,
        "missingCount": missing_count,
        "createdAt": _canonical_timestamp(workspace.get("createdAt"), "created"),
        "updatedAt": _canonical_timestamp(workspace.get("updatedAt"), "updated"),
    }


def _workspace_status_filter(status: str | None) -> str | None:
    if status is None:
        return None
    if not isinstance(status, str) or status not in WORKSPACE_STATUSES:
        raise TemplateMappingWorkspaceError("Unsupported mapping workspace status filter.")
    return status


def _workspace_report_type_filter(report_type: str | None) -> str | None:
    if report_type is None:
        return None
    if not isinstance(report_type, str) or report_type not in REPORT_REQUIREMENTS:
        raise TemplateMappingWorkspaceError("Unsupported workspace report type filter.")
    return report_type


def _workspace_archived_filter(archived: bool | None) -> bool | None:
    if archived is None:
        return None
    if not isinstance(archived, bool):
        raise TemplateMappingWorkspaceError("Workspace archived filter must be boolean.")
    return archived


def _workspace_query(q: str | None) -> str | None:
    if q is None:
        return None
    if not isinstance(q, str):
        raise TemplateMappingWorkspaceError("Workspace search query must be text.")
    normalized = _normalized_workspace_text(q, max_length=WORKSPACE_QUERY_MAX_LENGTH)
    if not normalized:
        return None
    return normalized.casefold()


def _normalized_workspace_text(value: str, *, max_length: int) -> str:
    normalized = unicodedata.normalize("NFKC", value.strip())
    if len(normalized) > max_length:
        raise TemplateMappingWorkspaceError(
            f"Workspace text cannot exceed {max_length} characters."
        )
    if any(unicodedata.category(character) in {"Cc", "Cf", "Cs"} for character in normalized):
        raise TemplateMappingWorkspaceError("Workspace text contains unsupported characters.")
    return normalized


def _workspace_list_limit(limit: int) -> int:
    if isinstance(limit, bool) or not isinstance(limit, int):
        raise TemplateMappingWorkspaceError("Workspace list limit must be an integer.")
    if not 1 <= limit <= WORKSPACE_LIST_MAX_LIMIT:
        raise TemplateMappingWorkspaceError(
            f"Workspace list limit must be between 1 and {WORKSPACE_LIST_MAX_LIMIT}."
        )
    return limit


def _encode_workspace_cursor(
    summary: dict[str, Any],
    *,
    status: str | None,
    report_type: str | None,
    archived: bool | None,
    query: str | None,
    collection_fingerprint: str,
) -> str:
    payload = {
        "v": _CURSOR_VERSION,
        "updatedAt": summary["updatedAt"],
        "workspaceId": summary["workspaceId"],
        "status": status,
        "reportType": report_type,
        "archived": archived,
        "q": query,
        "collectionFingerprint": collection_fingerprint,
    }
    encoded = json.dumps(payload, sort_keys=True, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(encoded).decode("ascii").rstrip("=")


def _decode_workspace_cursor(
    cursor: str | None,
    *,
    status: str | None,
    report_type: str | None,
    archived: bool | None,
    query: str | None,
    collection_fingerprint: str,
) -> tuple[str, str] | None:
    if cursor is None:
        return None
    if not isinstance(cursor, str) or not cursor or len(cursor) > WORKSPACE_CURSOR_MAX_LENGTH:
        raise TemplateMappingWorkspaceError("Invalid workspace list cursor.")
    padding = "=" * (-len(cursor) % 4)
    try:
        decoded = base64.b64decode(
            cursor + padding,
            altchars=b"-_",
            validate=True,
        )
        value = json.loads(decoded.decode("utf-8"))
    except (binascii.Error, UnicodeError, json.JSONDecodeError) as exc:
        raise TemplateMappingWorkspaceError("Invalid workspace list cursor.") from exc
    expected_keys = {
        "v",
        "updatedAt",
        "workspaceId",
        "status",
        "reportType",
        "archived",
        "q",
        "collectionFingerprint",
    }
    if (
        not isinstance(value, dict)
        or set(value) != expected_keys
        or value.get("v") != _CURSOR_VERSION
    ):
        raise TemplateMappingWorkspaceError("Invalid workspace list cursor.")
    workspace_id = value.get("workspaceId")
    updated_at = value.get("updatedAt")
    if not isinstance(workspace_id, str) or not _WORKSPACE_ID.fullmatch(workspace_id):
        raise TemplateMappingWorkspaceError("Invalid workspace list cursor.")
    canonical_updated_at = _canonical_timestamp(updated_at, "cursor")
    if (
        value.get("status") != status
        or value.get("reportType") != report_type
        or value.get("archived") is not archived
        or value.get("q") != query
    ):
        raise TemplateMappingWorkspaceError("Workspace list cursor does not match the filters.")
    if value.get("collectionFingerprint") != collection_fingerprint:
        raise TemplateMappingWorkspaceIndexChanged(
            "Workspace collection changed; restart pagination from the first page."
        )
    return canonical_updated_at, workspace_id


def _is_after_workspace_cursor(summary: dict[str, Any], cursor_key: tuple[str, str]) -> bool:
    updated_at, workspace_id = cursor_key
    return summary["updatedAt"] < updated_at or (
        summary["updatedAt"] == updated_at and summary["workspaceId"] > workspace_id
    )


def _canonical_timestamp(value: Any, label: str) -> str:
    if not isinstance(value, str) or not value:
        raise TemplateMappingWorkspaceError(f"Mapping workspace {label} timestamp is invalid.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TemplateMappingWorkspaceError(
            f"Mapping workspace {label} timestamp is invalid."
        ) from exc
    if parsed.tzinfo is None:
        raise TemplateMappingWorkspaceError(f"Mapping workspace {label} timestamp is invalid.")
    return parsed.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _workspace_file_fingerprint(path: Path, state: str) -> str:
    try:
        stat = path.stat()
        metadata = f"{stat.st_size}:{stat.st_mtime_ns}"
    except OSError:
        metadata = "unreadable"
    return f"{path.name}:{state}:{metadata}"


def _safe_actor(actor: str) -> str:
    value = actor.strip() if isinstance(actor, str) else ""
    return value[:80] or "local-user"


def _timestamp(now: datetime | None) -> str:
    value = now or datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
