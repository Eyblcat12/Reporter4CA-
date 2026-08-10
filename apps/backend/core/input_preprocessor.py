from __future__ import annotations

import csv
import io
import re
import unicodedata
from typing import Any

SECTIONS = ("servers", "clients")
DEFAULT_SECTION = "clients"

SECTION_ALIASES = {
    "server": "servers",
    "servers": "servers",
    "srv": "servers",
    "may_chu": "servers",
    "client": "clients",
    "clients": "clients",
    "workstation": "clients",
    "endpoint": "clients",
    "pc": "clients",
    "may_tram": "clients",
    "may_tinh": "clients",
}

COLUMN_ALIASES = {
    "type": {
        "type",
        "asset_type",
        "category",
        "role",
        "loai",
        "dang",
        "phan_loai",
        "nhom",
        # Bổ sung alias mới
        "device_type",
        "loai_thiet_bi",
    },
    "hostname": {
        "hostname",
        "host",
        "host_name",
        "name",
        "asset_name",
        "device",
        "device_name",
        "computer_name",
        "machine_name",
        "ten",
        "may",
        "thiet_bi",
        # Bổ sung alias mới
        "ten_may",
        "ten_thiet_bi",
        "ten_host",
        "computer",
        "pc_name",
        "server_name",
        "machine",
        "may_tinh",
        "may_chu",
        # Alias dạng ghép tiếng Việt
        "ten_may_chu",  # Tên máy chủ
        "ten_may_client",  # Tên máy client
        "ten_may_tram",  # Tên máy trạm
        "may_client",  # Máy client
        "may_tram",  # Máy trạm
    },
    "ip": {
        "ip",
        "ip_address",
        "address",
        "dia_chi",
        "dia_chi_ip",
        "dia_chi_truy_cap",
        "truy_cap",
        # Bổ sung alias mới
        "ipaddress",
        "ip_addr",
        "network",
    },
    "os": {
        "os",
        "operating_system",
        "system",
        "he_dieu_hanh",
        "hdh",
        # Bổ sung alias mới
        "platform",
        "os_name",
        "os_type",
        "he_thong",
    },
    "notes": {
        "notes",
        "note",
        "ghi_chu",
        "remark",
        "comments",
        # Bổ sung alias mới
        "mo_ta",
        "description",
        "detail",
        "chi_tiet",
    },
    "result": {
        "result",
        "ket_qua",
        "assessment_result",
        "finding",
        # Bổ sung alias mới
        "assessment",
        "danh_gia",
        "phat_hien",
        "evaluation",
    },
    "status": {
        "status",
        "trang_thai",
        "state",
        "hien_trang",  # Hiện trạng
        "hien_trang_danh_gia_va",  # HIỆN TRẠNG ĐÁNH GIÁ VA
        "hien_trang_ra_quet_ca",  # HIỆN TRẠNG RÀ QUÉT CA
    },
}

CANONICAL_COLUMN_MAP = {
    alias: canonical for canonical, aliases in COLUMN_ALIASES.items() for alias in aliases
}


def normalize_token(value: Any) -> str:
    text = str(value or "").strip()
    text = text.replace("Đ", "D").replace("đ", "d")
    text = unicodedata.normalize("NFD", text)
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    text = text.lower()
    text = re.sub(r"[^a-z0-9.]+", "_", text)
    return text.strip("_")


def normalize_column_name(value: Any) -> str:
    normalized = normalize_token(value)

    if "." in normalized:
        prefix, suffix = normalized.split(".", 1)
        prefix = SECTION_ALIASES.get(prefix, prefix)
        suffix = CANONICAL_COLUMN_MAP.get(suffix, suffix)
        return f"{prefix}.{suffix}"

    return CANONICAL_COLUMN_MAP.get(normalized, normalized)


def normalize_asset_type(value: Any, *, default_section: str = DEFAULT_SECTION) -> str:
    normalized = normalize_token(value)
    return SECTION_ALIASES.get(normalized, default_section)


def canonicalize_record(
    record: dict[str, Any], *, default_section: str = DEFAULT_SECTION
) -> tuple[str, dict[str, Any]]:
    section = default_section
    canonical_record: dict[str, Any] = {}

    for raw_key, raw_value in record.items():
        canonical_key = normalize_column_name(raw_key)

        if canonical_key == "type":
            section = normalize_asset_type(raw_value, default_section=default_section)
            continue

        canonical_record[canonical_key] = raw_value

    return section, canonical_record


def records_to_payload(
    records: list[dict[str, Any]],
    *,
    default_section: str = DEFAULT_SECTION,
) -> dict[str, Any]:
    payload: dict[str, Any] = {"servers": [], "clients": [], "metadata": {}}

    for record in records:
        if not isinstance(record, dict):
            continue

        section, canonical_record = canonicalize_record(record, default_section=default_section)
        has_data = any(
            str(value).strip() for value in canonical_record.values() if value is not None
        )
        if not has_data:
            continue

        payload[section].append(canonical_record)

    return payload


def detect_delimiter(raw_text: str) -> str:
    sample_lines = [line for line in raw_text.splitlines() if line.strip()]
    sample = "\n".join(sample_lines[:5])
    if not sample:
        return ","

    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        return dialect.delimiter
    except csv.Error:
        delimiter_scores = {
            candidate: sample.count(candidate) for candidate in [",", ";", "\t", "|"]
        }
        return max(delimiter_scores, key=delimiter_scores.get)  # type: ignore[arg-type]


def parse_delimited_text(
    raw_text: str,
    *,
    default_section: str = DEFAULT_SECTION,
) -> dict[str, Any]:
    delimiter = detect_delimiter(raw_text)
    reader = csv.DictReader(io.StringIO(raw_text), delimiter=delimiter)
    records = [dict(row) for row in reader]
    return records_to_payload(records, default_section=default_section)
