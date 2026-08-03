"""Preflight manifest and structural verification for generated reports."""

from __future__ import annotations

from collections import Counter
import re
from typing import Any
import unicodedata

from core.rule_engine import assess_asset


class ReportIntegrityError(RuntimeError):
    """Raised when the generated document does not match its evaluated input."""

    def __init__(
        self,
        message: str,
        *,
        errors: list[dict[str, Any]] | None = None,
        result: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.errors = list(errors or [])
        self.error_codes = tuple(str(error.get("code", "")) for error in self.errors)
        self.code = self.error_codes[0] if self.error_codes else "REPORT_INTEGRITY_FAILED"
        self.result = result or {}


_STANDARD_SECTIONS = (
    "Tổng quan",
    "Kết quả",
    "Phân tích điều tra",
    "Gỡ bỏ mã độc",
    "Indicators of compromise (IoCs)",
    "Khuyến nghị & khắc phục",
)
_REQUIRED_SECTIONS_BY_REPORT_TYPE = {
    "full": (
        *_STANDARD_SECTIONS,
        "Đánh giá chung đối với máy chủ",
        "Đánh giá chung với các máy trạm",
    ),
    "server_only": (
        *_STANDARD_SECTIONS,
        "Đánh giá chung đối với máy chủ",
        "Chi tiết kết quả CA các máy chủ",
    ),
    "client_only": (
        *_STANDARD_SECTIONS,
        "Đánh giá chung với các máy trạm",
        "Chi tiết kết quả CA các máy trạm",
    ),
    "summary": (
        "Tổng quan",
        "Kết quả và phân tích tổng hợp",
        "Kết luận và khuyến nghị",
    ),
    "technical": (
        "Tổng quan",
        "Phân tích chi tiết",
        "Findings từ rule engine",
        "Kết luận và khuyến nghị",
    ),
    "incident_response": (
        "Thông tin sự cố",
        "Tóm tắt điều hành",
        "Tài sản bị ảnh hưởng",
        "Dòng thời gian",
        "Phát hiện và bằng chứng",
        "Indicators of compromise (IoCs)",
        "MITRE ATT&CK",
        "Ứng phó sự cố",
        "Bài học kinh nghiệm",
        "Khuyến nghị & khắc phục",
    ),
}
_FINDING_REPORT_TYPES = frozenset({"technical", "incident_response"})
_NUMBERED_HEADING_PREFIX = re.compile(r"^\s*\d+(?:\.\d+)*\.?\s+")


def build_report_manifest(data: dict[str, Any], report_type: str) -> dict[str, Any]:
    """Describe exactly which assets, conclusions and findings must be rendered."""
    sections = ("servers", "clients")
    if report_type == "server_only":
        sections = ("servers",)
    elif report_type == "client_only":
        sections = ("clients",)

    entries: list[dict[str, Any]] = []
    for section in sections:
        for index, asset in enumerate(data.get(section, [])):
            findings = [
                item for item in asset.get("findings", [])
                if isinstance(item, dict) and item.get("evidence")
            ]
            finding_entries = []
            for finding in findings:
                evidence = finding.get("evidence", [])
                evidence_items = evidence if isinstance(evidence, list) else []
                evidence_text = "; ".join(
                    f"{item.get('field')}: {item.get('value')}"
                    for item in evidence_items
                    if isinstance(item, dict)
                )
                finding_entries.append({
                    "ruleId": str(finding.get("ruleId", "")).strip(),
                    "evidenceCount": len(evidence_items),
                    "evidenceText": evidence_text,
                })
            assessment = asset.get("assessment")
            if not isinstance(assessment, dict):
                assessment = assess_asset(findings)
            entries.append({
                "assetId": str(assessment.get("assetId") or f"{section}:{index}"),
                "assetType": "server" if section == "servers" else "client",
                "hostname": str(asset.get("hostname", "")).strip(),
                "assessment": str(assessment.get("classification", "clean")),
                "assessmentLabel": str(assessment.get("label", "")),
                "findingIds": [str(item.get("ruleId", "")).strip() for item in findings],
                "findingCount": len(findings),
                "evidenceCount": sum(len(item.get("evidence", [])) for item in findings),
                "findings": finding_entries,
            })

    assessment_counts = Counter(item["assessment"] for item in entries)
    asset_type_counts = Counter(item["assetType"] for item in entries)
    rule_counts = Counter(
        rule_id
        for item in entries
        for rule_id in item["findingIds"]
        if rule_id
    )
    return {
        "version": "1.0",
        "reportType": report_type,
        "assetCount": len(entries),
        "findingCount": sum(item["findingCount"] for item in entries),
        "evidenceCount": sum(item["evidenceCount"] for item in entries),
        "assetTypeCounts": dict(asset_type_counts),
        "assessmentCounts": dict(assessment_counts),
        "ruleCounts": dict(rule_counts),
        "requiredSections": list(_REQUIRED_SECTIONS_BY_REPORT_TYPE.get(report_type, ())),
        "assets": entries,
    }


def _normalize_text(value: Any) -> str:
    return unicodedata.normalize("NFC", str(value)).strip()


def _normalize_heading(value: Any) -> str:
    text = _NUMBERED_HEADING_PREFIX.sub("", _normalize_text(value))
    return text.casefold()


def _is_heading(paragraph: Any) -> bool:
    style = getattr(paragraph, "style", None)
    style_id = _normalize_text(getattr(style, "style_id", "")).replace(" ", "").casefold()
    style_name = _normalize_text(getattr(style, "name", "")).replace(" ", "").casefold()
    return style_id.startswith("heading") or style_name.startswith("heading")


def _index_document(document: Any) -> dict[str, Any]:
    """Index semantic report rows and headings in one traversal."""
    summary_rows: Counter[tuple[str, str, str]] = Counter()
    incident_assets: Counter[str] = Counter()
    finding_rows: Counter[tuple[str, str, str]] = Counter()

    for table in document.tables:
        row_iterator = iter(table.rows)
        header_row = next(row_iterator, None)
        if header_row is None:
            continue
        header = tuple(_normalize_text(cell.text) for cell in header_row.cells)

        summary_asset_type = None
        if (
            len(header) >= 3
            and header[0] == "STT"
            and header[1] in {"Máy chủ", "Máy trạm"}
            and header[2] == "Kết quả rà soát đánh giá"
        ):
            summary_asset_type = "server" if header[1] == "Máy chủ" else "client"

        is_incident_asset_table = (
            header[:4] == ("STT", "Tài sản", "Địa chỉ IP", "Kết quả")
        )
        evidence_column = None
        if header[:5] == ("Tài sản", "Rule", "Mức độ", "Phân loại", "Bằng chứng"):
            evidence_column = 4
        elif header[:4] == ("Tài sản", "Rule", "Mức độ", "Bằng chứng"):
            evidence_column = 3

        for row in row_iterator:
            values = tuple(_normalize_text(cell.text) for cell in row.cells)
            if summary_asset_type and len(values) >= 3 and values[1]:
                summary_rows[(summary_asset_type, values[1], values[2])] += 1
            if is_incident_asset_table and len(values) >= 2 and values[1]:
                incident_assets[values[1]] += 1
            if (
                evidence_column is not None
                and len(values) > evidence_column
                and values[0]
            ):
                finding_rows[(values[0], values[1], values[evidence_column])] += 1

    headings = {
        _normalize_heading(paragraph.text)
        for paragraph in document.paragraphs
        if _is_heading(paragraph) and _normalize_text(paragraph.text)
    }
    return {
        "summaryRows": summary_rows,
        "incidentAssets": incident_assets,
        "findingRows": finding_rows,
        "headings": headings,
    }


def _counter_dict(counter: Counter[Any]) -> dict[str, int]:
    return {
        str(key): int(value)
        for key, value in sorted(counter.items(), key=lambda item: str(item[0]))
        if value
    }


def _expected_findings(manifest: dict[str, Any]) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    for asset in manifest.get("assets", []):
        hostname = _normalize_text(asset.get("hostname", ""))
        entries = asset.get("findings")
        if isinstance(entries, list):
            for finding in entries:
                if not isinstance(finding, dict):
                    continue
                findings.append({
                    "hostname": hostname,
                    "ruleId": _normalize_text(finding.get("ruleId", "")),
                    "evidenceCount": int(finding.get("evidenceCount", 0)),
                    "evidenceText": _normalize_text(finding.get("evidenceText", "")),
                })
            continue

        # Backward compatibility for manifests created before evidence details
        # were added. Finding/rule coverage remains available; evidence coverage
        # is marked not applicable by the verifier.
        for rule_id in asset.get("findingIds", []):
            findings.append({
                "hostname": hostname,
                "ruleId": _normalize_text(rule_id),
                "evidenceCount": 0,
                "evidenceText": None,
            })
    return findings


def verify_report_document(document: Any, manifest: dict[str, Any]) -> dict[str, Any]:
    """Verify structural and semantic coverage in a generated DOCX."""
    report_type = str(manifest.get("reportType", "full"))
    index = _index_document(document)
    errors: list[dict[str, Any]] = []

    required_sections = [
        _normalize_text(section)
        for section in manifest.get(
            "requiredSections",
            _REQUIRED_SECTIONS_BY_REPORT_TYPE.get(report_type, ()),
        )
    ]
    missing_sections = [
        section
        for section in required_sections
        if _normalize_heading(section) not in index["headings"]
    ]
    if missing_sections:
        errors.append({
            "code": "REQUIRED_SECTION_MISSING",
            "message": f"missing required sections: {', '.join(missing_sections[:5])}",
            "expected": len(required_sections),
            "actual": len(required_sections) - len(missing_sections),
            "items": missing_sections,
        })

    assets = [item for item in manifest.get("assets", []) if isinstance(item, dict)]
    expected_assets = int(manifest.get("assetCount", len(assets)))
    expected_asset_types = Counter(
        {
            str(key): int(value)
            for key, value in dict(manifest.get("assetTypeCounts", {})).items()
        }
    )
    if not expected_asset_types:
        expected_asset_types.update(_normalize_text(asset.get("assetType", "")) for asset in assets)
        expected_asset_types.pop("", None)

    missing_assets: list[dict[str, str]] = []
    verified_asset_types: Counter[str] = Counter()
    asset_type_verification_applicable = report_type != "incident_response"

    if asset_type_verification_applicable:
        available_assets = Counter(index["summaryRows"])
        actual_asset_types = Counter(
            {
                asset_type: sum(
                    count
                    for (row_type, _hostname, _label), count in index["summaryRows"].items()
                    if row_type == asset_type
                )
                for asset_type in ("server", "client")
            }
        )
        actual_asset_types += Counter()
        actual_assets = sum(actual_asset_types.values())

        for asset in assets:
            asset_type = _normalize_text(asset.get("assetType", ""))
            hostname = _normalize_text(asset.get("hostname", ""))
            label = _normalize_text(asset.get("assessmentLabel", ""))
            key = (asset_type, hostname, label)
            if available_assets[key] > 0:
                available_assets[key] -= 1
                verified_asset_types[asset_type] += 1
            else:
                missing_assets.append({
                    "assetId": _normalize_text(asset.get("assetId", "")),
                    "assetType": asset_type,
                    "hostname": hostname,
                    "expectedAssessment": label,
                })
    else:
        available_hosts = Counter(index["incidentAssets"])
        actual_assets = sum(available_hosts.values())
        actual_asset_types = None
        for asset in assets:
            asset_type = _normalize_text(asset.get("assetType", ""))
            hostname = _normalize_text(asset.get("hostname", ""))
            if hostname and available_hosts[hostname] > 0:
                available_hosts[hostname] -= 1
                verified_asset_types[asset_type] += 1
            else:
                missing_assets.append({
                    "assetId": _normalize_text(asset.get("assetId", "")),
                    "assetType": asset_type,
                    "hostname": hostname,
                    "expectedAssessment": _normalize_text(asset.get("assessmentLabel", "")),
                })

    verified_assets = expected_assets - len(missing_assets)
    if actual_assets != expected_assets:
        errors.append({
            "code": "ASSET_COUNT_MISMATCH",
            "message": f"asset count mismatch: expected {expected_assets}, found {actual_assets}",
            "expected": expected_assets,
            "actual": actual_assets,
        })
    if (
        asset_type_verification_applicable
        and Counter(actual_asset_types) != expected_asset_types
    ):
        errors.append({
            "code": "ASSET_TYPE_COUNT_MISMATCH",
            "message": "server/client asset counters do not match the manifest",
            "expected": _counter_dict(expected_asset_types),
            "actual": _counter_dict(Counter(actual_asset_types)),
        })
    if missing_assets:
        missing_hosts = ", ".join(
            item["hostname"] or item["assetId"] for item in missing_assets[:5]
        )
        errors.append({
            "code": "ASSET_CONCLUSION_MISSING",
            "message": f"missing assets/conclusions: {missing_hosts}",
            "count": len(missing_assets),
            "items": missing_assets,
        })

    finding_verification_applicable = report_type in _FINDING_REPORT_TYPES
    evidence_verification_applicable = finding_verification_applicable and all(
        isinstance(asset.get("findings"), list) for asset in assets
    )
    expected_findings = int(manifest.get("findingCount", 0))
    expected_evidence = int(manifest.get("evidenceCount", 0))
    expected_rules = Counter(
        {
            str(key): int(value)
            for key, value in dict(manifest.get("ruleCounts", {})).items()
        }
    )
    verified_findings: int | None = None
    actual_findings: int | None = None
    verified_evidence: int | None = None
    actual_rules: Counter[str] | None = None
    verified_rules: Counter[str] | None = None
    missing_findings: list[dict[str, str]] = []
    missing_evidence: list[dict[str, Any]] = []

    if finding_verification_applicable:
        expected_finding_entries = _expected_findings(manifest)
        actual_rows = Counter(index["findingRows"])
        actual_pairs: Counter[tuple[str, str]] = Counter()
        actual_rules = Counter()
        for (hostname, rule_id, _evidence), count in actual_rows.items():
            actual_pairs[(hostname, rule_id)] += count
            if rule_id:
                actual_rules[rule_id] += count
        available_pairs = Counter(actual_pairs)
        available_exact_rows = Counter(actual_rows)
        verified_findings = 0
        verified_evidence = 0
        verified_rules = Counter()

        for finding in expected_finding_entries:
            hostname = finding["hostname"]
            rule_id = finding["ruleId"]
            pair = (hostname, rule_id)
            if available_pairs[pair] > 0:
                available_pairs[pair] -= 1
                verified_findings += 1
                if rule_id:
                    verified_rules[rule_id] += 1
            else:
                missing_findings.append({"hostname": hostname, "ruleId": rule_id})

            evidence_text = finding["evidenceText"]
            if evidence_verification_applicable and evidence_text is not None:
                exact_key = (hostname, rule_id, evidence_text)
                if available_exact_rows[exact_key] > 0:
                    available_exact_rows[exact_key] -= 1
                    verified_evidence += int(finding["evidenceCount"])
                else:
                    missing_evidence.append({
                        "hostname": hostname,
                        "ruleId": rule_id,
                        "expectedEvidenceCount": int(finding["evidenceCount"]),
                    })

        actual_findings = sum(actual_rows.values())
        if actual_findings != expected_findings or verified_findings != expected_findings:
            errors.append({
                "code": "FINDING_COUNT_MISMATCH",
                "message": (
                    f"finding count mismatch: expected {expected_findings}, "
                    f"found {actual_findings}, verified {verified_findings}"
                ),
                "expected": expected_findings,
                "actual": actual_findings,
                "verified": verified_findings,
            })
        if actual_rules != expected_rules or verified_rules != expected_rules:
            errors.append({
                "code": "RULE_COUNT_MISMATCH",
                "message": "rule counters do not match the manifest",
                "expected": _counter_dict(expected_rules),
                "actual": _counter_dict(actual_rules),
                "verified": _counter_dict(verified_rules),
            })
        if evidence_verification_applicable and verified_evidence != expected_evidence:
            errors.append({
                "code": "EVIDENCE_COUNT_MISMATCH",
                "message": (
                    f"evidence count mismatch: expected {expected_evidence}, "
                    f"verified {verified_evidence}"
                ),
                "expected": expected_evidence,
                "verified": verified_evidence,
                "items": missing_evidence,
            })

    result = {
        "valid": not errors,
        "expectedAssets": expected_assets,
        "actualAssets": actual_assets,
        "verifiedAssets": verified_assets,
        "assetTypeVerificationApplicable": asset_type_verification_applicable,
        "expectedAssetTypes": _counter_dict(expected_asset_types),
        "actualAssetTypes": (
            _counter_dict(Counter(actual_asset_types))
            if actual_asset_types is not None
            else None
        ),
        "verifiedAssetTypes": _counter_dict(verified_asset_types),
        "expectedFindings": expected_findings,
        "actualFindings": actual_findings,
        "verifiedFindings": verified_findings,
        "findingVerificationApplicable": finding_verification_applicable,
        "expectedRules": _counter_dict(expected_rules),
        "actualRules": _counter_dict(actual_rules) if actual_rules is not None else None,
        "verifiedRules": _counter_dict(verified_rules) if verified_rules is not None else None,
        "expectedEvidence": expected_evidence,
        # DOCX stores all evidence for a finding in one formatted cell, so an
        # independent raw evidence count cannot be recovered without guessing
        # at delimiters. Exact expected cell text is verified instead.
        "actualEvidence": None,
        "verifiedEvidence": verified_evidence,
        "evidenceVerificationApplicable": evidence_verification_applicable,
        "requiredSections": required_sections,
        "expectedSections": len(required_sections),
        "verifiedSections": len(required_sections) - len(missing_sections),
        "missingSections": missing_sections,
        "missingAssets": missing_assets,
        "missingFindings": missing_findings,
        "missingEvidence": missing_evidence,
        "errors": errors,
        "errorCodes": [str(error["code"]) for error in errors],
    }
    if errors:
        codes = ", ".join(result["errorCodes"])
        detail = "; ".join(str(error["message"]) for error in errors)
        raise ReportIntegrityError(
            f"Generated DOCX failed integrity verification [{codes}] ({detail}).",
            errors=errors,
            result=result,
        )
    return result
