"""Content-addressed, local prepared-template cache.

The cache owns only generated artifacts below its managed root. Source DOCX
files are read into an immutable byte snapshot, hashed, and never modified.
"""

from __future__ import annotations

import hashlib
import json
import os
import shutil
import threading
import uuid
import zipfile
from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

PREPARED_TEMPLATE_SCHEMA_VERSION = 1
PREPARED_TEMPLATE_COMPILER_VERSION = 1
TEMPLATE_COMPATIBILITY_VERSION = "1.0"


class PreparedTemplateError(RuntimeError):
    """Raised when a prepared artifact cannot be compiled or validated."""


@dataclass(frozen=True, slots=True)
class PreparedTemplateResult:
    key: str
    path: Path
    manifest: dict[str, object]
    source_bytes: bytes
    cache_hit: bool


Compiler = Callable[[bytes], tuple[bytes, Mapping[str, object]]]


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def file_sha256_bytes(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def prepared_template_key(
    source_hash: str,
    report_type: str,
    *,
    compatibility_version: str = TEMPLATE_COMPATIBILITY_VERSION,
    compiler_version: int = PREPARED_TEMPLATE_COMPILER_VERSION,
    blueprint_schema_version: int = 1,
) -> str:
    identity = "\n".join(
        (
            source_hash,
            str(report_type),
            str(compatibility_version),
            str(compiler_version),
            str(blueprint_schema_version),
        )
    ).encode("utf-8")
    return hashlib.sha256(identity).hexdigest()


class PreparedTemplateCache:
    """Thread-safe disk cache with per-key compilation and bounded LRU cleanup."""

    def __init__(
        self,
        root: str | Path,
        *,
        max_entries: int = 12,
        max_bytes: int = 512 * 1024 * 1024,
    ) -> None:
        self.root = Path(root).expanduser().resolve()
        self.max_entries = min(max(int(max_entries), 1), 128)
        self.max_bytes = min(max(int(max_bytes), 16 * 1024 * 1024), 4 * 1024**3)
        self.root.mkdir(parents=True, exist_ok=True)
        self._locks: dict[str, threading.Lock] = {}
        self._locks_guard = threading.Lock()
        self._leased: set[str] = set()
        self._sweep_temporary_files()
        self._sweep_invalid_entries()

    def get_or_compile(
        self,
        source_path: str | Path,
        report_type: str,
        compiler: Compiler,
        *,
        blueprint_schema_version: int = 1,
    ) -> PreparedTemplateResult:
        source = Path(source_path).expanduser().resolve()
        if not source.is_file() or source.suffix.casefold() != ".docx":
            raise PreparedTemplateError("Prepared template source must be an existing DOCX file.")
        source_bytes = source.read_bytes()
        source_hash = file_sha256_bytes(source_bytes)
        key = prepared_template_key(
            source_hash,
            report_type,
            blueprint_schema_version=blueprint_schema_version,
        )
        lock = self._lock_for(key)
        with lock:
            self._leased.add(key)
            try:
                cached = self._read_entry(key, source_hash, report_type)
                if cached is not None:
                    manifest, artifact_path = cached
                    manifest["lastAccessedAt"] = _utc_now()
                    self._write_json_atomic(self._entry_dir(key) / "manifest.json", manifest)
                    return PreparedTemplateResult(
                        key=key,
                        path=artifact_path,
                        manifest=manifest,
                        source_bytes=source_bytes,
                        cache_hit=True,
                    )

                self._discard_entry(key)
                try:
                    artifact_bytes, metadata = compiler(source_bytes)
                except Exception as exc:
                    raise PreparedTemplateError(
                        f"Prepared template compiler failed ({type(exc).__name__})."
                    ) from exc
                self._validate_docx_bytes(artifact_bytes)
                artifact_hash = file_sha256_bytes(artifact_bytes)
                now = _utc_now()
                manifest: dict[str, object] = {
                    "schemaVersion": PREPARED_TEMPLATE_SCHEMA_VERSION,
                    "compilerVersion": PREPARED_TEMPLATE_COMPILER_VERSION,
                    "compatibilityVersion": TEMPLATE_COMPATIBILITY_VERSION,
                    "blueprintSchemaVersion": int(blueprint_schema_version),
                    "key": key,
                    "sourceHash": source_hash,
                    "reportType": str(report_type),
                    "artifactHash": artifact_hash,
                    "artifactBytes": len(artifact_bytes),
                    "createdAt": now,
                    "lastAccessedAt": now,
                    "metadata": self._safe_metadata(metadata),
                }
                entry = self._entry_dir(key)
                entry.mkdir(parents=True, exist_ok=True)
                artifact_path = entry / "template.docx"
                self._write_bytes_atomic(artifact_path, artifact_bytes)
                self._write_json_atomic(entry / "manifest.json", manifest)
                self._cleanup_lru(protected={key})
                return PreparedTemplateResult(
                    key=key,
                    path=artifact_path,
                    manifest=manifest,
                    source_bytes=source_bytes,
                    cache_hit=False,
                )
            finally:
                self._leased.discard(key)

    def _lock_for(self, key: str) -> threading.Lock:
        with self._locks_guard:
            return self._locks.setdefault(key, threading.Lock())

    def _entry_dir(self, key: str) -> Path:
        if len(key) != 64 or any(character not in "0123456789abcdef" for character in key):
            raise PreparedTemplateError("Invalid prepared-template cache key.")
        candidate = (self.root / key).resolve()
        try:
            candidate.relative_to(self.root)
        except ValueError as exc:
            raise PreparedTemplateError("Prepared-template cache path escaped its root.") from exc
        return candidate

    def _read_entry(
        self,
        key: str,
        source_hash: str,
        report_type: str,
    ) -> tuple[dict[str, object], Path] | None:
        entry = self._entry_dir(key)
        manifest_path = entry / "manifest.json"
        artifact_path = entry / "template.docx"
        if not manifest_path.is_file() or not artifact_path.is_file():
            return None
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            if not isinstance(manifest, dict):
                return None
            expected = {
                "schemaVersion": PREPARED_TEMPLATE_SCHEMA_VERSION,
                "compilerVersion": PREPARED_TEMPLATE_COMPILER_VERSION,
                "compatibilityVersion": TEMPLATE_COMPATIBILITY_VERSION,
                "key": key,
                "sourceHash": source_hash,
                "reportType": str(report_type),
            }
            if any(manifest.get(name) != value for name, value in expected.items()):
                return None
            artifact = artifact_path.read_bytes()
            if manifest.get("artifactHash") != file_sha256_bytes(artifact):
                return None
            if manifest.get("artifactBytes") != len(artifact):
                return None
            self._validate_docx_bytes(artifact)
            return manifest, artifact_path
        except (
            OSError,
            ValueError,
            json.JSONDecodeError,
            zipfile.BadZipFile,
            PreparedTemplateError,
        ):
            return None

    @staticmethod
    def _validate_docx_bytes(payload: bytes) -> None:
        from io import BytesIO

        try:
            with zipfile.ZipFile(BytesIO(payload)) as archive:
                bad_member = archive.testzip()
                names = set(archive.namelist())
        except (OSError, zipfile.BadZipFile) as exc:
            raise PreparedTemplateError("Prepared artifact is not a valid DOCX package.") from exc
        if bad_member or "word/document.xml" not in names or "[Content_Types].xml" not in names:
            raise PreparedTemplateError("Prepared artifact failed DOCX package validation.")

    @staticmethod
    def _safe_metadata(metadata: Mapping[str, object]) -> dict[str, object]:
        allowed = {"templateMode"}
        return {
            str(key): value
            for key, value in metadata.items()
            if key in allowed and isinstance(value, (str, int, float, bool, type(None)))
        }

    def _write_bytes_atomic(self, target: Path, payload: bytes) -> None:
        temporary = target.with_name(f".{target.name}.{uuid.uuid4().hex}.tmp")
        try:
            temporary.write_bytes(payload)
            os.replace(temporary, target)
        finally:
            temporary.unlink(missing_ok=True)

    def _write_json_atomic(self, target: Path, payload: Mapping[str, object]) -> None:
        encoded = (json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode(
            "utf-8"
        )
        self._write_bytes_atomic(target, encoded)

    def _discard_entry(self, key: str) -> None:
        entry = self._entry_dir(key)
        if entry.exists():
            shutil.rmtree(entry)

    def _sweep_temporary_files(self) -> None:
        for path in self.root.rglob("*.tmp"):
            try:
                path.resolve().relative_to(self.root)
                path.unlink(missing_ok=True)
            except (OSError, ValueError):
                continue

    def _sweep_invalid_entries(self) -> None:
        """Remove only content-addressed entries that cannot be trusted."""

        for entry in self.root.iterdir():
            key = entry.name
            if (
                not entry.is_dir()
                or len(key) != 64
                or any(character not in "0123456789abcdef" for character in key)
            ):
                continue
            manifest_path = entry / "manifest.json"
            artifact_path = entry / "template.docx"
            valid = False
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                artifact = artifact_path.read_bytes()
                valid = (
                    isinstance(manifest, dict)
                    and manifest.get("schemaVersion") == PREPARED_TEMPLATE_SCHEMA_VERSION
                    and manifest.get("compilerVersion") == PREPARED_TEMPLATE_COMPILER_VERSION
                    and manifest.get("compatibilityVersion") == TEMPLATE_COMPATIBILITY_VERSION
                    and manifest.get("key") == key
                    and manifest.get("artifactHash") == file_sha256_bytes(artifact)
                    and manifest.get("artifactBytes") == len(artifact)
                )
                if valid:
                    self._validate_docx_bytes(artifact)
            except (
                OSError,
                ValueError,
                TypeError,
                json.JSONDecodeError,
                PreparedTemplateError,
            ):
                valid = False
            if not valid:
                self._discard_entry(key)

    def _cleanup_lru(self, *, protected: set[str] | None = None) -> None:
        protected_keys = set(protected or ()) | set(self._leased)
        entries: list[tuple[str, str, int]] = []
        for path in self.root.iterdir():
            if not path.is_dir() or len(path.name) != 64:
                continue
            manifest_path = path / "manifest.json"
            try:
                manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
                entries.append(
                    (
                        path.name,
                        str(manifest.get("lastAccessedAt", "")),
                        int(manifest.get("artifactBytes", 0)),
                    )
                )
            except (OSError, ValueError, TypeError, json.JSONDecodeError):
                if path.name not in protected_keys:
                    self._discard_entry(path.name)
        entries.sort(key=lambda item: item[1], reverse=True)
        total = 0
        kept = 0
        for key, _accessed, size in entries:
            if key in protected_keys:
                total += max(size, 0)
                kept += 1
                continue
            if kept < self.max_entries and total + max(size, 0) <= self.max_bytes:
                total += max(size, 0)
                kept += 1
                continue
            self._discard_entry(key)


__all__ = [
    "PREPARED_TEMPLATE_COMPILER_VERSION",
    "PREPARED_TEMPLATE_SCHEMA_VERSION",
    "TEMPLATE_COMPATIBILITY_VERSION",
    "PreparedTemplateCache",
    "PreparedTemplateError",
    "PreparedTemplateResult",
    "prepared_template_key",
]
