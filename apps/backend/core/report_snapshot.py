"""Immutable accepted/prepared snapshots shared by Preview and Generate."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
import hashlib
from types import MappingProxyType
from typing import Any, Mapping

from core.report_signature import SIGNATURE_SCHEMA_VERSION, canonical_sha256, normalize_string


ENGINE_CONTENT_SCHEMA_VERSION = "1.0"
DEFAULT_REPORT_TITLE = "BÁO CÁO ĐÁNH GIÁ AN TOÀN THÔNG TIN"


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def freeze_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        frozen: dict[str, Any] = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise TypeError("Snapshot object keys must be strings.")
            normalized_key = normalize_string(key)
            if normalized_key in frozen:
                raise ValueError("Unicode normalization produced a duplicate snapshot key.")
            frozen[normalized_key] = freeze_json(item)
        return MappingProxyType(frozen)
    if isinstance(value, (list, tuple)):
        return tuple(freeze_json(item) for item in value)
    if isinstance(value, str):
        return normalize_string(value)
    if value is None or isinstance(value, (bool, int, float)):
        # Canonical hashing performs the finite-float validation.
        return value
    raise TypeError(f"Unsupported snapshot value: {type(value).__name__}")


def thaw_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return {str(key): thaw_json(item) for key, item in value.items()}
    if isinstance(value, tuple):
        return [thaw_json(item) for item in value]
    return value


@dataclass(frozen=True)
class AcceptedReportSnapshot:
    rows: tuple[Any, ...]
    metadata: Mapping[str, Any]
    title: str
    organization: str
    assessment_date: str
    report_type: str
    template_bytes: bytes
    template_hash: str
    template_key: str
    template_source_path: str
    plugin_manifest: tuple[Any, ...]
    plugins_dir: str
    disable_plugins: bool
    request_signature: str
    accepted_at: str = field(default_factory=_utc_now)
    engine_schema_version: str = ENGINE_CONTENT_SCHEMA_VERSION
    signature_schema_version: str = SIGNATURE_SCHEMA_VERSION

    @classmethod
    def create(
        cls,
        *,
        rows: list[dict[str, Any]],
        metadata: dict[str, Any] | None,
        title: str,
        organization: str,
        assessment_date: str,
        report_type: str,
        template_bytes: bytes,
        template_key: str,
        template_source_path: str = "",
        plugin_manifest: list[dict[str, Any]] | tuple[dict[str, Any], ...] = (),
        plugins_dir: str = "",
        disable_plugins: bool = False,
    ) -> "AcceptedReportSnapshot":
        frozen_rows = freeze_json(rows)
        frozen_metadata = freeze_json(metadata or {})
        frozen_plugins = freeze_json(plugin_manifest)
        effective_title = normalize_string((title or "").strip() or DEFAULT_REPORT_TITLE)
        effective_organization = normalize_string((organization or "").strip())
        effective_date = normalize_string((assessment_date or "").strip())
        effective_type = normalize_string(report_type)
        template_hash = hashlib.sha256(template_bytes).hexdigest() if template_bytes else ""
        identity = {
            "schema": SIGNATURE_SCHEMA_VERSION,
            "engine": ENGINE_CONTENT_SCHEMA_VERSION,
            "rows": frozen_rows,
            "metadata": frozen_metadata,
            "title": effective_title,
            "organization": effective_organization,
            "assessmentDate": effective_date,
            "reportType": effective_type,
            "templateHash": template_hash,
            "templateKey": normalize_string(template_key),
            "plugins": frozen_plugins,
        }
        request_signature = canonical_sha256(identity)
        return cls(
            rows=frozen_rows,
            metadata=frozen_metadata,
            title=effective_title,
            organization=effective_organization,
            assessment_date=effective_date,
            report_type=effective_type,
            template_bytes=bytes(template_bytes),
            template_hash=template_hash,
            template_key=normalize_string(template_key),
            template_source_path=normalize_string(template_source_path),
            plugin_manifest=frozen_plugins,
            plugins_dir=normalize_string(plugins_dir),
            disable_plugins=bool(disable_plugins),
            request_signature=request_signature,
        )


@dataclass(frozen=True)
class PreparedReportSnapshot:
    accepted: AcceptedReportSnapshot
    payload: Mapping[str, Any]
    quality: Mapping[str, Any]
    warnings: tuple[Any, ...]
    plugin_manifest: tuple[Any, ...]
    cache_policy: str
    content_signature: str
    generated_at: str

    @classmethod
    def create(
        cls,
        accepted: AcceptedReportSnapshot,
        *,
        payload: dict[str, Any],
        quality: dict[str, Any] | None = None,
        warnings: list[Any] | tuple[Any, ...] = (),
        plugin_manifest: list[dict[str, Any]] | tuple[dict[str, Any], ...] | None = None,
        cache_policy: str = "deterministic",
        generated_at: str | None = None,
    ) -> "PreparedReportSnapshot":
        frozen_payload = freeze_json(payload)
        frozen_quality = freeze_json(quality or {})
        frozen_warnings = freeze_json(warnings)
        frozen_plugins = freeze_json(
            plugin_manifest if plugin_manifest is not None else accepted.plugin_manifest
        )
        effective_generated_at = normalize_string(generated_at or _utc_now())
        content_signature = canonical_sha256({
            "schema": SIGNATURE_SCHEMA_VERSION,
            "engine": accepted.engine_schema_version,
            "payload": frozen_payload,
            "quality": frozen_quality,
            "title": accepted.title,
            "organization": accepted.organization,
            "assessmentDate": accepted.assessment_date,
            "reportType": accepted.report_type,
            "templateHash": accepted.template_hash,
            "plugins": frozen_plugins,
        })
        return cls(
            accepted=accepted,
            payload=frozen_payload,
            quality=frozen_quality,
            warnings=frozen_warnings,
            plugin_manifest=frozen_plugins,
            cache_policy=cache_policy,
            content_signature=content_signature,
            generated_at=effective_generated_at,
        )
