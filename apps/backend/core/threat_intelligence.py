"""Evidence-preserving IoC and MITRE ATT&CK normalization."""

from __future__ import annotations

import ipaddress
import re
from typing import Any
from urllib.parse import urlsplit, urlunsplit

_HASH_LENGTHS = {32: "md5", 40: "sha1", 64: "sha256"}
_DOMAIN = re.compile(r"^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z]{2,63}$", re.I)
_FILENAME = re.compile(r"^[^<>:\"/\\|?*\x00-\x1f]+$")
_TECHNIQUE = re.compile(r"^T\d{4}(?:\.\d{3})?$")


def normalize_iocs(items: list[Any], *, default_source: str = "input") -> list[dict[str, Any]]:
    normalized: dict[tuple[str, str], dict[str, Any]] = {}
    for item in items if isinstance(items, list) else []:
        raw = item if isinstance(item, dict) else {"value": item}
        value = str(raw.get("value") or raw.get("indicator") or "").strip()
        if not value:
            continue
        ioc_type, canonical, valid = _normalize_value(value, str(raw.get("type") or "").lower())
        source = str(raw.get("source") or raw.get("evidence") or default_source).strip()
        # Hostnames and hashes are already canonical; URL paths, queries and
        # filenames may be case-sensitive evidence.
        key = (ioc_type, canonical)
        if key not in normalized:
            normalized[key] = {
                "type": ioc_type,
                "value": canonical,
                "valid": valid,
                "sources": [],
                "detail": str(raw.get("detail") or ""),
            }
        sources = raw.get("sources") if isinstance(raw.get("sources"), list) else [source]
        for evidence in sources:
            evidence = str(evidence).strip()
            if evidence and evidence not in normalized[key]["sources"]:
                normalized[key]["sources"].append(evidence)
    return list(normalized.values())


def collect_iocs(metadata: dict[str, Any], assets: Any) -> list[dict[str, Any]]:
    """Collect structured evidence consistently across all report renderers."""
    raw = list(metadata.get("iocs", [])) if isinstance(metadata.get("iocs"), list) else []
    for asset in assets:
        extras = asset.get("extras") if isinstance(asset.get("extras"), dict) else {}
        items = asset.get("iocs", extras.get("iocs", []))
        for item in items if isinstance(items, list) else []:
            entry = dict(item) if isinstance(item, dict) else {"value": item}
            entry.setdefault("source", asset.get("hostname") or "asset")
            raw.append(entry)
    return normalize_iocs(raw)


def _normalize_value(value: str, declared: str) -> tuple[str, str, bool]:
    try:
        address = ipaddress.ip_address(value)
        return "ip", address.compressed, declared in {"", "ip", f"ipv{address.version}"}
    except ValueError:
        pass
    if declared in {"ip", "ipv4", "ipv6"}:
        return "ip", value, False
    if declared in {"url", "uri"} or "://" in value:
        try:
            parsed = urlsplit(value)
            host = (parsed.hostname or "").lower()
            port = parsed.port
        except ValueError:
            return "url", value, False
        valid = (
            parsed.scheme.lower() in {"http", "https"}
            and declared in {"", "url", "uri"}
            and bool(host)
            and not any(character.isspace() or ord(character) < 32 for character in value)
        )
        if not valid:
            return "url", value, False
        netloc = f"[{host}]" if ":" in host else host
        if port is not None:
            netloc += f":{port}"
        if "@" in parsed.netloc:
            netloc = parsed.netloc.rsplit("@", 1)[0] + "@" + netloc
        return (
            "url",
            urlunsplit(
                (parsed.scheme.lower(), netloc, parsed.path or "/", parsed.query, parsed.fragment)
            ),
            valid,
        )
    compact = value.lower()
    if (
        all(character in "0123456789abcdef" for character in compact)
        and len(compact) in _HASH_LENGTHS
    ):
        detected = _HASH_LENGTHS[len(compact)]
        return detected, compact, declared in {"", "hash", detected}
    if declared in {"filename", "file"}:
        return "filename", value, bool(_FILENAME.fullmatch(value))
    if declared == "domain" or (not declared and _DOMAIN.fullmatch(compact.rstrip("."))):
        canonical = compact.rstrip(".")
        return "domain", canonical, bool(_DOMAIN.fullmatch(canonical))
    if not declared and "." in value and "/" not in value and "\\" not in value:
        return "filename", value, bool(_FILENAME.fullmatch(value))
    return declared or "unknown", value, False


def normalize_mitre(items: list[Any]) -> list[dict[str, Any]]:
    results: dict[str, dict[str, Any]] = {}
    for item in items if isinstance(items, list) else []:
        raw = item if isinstance(item, dict) else {"technique": item}
        technique = str(raw.get("technique") or raw.get("id") or "").upper().strip()
        if not technique:
            continue
        evidence = str(raw.get("evidence") or raw.get("source") or "").strip()
        results[technique] = {
            "technique": technique,
            "tactic": str(raw.get("tactic") or "Unspecified").strip(),
            "name": str(raw.get("name") or "").strip(),
            "evidence": evidence,
            "valid": bool(_TECHNIQUE.fullmatch(technique) and evidence),
        }
    return list(results.values())
