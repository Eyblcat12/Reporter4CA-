from __future__ import annotations

import json
import sys
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

from summarize_preview_benchmarks import summarize  # noqa: E402


class PreviewBenchmarkSummaryTests(unittest.TestCase):
    def test_ten_compatible_trials_publish_p95_and_pass_gate(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            for index in range(1, 11):
                payload = {
                    "schemaVersion": 1,
                    "fixture": "Tracking_2.csv",
                    "assets": 50,
                    "reportType": "full",
                    "requestedCacheState": "prewarmed",
                    "observedCacheState": "cache-warm/prepared-hit",
                    "targetPreviewMs": 10_000,
                    "previewMs": index * 100,
                    "productLatencyMs": index * 90,
                    "peakRssMiB": 700 + index,
                    "integrityValid": True,
                }
                (root / f"trial-{index:02d}.json").write_text(
                    json.dumps(payload), encoding="utf-8"
                )
            summary = summarize(root, required_trials=10)
            self.assertEqual(summary["sampleCount"], 10)
            self.assertEqual(summary["previewMs"]["p50"], 550.0)
            self.assertEqual(summary["previewMs"]["p95"], 955.0)
            self.assertTrue(summary["releaseGatePassed"])

    def test_mixed_cache_state_is_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            payload = {
                "schemaVersion": 1,
                "fixture": "Tracking_2.csv",
                "assets": 50,
                "reportType": "full",
                "requestedCacheState": "prewarmed",
                "observedCacheState": "cache-miss",
                "targetPreviewMs": 10_000,
                "previewMs": 100,
                "productLatencyMs": 90,
                "peakRssMiB": 700,
                "integrityValid": True,
            }
            (root / "trial-01.json").write_text(json.dumps(payload), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Unexpected cache state"):
                summarize(root, required_trials=1)


if __name__ == "__main__":
    unittest.main()
