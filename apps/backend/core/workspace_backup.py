"""Create, inspect, and transactionally restore Reporter Pro workspaces."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import tempfile
import threading
import zipfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from core.database import Database, LATEST_SCHEMA_VERSION


BACKUP_SCHEMA_VERSION = 1
MAX_BACKUP_BYTES = 512 * 1024 * 1024
MAX_EXTRACTED_BYTES = 1024 * 1024 * 1024
MAX_ARCHIVE_MEMBERS = 5000
_RESTORE_LOCK = threading.RLock()


class WorkspaceBackupError(RuntimeError):
    """Raised when a backup cannot be trusted or restored safely."""


def create_workspace_backup(
    database: Database,
    templates_dir: Path | str,
    output_path: Path | str,
    *,
    app_version: str = "2.1.1",
) -> dict[str, Any]:
    """Write a database/template backup archive and return its manifest."""
    template_root = Path(templates_dir).resolve()
    destination = Path(output_path)
    destination.parent.mkdir(parents=True, exist_ok=True)

    template_files = sorted(
        (
            path
            for path in template_root.rglob("*.docx")
            if path.is_file() and not path.name.startswith("~$")
        ),
        key=lambda path: path.relative_to(template_root).as_posix().lower(),
    ) if template_root.exists() else []

    with tempfile.TemporaryDirectory(prefix="reporter-pro-backup-") as directory:
        snapshot_path = Path(directory) / "reporter.db"
        database.backup_to(snapshot_path)

        manifest: dict[str, Any] = {
            "schemaVersion": BACKUP_SCHEMA_VERSION,
            "app": "Reporter Pro",
            "appVersion": app_version,
            "createdAt": datetime.now(timezone.utc).isoformat(),
            "database": {
                "path": "database/reporter.db",
                "schemaVersion": database.schema_version,
                "size": snapshot_path.stat().st_size,
                "sha256": _sha256(snapshot_path),
                "records": _database_counts(snapshot_path),
            },
            "templates": [
                {
                    "path": f"templates/{path.relative_to(template_root).as_posix()}",
                    "size": path.stat().st_size,
                    "sha256": _sha256(path),
                }
                for path in template_files
            ],
            "includesGeneratedReports": False,
            "notes": [
                "Generated reports and environment files are intentionally excluded.",
                "The database may contain saved connection settings; protect this archive.",
            ],
        }

        with zipfile.ZipFile(destination, "w", compression=zipfile.ZIP_DEFLATED) as archive:
            archive.write(snapshot_path, "database/reporter.db")
            for path in template_files:
                relative = path.relative_to(template_root).as_posix()
                archive.write(path, f"templates/{relative}")
            archive.writestr(
                "manifest.json",
                json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"),
            )

    return manifest


def inspect_workspace_backup(
    archive_path: Path | str,
    database: Database,
    templates_dir: Path | str,
) -> dict[str, Any]:
    """Validate a backup without changing live state and return a restore preview."""
    archive_file = Path(archive_path)
    validated = _validate_archive(archive_file)
    with tempfile.TemporaryDirectory(prefix="reporter-pro-restore-preview-") as directory:
        staged = Path(directory)
        _extract_validated_archive(archive_file, validated, staged)
        _validate_docx_tree(staged / "templates")
        staged_database = staged / validated["database"]["path"]
        backup_counts = _validate_database(staged_database)
        _validate_database_manifest(staged_database, validated["database"], backup_counts)
        live_snapshot = staged / "current.db"
        database.backup_to(live_snapshot)
        current_counts = _database_counts(live_snapshot)

    templates = [
        {
            "path": entry["path"],
            "size": entry["size"],
            "sha256": entry["sha256"],
        }
        for entry in validated["templates"]
    ]
    current_template_count = sum(
        1
        for path in Path(templates_dir).rglob("*.docx")
        if path.is_file() and not path.name.startswith("~$")
    ) if Path(templates_dir).exists() else 0
    return {
        "valid": True,
        "dryRun": True,
        "confirmationToken": _sha256(archive_file),
        "archive": {
            "size": archive_file.stat().st_size,
            "sha256": _sha256(archive_file),
            "createdAt": validated["createdAt"],
            "appVersion": validated["appVersion"],
            "schemaVersion": validated["schemaVersion"],
        },
        "database": {
            "schemaVersion": validated["database"]["schemaVersion"],
            "records": backup_counts,
            "currentRecords": current_counts,
        },
        "templates": templates,
        "templateCount": len(templates),
        "currentTemplateCount": current_template_count,
        "warnings": _restore_warnings(validated),
    }


def restore_workspace_backup(
    archive_path: Path | str,
    database: Database,
    templates_dir: Path | str,
    *,
    confirmation_token: str,
) -> dict[str, Any]:
    """Restore database/templates and roll both back after any partial failure."""
    archive_file = Path(archive_path)
    archive_hash = _sha256(archive_file)
    if not confirmation_token or confirmation_token != archive_hash:
        raise WorkspaceBackupError(
            "Backup changed after dry-run; preview the archive again before restoring."
        )

    with _RESTORE_LOCK:
        validated = _validate_archive(archive_file)
        template_root = Path(templates_dir).resolve()
        template_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(prefix="reporter-pro-restore-") as directory:
            work = Path(directory)
            staged = work / "staged"
            rollback_db = work / "rollback.db"
            rollback_templates = work / "templates"
            _extract_validated_archive(archive_file, validated, staged)
            staged_db = staged / validated["database"]["path"]
            _validate_docx_tree(staged / "templates")
            restored_counts = _validate_database(staged_db)
            _validate_database_manifest(staged_db, validated["database"], restored_counts)
            database.backup_to(rollback_db)
            _copy_docx_tree(template_root, rollback_templates)

            try:
                database.restore_from(staged_db)
                database.initialize()
                installed_paths = _install_templates(
                    staged / "templates", template_root
                )
                database.relocate_template_paths(installed_paths)
                final_counts = _validate_live_restore(
                    database, restored_counts, installed_paths
                )
            except Exception as exc:
                rollback_errors: list[str] = []
                try:
                    database.restore_from(rollback_db)
                except Exception as rollback_exc:  # pragma: no cover - catastrophic I/O
                    rollback_errors.append(f"database: {rollback_exc}")
                try:
                    _replace_docx_tree(rollback_templates, template_root)
                except Exception as rollback_exc:  # pragma: no cover - catastrophic I/O
                    rollback_errors.append(f"templates: {rollback_exc}")
                if rollback_errors:
                    raise WorkspaceBackupError(
                        "Restore failed and rollback was incomplete ("
                        + "; ".join(rollback_errors)
                        + f"): {exc}"
                    ) from exc
                raise WorkspaceBackupError(
                    f"Restore failed; the previous workspace was rolled back: {exc}"
                ) from exc

    return {
        "restored": True,
        "rollbackUsed": False,
        "archiveSha256": archive_hash,
        "database": {
            "schemaVersion": database.schema_version,
            "sourceSchemaVersion": validated["database"]["schemaVersion"],
            "records": final_counts,
        },
        "templateCount": len(validated["templates"]),
        "message": "Workspace restored successfully. Reload the application state.",
    }


def _validate_archive(archive_path: Path) -> dict[str, Any]:
    if not archive_path.is_file():
        raise WorkspaceBackupError("Backup archive does not exist.")
    if archive_path.stat().st_size > MAX_BACKUP_BYTES:
        raise WorkspaceBackupError("Backup archive exceeds the 512 MiB safety limit.")
    try:
        with zipfile.ZipFile(archive_path) as archive:
            infos = archive.infolist()
            if len(infos) > MAX_ARCHIVE_MEMBERS:
                raise WorkspaceBackupError("Backup contains too many files.")
            names = [info.filename for info in infos]
            if len(names) != len(set(names)):
                raise WorkspaceBackupError("Backup contains duplicate archive paths.")
            if "manifest.json" not in names:
                raise WorkspaceBackupError("Backup manifest.json is missing.")
            total_size = sum(info.file_size for info in infos)
            if total_size > MAX_EXTRACTED_BYTES:
                raise WorkspaceBackupError("Expanded backup exceeds the 1 GiB safety limit.")
            for info in infos:
                _safe_archive_path(info.filename)
                if info.is_dir():
                    continue
                # ZIP entries with Unix symlink bits are not accepted.
                if (info.external_attr >> 16) & 0o170000 == 0o120000:
                    raise WorkspaceBackupError("Backup contains a symbolic link.")
            try:
                manifest = json.loads(archive.read("manifest.json"))
            except (json.JSONDecodeError, UnicodeDecodeError) as exc:
                raise WorkspaceBackupError("Backup manifest is not valid JSON.") from exc
            _validate_manifest_shape(manifest)
            declared = {
                "manifest.json",
                manifest["database"]["path"],
                *(entry["path"] for entry in manifest["templates"]),
            }
            file_names = {info.filename for info in infos if not info.is_dir()}
            if file_names != declared:
                raise WorkspaceBackupError(
                    "Backup members do not exactly match the signed manifest."
                )
            for entry in (manifest["database"], *manifest["templates"]):
                info = archive.getinfo(entry["path"])
                if info.file_size != entry["size"]:
                    raise WorkspaceBackupError(
                        f"Size mismatch for {entry['path']}."
                    )
                if _sha256_stream(archive.open(info)) != entry["sha256"]:
                    raise WorkspaceBackupError(
                        f"Checksum mismatch for {entry['path']}."
                    )
            return manifest
    except zipfile.BadZipFile as exc:
        raise WorkspaceBackupError("Backup is not a valid ZIP archive.") from exc


def _validate_manifest_shape(manifest: Any) -> None:
    if not isinstance(manifest, dict):
        raise WorkspaceBackupError("Backup manifest must be a JSON object.")
    if manifest.get("schemaVersion") != BACKUP_SCHEMA_VERSION:
        raise WorkspaceBackupError("Unsupported backup schema version.")
    if manifest.get("app") != "Reporter Pro":
        raise WorkspaceBackupError("Archive was not created by Reporter Pro.")
    if not isinstance(manifest.get("createdAt"), str) or not isinstance(
        manifest.get("appVersion"), str
    ):
        raise WorkspaceBackupError("Backup metadata is incomplete.")
    database = manifest.get("database")
    templates = manifest.get("templates")
    if not isinstance(database, dict) or not isinstance(templates, list):
        raise WorkspaceBackupError("Backup database/template manifest is invalid.")
    entries = [database, *templates]
    for entry in entries:
        if not isinstance(entry, dict):
            raise WorkspaceBackupError("Backup file manifest entry is invalid.")
        path = entry.get("path")
        if not isinstance(path, str):
            raise WorkspaceBackupError("Backup file path is invalid.")
        _safe_archive_path(path)
        if not isinstance(entry.get("size"), int) or entry["size"] < 0:
            raise WorkspaceBackupError(f"Invalid size for {path}.")
        digest = entry.get("sha256")
        if not isinstance(digest, str) or len(digest) != 64 or any(
            char not in "0123456789abcdef" for char in digest
        ):
            raise WorkspaceBackupError(f"Invalid SHA-256 for {path}.")
    if database["path"] != "database/reporter.db":
        raise WorkspaceBackupError("Backup database path is not supported.")
    if not isinstance(database.get("schemaVersion"), int):
        raise WorkspaceBackupError("Backup database schema version is missing.")
    if database["schemaVersion"] > LATEST_SCHEMA_VERSION:
        raise WorkspaceBackupError(
            "Backup database is newer than this Reporter Pro version."
        )
    for template in templates:
        if not template["path"].startswith("templates/") or not template[
            "path"
        ].lower().endswith(".docx"):
            raise WorkspaceBackupError("Backup contains an invalid template path.")


def _safe_archive_path(value: str) -> Path:
    path = Path(value.replace("\\", "/"))
    if path.is_absolute() or ".." in path.parts or not path.parts:
        raise WorkspaceBackupError(f"Unsafe archive path: {value}")
    if path.parts[0].endswith(":"):
        raise WorkspaceBackupError(f"Unsafe archive path: {value}")
    return path


def _extract_validated_archive(
    archive_path: Path, manifest: dict[str, Any], destination: Path
) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive_path) as archive:
        for name in (
            manifest["database"]["path"],
            *(entry["path"] for entry in manifest["templates"]),
        ):
            target = destination.joinpath(*_safe_archive_path(name).parts)
            target.parent.mkdir(parents=True, exist_ok=True)
            with archive.open(name) as source, target.open("wb") as output:
                for chunk in iter(lambda: source.read(1024 * 1024), b""):
                    output.write(chunk)


def _validate_database(path: Path) -> dict[str, int]:
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        integrity = connection.execute("PRAGMA integrity_check").fetchone()
        if not integrity or integrity[0] != "ok":
            raise WorkspaceBackupError("Backup database failed SQLite integrity_check.")
        version_row = connection.execute(
            "SELECT COALESCE(MAX(version), 0) FROM schema_migrations"
        ).fetchone()
        version = int(version_row[0]) if version_row else 0
        if version > LATEST_SCHEMA_VERSION:
            raise WorkspaceBackupError("Backup database schema is too new.")
        return _database_counts_connection(connection)
    except sqlite3.Error as exc:
        raise WorkspaceBackupError(f"Backup database is invalid: {exc}") from exc
    finally:
        connection.close()


def _validate_database_manifest(
    path: Path, manifest: dict[str, Any], actual_counts: dict[str, int]
) -> None:
    connection = sqlite3.connect(f"file:{path.as_posix()}?mode=ro", uri=True)
    try:
        row = connection.execute(
            "SELECT COALESCE(MAX(version), 0) FROM schema_migrations"
        ).fetchone()
        actual_version = int(row[0]) if row else 0
    finally:
        connection.close()
    if actual_version != manifest["schemaVersion"]:
        raise WorkspaceBackupError(
            "Database schema version does not match the backup manifest."
        )
    expected_counts = manifest.get("records")
    if isinstance(expected_counts, dict):
        comparable = {
            key: int(value)
            for key, value in expected_counts.items()
            if key in actual_counts
        }
        if any(actual_counts[key] != value for key, value in comparable.items()):
            raise WorkspaceBackupError(
                "Database record counts do not match the backup manifest."
            )


def _database_counts_connection(connection: sqlite3.Connection) -> dict[str, int]:
    counts: dict[str, int] = {}
    for table in (
        "templates",
        "template_versions",
        "presets",
        "report_history",
        "detection_rules",
        "detection_rule_versions",
    ):
        exists = connection.execute(
            "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
        ).fetchone()
        counts[table] = int(connection.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]) if exists else 0
    return counts


def _restore_warnings(manifest: dict[str, Any]) -> list[str]:
    warnings: list[str] = []
    version = manifest["database"]["schemaVersion"]
    if version < LATEST_SCHEMA_VERSION:
        warnings.append(
            f"Database schema v{version} will be migrated to v{LATEST_SCHEMA_VERSION} after restore."
        )
    if not manifest["templates"]:
        warnings.append("Backup contains no DOCX templates.")
    return warnings


def _copy_docx_tree(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    if not source.exists():
        return
    for path in source.rglob("*.docx"):
        if path.is_file() and not path.name.startswith("~$"):
            target = destination / path.relative_to(source)
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(path.read_bytes())


def _replace_docx_tree(source: Path, destination: Path) -> None:
    destination.mkdir(parents=True, exist_ok=True)
    for path in sorted(destination.rglob("*.docx"), reverse=True):
        if path.is_file() and not path.name.startswith("~$"):
            path.unlink()
    _copy_docx_tree(source, destination)


def _install_templates(source: Path, destination: Path) -> dict[str, Path]:
    _replace_docx_tree(source, destination)
    paths: dict[str, Path] = {}
    duplicates: set[str] = set()
    for path in destination.rglob("*.docx"):
        key = path.name.casefold()
        if key in paths:
            duplicates.add(key)
        paths[key] = path
    for duplicate in duplicates:
        paths.pop(duplicate, None)
    return paths


def _validate_docx_tree(source: Path) -> None:
    if not source.exists():
        return
    for path in source.rglob("*.docx"):
        try:
            with zipfile.ZipFile(path) as document:
                if "word/document.xml" not in document.namelist():
                    raise WorkspaceBackupError(f"Invalid template DOCX: {path.name}")
        except zipfile.BadZipFile as exc:
            raise WorkspaceBackupError(f"Invalid template DOCX: {path.name}") from exc


def _validate_live_restore(
    database: Database, expected_counts: dict[str, int], installed_paths: dict[str, Path]
) -> dict[str, int]:
    with tempfile.TemporaryDirectory(prefix="reporter-pro-restore-verify-") as directory:
        snapshot = Path(directory) / "restored.db"
        database.backup_to(snapshot)
        actual_counts = _validate_database(snapshot)
    differences = {
        key: (expected, actual_counts.get(key, 0))
        for key, expected in expected_counts.items()
        if (
            actual_counts.get(key, 0) < expected
            if key in {"template_versions", "detection_rule_versions"}
            else actual_counts.get(key, 0) != expected
        )
    }
    if differences:
        raise WorkspaceBackupError(
            f"Restored database record counts differ: {differences}."
        )
    for path in installed_paths.values():
        try:
            with zipfile.ZipFile(path) as document:
                if "word/document.xml" not in document.namelist():
                    raise WorkspaceBackupError(f"Invalid restored DOCX: {path.name}")
        except zipfile.BadZipFile as exc:
            raise WorkspaceBackupError(f"Invalid restored DOCX: {path.name}") from exc
    return actual_counts


def _sha256_stream(handle: Any) -> str:
    digest = hashlib.sha256()
    for chunk in iter(lambda: handle.read(1024 * 1024), b""):
        digest.update(chunk)
    return digest.hexdigest()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _database_counts(path: Path) -> dict[str, int]:
    connection = sqlite3.connect(str(path))
    try:
        return _database_counts_connection(connection)
    finally:
        connection.close()
