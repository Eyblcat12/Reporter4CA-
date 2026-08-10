"""Compact, immutable table blueprints for a future DOCX fast path.

This module deliberately has no integration with ``report_generator`` yet.  It
provides two small building blocks:

* a conservative classifier that decides whether a prototype table is simple
  enough for a fast writer; and
* a compact blueprint containing only table properties, grid, header row and
  the distinct data-row style variants that are actually required.

Anything the classifier does not understand remains on the legacy path.
"""

from __future__ import annotations

import hashlib
import json
from copy import deepcopy
from dataclasses import dataclass
from typing import Any, Iterable

from docx.oxml import OxmlElement, parse_xml
from docx.oxml.ns import qn
from lxml import etree

BLUEPRINT_SCHEMA_VERSION = 1
OFFICE_RELATIONSHIP_NS = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"


@dataclass(frozen=True, slots=True)
class FastPathClassification:
    """Result of the conservative table/cell safety inspection."""

    safe: bool
    reasons: tuple[str, ...] = ()

    @property
    def path(self) -> str:
        return "fast" if self.safe else "legacy"

    @property
    def requires_fallback(self) -> bool:
        return not self.safe


class UnsafeTableBlueprintError(ValueError):
    """Raised when an unsafe prototype is sent to the compact compiler."""

    def __init__(self, classification: FastPathClassification) -> None:
        self.classification = classification
        joined = ", ".join(classification.reasons) or "unknown_structure"
        super().__init__(f"Table prototype requires legacy fallback: {joined}")


@dataclass(frozen=True, slots=True)
class TableBlueprint:
    """Immutable XML fragments required to reconstruct one prototype table."""

    schema_version: int
    fingerprint: str
    column_count: int
    tbl_pr_xml: bytes
    tbl_grid_xml: bytes
    header_row_xml: bytes
    data_row_variants_xml: tuple[bytes, ...]
    data_row_variant_fingerprints: tuple[str, ...]
    source_xml_bytes: int
    compact_xml_bytes: int
    source_node_count: int
    compact_node_count: int

    @property
    def data_row_variant_count(self) -> int:
        return len(self.data_row_variants_xml)

    @property
    def requires_integration_fallback(self) -> bool:
        """Whether the first fast-path integration must retain legacy rendering.

        The standalone compiler deliberately preserves up to two variants so
        they can be inspected and fingerprinted.  Integration v1 only knows
        how to select one deterministic data-row style.
        """

        return self.data_row_variant_count != 1

    def to_table_element(self) -> Any:
        """Return a fresh ``w:tbl`` containing only retained blueprint parts."""

        table = OxmlElement("w:tbl")
        for fragment in (
            self.tbl_pr_xml,
            self.tbl_grid_xml,
            self.header_row_xml,
            *self.data_row_variants_xml,
        ):
            if fragment:
                table.append(parse_xml(fragment))
        return table


def _table_element(table: Any) -> Any:
    element = getattr(table, "_tbl", table)
    if getattr(element, "tag", None) != qn("w:tbl"):
        raise TypeError("Expected a python-docx Table or w:tbl element.")
    return element


def _canonical_xml(element: Any | None) -> bytes:
    if element is None:
        return b""
    normalized = deepcopy(element)
    for node in normalized.iter():
        for attribute_name in list(node.attrib):
            qualified = etree.QName(attribute_name)
            if qualified.localname.casefold().startswith("rsid"):
                del node.attrib[attribute_name]
    return etree.tostring(normalized, method="c14n")


def _serialize(element: Any | None) -> bytes:
    if element is None:
        return b""
    return etree.tostring(element, encoding="UTF-8", xml_declaration=False)


def _node_count(element: Any) -> int:
    return sum(1 for _ in element.iter())


def _run_style_signature(run: Any) -> bytes:
    return _canonical_xml(run.find(qn("w:rPr")))


def _row_style_signature(row: Any) -> str:
    """Hash row/cell/paragraph/run formatting while ignoring sample text."""

    cells: list[dict[str, Any]] = []
    for cell in row.findall(qn("w:tc")):
        paragraphs: list[dict[str, Any]] = []
        for paragraph in cell.findall(qn("w:p")):
            styles: list[str] = []
            for run in paragraph.findall(qn("w:r")):
                encoded = _run_style_signature(run).hex()
                if not styles or styles[-1] != encoded:
                    styles.append(encoded)
            paragraphs.append(
                {
                    "pPr": _canonical_xml(paragraph.find(qn("w:pPr"))).hex(),
                    "runStyles": styles,
                }
            )
        cells.append(
            {
                "tcPr": _canonical_xml(cell.find(qn("w:tcPr"))).hex(),
                "paragraphs": paragraphs,
            }
        )
    payload = {
        "trPr": _canonical_xml(row.find(qn("w:trPr"))).hex(),
        "cells": cells,
    }
    canonical = json.dumps(
        payload,
        ensure_ascii=True,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("ascii")
    return hashlib.sha256(canonical).hexdigest()


def _has_relationship_attribute(element: Any) -> bool:
    for node in element.iter():
        for attribute_name in node.attrib:
            if etree.QName(attribute_name).namespace == OFFICE_RELATIONSHIP_NS:
                return True
    return False


def _append_reason(reasons: list[str], reason: str) -> None:
    if reason not in reasons:
        reasons.append(reason)


def _classify_table_and_row_structure(
    element: Any,
    rows: list[Any],
    reasons: list[str],
) -> None:
    """Validate the direct OOXML shape the compact writer understands."""

    allowed_table_children = {qn("w:tblPr"), qn("w:tblGrid"), qn("w:tr")}
    if any(child.tag not in allowed_table_children for child in element):
        _append_reason(reasons, "unsupported_table_content")

    grids = element.findall(qn("w:tblGrid"))
    grid_columns: list[Any] = []
    if len(grids) != 1:
        _append_reason(reasons, "malformed_table_grid")
    else:
        grid = grids[0]
        grid_columns = list(grid.findall(qn("w:gridCol")))
        if (
            not grid_columns
            or any(child.tag != qn("w:gridCol") for child in grid)
            or any(len(column) for column in grid_columns)
        ):
            _append_reason(reasons, "malformed_table_grid")

    allowed_row_children = {qn("w:trPr"), qn("w:tc")}
    for row in rows:
        for child in row:
            if child.tag == qn("w:tblPrEx"):
                _append_reason(reasons, "row_property_exception")
            elif child.tag not in allowed_row_children:
                _append_reason(reasons, "unsupported_row_content")

    if not rows:
        return
    header_cell_count = len(rows[0].findall(qn("w:tc")))
    grid_column_count = len(grid_columns)
    if (
        header_cell_count < 1
        or (grid_column_count and header_cell_count != grid_column_count)
        or any(
            len(row.findall(qn("w:tc"))) != header_cell_count
            or (grid_column_count and len(row.findall(qn("w:tc"))) != grid_column_count)
            for row in rows
        )
    ):
        _append_reason(reasons, "column_count_mismatch")


def _has_unsupported_cell_content(cell: Any) -> bool:
    """Reject content-layer XML the future simple writer does not model."""

    allowed_cell_children = {qn("w:tcPr"), qn("w:p")}
    allowed_paragraph_children = {
        qn("w:pPr"),
        qn("w:r"),
        qn("w:proofErr"),
        qn("w:bookmarkStart"),
        qn("w:bookmarkEnd"),
    }
    allowed_run_children = {
        qn("w:rPr"),
        qn("w:t"),
        qn("w:tab"),
        qn("w:br"),
        qn("w:cr"),
        qn("w:noBreakHyphen"),
        qn("w:softHyphen"),
    }
    for child in cell:
        if child.tag not in allowed_cell_children:
            return True
        if child.tag != qn("w:p"):
            continue
        for paragraph_child in child:
            if paragraph_child.tag not in allowed_paragraph_children:
                return True
            if paragraph_child.tag != qn("w:r"):
                continue
            if any(run_child.tag not in allowed_run_children for run_child in paragraph_child):
                return True
    return False


def classify_table_for_fast_path(table: Any) -> FastPathClassification:
    """Return a conservative fast/legacy decision for a prototype table.

    The classifier intentionally prefers false negatives over format loss.  A
    later integration can use ``classification.path`` without interpreting XML.
    """

    element = _table_element(table)
    reasons: list[str] = []
    rows = element.findall(qn("w:tr"))
    if not rows:
        _append_reason(reasons, "missing_header_row")
    elif len(rows) < 2:
        _append_reason(reasons, "missing_data_row")

    _classify_table_and_row_structure(element, rows, reasons)

    if element.find(".//" + qn("w:gridSpan")) is not None:
        _append_reason(reasons, "merged_cell")
    if element.find(".//" + qn("w:hMerge")) is not None:
        _append_reason(reasons, "merged_cell")
    if element.find(".//" + qn("w:vMerge")) is not None:
        _append_reason(reasons, "vertical_merge")
    if element.find(".//" + qn("w:hyperlink")) is not None:
        _append_reason(reasons, "hyperlink")
    if any(
        element.find(".//" + qn(tag)) is not None
        for tag in ("w:fldSimple", "w:fldChar", "w:instrText", "w:delInstrText")
    ):
        _append_reason(reasons, "field_code")
    if element.find(".//" + qn("w:sdt")) is not None:
        _append_reason(reasons, "content_control")

    for cell in element.iter(qn("w:tc")):
        if cell.find("./" + qn("w:tbl")) is not None:
            _append_reason(reasons, "nested_table")
        if _has_relationship_attribute(cell):
            _append_reason(reasons, "cell_relationship")
        if _has_unsupported_cell_content(cell):
            _append_reason(reasons, "unsupported_cell_content")

        paragraphs = list(cell.findall(qn("w:p")))
        if len(paragraphs) > 1:
            _append_reason(reasons, "multiple_paragraphs")
        for paragraph in paragraphs:
            run_styles = {_run_style_signature(run) for run in paragraph.findall(qn("w:r"))}
            if len(run_styles) > 1:
                _append_reason(reasons, "mixed_run_styles")

    return FastPathClassification(safe=not reasons, reasons=tuple(reasons))


def _fingerprint_parts(parts: Iterable[bytes]) -> str:
    digest = hashlib.sha256()
    digest.update(f"reporter-table-blueprint-v{BLUEPRINT_SCHEMA_VERSION}".encode("ascii"))
    for part in parts:
        digest.update(len(part).to_bytes(8, byteorder="big", signed=False))
        digest.update(part)
    return digest.hexdigest()


def compile_table_blueprint(
    table: Any,
    *,
    max_data_variants: int = 2,
) -> TableBlueprint:
    """Compile a safe prototype into compact immutable XML fragments.

    Distinct sample text does not create a new variant.  A variant is retained
    only when row, cell, paragraph or run formatting genuinely differs.
    """

    if max_data_variants < 1:
        raise ValueError("max_data_variants must be at least 1")

    element = _table_element(table)
    classification = classify_table_for_fast_path(element)
    if classification.requires_fallback:
        raise UnsafeTableBlueprintError(classification)

    rows = list(element.findall(qn("w:tr")))
    header_row = rows[0]
    variants: list[Any] = []
    variant_fingerprints: list[str] = []
    for row in rows[1:]:
        fingerprint = _row_style_signature(row)
        if fingerprint in variant_fingerprints:
            continue
        variants.append(row)
        variant_fingerprints.append(fingerprint)
        if len(variants) > max_data_variants:
            fallback = FastPathClassification(
                safe=False,
                reasons=("too_many_data_row_variants",),
            )
            raise UnsafeTableBlueprintError(fallback)

    tbl_pr = element.find(qn("w:tblPr"))
    tbl_grid = element.find(qn("w:tblGrid"))
    fragments = (
        _serialize(tbl_pr),
        _serialize(tbl_grid),
        _serialize(header_row),
        *(_serialize(row) for row in variants),
    )

    compact = OxmlElement("w:tbl")
    for fragment in fragments:
        if fragment:
            compact.append(parse_xml(fragment))

    fingerprint_parts = (
        _canonical_xml(tbl_pr),
        _canonical_xml(tbl_grid),
        _canonical_xml(header_row),
        *(value.encode("ascii") for value in variant_fingerprints),
    )
    source_xml = _serialize(element)
    compact_xml = _serialize(compact)
    header_cells = header_row.findall(qn("w:tc"))
    grid_columns = tbl_grid.findall(qn("w:gridCol")) if tbl_grid is not None else []
    return TableBlueprint(
        schema_version=BLUEPRINT_SCHEMA_VERSION,
        fingerprint=_fingerprint_parts(fingerprint_parts),
        column_count=len(grid_columns) or len(header_cells),
        tbl_pr_xml=fragments[0],
        tbl_grid_xml=fragments[1],
        header_row_xml=fragments[2],
        data_row_variants_xml=tuple(fragments[3:]),
        data_row_variant_fingerprints=tuple(variant_fingerprints),
        source_xml_bytes=len(source_xml),
        compact_xml_bytes=len(compact_xml),
        source_node_count=_node_count(element),
        compact_node_count=_node_count(compact),
    )


__all__ = [
    "BLUEPRINT_SCHEMA_VERSION",
    "FastPathClassification",
    "TableBlueprint",
    "UnsafeTableBlueprintError",
    "classify_table_for_fast_path",
    "compile_table_blueprint",
]
