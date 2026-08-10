"""Versioned, evidence-first detection rules for local report automation."""

from __future__ import annotations

import json
import re
from copy import deepcopy
from pathlib import Path
from typing import Any

DEFAULT_RULES_PATH = Path(__file__).resolve().parent.parent / "config" / "detection_rules.json"
ALLOWED_SEVERITIES = {"informational", "low", "medium", "high", "critical"}
ALLOWED_CLASSIFICATIONS = {"informational", "insufficient_data", "needs_review", "anomaly"}
STANDARD_ASSESSMENTS = {
    "clean": "Không phát hiện dấu hiệu bất thường",
    "insufficient_data": "Không đủ dữ liệu để kết luận",
    "needs_review": "Ghi nhận dấu hiệu cần xác minh",
    "anomaly": "Ghi nhận dấu hiệu bất thường",
}


def validate_rule(rule: dict[str, Any]) -> dict[str, Any]:
    """Validate and normalize a declarative rule; arbitrary code is never accepted."""
    normalized = deepcopy(rule)
    name = str(normalized.get("name", "")).strip()
    if not name:
        raise ValueError("Tên rule không được để trống")
    severity = str(normalized.get("severity", "medium"))
    classification = str(normalized.get("classification", "needs_review"))
    if severity not in ALLOWED_SEVERITIES:
        raise ValueError("Mức độ rule không hợp lệ")
    if classification not in ALLOWED_CLASSIFICATIONS:
        raise ValueError("Phân loại rule không hợp lệ")
    conditions = normalized.get("conditions")
    if not isinstance(conditions, dict):
        raise ValueError("Rule phải có conditions")
    fields = [str(item).strip() for item in conditions.get("fields", []) if str(item).strip()]
    allowed_fields = {
        "type",
        "hostname",
        "ip",
        "os",
        "result",
        "notes",
        "software",
        "process",
        "installed_software",
    }
    if not fields or any(field not in allowed_fields for field in fields):
        raise ValueError("Trường tìm kiếm không hợp lệ")
    contains_any = [
        str(item).strip() for item in conditions.get("containsAny", []) if str(item).strip()
    ]
    regex_any = [str(item).strip() for item in conditions.get("regexAny", []) if str(item).strip()]
    if not contains_any and not regex_any:
        raise ValueError("Cần ít nhất một từ khóa hoặc biểu thức tìm kiếm")
    if len(contains_any) > 50 or len(regex_any) > 10:
        raise ValueError("Rule có quá nhiều điều kiện")
    for pattern in regex_any:
        if len(pattern) > 200:
            raise ValueError("Biểu thức tìm kiếm quá dài")
        re.compile(pattern)
    normalized.update(
        {
            "name": name,
            "version": str(normalized.get("version", "1")),
            "severity": severity,
            "classification": classification,
            "enabled": bool(normalized.get("enabled", True)),
        }
    )
    normalized["conditions"] = {
        "fields": fields,
        "containsAny": contains_any,
        "containsAll": [
            str(item).strip() for item in conditions.get("containsAll", []) if str(item).strip()
        ],
        "excludeContainsAny": [
            str(item).strip()
            for item in conditions.get("excludeContainsAny", [])
            if str(item).strip()
        ],
        "regexAny": regex_any,
        "assetTypes": [
            str(item).strip().lower()
            for item in conditions.get("assetTypes", [])
            if str(item).strip()
        ],
    }
    return normalized


def load_rule_pack(path: str | Path | None = None) -> dict[str, Any]:
    source = Path(path) if path else DEFAULT_RULES_PATH
    payload = json.loads(source.read_text(encoding="utf-8"))
    if not isinstance(payload.get("rules"), list):
        raise ValueError("Rule pack must contain a rules array")
    seen: set[str] = set()
    for rule in payload["rules"]:
        rule_id = str(rule.get("id", "")).strip()
        if not rule_id or rule_id in seen:
            raise ValueError(f"Rule id is missing or duplicated: {rule_id}")
        seen.add(rule_id)
        if rule.get("severity") not in ALLOWED_SEVERITIES:
            raise ValueError(f"Invalid severity for rule {rule_id}")
        if rule.get("classification") not in ALLOWED_CLASSIFICATIONS:
            raise ValueError(f"Invalid classification for rule {rule_id}")
    return payload


def evaluate_asset(
    asset: dict[str, Any], rules: list[dict[str, Any]], *, disabled_rule_ids: set[str] | None = None
) -> list[dict[str, Any]]:
    disabled = disabled_rule_ids or set()
    findings: list[dict[str, Any]] = []
    for rule in rules:
        rule_id = str(rule.get("id", ""))
        if not rule.get("enabled", True) or rule_id in disabled:
            continue
        conditions = rule.get("conditions", {})
        asset_types = {str(item).lower() for item in conditions.get("assetTypes", [])}
        if asset_types and str(asset.get("type", "")).lower() not in asset_types:
            continue
        evidence = _match_evidence(asset, conditions)
        if not evidence:
            continue
        findings.append(
            {
                "ruleId": rule_id,
                "ruleVersion": str(rule.get("version", "1")),
                "source": str(
                    rule.get("source") or ("custom" if rule_id.startswith("CUSTOM_") else "builtin")
                ),
                "name": str(rule.get("name", rule_id)),
                "severity": rule["severity"],
                "classification": rule["classification"],
                "evidence": evidence,
                "remediation": str(rule.get("remediation", "")),
                "mitre": deepcopy(rule.get("mitre", [])),
            }
        )
    return findings


def _match_evidence(asset: dict[str, Any], conditions: dict[str, Any]) -> list[dict[str, str]]:
    fields = conditions.get("fields") or ["result", "notes"]
    contains_any = [str(item).casefold() for item in conditions.get("containsAny", [])]
    contains_all = [str(item).casefold() for item in conditions.get("containsAll", [])]
    excludes = [str(item).casefold() for item in conditions.get("excludeContainsAny", [])]
    regexes = [re.compile(str(item), re.IGNORECASE) for item in conditions.get("regexAny", [])]
    evidence: list[dict[str, str]] = []
    combined = "\n".join(str(asset.get(field, "")) for field in fields).casefold()
    if any(term and term in combined for term in excludes):
        return []
    if contains_all and not all(term in combined for term in contains_all):
        return []
    for field in fields:
        raw = str(asset.get(field, "")).strip()
        folded = raw.casefold()
        matches = [term for term in contains_any if term and term in folded]
        matches.extend(match.group(0) for pattern in regexes if (match := pattern.search(raw)))
        if matches:
            evidence.append(
                {"field": str(field), "value": raw, "matched": ", ".join(dict.fromkeys(matches))}
            )
    return evidence


def evaluate_payload(
    payload: dict[str, Any], *, disabled_rule_ids: list[str] | None = None
) -> dict[str, Any]:
    result = deepcopy(payload)
    pack = load_rule_pack()
    metadata = result.get("metadata", {}) if isinstance(result.get("metadata"), dict) else {}
    rule_settings = (
        metadata.get("ruleSettings", {}) if isinstance(metadata.get("ruleSettings"), dict) else {}
    )
    configured_disabled = rule_settings.get("disabledRuleIds", metadata.get("disabledRuleIds", []))
    disabled = set(
        disabled_rule_ids if disabled_rule_ids is not None else configured_disabled or []
    )
    custom_rules = rule_settings.get("customRules", [])
    validated_custom = [validate_rule(rule) for rule in custom_rules if isinstance(rule, dict)]
    rules = [*pack["rules"], *validated_custom]
    finding_count = 0
    assessment_counts = {
        "clean": 0,
        "insufficient_data": 0,
        "needs_review": 0,
        "anomaly": 0,
    }
    for section in ("servers", "clients"):
        for asset_index, asset in enumerate(result.get(section, [])):
            findings = evaluate_asset(asset, rules, disabled_rule_ids=disabled)
            if not str(asset.get("result", "")).strip():
                findings.append(
                    {
                        "ruleId": "SOURCE_RESULT_MISSING",
                        "ruleVersion": "1",
                        "source": "data_quality",
                        "name": "Missing source assessment result",
                        "severity": "informational",
                        "classification": "insufficient_data",
                        "evidence": [{"field": "result", "value": "", "matched": "<missing>"}],
                        "remediation": "Complete the source assessment result before final approval.",
                        "mitre": [],
                    }
                )
            asset["findings"] = findings
            assessment = assess_asset(findings)
            asset["assessment"] = {
                **assessment,
                "assetId": f"{section}:{asset_index}",
                "findingCount": len(findings),
                "evidenceCount": sum(len(item.get("evidence", [])) for item in findings),
            }
            finding_count += len(findings)
            assessment_counts[assessment["classification"]] += 1
    metadata = result.setdefault("metadata", {})
    metadata["ruleEngine"] = {
        "schemaVersion": pack.get("schemaVersion", "1.0"),
        "disabledRuleIds": sorted(disabled),
        "findingCount": finding_count,
        "customRuleCount": len(validated_custom),
        "assessmentCounts": assessment_counts,
    }
    return result


def assess_asset(findings: list[dict[str, Any]] | None) -> dict[str, str]:
    """Return the canonical, evidence-backed conclusion for one asset."""
    evidence_backed = [item for item in (findings or []) if item.get("evidence")]
    for classification in ("anomaly", "needs_review", "insufficient_data"):
        if any(item.get("classification") == classification for item in evidence_backed):
            return {
                "classification": classification,
                "label": STANDARD_ASSESSMENTS[classification],
            }
    return {"classification": "clean", "label": STANDARD_ASSESSMENTS["clean"]}


def assessment_text(findings: list[dict[str, Any]] | None) -> str:
    """Return a conservative, standardized Vietnamese report conclusion."""
    return assess_asset(findings)["label"]


def find_rule_conflicts(rules: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Find overlapping declarative rules without treating overlap as an error."""
    conflicts: list[dict[str, Any]] = []
    enabled = [rule for rule in rules if rule.get("enabled", True)]
    for index, left in enumerate(enabled):
        left_conditions = left.get("conditions", {})
        left_fields = {str(item) for item in left_conditions.get("fields", [])}
        left_terms = {
            str(item).strip().casefold()
            for item in left_conditions.get("containsAny", [])
            if str(item).strip()
        }
        for right in enabled[index + 1 :]:
            right_conditions = right.get("conditions", {})
            shared_fields = sorted(
                left_fields & {str(item) for item in right_conditions.get("fields", [])}
            )
            shared_terms = sorted(
                left_terms
                & {
                    str(item).strip().casefold()
                    for item in right_conditions.get("containsAny", [])
                    if str(item).strip()
                }
            )
            if not shared_fields or not shared_terms:
                continue
            conflicts.append(
                {
                    "ruleIds": [str(left.get("id", "")), str(right.get("id", ""))],
                    "ruleNames": [str(left.get("name", "")), str(right.get("name", ""))],
                    "sharedFields": shared_fields,
                    "sharedTerms": shared_terms,
                    "classificationConflict": left.get("classification")
                    != right.get("classification"),
                }
            )
    return conflicts
