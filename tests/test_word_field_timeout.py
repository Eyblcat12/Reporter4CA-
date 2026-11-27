"""Word's TOC/page-field wait grows with the report (synthetic data only).

The fixed 45 s used to run out on reports of about 270 assets: the user got a
DOCX with an empty table of contents and no word of it in the UI.
"""

from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "backend"
sys.path.insert(0, str(BACKEND))

from api.models import GenerateRequest, PreviewDocxRequest  # noqa: E402
from api.routes import (  # noqa: E402
    _create_preview_artifact_impl,
    _create_report_artifact_impl,
    _save_finalized_report,
)
from core.config import word_field_update_timeout_seconds  # noqa: E402
from core.database import Database  # noqa: E402
from core.docx_field_updater import FieldUpdateResult  # noqa: E402
from docx import Document  # noqa: E402

DEFERRED = FieldUpdateResult(False, "deferred", "Microsoft Word field update timed out.")


def _rows(count: int) -> list[dict[str, str]]:
    return [
        {
            "type": "server",
            "hostname": f"SRV-GIA-LAP-{index:03d}",
            "ip": f"10.9.0.{index}",
            "os": "Windows Server 2022",
            "result": "Không phát hiện",
        }
        for index in range(1, count + 1)
    ]


class WordTimeoutSettingTests(unittest.TestCase):
    def test_wait_grows_with_assets_and_is_capped(self) -> None:
        with patch.dict(os.environ, {"AUTO_REPORT_WORD_TIMEOUT_SECONDS": ""}):
            for assets, seconds in ((0, 45), (18, 63), (273, 318), (2000, 900), (-5, 45)):
                with self.subTest(assets=assets):
                    self.assertEqual(word_field_update_timeout_seconds(assets), seconds)

    def test_environment_sets_a_fixed_bounded_wait(self) -> None:
        for raw, seconds in (("10", 10), ("1", 5), ("999999", 3600), ("not-a-number", 318)):
            with self.subTest(raw=raw):
                with patch.dict(os.environ, {"AUTO_REPORT_WORD_TIMEOUT_SECONDS": raw}):
                    self.assertEqual(word_field_update_timeout_seconds(273), seconds)


class WordTimeoutPlumbingTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temporary = tempfile.TemporaryDirectory()
        self.root = Path(self.temporary.name)
        self.database = Database(self.root / "reporter.db")
        self.database.initialize()
        self.patches = [
            patch.dict(os.environ, {"AUTO_REPORT_WORD_TIMEOUT_SECONDS": ""}),
            patch("api.routes.get_db", return_value=self.database),
        ]
        for active in self.patches:
            active.start()

    def tearDown(self) -> None:
        for active in reversed(self.patches):
            active.stop()
        self.database.close()
        self.temporary.cleanup()

    def test_save_passes_the_wait_to_word_only_when_given(self) -> None:
        with patch("api.routes.refresh_docx_fields", return_value=DEFERRED) as refresh:
            _save_finalized_report(Document(), self.root / "a.docx", word_timeout_seconds=181)
            _save_finalized_report(Document(), self.root / "b.docx")
        self.assertEqual(refresh.call_args_list[0].kwargs["timeout_seconds"], 181)
        self.assertNotIn("timeout_seconds", refresh.call_args_list[1].kwargs)

    def test_generate_waits_for_its_size_and_says_how_long(self) -> None:
        messages: list[str] = []
        request = GenerateRequest(rows=_rows(30), reportType="server_only", outputName="x")
        with patch("api.routes.refresh_docx_fields", return_value=DEFERRED) as refresh:
            result = _create_report_artifact_impl(
                request, on_progress=lambda _phase, _value, message: messages.append(message)
            )
        Path(result["outputPath"]).unlink(missing_ok=True)

        self.assertEqual(refresh.call_args.kwargs["timeout_seconds"], 75)
        self.assertIn("Word đang cập nhật mục lục và số trang (tối đa 75 giây)", messages)
        self.assertEqual(result["fieldEngine"], "deferred")

    def test_preview_uses_the_same_wait(self) -> None:
        phases: list[tuple[str, str]] = []
        request = PreviewDocxRequest(rows=_rows(75), reportType="server_only")
        with patch("api.routes.refresh_docx_fields", return_value=DEFERRED) as refresh:
            result = _create_preview_artifact_impl(
                request,
                on_progress=lambda phase, _value, message: phases.append((phase, message)),
            )
        Path(result["path"]).unlink(missing_ok=True)

        self.assertEqual(refresh.call_args.kwargs["timeout_seconds"], 120)
        self.assertIn(
            ("finalizing", "Word đang cập nhật mục lục và số trang (tối đa 2 phút)"), phases
        )
        self.assertEqual(result["fieldEngine"], "deferred")


if __name__ == "__main__":
    unittest.main()
