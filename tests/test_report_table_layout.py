"""Layout regressions found by rendering generated reports in Microsoft Word.

Word wrapped the bold "STT" header to "ST"/"T" in every 12 mm STT column, and
the body footer counted the table-of-contents pages ("Trang 23 / 24" on the
last of 23 body pages). These tests pin the OOXML that fixes both. Rendering
itself still needs Word: structure alone cannot prove a column no longer wraps.
All data is synthetic.
"""

from __future__ import annotations

import io
import sys
import unittest
import zipfile
from pathlib import Path

from docx.oxml.ns import qn
from docx.shared import Mm

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "backend"
TEMPLATES = BACKEND / "templates"
sys.path.insert(0, str(BACKEND))

from core.report_generator import (  # noqa: E402
    DETAIL_CHECKLIST_ITEMS,
    STT_COLUMN_WIDTH_MM,
    ReportType,
    generate_report,
)

DEFAULT_TEMPLATES = {
    ReportType.FULL: TEMPLATES / "report_template.docx",
    ReportType.SERVER_ONLY: TEMPLATES / "server_only" / "report_server_only_default.docx",
    ReportType.CLIENT_ONLY: TEMPLATES / "client_only" / "report_client_only_default.docx",
    ReportType.SUMMARY: TEMPLATES / "summary" / "report_summary_default.docx",
    ReportType.TECHNICAL: TEMPLATES / "technical" / "report_technical_default.docx",
    ReportType.INCIDENT_RESPONSE: TEMPLATES / "report_template.docx",
}
# A4 is 210 mm wide; the default templates keep 30 mm left and 20 mm right margins.
PRINT_WIDTH_TWIPS = int(Mm(160).twips)
STT_WIDTH_TWIPS = int(Mm(STT_COLUMN_WIDTH_MM).twips)
LONG_VIETNAMESE_NOTE = " ".join(
    f"Ghi nhận tiến trình lạ thứ {index} chạy từ thư mục tạm của người dùng, "
    "đã đối chiếu nhật ký sự kiện và chữ ký số của tệp thực thi."
    for index in range(1, 41)
)


def _assets(count: int, prefix: str, os_name: str, *, malware_every: int = 0) -> list[dict]:
    assets = []
    for index in range(1, count + 1):
        malware = bool(malware_every) and index % malware_every == 1
        assets.append(
            {
                "hostname": f"{prefix}-{index:03d}",
                "ip": f"10.20.{index // 250}.{index % 250 + 1}",
                "os": os_name,
                "result": "Phát hiện mã độc" if malware else "Không phát hiện",
                "notes": "Tiến trình giả mạo dịch vụ hệ thống tại thư mục tạm" if malware else "",
            }
        )
    return assets


def _fixture(server_count: int, client_count: int) -> dict:
    servers = _assets(server_count, "SRV", "Windows Server 2022", malware_every=7)
    clients = _assets(client_count, "WS", "Windows 11", malware_every=5)
    if servers:
        servers[0]["notes"] = LONG_VIETNAMESE_NOTE
        servers[0]["extras"] = {
            "iocs": [{"type": "sha256", "value": "a" * 64, "source": "EDR giả lập"}]
        }
    return {
        "servers": servers,
        "clients": clients,
        "metadata": {
            "incidentName": "Sự cố giả lập",
            "severity": "high",
            "timeline": [
                {"time": "2026-07-20T10:00:00Z", "event": "Phát hiện", "evidence": "EDR-001"}
            ],
        },
    }


def _generate(report_type: ReportType, data: dict):
    return generate_report(
        data,
        title="Báo cáo giả lập",
        organization="Đơn vị giả lập",
        report_type=report_type,
        template_path=DEFAULT_TEMPLATES[report_type],
    )


def _stt_tables(document) -> list:
    return [table for table in document.tables if table.rows[0].cells[0].text.strip() == "STT"]


def _grid_widths(table) -> list[int]:
    return [int(column.get(qn("w:w"))) for column in table._tbl.tblGrid.findall(qn("w:gridCol"))]


def _footer_parts_xml(document) -> dict[str, str]:
    buffer = io.BytesIO()
    document.save(buffer)
    with zipfile.ZipFile(buffer) as archive:
        return {
            name: archive.read(name).decode("utf-8")
            for name in archive.namelist()
            if name.startswith("word/footer") and name.endswith(".xml")
        }


class _TableLayoutAssertions:
    def assert_stt_tables_fit(self, document, label: str) -> None:
        tables = _stt_tables(document)
        self.assertTrue(tables, f"{label}: no STT table generated")
        repeat_path = f"{qn('w:trPr')}/{qn('w:tblHeader')}"
        for index, table in enumerate(tables, start=1):
            with self.subTest(report=label, table=index, header=table.rows[0].cells[1].text):
                widths = _grid_widths(table)
                self.assertGreaterEqual(widths[0], STT_WIDTH_TWIPS)
                self.assertLessEqual(abs(sum(widths) - PRINT_WIDTH_TWIPS), len(widths))
                rows = [row._tr for row in table.rows]
                self.assertIsNotNone(
                    rows[0].find(repeat_path),
                    "the header row must repeat when the table continues on the next page",
                )
                self.assertFalse([row for row in rows[1:] if row.find(repeat_path) is not None])
                # Word clips a row that is taller than a page when the row may not
                # split (verified on a long synthetic note), so long evidence rows
                # must stay splittable.
                self.assertFalse(list(table._tbl.iter(qn("w:cantSplit"))))


class ReportTableLayoutTests(_TableLayoutAssertions, unittest.TestCase):
    def test_every_report_type_builds_stt_columns_that_fit_the_bold_header(self) -> None:
        expected_headers = {
            ("Máy chủ", "Phiên bản hệ điều hành"),
            ("Máy trạm", "Phiên bản hệ điều hành"),
            ("Máy chủ", "Kết quả rà soát đánh giá"),
            ("Máy trạm", "Kết quả rà soát đánh giá"),
            ("Hạng mục rà soát", "Kết quả rà soát"),
            ("Máy chủ", "Trạng thái"),
            ("Máy trạm", "Trạng thái"),
            ("Thông tin", "Chi tiết"),
            ("Tài sản", "Phát hiện/ghi chú"),
            ("Máy chủ", "Hành động/Trạng thái"),
            ("Máy trạm", "Hành động/Trạng thái"),
            ("Tài sản", "Kết quả"),
        }
        seen_headers: set[tuple[str, str]] = set()
        data = _fixture(server_count=3, client_count=3)
        for report_type in ReportType:
            document = _generate(report_type, data)
            self.assert_stt_tables_fit(document, report_type.value)
            for table in _stt_tables(document):
                cells = table.rows[0].cells
                seen_headers.add((cells[1].text.strip(), cells[-1].text.strip()))
        # Every builder that used a 12 mm STT column must have been exercised.
        self.assertLessEqual(expected_headers, seen_headers)

    def test_detail_table_widths_keep_checklist_text_on_one_line(self) -> None:
        document = _generate(ReportType.SERVER_ONLY, _fixture(server_count=1, client_count=0))
        detail = next(
            table
            for table in _stt_tables(document)
            if table.rows[0].cells[1].text.strip() == "Hạng mục rà soát"
        )
        # 74 mm still holds the longest single-line checklist item and 72 mm the
        # standard result text; 15/73/72 or 16/72/72 wrapped one more row in Word.
        self.assertEqual(_grid_widths(detail), [int(Mm(width).twips) for width in (14, 74, 72)])

    def test_multi_page_reports_keep_layout_and_long_vietnamese_evidence(self) -> None:
        data = _fixture(server_count=24, client_count=24)
        for report_type in (ReportType.FULL, ReportType.SERVER_ONLY, ReportType.CLIENT_ONLY):
            document = _generate(report_type, data)
            self.assert_stt_tables_fit(document, report_type.value)
            if report_type is ReportType.CLIENT_ONLY:
                continue
            detail_text = "\n".join(
                cell.text
                for table in _stt_tables(document)
                if table.rows[0].cells[1].text.strip() == "Hạng mục rà soát"
                for row in table.rows
                for cell in row.cells
            )
            with self.subTest(report=report_type.value):
                self.assertIn(LONG_VIETNAMESE_NOTE, detail_text)

    def test_body_footer_counts_body_pages_without_the_template_total(self) -> None:
        data = _fixture(server_count=2, client_count=2)
        for report_type in (ReportType.FULL, ReportType.SERVER_ONLY, ReportType.CLIENT_ONLY):
            with self.subTest(report=report_type.value):
                document = _generate(report_type, data)
                body_footer = document.sections[-1].footer._element
                instructions = " ".join(
                    node.text or "" for node in body_footer.iter(qn("w:instrText"))
                )
                self.assertIn("PAGE", instructions)
                self.assertIn("SECTIONPAGES", instructions)
                self.assertNotIn("NUMPAGES", instructions)
                for name, xml in _footer_parts_xml(document).items():
                    self.assertNotIn(">308<", xml, name)


class LargeServerOnlyReportTests(_TableLayoutAssertions, unittest.TestCase):
    """The 273-row case that previously needed the v2.3.2 timeout fallback."""

    @classmethod
    def setUpClass(cls) -> None:
        cls.data = {"servers": _assets(273, "SRV", "Windows Server 2022"), "clients": []}
        cls.document = _generate(ReportType.SERVER_ONLY, cls.data)

    def test_every_server_row_and_three_digit_number_is_kept(self) -> None:
        tables = _stt_tables(self.document)
        inventory = tables[0]
        summary = tables[1]
        for table in (inventory, summary):
            self.assertEqual(len(table.rows), 274)
            self.assertEqual(
                [row.cells[0].text for row in table.rows[1:]],
                [str(index) for index in range(1, 274)],
            )
            self.assertEqual(
                [row.cells[1].text for row in table.rows[1:]],
                [asset["hostname"] for asset in self.data["servers"]],
            )
        details = [
            table for table in tables if table.rows[0].cells[1].text.strip() == "Hạng mục rà soát"
        ]
        self.assertEqual(len(details), 273)
        self.assertTrue(
            all(len(table.rows) == len(DETAIL_CHECKLIST_ITEMS) + 1 for table in details)
        )

    def test_layout_rules_hold_for_every_table(self) -> None:
        self.assert_stt_tables_fit(self.document, "server_only/273")


if __name__ == "__main__":
    unittest.main()
