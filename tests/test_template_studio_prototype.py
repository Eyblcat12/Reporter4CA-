from __future__ import annotations

import re
import unittest
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / "docs" / "template-studio-prototype.html"
ENTERPRISE_PROTOTYPE = ROOT / "docs" / "template-studio-enterprise.html"
WORKBENCH_PROTOTYPE = ROOT / "docs" / "template-studio-workbench.html"


class _PrototypeParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.external_assets: list[str] = []
        self.embedded_content: list[str] = []
        self.navigation_targets: list[str] = []
        self.forms = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if values.get("id"):
            self.ids.append(values["id"] or "")
        if tag in {"script", "img", "link"}:
            target = values.get("src") or values.get("href")
            if target:
                self.external_assets.append(target)
        if tag in {"base", "embed", "iframe", "object"}:
            self.embedded_content.append(tag)
        if tag == "a" and values.get("href") and not (values["href"] or "").startswith("#"):
            self.navigation_targets.append(values["href"] or "")
        if tag == "meta" and (values.get("http-equiv") or "").lower() == "refresh":
            self.navigation_targets.append(values.get("content") or "meta-refresh")
        if tag == "form":
            self.forms += 1


def _assert_isolated(test: unittest.TestCase, html: str, parser: _PrototypeParser) -> None:
    test.assertFalse(parser.external_assets)
    test.assertFalse(parser.embedded_content)
    test.assertFalse(parser.navigation_targets)
    test.assertEqual(parser.forms, 0)
    for network_primitive in (
        "fetch(",
        "XMLHttpRequest",
        "WebSocket(",
        "EventSource(",
        "sendBeacon(",
        "window.open(",
    ):
        test.assertNotIn(network_primitive, html)


def _relative_luminance(hex_color: str) -> float:
    channels = [int(hex_color[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
        for value in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast_ratio(first: str, second: str) -> float:
    first_luminance = _relative_luminance(first)
    second_luminance = _relative_luminance(second)
    lighter = max(first_luminance, second_luminance)
    darker = min(first_luminance, second_luminance)
    return (lighter + 0.05) / (darker + 0.05)


def _theme_hex_variables(html: str, selector: str) -> dict[str, str]:
    match = re.search(rf"{re.escape(selector)}\s*\{{(?P<body>.*?)\n\s*\}}", html, re.DOTALL)
    if not match:
        raise AssertionError(f"Missing CSS theme block: {selector}")
    return dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})", match.group("body")))


class TemplateStudioPrototypeTests(unittest.TestCase):
    def test_prototype_is_standalone_and_cannot_call_the_live_tool(self) -> None:
        for prototype in (PROTOTYPE, ENTERPRISE_PROTOTYPE):
            with self.subTest(prototype=prototype.name):
                html = prototype.read_text(encoding="utf-8")
                parser = _PrototypeParser()
                parser.feed(html)

                duplicates = [item for item, count in Counter(parser.ids).items() if count > 1]
                self.assertFalse(duplicates)
                _assert_isolated(self, html, parser)
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

    def test_workbench_is_isolated_and_exposes_focused_mapping_interactions(self) -> None:
        html = WORKBENCH_PROTOTYPE.read_text(encoding="utf-8")
        parser = _PrototypeParser()
        parser.feed(html)

        duplicates = [item for item, count in Counter(parser.ids).items() if count > 1]
        self.assertFalse(duplicates)
        _assert_isolated(self, html, parser)
        for step in ("Analyze", "Map", "Review", "Test", "Publish"):
            self.assertIn(f"<strong>{step}</strong>", html)
        self.assertIn('id="mappingRows"', html)
        self.assertIn('id="drawer"', html)
        self.assertIn('data-filter="mapped"', html)
        self.assertIn('data-filter="missing"', html)
        self.assertIn('id="themeToggle"', html)
        self.assertIn("Legacy flow protected", html)
        self.assertIn('role="progressbar"', html)
        self.assertIn('aria-live="polite"', html)
        self.assertIn('class="row-select"', html)
        self.assertIn('aria-controls="drawer"', html)
        self.assertIn('aria-pressed="true"', html)
        self.assertIn("@media (prefers-reduced-motion: reduce)", html)
        self.assertIn('<html lang="en" data-theme="dark">', html)
        self.assertIn('aria-current="step"', html)
        self.assertIn('id="anchorSelect"', html)
        self.assertIn('id="validationPanel"', html)
        self.assertIn('id="approveMapping"', html)
        self.assertIn('id="removeMapping"', html)
        self.assertIn("event.key === 'Escape'", html)
        self.assertIn("requestedState === 'conflict'", html)
        self.assertIn("requestedState === 'load-error'", html)
        self.assertIn("requestedState === 'save-timeout'", html)
        self.assertIn("@media (max-width: 760px)", html)
        self.assertNotIn("min-width: 1120px", html)

    def test_workbench_mapping_states_are_truthful_and_revisioned(self) -> None:
        html = WORKBENCH_PROTOTYPE.read_text(encoding="utf-8")

        self.assertIn("row.status !== 'mapped'", html)
        self.assertIn("title.textContent = 'Mapping required'", html)
        self.assertIn("title.textContent = 'Ready for approval'", html)
        self.assertIn("title.textContent = 'Mapping is structurally valid'", html)
        self.assertIn("row.status = 'mapped'", html)
        self.assertIn("row.status = 'missing'", html)
        self.assertIn("revision += 1", html)
        self.assertIn("setSavingState('Saving…')", html)
        self.assertIn("setSavingState('Unsaved change')", html)
        self.assertIn("filter === 'all' || row.status === filter", html)

    def test_workbench_theme_tokens_meet_core_contrast_contract(self) -> None:
        html = WORKBENCH_PROTOTYPE.read_text(encoding="utf-8")
        dark = _theme_hex_variables(html, ":root")
        light = _theme_hex_variables(html, "[data-theme='light']")

        self.assertGreaterEqual(_contrast_ratio(dark["faint"], dark["surface"]), 4.5)
        self.assertGreaterEqual(_contrast_ratio(light["faint"], light["surface"]), 4.5)
        self.assertGreaterEqual(_contrast_ratio(dark["accent-solid"], "#ffffff"), 4.5)
        self.assertGreaterEqual(_contrast_ratio(light["accent-solid"], "#ffffff"), 4.5)
        self.assertGreaterEqual(_contrast_ratio(dark["border-strong"], dark["surface"]), 3.0)
        self.assertGreaterEqual(_contrast_ratio(light["border-strong"], light["surface"]), 3.0)


if __name__ == "__main__":
    unittest.main()
