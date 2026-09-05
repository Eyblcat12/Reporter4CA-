"""Preview-first, recoverable retention for isolated Template Studio drafts."""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import secrets
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

from .template_mapping_workspace import TemplateMappingWorkspaceError, TemplateStudioService

RETENTION_SCHEMA_VERSION = "1.0"
MIN_RETENTION_DAYS = 30
MAX_RETENTION_DAYS = 3650
CONFIRMATION_TTL_MINUTES = 15
_SHA256_DOCX = re.compile(r"^[0-9a-f]{64}\.docx$")
_QUARANTINE_ID = re.compile(r"^[0-9a-f]{16}$")


class TemplateWorkspaceRetentionError(ValueError):
    """Raised when cleanup cannot be proven safe or a plan became stale."""


class TemplateWorkspaceRetention:
    """Move eligible drafts to recoverable quarantine after an exact dry run."""

    def __init__(
        self,
        service: TemplateStudioService,
        *,
        secret: bytes | None = None,
        now: Callable[[], datetime] | None = None,
    ):
        self.service = service
        self.secret = secret or secrets.token_bytes(32)
        self._now = now or (lambda: datetime.now(timezone.utc))
        self.quarantine_root = self.service.root / "retention-quarantine"

    def preview(
        self,
        *,
        retention_days: int,
        protected_source_hashes: set[str] | None = None,
    ) -> dict[str, Any]:
        scan = self._scan(
            retention_days=retention_days,
            protected_source_hashes=protected_source_hashes or set(),
        )
        if scan["blockers"] or not (scan["workspaceIds"] or scan["sourceNames"]):
            token = None
        else:
            token = self._encode_token(
                {
                    "v": 1,
                    "quarantineId": secrets.token_hex(8),
                    "retentionDays": retention_days,
                    "fingerprint": scan["fingerprint"],
                    "workspaceIds": scan["workspaceIds"],
                    "sourceNames": scan["sourceNames"],
                    "expiresAt": _timestamp(
                        self._now() + timedelta(minutes=CONFIRMATION_TTL_MINUTES)
                    ),
                }
            )
        return {
            "dryRun": True,
            "retentionDays": retention_days,
            "cutoff": scan["cutoff"],
            "blocked": bool(scan["blockers"]),
            "blockers": scan["blockers"],
            "candidates": {
                "workspaces": scan["workspaceSummaries"],
                "sources": scan["sourceSummaries"],
            },
            "candidateWorkspaceCount": len(scan["workspaceIds"]),
            "candidateSourceCount": len(scan["sourceNames"]),
            "reclaimableBytes": scan["reclaimableBytes"],
            "fingerprint": scan["fingerprint"],
            "confirmationToken": token,
            "action": "quarantine",
            "permanentDelete": False,
        }

    def apply(
        self,
        confirmation_token: str,
        *,
        protected_source_hashes: set[str] | None = None,
    ) -> dict[str, Any]:
        payload = self._decode_token(confirmation_token)
        expires_at = _parse_timestamp(payload.get("expiresAt"), "confirmation expiry")
        if self._now().astimezone(timezone.utc) > expires_at:
            raise TemplateWorkspaceRetentionError("Retention confirmation expired; preview again.")
        scan = self._scan(
            retention_days=payload["retentionDays"],
            protected_source_hashes=protected_source_hashes or set(),
        )
        if scan["blockers"]:
            raise TemplateWorkspaceRetentionError("Retention is blocked; preview again.")
        if (
            scan["fingerprint"] != payload.get("fingerprint")
            or scan["workspaceIds"] != payload.get("workspaceIds")
            or scan["sourceNames"] != payload.get("sourceNames")
        ):
            raise TemplateWorkspaceRetentionError("Retention plan changed; preview again.")
        quarantine_id = payload["quarantineId"]
        target_root = self.quarantine_root / quarantine_id
        if target_root.exists():
            raise TemplateWorkspaceRetentionError("Retention confirmation was already applied.")
        moved: list[tuple[Path, Path]] = []
        manifest = {
            "schemaVersion": RETENTION_SCHEMA_VERSION,
            "quarantineId": quarantine_id,
            "createdAt": _timestamp(self._now()),
            "restoredAt": "",
            "workspaces": payload["workspaceIds"],
            "sources": payload["sourceNames"],
            "fingerprint": payload["fingerprint"],
        }
        try:
            for workspace_id in payload["workspaceIds"]:
                source = self.service.workspaces.root / f"{workspace_id}.json"
                destination = target_root / "workspaces" / source.name
                _move_owned(source, destination, self.service.workspaces.root, target_root)
                moved.append((source, destination))
            for source_name in payload["sourceNames"]:
                source = self.service.sources / source_name
                destination = target_root / "sources" / source.name
                _move_owned(source, destination, self.service.sources, target_root)
                moved.append((source, destination))
            _atomic_write(target_root / "manifest.json", _pretty_json(manifest))
        except (OSError, TemplateWorkspaceRetentionError) as exc:
            for original, quarantined in reversed(moved):
                if quarantined.exists() and not original.exists():
                    original.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(quarantined, original)
            raise TemplateWorkspaceRetentionError(
                "Retention quarantine failed and was rolled back."
            ) from exc
        return {
            "quarantineId": quarantine_id,
            "workspaceCount": len(payload["workspaceIds"]),
            "sourceCount": len(payload["sourceNames"]),
            "recoverable": True,
            "permanentDelete": False,
        }

    def restore(self, quarantine_id: str) -> dict[str, Any]:
        if not isinstance(quarantine_id, str) or not _QUARANTINE_ID.fullmatch(quarantine_id):
            raise TemplateWorkspaceRetentionError("Invalid quarantine identifier.")
        target_root = self.quarantine_root / quarantine_id
        if target_root.is_symlink() or not target_root.resolve().is_relative_to(
            self.quarantine_root.resolve()
        ):
            raise TemplateWorkspaceRetentionError("Retention quarantine path is unsafe.")
        manifest_path = target_root / "manifest.json"
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise TemplateWorkspaceRetentionError(
                "Retention quarantine was not found or is corrupt."
            ) from exc
        _validate_manifest(manifest, quarantine_id)
        if manifest.get("restoredAt"):
            raise TemplateWorkspaceRetentionError("Retention quarantine was already restored.")
        originals = [
            *(
                self.service.workspaces.root / f"{workspace_id}.json"
                for workspace_id in manifest["workspaces"]
            ),
            *(self.service.sources / source_name for source_name in manifest["sources"]),
        ]
        if any(path.exists() for path in originals):
            raise TemplateWorkspaceRetentionError(
                "Restore target already exists; no files were moved."
            )
        moved: list[tuple[Path, Path]] = []
        try:
            for workspace_id in manifest["workspaces"]:
                source = target_root / "workspaces" / f"{workspace_id}.json"
                destination = self.service.workspaces.root / source.name
                _move_owned(source, destination, target_root, self.service.workspaces.root)
                moved.append((source, destination))
            for source_name in manifest["sources"]:
                source = target_root / "sources" / source_name
                destination = self.service.sources / source.name
                _move_owned(source, destination, target_root, self.service.sources)
                moved.append((source, destination))
            manifest["restoredAt"] = _timestamp(self._now())
            _atomic_write(manifest_path, _pretty_json(manifest))
        except (OSError, TemplateWorkspaceRetentionError) as exc:
            for quarantined, restored in reversed(moved):
                if restored.exists() and not quarantined.exists():
                    quarantined.parent.mkdir(parents=True, exist_ok=True)
                    os.replace(restored, quarantined)
            raise TemplateWorkspaceRetentionError(
                "Retention restore failed and was rolled back."
            ) from exc
        return {
            "quarantineId": quarantine_id,
            "workspaceCount": len(manifest["workspaces"]),
            "sourceCount": len(manifest["sources"]),
            "restored": True,
        }

    def _scan(
        self,
        *,
        retention_days: int,
        protected_source_hashes: set[str],
    ) -> dict[str, Any]:
        if isinstance(retention_days, bool) or not isinstance(retention_days, int):
            raise TemplateWorkspaceRetentionError("Retention days must be an integer.")
        if not MIN_RETENTION_DAYS <= retention_days <= MAX_RETENTION_DAYS:
            raise TemplateWorkspaceRetentionError(
                f"Retention days must be between {MIN_RETENTION_DAYS} and {MAX_RETENTION_DAYS}."
            )
        if any(not re.fullmatch(r"[0-9a-f]{64}", value) for value in protected_source_hashes):
            raise TemplateWorkspaceRetentionError("Protected source checksum is invalid.")
        cutoff_time = self._now().astimezone(timezone.utc) - timedelta(days=retention_days)
        summaries, skipped_corrupt, collection_fingerprint = (
            self.service.workspaces.list_summaries()
        )
        blockers = []
        if skipped_corrupt:
            blockers.append(
                f"{skipped_corrupt} workspace file(s) are corrupt or unsupported; repair them first."
            )
        workspace_candidates = [
            item
            for item in summaries
            if item["archived"]
            and item["status"] in {"analyzed", "mapping_incomplete"}
            and _parse_timestamp(item["updatedAt"], "workspace update") <= cutoff_time
        ]
        workspace_ids = sorted(item["workspaceId"] for item in workspace_candidates)
        remaining_ids = {
            item["workspaceId"] for item in summaries if item["workspaceId"] not in workspace_ids
        }
        referenced_hashes: set[str] = set(protected_source_hashes)
        for workspace_id in remaining_ids:
            try:
                referenced_hashes.add(self.service.workspaces.load(workspace_id)["templateSha256"])
            except (KeyError, TemplateMappingWorkspaceError):
                blockers.append("A remaining workspace source reference could not be verified.")
                break

        source_summaries: list[dict[str, Any]] = []
        source_names: list[str] = []
        source_fingerprint_parts: list[str] = []
        if self.service.sources.exists():
            for path in sorted(self.service.sources.iterdir(), key=lambda item: item.name):
                if path.is_symlink() or not path.is_file() or not _SHA256_DOCX.fullmatch(path.name):
                    blockers.append("Template source storage contains an unsupported file.")
                    source_fingerprint_parts.append(f"unsupported:{path.name}")
                    continue
                stat_result = path.stat()
                source_fingerprint_parts.append(
                    f"{path.name}:{stat_result.st_size}:{stat_result.st_mtime_ns}"
                )
                source_hash = path.stem
                modified_at = datetime.fromtimestamp(stat_result.st_mtime, timezone.utc)
                if source_hash not in referenced_hashes and modified_at <= cutoff_time:
                    source_names.append(path.name)
                    source_summaries.append(
                        {
                            "sourceId": source_hash[:12],
                            "sizeBytes": stat_result.st_size,
                            "lastModifiedAt": _timestamp(modified_at),
                        }
                    )
        workspace_sizes = []
        for workspace_id in workspace_ids:
            try:
                workspace_sizes.append(
                    (self.service.workspaces.root / f"{workspace_id}.json").stat().st_size
                )
            except OSError:
                blockers.append("A workspace candidate changed during retention preview.")
        source_sizes = [item["sizeBytes"] for item in source_summaries]
        fingerprint_payload = {
            "collection": collection_fingerprint,
            "sources": source_fingerprint_parts,
            "protected": sorted(protected_source_hashes),
            "workspaceIds": workspace_ids,
            "sourceNames": source_names,
        }
        fingerprint = hashlib.sha256(_canonical_json(fingerprint_payload)).hexdigest()
        return {
            "cutoff": _timestamp(cutoff_time),
            "blockers": sorted(set(blockers)),
            "workspaceIds": workspace_ids,
            "sourceNames": source_names,
            "workspaceSummaries": workspace_candidates,
            "sourceSummaries": source_summaries,
            "reclaimableBytes": sum(workspace_sizes) + sum(source_sizes),
            "fingerprint": fingerprint,
        }

    def _encode_token(self, payload: dict[str, Any]) -> str:
        encoded = base64.urlsafe_b64encode(_canonical_json(payload)).decode("ascii").rstrip("=")
        signature = hmac.new(self.secret, encoded.encode("ascii"), hashlib.sha256).hexdigest()
        return f"{encoded}.{signature}"

    def _decode_token(self, token: str) -> dict[str, Any]:
        if not isinstance(token, str) or len(token) > 4096 or token.count(".") != 1:
            raise TemplateWorkspaceRetentionError("Invalid retention confirmation token.")
        encoded, signature = token.split(".", 1)
        expected = hmac.new(self.secret, encoded.encode("ascii"), hashlib.sha256).hexdigest()
        if not hmac.compare_digest(signature, expected):
            raise TemplateWorkspaceRetentionError("Invalid retention confirmation token.")
        try:
            padding = "=" * (-len(encoded) % 4)
            payload = json.loads(base64.b64decode(encoded + padding, altchars=b"-_", validate=True))
        except (ValueError, UnicodeError, json.JSONDecodeError) as exc:
            raise TemplateWorkspaceRetentionError("Invalid retention confirmation token.") from exc
        expected_keys = {
            "v",
            "quarantineId",
            "retentionDays",
            "fingerprint",
            "workspaceIds",
            "sourceNames",
            "expiresAt",
        }
        if not isinstance(payload, dict) or set(payload) != expected_keys or payload.get("v") != 1:
            raise TemplateWorkspaceRetentionError("Invalid retention confirmation token.")
        if not _QUARANTINE_ID.fullmatch(payload.get("quarantineId", "")):
            raise TemplateWorkspaceRetentionError("Invalid retention confirmation token.")
        if (
            isinstance(payload.get("retentionDays"), bool)
            or not isinstance(payload.get("retentionDays"), int)
            or not MIN_RETENTION_DAYS <= payload["retentionDays"] <= MAX_RETENTION_DAYS
            or not isinstance(payload.get("fingerprint"), str)
            or not re.fullmatch(r"[0-9a-f]{64}", payload["fingerprint"])
            or not _valid_workspace_ids(payload.get("workspaceIds"))
            or not _valid_source_names(payload.get("sourceNames"))
        ):
            raise TemplateWorkspaceRetentionError("Invalid retention confirmation token.")
        return payload


def _move_owned(source: Path, destination: Path, source_root: Path, destination_root: Path) -> None:
    if source.is_symlink() or not source.is_file():
        raise TemplateWorkspaceRetentionError("Retention source is not a regular owned file.")
    resolved_source = source.resolve(strict=True)
    resolved_source_root = source_root.resolve(strict=True)
    resolved_destination_root = destination_root.resolve()
    if not resolved_source.is_relative_to(resolved_source_root):
        raise TemplateWorkspaceRetentionError("Retention source escaped its owned root.")
    destination.parent.mkdir(parents=True, exist_ok=True)
    resolved_destination = destination.resolve()
    if not resolved_destination.is_relative_to(resolved_destination_root):
        raise TemplateWorkspaceRetentionError("Retention target escaped its owned root.")
    if destination.exists():
        raise TemplateWorkspaceRetentionError("Retention target already exists.")
    os.replace(source, destination)


def _validate_manifest(manifest: dict[str, Any], quarantine_id: str) -> None:
    expected = {
        "schemaVersion",
        "quarantineId",
        "createdAt",
        "restoredAt",
        "workspaces",
        "sources",
        "fingerprint",
    }
    if not isinstance(manifest, dict) or set(manifest) != expected:
        raise TemplateWorkspaceRetentionError("Retention quarantine manifest is invalid.")
    if (
        manifest.get("schemaVersion") != RETENTION_SCHEMA_VERSION
        or manifest.get("quarantineId") != quarantine_id
        or not _valid_workspace_ids(manifest.get("workspaces"))
        or not _valid_source_names(manifest.get("sources"))
        or not isinstance(manifest.get("fingerprint"), str)
        or not re.fullmatch(r"[0-9a-f]{64}", manifest["fingerprint"])
    ):
        raise TemplateWorkspaceRetentionError("Retention quarantine manifest is invalid.")
    _parse_timestamp(manifest.get("createdAt"), "quarantine creation")
    restored_at = manifest.get("restoredAt")
    if not isinstance(restored_at, str):
        raise TemplateWorkspaceRetentionError("Retention quarantine manifest is invalid.")
    if restored_at:
        _parse_timestamp(restored_at, "quarantine restore")


def _valid_workspace_ids(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) <= 10000
        and all(isinstance(item, str) and re.fullmatch(r"[0-9a-f]{32}", item) for item in value)
        and len(value) == len(set(value))
    )


def _valid_source_names(value: Any) -> bool:
    return (
        isinstance(value, list)
        and len(value) <= 10000
        and all(isinstance(item, str) and _SHA256_DOCX.fullmatch(item) for item in value)
        and len(value) == len(set(value))
    )


def _parse_timestamp(value: Any, label: str) -> datetime:
    if not isinstance(value, str) or not value:
        raise TemplateWorkspaceRetentionError(f"Invalid {label} timestamp.")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise TemplateWorkspaceRetentionError(f"Invalid {label} timestamp.") from exc
    if parsed.tzinfo is None:
        raise TemplateWorkspaceRetentionError(f"Invalid {label} timestamp.")
    return parsed.astimezone(timezone.utc)


def _timestamp(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="microseconds").replace("+00:00", "Z")


def _canonical_json(value: dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
        "utf-8"
    )


def _pretty_json(value: dict[str, Any]) -> bytes:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2).encode("utf-8")


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
