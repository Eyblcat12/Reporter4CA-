"""Streaming canonical identities for report requests and prepared content."""

from __future__ import annotations

import hashlib
import json
import math
import unicodedata
from collections.abc import Mapping, Sequence
from typing import Any

SIGNATURE_SCHEMA_VERSION = "1.0"


class CanonicalValueError(ValueError):
    """Raised when a value cannot have one stable, cross-process identity."""


def normalize_string(value: str) -> str:
    return unicodedata.normalize("NFC", value)


def canonical_sha256(value: Any) -> str:
    """Hash canonical JSON-like data incrementally without one giant JSON copy."""

    digest = hashlib.sha256()
    for chunk in iter_canonical_chunks(value):
        digest.update(chunk)
    return digest.hexdigest()


def iter_canonical_chunks(value: Any):
    """Yield unambiguous UTF-8 chunks; mappings sort keys, sequences keep order."""

    if value is None:
        yield b"n;"
        return
    if isinstance(value, bool):
        yield b"b1;" if value else b"b0;"
        return
    if isinstance(value, int):
        yield f"i{value};".encode("ascii")
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise CanonicalValueError("NaN and Infinity are not valid report values.")
        encoded = json.dumps(value, allow_nan=False, separators=(",", ":"))
        yield b"f" + encoded.encode("ascii") + b";"
        return
    if isinstance(value, str):
        encoded = normalize_string(value).encode("utf-8")
        yield f"s{len(encoded)}:".encode("ascii")
        yield encoded
        yield b";"
        return
    if isinstance(value, Mapping):
        normalized_items: list[tuple[str, Any]] = []
        seen: set[str] = set()
        for key, item in value.items():
            if not isinstance(key, str):
                raise CanonicalValueError("Report object keys must be strings.")
            normalized_key = normalize_string(key)
            if normalized_key in seen:
                raise CanonicalValueError("Unicode normalization produced a duplicate key.")
            seen.add(normalized_key)
            normalized_items.append((normalized_key, item))
        normalized_items.sort(key=lambda item: item[0])
        yield f"m{len(normalized_items)}[".encode("ascii")
        for key, item in normalized_items:
            yield from iter_canonical_chunks(key)
            yield from iter_canonical_chunks(item)
        yield b"]"
        return
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, memoryview)):
        yield f"a{len(value)}[".encode("ascii")
        for item in value:
            yield from iter_canonical_chunks(item)
        yield b"]"
        return
    raise CanonicalValueError(f"Unsupported canonical report value: {type(value).__name__}")
