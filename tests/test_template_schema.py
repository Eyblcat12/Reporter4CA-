from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "backend"))

from core.template_schema import COMPATIBILITY_VERSION, evaluate_template_compatibility


class TemplateSchemaTests(unittest.TestCase):
    def test_cover_template_is_compatible_with_explicit_warnings(self) -> None:
        result = evaluate_template_compatibility({
            "template_mode": "cover", "tokens_found": ["{{TITLE}}"],
            "unknown_tokens": [], "prototype_tables": [],
        }, "technical")
        self.assertEqual(result["status"], "compatible_with_warnings")
        self.assertEqual(result["version"], COMPATIBILITY_VERSION)
        self.assertTrue(any(item["code"] == "ENGINE_GENERATED_SECTIONS" for item in result["warnings"]))

    def test_full_template_missing_required_table_is_incompatible(self) -> None:
        result = evaluate_template_compatibility({
            "template_mode": "full", "tokens_found": ["{{TITLE}}"],
            "unknown_tokens": [], "prototype_tables": ["summary_server"],
        }, "summary")
        self.assertEqual(result["status"], "incompatible")
        self.assertEqual(result["errors"][0]["item"], "summary_client")

    def test_unknown_token_is_reported_with_guidance(self) -> None:
        result = evaluate_template_compatibility({
            "template_mode": "cover", "tokens_found": ["{{TITLE}}"],
            "unknown_tokens": ["{{CLIENT_SECRET}}"], "prototype_tables": [],
        }, "full")
        self.assertTrue(any(item["item"] == "{{CLIENT_SECRET}}" for item in result["warnings"]))
        self.assertTrue(result["guidance"])

    def test_empty_document_is_incompatible(self) -> None:
        result = evaluate_template_compatibility({
            "template_mode": "none", "tokens_found": [], "prototype_tables": [],
        }, "incident_response")
        self.assertEqual(result["status"], "incompatible")


if __name__ == "__main__":
    unittest.main()
