"""Pydantic models cho API request/response."""

from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from core.report_snapshot import DEFAULT_REPORT_TITLE
from pydantic import BaseModel, Field


class ReportType(str, Enum):
    FULL = "full"
    SERVER_ONLY = "server_only"
    CLIENT_ONLY = "client_only"
    SUMMARY = "summary"
    TECHNICAL = "technical"
    INCIDENT_RESPONSE = "incident_response"


class AssetRow(BaseModel):
    type: str = "client"
    hostname: str = ""
    ip: str = ""
    os: str = ""
    notes: str = ""
    result: str = ""
    extras: dict[str, Any] = Field(default_factory=dict)


class NormalizeRawRequest(BaseModel):
    raw_text: str = Field(alias="rawText", default="")
    default_type: str = Field(alias="defaultType", default="client")

    model_config = {"populate_by_name": True}


class ColumnPreviewRequest(BaseModel):
    filename: str = ""
    content_base64: str = Field(alias="contentBase64", default="")

    model_config = {"populate_by_name": True}


class ImportFileRequest(BaseModel):
    filename: str = ""
    content_base64: str = Field(alias="contentBase64", default="")
    default_type: str = Field(alias="defaultType", default="client")
    column_mapping: dict[str, str] | None = Field(alias="columnMapping", default=None)
    sheet_name: str = Field(alias="sheetName", default="")
    header_row: int = Field(alias="headerRow", default=0, ge=0, le=100)

    model_config = {"populate_by_name": True}


class PreviewRequest(BaseModel):
    rows: list[dict[str, Any]] = Field(default_factory=list)
    metadata: dict[str, Any] = Field(default_factory=dict)
    plugins_dir: str = Field(alias="pluginsDir", default="")
    disable_plugins: bool = Field(alias="disablePlugins", default=False)

    model_config = {"populate_by_name": True}


class GenerateRequest(BaseModel):
    rows: list[dict[str, Any]] = Field(default_factory=list)
    title: str = DEFAULT_REPORT_TITLE
    organization: str = ""
    assessment_date: str = Field(alias="assessmentDate", default="")
    template_path: str = Field(alias="templatePath", default="")
    report_type: ReportType = Field(alias="reportType", default=ReportType.FULL)
    metadata: dict[str, Any] = Field(default_factory=dict)
    plugins_dir: str = Field(alias="pluginsDir", default="")
    disable_plugins: bool = Field(alias="disablePlugins", default=False)
    output_name: str = Field(alias="outputName", default="")
    client_request_id: str = Field(alias="clientRequestId", default="", max_length=128)
    preview_id: str = Field(alias="previewId", default="", max_length=128)

    model_config = {"populate_by_name": True}


class CountsResponse(BaseModel):
    servers: int = 0
    clients: int = 0
    total: int = 0


class WebBundle(BaseModel):
    payload: dict[str, Any] = Field(default_factory=dict)
    rows: list[dict[str, Any]] = Field(default_factory=list)
    counts: CountsResponse = Field(default_factory=CountsResponse)
    preview_text: str = Field(alias="previewText", default="")

    model_config = {"populate_by_name": True}


class ColumnPreviewResponse(BaseModel):
    sheets: list[str] = Field(default_factory=list)
    columns: list[str] = Field(default_factory=list)
    sample_rows: list[dict[str, Any]] = Field(alias="sampleRows", default_factory=list)
    suggested_mapping: dict[str, str] = Field(alias="suggestedMapping", default_factory=dict)
    header_row: int = Field(alias="headerRow", default=0)
    sheet_names: list[str] = Field(alias="sheetNames", default_factory=list)

    model_config = {"populate_by_name": True}


class SheetSelectRequest(BaseModel):
    """Request để chọn sheet và header row cụ thể cho file Excel."""

    filename: str = ""
    content_base64: str = Field(alias="contentBase64", default="")
    sheet_name: str = Field(alias="sheetName", default="")
    header_row: int = Field(alias="headerRow", default=0)

    model_config = {"populate_by_name": True}


class ValidateRowsRequest(BaseModel):
    """Request kiểm tra dữ liệu rows trước khi tạo báo cáo."""

    rows: list[dict[str, Any]] = Field(default_factory=list)


class ValidateIncidentRequest(BaseModel):
    """Request kiểm tra metadata trước khi tạo báo cáo Incident Response."""

    metadata: dict[str, Any] = Field(default_factory=dict)


class ValidationIssue(BaseModel):
    """Một vấn đề phát hiện được trong quá trình validate."""

    row: int
    field: str
    level: str  # 'error' hoặc 'warning'
    code: str = ""
    message: str


class DataQualitySummary(BaseModel):
    total_rows: int = Field(alias="totalRows", default=0)
    valid_rows: int = Field(alias="validRows", default=0)
    error_rows: int = Field(alias="errorRows", default=0)
    warning_rows: int = Field(alias="warningRows", default=0)
    errors: int = 0
    warnings: int = 0
    servers: int = 0
    clients: int = 0
    duplicate_hostnames: int = Field(alias="duplicateHostnames", default=0)
    invalid_ips: int = Field(alias="invalidIps", default=0)
    missing_os: int = Field(alias="missingOs", default=0)
    missing_result: int = Field(alias="missingResult", default=0)

    model_config = {"populate_by_name": True}


class ValidateRowsResponse(BaseModel):
    """Kết quả validate rows."""

    valid: bool
    issues: list[ValidationIssue] = Field(default_factory=list)
    summary: DataQualitySummary = Field(default_factory=DataQualitySummary)


# ---------------------------------------------------------------------------
# Detection rule models
# ---------------------------------------------------------------------------


class DetectionRuleRequest(BaseModel):
    name: str
    description: str = ""
    version: str = "1"
    severity: str = "medium"
    classification: str = "needs_review"
    remediation: str = ""
    enabled: bool = True
    conditions: dict[str, Any] = Field(default_factory=dict)


class EvaluateRuleRequest(BaseModel):
    rows: list[dict[str, Any]] = Field(default_factory=list)
    rule: DetectionRuleRequest
    disabled_rule_ids: list[str] = Field(alias="disabledRuleIds", default_factory=list)
    editing_rule_id: str = Field(alias="editingRuleId", default="")

    model_config = {"populate_by_name": True}


class ImportRulesRequest(BaseModel):
    rules: list[dict[str, Any]] = Field(default_factory=list)
    strategy: Literal["skip", "rename"] = "skip"


# ---------------------------------------------------------------------------
# Template management models
# ---------------------------------------------------------------------------


class UploadTemplateRequest(BaseModel):
    """Upload a new DOCX template."""

    filename: str
    content_base64: str = Field(alias="contentBase64", default="")
    name: str = ""
    description: str = ""
    report_type: ReportType = Field(alias="reportType", default=ReportType.FULL)
    is_default: bool = Field(alias="isDefault", default=False)

    model_config = {"populate_by_name": True}


class TemplateInfo(BaseModel):
    """Template metadata returned by API."""

    id: str = ""
    name: str = ""
    filename: str = ""
    path: str = ""
    size: int = 0
    file_hash: str = Field(alias="fileHash", default="")
    is_default: bool = Field(alias="isDefault", default=False)
    is_generated: bool = Field(alias="isGenerated", default=False)
    has_tokens: bool = Field(alias="hasTokens", default=False)
    template_mode: str = Field(alias="templateMode", default="cover")
    report_type: ReportType = Field(alias="reportType", default=ReportType.FULL)
    table_count: int = Field(alias="tableCount", default=0)
    heading_count: int = Field(alias="headingCount", default=0)
    description: str = ""
    created_at: str = Field(alias="createdAt", default="")

    model_config = {"populate_by_name": True}


class UpdateTemplateRequest(BaseModel):
    """Reclassify a template or make it the default for its report type."""

    name: str | None = None
    description: str | None = None
    report_type: ReportType | None = Field(alias="reportType", default=None)
    is_default: bool | None = Field(alias="isDefault", default=None)

    model_config = {"populate_by_name": True}


class TemplateVersionRequest(BaseModel):
    content_base64: str = Field(alias="contentBase64", default="")
    note: str = ""

    model_config = {"populate_by_name": True}


class TemplateAnalysis(BaseModel):
    """Detailed template analysis result."""

    template_mode: str = Field(alias="templateMode", default="cover")
    has_tokens: bool = Field(alias="hasTokens", default=False)
    tokens_found: list[str] = Field(alias="tokensFound", default_factory=list)
    table_count: int = Field(alias="tableCount", default=0)
    heading_count: int = Field(alias="headingCount", default=0)
    heading_list: list[str] = Field(alias="headingList", default_factory=list)
    page_estimate: int = Field(alias="pageEstimate", default=0)
    styles_used: list[str] = Field(alias="stylesUsed", default_factory=list)
    has_prototypes: bool = Field(alias="hasPrototypes", default=False)
    prototype_tables: list[str] = Field(alias="prototypeTables", default_factory=list)

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Preset models
# ---------------------------------------------------------------------------


class SavePresetRequest(BaseModel):
    """Create or update a report preset."""

    id: str | None = None
    name: str
    description: str = ""
    settings: dict[str, Any] = Field(default_factory=dict)
    column_mapping: dict[str, str] | None = Field(alias="columnMapping", default=None)
    template_id: str | None = Field(alias="templateId", default=None)

    model_config = {"populate_by_name": True}


class PresetInfo(BaseModel):
    """Preset metadata."""

    id: str = ""
    name: str = ""
    description: str = ""
    settings: dict[str, Any] = Field(default_factory=dict)
    column_mapping: dict[str, str] | None = Field(alias="columnMapping", default=None)
    template_id: str | None = Field(alias="templateId", default=None)
    created_at: str = Field(alias="createdAt", default="")
    updated_at: str = Field(alias="updatedAt", default="")

    model_config = {"populate_by_name": True}


# ---------------------------------------------------------------------------
# Preview / History models
# ---------------------------------------------------------------------------


class PreviewDocxRequest(BaseModel):
    """Generate a DOCX for preview (no save)."""

    rows: list[dict[str, Any]] = Field(default_factory=list)
    title: str = DEFAULT_REPORT_TITLE
    organization: str = ""
    assessment_date: str = Field(alias="assessmentDate", default="")
    template_path: str = Field(alias="templatePath", default="")
    report_type: ReportType = Field(alias="reportType", default=ReportType.FULL)
    metadata: dict[str, Any] = Field(default_factory=dict)
    plugins_dir: str = Field(alias="pluginsDir", default="")
    disable_plugins: bool = Field(alias="disablePlugins", default=False)
    client_request_id: str = Field(alias="clientRequestId", default="", max_length=128)

    model_config = {"populate_by_name": True}


class SaveAsTemplateRequest(BaseModel):
    """Save a generated report as a reusable template."""

    name: str
    description: str = ""
    report_type: ReportType = Field(alias="reportType", default=ReportType.FULL)

    model_config = {"populate_by_name": True}


class ReportHistoryItem(BaseModel):
    """Report history entry."""

    id: str = ""
    title: str = ""
    organization: str = ""
    report_type: str = Field(alias="reportType", default="full")
    row_count: int = Field(alias="rowCount", default=0)
    server_count: int = Field(alias="serverCount", default=0)
    client_count: int = Field(alias="clientCount", default=0)
    output_filename: str = Field(alias="outputFilename", default="")
    file_size: int = Field(alias="fileSize", default=0)
    created_at: str = Field(alias="createdAt", default="")

    model_config = {"populate_by_name": True}
