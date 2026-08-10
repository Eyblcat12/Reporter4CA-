"""Shared immutable pipeline primitives for Preview and Generate."""

from __future__ import annotations

import tempfile
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from plugins.manager import combined_cache_policy, plugin_manifest

from core.report_signature import canonical_sha256
from core.report_snapshot import (
    AcceptedReportSnapshot,
    PreparedReportSnapshot,
    thaw_json,
)


class SnapshotChangedError(RuntimeError):
    """Raised when a pinned plugin/template identity changed before execution."""


@dataclass(frozen=True)
class OrchestratedDocument:
    document: Any
    prepared: PreparedReportSnapshot
    manifest: dict[str, Any]
    integrity: dict[str, Any]


class ReportOrchestrator:
    """Prepare and build one report from the same accepted snapshot contract."""

    def prepare(
        self,
        accepted: AcceptedReportSnapshot,
        *,
        plugins: list[Any],
        validate_and_normalize: Callable[
            [list[dict[str, Any]], dict[str, Any], str],
            tuple[dict[str, Any], dict[str, Any], list[Any]],
        ],
        apply_input_plugins: Callable[[dict[str, Any], list[Any]], dict[str, Any]],
    ) -> PreparedReportSnapshot:
        metadata = thaw_json(accepted.metadata)
        plugin_settings = metadata.get("pluginSettings", {})
        actual_manifest = plugin_manifest(
            plugins,
            plugin_settings if isinstance(plugin_settings, dict) else {},
        )
        if canonical_sha256(actual_manifest) != canonical_sha256(accepted.plugin_manifest):
            raise SnapshotChangedError("PLUGIN_SNAPSHOT_CHANGED")
        rows = thaw_json(accepted.rows)
        payload, quality, warnings = validate_and_normalize(
            rows,
            metadata,
            accepted.report_type,
        )
        processed = apply_input_plugins(payload, plugins)
        if not isinstance(processed, dict):
            raise TypeError("Input plugin pipeline must return a report payload object.")
        return PreparedReportSnapshot.create(
            accepted,
            payload=processed,
            quality=quality,
            warnings=warnings,
            plugin_manifest=actual_manifest,
            cache_policy=combined_cache_policy(actual_manifest),
        )

    def build(
        self,
        prepared: PreparedReportSnapshot,
        *,
        plugins: list[Any],
        build_document: Callable[..., Any],
        apply_document_plugins: Callable[[Any, dict[str, Any], list[Any]], Any],
        verify_document: Callable[[Any, dict[str, Any]], dict[str, Any]],
        metrics: Any | None = None,
        check_cancelled: Any | None = None,
        on_build_progress: Any | None = None,
    ) -> OrchestratedDocument:
        accepted = prepared.accepted
        payload = thaw_json(prepared.payload)
        with materialized_template(accepted) as template_path:
            document = build_document(
                payload,
                title=accepted.title,
                organization=accepted.organization,
                assessment_date=accepted.assessment_date or None,
                template_path=template_path,
                report_type=accepted.report_type,
                metrics=metrics,
                check_cancelled=check_cancelled,
                on_build_progress=on_build_progress,
            )
        manifest = getattr(document, "_reporter_manifest", {})
        integrity = getattr(document, "_reporter_integrity", {})
        if not isinstance(manifest, dict):
            manifest = {}
        if not isinstance(integrity, dict):
            integrity = {"valid": True, "verificationSkipped": True}
        document = apply_document_plugins(document, payload, plugins)
        if manifest:
            integrity = verify_document(document, manifest)
        return OrchestratedDocument(
            document=document,
            prepared=prepared,
            manifest=manifest,
            integrity=integrity,
        )


@contextmanager
def materialized_template(snapshot: AcceptedReportSnapshot):
    """Expose pinned template bytes only for the duration of one build."""

    if not snapshot.template_bytes:
        yield None
        return
    temporary_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as temporary:
            temporary.write(snapshot.template_bytes)
            temporary_path = Path(temporary.name)
        yield str(temporary_path)
    finally:
        if temporary_path is not None:
            temporary_path.unlink(missing_ok=True)
