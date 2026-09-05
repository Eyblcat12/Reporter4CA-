from __future__ import annotations

import re
import unittest
from collections import Counter
from html.parser import HTMLParser
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PROTOTYPE = ROOT / "docs" / "template-studio-workbench-v2.html"


class _Parser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: list[str] = []
        self.external: list[str] = []
        self.forms = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if values.get("id"):
            self.ids.append(values["id"] or "")
        if tag in {"script", "img", "link", "iframe", "object", "embed"}:
            target = values.get("src") or values.get("href")
            if target:
                self.external.append(target)
        if tag == "form":
            self.forms += 1


def _luminance(value: str) -> float:
    channels = [int(value[index : index + 2], 16) / 255 for index in (1, 3, 5)]
    linear = [
        channel / 12.92 if channel <= 0.04045 else ((channel + 0.055) / 1.055) ** 2.4
        for channel in channels
    ]
    return 0.2126 * linear[0] + 0.7152 * linear[1] + 0.0722 * linear[2]


def _contrast(first: str, second: str) -> float:
    values = sorted((_luminance(first), _luminance(second)))
    return (values[1] + 0.05) / (values[0] + 0.05)


def _theme(html: str, selector: str) -> dict[str, str]:
    match = re.search(rf"{re.escape(selector)}\s*\{{(?P<body>.*?)\n\s*\}}", html, re.DOTALL)
    if not match:
        raise AssertionError(f"Missing theme: {selector}")
    return dict(re.findall(r"--([\w-]+):\s*(#[0-9a-fA-F]{6})", match.group("body")))


class TemplateStudioWorkbenchV2Tests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.html = PROTOTYPE.read_text(encoding="utf-8")

    def test_is_standalone_and_does_not_contact_the_live_tool(self) -> None:
        parser = _Parser()
        parser.feed(self.html)
        self.assertFalse(parser.external)
        self.assertEqual(0, parser.forms)
        self.assertFalse([item for item, count in Counter(parser.ids).items() if count > 1])
        for primitive in (
            "fetch(",
            "XMLHttpRequest",
            "WebSocket(",
            "EventSource(",
            "sendBeacon(",
            "window.open(",
        ):
            self.assertNotIn(primitive, self.html)

    def test_preserves_product_boundary_and_authoring_workflow(self) -> None:
        self.assertIn("Luồng mặc định được bảo vệ", self.html)
        for step in ("Phân tích", "Ánh xạ", "Rà soát", "Kiểm thử", "Phát hành"):
            self.assertIn(f">{step}<", self.html)
        self.assertNotIn("AUTO_REPORT_TEMPLATE_PACKS=1", self.html)
        self.assertNotIn("Legacy Renderer", self.html)

    def test_primary_detail_and_responsive_drawer_states_are_explicit(self) -> None:
        self.assertIn('class="work-area"', self.html)
        self.assertIn('id="inspector"', self.html)
        self.assertIn("@media (max-width: 1120px)", self.html)
        self.assertIn('id="scrim"', self.html)
        self.assertIn("trapOverlayFocus", self.html)
        self.assertIn("refs.primary.toggleAttribute('inert'", self.html)
        self.assertIn("event.key === 'Escape'", self.html)

    def test_required_optional_and_recovery_states_are_reviewable(self) -> None:
        self.assertIn("required: true", self.html)
        self.assertIn("required: false", self.html)
        for state in ("loading", "conflict", "save-error", "empty"):
            self.assertIn(f'value="{state}"', self.html)
        self.assertIn("Draft vẫn được giữ", self.html)
        self.assertIn('id="undoRemove"', self.html)
        self.assertIn('id="removeConfirm"', self.html)
        self.assertIn("workspace rev.", self.html)

    def test_accessibility_contract_is_present(self) -> None:
        for marker in (
            'role="progressbar"',
            'aria-live="polite"',
            'aria-current="step"',
            'aria-controls="inspector"',
            'aria-expanded="',
            ":focus-visible",
            "@media (prefers-reduced-motion: reduce)",
            '<html lang="vi"',
        ):
            self.assertIn(marker, self.html)
        self.assertIn("themeToggle.setAttribute('aria-label'", self.html)

    def test_core_theme_contrast_meets_wcag_aa(self) -> None:
        dark = _theme(self.html, ":root")
        light = _theme(self.html, "[data-theme='light']")
        for theme in (dark, light):
            self.assertGreaterEqual(_contrast(theme["text"], theme["surface"]), 4.5)
            self.assertGreaterEqual(_contrast(theme["muted"], theme["surface"]), 4.5)
            self.assertGreaterEqual(_contrast(theme["accent"], "#ffffff"), 4.5)
            self.assertGreaterEqual(_contrast(theme["accent-hover"], "#ffffff"), 4.5)
            self.assertGreaterEqual(_contrast(theme["border-strong"], theme["surface"]), 3.0)


if __name__ == "__main__":
    unittest.main()
