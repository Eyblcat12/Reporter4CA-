"""FastAPI routes — toan bo REST API endpoints cho Reporter Pro."""

from __future__ import annotations

import base64
import json
import re
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from starlette.background import BackgroundTask

from api.models import (
    ColumnPreviewRequest,
    ColumnPreviewResponse,
    DataQualitySummary,
    DetectionRuleRequest,
    EvaluateRuleRequest,
    GenerateRequest,
    ImportFileRequest,
    ImportRulesRequest,
    NormalizeRawRequest,
    PreviewDocxRequest,
    PreviewRequest,
    ReportType,
    SaveAsTemplateRequest,
    SavePresetRequest,
    SheetSelectRequest,
    UpdateTemplateRequest,
    UploadTemplateRequest,
    TemplateVersionRequest,
    ValidateIncidentRequest,
    ValidateRowsRequest,
    ValidateRowsResponse,
    ValidationIssue,
)
from core.column_mapper import auto_detect_mapping, apply_mapping
from core.config import APP_NAME, APP_VERSION, allow_custom_runtime_paths, max_import_bytes, max_report_rows
from core.database import get_db, file_sha256
from core.data_quality import assess_rows
from core.docx_field_updater import FieldUpdateResult, refresh_docx_fields
from core.gui_state import build_payload_from_rows, normalized_payload_to_rows, summarize_rows
from core.input_parser import normalize_payload, parse_input
from core.input_preprocessor import DEFAULT_SECTION, parse_delimited_text
from core.incident_validation import assess_incident_metadata
from core.report_generator import generate_report, render_preview_text, save_report
from core.report_jobs import JobCancelled, ReportJob, ReportJobManager
from core.rule_engine import evaluate_asset, find_rule_conflicts, load_rule_pack, validate_rule
from core.template_analyzer import (
    MAX_TEMPLATE_SIZE,
    analyze_template,
    sanitize_filename,
    validate_docx_bytes,
)
from core.template_schema import compare_template_analysis
from core.workspace_backup import create_workspace_backup

import sys

PROJECT_ROOT = Path(__file__).resolve().parent.parent
BUNDLE_ROOT = Path(getattr(sys, "_MEIPASS", PROJECT_ROOT))
DEFAULT_PLUGINS_DIR = BUNDLE_ROOT / "plugins"
SAMPLES_DIR = BUNDLE_ROOT / "samples"
TEMPLATES_DIR = BUNDLE_ROOT / "templates"
GENERATED_REPORTS_DIR = BUNDLE_ROOT / "data" / "generated"

router = APIRouter(prefix="/api")

# Store last generated report path for save-as-template
_last_generated: dict[str, Path] = {}
_report_jobs = ReportJobManager(max_workers=1, max_pending=2)
_REPORT_TYPES = {item.value for item in ReportType}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _template_report_type(file_path: Path) -> str:
    try:
        relative = file_path.relative_to(TEMPLATES_DIR)
    except ValueError:
        return ReportType.FULL.value
    if len(relative.parts) > 1 and relative.parts[0] in _REPORT_TYPES:
        return relative.parts[0]
    return ReportType.FULL.value


def _metadata_with_custom_rules(metadata: dict[str, Any] | None) -> dict[str, Any]:
    """Snapshot active custom rules so preview and background jobs are reproducible."""
    result = dict(metadata or {})
    settings = dict(result.get("ruleSettings") or {})
    settings["customRules"] = get_db().list_detection_rules()
    result["ruleSettings"] = settings
    return result


def _managed_template_path(value: str | Path) -> Path:
    """Resolve a database-backed template path inside the managed template root."""
    root = TEMPLATES_DIR.resolve()
    candidate = Path(value).expanduser().resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise HTTPException(409, "Template path is outside the managed directory.") from exc
    if candidate.suffix.lower() != ".docx":
        raise HTTPException(409, "Managed template must be a DOCX file.")
    return candidate


def _default_template_path(report_type: ReportType | str) -> str | None:
    report_type_value = report_type.value if isinstance(report_type, ReportType) else str(report_type)
    db = get_db()
    registered = db.get_default_template(report_type_value)
    if registered:
        try:
            registered_path = _managed_template_path(registered["file_path"])
            if registered_path.exists():
                return str(registered_path)
        except HTTPException:
            pass

    category_dir = TEMPLATES_DIR / report_type_value
    if category_dir.exists():
        candidates = sorted(
            path for path in category_dir.glob("*.docx") if not path.name.startswith("~")
        )
        if candidates:
            return str(candidates[0])

    fallback = TEMPLATES_DIR / "report_template.docx"
    return str(fallback) if fallback.exists() else None

def _load_plugins(plugins_dir: str | Path = "", disable: bool = False) -> list[Any]:
    if disable:
        return []
    try:
        from plugins.manager import load_plugins
        target = Path(str(plugins_dir or "")).expanduser()
        if str(target) in {"", "."}:
            target = DEFAULT_PLUGINS_DIR
        elif not allow_custom_runtime_paths():
            return []
        return load_plugins(target)
    except Exception:
        return []


def _apply_input_plugins(data: dict, plugins: list) -> dict:
    try:
        from plugins.manager import apply_input_plugins
        return apply_input_plugins(data, plugins)
    except Exception:
        return data


def _apply_document_plugins(document: Any, data: dict, plugins: list) -> Any:
    try:
        from plugins.manager import apply_document_plugins
        return apply_document_plugins(document, data, plugins)
    except Exception:
        return document


def _build_web_bundle(data: dict[str, Any]) -> dict[str, Any]:
    rows = normalized_payload_to_rows(data)
    counts = summarize_rows(rows)
    return {
        "payload": data,
        "rows": rows,
        "counts": counts,
        "previewText": render_preview_text(data),
    }


def _decode_base64(content_base64: str, *, max_bytes: int | None = None) -> bytes:
    """Decode an upload with strict validation and an optional size ceiling."""
    payload = content_base64.strip()
    if "," in payload and ";base64" in payload:
        payload = payload.split(",", 1)[1]
    payload = re.sub(r"\s+", "", payload)
    if not payload:
        raise HTTPException(400, "Dữ liệu base64 trống hoặc không hợp lệ.")

    if max_bytes is not None:
        encoded_limit = ((max_bytes + 2) // 3) * 4
        if len(payload) > encoded_limit + 4:
            raise HTTPException(413, f"File vượt quá giới hạn {max_bytes // 1024 // 1024} MB.")

    try:
        decoded = base64.b64decode(payload, validate=True)
    except (ValueError, base64.binascii.Error) as exc:
        raise HTTPException(400, "Dữ liệu base64 không hợp lệ.") from exc

    if max_bytes is not None and len(decoded) > max_bytes:
        raise HTTPException(413, f"File vượt quá giới hạn {max_bytes // 1024 // 1024} MB.")
    return decoded


def _payload_from_rows(rows: list[dict], metadata: dict | None = None) -> dict:
    payload = build_payload_from_rows(rows)
    payload["metadata"] = metadata if isinstance(metadata, dict) else {}
    return normalize_payload(payload, source="web_rows")


def _suggest_filename(body_name: str) -> str:
    raw = (body_name or "").strip()
    if raw:
        sanitized = "".join(c if c.isalnum() or c in {"-", "_", "."} else "-" for c in raw)
        return sanitized if sanitized.lower().endswith(".docx") else f"{sanitized}.docx"
    return "reporter-output.docx"


def _compatibility_fields(analysis: dict[str, Any]) -> dict[str, str]:
    compatibility = analysis.get("compatibility", {})
    return {
        "compatibility_status": compatibility.get("status", "unknown"),
        "compatibility_version": compatibility.get("version", ""),
        "compatibility_json": json.dumps(compatibility, ensure_ascii=False),
    }


def _assert_template_compatible(template_path: str | None) -> None:
    if not template_path:
        return
    template = get_db().get_template_by_path(str(Path(template_path)))
    resolved = Path(template_path).expanduser().resolve()
    managed_root = TEMPLATES_DIR.resolve()
    if not template and not allow_custom_runtime_paths() and not resolved.is_relative_to(managed_root):
        raise HTTPException(403, "Custom template paths are disabled in local/team safe mode.")
    if template and template.get("compatibility_status") == "incompatible":
        raise HTTPException(422, "Template is incompatible. Review its compatibility report before generating.")


def _assert_report_size(rows: list[dict[str, Any]]) -> None:
    limit = max_report_rows()
    if len(rows) > limit:
        raise HTTPException(413, f"Report contains {len(rows)} rows; local limit is {limit}.")


def _save_finalized_report(document: Any, output_path: str | Path) -> tuple[Path, FieldUpdateResult]:
    """Save a report, then refresh calculated fields without risking the file."""
    saved_path = save_report(document, output_path)
    field_update = refresh_docx_fields(saved_path)
    if not field_update.updated:
        print(
            f"[Reporter Pro] DOCX field update deferred: {field_update.detail}",
            flush=True,
        )
    return saved_path, field_update


def _create_report_artifact(
    req: GenerateRequest,
    *,
    on_progress: Any | None = None,
    check_cancelled: Any | None = None,
) -> dict[str, Any]:
    """Generate one DOCX and record exactly one terminal history entry."""
    started_at = time.perf_counter()
    template_path = ""
    output_path: Path | None = None
    temporary_path: Path | None = None
    history_recorded = False

    def progress(phase: str, value: int, message: str) -> None:
        if check_cancelled:
            check_cancelled()
        if on_progress:
            on_progress(phase, value, message)

    def record(status: str, *, filename: str = "", error_code: str = "") -> str:
        nonlocal history_recorded
        try:
            db = get_db()
            template_record = (
                db.get_template_by_path(str(Path(template_path))) if template_path else None
            )
            report_id = db.add_report(
                title=req.title,
                organization=req.organization,
                report_type=req.report_type.value,
                row_count=len(req.rows),
                server_count=sum(1 for row in req.rows if row.get("type") == "server"),
                client_count=sum(1 for row in req.rows if row.get("type") == "client"),
                output_filename=filename,
                output_path=str(output_path) if output_path else "",
                file_size=output_path.stat().st_size if output_path and output_path.exists() else 0,
                status=status,
                duration_ms=round((time.perf_counter() - started_at) * 1000),
                error_code=error_code,
                template_id=template_record["id"] if template_record else None,
            )
            history_recorded = True
            return report_id
        except Exception:
            return ""

    try:
        _assert_report_size(req.rows)
        progress("validating", 10, "Đang kiểm tra chất lượng dữ liệu")
        quality = assess_rows(req.rows)
        if not req.rows:
            raise HTTPException(400, "Khong co du lieu de tao bao cao.")
        if not quality["valid"]:
            raise HTTPException(422, {
                "message": "Dữ liệu còn lỗi nghiêm trọng. Hãy sửa trước khi tạo báo cáo.",
                "quality": quality,
            })

        metadata = _metadata_with_custom_rules({
            **(req.metadata or {}), "dataQuality": quality["summary"]
        })
        if req.report_type == ReportType.INCIDENT_RESPONSE:
            incident_quality = assess_incident_metadata(metadata)
            if not incident_quality["valid"]:
                raise HTTPException(422, {
                    "message": "Thông tin Incident Response còn lỗi nghiêm trọng.",
                    "incidentQuality": incident_quality,
                })
            metadata["incidentQuality"] = incident_quality["summary"]
        payload = _payload_from_rows(req.rows, metadata)
        progress("processing", 25, "Đang chuẩn hóa dữ liệu và chạy plugin")
        plugins = _load_plugins(req.plugins_dir, req.disable_plugins)
        processed = _apply_input_plugins(payload, plugins)
        template_path = req.template_path or _default_template_path(req.report_type)
        _assert_template_compatible(template_path)

        progress("generating", 45, "Đang tạo nội dung DOCX")
        document = generate_report(
            processed,
            title=req.title or "BAO CAO DFIR / COMPROMISE ASSESSMENT",
            organization=req.organization or "",
            assessment_date=req.assessment_date or None,
            template_path=template_path,
            report_type=req.report_type.value,
        )
        progress("plugins", 68, "Đang hoàn thiện nội dung")
        document = _apply_document_plugins(document, processed, plugins)

        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as temporary:
            temporary_path = Path(temporary.name)
        progress("finalizing", 82, "Đang cập nhật mục lục và fields")
        output_path, field_update = _save_finalized_report(document, temporary_path)
        progress("recording", 94, "Đang lưu lịch sử")
        filename = _suggest_filename(req.output_name)
        report_id = record("success", filename=filename)
        if report_id:
            _last_generated[report_id] = output_path
        return {
            "outputPath": str(output_path),
            "filename": filename,
            "reportId": report_id,
            "fieldEngine": field_update.engine,
        }
    except JobCancelled:
        if not history_recorded:
            record("cancelled", error_code="CANCELLED")
        (output_path or temporary_path) and (output_path or temporary_path).unlink(missing_ok=True)
        raise
    except HTTPException:
        (output_path or temporary_path) and (output_path or temporary_path).unlink(missing_ok=True)
        raise
    except Exception as exc:
        if not history_recorded:
            record("failed", error_code=type(exc).__name__)
        (output_path or temporary_path) and (output_path or temporary_path).unlink(missing_ok=True)
        raise


# ---------------------------------------------------------------------------
# GET endpoints
# ---------------------------------------------------------------------------

@router.get("/health")
async def health():
    plugins = _load_plugins()
    return {
        "status": "ok",
        "app": APP_NAME,
        "version": APP_VERSION,
        "databaseSchema": get_db().schema_version,
        "plugins": [
            {"name": p.name(), "version": getattr(p, "version", "0.0.0")}
            for p in plugins
        ],
    }


@router.get("/system/backup")
async def download_workspace_backup():
    """Download a consistent local backup of SQLite state and DOCX templates."""
    with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as temporary:
        backup_path = Path(temporary.name)

    try:
        manifest = create_workspace_backup(
            get_db(),
            TEMPLATES_DIR,
            backup_path,
            app_version=APP_VERSION,
        )
    except Exception as exc:
        backup_path.unlink(missing_ok=True)
        raise HTTPException(status_code=500, detail=f"Không thể tạo backup: {exc}") from exc

    timestamp = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M%S")
    return FileResponse(
        path=str(backup_path),
        media_type="application/zip",
        filename=f"reporter-pro-backup-{timestamp}.zip",
        headers={
            "X-Backup-Schema": str(manifest["schemaVersion"]),
            "X-Backup-Templates": str(len(manifest["templates"])),
        },
        background=BackgroundTask(backup_path.unlink, missing_ok=True),
    )


@router.get("/sample")
async def sample():
    sample_path = SAMPLES_DIR / "input.json"
    if not sample_path.exists():
        raise HTTPException(404, "Sample file not found.")
    data = parse_input(sample_path, default_section="servers")
    return _build_web_bundle(data)


@router.get("/rules")
async def list_detection_rules():
    """Return immutable built-ins plus editable local/team rules."""
    pack = load_rule_pack()
    builtins = [{**rule, "source": "builtin", "editable": False} for rule in pack["rules"]]
    return {
        "schemaVersion": pack.get("schemaVersion", "1.0"),
        "rules": [*builtins, *get_db().list_detection_rules()],
    }


@router.post("/rules", status_code=201)
async def create_detection_rule(req: DetectionRuleRequest):
    try:
        rule = validate_rule(req.model_dump())
        return get_db().save_detection_rule(rule)
    except (ValueError, re.error) as exc:
        raise HTTPException(422, str(exc))


@router.get("/rules/export")
async def export_detection_rules():
    rules = []
    for rule in get_db().list_detection_rules():
        rules.append({
            key: value for key, value in rule.items()
            if key not in {"createdAt", "updatedAt", "source", "editable", "archived"}
        })
    return {
        "schemaVersion": "1.0", "exportedAt": datetime.now(timezone.utc).isoformat(),
        "rules": rules,
    }


@router.post("/rules/import")
async def import_detection_rules(req: ImportRulesRequest):
    if not req.rules:
        raise HTTPException(422, "Gói import không có rule")
    if len(req.rules) > 100:
        raise HTTPException(422, "Mỗi lần chỉ được import tối đa 100 rule")
    db = get_db()
    existing_names = {rule["name"].casefold() for rule in db.list_detection_rules()}
    imported, skipped, errors = [], [], []
    for index, candidate in enumerate(req.rules):
        try:
            clean = {
                key: value for key, value in candidate.items()
                if key not in {"id", "createdAt", "updatedAt", "source", "editable", "archived"}
            }
            rule = validate_rule(clean)
            original_name = rule["name"]
            if original_name.casefold() in existing_names:
                if req.strategy == "skip":
                    skipped.append({"index": index, "name": original_name, "reason": "duplicate_name"})
                    continue
                suffix = 2
                renamed = f"{original_name} (imported)"
                while renamed.casefold() in existing_names:
                    renamed = f"{original_name} (imported {suffix})"
                    suffix += 1
                rule["name"] = renamed
            saved = db.save_detection_rule(rule)
            existing_names.add(saved["name"].casefold())
            imported.append(saved)
        except (ValueError, re.error, TypeError) as exc:
            errors.append({"index": index, "name": str(candidate.get("name", "")), "reason": str(exc)})
    return {"imported": imported, "skipped": skipped, "errors": errors}


@router.get("/rules/conflicts")
async def detection_rule_conflicts():
    pack = load_rule_pack()
    rules = [*pack["rules"], *get_db().list_detection_rules()]
    return {"conflicts": find_rule_conflicts(rules)}


@router.post("/rules/{rule_id}/clone", status_code=201)
async def clone_detection_rule(rule_id: str):
    source = get_db().get_detection_rule(rule_id)
    if not source:
        source = next((rule for rule in load_rule_pack()["rules"] if rule.get("id") == rule_id), None)
    if not source:
        raise HTTPException(404, "Không tìm thấy rule")
    clone = {
        key: value for key, value in source.items()
        if key not in {"id", "createdAt", "updatedAt", "source", "editable", "archived"}
    }
    clone["name"] = f"{source['name']} (copy)"
    clone["version"] = "1"
    return get_db().save_detection_rule(validate_rule(clone))


@router.patch("/rules/{rule_id}")
async def update_detection_rule(rule_id: str, req: DetectionRuleRequest):
    if not rule_id.startswith("CUSTOM_"):
        raise HTTPException(403, "Rule mặc định không thể chỉnh sửa")
    try:
        rule = validate_rule({**req.model_dump(), "id": rule_id})
        updated = get_db().update_detection_rule(rule_id, rule)
        if not updated:
            raise HTTPException(404, "Không tìm thấy rule")
        return updated
    except (ValueError, re.error) as exc:
        raise HTTPException(422, str(exc))


@router.get("/rules/{rule_id}/versions")
async def list_detection_rule_versions(rule_id: str):
    if not get_db().get_detection_rule(rule_id):
        raise HTTPException(404, "Không tìm thấy rule")
    return {"versions": get_db().list_detection_rule_versions(rule_id)}


@router.post("/rules/{rule_id}/versions/{version_number}/rollback")
async def rollback_detection_rule(rule_id: str, version_number: int):
    if not rule_id.startswith("CUSTOM_"):
        raise HTTPException(403, "Rule mặc định không thể khôi phục phiên bản")
    restored = get_db().rollback_detection_rule(rule_id, version_number)
    if not restored:
        raise HTTPException(404, "Không tìm thấy phiên bản rule")
    return restored


@router.post("/rules/evaluate")
async def evaluate_detection_rule(req: EvaluateRuleRequest):
    """Dry-run a draft rule against current imported rows without persisting it."""
    try:
        rule = validate_rule(req.rule.model_dump())
    except (ValueError, re.error) as exc:
        raise HTTPException(422, str(exc))
    matches = []
    for index, row in enumerate(req.rows):
        findings = evaluate_asset(row, [rule])
        if findings:
            matches.append({
                "row": index,
                "hostname": row.get("hostname", ""),
                "type": row.get("type", ""),
                "evidence": findings[0]["evidence"],
            })
    return {"matchedRows": len(matches), "totalRows": len(req.rows), "matches": matches[:100]}


@router.get("/templates")
async def list_templates():
    db = get_db()
    # Seed default template if not in DB yet
    default_tpl = TEMPLATES_DIR / "report_template.docx"
    db.seed_default_template(default_tpl)
    # Also scan for any DOCX in templates/ not yet in DB
    if TEMPLATES_DIR.exists():
        for f in TEMPLATES_DIR.rglob("*.docx"):
            if f.suffix.lower() == ".docx" and not f.name.startswith("~") and "_versions" not in f.parts:
                existing = db.get_template_by_filename(f.name)
                if not existing:
                    report_type = _template_report_type(f)
                    analysis = analyze_template(f, report_type)
                    tid = db.add_template(
                        name=f.stem.replace("_", " ").title(),
                        filename=f.name,
                        file_path=str(f),
                        file_size=f.stat().st_size,
                        file_hash=file_sha256(f),
                        has_tokens=analysis.get("has_tokens", False),
                        template_mode=analysis.get("template_mode", "cover"),
                        report_type=report_type,
                        table_count=analysis.get("table_count", 0),
                        heading_count=analysis.get("heading_count", 0),
                        **_compatibility_fields(analysis),
                    )
                    if analysis.get("compatibility", {}).get("status") != "incompatible" and not db.get_default_template(report_type):
                        db.set_default_template(tid)
    rows = db.list_templates()
    templates = []
    for r in rows:
        templates.append({
            "id": r["id"],
            "name": r["name"],
            "filename": r["filename"],
            "path": r["file_path"],
            "size": r["file_size"],
            "fileHash": r.get("file_hash", ""),
            "isDefault": bool(r["is_default"]),
            "isGenerated": bool(r.get("is_generated", 0)),
            "hasTokens": bool(r.get("has_tokens", 0)),
            "templateMode": r.get("template_mode", "cover"),
            "reportType": r.get("report_type", ReportType.FULL.value),
            "tableCount": r.get("table_count", 0),
            "headingCount": r.get("heading_count", 0),
            "compatibilityStatus": r.get("compatibility_status", "unknown"),
            "compatibilityVersion": r.get("compatibility_version", ""),
            "compatibility": json.loads(r.get("compatibility_json") or "{}"),
            "description": r.get("description", ""),
            "createdAt": r.get("created_at", ""),
        })
    return {"templates": templates}


# ---------------------------------------------------------------------------
# POST endpoints
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Smart header detection helpers
# ---------------------------------------------------------------------------

def _is_header_like(value: Any) -> bool:
    """Kiểm tra xem giá trị có giống tên cột (header) hay không.
    Header thường là chuỗi text, không phải số hay ngày tháng."""
    if value is None or (isinstance(value, float) and str(value) == 'nan'):
        return False
    s = str(value).strip()
    if not s:
        return False
    # Loại bỏ các giá trị là số thuần tuý
    try:
        float(s.replace(",", ""))
        return False
    except ValueError:
        pass
    # Loại bỏ giá trị giống ngày tháng (yyyy-mm-dd, dd/mm/yyyy, ...)
    if re.match(r"^\d{1,4}[/\-.]\d{1,2}[/\-.]\d{1,4}", s):
        return False
    return True


def _detect_header_row(tmp_path: Path, suffix: str, sheet_name: str | None = None, max_scan: int = 10) -> int:
    """Quét tối đa max_scan dòng đầu, chấm điểm mỗi dòng theo số ô
    trông giống header. Trả về chỉ số dòng (0-indexed) phù hợp nhất."""
    import pandas as pd

    read_kwargs: dict[str, Any] = {"header": None, "nrows": max_scan}
    if suffix in {".xlsx", ".xls"}:
        if sheet_name:
            read_kwargs["sheet_name"] = sheet_name
        raw_df = pd.read_excel(tmp_path, **read_kwargs)
    elif suffix == ".csv":
        raw_df = pd.read_csv(tmp_path, **read_kwargs)
    else:
        return 0

    if raw_df.empty:
        return 0

    best_row = 0
    best_score = 0
    for idx in range(len(raw_df)):
        row_values = raw_df.iloc[idx]
        score = sum(1 for v in row_values if _is_header_like(v))
        if score > best_score:
            best_score = score
            best_row = idx

    return best_row


def _read_with_header(tmp_path: Path, suffix: str, header_row: int,
                      sheet_name: str | None = None, nrows: int = 50) -> tuple[list[str], "pd.DataFrame"]:
    """Đọc file với header_row chỉ định, trả về (columns, DataFrame)."""
    import pandas as pd

    if suffix in {".xlsx", ".xls"}:
        kw: dict[str, Any] = {"header": header_row, "nrows": nrows}
        if sheet_name:
            kw["sheet_name"] = sheet_name
        df = pd.read_excel(tmp_path, **kw)
    elif suffix == ".csv":
        df = pd.read_csv(tmp_path, header=header_row, nrows=nrows)
    else:
        df = pd.DataFrame()

    columns = [str(c) for c in df.columns]
    return columns, df


@router.post("/column-preview")
async def column_preview(req: ColumnPreviewRequest):
    if not req.filename or not req.content_base64:
        raise HTTPException(400, "Filename va contentBase64 la bat buoc.")

    decoded = _decode_base64(req.content_base64, max_bytes=max_import_bytes())
    suffix_from_name = Path(req.filename).suffix.lower() or ".xlsx"

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix_from_name) as tmp:
        tmp_path = Path(tmp.name)
        tmp.write(decoded)

    # Phát hiện format thật bằng magic bytes
    from core.input_parser import detect_real_format
    suffix = detect_real_format(tmp_path)

    try:
        import pandas as pd

        sheet_names: list[str] = []
        columns: list[str] = []
        sample_rows: list[dict] = []
        header_row = 0

        # --- Xử lý file text thô (không phải Excel / CSV chuẩn) ---
        if suffix not in {".xlsx", ".xls", ".csv"}:
            raw = tmp_path.read_text(encoding="utf-8-sig")
            from core.input_preprocessor import detect_delimiter
            import csv, io
            delimiter = detect_delimiter(raw)
            reader = csv.DictReader(io.StringIO(raw), delimiter=delimiter)
            records = [dict(row) for row in list(reader)[:50]]
            columns = list(records[0].keys()) if records else []
            sample_rows = records[:5]
            suggested = auto_detect_mapping(columns)
            return ColumnPreviewResponse(
                sheets=[],
                columns=columns,
                sampleRows=sample_rows,
                suggestedMapping=suggested,
                headerRow=0,
                sheetNames=[],
            ).model_dump(by_alias=True)

        # --- Lấy danh sách sheet (nếu là Excel) ---
        if suffix in {".xlsx", ".xls"}:
            workbook = pd.read_excel(tmp_path, sheet_name=None, nrows=0)
            sheet_names = list(workbook.keys())

        # --- Smart header detection: quét 10 dòng đầu ---
        header_row = _detect_header_row(tmp_path, suffix)

        # --- Đọc lại file với header row đã phát hiện ---
        columns, first_frame = _read_with_header(tmp_path, suffix, header_row)

        first_frame = first_frame.fillna("")
        sample_rows = first_frame.head(5).to_dict(orient="records")
        # Chuyển tất cả giá trị sang string cho JSON safety
        sample_rows = [
            {k: str(v) if v != "" else "" for k, v in row.items()}
            for row in sample_rows
        ]
        suggested = auto_detect_mapping(columns)

        return ColumnPreviewResponse(
            sheets=sheet_names,
            columns=columns,
            sampleRows=sample_rows,
            suggestedMapping=suggested,
            headerRow=header_row,
            sheetNames=sheet_names,
        ).model_dump(by_alias=True)

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, f"Không đọc được file '{req.filename}': {exc}. Hãy kiểm tra định dạng file.")
    finally:
        tmp_path.unlink(missing_ok=True)


@router.post("/sheet-select")
async def sheet_select(req: SheetSelectRequest):
    """Cho phép frontend chọn sheet và header row cụ thể,
    trả về preview giống column-preview nhưng theo lựa chọn của user."""
    if not req.filename or not req.content_base64:
        raise HTTPException(400, "Filename va contentBase64 la bat buoc.")

    decoded = _decode_base64(req.content_base64, max_bytes=max_import_bytes())
    suffix = Path(req.filename).suffix.lower() or ".xlsx"

    if suffix not in {".xlsx", ".xls"}:
        raise HTTPException(400, "sheet-select chi ho tro file Excel (.xlsx, .xls).")

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        tmp_path = Path(tmp.name)
        tmp.write(decoded)

    try:
        import pandas as pd

        # Lấy danh sách sheet
        workbook = pd.read_excel(tmp_path, sheet_name=None, nrows=0)
        sheet_names = list(workbook.keys())

        target_sheet = req.sheet_name if req.sheet_name else None
        header_row = req.header_row

        columns, df = _read_with_header(
            tmp_path, suffix, header_row, sheet_name=target_sheet, nrows=50
        )

        df = df.fillna("")
        sample_rows = df.head(5).to_dict(orient="records")
        sample_rows = [
            {k: str(v) if v != "" else "" for k, v in row.items()}
            for row in sample_rows
        ]
        suggested = auto_detect_mapping(columns)

        return ColumnPreviewResponse(
            sheets=sheet_names,
            columns=columns,
            sampleRows=sample_rows,
            suggestedMapping=suggested,
            headerRow=header_row,
            sheetNames=sheet_names,
        ).model_dump(by_alias=True)

    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, f"Khong doc duoc file: {exc}")
    finally:
        tmp_path.unlink(missing_ok=True)


@router.post("/import-file")
async def import_file(req: ImportFileRequest):
    if not req.filename or not req.content_base64:
        raise HTTPException(400, "Filename va contentBase64 la bat buoc.")

    decoded = _decode_base64(req.content_base64, max_bytes=max_import_bytes())
    suffix_from_name = Path(req.filename).suffix.lower() or ".txt"
    default_section = "servers" if req.default_type == "server" else DEFAULT_SECTION

    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix_from_name) as tmp:
        tmp_path = Path(tmp.name)
        tmp.write(decoded)

    # Phát hiện format thật bằng magic bytes
    from core.input_parser import detect_real_format
    suffix = detect_real_format(tmp_path)

    try:
        if req.column_mapping:
            # Use column mapping
            from core.input_parser import parse_with_column_mapping
            data = parse_with_column_mapping(
                tmp_path,
                req.column_mapping,
                default_section=default_section,
                sheet_name=req.sheet_name or None,
                header_row=req.header_row,
            )
        else:
            data = parse_input(tmp_path, default_section=default_section)
        return _build_web_bundle(data)
    except ValueError as exc:
        raise HTTPException(400, f"Lỗi dữ liệu: {exc}")
    except Exception as exc:
        raise HTTPException(400, f"Không thể import file '{req.filename}': {exc}")
    finally:
        tmp_path.unlink(missing_ok=True)


@router.post("/normalize-raw")
async def normalize_raw(req: NormalizeRawRequest):
    try:
        default_section = "servers" if req.default_type == "server" else DEFAULT_SECTION
        payload = parse_delimited_text(req.raw_text, default_section=default_section)
        data = normalize_payload(payload, source="web_raw_text")
        return _build_web_bundle(data)
    except Exception as exc:
        raise HTTPException(400, str(exc))


@router.post("/preview")
async def preview(req: PreviewRequest):
    try:
        metadata = _metadata_with_custom_rules(req.metadata)
        if req.rows:
            payload = _payload_from_rows(req.rows, metadata)
        else:
            raise HTTPException(400, "Khong co du lieu de preview.")

        plugins = _load_plugins(req.plugins_dir, req.disable_plugins)
        processed = _apply_input_plugins(payload, plugins)
        bundle = _build_web_bundle(processed)
        bundle["plugins"] = [p.name() for p in plugins]
        return bundle
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(400, str(exc))


@router.post("/generate")
async def generate(req: GenerateRequest):
    try:
        artifact = _create_report_artifact(req)
        return FileResponse(
            path=artifact["outputPath"],
            filename=artifact["filename"],
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Disposition": f'attachment; filename="{artifact["filename"]}"',
                "X-Report-Id": artifact["reportId"],
                "X-Docx-Fields": artifact["fieldEngine"],
            },
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Loi tao bao cao: {exc}")


def _run_report_job(job: ReportJob) -> dict[str, Any]:
    request = GenerateRequest(**job.request)
    return _create_report_artifact(
        request,
        on_progress=lambda phase, value, message: _report_jobs.update(
            job, phase=phase, progress=value, message=message
        ),
        check_cancelled=lambda: _report_jobs.check_cancelled(job),
    )


@router.post("/report-jobs", status_code=202)
async def create_report_job(req: GenerateRequest):
    if not req.rows:
        raise HTTPException(400, "Khong co du lieu de tao bao cao.")
    _assert_report_size(req.rows)
    try:
        job, deduplicated = _report_jobs.submit(
            req.model_dump(by_alias=True), _run_report_job
        )
    except RuntimeError as exc:
        raise HTTPException(429, str(exc)) from exc
    return {"job": job.public(), "deduplicated": deduplicated}


@router.get("/report-jobs")
async def list_report_jobs():
    return {"jobs": _report_jobs.list()}


@router.get("/report-jobs/{job_id}")
async def get_report_job(job_id: str):
    job = _report_jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Report job not found.")
    return {"job": job.public()}


@router.delete("/report-jobs/{job_id}")
async def cancel_report_job(job_id: str):
    job = _report_jobs.cancel(job_id)
    if not job:
        raise HTTPException(404, "Report job not found.")
    return {"job": job.public()}


@router.get("/report-jobs/{job_id}/download")
async def download_report_job(job_id: str):
    job = _report_jobs.get(job_id)
    if not job:
        raise HTTPException(404, "Report job not found.")
    if job.status != "completed" or not job.output_path or not Path(job.output_path).exists():
        raise HTTPException(409, "Report job output is not ready.")
    return FileResponse(
        path=job.output_path,
        filename=job.filename,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"X-Report-Id": job.report_id},
    )


# ---------------------------------------------------------------------------
# Validate rows
# ---------------------------------------------------------------------------

@router.post("/validate-rows")
async def validate_rows(req: ValidateRowsRequest):
    """Kiểm tra dữ liệu rows và trả về issue cùng thống kê có thể lọc."""
    result = assess_rows(req.rows)
    return ValidateRowsResponse(
        valid=result["valid"],
        issues=[ValidationIssue(**issue) for issue in result["issues"]],
        summary=DataQualitySummary(**result["summary"]),
    ).model_dump(by_alias=True)


@router.post("/validate-incident")
async def validate_incident(req: ValidateIncidentRequest):
    """Kiểm tra tính đầy đủ và khả năng truy vết của metadata IR."""
    return assess_incident_metadata(req.metadata)


# ---------------------------------------------------------------------------
# Template management endpoints
# ---------------------------------------------------------------------------

@router.post("/templates/upload")
async def upload_template(req: UploadTemplateRequest):
    """Upload a new DOCX template file."""
    if not req.filename or not req.content_base64:
        raise HTTPException(400, "filename va contentBase64 la bat buoc.")

    decoded = _decode_base64(req.content_base64, max_bytes=MAX_TEMPLATE_SIZE)

    # Security: validate file
    try:
        validate_docx_bytes(decoded)
    except ValueError as e:
        raise HTTPException(400, str(e))

    safe_name = sanitize_filename(req.filename)

    # Don't overwrite existing files
    report_type = req.report_type.value
    category_dir = TEMPLATES_DIR / report_type
    target = category_dir / safe_name
    if target.exists():
        stem = Path(safe_name).stem
        counter = 1
        while target.exists():
            safe_name = f"{stem}_{counter}.docx"
            target = category_dir / safe_name
            counter += 1

    category_dir.mkdir(parents=True, exist_ok=True)
    target.write_bytes(decoded)

    # Analyze the template
    analysis = analyze_template(target, report_type)

    # Register in DB
    db = get_db()
    display_name = req.name.strip() if req.name.strip() else target.stem.replace("_", " ").title()
    tid = db.add_template(
        name=display_name,
        filename=safe_name,
        file_path=str(target),
        file_size=len(decoded),
        file_hash=file_sha256(target),
        has_tokens=analysis.get("has_tokens", False),
        template_mode=analysis.get("template_mode", "cover"),
        report_type=report_type,
        table_count=analysis.get("table_count", 0),
        heading_count=analysis.get("heading_count", 0),
        description=req.description,
        **_compatibility_fields(analysis),
    )
    compatible = analysis.get("compatibility", {}).get("status") != "incompatible"
    if compatible and (req.is_default or not db.get_default_template(report_type)):
        db.set_default_template(tid)

    return {
        "id": tid,
        "name": display_name,
        "filename": safe_name,
        "reportType": report_type,
        "analysis": analysis,
        "defaultRejected": bool(req.is_default and not compatible),
    }


@router.patch("/templates/{template_id}")
async def update_template(template_id: str, req: UpdateTemplateRequest):
    """Update template category/metadata and its per-category default flag."""
    db = get_db()
    template = db.get_template(template_id)
    if not template:
        raise HTTPException(404, "Template not found.")

    updates: dict[str, Any] = {}
    if req.name is not None:
        updates["name"] = req.name.strip() or template["name"]
    if req.description is not None:
        updates["description"] = req.description
    if req.report_type is not None:
        updates["report_type"] = req.report_type.value
        file_path = _managed_template_path(template["file_path"])
        analysis = analyze_template(file_path, req.report_type.value)
        updates.update(_compatibility_fields(analysis))
    if updates:
        db.update_template(template_id, **updates)

    updated = db.get_template(template_id)
    target_type = updated.get("report_type", ReportType.FULL.value)
    moved_default = bool(template.get("is_default")) and req.report_type is not None
    can_be_default = updated.get("compatibility_status") != "incompatible"
    if not can_be_default and updated.get("is_default"):
        db.unset_default_template(template_id)
        updated = db.get_template(template_id)
    if req.is_default is True and not can_be_default:
        raise HTTPException(422, "Incompatible template cannot be set as default.")
    if can_be_default and (req.is_default is True or moved_default or not db.get_default_template(target_type)):
        db.set_default_template(template_id)
    return {"ok": True, "template": db.get_template(template_id)}


@router.delete("/templates/{template_id}")
async def delete_template(template_id: str):
    """Delete a template (cannot delete default)."""
    db = get_db()
    tpl = db.get_template(template_id)
    if not tpl:
        raise HTTPException(404, "Template khong ton tai.")
    if tpl["is_default"]:
        raise HTTPException(403, "Khong the xoa template mac dinh.")

    # Delete file from disk
    file_path = _managed_template_path(tpl["file_path"])
    if file_path.exists():
        file_path.unlink(missing_ok=True)

    db.delete_template(template_id)
    return {"ok": True, "deleted": template_id}


@router.get("/templates/{template_id}/content")
async def template_content(template_id: str):
    """Return template DOCX bytes for the lazy browser thumbnail renderer."""
    db = get_db()
    tpl = db.get_template(template_id)
    if not tpl:
        raise HTTPException(404, "Template khong ton tai.")
    file_path = _managed_template_path(tpl["file_path"])
    if not file_path.exists() or file_path.suffix.lower() != ".docx":
        raise HTTPException(404, "File template khong con tren disk.")
    return FileResponse(
        path=str(file_path),
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        headers={"Cache-Control": "private, max-age=300"},
    )


@router.get("/templates/{template_id}/analyze")
async def analyze_template_endpoint(template_id: str):
    """Return detailed analysis of a template."""
    db = get_db()
    tpl = db.get_template(template_id)
    if not tpl:
        raise HTTPException(404, "Template khong ton tai.")

    file_path = _managed_template_path(tpl["file_path"])
    if not file_path.exists():
        raise HTTPException(404, "File template khong con tren disk.")

    report_type = tpl.get("report_type", ReportType.FULL.value)
    analysis = analyze_template(file_path, report_type)
    db.update_template(template_id, **_compatibility_fields(analysis))
    if analysis.get("compatibility", {}).get("status") == "incompatible" and tpl.get("is_default"):
        db.unset_default_template(template_id)
    return {"template": tpl, "analysis": analysis}


def _version_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": row["id"], "templateId": row["template_id"],
        "version": row["version_number"], "size": row["file_size"],
        "fileHash": row["file_hash"], "note": row.get("note", ""),
        "createdAt": row["created_at"],
        "analysis": json.loads(row.get("analysis_json") or "{}"),
    }


def _ensure_template_baseline_version(template: dict[str, Any]) -> None:
    db = get_db()
    if db.list_template_versions(template["id"]):
        return
    path = _managed_template_path(template["file_path"])
    analysis = analyze_template(path, template.get("report_type", ReportType.FULL.value))
    db.add_template_version(
        template["id"], file_path=str(path), file_size=path.stat().st_size,
        file_hash=file_sha256(path), analysis=analysis, note="Baseline",
    )


@router.get("/templates/{template_id}/versions")
async def list_template_versions(template_id: str):
    db = get_db()
    template = db.get_template(template_id)
    if not template:
        raise HTTPException(404, "Template not found.")
    _ensure_template_baseline_version(template)
    return {"versions": [_version_payload(row) for row in db.list_template_versions(template_id)]}


@router.post("/templates/{template_id}/versions")
async def create_template_version(template_id: str, req: TemplateVersionRequest):
    db = get_db()
    template = db.get_template(template_id)
    if not template:
        raise HTTPException(404, "Template not found.")
    decoded = _decode_base64(req.content_base64, max_bytes=MAX_TEMPLATE_SIZE)
    try:
        validate_docx_bytes(decoded)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    _ensure_template_baseline_version(template)
    next_version = max(row["version_number"] for row in db.list_template_versions(template_id)) + 1
    version_dir = TEMPLATES_DIR / "_versions" / template_id
    version_dir.mkdir(parents=True, exist_ok=True)
    target = version_dir / f"v{next_version}.docx"
    target.write_bytes(decoded)
    analysis = analyze_template(target, template.get("report_type", ReportType.FULL.value))
    version = db.add_template_version(
        template_id, file_path=str(target), file_size=len(decoded), file_hash=file_sha256(target),
        analysis=analysis, note=req.note.strip(),
    )
    compatible = analysis.get("compatibility", {}).get("status") != "incompatible"
    if compatible:
        db.update_template(
            template_id, file_path=str(target), file_size=len(decoded), file_hash=file_sha256(target),
            has_tokens=analysis.get("has_tokens", False), template_mode=analysis.get("template_mode", "cover"),
            table_count=analysis.get("table_count", 0), heading_count=analysis.get("heading_count", 0),
            **_compatibility_fields(analysis),
        )
    return {"version": _version_payload(version), "activated": compatible}


@router.post("/templates/{template_id}/versions/{version_number}/rollback")
async def rollback_template_version(template_id: str, version_number: int):
    db = get_db()
    template = db.get_template(template_id)
    version = db.get_template_version(template_id, version_number)
    if not template or not version:
        raise HTTPException(404, "Template version not found.")
    path = _managed_template_path(version["file_path"])
    analysis = json.loads(version.get("analysis_json") or "{}")
    if analysis.get("compatibility", {}).get("status") == "incompatible":
        raise HTTPException(422, "Cannot roll back to an incompatible template version.")
    db.update_template(
        template_id, file_path=str(path), file_size=version["file_size"], file_hash=version["file_hash"],
        has_tokens=analysis.get("has_tokens", False), template_mode=analysis.get("template_mode", "cover"),
        table_count=analysis.get("table_count", 0), heading_count=analysis.get("heading_count", 0),
        **_compatibility_fields(analysis),
    )
    return {"ok": True, "activeVersion": version_number, "template": db.get_template(template_id)}


@router.get("/templates/{template_id}/versions/compare")
async def compare_template_versions(template_id: str, fromVersion: int, toVersion: int):
    db = get_db()
    before = db.get_template_version(template_id, fromVersion)
    after = db.get_template_version(template_id, toVersion)
    if not before or not after:
        raise HTTPException(404, "Template version not found.")
    return {
        "fromVersion": fromVersion, "toVersion": toVersion,
        "diff": compare_template_analysis(
            json.loads(before.get("analysis_json") or "{}"),
            json.loads(after.get("analysis_json") or "{}"),
        ),
    }


# ---------------------------------------------------------------------------
# Preset endpoints
# ---------------------------------------------------------------------------

@router.get("/presets")
async def list_presets():
    db = get_db()
    return {"presets": db.list_presets()}


@router.post("/presets")
async def save_preset(req: SavePresetRequest):
    db = get_db()
    pid = db.save_preset(
        name=req.name,
        settings=req.settings,
        column_mapping=req.column_mapping,
        template_id=req.template_id,
        description=req.description,
        preset_id=req.id,
    )
    return {"id": pid, "ok": True}


@router.delete("/presets/{preset_id}")
async def delete_preset(preset_id: str):
    db = get_db()
    deleted = db.delete_preset(preset_id)
    if not deleted:
        raise HTTPException(404, "Preset khong ton tai.")
    return {"ok": True, "deleted": preset_id}


@router.get("/presets/{preset_id}")
async def get_preset(preset_id: str):
    db = get_db()
    preset = db.get_preset(preset_id)
    if not preset:
        raise HTTPException(404, "Preset khong ton tai.")
    return preset


# ---------------------------------------------------------------------------
# Preview DOCX (generate without saving)
# ---------------------------------------------------------------------------

@router.post("/preview-docx")
async def preview_docx(req: PreviewDocxRequest):
    """Generate a DOCX for preview — returns the file as blob."""
    try:
        metadata = req.metadata or {}
        if not req.rows:
            raise HTTPException(400, "Khong co du lieu de preview.")
        _assert_report_size(req.rows)

        if req.report_type == ReportType.INCIDENT_RESPONSE:
            incident_quality = assess_incident_metadata(metadata)
            if not incident_quality["valid"]:
                raise HTTPException(422, {
                    "message": "Thông tin Incident Response còn lỗi nghiêm trọng.",
                    "incidentQuality": incident_quality,
                })
            metadata = {**metadata, "incidentQuality": incident_quality["summary"]}

        payload = _payload_from_rows(req.rows, metadata)
        plugins = _load_plugins(req.plugins_dir, req.disable_plugins)
        processed = _apply_input_plugins(payload, plugins)

        template_path = req.template_path or _default_template_path(req.report_type)
        _assert_template_compatible(template_path)

        document = generate_report(
            processed,
            title=req.title or "BÁO CÁO ĐÁNH GIÁ AN TOÀN THÔNG TIN",
            organization=req.organization or "",
            assessment_date=req.assessment_date or None,
            template_path=template_path,
            report_type=req.report_type.value,
        )

        with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as tmp:
            tmp_path = Path(tmp.name)

        _, field_update = _save_finalized_report(document, tmp_path)

        return FileResponse(
            path=str(tmp_path),
            media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={
                "Content-Type": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                "X-Docx-Fields": field_update.engine,
            },
        )
    except HTTPException:
        raise
    except Exception as exc:
        raise HTTPException(500, f"Loi preview: {exc}")


# ---------------------------------------------------------------------------
# Save generated report as template
# ---------------------------------------------------------------------------

@router.post("/reports/{report_id}/save-as-template")
async def save_report_as_template(report_id: str, req: SaveAsTemplateRequest):
    """Save a previously generated report DOCX as a reusable template."""
    # Check if we have the file path
    source_path = _last_generated.get(report_id)

    if not source_path or not source_path.exists():
        # Try from DB history
        db = get_db()
        report = db.get_report(report_id)
        if report and report.get("output_path"):
            source_path = Path(report["output_path"])

    if not source_path or not source_path.exists():
        raise HTTPException(404, "File bao cao khong ton tai hoac da bi xoa.")

    # Copy to templates directory
    safe_name = sanitize_filename(req.name or f"generated_{report_id}")
    report_type = req.report_type.value
    category_dir = TEMPLATES_DIR / report_type
    target = category_dir / safe_name
    counter = 1
    while target.exists():
        safe_name = f"{Path(safe_name).stem}_{counter}.docx"
        target = category_dir / safe_name
        counter += 1

    import shutil
    category_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(str(source_path), str(target))

    # Analyze
    analysis = analyze_template(target, report_type)

    # Register in DB
    db = get_db()
    tid = db.add_template(
        name=req.name.strip() or target.stem.replace("_", " ").title(),
        filename=safe_name,
        file_path=str(target),
        file_size=target.stat().st_size,
        file_hash=file_sha256(target),
        is_generated=True,
        has_tokens=analysis.get("has_tokens", False),
        template_mode=analysis.get("template_mode", "cover"),
        report_type=report_type,
        table_count=analysis.get("table_count", 0),
        heading_count=analysis.get("heading_count", 0),
        description=req.description,
        **_compatibility_fields(analysis),
    )
    if analysis.get("compatibility", {}).get("status") != "incompatible" and not db.get_default_template(report_type):
        db.set_default_template(tid)

    return {
        "id": tid,
        "name": req.name,
        "filename": safe_name,
        "reportType": report_type,
        "analysis": analysis,
    }


# ---------------------------------------------------------------------------
# Report history
# ---------------------------------------------------------------------------

@router.get("/reports/history")
async def report_history():
    db = get_db()
    return {"reports": db.list_reports(limit=None)}


@router.get("/dashboard/summary")
async def dashboard_summary(days: int = 90):
    if days not in {30, 90, 180}:
        raise HTTPException(422, "days must be one of 30, 90, or 180")
    return get_db().dashboard_summary(days)
