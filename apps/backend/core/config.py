"""Central local-first application settings."""

from __future__ import annotations

import os


APP_NAME = "Reporter Pro"
APP_VERSION = "2.0.0"
DEFAULT_CORS_ORIGINS = (
    "http://127.0.0.1:5173",
    "http://localhost:5173",
)
DEFAULT_MAX_IMPORT_MB = 50
DEFAULT_MAX_REPORT_ROWS = 50_000
DEFAULT_PREPARED_TEMPLATE_CACHE_MB = 512
DEFAULT_PREPARED_TEMPLATE_CACHE_ENTRIES = 12
DEFAULT_PREVIEW_ARTIFACT_TTL_SECONDS = 15 * 60
DEFAULT_PREVIEW_ARTIFACT_CACHE_MB = 512
DEFAULT_PREVIEW_ARTIFACT_CACHE_ENTRIES = 20
_TRUTHY = {"1", "true", "yes", "on"}


def cors_origins() -> list[str]:
    """Return explicit browser origins; wildcard CORS is never enabled by default."""
    raw = os.getenv("AUTO_REPORT_CORS_ORIGINS", "")
    origins = [item.strip().rstrip("/") for item in raw.split(",") if item.strip()]
    return list(dict.fromkeys(origins or DEFAULT_CORS_ORIGINS))


def max_import_bytes() -> int:
    """Return the local import limit with a defensive 1–512 MB range."""
    raw = os.getenv("AUTO_REPORT_MAX_IMPORT_MB", str(DEFAULT_MAX_IMPORT_MB))
    try:
        megabytes = int(raw)
    except ValueError:
        megabytes = DEFAULT_MAX_IMPORT_MB
    return min(max(megabytes, 1), 512) * 1024 * 1024


def max_report_rows() -> int:
    """Bound report work for a personal/team workstation (100–500,000 rows)."""
    raw = os.getenv("AUTO_REPORT_MAX_ROWS", str(DEFAULT_MAX_REPORT_ROWS))
    try:
        rows = int(raw)
    except ValueError:
        rows = DEFAULT_MAX_REPORT_ROWS
    return min(max(rows, 100), 500_000)


def allow_custom_runtime_paths() -> bool:
    return os.getenv("AUTO_REPORT_ALLOW_CUSTOM_PATHS", "0").strip().lower() in {"1", "true", "yes"}


def performance_metrics_enabled() -> bool:
    """Return whether detailed, aggregate-only runtime timing is enabled."""

    return os.getenv("AUTO_REPORT_PERF_METRICS", "0").strip().lower() in _TRUTHY


def compact_prototype_enabled() -> bool:
    """Return whether the conservative compact table-prototype path is enabled."""

    return (
        os.getenv("AUTO_REPORT_COMPACT_PROTOTYPE", "0").strip().lower()
        in _TRUTHY
    )


def fast_cell_enabled() -> bool:
    """Return whether conservative in-place writes may be used for simple cells."""

    return os.getenv("AUTO_REPORT_FAST_CELL", "1").strip().lower() in _TRUTHY


def unified_report_scheduler_enabled() -> bool:
    """Route direct Preview/Generate builds through the bounded local scheduler."""

    return os.getenv("AUTO_REPORT_UNIFIED_SCHEDULER", "1").strip().lower() in _TRUTHY


def preview_jobs_enabled() -> bool:
    """Expose the asynchronous Preview Job API without changing the legacy UI."""

    return os.getenv("AUTO_REPORT_PREVIEW_JOBS", "0").strip().lower() in _TRUTHY


def preview_cache_enabled() -> bool:
    """Allow explicit Generate promotion from a verified Preview artifact."""

    return os.getenv("AUTO_REPORT_PREVIEW_CACHE", "0").strip().lower() in _TRUTHY


def preview_artifact_ttl_seconds() -> int:
    raw = os.getenv("AUTO_REPORT_PREVIEW_TTL_SECONDS", str(DEFAULT_PREVIEW_ARTIFACT_TTL_SECONDS))
    try:
        value = int(raw)
    except ValueError:
        value = DEFAULT_PREVIEW_ARTIFACT_TTL_SECONDS
    return min(max(value, 60), 24 * 60 * 60)


def preview_artifact_cache_entries() -> int:
    raw = os.getenv("AUTO_REPORT_PREVIEW_CACHE_ENTRIES", str(DEFAULT_PREVIEW_ARTIFACT_CACHE_ENTRIES))
    try:
        value = int(raw)
    except ValueError:
        value = DEFAULT_PREVIEW_ARTIFACT_CACHE_ENTRIES
    return min(max(value, 1), 200)


def preview_artifact_cache_bytes() -> int:
    raw = os.getenv("AUTO_REPORT_PREVIEW_CACHE_MB", str(DEFAULT_PREVIEW_ARTIFACT_CACHE_MB))
    try:
        value = int(raw)
    except ValueError:
        value = DEFAULT_PREVIEW_ARTIFACT_CACHE_MB
    return min(max(value, 16), 4096) * 1024 * 1024


def prepared_template_enabled() -> bool:
    """Return whether immutable prepared-template artifacts may be reused."""

    return (
        os.getenv("AUTO_REPORT_PREPARED_TEMPLATE", "1").strip().lower()
        in _TRUTHY
    )


def prepared_template_cache_entries() -> int:
    """Bound the local cache to a small number of immutable templates."""

    raw = os.getenv(
        "AUTO_REPORT_PREPARED_CACHE_ENTRIES",
        str(DEFAULT_PREPARED_TEMPLATE_CACHE_ENTRIES),
    )
    try:
        value = int(raw)
    except ValueError:
        value = DEFAULT_PREPARED_TEMPLATE_CACHE_ENTRIES
    return min(max(value, 1), 128)


def prepared_template_cache_bytes() -> int:
    """Return the prepared-template cache byte budget (16 MiB–4 GiB)."""

    raw = os.getenv(
        "AUTO_REPORT_PREPARED_CACHE_MB",
        str(DEFAULT_PREPARED_TEMPLATE_CACHE_MB),
    )
    try:
        megabytes = int(raw)
    except ValueError:
        megabytes = DEFAULT_PREPARED_TEMPLATE_CACHE_MB
    return min(max(megabytes, 16), 4096) * 1024 * 1024
