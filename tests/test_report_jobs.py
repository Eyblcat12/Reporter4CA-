from __future__ import annotations

import threading
import time
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "backend"
sys.path.insert(0, str(BACKEND))

from core.report_jobs import JobCancelled, ReportJobManager
from core.config import unified_report_scheduler_enabled
from unittest.mock import patch
import os


def wait_for(predicate, timeout: float = 2.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("Timed out waiting for job state")


class ReportJobManagerTests(unittest.TestCase):
    def test_unified_scheduler_defaults_on_and_can_roll_back(self) -> None:
        with patch.dict(os.environ, {}, clear=True):
            self.assertTrue(unified_report_scheduler_enabled())
        with patch.dict(os.environ, {"AUTO_REPORT_UNIFIED_SCHEDULER": "0"}):
            self.assertFalse(unified_report_scheduler_enabled())

    def test_deduplicates_identical_active_requests(self) -> None:
        manager = ReportJobManager(max_workers=1, max_pending=2)
        release = threading.Event()

        def runner(job):
            release.wait(1)
            return {"filename": "one.docx"}

        first, first_duplicate = manager.submit({"rows": [1]}, runner)
        second, second_duplicate = manager.submit({"rows": [1]}, runner)
        self.assertFalse(first_duplicate)
        self.assertTrue(second_duplicate)
        self.assertEqual(first.id, second.id)
        release.set()
        wait_for(lambda: first.status == "completed")
        manager.shutdown()

    def test_enforces_one_running_and_two_queued_jobs(self) -> None:
        manager = ReportJobManager(max_workers=1, max_pending=2)
        release = threading.Event()

        def runner(job):
            release.wait(1)
            return {}

        manager.submit({"id": 1}, runner)
        manager.submit({"id": 2}, runner)
        manager.submit({"id": 3}, runner)
        with self.assertRaises(RuntimeError):
            manager.submit({"id": 4}, runner)
        release.set()
        manager.shutdown()

    def test_running_job_can_cancel_cooperatively(self) -> None:
        manager = ReportJobManager(max_workers=1, max_pending=2)
        entered = threading.Event()

        def runner(job):
            entered.set()
            while True:
                manager.check_cancelled(job)
                time.sleep(0.01)

        job, _ = manager.submit({"id": "cancel"}, runner)
        self.assertTrue(entered.wait(1))
        manager.cancel(job.id)
        wait_for(lambda: job.status == "cancelled")
        self.assertEqual(job.error_code, "CANCELLED")
        manager.shutdown()

    def test_runner_failure_returns_safe_public_error(self) -> None:
        manager = ReportJobManager()

        def runner(job):
            raise RuntimeError("private filesystem detail")

        job, _ = manager.submit({"id": "failure"}, runner)
        wait_for(lambda: job.status == "failed")
        public = job.public()
        self.assertEqual(public["errorCode"], "RuntimeError")
        self.assertNotIn("private filesystem detail", public["errorMessage"])
        manager.shutdown()

    def test_completed_job_exposes_report_integrity_summary(self) -> None:
        manager = ReportJobManager()
        job, _ = manager.submit(
            {"id": "integrity"},
            lambda _: {
                "filename": "verified.docx",
                "integrity": {"valid": True, "expectedAssets": 30, "verifiedAssets": 30},
            },
        )
        wait_for(lambda: job.status == "completed")
        self.assertEqual(job.public()["integrity"]["verifiedAssets"], 30)
        manager.shutdown()

    def test_long_session_prunes_old_terminal_jobs_from_memory(self) -> None:
        manager = ReportJobManager(max_workers=1, max_pending=2, max_retained=10)
        for index in range(25):
            job, _ = manager.submit({"id": index}, lambda _: {})
            wait_for(lambda: job.status == "completed")
        self.assertLessEqual(len(manager.list(limit=100)), 10)
        manager.shutdown()

    def test_kind_is_part_of_dedup_identity(self) -> None:
        manager = ReportJobManager(max_workers=1, max_pending=2)
        release = threading.Event()

        def runner(_job):
            release.wait(1)
            return {}

        report, _ = manager.submit({"same": True}, runner, kind="report")
        preview, deduplicated = manager.submit({"same": True}, runner, kind="preview")
        self.assertFalse(deduplicated)
        self.assertNotEqual(report.id, preview.id)
        release.set()
        manager.shutdown()

    def test_required_output_is_assigned_before_completed_becomes_visible(self) -> None:
        manager = ReportJobManager()
        job, _ = manager.submit(
            {"id": "missing-output"},
            lambda _job: {"filename": "missing.docx"},
            requires_output=True,
        )
        wait_for(lambda: job.status in {"completed", "failed"})
        self.assertEqual(job.status, "failed")
        self.assertFalse(job.public()["downloadReady"])
        self.assertIsInstance(job.failure, RuntimeError)
        manager.shutdown()

    def test_shutdown_cancels_running_and_queued_jobs_to_terminal_states(self) -> None:
        manager = ReportJobManager(max_workers=1, max_pending=1)

        def runner(job):
            while True:
                manager.check_cancelled(job)
                time.sleep(0.005)

        running, _ = manager.submit({"id": "running"}, runner)
        queued, _ = manager.submit({"id": "queued"}, runner)
        wait_for(lambda: running.status == "running")
        manager.shutdown(wait=True)
        self.assertEqual(running.status, "cancelled")
        self.assertEqual(queued.status, "cancelled")

    def test_report_and_preview_never_exceed_shared_worker_limit(self) -> None:
        manager = ReportJobManager(max_workers=1, max_pending=2)
        lock = threading.Lock()
        active = 0
        maximum = 0

        def runner(_job):
            nonlocal active, maximum
            with lock:
                active += 1
                maximum = max(maximum, active)
            time.sleep(0.02)
            with lock:
                active -= 1
            return {}

        jobs = [
            manager.submit({"id": 1}, runner, kind="report")[0],
            manager.submit({"id": 2}, runner, kind="preview")[0],
            manager.submit({"id": 3}, runner, kind="report")[0],
        ]
        for job in jobs:
            wait_for(lambda current=job: current.status == "completed")
        self.assertEqual(maximum, 1)
        manager.shutdown()


if __name__ == "__main__":
    unittest.main()
