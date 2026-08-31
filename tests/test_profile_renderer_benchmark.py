from __future__ import annotations

import argparse
import tempfile
import unittest
from pathlib import Path

from scripts.benchmark_profile_renderer import (
    benchmark,
    run_isolated_trial,
    synthetic_pack,
    synthetic_payload,
    synthetic_template,
)


class ProfileRendererBenchmarkTests(unittest.TestCase):
    def test_synthetic_fixture_is_deterministic_in_shape_and_publishable(self) -> None:
        payload = synthetic_payload(50, "full")
        self.assertEqual(20, len(payload["servers"]))
        self.assertEqual(30, len(payload["clients"]))
        self.assertEqual(50, len(payload["servers"]) + len(payload["clients"]))
        template, anchors = synthetic_template("full")
        with tempfile.TemporaryDirectory() as temporary:
            pack = synthetic_pack(Path(temporary), "full", template, anchors)
        self.assertTrue(pack.startswith(b"PK"))

    def test_small_benchmark_runs_in_isolated_worker_and_cleans_docx(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "benchmark.json"
            report, actual = benchmark(
                argparse.Namespace(
                    asset_counts=[5],
                    report_type="full",
                    timeout_seconds=60,
                    memory_limit_mib=1024,
                    allow_large=False,
                    output=output,
                )
            )
            hidden_docx = list(Path(temporary).glob("*.docx"))

        self.assertEqual(output.resolve(), actual)
        self.assertTrue(report["completed"])
        self.assertEqual("passed", report["trials"][0]["status"])
        self.assertEqual(5, report["trials"][0]["assetCount"])
        self.assertFalse(report["trials"][0]["legacyRendererUsed"])
        self.assertEqual([], hidden_docx)

    def test_large_counts_require_explicit_opt_in(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            with self.assertRaisesRegex(ValueError, "allow-large"):
                benchmark(
                    argparse.Namespace(
                        asset_counts=[10_000],
                        report_type="full",
                        timeout_seconds=60,
                        memory_limit_mib=1024,
                        allow_large=False,
                        output=Path(temporary) / "benchmark.json",
                    )
                )

    def test_worker_memory_watchdog_returns_controlled_result(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            result = run_isolated_trial(
                asset_count=50,
                report_type="full",
                timeout_seconds=60,
                memory_limit_mib=1,
                run_dir=Path(temporary),
            )

        self.assertEqual("resource_limited", result["status"])
        self.assertEqual("memory_limit", result["terminationReason"])
        self.assertGreater(result["observedPeakRssMiB"], 1)


if __name__ == "__main__":
    unittest.main()
