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
from core.config import (  # noqa: E402
    job_memory_limit_mib,
    job_resource_poll_seconds,
    job_timeout_seconds,
)


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

    def test_job_resource_limits_are_opt_in_and_bounded(self) -> None:
        with patch.dict("os.environ", {}, clear=True):
            self.assertIsNone(job_memory_limit_mib())
            self.assertIsNone(job_timeout_seconds())
        with patch.dict(
            "os.environ",
            {
                "AUTO_REPORT_JOB_MEMORY_LIMIT_MB": "64",
                "AUTO_REPORT_JOB_TIMEOUT_SECONDS": "5",
                "AUTO_REPORT_JOB_RESOURCE_POLL_MS": "1",
            },
        ):
            self.assertEqual(job_memory_limit_mib(), 256)
            self.assertEqual(job_timeout_seconds(), 30)
            self.assertEqual(job_resource_poll_seconds(), 0.1)


if __name__ == "__main__":
    unittest.main()
