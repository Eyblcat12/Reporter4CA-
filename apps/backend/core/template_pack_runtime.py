"""Explicit published-pack dispatch; never replaces the default renderer."""

from __future__ import annotations

import hashlib
import io
from typing import Any

from .profile_renderer import build_profile_semantic_sources, render_profile_document
from .report_orchestrator import OrchestratedDocument, SnapshotChangedError
from .report_snapshot import thaw_json
from .rule_engine import evaluate_payload
from .template_pack import TemplatePackError, inspect_template_pack
from .template_pack_validation import _verify_rendered_content

PACK_PREFIX = "rptpack:"


def prepare_profile_payload(payload: dict[str, Any], report_type: str) -> dict[str, Any]:
    evaluated = evaluate_payload(payload)
    if report_type == "server_only":
        evaluated["clients"] = []
    elif report_type == "client_only":
        evaluated["servers"] = []
    return evaluated


def resolve_pack(catalog: Any, selector: str, report_type: str) -> tuple[bytes, Any]:
    parts = selector.split(":")
    if len(parts) != 3 or parts[0] != "rptpack":
        raise TemplatePackError("Invalid Template Pack selection.")
    payload = catalog.pack_bytes(parts[1], parts[2])
    inspection = inspect_template_pack(payload, require_publishable=True)
    if inspection.profile["reportType"] != report_type:
        raise TemplatePackError("Template Pack does not support the selected report type.")
    return payload, inspection


def published_templates(catalog: Any) -> list[dict[str, Any]]:
    result = []
    for pack_id, pack in catalog.snapshot()["packs"].items():
        for version, record in pack["versions"].items():
            selector = f"{PACK_PREFIX}{pack_id}:{version}"
            # Do not offer a corrupt or no-longer-publishable archive.
            try:
                payload, inspection = resolve_pack(catalog, selector, record["reportType"])
            except (ValueError, OSError):
                continue
            result.append(
                {
                    "id": selector,
                    "path": selector,
                    "name": f"{inspection.profile['displayName']} · {version} (Studio)",
                    "filename": f"{pack_id}-{version}.rptpack",
                    "size": len(payload),
                    "reportType": record["reportType"],
                    "isDefault": False,
                    "templateMode": "profile",
                    "compatibilityStatus": "compatible",
                    "fileHash": hashlib.sha256(payload).hexdigest(),
                }
            )
    return result


def build_published_document(
    catalog: Any, prepared: Any, *, check_cancelled=None, on_progress=None
):
    selector, expected_hash = prepared.accepted.template_key.rsplit(":", 1)
    payload, inspection = resolve_pack(catalog, selector, prepared.accepted.report_type)
    if hashlib.sha256(payload).hexdigest() != expected_hash:
        raise SnapshotChangedError("TEMPLATE_PACK_SNAPSHOT_CHANGED")
    rendered = render_profile_document(
        payload, prepared, check_cancelled=check_cancelled, on_progress=on_progress
    )
    buffer = io.BytesIO()
    rendered.document.save(buffer)
    sources = build_profile_semantic_sources(prepared, thaw_json(prepared.payload))
    issues = _verify_rendered_content(
        buffer.getvalue(), inspection.profile["slots"], sources, rendered.manifest
    )
    if issues:
        raise TemplatePackError(
            f"Profile integrity failed: {issues[0].code} ({issues[0].semantic})"
        )
    return OrchestratedDocument(
        rendered.document,
        prepared,
        rendered.manifest,
        {
            "valid": True,
            "renderer": "profile",
            "packId": inspection.pack_id,
            "packVersion": inspection.version,
        },
    )
