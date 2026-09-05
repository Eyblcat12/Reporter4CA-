# Synthetic Template Studio pilot fixtures

These DOCX files are generated test assets. They contain no customer content and
must never replace Reporter Pro's approved default templates.

The three fixtures intentionally use different document structures and mixtures
of token, bookmark, and content-control anchors:

- `cross_platform_assessment_full.docx`
- `infrastructure_review_server.docx`
- `endpoint_assurance_client.docx`

Regenerate them with the bundled workspace Python runtime:

```powershell
python tests/fixtures/template_studio/synthetic_templates/generate_fixtures.py
```

`manifest.json` records the exact checksums and approved semantic anchors used by
the automated pilot. Any fixture edit must regenerate that manifest and pass the
structural, render, and visual checks before merge.
