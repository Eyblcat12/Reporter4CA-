"""Managed, leased Preview DOCX artifacts for the local/team runtime."""

from __future__ import annotations

import hashlib
import os
import shutil
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Iterator


class PreviewArtifactError(RuntimeError):
    code = "ARTIFACT_ERROR"


class ArtifactNotReady(PreviewArtifactError):
    code = "JOB_NOT_READY"


class ArtifactStale(PreviewArtifactError):
    code = "ARTIFACT_STALE"


class ArtifactExpired(PreviewArtifactError):
    code = "ARTIFACT_EXPIRED"


class ArtifactCorrupt(PreviewArtifactError):
    code = "ARTIFACT_CORRUPT"


def _utc_iso(timestamp: float) -> str:
    return datetime.fromtimestamp(timestamp, tz=timezone.utc).isoformat()


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


@dataclass
class PreviewArtifact:
    id: str
    job_id: str
    request_signature: str
    content_signature: str
    template_hash: str
    cache_mode: str
    path: Path
    file_sha256: str
    size_bytes: int
    created_at_epoch: float
    expires_at_epoch: float
    state: str = "ready"
    lease_count: int = 0
    last_access_epoch: float = 0.0
    snapshot: Any = field(default=None, repr=False)
    plugin_manifest: tuple[Any, ...] = field(default_factory=tuple, repr=False)

    def public(self) -> dict[str, Any]:
        return {
            "previewId": self.id,
            "jobId": self.job_id,
            "status": self.state,
            "signature": self.request_signature,
            "contentSignature": self.content_signature,
            "templateHash": self.template_hash,
            "expiresAt": _utc_iso(self.expires_at_epoch),
            "cacheMode": self.cache_mode,
            "sizeBytes": self.size_bytes,
        }


class PreviewArtifactRegistry:
    """In-memory registry backed by a strictly managed local cache directory."""

    def __init__(
        self,
        root: str | Path,
        *,
        ttl_seconds: int = 15 * 60,
        max_artifacts: int = 20,
        max_bytes: int = 512 * 1024 * 1024,
        clock: Callable[[], float] = time.time,
    ) -> None:
        self.root = Path(root).resolve()
        self.root.mkdir(parents=True, exist_ok=True)
        self.ttl_seconds = max(1, int(ttl_seconds))
        self.max_artifacts = max(1, int(max_artifacts))
        self.max_bytes = max(1, int(max_bytes))
        self._clock = clock
        self._lock = threading.RLock()
        self._artifacts: dict[str, PreviewArtifact] = {}
        self.startup_sweep()

    def startup_sweep(self) -> None:
        """Remove only orphan files owned by this cache namespace."""

        for candidate in self.root.glob("preview-*.docx"):
            if candidate.is_file():
                candidate.unlink(missing_ok=True)
        for candidate in self.root.glob(".preview-*.tmp"):
            if candidate.is_file():
                candidate.unlink(missing_ok=True)

    def register_ready(
        self,
        source: str | Path,
        *,
        artifact_id: str | None = None,
        job_id: str,
        request_signature: str,
        content_signature: str,
        template_hash: str,
        cache_mode: str = "deterministic",
        snapshot: Any = None,
        plugin_manifest: tuple[Any, ...] = (),
    ) -> PreviewArtifact:
        source_path = Path(source)
        if not source_path.is_file():
            raise FileNotFoundError(source_path)
        now = self._clock()
        artifact_id = artifact_id or uuid.uuid4().hex[:16]
        if not artifact_id.isalnum() or len(artifact_id) > 64:
            raise ValueError("Invalid Preview artifact identifier.")
        destination = self.root / f"preview-{artifact_id}.docx"
        temporary = self.root / f".preview-{artifact_id}.tmp"
        try:
            shutil.copyfile(source_path, temporary)
            file_hash = _sha256(temporary)
            size = temporary.stat().st_size
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)

        artifact = PreviewArtifact(
            id=artifact_id,
            job_id=job_id,
            request_signature=request_signature,
            content_signature=content_signature,
            template_hash=template_hash,
            cache_mode=cache_mode,
            path=destination,
            file_sha256=file_hash,
            size_bytes=size,
            created_at_epoch=now,
            expires_at_epoch=now + self.ttl_seconds,
            last_access_epoch=now,
            snapshot=snapshot,
            plugin_manifest=tuple(plugin_manifest),
        )
        with self._lock:
            self._artifacts[artifact.id] = artifact
            self._evict_locked()
        source_path.unlink(missing_ok=True)
        return artifact

    def snapshot(self, artifact_id: str) -> dict[str, Any] | None:
        with self._lock:
            artifact = self._artifacts.get(artifact_id)
            if artifact is None:
                return None
            self._refresh_expiry_locked(artifact)
            return artifact.public()

    def find_ready(self, request_signature: str) -> PreviewArtifact | None:
        with self._lock:
            candidates = sorted(
                self._artifacts.values(),
                key=lambda item: item.created_at_epoch,
                reverse=True,
            )
            for artifact in candidates:
                self._refresh_expiry_locked(artifact)
                if (
                    artifact.request_signature == request_signature
                    and artifact.state == "ready"
                    and artifact.cache_mode == "deterministic"
                ):
                    return artifact
            return None

    def mark_stale(self, artifact_id: str) -> None:
        with self._lock:
            artifact = self._artifacts.get(artifact_id)
            if artifact and artifact.state == "ready":
                artifact.state = "stale"

    @contextmanager
    def lease(
        self,
        artifact_id: str,
        *,
        request_signature: str | None = None,
        template_hash: str | None = None,
        promoting: bool = False,
    ) -> Iterator[PreviewArtifact]:
        with self._lock:
            artifact = self._artifacts.get(artifact_id)
            if artifact is None:
                raise ArtifactExpired("Preview artifact is unavailable or expired.")
            self._refresh_expiry_locked(artifact)
            if artifact.state == "expired":
                raise ArtifactExpired("Preview artifact has expired.")
            if artifact.state == "stale":
                raise ArtifactStale("Preview artifact is stale.")
            if artifact.state not in {"ready", "leased", "promoting"}:
                raise ArtifactNotReady("Preview artifact is not ready.")
            if request_signature and artifact.request_signature != request_signature:
                artifact.state = "stale"
                raise ArtifactStale("Preview artifact no longer matches the request.")
            if template_hash and artifact.template_hash != template_hash:
                artifact.state = "stale"
                raise ArtifactStale("Preview artifact template no longer matches.")
            if not artifact.path.is_file() or _sha256(artifact.path) != artifact.file_sha256:
                artifact.state = "failed"
                artifact.path.unlink(missing_ok=True)
                raise ArtifactCorrupt("Preview artifact failed integrity verification.")
            artifact.lease_count += 1
            artifact.last_access_epoch = self._clock()
            artifact.state = "promoting" if promoting else "leased"
        try:
            yield artifact
        finally:
            with self._lock:
                current = self._artifacts.get(artifact_id)
                if current is not None:
                    current.lease_count = max(0, current.lease_count - 1)
                    current.last_access_epoch = self._clock()
                    if current.lease_count == 0 and current.state in {"leased", "promoting"}:
                        current.state = "ready"

    def cleanup(self) -> dict[str, int]:
        with self._lock:
            for artifact in self._artifacts.values():
                self._refresh_expiry_locked(artifact)
            removed = self._remove_disposable_locked()
            removed += self._evict_locked()
            return {"removed": removed, "remaining": len(self._artifacts)}

    def shutdown(self) -> None:
        """Best-effort cleanup; leased files remain for the OS/process exit path."""

        with self._lock:
            for artifact in self._artifacts.values():
                if artifact.lease_count == 0:
                    artifact.path.unlink(missing_ok=True)
            self._artifacts = {
                key: value for key, value in self._artifacts.items() if value.lease_count > 0
            }

    def _refresh_expiry_locked(self, artifact: PreviewArtifact) -> None:
        if artifact.state in {"ready", "stale"} and self._clock() >= artifact.expires_at_epoch:
            artifact.state = "expired"

    def _remove_disposable_locked(self) -> int:
        removed = 0
        for artifact_id, artifact in list(self._artifacts.items()):
            if artifact.lease_count == 0 and artifact.state in {"expired", "failed"}:
                artifact.path.unlink(missing_ok=True)
                self._artifacts.pop(artifact_id, None)
                removed += 1
        return removed

    def _evict_locked(self) -> int:
        removed = self._remove_disposable_locked()
        while True:
            total_bytes = sum(item.size_bytes for item in self._artifacts.values())
            if len(self._artifacts) <= self.max_artifacts and total_bytes <= self.max_bytes:
                break
            candidates = sorted(
                (
                    item
                    for item in self._artifacts.values()
                    if item.lease_count == 0 and item.state in {"ready", "stale"}
                ),
                key=lambda item: (item.last_access_epoch, item.created_at_epoch),
            )
            if not candidates:
                break
            victim = candidates[0]
            victim.path.unlink(missing_ok=True)
            self._artifacts.pop(victim.id, None)
            removed += 1
        return removed
