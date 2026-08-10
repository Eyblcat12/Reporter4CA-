from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

from docx import Document

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "backend"
SAMPLES = BACKEND / "samples"
sys.path.insert(0, str(BACKEND))

from core.column_mapper import auto_detect_mapping  # noqa: E402
from core.data_quality import assess_rows  # noqa: E402
from core.gui_state import normalized_payload_to_rows  # noqa: E402
from core.input_parser import detect_real_format, parse_with_column_mapping  # noqa: E402
from core.report_generator import ReportType, _asset_statistics, generate_report  # noqa: E402
from core.report_integrity import verify_report_document  # noqa: E402
from core.rule_engine import evaluate_payload  # noqa: E402


class TrackingImportTests(unittest.TestCase):
    def _save_reopen_and_verify(self, document, manifest, filename: str) -> dict:
        with tempfile.TemporaryDirectory() as directory:
            output_path = Path(directory) / filename
            document.save(output_path)
            reopened = Document(output_path)
            return verify_report_document(reopened, manifest)

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
            asset
            for asset in assets
            if "phát hiện mã độc" in str(asset.get("result", "")).casefold()
        ]
        detected = [
            asset
            for asset in assets
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

    def test_full_tracking_report_verifies_all_thirty_assets_and_eight_anomalies(self) -> None:
        import pandas as pd

        source = SAMPLES / "Tracking.csv"
        columns = [str(column) for column in pd.read_excel(source, nrows=1).columns]
        payload = parse_with_column_mapping(
            source,
            auto_detect_mapping(columns),
            default_section="clients",
        )
        document = generate_report(
            payload,
            title="Tracking integrity regression",
            organization="Reporter Pro",
            template_path=BACKEND / "templates" / "report_template.docx",
            report_type=ReportType.FULL,
        )
        manifest = document._reporter_manifest
        integrity = self._save_reopen_and_verify(
            document,
            manifest,
            "tracking-30-roundtrip.docx",
        )

        self.assertEqual(manifest["assetCount"], 30)
        self.assertEqual(manifest["assetTypeCounts"], {"server": 20, "client": 10})
        self.assertEqual(manifest["assessmentCounts"], {"anomaly": 8, "clean": 22})
        self.assertEqual(manifest["findingCount"], 8)
        self.assertEqual(manifest["evidenceCount"], 12)
        self.assertEqual(manifest["ruleCounts"], {"MALWARE_EVIDENCE": 8})
        self.assertEqual(integrity["actualAssets"], 30)
        self.assertEqual(integrity["verifiedAssets"], 30)
        self.assertEqual(integrity["actualAssetTypes"], {"client": 10, "server": 20})
        self.assertEqual(integrity["verifiedAssetTypes"], {"client": 10, "server": 20})
        self.assertFalse(integrity["findingVerificationApplicable"])
        self.assertEqual(
            integrity["verifiedSections"],
            len(manifest["requiredSections"]),
        )
        self.assertEqual(integrity["errorCodes"], [])
        self.assertTrue(integrity["valid"])

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
                "Phát hiện mã độc",
                "Ghi nhận dấu hiệu bất thường",
                "Cần xác minh",
                "Không phát hiện",
                "Không phát hiện - Đã kiểm tra",
                "Chưa kết luận",
            },
        )
        self.assertEqual(
            finding_ids,
            {
                "MALWARE_EVIDENCE",
                "DECLARED_ANOMALY",
                "DECLARED_REVIEW",
                "INCOMPLETE_ASSESSMENT",
                "PROXY_TOOL_REVIEW",
            },
        )

    def test_diverse_fifty_asset_report_roundtrip_preserves_scope_and_manifest(self) -> None:
        import pandas as pd

        source = SAMPLES / "Tracking_2.csv"
        columns = [str(column) for column in pd.read_csv(source, nrows=1).columns]
        payload = parse_with_column_mapping(
            source,
            auto_detect_mapping(columns),
            default_section="clients",
        )
        document = generate_report(
            payload,
            title="Tracking 2 integrity regression",
            organization="Reporter Pro",
            template_path=BACKEND / "templates" / "report_template.docx",
            report_type=ReportType.FULL,
        )
        manifest = document._reporter_manifest
        integrity = self._save_reopen_and_verify(
            document,
            manifest,
            "tracking-50-roundtrip.docx",
        )

        self.assertEqual(manifest["assetCount"], 50)
        self.assertEqual(manifest["assetTypeCounts"], {"server": 22, "client": 28})
        self.assertEqual(
            manifest["assessmentCounts"],
            {"anomaly": 20, "needs_review": 11, "clean": 17, "insufficient_data": 2},
        )
        self.assertEqual(manifest["findingCount"], 37)
        self.assertEqual(manifest["evidenceCount"], 44)
        self.assertEqual(
            manifest["ruleCounts"],
            {
                "MALWARE_EVIDENCE": 10,
                "DECLARED_ANOMALY": 10,
                "DECLARED_REVIEW": 11,
                "INCOMPLETE_ASSESSMENT": 2,
                "PROXY_TOOL_REVIEW": 4,
            },
        )
        self.assertEqual(integrity["actualAssets"], 50)
        self.assertEqual(integrity["verifiedAssets"], 50)
        self.assertEqual(integrity["actualAssetTypes"], {"client": 28, "server": 22})
        self.assertEqual(integrity["verifiedAssetTypes"], {"client": 28, "server": 22})
        self.assertFalse(integrity["findingVerificationApplicable"])
        self.assertEqual(
            integrity["verifiedSections"],
            len(manifest["requiredSections"]),
        )
        self.assertEqual(integrity["missingAssets"], [])
        self.assertEqual(integrity["errorCodes"], [])
        self.assertTrue(integrity["valid"])


if __name__ == "__main__":
    unittest.main()
