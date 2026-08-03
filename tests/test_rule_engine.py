from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "backend"))

from core.rule_engine import (
    assess_asset,
    assessment_text,
    evaluate_asset,
    evaluate_payload,
    find_rule_conflicts,
    load_rule_pack,
    validate_rule,
)


class RuleEngineTests(unittest.TestCase):
    def setUp(self) -> None:
        self.pack = load_rule_pack()

    def test_proxy_tool_creates_traceable_review_finding(self) -> None:
        findings = evaluate_asset({"type": "client", "hostname": "PC-01", "software": "Proxifier 4"}, self.pack["rules"])
        self.assertEqual(findings[0]["ruleId"], "PROXY_TOOL_REVIEW")
        self.assertEqual(findings[0]["classification"], "needs_review")
        self.assertEqual(findings[0]["evidence"][0]["field"], "software")

    def test_negated_malware_text_does_not_create_false_positive(self) -> None:
        findings = evaluate_asset({"result": "No malware detected", "notes": "Clean"}, self.pack["rules"])
        self.assertFalse(any(item["ruleId"] == "MALWARE_EVIDENCE" for item in findings))

    def test_rule_can_be_disabled_by_preset_configuration(self) -> None:
        payload = {"servers": [], "clients": [{"software": "Tor Browser"}], "metadata": {}}
        result = evaluate_payload(payload, disabled_rule_ids=["PROXY_TOOL_REVIEW"])
        self.assertFalse(any(
            item["ruleId"] == "PROXY_TOOL_REVIEW"
            for item in result["clients"][0]["findings"]
        ))
        self.assertEqual(result["clients"][0]["assessment"]["classification"], "insufficient_data")
        self.assertEqual(result["metadata"]["ruleEngine"]["disabledRuleIds"], ["PROXY_TOOL_REVIEW"])

    def test_missing_evidence_never_creates_finding(self) -> None:
        findings = evaluate_asset({"hostname": "PC-02", "result": ""}, self.pack["rules"])
        self.assertEqual(findings, [])

    def test_asset_assessment_uses_explicit_precedence_and_structured_counts(self) -> None:
        payload = {
            "servers": [
                {"hostname": "SRV-01", "result": "Ghi nhận dấu hiệu bất thường"},
                {"hostname": "SRV-02", "result": "Chưa kết luận"},
            ],
            "clients": [{"hostname": "PC-01", "result": "Không phát hiện"}],
            "metadata": {},
        }
        result = evaluate_payload(payload)

        self.assertEqual(result["servers"][0]["assessment"]["classification"], "anomaly")
        self.assertEqual(result["servers"][1]["assessment"]["classification"], "insufficient_data")
        self.assertEqual(result["clients"][0]["assessment"]["classification"], "clean")
        self.assertEqual(
            result["metadata"]["ruleEngine"]["assessmentCounts"],
            {"clean": 1, "insufficient_data": 1, "needs_review": 0, "anomaly": 1},
        )

    def test_missing_result_is_not_silently_classified_as_clean(self) -> None:
        result = evaluate_payload({
            "servers": [],
            "clients": [{"hostname": "PC-EMPTY", "notes": "Collection incomplete"}],
            "metadata": {},
        })
        asset = result["clients"][0]
        self.assertEqual(asset["assessment"]["classification"], "insufficient_data")
        self.assertEqual(asset["findings"][0]["ruleId"], "SOURCE_RESULT_MISSING")
        self.assertEqual(asset["findings"][0]["source"], "data_quality")

    def test_anomaly_takes_precedence_over_review_and_insufficient_data(self) -> None:
        findings = [
            {"classification": "insufficient_data", "evidence": [{"field": "result", "value": "Chưa kết luận"}]},
            {"classification": "needs_review", "evidence": [{"field": "notes", "value": "Proxy"}]},
            {"classification": "anomaly", "evidence": [{"field": "result", "value": "Bất thường"}]},
        ]
        self.assertEqual(assess_asset(findings)["classification"], "anomaly")

    def test_custom_rule_from_metadata_is_applied_immediately(self) -> None:
        custom = validate_rule({
            "id": "CUSTOM_INTERNAL_PROXY", "name": "Internal proxy review",
            "severity": "medium", "classification": "needs_review",
            "conditions": {
                "fields": ["notes"], "containsAny": ["Acme Relay"],
                "excludeContainsAny": ["approved"],
            },
        })
        payload = {
            "servers": [],
            "clients": [{"hostname": "PC-03", "notes": "Observed Acme Relay"}],
            "metadata": {"ruleSettings": {"customRules": [custom]}},
        }
        result = evaluate_payload(payload)
        finding = next(item for item in result["clients"][0]["findings"] if item["ruleId"] == "CUSTOM_INTERNAL_PROXY")
        self.assertEqual(finding["evidence"][0]["field"], "notes")
        self.assertEqual(assessment_text([finding]), "Ghi nhận dấu hiệu cần xác minh")

    def test_custom_rule_exclusion_prevents_false_positive(self) -> None:
        rule = validate_rule({
            "name": "Proxy review", "severity": "medium", "classification": "anomaly",
            "conditions": {"fields": ["notes"], "containsAny": ["proxy"], "excludeContainsAny": ["approved"]},
        })
        self.assertEqual(evaluate_asset({"notes": "Approved proxy for business"}, [rule]), [])
        self.assertEqual(assessment_text([]), "Không phát hiện dấu hiệu bất thường")

    def test_conflicts_require_shared_field_and_keyword(self) -> None:
        conflicts = find_rule_conflicts([
            {"id": "A", "name": "A", "classification": "needs_review", "conditions": {"fields": ["notes"], "containsAny": ["Proxifier"]}},
            {"id": "B", "name": "B", "classification": "anomaly", "conditions": {"fields": ["notes", "software"], "containsAny": ["proxifier"]}},
            {"id": "C", "name": "C", "classification": "anomaly", "conditions": {"fields": ["result"], "containsAny": ["proxifier"]}},
        ])
        self.assertEqual(len(conflicts), 1)
        self.assertEqual(conflicts[0]["ruleIds"], ["A", "B"])
        self.assertTrue(conflicts[0]["classificationConflict"])


if __name__ == "__main__":
    unittest.main()
