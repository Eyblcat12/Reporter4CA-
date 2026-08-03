from __future__ import annotations

from typing import Any

from core.input_preprocessor import DEFAULT_SECTION, normalize_asset_type


GUI_ROW_KEYS = ("type", "hostname", "os", "ip", "notes", "result")
BASE_ASSET_KEYS = {"hostname", "os", "ip", "notes", "result"}


def blank_gui_row(asset_type: str = "client") -> dict[str, Any]:
    normalized_type = normalize_gui_asset_type(asset_type)
    return {
        "type": normalized_type,
        "hostname": "",
        "os": "",
        "ip": "",
        "notes": "",
        "result": "",
        "extras": {},
    }


def normalize_gui_asset_type(value: Any, *, default_type: str = "client") -> str:
    default_section = "servers" if default_type == "server" else DEFAULT_SECTION
    normalized_section = normalize_asset_type(value, default_section=default_section)
    return "server" if normalized_section == "servers" else "client"


def sanitize_gui_row(record: dict[str, Any], *, default_type: str = "client") -> dict[str, Any]:
    sanitized = blank_gui_row(default_type)
    sanitized["type"] = normalize_gui_asset_type(record.get("type"), default_type=default_type)

    for key in ("hostname", "os", "ip", "notes", "result"):
        sanitized[key] = str(record.get(key, "") or "").strip()

    extras = record.get("extras", {})
    if isinstance(extras, dict):
        sanitized["extras"] = {
            str(key): value
            for key, value in extras.items()
            if key not in BASE_ASSET_KEYS and key != "type"
        }

    return sanitized


def build_payload_from_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    payload: dict[str, Any] = {"servers": [], "clients": [], "metadata": {}}

    for row in rows:
        sanitized = sanitize_gui_row(row)
        if not sanitized["hostname"]:
            continue

        asset = {
            "hostname": sanitized["hostname"],
            "ip": sanitized["ip"],
            "os": sanitized["os"],
        }

        # Ho tro truong 'result' — ket qua danh gia cho tung asset
        if sanitized["result"]:
            asset["result"] = sanitized["result"]

        if sanitized["notes"]:
            asset["notes"] = sanitized["notes"]

        extras = sanitized.get("extras", {})
        if isinstance(extras, dict):
            for key, value in extras.items():
                if key not in asset and key != "type":
                    asset[key] = value

        section = "servers" if sanitized["type"] == "server" else "clients"
        payload[section].append(asset)

    return payload


def normalized_payload_to_rows(data: dict[str, Any]) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []

    for section, asset_type in (("servers", "server"), ("clients", "client")):
        for item in data.get(section, []):
            if not isinstance(item, dict):
                continue

            row = blank_gui_row(asset_type)
            row["hostname"] = str(item.get("hostname", "") or "").strip()
            row["os"] = str(item.get("os", "") or "").strip()
            row["ip"] = str(item.get("ip", "") or "").strip()
            row["notes"] = str(item.get("notes", "") or "").strip()
            row["result"] = str(item.get("result", "") or "").strip()
            row["extras"] = {
                str(key): value
                for key, value in item.items()
                if key not in BASE_ASSET_KEYS and key != "type"
            }
            rows.append(row)

    return rows


def summarize_rows(rows: list[dict[str, Any]]) -> dict[str, int]:
    servers = 0
    clients = 0

    for row in rows:
        sanitized = sanitize_gui_row(row)
        if not sanitized["hostname"]:
            continue
        if sanitized["type"] == "server":
            servers += 1
        else:
            clients += 1

    return {
        "servers": servers,
        "clients": clients,
        "total": servers + clients,
    }
