"""Bounded automatic workspace backups for the local/team runtime."""

from __future__ import annotations

import os
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from core.workspace_backup import create_workspace_backup

AUTO_BACKUP_PREFIX = "reporter-pro-auto-"


class ScheduledBackupManager:
    """Create at most one due backup and retain only owned automatic archives."""

    def __init__(
        self,
        database_factory: Callable[[], Any],
        templates_dir: Path | str,
        backup_dir: Path | str,
        *,
        interval_hours: int = 24,
        retention: int = 7,
        enabled: bool = True,
        now: Callable[[], datetime] | None = None,
    ) -> None:
        self.database_factory = database_factory
        self.templates_dir = Path(templates_dir)
        self.backup_dir = Path(backup_dir)
        self.interval_seconds = max(1, int(interval_hours)) * 60 * 60
        self.retention = min(max(int(retention), 1), 90)
        self.enabled = enabled
        self.now = now or (lambda: datetime.now(timezone.utc))
        self._lock = threading.Lock()

    def run_if_due(self) -> dict[str, Any]:
        if not self.enabled:
            return {"created": False, "reason": "disabled"}
        if not self._lock.acquire(blocking=False):
            return {"created": False, "reason": "already_running"}
        try:
            self.backup_dir.mkdir(parents=True, exist_ok=True)
            existing = self._owned_archives()
            now = self.now().astimezone(timezone.utc)
            if existing:
                newest = max(existing, key=lambda path: path.stat().st_mtime)
                age_seconds = now.timestamp() - newest.stat().st_mtime
                if age_seconds < self.interval_seconds:
                    return {
                        "created": False,
                        "reason": "not_due",
                        "latest": newest.name,
                    }

            timestamp = now.strftime("%Y%m%d-%H%M%S")
            destination = self.backup_dir / f"{AUTO_BACKUP_PREFIX}{timestamp}.zip"
            temporary = self.backup_dir / f".{destination.name}.{os.getpid()}.tmp"
            try:
                manifest = create_workspace_backup(
                    self.database_factory(),
                    self.templates_dir,
                    temporary,
                )
                os.replace(temporary, destination)
            finally:
                temporary.unlink(missing_ok=True)
            removed = self._enforce_retention()
            return {
                "created": True,
                "path": str(destination),
                "filename": destination.name,
                "removed": removed,
                "manifest": manifest,
            }
        finally:
            self._lock.release()

    def _owned_archives(self) -> list[Path]:
        return sorted(
            (path for path in self.backup_dir.glob(f"{AUTO_BACKUP_PREFIX}*.zip") if path.is_file()),
            key=lambda path: (path.stat().st_mtime, path.name),
            reverse=True,
        )

    def _enforce_retention(self) -> list[str]:
        removed: list[str] = []
        for path in self._owned_archives()[self.retention :]:
            path.unlink(missing_ok=True)
            removed.append(path.name)
        return removed
