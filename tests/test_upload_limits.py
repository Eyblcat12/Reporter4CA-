from __future__ import annotations

import base64
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "backend"
sys.path.insert(0, str(BACKEND))

from api.routes import _assert_report_size, _decode_base64  # noqa: E402


class UploadLimitTests(unittest.TestCase):
    def test_decode_accepts_plain_and_data_url_base64(self) -> None:
        encoded = base64.b64encode(b"reporter").decode()
        self.assertEqual(_decode_base64(encoded, max_bytes=32), b"reporter")
        self.assertEqual(
            _decode_base64(f"data:text/plain;base64,{encoded}", max_bytes=32),
            b"reporter",
        )

    def test_decode_rejects_invalid_base64(self) -> None:
        with self.assertRaises(HTTPException) as context:
            _decode_base64("%%%not-base64%%%", max_bytes=32)
        self.assertEqual(context.exception.status_code, 400)

    def test_decode_rejects_file_above_limit_before_processing(self) -> None:
        encoded = base64.b64encode(b"12345").decode()
        with self.assertRaises(HTTPException) as context:
            _decode_base64(encoded, max_bytes=4)
        self.assertEqual(context.exception.status_code, 413)

    def test_report_row_limit_is_configurable_and_bounded(self) -> None:
        with patch.dict("os.environ", {"AUTO_REPORT_MAX_ROWS": "100"}):
            _assert_report_size([{}] * 100)
            with self.assertRaises(HTTPException) as context:
                _assert_report_size([{}] * 101)
        self.assertEqual(context.exception.status_code, 413)


if __name__ == "__main__":
    unittest.main()
