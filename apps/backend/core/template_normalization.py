"""Explicit, copy-only placement of stable anchors into an unprepared DOCX."""

from __future__ import annotations

import io
from typing import Any

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

from .template_profile_analyzer import analyze_profile_template
from .template_profiles import REPORT_REQUIREMENTS


def structure_blocks(data: bytes, report_type: str) -> list[dict[str, Any]]:
    analyze_profile_template(data, report_type)
    document = Document(io.BytesIO(data))
    return [
        {
            "index": index,
            "kind": "table" if node.tag == qn("w:tbl") else "paragraph",
            "text": " ".join(t.text or "" for t in node.iter(qn("w:t")))[:220] or "(trống)",
        }
        for index, node in enumerate(document.element.body)
        if node.tag in {qn("w:p"), qn("w:tbl")}
    ]


def normalize_template_source(
    data: bytes, report_type: str, placements: list[dict[str, Any]]
) -> bytes:
    blocks = {item["index"]: item for item in structure_blocks(data, report_type)}
    required = set(REPORT_REQUIREMENTS[report_type])
    if {item["semantic"] for item in placements} != required or len(placements) != len(required):
        raise ValueError("Chọn vị trí cho đầy đủ các nội dung bắt buộc, không trùng semantic.")
    if len({item["blockIndex"] for item in placements}) != len(placements):
        raise ValueError("Mỗi vị trí chỉ được dùng cho một nội dung.")
    document = Document(io.BytesIO(data))
    nodes = list(document.element.body)
    for item in placements:
        if item["blockIndex"] not in blocks or item["mode"] not in {"after", "replace"}:
            raise ValueError("Vị trí hoặc chế độ chuẩn hóa không hợp lệ.")
        node = nodes[item["blockIndex"]]
        if item["mode"] == "replace" and any(
            element.tag == qn("w:sectPr") for element in node.iter()
        ):
            raise ValueError(
                "Đoạn chứa section break không thể thay thế. Chọn chèn phía sau hoặc một vùng nội dung khác."
            )
        # Do not enclose existing anchors; overlapping controls are ambiguous.
        if any(element.tag in {qn("w:sdt"), qn("w:bookmarkStart")} for element in node.iter()):
            raise ValueError("Vị trí đã chứa anchor. Chọn một vị trí không lồng anchor.")
        control = OxmlElement("w:sdt")
        properties = OxmlElement("w:sdtPr")
        tag = OxmlElement("w:tag")
        tag.set(qn("w:val"), "REPORTER_" + item["semantic"].upper().replace(".", "_"))
        properties.append(tag)
        control.append(properties)
        content = OxmlElement("w:sdtContent")
        control.append(content)
        node.addnext(control)
        if item["mode"] == "replace":
            content.append(node)
        else:
            content.append(OxmlElement("w:p"))
    output = io.BytesIO()
    document.save(output)
    normalized = output.getvalue()
    analysis = analyze_profile_template(normalized, report_type)
    if analysis["facts"]["anchorConflicts"]:
        raise ValueError("Chuẩn hóa gây trùng anchor; nguồn gốc chưa bị thay đổi.")
    return normalized
