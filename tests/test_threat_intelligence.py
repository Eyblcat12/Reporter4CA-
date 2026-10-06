from __future__ import annotations

import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "apps" / "backend"))

from core.threat_intelligence import normalize_iocs, normalize_mitre


class ThreatIntelligenceTests(unittest.TestCase):
    def test_url_evidence_preserves_case_credentials_ipv6_and_fragment(self) -> None:
        values = [
            "https://EXAMPLE.com/Payload?a=B#Part",
            "https://example.com/payload?a=B#Part",
            "https://User:Pass@[2001:db8::1]:443/Payload",
        ]
        result = normalize_iocs([{"type": "url", "value": value} for value in values])
        self.assertEqual(len(result), 3)
        self.assertEqual(result[0]["value"], values[0].replace("EXAMPLE", "example"))
        self.assertEqual(result[2]["value"], values[2])
        self.assertTrue(all(item["valid"] for item in result))

    def test_malformed_urls_never_raise_or_become_valid(self) -> None:
        for value in (
            "https://example.com:bad/path",
            "http://[broken",
            "http://x:99999",
            "http://a b/",
        ):
            with self.subTest(value=value):
                result = normalize_iocs([{"type": "url", "value": value}])
                self.assertFalse(result[0]["valid"])
                self.assertEqual(result[0]["value"], value)

    def test_explicit_filename_and_ip_family_are_respected(self) -> None:
        self.assertFalse(normalize_iocs([{"type": "md5", "value": "malware.exe"}])[0]["valid"])
        self.assertFalse(
            normalize_iocs([{"type": "md5", "value": "https://example.com"}])[0]["valid"]
        )
        self.assertEqual(
            normalize_iocs([{"type": "filename", "value": "Malware.exe"}])[0]["type"], "filename"
        )
        self.assertFalse(normalize_iocs([{"type": "ipv4", "value": "::1"}])[0]["valid"])

    def test_iocs_are_validated_canonicalized_and_deduplicated(self) -> None:
        result = normalize_iocs(
            [
                {"value": "Example.COM", "type": "domain", "source": "EDR-1"},
                {"value": "example.com", "type": "domain", "source": "DNS-2"},
                {"value": "999.2.3.4", "type": "ip", "source": "note"},
            ]
        )
        self.assertEqual(len(result), 2)
        domain = next(item for item in result if item["type"] == "domain")
        self.assertEqual(domain["sources"], ["EDR-1", "DNS-2"])
        self.assertTrue(domain["valid"])
        self.assertFalse(next(item for item in result if item["value"] == "999.2.3.4")["valid"])

    def test_mitre_mapping_requires_valid_id_and_evidence(self) -> None:
        result = normalize_mitre(
            [
                {"technique": "t1055", "tactic": "Defense Evasion", "evidence": "EDR-1"},
                {"technique": "T999", "tactic": "Unknown"},
            ]
        )
        self.assertTrue(result[0]["valid"])
        self.assertFalse(result[1]["valid"])


if __name__ == "__main__":
    unittest.main()
