"""Flexible column mapping engine — cho phép người dùng tự map cột dữ liệu nguồn
sang các trường chuẩn của hệ thống."""

from __future__ import annotations

from typing import Any

from core.input_preprocessor import CANONICAL_COLUMN_MAP, COLUMN_ALIASES, normalize_token

# ---------------------------------------------------------------------------
# Danh sách các trường có thể map tới
# ---------------------------------------------------------------------------

MAPPABLE_FIELDS: list[dict[str, str]] = [
    {"field": "hostname", "label": "Tên máy (Hostname)", "required": True},
    {"field": "hostname_server", "label": "Hostname (Máy chủ / Server)", "required": False},
    {"field": "hostname_client", "label": "Hostname (Máy trạm / Client)", "required": False},
    {"field": "ip", "label": "Địa chỉ IP", "required": False},
    {"field": "os", "label": "Hệ điều hành", "required": False},
    {"field": "type", "label": "Loại thiết bị (Server/Client)", "required": False},
    {"field": "result", "label": "Kết quả đánh giá", "required": False},
    {"field": "notes", "label": "Ghi chú", "required": False},
    {"field": "status", "label": "Trạng thái", "required": False},
]


def get_mappable_fields() -> list[dict[str, Any]]:
    """Trả về danh sách các trường hệ thống có thể map tới,
    bao gồm aliases gợi ý cho mỗi trường."""
    result: list[dict[str, Any]] = []
    for field_info in MAPPABLE_FIELDS:
        field_name = field_info["field"]
        aliases = sorted(COLUMN_ALIASES.get(field_name, {field_name}))
        result.append(
            {
                "field": field_name,
                "label": field_info["label"],
                "required": field_info.get("required", False),
                "aliases": aliases,
            }
        )
    return result


# Từ khóa nhận diện cột server vs client hostname
_SERVER_HINTS = {"server", "srv", "may_chu", "chu"}
_CLIENT_HINTS = {"client", "pc", "may_tram", "tram", "workstation", "endpoint"}


def auto_detect_mapping(columns: list[str]) -> dict[str, str]:
    """Tự động gợi ý mapping từ tên cột nguồn -> trường chuẩn.

    Trả về dict dạng: {"source_column_name": "canonical_field_name"}
    Chỉ map những cột nhận dạng được, bỏ qua cột không khớp.
    Hỗ trợ tự động phát hiện dual hostname (server + client).
    """
    mapping: dict[str, str] = {}
    used_fields: set[str] = set()

    # Phát hiện nếu có nhiều cột hostname
    hostname_columns: list[tuple[str, str]] = []  # (column_name, normalized)
    for column in columns:
        normalized = normalize_token(column)
        canonical = CANONICAL_COLUMN_MAP.get(normalized)
        if canonical == "hostname":
            hostname_columns.append((column, normalized))

    # Nếu có >= 2 cột hostname -> dùng dual hostname
    use_dual = len(hostname_columns) >= 2

    for column in columns:
        normalized = normalize_token(column)
        canonical = CANONICAL_COLUMN_MAP.get(normalized)

        if canonical == "hostname" and use_dual:
            # Phân loại thành hostname_server hoặc hostname_client
            tokens = set(normalized.split("_"))
            if tokens & _SERVER_HINTS:
                target = "hostname_server"
            elif tokens & _CLIENT_HINTS:
                target = "hostname_client"
            else:
                target = "hostname"  # fallback
            if target not in used_fields:
                mapping[column] = target
                used_fields.add(target)
            continue

        if canonical is not None and canonical not in used_fields:
            mapping[column] = canonical
            used_fields.add(canonical)

    return mapping


def apply_mapping(records: list[dict[str, Any]], mapping: dict[str, str]) -> list[dict[str, Any]]:
    """Áp dụng mapping do người dùng chỉ định lên danh sách records.

    mapping: {"source_column_name": "target_field_name"}
    Các cột không có trong mapping sẽ được giữ nguyên.
    """
    if not mapping:
        return records

    mapped_records: list[dict[str, Any]] = []
    for record in records:
        mapped_record: dict[str, Any] = {}
        for key, value in record.items():
            target_key = mapping.get(key, key)
            mapped_record[target_key] = value
        mapped_records.append(mapped_record)

    return mapped_records


def split_dual_hostname_rows(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Tách mỗi record có hostname_server + hostname_client thành 2 records riêng biệt.

    Nếu record có hostname_server → tạo record type=server với hostname=hostname_server
    Nếu record có hostname_client → tạo record type=client với hostname=hostname_client
    Record nào có cả 2 → tạo 2 records. Hostname trống thì bỏ qua.
    """
    result: list[dict[str, Any]] = []
    for record in records:
        server_name = str(record.get("hostname_server", "")).strip()
        client_name = str(record.get("hostname_client", "")).strip()

        # Build base record without dual hostname fields
        base = {k: v for k, v in record.items() if k not in ("hostname_server", "hostname_client")}

        if server_name and server_name.lower() not in ("", "nan", "none", "null"):
            server_rec = {**base, "hostname": server_name, "type": "server"}
            result.append(server_rec)

        if client_name and client_name.lower() not in ("", "nan", "none", "null"):
            client_rec = {**base, "hostname": client_name, "type": "client"}
            result.append(client_rec)

        # Fallback: if neither is set but there's a regular hostname, keep it
        if not server_name and not client_name:
            if str(record.get("hostname", "")).strip():
                result.append(record)

    return result


def validate_mapping(mapping: dict[str, str], columns: list[str]) -> list[str]:
    """Kiểm tra tính hợp lệ của mapping.

    Trả về danh sách lỗi (rỗng nếu hợp lệ).
    """
    errors: list[str] = []
    known_fields = {field["field"] for field in MAPPABLE_FIELDS}

    # Kiem tra source column ton tai
    for source_col in mapping:
        if source_col not in columns:
            errors.append(f"Cot nguon '{source_col}' khong ton tai trong du lieu.")

    # Kiem tra target field hop le
    for source_col, target_field in mapping.items():
        if target_field not in known_fields:
            errors.append(
                f"Truong dich '{target_field}' khong hop le. "
                f"Cac truong hop le: {', '.join(sorted(known_fields))}"
            )

    # Cho phep hostname hoac hostname_server/hostname_client, nhung khong ca hai
    target_values = set(mapping.values())
    has_hostname = "hostname" in target_values
    has_dual = "hostname_server" in target_values or "hostname_client" in target_values
    if has_hostname and has_dual:
        errors.append(
            "Không thể dùng đồng thời 'Hostname' và 'Hostname (Máy chủ/Máy trạm)'. "
            "Hãy chọn một trong hai cách."
        )

    # Kiem tra trung lap target
    target_counts: dict[str, int] = {}
    for target in mapping.values():
        target_counts[target] = target_counts.get(target, 0) + 1
    for target, count in target_counts.items():
        if count > 1:
            errors.append(f"Truong '{target}' duoc map tu {count} cot khac nhau.")

    return errors
