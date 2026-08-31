from __future__ import annotations

import hashlib
import json
import tempfile
import unittest
from pathlib import Path

from apps.backend.core.template_pack import inspect_template_pack
from scripts.fuzz_template_packs import apply_recipe, build_recipe, run_fuzz
from tests.test_template_packs import _pack_bytes


class TemplatePackFuzzHarnessTests(unittest.TestCase):
    def test_recipes_are_deterministic_and_replayable(self) -> None:
        source = _pack_bytes()
        for case in range(21):
            first = build_recipe(len(source), 12345, case)
            second = build_recipe(len(source), 12345, case)
            self.assertEqual(first, second)
            self.assertEqual(apply_recipe(source, first), apply_recipe(source, second))

    def test_bounded_fuzz_run_reports_only_aggregate_metadata(self) -> None:
        source = _pack_bytes()
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "result.json"
            result = run_fuzz(
                source,
                iterations=64,
                duration_seconds=0,
                seed=0xC0DEC0DE,
                output=output,
                checkpoint_every=7,
            )
            stored = json.loads(output.read_text(encoding="utf-8"))

        self.assertEqual("passed", result["outcome"])
        self.assertEqual(64, result["completedIterations"])
        self.assertEqual(64, result["acceptedMutations"] + result["controlledRejections"])
        self.assertEqual(hashlib.sha256(source).hexdigest(), result["sourceSha256"])
        self.assertEqual(result, stored)
        self.assertFalse(result["containsSourceBytes"])
        self.assertNotIn(source[:32].hex(), json.dumps(result))

    def test_unexpected_exception_stops_and_records_replay_recipe_without_source(self) -> None:
        source = _pack_bytes()
        calls = 0

        def broken_inspector(data: bytes, *, require_publishable: bool) -> object:
            nonlocal calls
            calls += 1
            if calls == 1:
                return inspect_template_pack(data, require_publishable=require_publishable)
            raise MemoryError("sensitive source detail")

        with tempfile.TemporaryDirectory() as temporary:
            result = run_fuzz(
                source,
                iterations=100,
                duration_seconds=0,
                seed=7,
                output=Path(temporary) / "failed.json",
                inspector=broken_inspector,
            )

        self.assertEqual("failed", result["outcome"])
        self.assertEqual(1, result["completedIterations"])
        self.assertEqual("MemoryError", result["failure"]["exceptionType"])
        self.assertNotIn("sensitive", json.dumps(result))
        recipe = build_recipe(len(source), 7, result["failure"]["case"])
        self.assertEqual(apply_recipe(source, recipe), apply_recipe(source, recipe))

    def test_invalid_limits_and_invalid_seed_pack_are_rejected(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "result.json"
            with self.assertRaisesRegex(ValueError, "iterations"):
                run_fuzz(b"PK", iterations=0, duration_seconds=0, seed=1, output=output)
            with self.assertRaisesRegex(ValueError, "source size"):
                run_fuzz(b"P", iterations=1, duration_seconds=0, seed=1, output=output)
            with self.assertRaises(Exception):
                run_fuzz(b"PK", iterations=1, duration_seconds=0, seed=1, output=output)


if __name__ == "__main__":
    unittest.main()
