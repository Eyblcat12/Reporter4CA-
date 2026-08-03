# Template categories

Reporter Pro supports one template collection and one default template for each report type:

- `full/` — complete server and client report
- `server_only/` — server-only report
- `client_only/` — client-only report
- `summary/` — executive summary report
- `technical/` — technical detail report
- `incident_response/` — incident response report

Templates uploaded from the UI are stored in the matching folder automatically.
DOCX files copied into one of these folders are discovered by the backend and
registered under that report type. Existing DOCX files in the root `templates/`
folder remain in the `full` category for backward compatibility.

Bundled category templates:

- `server_only/report_server_only_default.docx` keeps the reference cover,
  styles, headers and footers, with server inventory/summary/detail prototypes.
- `client_only/report_client_only_default.docx` keeps the same presentation,
  with client inventory/summary/detail prototypes.
