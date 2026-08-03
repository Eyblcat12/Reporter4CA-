from __future__ import annotations

import sys
import json
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from unittest.mock import patch

from soak_report_jobs import atomic_write_json, current_rss_mb, evaluate_thresholds, percentile, reconcile_stale_statuses, run_soak


class SoakHarnessTests(unittest.TestCase):
    def test_percentile_interpolates_duration_samples(self) -> None:
        self.assertEqual(percentile([1, 2, 3, 4], 0.5), 2.5)

    def test_thresholds_report_timeout_failure_and_memory_growth(self) -> None:
        failures = evaluate_thresholds({
            "completed": 1, "timeouts": 1, "unexpectedFailures": 2,
            "dedupMismatches": 1, "heapGrowthMb": 200.0,
        }, 128.0)
        self.assertEqual(len(failures), 4)

    def test_healthy_metrics_pass(self) -> None:
        self.assertEqual(evaluate_thresholds({
            "completed": 3, "timeouts": 0, "unexpectedFailures": 0,
            "dedupMismatches": 0, "heapGrowthMb": 12.0,
        }, 128.0), [])

    def test_atomic_json_write_never_leaves_partial_payload(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "state.json"
            atomic_write_json(path, {"status": "running", "iteration": 2})
            self.assertEqual(json.loads(path.read_text(encoding="utf-8"))["iteration"], 2)
            self.assertFalse(path.with_suffix(".json.tmp").exists())

    def test_orphaned_running_status_is_marked_interrupted(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "old.status.json"
            path.write_text(json.dumps({"status": "running", "pid": 99999999}), encoding="utf-8")
            with patch("soak_report_jobs.process_is_alive", return_value=False):
                reconciled = reconcile_stale_statuses(Path(directory))
            state = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(reconciled, [path])
            self.assertEqual(state["status"], "interrupted")
            self.assertIn("finishedAt", state)

    def test_process_rss_is_available_for_native_memory_monitoring(self) -> None:
        self.assertGreater(current_rss_mb(), 0)

    def test_planned_failure_and_cancel_do_not_create_dedup_races(self) -> None:
        class FakeDocument:
            def save(self, output) -> None:
                output.write(b"PK" + b"x" * 1200)

        config = {
            "profile": "test", "duration_minutes": 1, "rows": 1,
            "max_jobs": 11, "job_timeout": 5, "memory_growth_mb": 128,
        }
        with patch("soak_report_jobs.generate_report", return_value=FakeDocument()):
            metrics = run_soak(config)
        self.assertEqual(metrics["submitted"], 11)
        self.assertEqual(metrics["deduplicated"], 11)
        self.assertEqual(metrics["dedupMismatches"], 0)
        self.assertEqual(metrics["unexpectedFailures"], 0)
        self.assertEqual(metrics["failed"], 1)
        self.assertEqual(metrics["cancelled"], 1)


if __name__ == "__main__":
    unittest.main()
