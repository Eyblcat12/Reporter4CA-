from __future__ import annotations

import sys
import threading
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "backend"
sys.path.insert(0, str(BACKEND))

from api.routes import router  # noqa: E402
from core.runtime_lifecycle import (  # noqa: E402
    RUNTIME_PROTOCOL_VERSION,
    RuntimeLifecycle,
    workspace_fingerprint,
)


class RuntimeLifecycleTests(unittest.TestCase):
    def test_last_closed_browser_requests_shutdown_after_grace(self) -> None:
        lifecycle = RuntimeLifecycle(close_grace_seconds=0)
        lifecycle.attach_launcher("launcher-123", 1234)
        lifecycle.open_browser("browser-123")

        status = lifecycle.close_browser("browser-123")

        self.assertEqual(status["activeBrowserSessions"], 0)
        self.assertTrue(status["shouldShutdown"])

    def test_one_open_tab_keeps_multi_tab_session_alive(self) -> None:
        lifecycle = RuntimeLifecycle(close_grace_seconds=0)
        lifecycle.attach_launcher("launcher-123", 1234)
        lifecycle.open_browser("browser-one")
        lifecycle.open_browser("browser-two")

        status = lifecycle.close_browser("browser-one")

        self.assertEqual(status["activeBrowserSessions"], 1)
        self.assertFalse(status["shouldShutdown"])

    def test_reload_can_reopen_during_shutdown_grace(self) -> None:
        lifecycle = RuntimeLifecycle(close_grace_seconds=5)
        with patch("core.runtime_lifecycle.time.monotonic", return_value=100):
            lifecycle.attach_launcher("launcher-123", 1234)
            lifecycle.open_browser("old-browser")
            lifecycle.close_browser("old-browser")
        with patch("core.runtime_lifecycle.time.monotonic", return_value=102):
            status = lifecycle.open_browser("new-browser")

        self.assertEqual(status["activeBrowserSessions"], 1)
        self.assertFalse(status["shouldShutdown"])

    def test_launcher_expiry_is_detected_without_browser_activity(self) -> None:
        lifecycle = RuntimeLifecycle(launcher_ttl_seconds=8)
        with patch("core.runtime_lifecycle.time.monotonic", return_value=100):
            lifecycle.attach_launcher("launcher-123", 1234)
        with patch("core.runtime_lifecycle.time.monotonic", return_value=109):
            self.assertTrue(lifecycle.launcher_expired())

    def test_active_report_operation_cannot_be_killed_by_watchdog(self) -> None:
        lifecycle = RuntimeLifecycle(launcher_ttl_seconds=8)
        with patch("core.runtime_lifecycle.time.monotonic", return_value=100):
            lifecycle.attach_launcher("launcher-123", 1234)
        with lifecycle.operation():
            with patch("core.runtime_lifecycle.time.monotonic", return_value=500):
                self.assertFalse(lifecycle.launcher_expired())

    def test_completed_operation_restores_launcher_heartbeat_grace(self) -> None:
        lifecycle = RuntimeLifecycle(launcher_ttl_seconds=8)
        with patch("core.runtime_lifecycle.time.monotonic", return_value=100):
            lifecycle.attach_launcher("launcher-123", 1234)
        with patch("core.runtime_lifecycle.time.monotonic", return_value=500):
            with lifecycle.operation():
                pass
            self.assertFalse(lifecycle.launcher_expired())
        with patch("core.runtime_lifecycle.time.monotonic", return_value=509):
            self.assertTrue(lifecycle.launcher_expired())

    def test_same_launcher_attach_is_idempotent_and_preserves_browser_sessions(self) -> None:
        lifecycle = RuntimeLifecycle()
        lifecycle.attach_launcher("launcher-123", 1234)
        lifecycle.open_browser("browser-123")

        status = lifecycle.attach_launcher("launcher-123", 1234)

        self.assertEqual(status["launcherPid"], 1234)
        self.assertTrue(status["browserSeen"])
        self.assertEqual(status["activeBrowserSessions"], 1)

    def test_active_launcher_lease_rejects_a_different_launcher(self) -> None:
        lifecycle = RuntimeLifecycle(launcher_ttl_seconds=8)
        with patch("core.runtime_lifecycle.time.monotonic", return_value=100):
            lifecycle.attach_launcher("launcher-one", 1111)
            lifecycle.open_browser("browser-one")

        with patch("core.runtime_lifecycle.time.monotonic", return_value=101):
            with self.assertRaises(ValueError):
                lifecycle.attach_launcher("launcher-two", 2222)
            status = lifecycle.status()

        self.assertEqual(status["launcherPid"], 1111)
        self.assertEqual(status["activeBrowserSessions"], 1)
        with patch("core.runtime_lifecycle.time.monotonic", return_value=102):
            lifecycle.launcher_heartbeat("launcher-one")
            with self.assertRaises(ValueError):
                lifecycle.launcher_heartbeat("launcher-two")

    def test_expired_launcher_lease_can_be_recovered_by_a_new_launcher(self) -> None:
        lifecycle = RuntimeLifecycle(launcher_ttl_seconds=8)
        with patch("core.runtime_lifecycle.time.monotonic", return_value=100):
            lifecycle.attach_launcher("launcher-one", 1111)

        with patch("core.runtime_lifecycle.time.monotonic", return_value=109):
            status = lifecycle.attach_launcher("launcher-two", 2222)

        self.assertTrue(status["managedByLauncher"])
        self.assertEqual(status["launcherPid"], 2222)
        with patch("core.runtime_lifecycle.time.monotonic", return_value=110):
            with self.assertRaises(ValueError):
                lifecycle.launcher_heartbeat("launcher-one")
            self.assertEqual(
                lifecycle.launcher_heartbeat("launcher-two")["launcherPid"],
                2222,
            )

    def test_owner_detach_is_terminal_and_rejects_late_heartbeat(self) -> None:
        lifecycle = RuntimeLifecycle()
        lifecycle.attach_launcher("launcher-123", 1234)

        self.assertTrue(lifecycle.detach_launcher("launcher-123"))
        with self.assertRaises(ValueError):
            lifecycle.launcher_heartbeat("launcher-123")

    def test_foreign_detach_does_not_change_the_active_owner(self) -> None:
        lifecycle = RuntimeLifecycle()
        lifecycle.attach_launcher("launcher-one", 1111)

        self.assertFalse(lifecycle.detach_launcher("launcher-two"))
        status = lifecycle.launcher_heartbeat("launcher-one")

        self.assertTrue(status["managedByLauncher"])
        self.assertEqual(status["launcherPid"], 1111)

    def test_active_operation_suppresses_browser_driven_shutdown(self) -> None:
        lifecycle = RuntimeLifecycle(close_grace_seconds=0)
        lifecycle.attach_launcher("launcher-123", 1234)
        lifecycle.open_browser("browser-123")

        with lifecycle.operation():
            status = lifecycle.close_browser("browser-123")
            self.assertEqual(status["activeOperations"], 1)
            self.assertFalse(status["shouldShutdown"])

        self.assertTrue(lifecycle.status()["shouldShutdown"])

    def test_simultaneous_attach_has_exactly_one_owner(self) -> None:
        lifecycle = RuntimeLifecycle()
        barrier = threading.Barrier(2)
        result_lock = threading.Lock()
        accepted: list[tuple[str, int]] = []
        rejected: list[str] = []

        def attach(launcher_id: str, pid: int) -> None:
            barrier.wait()
            try:
                lifecycle.attach_launcher(launcher_id, pid)
            except ValueError:
                with result_lock:
                    rejected.append(launcher_id)
            else:
                with result_lock:
                    accepted.append((launcher_id, pid))

        threads = [
            threading.Thread(target=attach, args=("launcher-one", 1111)),
            threading.Thread(target=attach, args=("launcher-two", 2222)),
        ]
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join(timeout=2)

        self.assertTrue(all(not thread.is_alive() for thread in threads))
        self.assertEqual(len(accepted), 1)
        self.assertEqual(len(rejected), 1)
        winner_id, winner_pid = accepted[0]
        self.assertEqual(lifecycle.status()["launcherPid"], winner_pid)
        self.assertEqual(lifecycle.launcher_heartbeat(winner_id)["launcherPid"], winner_pid)

    def test_runtime_identity_fences_a_different_instance_or_workspace(self) -> None:
        lifecycle = RuntimeLifecycle(
            workspace_root=ROOT,
            instance_id="instance-1234567890",
            process_id=4321,
            started_at="2026-07-30T00:00:00+00:00",
        )
        status = lifecycle.status()

        self.assertEqual(status["runtimeProtocolVersion"], RUNTIME_PROTOCOL_VERSION)
        self.assertEqual(status["instanceId"], "instance-1234567890")
        self.assertEqual(status["workspaceFingerprint"], workspace_fingerprint(ROOT))
        self.assertEqual(status["processId"], 4321)
        with self.assertRaises(ValueError):
            lifecycle.attach_launcher(
                "launcher-123",
                1234,
                instance_id="different-instance",
                workspace_id=status["workspaceFingerprint"],
            )
        with self.assertRaises(ValueError):
            lifecycle.attach_launcher(
                "launcher-123",
                1234,
                instance_id=status["instanceId"],
                workspace_id="different-workspace",
            )


class RuntimeLifecycleApiTests(unittest.TestCase):
    def setUp(self) -> None:
        self.lifecycle = RuntimeLifecycle(
            workspace_root=ROOT,
            instance_id="api-instance-1234567890",
            process_id=9876,
        )
        self.patch = patch("api.routes.runtime_lifecycle", self.lifecycle)
        self.patch.start()
        app = FastAPI()
        app.include_router(router)
        self.client = TestClient(app)

    def tearDown(self) -> None:
        self.client.close()
        self.patch.stop()

    def payload(self, launcher_id: str, pid: int) -> dict:
        return {
            "launcherId": launcher_id,
            "pid": pid,
            "instanceId": self.lifecycle.instance_id,
            "workspaceFingerprint": self.lifecycle.workspace_fingerprint,
        }

    def test_runtime_status_publishes_versioned_instance_identity(self) -> None:
        response = self.client.get("/api/runtime/status")

        self.assertEqual(response.status_code, 200)
        status = response.json()
        self.assertEqual(status["runtimeProtocolVersion"], RUNTIME_PROTOCOL_VERSION)
        self.assertEqual(status["instanceId"], self.lifecycle.instance_id)
        self.assertEqual(
            status["workspaceFingerprint"],
            self.lifecycle.workspace_fingerprint,
        )

    def test_second_active_launcher_receives_conflict_without_stealing_lease(self) -> None:
        first = self.client.post(
            "/api/runtime/launcher/attach",
            json=self.payload("launcher-one", 1111),
        )
        second = self.client.post(
            "/api/runtime/launcher/attach",
            json=self.payload("launcher-two", 2222),
        )

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 409)
        self.assertEqual(self.lifecycle.status()["launcherPid"], 1111)


if __name__ == "__main__":
    unittest.main()
