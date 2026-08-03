# Golden DOCX structural regression reports

Golden DOCX tests compare the semantic structure of all six report types instead of
comparing ZIP bytes. The snapshot covers headings, paragraphs, tables, numbering,
remaining tokens, sections, relationships and embedded media.

## Run the test

```powershell
apps/backend/.venv/Scripts/python.exe -m unittest tests.test_docx_golden -v
```

When a regression is detected, two local artifacts are generated:

- `artifacts/golden-docx/golden-docx-diff.json`: structured data for CI and automation.
- `artifacts/golden-docx/golden-docx-diff.html`: visual table grouped by report type and category.

CI can retain this directory as an artifact when the backend regression job fails.
The HTML report shows whether each value was added, removed or changed, together with
its precise snapshot path and the Golden/Actual values.

## Update a reviewed baseline

Golden files must not be updated as an automatic recovery action. After reviewing the
HTML diff and confirming that every change is intentional, run:

```powershell
$env:UPDATE_GOLDEN_DOCX = "1"
apps/backend/.venv/Scripts/python.exe -m unittest tests.test_docx_golden -v
Remove-Item Env:UPDATE_GOLDEN_DOCX
```

Review the resulting changes under `tests/golden/docx-v1/` before committing them.
