from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "backend"))

from core.threat_intelligence import normalize_iocs, normalize_mitre


class ThreatIntelligenceTests(unittest.TestCase):
    def test_iocs_are_validated_canonicalized_and_deduplicated(self) -> None:
        result = normalize_iocs([
            {"value": "Example.COM", "type": "domain", "source": "EDR-1"},
            {"value": "example.com", "type": "domain", "source": "DNS-2"},
            {"value": "999.2.3.4", "type": "ip", "source": "note"},
        ])
        self.assertEqual(len(result), 2)
        domain = next(item for item in result if item["type"] == "domain")
        self.assertEqual(domain["sources"], ["EDR-1", "DNS-2"])
        self.assertTrue(domain["valid"])
        self.assertFalse(next(item for item in result if item["value"] == "999.2.3.4")["valid"])

    def test_mitre_mapping_requires_valid_id_and_evidence(self) -> None:
        result = normalize_mitre([
            {"technique": "t1055", "tactic": "Defense Evasion", "evidence": "EDR-1"},
            {"technique": "T999", "tactic": "Unknown"},
        ])
        self.assertTrue(result[0]["valid"])
        self.assertFalse(result[1]["valid"])


if __name__ == "__main__":
    unittest.main()
