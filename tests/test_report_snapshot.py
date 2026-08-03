from __future__ import annotations

import math
import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "backend"
sys.path.insert(0, str(BACKEND))

from core.report_signature import CanonicalValueError, canonical_sha256  # noqa: E402
from core.report_snapshot import (  # noqa: E402
    DEFAULT_REPORT_TITLE,
    AcceptedReportSnapshot,
    PreparedReportSnapshot,
    thaw_json,
)
from core.report_orchestrator import ReportOrchestrator  # noqa: E402


def accepted(**overrides):
    values = {
        "rows": [{"hostname": "máy-01", "type": "server", "result": "Clean"}],
        "metadata": {"ruleSettings": {"customRules": [{"id": "RULE-1"}]}},
        "title": "",
        "organization": "Reporter Pro",
        "assessment_date": "2026-08-03",
        "report_type": "full",
        "template_bytes": b"template-v1",
        "template_key": "default/full",
        "plugin_manifest": [{
            "pluginId": "os-detector",
            "version": "1",
            "cachePolicy": "deterministic",
            "sourceHash": "abc",
            "cacheIdentity": {},
        }],
    }
    values.update(overrides)
    return AcceptedReportSnapshot.create(**values)


class ReportSignatureTests(unittest.TestCase):
    def test_mapping_order_is_ignored_but_row_order_is_preserved(self) -> None:
        self.assertEqual(canonical_sha256({"b": 2, "a": 1}), canonical_sha256({"a": 1, "b": 2}))
        self.assertNotEqual(canonical_sha256([{"id": 1}, {"id": 2}]), canonical_sha256([{"id": 2}, {"id": 1}]))

    def test_unicode_nfc_has_one_identity(self) -> None:
        self.assertEqual(canonical_sha256("Café"), canonical_sha256("Cafe\u0301"))
        self.assertEqual(
            accepted(rows=[{"hostname": "Café"}]).request_signature,
            accepted(rows=[{"hostname": "Cafe\u0301"}]).request_signature,
        )

    def test_nan_infinity_and_normalized_duplicate_keys_are_rejected(self) -> None:
        for value in (math.nan, math.inf, -math.inf):
            with self.subTest(value=value), self.assertRaises(CanonicalValueError):
                canonical_sha256({"value": value})
        with self.assertRaises(CanonicalValueError):
            canonical_sha256({"é": 1, "e\u0301": 2})


class ReportSnapshotTests(unittest.TestCase):
    def test_snapshot_applies_one_default_title_and_is_deeply_immutable(self) -> None:
        snapshot = accepted()
        self.assertEqual(snapshot.title, DEFAULT_REPORT_TITLE)
        with self.assertRaises(TypeError):
            snapshot.metadata["new"] = "value"
        with self.assertRaises(TypeError):
            snapshot.rows[0]["hostname"] = "changed"

    def test_output_filename_and_accept_timestamp_are_not_content_identity(self) -> None:
        # outputName is deliberately absent from AcceptedReportSnapshot.create.
        first = accepted()
        second = accepted()
        self.assertEqual(first.request_signature, second.request_signature)
        prepared_a = PreparedReportSnapshot.create(
            first,
            payload={"servers": thaw_json(first.rows), "clients": [], "metadata": {}},
            generated_at="2026-08-03T00:00:00Z",
        )
        prepared_b = PreparedReportSnapshot.create(
            second,
            payload={"servers": thaw_json(second.rows), "clients": [], "metadata": {}},
            generated_at="2026-08-03T01:00:00Z",
        )
        self.assertEqual(prepared_a.content_signature, prepared_b.content_signature)

    def test_rule_template_and_plugin_changes_each_change_request_signature(self) -> None:
        baseline = accepted().request_signature
        changed_rule = accepted(metadata={"ruleSettings": {"customRules": [{"id": "RULE-2"}]}})
        changed_template = accepted(template_bytes=b"template-v2")
        changed_plugin = accepted(plugin_manifest=[{
            "pluginId": "os-detector", "version": "2", "cachePolicy": "deterministic",
            "sourceHash": "def", "cacheIdentity": {},
        }])
        self.assertNotEqual(baseline, changed_rule.request_signature)
        self.assertNotEqual(baseline, changed_template.request_signature)
        self.assertNotEqual(baseline, changed_plugin.request_signature)

    def test_preview_and_generate_from_same_accepted_input_have_content_parity(self) -> None:
        snapshot = accepted()
        payload = {
            "servers": [dict(thaw_json(snapshot.rows[0]))],
            "clients": [],
            "metadata": thaw_json(snapshot.metadata),
        }
        preview = PreparedReportSnapshot.create(snapshot, payload=payload, quality={"valid": True})
        generate = PreparedReportSnapshot.create(snapshot, payload=payload, quality={"valid": True})
        self.assertEqual(preview.content_signature, generate.content_signature)

    def test_orchestrator_build_reads_pinned_template_bytes(self) -> None:
        snapshot = accepted(template_bytes=b"pinned-template-bytes", plugin_manifest=[])
        orchestrator = ReportOrchestrator()
        prepared = orchestrator.prepare(
            snapshot,
            plugins=[],
            validate_and_normalize=lambda rows, metadata, _report_type: (
                {"servers": rows, "clients": [], "metadata": metadata},
                {"valid": True},
                [],
            ),
            apply_input_plugins=lambda payload, _plugins: payload,
        )
        observed: list[bytes] = []

        class DocumentStub:
            _reporter_manifest = {}
            _reporter_integrity = {"valid": True}

        def build(_payload, **kwargs):
            observed.append(Path(kwargs["template_path"]).read_bytes())
            return DocumentStub()

        result = orchestrator.build(
            prepared,
            plugins=[],
            build_document=build,
            apply_document_plugins=lambda document, _payload, _plugins: document,
            verify_document=lambda _document, _manifest: {"valid": True},
        )
        self.assertEqual(observed, [b"pinned-template-bytes"])
        self.assertTrue(result.integrity["valid"])


if __name__ == "__main__":
    unittest.main()
