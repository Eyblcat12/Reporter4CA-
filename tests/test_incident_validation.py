from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "backend"))

from core.incident_validation import assess_incident_metadata  # noqa: E402


class IncidentValidationTests(unittest.TestCase):
    def test_complete_incident_is_ready_and_counts_traceability(self) -> None:
        result = assess_incident_metadata({
            "incidentId": "IR-2026-001",
            "detectedAt": "2026-07-21T09:00",
            "timeline": [{
                "time": "09:00", "event": "EDR alert", "evidence": "EDR-1",
                "relatedIocs": "203.0.113.10",
            }],
            "iocs": [{"type": "IP", "value": "203.0.113.10", "source": "EDR-1"}],
            "containmentActions": [{
                "action": "Isolate host", "status": "completed", "owner": "SOC", "evidence": "EDR-2",
            }],
        })
        self.assertTrue(result["valid"])
        self.assertEqual(result["errors"], [])
        self.assertEqual(result["summary"]["completedActions"], 1)
        self.assertEqual(result["summary"]["evidenceReferences"], 2)

    def test_errors_block_but_missing_traceability_is_warning(self) -> None:
        result = assess_incident_metadata({
            "timeline": [{"time": "", "event": "", "relatedIocs": "unknown.example"}],
            "iocs": [{"type": "domain", "value": "unknown.example", "source": ""}],
            "recoveryActions": [{"action": "Restore service", "status": "running"}],
        })
        self.assertFalse(result["valid"])
        self.assertEqual(
            {item["code"] for item in result["errors"]},
            {"missing_incident_id", "missing_detected_at", "missing_timeline_event"},
        )
        self.assertIn("missing_action_owner", {item["code"] for item in result["warnings"]})
        self.assertIn("missing_ioc_source", {item["code"] for item in result["warnings"]})


if __name__ == "__main__":
    unittest.main()
