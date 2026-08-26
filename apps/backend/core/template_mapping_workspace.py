"""Draft mapping workspace for the experimental Template Studio.

The workspace is a pure, revisioned domain model.  It is not imported by the
Legacy Renderer and it cannot publish or render a Template Pack.  Persistence is
opt-in through ``TemplateMappingWorkspaceStore`` and uses atomic JSON writes.
"""

from __future__ import annotations

import copy
import hashlib
import json
import os
import re
import tempfile
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .template_profile_analyzer import analyze_profile_template
from .template_profiles import (
    ANCHOR_KINDS,
    COMMON_REQUIREMENTS,
    PROFILE_SCHEMA_VERSION,
    REPORT_REQUIREMENTS,
    validate_template_profile,
)

WORKSPACE_SCHEMA_VERSION = "1.0"
MAX_AUDIT_EVENTS = 500
_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._-]{1,127}$")
_COLUMN_TARGET = re.compile(r"^column:[1-9][0-9]{0,2}$")


class TemplateMappingWorkspaceError(ValueError):
    """Raised when a draft mapping command violates the workspace contract."""


class TemplateMappingRevisionConflict(TemplateMappingWorkspaceError):
    """Raised when a command was based on an outdated workspace revision."""


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
    if not isinstance(template_sha256, str) or not re.fullmatch(r"[0-9a-f]{64}", template_sha256):
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
        if not re.fullmatch(r"[0-9a-f]{32}", workspace_id):
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


def _checked_copy(workspace: dict[str, Any], expected_revision: int) -> dict[str, Any]:
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
    if not isinstance(workspace_id, str) or not re.fullmatch(r"[0-9a-f]{32}", workspace_id):
        raise TemplateMappingWorkspaceError("Invalid workspace identifier.")
    return workspace_id


def _safe_actor(actor: str) -> str:
    value = actor.strip() if isinstance(actor, str) else ""
    return value[:80] or "local-user"


def _timestamp(now: datetime | None) -> str:
    value = now or datetime.now(timezone.utc)
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
