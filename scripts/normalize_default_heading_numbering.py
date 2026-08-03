from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn


ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "backend"
sys.path.insert(0, str(BACKEND))

from core.report_generator import _create_reporter_heading_numbering  # noqa: E402


def normalize_template(template_path: Path, backup_root: Path) -> Path:
    relative_path = template_path.resolve().relative_to(ROOT.resolve())
    backup_path = backup_root / relative_path
    backup_path.parent.mkdir(parents=True, exist_ok=True)
    if not backup_path.exists():
        shutil.copy2(template_path, backup_path)

    document = Document(template_path)
    num_id = _create_reporter_heading_numbering(
        document.part.numbering_part.element
    )
    if num_id is None:
        raise RuntimeError("Unable to create Reporter heading numbering")

    for level in range(1, 4):
        style = document.styles[f"Heading {level}"]
        style.paragraph_format.left_indent = 0
        style.paragraph_format.first_line_indent = 0

        p_pr = style.element.get_or_add_pPr()
        current_num_pr = p_pr.find(qn("w:numPr"))
        if current_num_pr is not None:
            p_pr.remove(current_num_pr)
        num_pr = OxmlElement("w:numPr")
        ilvl = OxmlElement("w:ilvl")
        ilvl.set(qn("w:val"), str(level - 1))
        num_id_element = OxmlElement("w:numId")
        num_id_element.set(qn("w:val"), str(num_id))
        num_pr.append(ilvl)
        num_pr.append(num_id_element)
        p_pr.append(num_pr)

    temporary_path = template_path.with_suffix(".heading-update.tmp.docx")
    document.save(temporary_path)
    Document(temporary_path)
    temporary_path.replace(template_path)
    return backup_path


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Align and reset Heading 1-3 numbering in a Reporter Pro template."
    )
    parser.add_argument(
        "template",
        nargs="?",
        type=Path,
        default=BACKEND / "templates" / "report_template.docx",
    )
    parser.add_argument(
        "--backup-root",
        type=Path,
        default=ROOT / "artifacts" / "template-backups" / "heading-numbering-20260730",
    )
    args = parser.parse_args()

    template_path = args.template.resolve()
    if not template_path.is_file():
        raise FileNotFoundError(template_path)
    backup_path = normalize_template(template_path, args.backup_root.resolve())
    print(f"Updated: {template_path}")
    print(f"Backup:  {backup_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
