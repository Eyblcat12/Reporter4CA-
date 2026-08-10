"""Structured JSON and human-readable HTML reports for Golden DOCX regressions."""

from __future__ import annotations

import html
import json
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

_MISSING = object()


def _category(path: str) -> str:
    root = path.removeprefix("root.").split(".", 1)[0].split("[", 1)[0]
    return {
        "headings": "Headings",
        "tables": "Tables",
        "paragraphCount": "Paragraphs",
        "paragraphDigest": "Paragraphs",
        "snapshotSchemaVersion": "Snapshot Schema",
        "numberedParagraphs": "Numbering",
        "remainingTokens": "Tokens",
        "sectionCount": "Sections",
        "sections": "Sections",
        "headersFooters": "Header/Footer",
        "relationships": "Relationships",
        "media": "Media",
        "tocFields": "TOC/Fields",
        "semanticCounts": "Findings/Evidence",
    }.get(root, "Other")


def _difference(
    change: str, path: str, expected: Any = _MISSING, actual: Any = _MISSING
) -> dict[str, Any]:
    result: dict[str, Any] = {"change": change, "category": _category(path), "path": path}
    if expected is not _MISSING:
        result["expected"] = expected
    if actual is not _MISSING:
        result["actual"] = actual
    return result


def structural_diff(expected: Any, actual: Any, path: str = "root") -> list[dict[str, Any]]:
    """Compare nested snapshots while keeping list differences addressable by index."""
    differences: list[dict[str, Any]] = []
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key in sorted(set(expected) | set(actual)):
            child = f"{path}.{key}"
            if key not in expected:
                differences.append(_difference("added", child, actual=actual[key]))
            elif key not in actual:
                differences.append(_difference("removed", child, expected=expected[key]))
            else:
                differences.extend(structural_diff(expected[key], actual[key], child))
    elif isinstance(expected, list) and isinstance(actual, list):
        for index in range(max(len(expected), len(actual))):
            child = f"{path}[{index}]"
            if index >= len(expected):
                differences.append(_difference("added", child, actual=actual[index]))
            elif index >= len(actual):
                differences.append(_difference("removed", child, expected=expected[index]))
            else:
                differences.extend(structural_diff(expected[index], actual[index], child))
    elif expected != actual:
        differences.append(_difference("changed", path, expected=expected, actual=actual))
    return differences


def _summary(differences: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "total": len(differences),
        "byChange": dict(sorted(Counter(item["change"] for item in differences).items())),
        "byCategory": dict(sorted(Counter(item["category"] for item in differences).items())),
    }


def build_diff_report(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = sum(len(item["differences"]) for item in results)
    all_differences = [difference for item in results for difference in item["differences"]]
    return {
        "schemaVersion": 1,
        "createdAt": datetime.now(timezone.utc).isoformat(),
        "status": "failed" if total else "passed",
        "summary": _summary(all_differences),
        "reportTypes": [
            {
                "reportType": item["reportType"],
                "status": "failed" if item["differences"] else "passed",
                "summary": _summary(item["differences"]),
                "differences": item["differences"],
            }
            for item in results
        ],
    }


def _display(value: Any) -> str:
    if value is _MISSING:
        return "—"
    return json.dumps(value, ensure_ascii=False, indent=2)


def render_diff_html(report: dict[str, Any]) -> str:
    sections: list[str] = []
    for item in report["reportTypes"]:
        rows = []
        for difference in item["differences"]:
            rows.append(
                "<tr>"
                f"<td><span class='change {html.escape(difference['change'])}'>{html.escape(difference['change'])}</span></td>"
                f"<td>{html.escape(difference['category'])}</td>"
                f"<td><code>{html.escape(difference['path'])}</code></td>"
                f"<td><pre>{html.escape(_display(difference.get('expected', _MISSING)))}</pre></td>"
                f"<td><pre>{html.escape(_display(difference.get('actual', _MISSING)))}</pre></td>"
                "</tr>"
            )
        table = (
            "<table><thead><tr><th>Change</th><th>Category</th><th>Path</th>"
            "<th>Golden</th><th>Actual</th></tr></thead><tbody>"
            + "".join(rows)
            + "</tbody></table>"
            if rows
            else "<p class='passed'>No structural differences.</p>"
        )
        sections.append(
            f"<section><h2>{html.escape(item['reportType'])} "
            f"<span class='count'>{item['summary']['total']} differences</span></h2>{table}</section>"
        )

    summary_cards = (
        "".join(
            f"<div class='card'><strong>{count}</strong><span>{html.escape(category)}</span></div>"
            for category, count in report["summary"]["byCategory"].items()
        )
        or "<div class='card'><strong>0</strong><span>Differences</span></div>"
    )
    return f"""<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Golden DOCX structural diff</title><style>
:root {{ color-scheme: dark; font-family: Inter,Segoe UI,sans-serif; background:#090b12; color:#eef0f7; }}
body {{ margin:0; padding:32px; }} main {{ max-width:1500px; margin:auto; }}
h1 {{ margin-bottom:6px; }} .meta {{ color:#9ba3b8; margin-bottom:24px; }}
.summary {{ display:flex; flex-wrap:wrap; gap:10px; margin:20px 0 30px; }}
.card {{ min-width:120px; padding:14px 18px; border:1px solid #292e3d; border-radius:12px; background:#121622; }}
.card strong,.card span {{ display:block; }} .card strong {{ font-size:22px; }} .card span {{ color:#9ba3b8; font-size:12px; }}
section {{ margin:24px 0; padding:20px; border:1px solid #292e3d; border-radius:14px; background:#0f131e; }}
h2 {{ margin-top:0; }} .count {{ color:#9ba3b8; font-size:13px; font-weight:500; }}
table {{ width:100%; border-collapse:collapse; font-size:13px; }} th,td {{ border-top:1px solid #292e3d; padding:10px; text-align:left; vertical-align:top; }}
th {{ color:#9ba3b8; }} code {{ color:#b8a7ff; }} pre {{ max-width:420px; margin:0; white-space:pre-wrap; word-break:break-word; }}
.change {{ padding:3px 7px; border-radius:999px; font-weight:700; text-transform:uppercase; font-size:10px; }}
.changed {{ background:#4a3513; color:#ffd37a; }} .added {{ background:#123b2f; color:#74e0b7; }} .removed {{ background:#491e28; color:#ff9cac; }}
.passed {{ color:#74e0b7; }}
</style></head><body><main><h1>Golden DOCX structural diff</h1>
<p class="meta">Status: {html.escape(report["status"].upper())} · Generated {html.escape(report["createdAt"])}</p>
<div class="summary">{summary_cards}</div>{"".join(sections)}</main></body></html>"""


def write_diff_reports(results: list[dict[str, Any]], output_dir: Path) -> tuple[Path, Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    report = build_diff_report(results)
    json_path = output_dir / "golden-docx-diff.json"
    html_path = output_dir / "golden-docx-diff.html"
    json_path.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    html_path.write_text(render_diff_html(report), encoding="utf-8")
    return json_path, html_path
