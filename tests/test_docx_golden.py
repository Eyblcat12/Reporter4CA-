from __future__ import annotations

import hashlib
import json
import os
import re
import sys
import tempfile
import unittest
import zipfile
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "backend"
GOLDEN_ROOT = ROOT / "tests" / "golden" / "docx-v1"
sys.path.insert(0, str(BACKEND))

from core.report_generator import ReportType, generate_report
from tests.docx_golden_report import structural_diff, write_diff_reports


REPORT_TYPES = [item.value for item in ReportType]
TOKEN_PATTERN = re.compile(r"\{\{[^{}]+\}\}")
GOLDEN_REPORT_DIR = Path(
    os.getenv("GOLDEN_DOCX_REPORT_DIR", str(ROOT / "artifacts" / "golden-docx"))
)


def fixture_data() -> dict:
    return {
        "servers": [{
            "hostname": "SRV-GOLDEN-01", "ip": "10.10.0.10", "os": "Windows Server 2022",
            "result": "Malware detected", "notes": "SHA256 evidence linked to T1055",
        }],
        "clients": [{
            "hostname": "WS-GOLDEN-01", "ip": "10.10.0.20", "os": "Windows 11",
            "result": "No finding", "notes": "Validated by endpoint telemetry",
        }],
        "metadata": {
            "incidentName": "Golden incident", "severity": "high",
            "timeline": [{"time": "2026-07-20T10:00:00Z", "event": "Detection", "evidence": "EDR-001"}],
        },
    }


def document_snapshot(document) -> dict:
    paragraphs = [paragraph.text.strip() for paragraph in document.paragraphs if paragraph.text.strip()]
    headings = [
        {"style": paragraph.style.name, "text": paragraph.text.strip()}
        for paragraph in document.paragraphs
        if paragraph.text.strip() and paragraph.style and paragraph.style.name.startswith("Heading")
    ]
    tables = []
    for table in document.tables:
        header = [cell.text.strip() for cell in table.rows[0].cells] if table.rows else []
        tables.append({"rows": len(table.rows), "columns": len(header), "header": header})
    numbered = sum(
        1 for paragraph in document.paragraphs
        if paragraph._p.pPr is not None and paragraph._p.pPr.numPr is not None
    )

    with tempfile.NamedTemporaryFile(suffix=".docx", delete=False) as temporary:
        output_path = Path(temporary.name)
    try:
        document.save(output_path)
        with zipfile.ZipFile(output_path) as archive:
            relationship_types = Counter()
            media = []
            for name in archive.namelist():
                if name.startswith("word/media/") and not name.endswith("/"):
                    content = archive.read(name)
                    media.append({
                        "name": Path(name).name, "size": len(content),
                        "sha256": hashlib.sha256(content).hexdigest(),
                    })
                if not name.endswith(".rels"):
                    continue
                content = archive.read(name).decode("utf-8", errors="ignore")
                for rel_type in re.findall(r'Type="([^"]+)"', content):
                    relationship_types[rel_type.rsplit("/", 1)[-1]] += 1
    finally:
        output_path.unlink(missing_ok=True)

    return {
        "paragraphCount": len(paragraphs),
        "paragraphDigest": hashlib.sha256("\n".join(paragraphs).encode("utf-8")).hexdigest(),
        "headings": headings,
        "tables": tables,
        "numberedParagraphs": numbered,
        "remainingTokens": sorted(set(TOKEN_PATTERN.findall("\n".join(paragraphs)))),
        "sectionCount": len(document.sections),
        "relationships": dict(sorted(relationship_types.items())),
        "media": sorted(media, key=lambda item: item["name"]),
    }


def readable_diff(expected: object, actual: object, path: str = "root") -> list[str]:
    markers = {"added": "+", "removed": "-", "changed": "~"}
    return [
        f"{markers[item['change']]} {item['path']}: "
        f"expected {item.get('expected')!r}; actual {item.get('actual')!r}"
        for item in structural_diff(expected, actual, path)
    ]


class DocxGoldenTests(unittest.TestCase):
    def test_all_report_types_match_structural_golden_files(self) -> None:
        update = os.getenv("UPDATE_GOLDEN_DOCX") == "1"
        regressions: list[dict[str, object]] = []
        if update:
            GOLDEN_ROOT.mkdir(parents=True, exist_ok=True)

        for report_type in REPORT_TYPES:
            with self.subTest(report_type=report_type):
                document = generate_report(
                    fixture_data(), title="Golden Report", organization="Reporter Team",
                    assessment_date="2026-07-20", report_type=report_type,
                )
                actual = document_snapshot(document)
                golden_path = GOLDEN_ROOT / f"{report_type}.json"
                if update:
                    golden_path.write_text(
                        json.dumps(actual, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
                    )
                self.assertTrue(golden_path.exists(), f"Missing golden file: {golden_path}")
                expected = json.loads(golden_path.read_text(encoding="utf-8"))
                structured = structural_diff(expected, actual)
                differences = readable_diff(expected, actual)
                if differences:
                    regressions.append({"reportType": report_type, "differences": structured})

        if regressions:
            json_path, html_path = write_diff_reports(regressions, GOLDEN_REPORT_DIR)
            self.fail(
                "DOCX structural regression detected:\n"
                + "\n".join(
                    f"- {item['reportType']}: {len(item['differences'])} differences"
                    for item in regressions
                )
                + f"\nJSON report: {json_path}\nHTML report: {html_path}"
                + "\nUse UPDATE_GOLDEN_DOCX=1 only after reviewing this diff."
            )

    def test_structured_diff_report_is_granular_and_readable(self) -> None:
        expected = {
            "headings": [{"style": "Heading 1", "text": "Overview"}],
            "tables": [{"rows": 2, "columns": 3}],
            "remainingTokens": [],
            "media": [{"name": "chart.png", "size": 100}],
        }
        actual = {
            "headings": [{"style": "Heading 1", "text": "Summary"}],
            "tables": [{"rows": 3, "columns": 3}],
            "remainingTokens": ["{{UNRESOLVED}}"],
            "media": [],
        }
        differences = structural_diff(expected, actual)
        self.assertEqual(
            {item["category"] for item in differences},
            {"Headings", "Tables", "Tokens", "Media"},
        )
        self.assertIn("root.headings[0].text", {item["path"] for item in differences})
        self.assertIn("root.remainingTokens[0]", {item["path"] for item in differences})

        with tempfile.TemporaryDirectory() as directory:
            json_path, html_path = write_diff_reports(
                [{"reportType": "technical", "differences": differences}], Path(directory)
            )
            report = json.loads(json_path.read_text(encoding="utf-8"))
            rendered = html_path.read_text(encoding="utf-8")
            self.assertEqual(report["status"], "failed")
            self.assertEqual(report["summary"]["byCategory"]["Headings"], 1)
            self.assertIn("Golden DOCX structural diff", rendered)
            self.assertIn("root.headings[0].text", rendered)


if __name__ == "__main__":
    unittest.main()
