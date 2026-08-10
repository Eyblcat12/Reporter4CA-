"""Deterministic data-quality checks shared by validation and generation."""

from __future__ import annotations

import ipaddress
from typing import Any


def assess_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    issues: list[dict[str, Any]] = []
    seen_hostnames: dict[str, int] = {}
    error_rows: set[int] = set()
    warning_rows: set[int] = set()
    counters = {
        "duplicateHostnames": 0,
        "invalidIps": 0,
        "missingOs": 0,
        "missingResult": 0,
    }

    def add_issue(row: int, field: str, level: str, code: str, message: str) -> None:
        issues.append(
            {
                "row": row,
                "field": field,
                "level": level,
                "code": code,
                "message": message,
            }
        )
        (error_rows if level == "error" else warning_rows).add(row)

    for index, item in enumerate(rows):
        row_number = index + 1
        hostname = str(item.get("hostname", "")).strip()
        if not hostname:
            add_issue(
                row_number,
                "hostname",
                "error",
                "missing_hostname",
                "Hostname không được để trống.",
            )
        else:
            normalized = hostname.casefold()
            if normalized in seen_hostnames:
                counters["duplicateHostnames"] += 1
                add_issue(
                    row_number,
                    "hostname",
                    "warning",
                    "duplicate_hostname",
                    f"Hostname '{hostname}' bị trùng với dòng {seen_hostnames[normalized]}.",
                )
            else:
                seen_hostnames[normalized] = row_number

        ip_value = str(item.get("ip", "")).strip()
        if ip_value:
            try:
                ipaddress.ip_address(ip_value)
            except ValueError:
                counters["invalidIps"] += 1
                add_issue(
                    row_number,
                    "ip",
                    "warning",
                    "invalid_ip",
                    f"Địa chỉ IP '{ip_value}' không hợp lệ.",
                )

        if not str(item.get("os", "")).strip():
            counters["missingOs"] += 1
            add_issue(
                row_number,
                "os",
                "warning",
                "missing_os",
                "Hệ điều hành (OS) đang trống.",
            )

        if not str(item.get("result", "")).strip():
            counters["missingResult"] += 1
            add_issue(
                row_number,
                "result",
                "warning",
                "missing_result",
                "Kết quả đánh giá đang trống.",
            )

    servers = sum(1 for row in rows if row.get("type") == "server")
    clients = sum(1 for row in rows if row.get("type") == "client")
    summary = {
        "totalRows": len(rows),
        "validRows": len(rows) - len(error_rows),
        "errorRows": len(error_rows),
        "warningRows": len(warning_rows),
        "errors": sum(1 for issue in issues if issue["level"] == "error"),
        "warnings": sum(1 for issue in issues if issue["level"] == "warning"),
        "servers": servers,
        "clients": clients,
        **counters,
    }
    return {"valid": not error_rows, "issues": issues, "summary": summary}
