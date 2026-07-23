"""Validation and readiness summary for Incident Response metadata."""

from __future__ import annotations

from typing import Any


def _text(value: Any) -> str:
    return str(value or "").strip()


def assess_incident_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    """Return blocking errors, soft warnings and traceability counts for IR data."""
    data = metadata or {}
    errors: list[dict[str, Any]] = []
    warnings: list[dict[str, Any]] = []

    def issue(target: list[dict[str, Any]], code: str, field: str, message: str, row: int | None = None) -> None:
        item: dict[str, Any] = {"code": code, "field": field, "message": message}
        if row is not None:
            item["row"] = row
        target.append(item)

    if not _text(data.get("incidentId")):
        issue(errors, "missing_incident_id", "incidentId", "Chưa có mã sự cố.")
    if not _text(data.get("detectedAt")):
        issue(errors, "missing_detected_at", "detectedAt", "Chưa có thời điểm phát hiện.")

    timeline = data.get("timeline") if isinstance(data.get("timeline"), list) else []
    iocs = data.get("iocs") if isinstance(data.get("iocs"), list) else []
    action_groups = (
        ("containmentActions", "khoanh vùng"),
        ("eradicationActions", "loại bỏ"),
        ("recoveryActions", "khôi phục"),
    )

    if not timeline:
        issue(errors, "missing_timeline", "timeline", "Timeline phải có ít nhất một sự kiện.")

    known_iocs = {_text(item.get("value")) for item in iocs if isinstance(item, dict) and _text(item.get("value"))}
    evidence_refs: set[str] = set()
    for index, event in enumerate(timeline, start=1):
        event = event if isinstance(event, dict) else {}
        if not _text(event.get("event")):
            issue(errors, "missing_timeline_event", "timeline", "Sự kiện timeline chưa có mô tả.", index)
        if not _text(event.get("time")):
            issue(warnings, "missing_timeline_time", "timeline", "Sự kiện timeline chưa có thời gian.", index)
        evidence = _text(event.get("evidence"))
        if evidence:
            evidence_refs.add(evidence)
        else:
            issue(warnings, "missing_timeline_evidence", "timeline", "Sự kiện timeline chưa liên kết evidence.", index)
        related = [part.strip() for part in _text(event.get("relatedIocs")).split(",") if part.strip()]
        for value in related:
            if value not in known_iocs:
                issue(warnings, "unknown_related_ioc", "timeline", f"IoC liên quan '{value}' chưa có trong danh sách IoC.", index)

    for index, ioc in enumerate(iocs, start=1):
        ioc = ioc if isinstance(ioc, dict) else {}
        if not _text(ioc.get("type")) or not _text(ioc.get("value")):
            issue(errors, "invalid_ioc", "iocs", "IoC phải có cả loại và giá trị.", index)
        source = _text(ioc.get("source"))
        if source:
            evidence_refs.add(source)
        else:
            issue(warnings, "missing_ioc_source", "iocs", "IoC chưa có nguồn evidence.", index)

    action_count = 0
    completed_count = 0
    for field, label in action_groups:
        actions = data.get(field) if isinstance(data.get(field), list) else []
        action_count += len(actions)
        for index, action in enumerate(actions, start=1):
            action = action if isinstance(action, dict) else {}
            if not _text(action.get("action")):
                issue(errors, "missing_action", field, f"Hành động {label} chưa có mô tả.", index)
            if _text(action.get("status")).lower() in {"done", "completed", "complete", "đã hoàn thành", "hoàn thành"}:
                completed_count += 1
            if not _text(action.get("owner")):
                issue(warnings, "missing_action_owner", field, f"Hành động {label} chưa có người phụ trách.", index)
            evidence = _text(action.get("evidence"))
            if evidence:
                evidence_refs.add(evidence)
            else:
                issue(warnings, "missing_action_evidence", field, f"Hành động {label} chưa liên kết evidence.", index)

    return {
        "valid": not errors,
        "errors": errors,
        "warnings": warnings,
        "summary": {
            "timelineEvents": len(timeline),
            "iocs": len(iocs),
            "actions": action_count,
            "completedActions": completed_count,
            "evidenceReferences": len(evidence_refs),
            "errors": len(errors),
            "warnings": len(warnings),
        },
    }
