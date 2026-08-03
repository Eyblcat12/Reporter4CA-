from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi import HTTPException

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "backend"
sys.path.insert(0, str(BACKEND))

from api.models import GenerateRequest, ValidateRowsRequest  # noqa: E402
from api.routes import generate, validate_rows  # noqa: E402
from core.data_quality import assess_rows  # noqa: E402


class DataQualityTests(unittest.TestCase):
    def test_quality_summary_classifies_errors_warnings_and_asset_types(self) -> None:
        result = assess_rows([
            {"type": "server", "hostname": "srv-01", "ip": "10.0.0.1", "os": "Linux", "result": "Clean"},
            {"type": "client", "hostname": "SRV-01", "ip": "999.1.1.1", "os": "", "result": ""},
            {"type": "client", "hostname": "", "ip": "2001:db8::1", "os": "Windows", "result": "Clean"},
        ])
        self.assertFalse(result["valid"])
        self.assertEqual(result["summary"]["errorRows"], 1)
        self.assertEqual(result["summary"]["warningRows"], 1)
        self.assertEqual(result["summary"]["duplicateHostnames"], 1)
        self.assertEqual(result["summary"]["invalidIps"], 1)
        self.assertEqual(result["summary"]["missingOs"], 1)
        self.assertEqual(result["summary"]["missingResult"], 1)
        self.assertEqual((result["summary"]["servers"], result["summary"]["clients"]), (1, 2))

    def test_validate_endpoint_returns_filterable_issue_codes(self) -> None:
        response = asyncio.run(validate_rows(ValidateRowsRequest(rows=[{"hostname": "", "result": ""}])))
        self.assertFalse(response["valid"])
        self.assertIn("missing_hostname", {issue["code"] for issue in response["issues"]})
        self.assertEqual(response["summary"]["totalRows"], 1)

    def test_generate_rejects_blocking_data_before_report_engine_runs(self) -> None:
        request = GenerateRequest(rows=[{"type": "server", "hostname": ""}])
        with patch("api.routes.generate_report") as report_engine:
            with self.assertRaises(HTTPException) as context:
                asyncio.run(generate(request))
        self.assertEqual(context.exception.status_code, 422)
        report_engine.assert_not_called()


if __name__ == "__main__":
    unittest.main()
