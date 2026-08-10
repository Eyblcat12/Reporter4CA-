from __future__ import annotations

import asyncio
import base64
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "backend"
SAMPLES = BACKEND / "samples"
sys.path.insert(0, str(BACKEND))

from api.models import ColumnPreviewRequest, ImportFileRequest  # noqa: E402
from api.routes import column_preview, import_file  # noqa: E402


class ImportApiTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        source = SAMPLES / "Tracking.csv"
        cls.encoded = (
            "data:application/octet-stream;base64," + base64.b64encode(source.read_bytes()).decode()
        )

    def test_first_import_returns_rows_with_suggested_mapping(self) -> None:
        preview = asyncio.run(
            column_preview(
                ColumnPreviewRequest(
                    filename="tracking-template.csv",
                    contentBase64=self.encoded,
                )
            )
        )
        bundle = asyncio.run(
            import_file(
                ImportFileRequest(
                    filename="tracking-template.csv",
                    contentBase64=self.encoded,
                    defaultType="client",
                    columnMapping=preview["suggestedMapping"],
                    sheetName=preview["sheets"][0] if preview["sheets"] else "",
                    headerRow=preview["headerRow"],
                )
            )
        )
        self.assertEqual(bundle["counts"], {"servers": 20, "clients": 10, "total": 30})
        self.assertEqual(len(bundle["rows"]), 30)


if __name__ == "__main__":
    unittest.main()
