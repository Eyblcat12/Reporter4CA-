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
