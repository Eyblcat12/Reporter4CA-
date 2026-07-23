from __future__ import annotations

import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "backend"
SAMPLES = BACKEND / "samples"
sys.path.insert(0, str(BACKEND))

from core.column_mapper import auto_detect_mapping  # noqa: E402
from core.data_quality import assess_rows  # noqa: E402
from core.gui_state import normalized_payload_to_rows  # noqa: E402
from core.input_parser import detect_real_format, parse_with_column_mapping  # noqa: E402
from core.report_generator import _asset_statistics  # noqa: E402
from core.rule_engine import evaluate_payload  # noqa: E402


class TrackingImportTests(unittest.TestCase):
    def test_generic_tracking_template_maps_server_and_client_columns(self) -> None:
        import pandas as pd

        source = SAMPLES / "Tracking.csv"
        self.assertEqual(detect_real_format(source), ".xlsx")
        columns = [str(column) for column in pd.read_excel(source, nrows=1).columns]
        mapping = auto_detect_mapping(columns)
        payload = parse_with_column_mapping(source, mapping, default_section="clients")

        self.assertEqual(len(payload["servers"]), 20)
        self.assertEqual(len(payload["clients"]), 10)
        self.assertEqual(payload["servers"][0]["hostname"], "SRV-DC-01")
        self.assertEqual(payload["clients"][0]["hostname"], "PC-KT-015")

    def test_all_declared_malware_results_become_evidence_backed_anomalies(self) -> None:
        import pandas as pd

        source = SAMPLES / "Tracking.csv"
        columns = [str(column) for column in pd.read_excel(source, nrows=1).columns]
        payload = parse_with_column_mapping(
            source,
            auto_detect_mapping(columns),
            default_section="clients",
        )
        evaluated = evaluate_payload(payload)
        assets = evaluated["servers"] + evaluated["clients"]
        declared = [
            asset for asset in assets
            if "phát hiện mã độc" in str(asset.get("result", "")).casefold()
        ]
        detected = [
            asset for asset in assets
            if any(
                finding.get("ruleId") == "MALWARE_EVIDENCE"
                and finding.get("classification") == "anomaly"
                and finding.get("evidence")
                for finding in asset.get("findings", [])
            )
        ]

        self.assertEqual(len(declared), 8)
        self.assertEqual(len(detected), 8)
        self.assertEqual(_asset_statistics(evaluated), (30, 8, 22))
        self.assertEqual(
            {asset["hostname"] for asset in detected},
            {asset["hostname"] for asset in declared},
        )

    def test_diverse_fifty_asset_csv_is_report_ready(self) -> None:
        import pandas as pd

        source = SAMPLES / "Tracking_2.csv"
        self.assertEqual(detect_real_format(source), ".csv")
        columns = [str(column) for column in pd.read_csv(source, nrows=1).columns]
        mapping = auto_detect_mapping(columns)
        payload = parse_with_column_mapping(source, mapping, default_section="clients")
        rows = normalized_payload_to_rows(payload)
        quality = assess_rows(rows)
        evaluated = evaluate_payload(payload)
        finding_ids = {
            finding["ruleId"]
            for section in ("servers", "clients")
            for asset in evaluated[section]
            for finding in asset.get("findings", [])
        }

        self.assertEqual(len(payload["servers"]), 22)
        self.assertEqual(len(payload["clients"]), 28)
        self.assertEqual(len(rows), 50)
        self.assertTrue(quality["valid"])
        self.assertEqual(quality["summary"]["warnings"], 0)
        self.assertEqual(
            {row["result"] for row in rows},
            {
                "Phát hiện mã độc", "Ghi nhận dấu hiệu bất thường", "Cần xác minh",
                "Không phát hiện", "Không phát hiện - Đã kiểm tra", "Chưa kết luận",
            },
        )
        self.assertEqual(finding_ids, {"MALWARE_EVIDENCE", "PROXY_TOOL_REVIEW"})


if __name__ == "__main__":
    unittest.main()
