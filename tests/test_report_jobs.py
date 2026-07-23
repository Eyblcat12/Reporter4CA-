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


def wait_for(predicate, timeout: float = 2.0) -> None:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("Timed out waiting for job state")


class ReportJobManagerTests(unittest.TestCase):
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

    def test_long_session_prunes_old_terminal_jobs_from_memory(self) -> None:
        manager = ReportJobManager(max_workers=1, max_pending=2, max_retained=10)
        for index in range(25):
            job, _ = manager.submit({"id": index}, lambda _: {})
            wait_for(lambda: job.status == "completed")
        self.assertLessEqual(len(manager.list(limit=100)), 10)
        manager.shutdown()


if __name__ == "__main__":
    unittest.main()
