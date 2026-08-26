from __future__ import annotations

import unittest
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / "docs" / "template-studio-prototype.html"
ENTERPRISE_PROTOTYPE = ROOT / "docs" / "template-studio-enterprise.html"


class _PrototypeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.external_assets: list[str] = []
        self.forms = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if values.get("id"):
            self.ids.append(values["id"] or "")
        if tag in {"script", "img", "link"}:
            target = values.get("src") or values.get("href")
            if target:
                self.external_assets.append(target)
        if tag == "form":
            self.forms += 1


class TemplateStudioPrototypeTests(unittest.TestCase):
    def test_prototype_is_standalone_and_cannot_call_the_live_tool(self) -> None:
        for prototype in (PROTOTYPE, ENTERPRISE_PROTOTYPE):
            with self.subTest(prototype=prototype.name):
                html = prototype.read_text(encoding="utf-8")
                parser = _PrototypeParser()
                parser.feed(html)

                duplicates = [item for item, count in Counter(parser.ids).items() if count > 1]
                self.assertFalse(duplicates)
                self.assertFalse(parser.external_assets)
                self.assertEqual(parser.forms, 0)
                self.assertNotIn("fetch(", html)
                self.assertNotIn("XMLHttpRequest", html)
                self.assertIn("Legacy", html)
                self.assertIn("EXPERIMENTAL", html.upper())

    def test_prototype_exposes_mapping_and_publication_gate_states(self) -> None:
        html = PROTOTYPE.read_text(encoding="utf-8")

        self.assertIn('data-state="mapping"', html)
        self.assertIn('data-state="ready"', html)
        self.assertIn('id="coverageValue"', html)
        self.assertIn('id="testRender" disabled', html)
        self.assertIn('id="publish" disabled', html)
        self.assertIn("Manual approval required", html)

    def test_enterprise_prototype_exposes_governance_and_theme_states(self) -> None:
        html = ENTERPRISE_PROTOTYPE.read_text(encoding="utf-8")

        self.assertIn("Legacy templates protected", html)
        self.assertIn("Template Administrator", html)
        self.assertIn("Template checksum", html)
        self.assertIn(">Evidence<", html)
        self.assertIn(">Audit<", html)
        self.assertIn('data-state="draft"', html)
        self.assertIn('data-state="validated"', html)
        self.assertIn('data-state="approved"', html)
        self.assertIn('id="themeToggle"', html)
        self.assertIn('id="publish" disabled', html)
        self.assertNotIn("Legacy workflow protection is active", html)


if __name__ == "__main__":
    unittest.main()
