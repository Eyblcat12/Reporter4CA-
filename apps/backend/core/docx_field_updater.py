"""Refresh calculated Word fields in a generated DOCX when an engine is available.

The report builder can create and preserve Word fields, but it cannot calculate
their displayed results.  In particular, a TOC needs Word's pagination engine
before browser previewers can display the new headings and page numbers.

This module deliberately has no third-party dependency.  On Windows it uses the
built-in Windows Script Host to automate an installed Microsoft Word.  The update is
performed on a copy and committed atomically, so an unavailable or failing Word
installation never damages the report that was already generated.
"""

from __future__ import annotations

import os
import platform
import re
import shutil
import subprocess
import tempfile
import threading
import uuid
import zipfile
from dataclasses import dataclass
from pathlib import Path


DEFAULT_FIELD_UPDATE_TIMEOUT_SECONDS = 180
_WORD_UPDATE_LOCK = threading.Lock()


@dataclass(frozen=True)
class FieldUpdateResult:
    """Outcome of an optional calculated-field refresh."""

    updated: bool
    engine: str
    detail: str = ""


def refresh_docx_fields(
    docx_path: str | Path,
    *,
    timeout_seconds: int = DEFAULT_FIELD_UPDATE_TIMEOUT_SECONDS,
) -> FieldUpdateResult:
    """Refresh TOC/page/reference fields without making report creation fragile.

    A successful refresh replaces ``docx_path`` atomically.  If Word is not
    available, or if it fails, the original DOCX remains untouched and callers
    can still return it; ``w:updateFields``/``w:dirty`` provide the normal Word
    fallback when the user later opens the document.
    """

    path = Path(docx_path).resolve()
    if not path.is_file():
        raise FileNotFoundError(f"DOCX file does not exist: {path}")

    if platform.system() != "Windows":
        return FieldUpdateResult(False, "deferred", "Microsoft Word automation is only available on Windows.")

    script_host = shutil.which("cscript.exe") or shutil.which("cscript")
    if not script_host:
        return FieldUpdateResult(False, "deferred", "Windows Script Host is not available.")

    working_copy = path.with_name(f".{path.stem}.field-refresh-{uuid.uuid4().hex}.docx")
    shutil.copy2(path, working_copy)

    try:
        # Prevent Word from eagerly updating every stale PAGEREF while opening
        # a template-derived document. The script rebuilds TOCs first.
        _set_update_fields_on_open(working_copy, enabled=False)
        with _WORD_UPDATE_LOCK:
            completed = _run_word_update(
                script_host,
                working_copy,
                timeout_seconds=timeout_seconds,
            )

        if completed.returncode != 0:
            detail = _process_error_detail(completed)
            return FieldUpdateResult(False, "deferred", detail or "Microsoft Word could not refresh fields.")

        # Word has already calculated and saved every field. Leaving
        # updateFields=true makes the next interactive Word session ask the
        # user to update the TOC again, even though the cached TOC is current.
        _set_update_fields_on_open(working_copy, enabled=False)
        _clear_dirty_field_flags(working_copy)
        if not zipfile.is_zipfile(working_copy):
            return FieldUpdateResult(False, "deferred", "Microsoft Word returned an invalid DOCX file.")

        os.replace(working_copy, path)
        return FieldUpdateResult(True, "microsoft-word")
    except subprocess.TimeoutExpired:
        return FieldUpdateResult(False, "deferred", "Microsoft Word field update timed out.")
    except Exception as exc:
        return FieldUpdateResult(False, "deferred", str(exc))
    finally:
        working_copy.unlink(missing_ok=True)


def _run_word_update(
    script_host: str,
    docx_path: Path,
    *,
    timeout_seconds: int,
) -> subprocess.CompletedProcess[str]:
    creation_flags = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    script_path: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding="ascii",
            suffix=".vbs",
            prefix="reporter-field-refresh-",
            dir=docx_path.parent,
            delete=False,
        ) as script_file:
            script_file.write(_word_update_script())
            script_path = Path(script_file.name)

        return subprocess.run(
            [script_host, "//B", "//Nologo", str(script_path), str(docx_path)],
            capture_output=True,
            text=True,
            timeout=timeout_seconds,
            creationflags=creation_flags,
            check=False,
        )
    finally:
        if script_path is not None:
            script_path.unlink(missing_ok=True)


def _word_update_script() -> str:
    # Native late-bound COM avoids pywin32 and .NET Office Interop conflicts.
    return r'''Option Explicit
Dim wordApp, document, toc, documentPath
Dim operationError, operationDescription

If WScript.Arguments.Count <> 1 Then
    WScript.Echo "A DOCX path is required."
    WScript.Quit 2
End If

documentPath = WScript.Arguments(0)
On Error Resume Next
Set wordApp = CreateObject("Word.Application")
If Err.Number <> 0 Then
    WScript.Echo "Microsoft Word is not available: " & Err.Description
    WScript.Quit 3
End If

wordApp.Visible = False
wordApp.DisplayAlerts = 0
wordApp.Options.SaveNormalPrompt = False
Err.Clear

Set document = wordApp.Documents.Open(documentPath, False, False, False)
If Err.Number <> 0 Then
    operationError = Err.Number
    operationDescription = Err.Description
Else
    document.Repaginate
    ' Rebuild TOCs first. Templates can contain hundreds of stale PAGEREF
    ' fields; updating those individually before replacing the TOC is wasteful.
    For Each toc In document.TablesOfContents
        toc.Update
    Next

    document.Repaginate
    document.Fields.Update
    For Each toc In document.TablesOfContents
        toc.UpdatePageNumbers
    Next

    Err.Clear
    document.Save
    operationError = Err.Number
    operationDescription = Err.Description
End If

Err.Clear
If Not document Is Nothing Then document.Close False
If Not wordApp Is Nothing Then wordApp.Quit
Set document = Nothing
Set wordApp = Nothing

If operationError <> 0 Then
    WScript.Echo "Microsoft Word field update failed: " & operationDescription
    WScript.Quit 4
End If

WScript.Quit 0
'''


def _set_update_fields_on_open(docx_path: Path, *, enabled: bool) -> None:
    """Toggle ``w:updateFields`` in settings.xml without reserializing DOCX."""

    replacement = f'<w:updateFields w:val="{str(enabled).lower()}"/>'
    temp_path = docx_path.with_name(f".{docx_path.name}.{uuid.uuid4().hex}.zip")
    found_settings = False

    try:
        with zipfile.ZipFile(docx_path, "r") as source, zipfile.ZipFile(temp_path, "w") as target:
            for info in source.infolist():
                payload = source.read(info.filename)
                if info.filename == "word/settings.xml":
                    found_settings = True
                    xml = payload.decode("utf-8")
                    pattern = r"<w:updateFields\b[^>]*(?:/>|>.*?</w:updateFields>)"
                    if re.search(pattern, xml, flags=re.DOTALL):
                        xml = re.sub(pattern, replacement, xml, count=1, flags=re.DOTALL)
                    else:
                        xml = xml.replace("</w:settings>", f"{replacement}</w:settings>")
                    payload = xml.encode("utf-8")
                target.writestr(info, payload)

        if not found_settings:
            raise ValueError("DOCX does not contain word/settings.xml")
        os.replace(temp_path, docx_path)
    finally:
        temp_path.unlink(missing_ok=True)


def _clear_dirty_field_flags(docx_path: Path) -> None:
    """Remove stale-field flags after Word has saved refreshed field results."""

    temp_path = docx_path.with_name(f".{docx_path.name}.{uuid.uuid4().hex}.zip")
    field_tag_pattern = re.compile(rb"<w:fldChar\b[^>]*>")
    dirty_attribute_pattern = re.compile(rb'\s+w:dirty="(?:true|1)"')

    def clean_field_tag(match: re.Match[bytes]) -> bytes:
        return dirty_attribute_pattern.sub(b"", match.group(0))

    try:
        with zipfile.ZipFile(docx_path, "r") as source, zipfile.ZipFile(temp_path, "w") as target:
            for info in source.infolist():
                payload = source.read(info.filename)
                if info.filename.startswith("word/") and info.filename.endswith(".xml"):
                    payload = field_tag_pattern.sub(clean_field_tag, payload)
                target.writestr(info, payload)
        os.replace(temp_path, docx_path)
    finally:
        temp_path.unlink(missing_ok=True)


def _process_error_detail(completed: subprocess.CompletedProcess[str]) -> str:
    output = (completed.stderr or completed.stdout or "").strip()
    if not output:
        return ""
    # The script host may include several diagnostic lines; one compact line is
    # enough for backend logs/headers and avoids exposing a full stack trace.
    return " ".join(output.split())[:500]
