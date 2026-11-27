from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
import zipfile
from pathlib import Path
from unittest.mock import patch

from docx import Document
from docx.oxml import OxmlElement
from docx.oxml.ns import qn

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "apps" / "backend"
sys.path.insert(0, str(BACKEND))

from core.docx_field_updater import _word_update_script, refresh_docx_fields  # noqa: E402
from core.report_generator import (  # noqa: E402
    _enable_field_updates,
    _replace_literal_footer_page_totals,
)
from core.report_jobs import JobCancelled  # noqa: E402


class DocxFieldUpdaterTests(unittest.TestCase):
    def test_cancel_while_script_host_is_running_preserves_original(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "report.docx"
            Document().save(path)
            original = path.read_bytes()
            with (
                patch("core.docx_field_updater.platform.system", return_value="Windows"),
                patch("core.docx_field_updater.shutil.which", return_value="cscript.exe"),
                patch("core.docx_field_updater.subprocess.Popen") as popen,
            ):
                process = popen.return_value.__enter__.return_value
                process.wait.side_effect = subprocess.TimeoutExpired("cscript.exe", 0.5)
                process.poll.return_value = None

                def cancel_during_wait():
                    if process.wait.called:
                        raise JobCancelled()

                with self.assertRaises(JobCancelled):
                    refresh_docx_fields(path, check_cancelled=cancel_during_wait)
                process.kill.assert_called_once_with()
            self.assertEqual(path.read_bytes(), original)
            self.assertEqual(list(path.parent.iterdir()), [path])

    def test_timeout_with_word_locked_copy_preserves_original_and_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "report.docx"
            Document().save(path)
            original = path.read_bytes()
            real_unlink = Path.unlink

            def word_locked_copy(candidate, *args, **kwargs):
                if ".field-refresh-" in candidate.name and candidate.suffix == ".docx":
                    raise PermissionError("Synthetic Word file lock")
                return real_unlink(candidate, *args, **kwargs)

            with (
                patch("core.docx_field_updater.platform.system", return_value="Windows"),
                patch("core.docx_field_updater.shutil.which", return_value="cscript.exe"),
                patch(
                    "core.docx_field_updater._run_word_update",
                    side_effect=subprocess.TimeoutExpired("cscript.exe", 180),
                ),
                patch.object(Path, "unlink", word_locked_copy),
            ):
                result = refresh_docx_fields(path)
            self.assertFalse(result.updated)
            self.assertEqual(result.engine, "deferred")
            self.assertIn("timed out", result.detail)
            self.assertEqual(path.read_bytes(), original)

    def test_busy_word_lock_defers_without_running_word(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "report.docx"
            Document().save(path)
            original = path.read_bytes()
            with (
                patch("core.docx_field_updater.platform.system", return_value="Windows"),
                patch("core.docx_field_updater.shutil.which", return_value="cscript.exe"),
                patch("core.docx_field_updater._WORD_UPDATE_LOCK") as lock,
                patch("core.docx_field_updater._run_word_update") as run,
            ):
                lock.acquire.return_value = False
                result = refresh_docx_fields(path, timeout_seconds=2)
            lock.acquire.assert_called_once_with(blocking=False)
            lock.release.assert_not_called()
            run.assert_not_called()
            self.assertFalse(result.updated)
            self.assertIn("busy", result.detail)
            self.assertEqual(path.read_bytes(), original)
            self.assertFalse(any(path.parent.glob("*.field-refresh-*.docx")))

    def test_literal_footer_total_is_replaced_with_dynamic_numpages_field(self) -> None:
        document = Document()
        paragraph = document.sections[0].footer.paragraphs[0]
        paragraph.add_run("Trang ")
        paragraph.add_run("3")
        paragraph.add_run(" / ")
        paragraph.add_run("308")

        self.assertEqual(_replace_literal_footer_page_totals(document), 1)

        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "dynamic-footer.docx"
            document.save(path)
            with zipfile.ZipFile(path) as archive:
                footer_xml = archive.read("word/footer1.xml").decode("utf-8")
        self.assertIn("NUMPAGES", footer_xml)
        self.assertNotIn("SECTIONPAGES", footer_xml)
        self.assertIn('w:dirty="true"', footer_xml)
        # The template literal must not survive as a cached, unverified total.
        self.assertNotIn(">308<", footer_xml)

    def test_restarted_body_section_footer_counts_section_pages_without_cache(self) -> None:
        # Mirrors the default templates: TOC section, then a body section that
        # restarts page numbering and owns the "Trang PAGE / 308" footer.
        document = Document()
        body = document.add_section()
        page_numbering = OxmlElement("w:pgNumType")
        page_numbering.set(qn("w:start"), "1")
        body._sectPr.append(page_numbering)
        body.footer.is_linked_to_previous = False
        paragraph = body.footer.paragraphs[0]
        for value in ("Trang ", "3", " / ", "308"):
            paragraph.add_run(value)

        self.assertEqual(_replace_literal_footer_page_totals(document), 1)

        footer = body.footer._element
        instructions = "".join(node.text or "" for node in footer.iter(qn("w:instrText")))
        self.assertIn("SECTIONPAGES", instructions)
        self.assertNotIn("NUMPAGES", instructions)
        results = [node.text or "" for node in footer.iter(qn("w:t"))]
        self.assertEqual(results, ["Trang ", "3", " / ", ""])
        begin = next(
            node
            for node in footer.iter(qn("w:fldChar"))
            if node.get(qn("w:fldCharType")) == "begin"
        )
        self.assertEqual(begin.get(qn("w:dirty")), "true")

    def test_footer_shared_with_front_matter_keeps_numpages(self) -> None:
        # The restarting body section reuses the first section's footer, so a
        # section count would be wrong on the front-matter pages.
        document = Document()
        paragraph = document.sections[0].footer.paragraphs[0]
        for value in ("Trang ", "3", " / ", "308"):
            paragraph.add_run(value)
        body = document.add_section()
        page_numbering = OxmlElement("w:pgNumType")
        page_numbering.set(qn("w:start"), "1")
        body._sectPr.append(page_numbering)
        self.assertTrue(body.footer.is_linked_to_previous)

        self.assertEqual(_replace_literal_footer_page_totals(document), 1)

        instructions = "".join(
            node.text or "" for node in document.sections[0].footer._element.iter(qn("w:instrText"))
        )
        self.assertIn("NUMPAGES", instructions)
        self.assertNotIn("SECTIONPAGES", instructions)

    def test_word_script_stores_calculated_page_totals(self) -> None:
        script = _word_update_script()
        self.assertIn("If fieldItem.Type = 26 Or fieldItem.Type = 66 Then", script)

    def test_word_script_lays_out_a_long_report_as_few_times_as_possible(self) -> None:
        # Each relayout of a 350-page report costs 20-25 s; the old script did
        # about eight and rebuilt the same TOC three times.
        script = _word_update_script()
        main = script[: script.index("Function BodyHasFieldsOutsideTocs")]
        toc_rebuild = main.index("toc.Update")
        body_check = main.index("If BodyHasFieldsOutsideTocs(document) Then")
        self.assertLess(toc_rebuild, body_check)
        # The whole main story is updated again only behind the body check.
        self.assertEqual(main.count("document.Fields.Update"), 1)
        self.assertLess(body_check, main.index("document.Fields.Update"))
        self.assertEqual(main.count("document.Repaginate"), 1)
        self.assertLess(body_check, main.index("document.Repaginate"))
        # Other stories (headers, footers, text boxes, notes) are still updated.
        self.assertIn("If currentStory.StoryType <> 1 Then currentStory.Fields.Update", main)
        self.assertLess(
            main.index("headerFooter.Range.Fields.Update"), main.index("toc.UpdatePageNumbers")
        )

    def test_word_script_body_check_falls_back_to_the_full_update(self) -> None:
        function = _word_update_script().split("Function BodyHasFieldsOutsideTocs(doc)", 1)[1]
        # True is the answer until every field was seen, so an error while
        # checking keeps the full update; TOC, PAGEREF and HYPERLINK inside a
        # TOC are the only fields the rebuilt TOCs cover.
        self.assertLess(
            function.index("BodyHasFieldsOutsideTocs = True"), function.index("For Each item")
        )
        # A table of figures is a TOC field too, but toc.Update skips it.
        self.assertLess(
            function.index("If doc.TablesOfFigures.Count > 0 Then Exit Function"),
            function.index("For Each item"),
        )
        self.assertIn("If item.Type <> 13 Then", function)
        self.assertIn("If item.Type = 37 Or item.Type = 88 Then", function)
        self.assertIn("item.Code.InRange(tocItem.Range)", function)
        self.assertLess(function.index("Next"), function.index("BodyHasFieldsOutsideTocs = False"))

    def test_enable_field_updates_marks_fields_dirty(self) -> None:
        document = Document()
        paragraph = document.add_paragraph()
        field_begin = OxmlElement("w:fldChar")
        field_begin.set(qn("w:fldCharType"), "begin")
        paragraph.add_run()._r.append(field_begin)

        _enable_field_updates(document)

        update_fields = document.settings.element.find(qn("w:updateFields"))
        self.assertIsNotNone(update_fields)
        self.assertEqual(update_fields.get(qn("w:val")), "true")
        self.assertEqual(field_begin.get(qn("w:dirty")), "true")

    def test_enable_field_updates_overrides_disabled_setting(self) -> None:
        document = Document()
        update_fields = OxmlElement("w:updateFields")
        update_fields.set(qn("w:val"), "false")
        document.settings.element.append(update_fields)

        _enable_field_updates(document)

        matches = document.settings.element.findall(qn("w:updateFields"))
        self.assertEqual(len(matches), 1)
        self.assertEqual(matches[0].get(qn("w:val")), "true")

    def test_non_windows_keeps_original_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "report.docx"
            document = Document()
            document.add_paragraph("Original")
            document.save(path)
            original = path.read_bytes()

            with patch("core.docx_field_updater.platform.system", return_value="Linux"):
                result = refresh_docx_fields(path)

            self.assertFalse(result.updated)
            self.assertEqual(result.engine, "deferred")
            self.assertEqual(path.read_bytes(), original)

    def test_failed_word_update_keeps_original_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "report.docx"
            document = Document()
            document.add_paragraph("Original")
            document.save(path)
            original = path.read_bytes()

            failed = subprocess.CompletedProcess(
                [], returncode=1, stdout="", stderr="Word unavailable"
            )
            with (
                patch("core.docx_field_updater.platform.system", return_value="Windows"),
                patch("core.docx_field_updater.shutil.which", return_value="powershell.exe"),
                patch("core.docx_field_updater._run_word_update", return_value=failed),
            ):
                result = refresh_docx_fields(path)

            self.assertFalse(result.updated)
            self.assertEqual(path.read_bytes(), original)
            self.assertFalse(any(path.parent.glob("*.field-refresh-*.docx")))

    def test_successful_word_update_replaces_file_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "report.docx"
            document = Document()
            paragraph = document.add_paragraph("Original")
            field_begin = OxmlElement("w:fldChar")
            field_begin.set(qn("w:fldCharType"), "begin")
            paragraph.add_run()._r.append(field_begin)
            _enable_field_updates(document)
            document.save(path)

            def update_copy(_powershell, working_copy, *, timeout_seconds, check_cancelled):
                updated = Document(working_copy)
                updated.add_paragraph("Updated by Word")
                updated.save(working_copy)
                return subprocess.CompletedProcess([], returncode=0, stdout="", stderr="")

            with (
                patch("core.docx_field_updater.platform.system", return_value="Windows"),
                patch("core.docx_field_updater.shutil.which", return_value="powershell.exe"),
                patch("core.docx_field_updater._run_word_update", side_effect=update_copy),
            ):
                result = refresh_docx_fields(path)

            self.assertTrue(result.updated)
            self.assertEqual(result.engine, "microsoft-word")
            self.assertTrue(zipfile.is_zipfile(path))
            self.assertIn("Updated by Word", "\n".join(p.text for p in Document(path).paragraphs))
            with zipfile.ZipFile(path) as archive:
                settings = archive.read("word/settings.xml").decode("utf-8")
                document_xml = archive.read("word/document.xml").decode("utf-8")
            self.assertIn('w:updateFields w:val="false"', settings)
            self.assertNotIn('w:updateFields w:val="true"', settings)
            self.assertNotIn('w:dirty="true"', document_xml)

    def test_failed_word_update_preserves_update_on_open_fallback(self) -> None:
        with tempfile.TemporaryDirectory() as tmp_dir:
            path = Path(tmp_dir) / "report.docx"
            document = Document()
            paragraph = document.add_paragraph("Original")
            field_begin = OxmlElement("w:fldChar")
            field_begin.set(qn("w:fldCharType"), "begin")
            paragraph.add_run()._r.append(field_begin)
            _enable_field_updates(document)
            document.save(path)

            failed = subprocess.CompletedProcess(
                [], returncode=1, stdout="", stderr="Word unavailable"
            )
            with (
                patch("core.docx_field_updater.platform.system", return_value="Windows"),
                patch("core.docx_field_updater.shutil.which", return_value="cscript.exe"),
                patch("core.docx_field_updater._run_word_update", return_value=failed),
            ):
                result = refresh_docx_fields(path)

            self.assertFalse(result.updated)
            with zipfile.ZipFile(path) as archive:
                settings = archive.read("word/settings.xml").decode("utf-8")
                document_xml = archive.read("word/document.xml").decode("utf-8")
            self.assertIn('w:updateFields w:val="true"', settings)
            self.assertIn('w:dirty="true"', document_xml)


if __name__ == "__main__":
    unittest.main()
