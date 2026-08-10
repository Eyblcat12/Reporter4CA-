"""Coordinate the local launcher and browser tabs for one Reporter session."""

from __future__ import annotations

import hashlib
import os
import threading
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

RUNTIME_PROTOCOL_VERSION = 2


def workspace_fingerprint(root: str | Path) -> str:
    """Return a stable, non-secret identity for one local Reporter checkout."""
    normalized = str(Path(root).resolve()).replace("\\", "/").rstrip("/").casefold()
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()[:24]


@dataclass
class _BrowserSession:
    last_seen: float
    closed_at: float | None = None


class RuntimeLifecycle:
    """In-memory lifecycle state for the local, single-user application."""

    def __init__(
        self,
        *,
        browser_ttl_seconds: float = 90.0,
        close_grace_seconds: float = 5.0,
        launcher_ttl_seconds: float = 8.0,
        workspace_root: str | Path | None = None,
        instance_id: str | None = None,
        process_id: int | None = None,
        started_at: str | None = None,
    ) -> None:
        self.browser_ttl_seconds = browser_ttl_seconds
        self.close_grace_seconds = close_grace_seconds
        self.launcher_ttl_seconds = launcher_ttl_seconds
        resolved_root = workspace_root or Path(__file__).resolve().parents[3]
        self.protocol_version = RUNTIME_PROTOCOL_VERSION
        self.instance_id = instance_id or uuid.uuid4().hex
        self.workspace_fingerprint = workspace_fingerprint(resolved_root)
        self.process_id = process_id if process_id is not None else os.getpid()
        self.started_at = started_at or datetime.now(timezone.utc).isoformat()
        self._lock = threading.RLock()
        self._sessions: dict[str, _BrowserSession] = {}
        self._launcher_id = ""
        self._launcher_pid = 0
        self._launcher_last_seen = 0.0
        self._shutdown_requested = False
        self._browser_seen = False
        self._no_browser_since: float | None = None
        self._active_operations = 0

    def attach_launcher(
        self,
        launcher_id: str,
        pid: int,
        *,
        instance_id: str = "",
        workspace_id: str = "",
    ) -> dict:
        now = time.monotonic()
        with self._lock:
            self._assert_identity_locked(instance_id, workspace_id)
            if self._shutdown_requested:
                raise ValueError("Reporter Pro backend is already shutting down.")

            same_owner = launcher_id == self._launcher_id and pid == self._launcher_pid
            if self._launcher_lease_active_locked(now) and not same_owner:
                raise ValueError(
                    f"Reporter Pro is already managed by launcher PID {self._launcher_pid}."
                )

            recovered = bool(self._launcher_id and not same_owner)
            self._launcher_id = launcher_id
            self._launcher_pid = pid
            self._launcher_last_seen = now
            if not same_owner:
                self._sessions.clear()
                self._browser_seen = False
                self._no_browser_since = None
            status = self._status_locked(now)
            status["launcherAttached"] = True
            status["recoveredLauncher"] = recovered
            return status

    def launcher_heartbeat(
        self,
        launcher_id: str,
        pid: int = 0,
        *,
        instance_id: str = "",
        workspace_id: str = "",
    ) -> dict:
        now = time.monotonic()
        with self._lock:
            self._assert_identity_locked(instance_id, workspace_id)
            if (
                self._shutdown_requested
                or launcher_id != self._launcher_id
                or (pid and pid != self._launcher_pid)
                or not self._launcher_lease_active_locked(now)
            ):
                raise ValueError("Launcher session is not active.")
            self._launcher_last_seen = now
            return self._status_locked(now)

    def detach_launcher(
        self,
        launcher_id: str,
        pid: int = 0,
        *,
        instance_id: str = "",
        workspace_id: str = "",
    ) -> bool:
        with self._lock:
            self._assert_identity_locked(instance_id, workspace_id)
            if launcher_id != self._launcher_id or (pid and pid != self._launcher_pid):
                return False
            self._shutdown_requested = True
            return True

    def open_browser(self, session_id: str) -> dict:
        now = time.monotonic()
        with self._lock:
            self._sessions[session_id] = _BrowserSession(last_seen=now)
            self._browser_seen = True
            self._no_browser_since = None
            return self._status_locked(now)

    def browser_heartbeat(self, session_id: str) -> dict:
        now = time.monotonic()
        with self._lock:
            session = self._sessions.get(session_id)
            if session is None:
                session = _BrowserSession(last_seen=now)
                self._sessions[session_id] = session
            session.last_seen = now
            session.closed_at = None
            self._browser_seen = True
            self._no_browser_since = None
            return self._status_locked(now)

    def close_browser(self, session_id: str) -> dict:
        now = time.monotonic()
        with self._lock:
            session = self._sessions.get(session_id)
            if session is not None:
                session.closed_at = now
            return self._status_locked(now)

    def status(self) -> dict:
        with self._lock:
            return self._status_locked(time.monotonic())

    def launcher_expired(self) -> bool:
        now = time.monotonic()
        with self._lock:
            return bool(
                self._launcher_id
                and self._active_operations == 0
                and (self._shutdown_requested or not self._launcher_lease_active_locked(now))
            )

    @contextmanager
    def operation(self):
        """Prevent lifecycle shutdown while a report artifact is being finalized."""
        with self._lock:
            self._active_operations += 1
        try:
            yield
        finally:
            now = time.monotonic()
            with self._lock:
                self._active_operations = max(0, self._active_operations - 1)
                if (
                    self._active_operations == 0
                    and self._launcher_id
                    and not self._shutdown_requested
                ):
                    # Give the launcher a full heartbeat window after CPU-heavy work.
                    self._launcher_last_seen = now

    def reset(self) -> None:
        """Reset process-local state; primarily useful for isolated tests."""
        with self._lock:
            self._sessions.clear()
            self._launcher_id = ""
            self._launcher_pid = 0
            self._launcher_last_seen = 0.0
            self._shutdown_requested = False
            self._browser_seen = False
            self._no_browser_since = None
            self._active_operations = 0

    def _assert_identity_locked(self, instance_id: str, workspace_id: str) -> None:
        if instance_id and instance_id != self.instance_id:
            raise ValueError("Reporter Pro backend instance changed.")
        if workspace_id and workspace_id != self.workspace_fingerprint:
            raise ValueError("Reporter Pro workspace identity does not match.")

    def _launcher_lease_active_locked(self, now: float) -> bool:
        return bool(
            self._launcher_id
            and not self._shutdown_requested
            and now - self._launcher_last_seen <= self.launcher_ttl_seconds
        )

    def _status_locked(self, now: float) -> dict:
        active_ids = []
        for session_id, session in list(self._sessions.items()):
            is_active = (
                session.closed_at is None and now - session.last_seen <= self.browser_ttl_seconds
            )
            if is_active:
                active_ids.append(session_id)

        if active_ids:
            self._no_browser_since = None
        elif self._browser_seen and self._no_browser_since is None:
            self._no_browser_since = now

        auto_shutdown = bool(self._launcher_id)
        launcher_lease_active = self._launcher_lease_active_locked(now)
        grace_elapsed = (
            self._no_browser_since is not None
            and now - self._no_browser_since >= self.close_grace_seconds
        )
        if self._shutdown_requested:
            launcher_state = "draining"
        elif launcher_lease_active:
            launcher_state = "active"
        elif self._launcher_id:
            launcher_state = "stale"
        else:
            launcher_state = "unmanaged"
        return {
            "runtimeProtocolVersion": self.protocol_version,
            "instanceId": self.instance_id,
            "workspaceFingerprint": self.workspace_fingerprint,
            "processId": self.process_id,
            "startedAt": self.started_at,
            "managedByLauncher": auto_shutdown,
            "launcherPid": self._launcher_pid if auto_shutdown else None,
            "launcherLeaseActive": launcher_lease_active,
            "launcherState": launcher_state,
            "shutdownRequested": self._shutdown_requested,
            "browserSeen": self._browser_seen,
            "activeBrowserSessions": len(active_ids),
            "activeOperations": self._active_operations,
            "shouldShutdown": bool(
                launcher_lease_active
                and self._browser_seen
                and not active_ids
                and grace_elapsed
                and self._active_operations == 0
            ),
            "closeGraceSeconds": self.close_grace_seconds,
        }


runtime_lifecycle = RuntimeLifecycle()
