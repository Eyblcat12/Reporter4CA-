from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from scripts.validate_clean_source import REQUIRED, validate_source_tree

ROOT = Path(__file__).resolve().parents[1]


class CleanSourceValidatorTests(unittest.TestCase):
    def test_minimal_clean_source_contract_is_valid(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for relative in REQUIRED:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("placeholder", encoding="utf-8")
            (root / ".env.example").write_text("AUTO_REPORT_TEMPLATE_PACKS=1\n", encoding="utf-8")
            (root / "apps/frontend/package-lock.json").write_text(
                json.dumps({"lockfileVersion": 3}), encoding="utf-8"
            )
            issues = validate_source_tree(root)

        self.assertEqual([], issues)

    def test_missing_required_and_runtime_artifacts_are_reported(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            for relative in REQUIRED:
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("placeholder", encoding="utf-8")
            (root / ".env.example").write_text("AUTO_REPORT_TEMPLATE_PACKS=1\n", encoding="utf-8")
            (root / "apps/frontend/package-lock.json").write_text(
                json.dumps({"lockfileVersion": 3}), encoding="utf-8"
            )
            (root / "apps/backend/data/report.db").parent.mkdir(parents=True)
            (root / "apps/backend/data/report.db").write_bytes(b"runtime")
            (root / ".env").write_text("secret", encoding="utf-8")
            issues = validate_source_tree(root)

        self.assertTrue(any("Runtime artifact" in issue for issue in issues))
        self.assertTrue(any("Local-only" in issue for issue in issues))


if __name__ == "__main__":
    unittest.main()
