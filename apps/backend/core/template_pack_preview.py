"""Isolated Preview/diff and byte-for-byte promotion for published Template Packs."""

from __future__ import annotations

import hashlib
import io
import json
import threading
from collections import OrderedDict
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Any, Callable

from .profile_renderer import PROFILE_RENDERER_VERSION, render_profile_document
from .report_snapshot import PreparedReportSnapshot
from .template_pack import inspect_template_pack
from .template_pack_validation import structural_diff, structural_snapshot

PREVIEW_SCHEMA_VERSION = "1.0"


class TemplatePackPreviewError(ValueError):
    """Raised when a pack preview is stale, corrupt or incompatible."""


@dataclass(frozen=True)
class TemplatePackPreviewIdentity:
    pack_id: str
    pack_version: str
    pack_sha256: str
    template_sha256: str
    request_signature: str
    content_signature: str
    renderer_version: str = PROFILE_RENDERER_VERSION

    @property
    def cache_key(self) -> str:
        return _canonical_sha256(self.public())

    def public(self) -> dict[str, str]:
        return {
            "packId": self.pack_id,
            "packVersion": self.pack_version,
            "packSha256": self.pack_sha256,
            "templateSha256": self.template_sha256,
            "requestSignature": self.request_signature,
            "contentSignature": self.content_signature,
            "rendererVersion": self.renderer_version,
        }


@dataclass(frozen=True)
class TemplatePackPreviewArtifact:
    preview_id: str
    identity: TemplatePackPreviewIdentity
    artifact_sha256: str
    size_bytes: int
    created_at: str
    template_structure: dict[str, Any]
    rendered_structure: dict[str, Any]
    structure_diff: tuple[dict[str, Any], ...]
    manifest: dict[str, Any]
    artifact_bytes: bytes
    cache_hit: bool = False

    def public(self) -> dict[str, Any]:
        return {
            "previewId": self.preview_id,
            "identity": self.identity.public(),
            "artifactSha256": self.artifact_sha256,
            "sizeBytes": self.size_bytes,
            "createdAt": self.created_at,
            "cacheHit": self.cache_hit,
            "templateStructure": self.template_structure,
            "renderedStructure": self.rendered_structure,
            "structureDiff": list(self.structure_diff),
            "manifest": self.manifest,
            "selectionIntegrated": False,
            "legacyRendererUsed": False,
        }


@dataclass(frozen=True)
class TemplatePackPromotion:
    preview_id: str
    identity: TemplatePackPreviewIdentity
    artifact_sha256: str
    artifact_bytes: bytes


class TemplatePackPreviewCache:
    """Bounded process-local cache keyed by complete pack and snapshot identity."""

    def __init__(self, *, max_entries: int = 8, max_bytes: int = 256 * 1024 * 1024):
        self.max_entries = max(1, int(max_entries))
        self.max_bytes = max(1, int(max_bytes))
        self._entries: OrderedDict[str, TemplatePackPreviewArtifact] = OrderedDict()
        self._lock = threading.RLock()

    def get(self, identity: TemplatePackPreviewIdentity) -> TemplatePackPreviewArtifact | None:
        with self._lock:
            artifact = self._entries.get(identity.cache_key)
            if artifact is None:
                return None
            if (
                artifact.identity != identity
                or _sha256(artifact.artifact_bytes) != artifact.artifact_sha256
            ):
                self._entries.pop(identity.cache_key, None)
                return None
            self._entries.move_to_end(identity.cache_key)
            return replace(artifact, cache_hit=True)

    def put(self, artifact: TemplatePackPreviewArtifact) -> None:
        if artifact.size_bytes > self.max_bytes:
            return
        with self._lock:
            self._entries[artifact.identity.cache_key] = replace(artifact, cache_hit=False)
            self._entries.move_to_end(artifact.identity.cache_key)
            while len(self._entries) > self.max_entries or self.total_bytes > self.max_bytes:
                self._entries.popitem(last=False)

    @property
    def total_bytes(self) -> int:
        return sum(item.size_bytes for item in self._entries.values())

    @property
    def entry_count(self) -> int:
        return len(self._entries)


def preview_template_pack(
    pack_bytes: bytes,
    prepared: PreparedReportSnapshot,
    *,
    cache: TemplatePackPreviewCache | None = None,
    check_cancelled: Callable[[], Any] | None = None,
    on_progress: Callable[[int, str], Any] | None = None,
) -> TemplatePackPreviewArtifact:
    """Create or reuse a preview pinned to the exact pack and accepted snapshot."""

    inspection = inspect_template_pack(pack_bytes, require_publishable=True)
    identity = _identity(pack_bytes, prepared, inspection.pack_id, inspection.version)
    if cache is not None:
        cached = cache.get(identity)
        if cached is not None:
            if on_progress is not None:
                on_progress(100, "preview.cache_hit")
            return cached
    rendered = render_profile_document(
        pack_bytes,
        prepared,
        check_cancelled=check_cancelled,
        on_progress=(
            (lambda percent, semantic: on_progress(round(percent * 0.8), semantic))
            if on_progress is not None
            else None
        ),
    )
    output = io.BytesIO()
    rendered.document.save(output)
    artifact_bytes = output.getvalue()
    if on_progress is not None:
        on_progress(85, "preview.structure")
    template_structure = structural_snapshot(
        inspection.template_bytes,
        {"reportType": prepared.accepted.report_type, "renderedSemantics": [], "rowCounts": {}},
    )
    rendered_structure = structural_snapshot(artifact_bytes, rendered.manifest)
    differences = tuple(
        issue.public() for issue in structural_diff(template_structure, rendered_structure)
    )
    preview_id = identity.cache_key[:24]
    artifact = TemplatePackPreviewArtifact(
        preview_id=preview_id,
        identity=identity,
        artifact_sha256=_sha256(artifact_bytes),
        size_bytes=len(artifact_bytes),
        created_at=_timestamp(),
        template_structure=template_structure,
        rendered_structure=rendered_structure,
        structure_diff=differences,
        manifest=rendered.manifest,
        artifact_bytes=artifact_bytes,
    )
    if cache is not None:
        cache.put(artifact)
    if on_progress is not None:
        on_progress(100, "preview.ready")
    return artifact


def promote_template_pack_preview(
    preview: TemplatePackPreviewArtifact,
    pack_bytes: bytes,
    prepared: PreparedReportSnapshot,
) -> TemplatePackPromotion:
    """Promote exact preview bytes only when every identity component is current."""

    inspection = inspect_template_pack(pack_bytes, require_publishable=True)
    current = _identity(pack_bytes, prepared, inspection.pack_id, inspection.version)
    if current != preview.identity:
        raise TemplatePackPreviewError(
            "Preview is stale because the pack, template, request or prepared content changed."
        )
    actual_hash = _sha256(preview.artifact_bytes)
    if actual_hash != preview.artifact_sha256:
        raise TemplatePackPreviewError("Preview artifact failed checksum verification.")
    if preview.manifest.get("contentSignature") != prepared.content_signature:
        raise TemplatePackPreviewError("Preview content signature no longer matches Generate.")
    return TemplatePackPromotion(
        preview_id=preview.preview_id,
        identity=current,
        artifact_sha256=actual_hash,
        artifact_bytes=preview.artifact_bytes,
    )


def _identity(
    pack_bytes: bytes,
    prepared: PreparedReportSnapshot,
    pack_id: str,
    pack_version: str,
) -> TemplatePackPreviewIdentity:
    return TemplatePackPreviewIdentity(
        pack_id=pack_id,
        pack_version=pack_version,
        pack_sha256=_sha256(pack_bytes),
        template_sha256=prepared.accepted.template_hash,
        request_signature=prepared.accepted.request_signature,
        content_signature=prepared.content_signature,
    )


def _canonical_sha256(value: Any) -> str:
    encoded = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return _sha256(encoded.encode("utf-8"))


def _sha256(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat()
