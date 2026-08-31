"""Build and version experimental Template Packs without touching legacy templates.

The catalog is intentionally filesystem-backed and isolated from the production
template database.  Activating a version here only selects the candidate inside
Template Studio; it does not expose the pack to the Legacy Renderer.
"""

from __future__ import annotations

import copy
import hashlib
import io
import json
import os
import re
import tempfile
import threading
import time
import zipfile
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .template_mapping_workspace import workspace_profile
from .template_pack import (
    PACK_FORMAT_VERSION,
    TemplatePackError,
    TemplatePackInspection,
    inspect_template_pack,
)
from .template_profiles import validate_template_profile

CATALOG_SCHEMA_VERSION = "1.0"
CATALOG_CHECKSUM_FIELD = "catalogSha256"
MAX_CATALOG_AUDIT_EVENTS = 1000
CATALOG_LOCK_TIMEOUT_SECONDS = 10.0
_IDENTIFIER = re.compile(r"^[a-z0-9][a-z0-9._-]{1,127}$")
_VERSION = re.compile(r"^[0-9]+\.[0-9]+\.[0-9]+(?:-[0-9A-Za-z][0-9A-Za-z.-]{0,63})?$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")


class TemplatePackCatalogError(ValueError):
    """Raised when a build or catalog mutation violates the safety contract."""


class TemplatePackCatalogRevisionConflict(TemplatePackCatalogError):
    """Raised when a catalog command was based on an outdated revision."""


@dataclass(frozen=True)
class TemplatePackValidationEvidence:
    """Trusted results produced by the backend Template Pack validation runner.

    The public API deliberately does not accept this object yet.  Fixture and
    integrity results come from the Profile Renderer runner; visual approval
    remains an explicit human gate bound to the exact artifact checksum.
    """

    fixture_id: str
    fixture_passed: bool
    integrity_passed: bool
    visual_approved: bool
    validator_version: str
    validated_at: str = ""
    validation_run_id: str = ""
    artifact_sha256: str = ""
    structural_sha256: str = ""
    reviewed_by: str = ""
    reviewed_at: str = ""

    def public(self) -> dict[str, Any]:
        fixture_id = self.fixture_id.strip()
        validator_version = self.validator_version.strip()
        if not fixture_id or len(fixture_id) > 128:
            raise TemplatePackCatalogError("Validation evidence requires a fixture id.")
        if not validator_version or len(validator_version) > 64:
            raise TemplatePackCatalogError("Validation evidence requires a validator version.")
        if not all((self.fixture_passed, self.integrity_passed, self.visual_approved)):
            raise TemplatePackCatalogError(
                "Fixture, integrity and visual validation must pass before pack build."
            )
        validated_at = self.validated_at.strip() or _timestamp()
        result = {
            "fixturePassed": True,
            "integrityPassed": True,
            "visualApproved": True,
            "fixtureId": fixture_id,
            "validatedAt": validated_at,
            "validatorVersion": validator_version,
        }
        extended = {
            "validationRunId": self.validation_run_id.strip(),
            "artifactSha256": self.artifact_sha256.strip().lower(),
            "structuralSha256": self.structural_sha256.strip().lower(),
            "reviewedBy": self.reviewed_by.strip(),
            "reviewedAt": self.reviewed_at.strip(),
        }
        if not all(extended.values()):
            raise TemplatePackCatalogError(
                "Runner-issued evidence requires complete artifact and reviewer provenance."
            )
        if not all(
            _SHA256.fullmatch(extended[field])
            for field in ("validationRunId", "artifactSha256", "structuralSha256")
        ):
            raise TemplatePackCatalogError("Validation run and artifact checksums must be SHA-256.")
        result.update(extended)
        return result


def build_template_pack(
    workspace: dict[str, Any],
    template_bytes: bytes,
    evidence: TemplatePackValidationEvidence,
) -> bytes:
    """Build a deterministic, publication-gated ``.rptpack`` archive."""

    profile = _pack_profile(workspace, template_bytes)
    profile["status"] = "published"
    profile["validation"] = evidence.public()
    validation = validate_template_profile(profile)
    if not validation.publishable:
        detail = next(
            (item.message for item in (*validation.errors, *validation.warnings)),
            "Profile failed the publication gate.",
        )
        raise TemplatePackCatalogError(detail)

    return _build_pack_archive(profile, template_bytes, require_publishable=True)


def build_template_pack_candidate(workspace: dict[str, Any], template_bytes: bytes) -> bytes:
    """Build a deterministic, non-publishable pack used only by the validation runner."""

    profile = _pack_profile(workspace, template_bytes)
    profile["status"] = "mapping_complete"
    profile["validation"] = {
        "fixturePassed": False,
        "integrityPassed": False,
        "visualApproved": False,
    }
    validation = validate_template_profile(profile)
    if not validation.structural_valid or not validation.mapping_complete:
        detail = next(
            (item.message for item in (*validation.errors, *validation.warnings)),
            "Candidate profile failed the mapping gate.",
        )
        raise TemplatePackCatalogError(detail)
    return _build_pack_archive(profile, template_bytes, require_publishable=False)


def _pack_profile(workspace: dict[str, Any], template_bytes: bytes) -> dict[str, Any]:
    if workspace.get("status") != "mapping_complete":
        raise TemplatePackCatalogError("Workspace must have 100% mapping before pack build.")
    expected_template_hash = workspace.get("templateSha256")
    actual_template_hash = hashlib.sha256(template_bytes).hexdigest()
    if expected_template_hash != actual_template_hash:
        raise TemplatePackCatalogError("Workspace and template checksums do not match.")
    return workspace_profile(workspace)


def _build_pack_archive(
    profile: dict[str, Any],
    template_bytes: bytes,
    *,
    require_publishable: bool,
) -> bytes:
    layout = {
        key: profile[key]
        for key in (
            "schemaVersion",
            "profileId",
            "displayName",
            "version",
            "reportType",
            "status",
        )
    }
    layout["slots"] = [
        {key: slot[key] for key in ("id", "semantic", "renderer", "anchor", "repeat")}
        for slot in profile["slots"]
    ]
    mapping = {
        "profileId": profile["profileId"],
        "slots": [
            {"id": slot["id"], "source": slot["source"], "fields": slot["fields"]}
            for slot in profile["slots"]
        ],
    }
    payloads = {
        "template.docx": template_bytes,
        "layout.json": _canonical_json(layout),
        "mapping.json": _canonical_json(mapping),
        "validation.json": _canonical_json(profile["validation"]),
    }
    manifest = {
        "formatVersion": PACK_FORMAT_VERSION,
        "packId": profile["profileId"],
        "version": profile["version"],
        "checksums": {
            name: hashlib.sha256(payload).hexdigest() for name, payload in payloads.items()
        },
    }

    output = io.BytesIO()
    with zipfile.ZipFile(output, "w", zipfile.ZIP_DEFLATED, compresslevel=6) as archive:
        _write_deterministic(archive, "manifest.json", _canonical_json(manifest))
        for name in ("template.docx", "layout.json", "mapping.json", "validation.json"):
            _write_deterministic(archive, name, payloads[name])
    built = output.getvalue()
    try:
        inspection = inspect_template_pack(built, require_publishable=require_publishable)
    except TemplatePackError as exc:
        raise TemplatePackCatalogError(f"Built pack failed self-inspection: {exc}") from exc
    if not require_publishable and inspection.publishable:
        raise TemplatePackCatalogError("Validation candidate must not be publication-ready.")
    return built


class TemplatePackCatalog:
    """Immutable version catalog for validated Template Packs."""

    def __init__(self, root: Path):
        self.root = root.resolve()
        self.index_path = self.root / "catalog.json"
        self.checkpoint_path = self.root / "catalog.checkpoint.json"
        self.lock_path = self.root / "catalog.lock"
        self.pack_root = self.root / "packs"
        self._lock = threading.RLock()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            with _catalog_file_lock(self.lock_path):
                return self._public(self._load())

    def recovery_preview(self) -> dict[str, Any]:
        """Inspect primary/checkpoint integrity without changing catalog state."""

        with self._lock:
            with _catalog_file_lock(self.lock_path):
                return self._recovery_preview()

    def recover(self, confirmation_token: str) -> dict[str, Any]:
        """Restore the last valid checkpoint after an explicit preview token."""

        with self._lock:
            with _catalog_file_lock(self.lock_path):
                preview = self._recovery_preview()
                if not preview["canRecover"]:
                    raise TemplatePackCatalogError("No valid catalog checkpoint is available.")
                if not confirmation_token or confirmation_token != preview["confirmationToken"]:
                    raise TemplatePackCatalogError(
                        "Catalog recovery preview changed; preview again before restoring."
                    )
                try:
                    checkpoint_bytes = self.checkpoint_path.read_bytes()
                    checkpoint = self._decode_catalog(checkpoint_bytes)
                except OSError as exc:
                    raise TemplatePackCatalogError("Catalog checkpoint is unavailable.") from exc
                _atomic_write(self.index_path, checkpoint_bytes)
                restored = self._public(checkpoint)
                restored["recovery"] = {
                    "restored": True,
                    "restoredRevision": checkpoint["revision"],
                    "checkpointSha256": hashlib.sha256(checkpoint_bytes).hexdigest(),
                }
                return restored

    def install(
        self,
        pack_bytes: bytes,
        *,
        expected_revision: int,
        actor: str = "local-user",
    ) -> dict[str, Any]:
        """Install one immutable, already-publishable pack version atomically."""

        try:
            inspection = inspect_template_pack(pack_bytes, require_publishable=True)
        except TemplatePackError as exc:
            raise TemplatePackCatalogError(str(exc)) from exc
        _validate_identity(inspection.pack_id, inspection.version)
        pack_sha256 = hashlib.sha256(pack_bytes).hexdigest()

        with self._lock:
            with _catalog_file_lock(self.lock_path):
                return self._install_locked(
                    inspection,
                    pack_bytes,
                    pack_sha256=pack_sha256,
                    expected_revision=expected_revision,
                    actor=actor,
                )

    def _install_locked(
        self,
        inspection: TemplatePackInspection,
        pack_bytes: bytes,
        *,
        pack_sha256: str,
        expected_revision: int,
        actor: str,
    ) -> dict[str, Any]:
        catalog = self._checked_catalog(expected_revision)
        entry = catalog["packs"].setdefault(
            inspection.pack_id,
            {"activeVersion": "", "versions": {}},
        )
        existing = entry["versions"].get(inspection.version)
        if existing:
            if existing.get("packSha256") != pack_sha256:
                raise TemplatePackCatalogError(
                    "Pack versions are immutable; use a new semantic version."
                )
            return self._public(catalog)

        target = self._pack_path(inspection.pack_id, inspection.version)
        created_target = False
        if target.exists():
            existing_hash = hashlib.sha256(target.read_bytes()).hexdigest()
            if existing_hash != pack_sha256:
                raise TemplatePackCatalogError("Stored pack conflicts with catalog state.")
        else:
            _atomic_write(target, pack_bytes)
            created_target = True
        installed_at = _timestamp()
        entry["versions"][inspection.version] = {
            "packSha256": pack_sha256,
            "templateSha256": inspection.template_sha256,
            "reportType": inspection.profile["reportType"],
            "displayName": inspection.profile["displayName"],
            "installedAt": installed_at,
            "state": "installed",
        }
        self._advance(
            catalog,
            action="pack.installed",
            pack_id=inspection.pack_id,
            version=inspection.version,
            actor=actor,
        )
        try:
            self._save(catalog)
        except Exception:
            # The catalog index is the commit point.  Roll back only a payload
            # created by this call so a failed index write cannot leave an
            # apparently installable orphan version behind.
            if created_target:
                target.unlink(missing_ok=True)
            raise
        return self._public(catalog)

    def activate(
        self,
        pack_id: str,
        version: str,
        *,
        expected_revision: int,
        actor: str = "local-user",
    ) -> dict[str, Any]:
        """Select a Template Studio version without integrating the legacy flow."""

        return self._select(
            pack_id,
            version,
            expected_revision=expected_revision,
            actor=actor,
            action="pack.activated",
        )

    def rollback(
        self,
        pack_id: str,
        version: str,
        *,
        expected_revision: int,
        actor: str = "local-user",
    ) -> dict[str, Any]:
        """Move the Template Studio selection to an installed older version."""

        return self._select(
            pack_id,
            version,
            expected_revision=expected_revision,
            actor=actor,
            action="pack.rolled_back",
        )

    def pack_bytes(self, pack_id: str, version: str) -> bytes:
        _validate_identity(pack_id, version)
        with self._lock:
            with _catalog_file_lock(self.lock_path):
                return self._pack_bytes_locked(pack_id, version)

    def _pack_bytes_locked(self, pack_id: str, version: str) -> bytes:
        catalog = self._load()
        metadata = catalog.get("packs", {}).get(pack_id, {}).get("versions", {}).get(version)
        if not metadata:
            raise TemplatePackCatalogError("Template Pack version was not found.")
        path = self._pack_path(pack_id, version)
        try:
            payload = path.read_bytes()
        except FileNotFoundError as exc:
            raise TemplatePackCatalogError("Template Pack payload is missing.") from exc
        if hashlib.sha256(payload).hexdigest() != metadata.get("packSha256"):
            raise TemplatePackCatalogError("Template Pack payload checksum is invalid.")
        return payload

    def _select(
        self,
        pack_id: str,
        version: str,
        *,
        expected_revision: int,
        actor: str,
        action: str,
    ) -> dict[str, Any]:
        _validate_identity(pack_id, version)
        with self._lock:
            with _catalog_file_lock(self.lock_path):
                catalog = self._checked_catalog(expected_revision)
                entry = catalog["packs"].get(pack_id)
                if not entry or version not in entry.get("versions", {}):
                    raise TemplatePackCatalogError("Template Pack version was not found.")
                self._pack_bytes_locked(pack_id, version)
                previous = entry.get("activeVersion", "")
                if previous == version:
                    return self._public(catalog)
                entry["activeVersion"] = version
                self._advance(
                    catalog,
                    action=action,
                    pack_id=pack_id,
                    version=version,
                    actor=actor,
                    previous_version=previous,
                )
                self._save(catalog)
                return self._public(catalog)

    def _checked_catalog(self, expected_revision: int) -> dict[str, Any]:
        catalog = self._load()
        if catalog["revision"] != expected_revision:
            raise TemplatePackCatalogRevisionConflict(
                f"Catalog revision changed; expected {expected_revision}, "
                f"current {catalog['revision']}."
            )
        return catalog

    def _load(self) -> dict[str, Any]:
        if not self.index_path.exists():
            return _empty_catalog()
        try:
            return self._decode_catalog(self.index_path.read_bytes())
        except OSError as exc:
            raise TemplatePackCatalogError("Template Pack catalog is corrupt.") from exc

    def _decode_catalog(self, payload: bytes) -> dict[str, Any]:
        try:
            catalog = json.loads(payload.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise TemplatePackCatalogError("Template Pack catalog is corrupt.") from exc
        if (
            not isinstance(catalog, dict)
            or catalog.get("catalogSchemaVersion") != CATALOG_SCHEMA_VERSION
            or not isinstance(catalog.get("revision"), int)
            or not isinstance(catalog.get("packs"), dict)
            or not isinstance(catalog.get("audit"), list)
        ):
            raise TemplatePackCatalogError("Template Pack catalog schema is invalid.")
        checksum = catalog.get(CATALOG_CHECKSUM_FIELD)
        if checksum is not None:
            if not isinstance(checksum, str) or not _SHA256.fullmatch(checksum):
                raise TemplatePackCatalogError("Template Pack catalog checksum is invalid.")
            unsealed = {
                key: value for key, value in catalog.items() if key != CATALOG_CHECKSUM_FIELD
            }
            if checksum != hashlib.sha256(_canonical_json(unsealed)).hexdigest():
                raise TemplatePackCatalogError("Template Pack catalog checksum is invalid.")
        return catalog

    def _save(self, catalog: dict[str, Any]) -> None:
        sealed = _seal_catalog(catalog)
        if self.index_path.exists():
            try:
                current = self.index_path.read_bytes()
                self._decode_catalog(current)
            except (OSError, TemplatePackCatalogError):
                current = b""
            if current:
                _atomic_write(self.checkpoint_path, current)
        _atomic_write(self.index_path, _pretty_json(sealed))
        catalog[CATALOG_CHECKSUM_FIELD] = sealed[CATALOG_CHECKSUM_FIELD]

    def _recovery_preview(self) -> dict[str, Any]:
        primary = self._path_health(self.index_path)
        checkpoint = self._path_health(self.checkpoint_path)
        can_recover = not primary["valid"] and checkpoint["valid"]
        identity = {
            "schema": CATALOG_SCHEMA_VERSION,
            "primarySha256": primary["sha256"],
            "checkpointSha256": checkpoint["sha256"],
            "checkpointRevision": checkpoint["revision"],
        }
        return {
            "primary": primary,
            "checkpoint": checkpoint,
            "canRecover": can_recover,
            "confirmationToken": hashlib.sha256(_canonical_json(identity)).hexdigest()
            if can_recover
            else "",
            "legacyRendererUnchanged": True,
        }

    def _path_health(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            return {"exists": False, "valid": False, "revision": None, "sha256": ""}
        try:
            payload = path.read_bytes()
            catalog = self._decode_catalog(payload)
            payloads_valid = self._catalog_payloads_valid(catalog)
        except (OSError, TemplatePackCatalogError):
            try:
                checksum = hashlib.sha256(path.read_bytes()).hexdigest()
            except OSError:
                checksum = ""
            return {"exists": True, "valid": False, "revision": None, "sha256": checksum}
        return {
            "exists": True,
            "valid": payloads_valid,
            "revision": catalog["revision"],
            "sha256": hashlib.sha256(payload).hexdigest(),
            "sealed": CATALOG_CHECKSUM_FIELD in catalog,
            "payloadsValid": payloads_valid,
        }

    def _catalog_payloads_valid(self, catalog: dict[str, Any]) -> bool:
        for pack_id, pack in catalog.get("packs", {}).items():
            if not isinstance(pack, dict) or not isinstance(pack.get("versions"), dict):
                return False
            for version, metadata in pack["versions"].items():
                if not isinstance(metadata, dict):
                    return False
                try:
                    _validate_identity(pack_id, version)
                    data = self._pack_path(pack_id, version).read_bytes()
                except (OSError, TemplatePackCatalogError):
                    return False
                if hashlib.sha256(data).hexdigest() != metadata.get("packSha256"):
                    return False
        return True

    def _pack_path(self, pack_id: str, version: str) -> Path:
        return self.pack_root / pack_id / f"{version}.rptpack"

    @staticmethod
    def _advance(
        catalog: dict[str, Any],
        *,
        action: str,
        pack_id: str,
        version: str,
        actor: str,
        previous_version: str = "",
    ) -> None:
        catalog["revision"] += 1
        catalog["updatedAt"] = _timestamp()
        catalog["audit"] = [
            *catalog.get("audit", []),
            {
                "revision": catalog["revision"],
                "action": action,
                "packId": pack_id,
                "version": version,
                "previousVersion": previous_version,
                "actor": _safe_actor(actor),
                "timestamp": catalog["updatedAt"],
            },
        ][-MAX_CATALOG_AUDIT_EVENTS:]

    @staticmethod
    def _public(catalog: dict[str, Any]) -> dict[str, Any]:
        result = copy.deepcopy(catalog)
        result["integrity"] = "sealed" if CATALOG_CHECKSUM_FIELD in catalog else "legacy_unsealed"
        result["selectionIntegrated"] = False
        result["legacyRendererUnchanged"] = True
        return result


def _validate_identity(pack_id: str, version: str) -> None:
    if not _IDENTIFIER.fullmatch(pack_id):
        raise TemplatePackCatalogError("Invalid Template Pack identifier.")
    if not _VERSION.fullmatch(version):
        raise TemplatePackCatalogError("Template Pack version must use semantic versioning.")


def _empty_catalog() -> dict[str, Any]:
    return {
        "catalogSchemaVersion": CATALOG_SCHEMA_VERSION,
        "revision": 0,
        "updatedAt": "",
        "packs": {},
        "audit": [],
    }


def _seal_catalog(catalog: dict[str, Any]) -> dict[str, Any]:
    sealed = copy.deepcopy(catalog)
    sealed.pop(CATALOG_CHECKSUM_FIELD, None)
    sealed[CATALOG_CHECKSUM_FIELD] = hashlib.sha256(_canonical_json(sealed)).hexdigest()
    return sealed


def _canonical_json(value: dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()


def _pretty_json(value: dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")


def _write_deterministic(archive: zipfile.ZipFile, name: str, payload: bytes) -> None:
    info = zipfile.ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
    info.compress_type = zipfile.ZIP_DEFLATED
    info.external_attr = 0o600 << 16
    archive.writestr(info, payload)


@contextmanager
def _catalog_file_lock(
    lock_path: Path,
    *,
    timeout_seconds: float = CATALOG_LOCK_TIMEOUT_SECONDS,
):
    """Hold one exclusive byte-range lock across processes on the catalog root."""

    lock_path.parent.mkdir(parents=True, exist_ok=True)
    deadline = time.monotonic() + timeout_seconds
    with lock_path.open("a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"\0")
            handle.flush()
            os.fsync(handle.fileno())
        acquired = False
        try:
            while not acquired:
                handle.seek(0)
                try:
                    if os.name == "nt":
                        import msvcrt

                        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
                    else:
                        import fcntl

                        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                    acquired = True
                except OSError as exc:
                    if time.monotonic() >= deadline:
                        raise TemplatePackCatalogError(
                            "Template Pack catalog is busy; retry the operation."
                        ) from exc
                    time.sleep(0.05)
            yield
        finally:
            if acquired:
                handle.seek(0)
                if os.name == "nt":
                    import msvcrt

                    msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
                else:
                    import fcntl

                    fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


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


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _safe_actor(actor: str) -> str:
    value = actor.strip() if isinstance(actor, str) else ""
    return value[:80] or "local-user"
