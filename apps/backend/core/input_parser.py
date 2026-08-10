from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from core.input_preprocessor import (
    DEFAULT_SECTION,
    SECTIONS,
    normalize_asset_type,
    normalize_column_name,
    parse_delimited_text,
)

SUPPORTED_EXTENSIONS = {".json", ".csv", ".xlsx", ".xls", ".txt", ".tsv"}
DEFAULT_TEXT_VALUE = "N/A"


def detect_real_format(path: str | Path) -> str:
    """Phát hiện định dạng thật của file bằng magic bytes, không phụ thuộc extension."""
    file_path = Path(path)
    try:
        with open(file_path, "rb") as f:
            header = f.read(8)
    except Exception:
        return file_path.suffix.lower()

    # PK signature = ZIP-based format (xlsx, docx, etc.)
    if header[:2] == b"PK":
        return ".xlsx"
    # JSON starts with { or [
    if header[:1] in (b"{", b"["):
        return ".json"
    # BOM check for UTF-8 text
    if header[:3] == b"\xef\xbb\xbf":
        return ".csv"
    # Default: trust extension if valid, else treat as CSV
    ext = file_path.suffix.lower()
    return ext if ext in SUPPORTED_EXTENSIONS else ".csv"


def parse_input(path: str | Path, *, default_section: str = "servers") -> dict[str, Any]:
    input_path = Path(path)
    suffix = detect_real_format(input_path)

    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(
            f"Định dạng file không được hỗ trợ: {suffix or '(không có extension)'}. "
            f"Các định dạng hỗ trợ: {', '.join(sorted(SUPPORTED_EXTENSIONS))}"
        )

    if suffix == ".json":
        return parse_json(input_path, default_section=default_section)
    if suffix in {".txt", ".tsv"}:
        return parse_raw_text_file(input_path, default_section=default_section)
    return parse_table_file(input_path, default_section=default_section)


def parse_json(path: str | Path, *, default_section: str = "servers") -> dict[str, Any]:
    json_path = Path(path)
    payload = json.loads(json_path.read_text(encoding="utf-8"))
    if isinstance(payload, list):
        payload = {default_section: payload}
    if not isinstance(payload, dict):
        raise ValueError("JSON dau vao phai la object hoac list o cap goc.")
    return normalize_payload(payload, source=json_path.name)


def parse_raw_text_file(
    path: str | Path, *, default_section: str = DEFAULT_SECTION
) -> dict[str, Any]:
    text_path = Path(path)
    raw_text = text_path.read_text(encoding="utf-8-sig")
    payload = parse_delimited_text(raw_text, default_section=default_section)
    return normalize_payload(payload, source=text_path.name)


def parse_table_file(path: str | Path, *, default_section: str = "servers") -> dict[str, Any]:
    try:
        import pandas as pd
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Can cai dat pandas va openpyxl de doc file CSV/Excel. "
            "Hay chay: python -m pip install -r requirements.txt"
        ) from exc

    table_path = Path(path)
    suffix = table_path.suffix.lower()

    if suffix == ".csv":
        frame = pd.read_csv(table_path)
        return normalize_payload(
            _parse_table_frame(frame, default_section=default_section), source=table_path.name
        )

    workbook = pd.read_excel(table_path, sheet_name=None)
    normalized_workbook = {
        str(sheet_name).strip().lower(): frame for sheet_name, frame in workbook.items()
    }

    if any(sheet_name in normalized_workbook for sheet_name in SECTIONS):
        payload: dict[str, Any] = {"servers": [], "clients": []}
        for section in SECTIONS:
            frame = normalized_workbook.get(section)
            payload[section] = [] if frame is None else _records_from_standard_frame(frame)
        return normalize_payload(payload, source=table_path.name)

    if len(normalized_workbook) == 1:
        frame = next(iter(normalized_workbook.values()))
        return normalize_payload(
            _parse_table_frame(frame, default_section=default_section), source=table_path.name
        )

    payload = {"servers": [], "clients": []}
    for sheet_name, frame in normalized_workbook.items():
        if "server" in sheet_name:
            payload["servers"].extend(_records_from_standard_frame(frame))
        elif any(token in sheet_name for token in ("client", "endpoint", "workstation")):
            payload["clients"].extend(_records_from_standard_frame(frame))

    if payload["servers"] or payload["clients"]:
        return normalize_payload(payload, source=table_path.name)

    raise ValueError(
        "Khong xac dinh duoc cau truc sheet. Hay dung sheet 'Servers'/'Clients' hoac mot sheet co cot Type/Category."
    )


def parse_with_column_mapping(
    path: str | Path,
    mapping: dict[str, str],
    *,
    default_section: str = "servers",
    sheet_name: str | None = None,
    header_row: int = 0,
) -> dict[str, Any]:
    """Parse file rồi áp dụng column mapping do người dùng cung cấp."""
    try:
        import pandas as pd
    except ModuleNotFoundError as exc:
        raise RuntimeError("Can cai dat pandas va openpyxl de doc file CSV/Excel.") from exc

    table_path = Path(path)
    suffix = detect_real_format(table_path)

    if suffix == ".csv":
        frame = pd.read_csv(table_path, header=header_row)
    elif suffix in {".xlsx", ".xls"}:
        frame = pd.read_excel(
            table_path,
            sheet_name=sheet_name if sheet_name else 0,
            header=header_row,
        )
    elif suffix in {".txt", ".tsv"}:
        raw_text = table_path.read_text(encoding="utf-8-sig")
        from core.input_preprocessor import detect_delimiter

        delimiter = detect_delimiter(raw_text)
        frame = pd.read_csv(table_path, delimiter=delimiter, header=header_row)
    elif suffix == ".json":
        data = json.loads(table_path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            frame = pd.DataFrame(data)
        elif isinstance(data, dict):
            # Thu lay danh sach tu section dau tien
            for key in ("servers", "clients"):
                if key in data and isinstance(data[key], list):
                    frame = pd.DataFrame(data[key])
                    break
            else:
                frame = pd.DataFrame([data])
        else:
            raise ValueError("JSON khong hop le cho column mapping.")
    else:
        raise ValueError(
            f"Định dạng file không hỗ trợ column mapping: {suffix}. "
            f"Hãy dùng file .xlsx, .csv, .json, .txt hoặc .tsv."
        )

    # Ap dung mapping: mapping = {"source_column": "target_field", ...}
    rename_map = {src: tgt for src, tgt in mapping.items() if src in frame.columns}
    frame = frame.rename(columns=rename_map)

    # --- Dual hostname split: tách hàng chứa cả server + client hostname ---
    has_dual = any(tgt in ("hostname_server", "hostname_client") for tgt in mapping.values())
    if has_dual:
        from core.column_mapper import split_dual_hostname_rows

        records = frame.fillna("").to_dict(orient="records")
        split_records = split_dual_hostname_rows(records)
        payload: dict[str, Any] = {"servers": [], "clients": [], "metadata": {}}
        for rec in split_records:
            asset_type = rec.pop("type", default_section)
            section = "servers" if asset_type in ("server", "servers") else "clients"
            payload[section].append(rec)
        return normalize_payload(payload, source=table_path.name)

    return normalize_payload(
        _parse_table_frame(frame, default_section=default_section),
        source=table_path.name,
    )


def normalize_payload(payload: dict[str, Any], source: str) -> dict[str, Any]:
    normalized: dict[str, Any] = {
        "servers": [],
        "clients": [],
        "metadata": _normalize_metadata(payload.get("metadata")),
    }

    for section in SECTIONS:
        raw_items = payload.get(section, [])
        if raw_items is None:
            raw_items = []
        if not isinstance(raw_items, list):
            raise ValueError(f"Truong '{section}' phai la danh sach.")

        normalized[section] = [
            _normalize_asset(item, section=section, row_index=index, source=source)
            for index, item in enumerate(raw_items, start=1)
        ]

    return normalized


def _normalize_metadata(value: Any) -> dict[str, Any]:
    if value in (None, ""):
        return {}
    if not isinstance(value, dict):
        raise ValueError("Truong 'metadata' phai la object neu duoc cung cap.")
    return value


def _normalize_asset(item: Any, *, section: str, row_index: int, source: str) -> dict[str, Any]:
    if not isinstance(item, dict):
        raise ValueError(f"Dong {row_index} trong '{section}' cua {source} khong hop le.")

    normalized_item = {normalize_column_name(key): value for key, value in item.items()}
    hostname = _normalize_text(normalized_item.get("hostname"), allow_empty=False)
    if not hostname:
        raise ValueError(
            f"Dong {row_index} trong '{section}' cua {source} thieu truong bat buoc 'hostname'."
        )

    asset: dict[str, Any] = {
        "hostname": hostname,
        "ip": _normalize_text(normalized_item.get("ip"), default=DEFAULT_TEXT_VALUE),
        "os": _normalize_text(normalized_item.get("os"), default=DEFAULT_TEXT_VALUE),
    }

    # Ho tro truong 'result' — ket qua danh gia tung asset
    result_value = normalized_item.get("result")
    if result_value is not None and not _is_missing(result_value):
        asset["result"] = str(result_value).strip()

    # Ho tro truong 'status' — trang thai binh thuong / bat thuong
    status_value = normalized_item.get("status")
    if status_value is not None and not _is_missing(status_value):
        asset["status"] = str(status_value).strip()

    for key, value in normalized_item.items():
        if key in asset or key == "type":
            continue
        if _is_missing(value):
            continue
        asset[key] = str(value).strip()

    return asset


def _parse_table_frame(frame: Any, *, default_section: str = "servers") -> dict[str, Any]:
    normalized_columns = {column: normalize_column_name(column) for column in frame.columns}

    if any(name.startswith("servers.") for name in normalized_columns.values()) or any(
        name.startswith("clients.") for name in normalized_columns.values()
    ):
        return {
            "servers": _records_from_prefixed_columns(frame, "servers"),
            "clients": _records_from_prefixed_columns(frame, "clients"),
        }

    column_names = set(normalized_columns.values())
    type_column = next(
        (
            column
            for column, normalized_name in normalized_columns.items()
            if normalized_name in {"type", "category", "asset_type", "role"}
        ),
        None,
    )

    if type_column is not None and "hostname" in column_names:
        return _records_from_type_column(frame, type_column, default_section=default_section)

    if "hostname" in column_names:
        return {
            "servers": _records_from_standard_frame(frame) if default_section == "servers" else [],
            "clients": _records_from_standard_frame(frame) if default_section == "clients" else [],
        }

    raise ValueError(
        "Khong tim thay cot hop le. Can co mot trong cac cau truc: Hostname/IP/OS + Type, "
        "hoac Servers.Hostname / Clients.Hostname."
    )


def _records_from_prefixed_columns(frame: Any, prefix: str) -> list[dict[str, Any]]:
    target_columns = {}
    for column in frame.columns:
        normalized_name = normalize_column_name(column)
        if normalized_name.startswith(prefix + "."):
            short_name = normalized_name.split(".", 1)[1]
            target_columns[column] = short_name

    if not target_columns:
        return []

    subset = frame[list(target_columns)].rename(columns=target_columns)
    return _records_from_standard_frame(subset)


def _records_from_type_column(
    frame: Any,
    type_column: str,
    *,
    default_section: str = DEFAULT_SECTION,
) -> dict[str, list[dict[str, Any]]]:
    result = {"servers": [], "clients": []}
    for row in frame.to_dict(orient="records"):
        raw_type = _normalize_text(row.get(type_column), default="")
        section = normalize_asset_type(raw_type, default_section=default_section)
        row_copy = dict(row)
        row_copy.pop(type_column, None)
        result[section].append(row_copy)
    return result


def _records_from_standard_frame(frame: Any) -> list[dict[str, Any]]:
    records = []
    for row in frame.to_dict(orient="records"):
        normalized_row = {}
        for key, value in row.items():
            normalized_key = normalize_column_name(key)
            normalized_row[normalized_key] = None if _is_missing(value) else value
        if all(_is_missing(value) for value in normalized_row.values()):
            continue
        records.append(normalized_row)
    return records


def _normalize_text(value: Any, *, default: str = "", allow_empty: bool = True) -> str:
    if _is_missing(value):
        return default

    text = str(value).strip()
    if not text:
        return default if allow_empty else ""
    return text


def _is_missing(value: Any) -> bool:
    if value is None:
        return True

    try:
        import math

        if isinstance(value, float) and math.isnan(value):
            return True
    except TypeError:
        pass

    return str(value).strip().lower() in {"", "nan", "none", "null"}
