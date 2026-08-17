"""Central local-first application settings."""

from __future__ import annotations

import os

APP_NAME = "Reporter Pro"
APP_VERSION = "2.1.2"
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
DEFAULT_JOB_RESOURCE_POLL_MS = 500
DEFAULT_AUTO_BACKUP_INTERVAL_HOURS = 24
DEFAULT_AUTO_BACKUP_RETENTION = 7
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


def job_memory_limit_mib() -> int | None:
    """Return an opt-in backend RSS limit for one document job.

    A value of zero keeps monitoring enabled without cancelling large workloads.
    The limit is intentionally not inferred from row count because DOCX memory use
    depends heavily on the selected customer template and report type.
    """

    raw = os.getenv("AUTO_REPORT_JOB_MEMORY_LIMIT_MB", "0")
    try:
        value = int(raw)
    except ValueError:
        value = 0
    if value <= 0:
        return None
    return min(max(value, 256), 131_072)


def job_timeout_seconds() -> int | None:
    """Return an opt-in wall-clock timeout for Preview/Generate jobs."""

    raw = os.getenv("AUTO_REPORT_JOB_TIMEOUT_SECONDS", "0")
    try:
        value = int(raw)
    except ValueError:
        value = 0
    if value <= 0:
        return None
    return min(max(value, 30), 24 * 60 * 60)


def job_resource_poll_seconds() -> float:
    """Return the resource sampling interval, clamped to 100–5,000 ms."""

    raw = os.getenv("AUTO_REPORT_JOB_RESOURCE_POLL_MS", str(DEFAULT_JOB_RESOURCE_POLL_MS))
    try:
        value = int(raw)
    except ValueError:
        value = DEFAULT_JOB_RESOURCE_POLL_MS
    return min(max(value, 100), 5_000) / 1_000


def automatic_backup_enabled() -> bool:
    """Return whether the local workspace backup scheduler is enabled."""

    return os.getenv("AUTO_REPORT_AUTO_BACKUP", "1").strip().lower() in _TRUTHY


def automatic_backup_interval_hours() -> int:
    raw = os.getenv(
        "AUTO_REPORT_AUTO_BACKUP_INTERVAL_HOURS",
        str(DEFAULT_AUTO_BACKUP_INTERVAL_HOURS),
    )
    try:
        value = int(raw)
    except ValueError:
        value = DEFAULT_AUTO_BACKUP_INTERVAL_HOURS
    return min(max(value, 1), 24 * 30)


def automatic_backup_retention() -> int:
    raw = os.getenv("AUTO_REPORT_AUTO_BACKUP_RETENTION", str(DEFAULT_AUTO_BACKUP_RETENTION))
    try:
        value = int(raw)
    except ValueError:
        value = DEFAULT_AUTO_BACKUP_RETENTION
    return min(max(value, 1), 90)


def allow_custom_runtime_paths() -> bool:
    return os.getenv("AUTO_REPORT_ALLOW_CUSTOM_PATHS", "0").strip().lower() in {"1", "true", "yes"}


def performance_metrics_enabled() -> bool:
    """Return whether detailed, aggregate-only runtime timing is enabled."""

    return os.getenv("AUTO_REPORT_PERF_METRICS", "0").strip().lower() in _TRUTHY


def compact_prototype_enabled() -> bool:
    """Return whether the conservative compact table-prototype path is enabled."""

    return os.getenv("AUTO_REPORT_COMPACT_PROTOTYPE", "1").strip().lower() in _TRUTHY


def fast_cell_enabled() -> bool:
    """Return whether conservative in-place writes may be used for simple cells."""

    return os.getenv("AUTO_REPORT_FAST_CELL", "1").strip().lower() in _TRUTHY


def unified_report_scheduler_enabled() -> bool:
    """Route direct Preview/Generate builds through the bounded local scheduler."""

    return os.getenv("AUTO_REPORT_UNIFIED_SCHEDULER", "1").strip().lower() in _TRUTHY


def preview_jobs_enabled() -> bool:
    """Expose async Preview Jobs; set the flag to 0 for compatibility rollback."""

    return os.getenv("AUTO_REPORT_PREVIEW_JOBS", "1").strip().lower() in _TRUTHY


def preview_cache_enabled() -> bool:
    """Allow verified Preview promotion; set the flag to 0 for cold Generate."""

    return os.getenv("AUTO_REPORT_PREVIEW_CACHE", "1").strip().lower() in _TRUTHY


def preview_artifact_ttl_seconds() -> int:
    raw = os.getenv("AUTO_REPORT_PREVIEW_TTL_SECONDS", str(DEFAULT_PREVIEW_ARTIFACT_TTL_SECONDS))
    try:
        value = int(raw)
    except ValueError:
        value = DEFAULT_PREVIEW_ARTIFACT_TTL_SECONDS
    return min(max(value, 60), 24 * 60 * 60)


def preview_artifact_cache_entries() -> int:
    raw = os.getenv(
        "AUTO_REPORT_PREVIEW_CACHE_ENTRIES", str(DEFAULT_PREVIEW_ARTIFACT_CACHE_ENTRIES)
    )
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

    return os.getenv("AUTO_REPORT_PREPARED_TEMPLATE", "1").strip().lower() in _TRUTHY


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
