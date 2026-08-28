# Template Packs (experimental architecture)

> Trạng thái triển khai, commit hiện tại, backlog và checklist bàn giao được cập
> nhật tại [TEMPLATE_STUDIO_STATUS.md](TEMPLATE_STUDIO_STATUS.md). Đọc tài liệu đó
> trước khi tiếp tục sửa subsystem này.

Template Packs are the planned extension point for supporting customer Word
templates whose structure differs from the templates shipped with Reporter Pro.
They are developed **beside** the current renderer, not as a replacement for it.

## Compatibility guarantee

The production path remains:

```text
Tracking data -> Legacy Renderer -> current full/server/client/... template -> DOCX
```

The experimental path is separate:

```text
New DOCX
  -> analyze
  -> manually map and normalize
  -> 100% semantic coverage gate
  -> fixture + integrity + visual tests
  -> publish Template Pack
  -> Profile Renderer (future, opt-in only)
```

Current safeguards:

- `AUTO_REPORT_TEMPLATE_PACKS` defaults to `0` (disabled).
- The legacy `ReportBuilder` and its template selection are unchanged.
- Pack inspection is read-only and never extracts, installs or executes content.
- A draft or partially mapped pack cannot become selectable.
- No silent fallback from a failed Profile Renderer build to a different layout.
- Enabling the subsystem in the future will still require selecting a published
  pack explicitly. Existing report types continue to use the Legacy Renderer.

## Pack format 1.0

A `.zip` Template Pack contains exactly these data files:

| File | Purpose |
|---|---|
| `manifest.json` | Pack identity, format version and SHA-256 checksums |
| `template.docx` | The approved Word template |
| `layout.json` | Semantic slots, renderers and stable Word anchors |
| `mapping.json` | Canonical tracking/analysis sources and table-field mappings |
| `validation.json` | Fixture, integrity and visual approval evidence |

The normative Draft 2020-12 schemas are stored in
`apps/backend/config/template_packs/`. Pack inspection also enforces the same
closed-field policy at runtime, so unsupported manifest, layout, mapping or
validation properties are rejected rather than ignored.

Executable files, plugins, extra archive members, encrypted members, symbolic
links and path traversal are rejected. Size, entry-count, expanded-size and
compression-ratio limits are checked without extracting the archive.

## Stable anchors

The preferred anchor order is:

1. Word content control with a stable tag;
2. Word bookmark with a stable name;
3. explicit `{{UPPER_SNAKE_CASE}}` token as a compatibility fallback.

Heading text and table order are not stable identifiers. A customer may rename a
heading or move a table during document editing, so neither should be the primary
mapping key.

## Meaning of 100% mapping

Coverage is calculated from the canonical semantic catalog for the selected
report type. A required semantic is counted only when all of these are valid:

- the semantic block exists;
- its stable Word anchor is valid and unique;
- its renderer matches the canonical block type;
- its normalized data source is correct;
- every required table field has an explicit source-to-target mapping.

Static customer text does not need a data mapping, but the normalization process
must explicitly leave it static. The percentage is computed by the validator; a
user cannot type `100%` manually.

## Publication states

```text
draft -> analyzed -> mapping_incomplete -> mapping_complete
      -> test_failed | test_passed -> published
```

`published` alone is insufficient. Activation also requires exactly 100% mapping,
a matching template checksum, and passing fixture, structural-integrity and
visual-review evidence.

## Delivery phases

1. Schema, semantic catalog, safe archive inspector and regression barriers.
2. Feature-gated inspect API with no storage or rendering side effects.
3. Separate Template Studio for analyze, map, validate, test and publish.
4. Profile Renderer implemented alongside the Legacy Renderer.
5. Per-pack fixtures, golden DOCX comparison, performance benchmark and rollback.
6. Opt-in release only after legacy regression and pack-specific gates pass.

The first phase intentionally makes no database migration and exposes no new
selection in the production UI. This keeps Reporter Pro usable throughout the
development cycle.

## Experimental API boundary

Both endpoints return `404` unless `AUTO_REPORT_TEMPLATE_PACKS=1` is set before
starting the backend:

- `POST /api/template-packs/analyze-template` reads a DOCX and reports content
  controls, bookmarks, tokens, duplicate-anchor conflicts, headings, tables,
  headers/footers, sections, page breaks, numbering and relationships. It returns
  an unapproved semantic checklist whose coverage always starts at `0%`; name
  matches are suggestions that still require review.
- `POST /api/template-packs/inspect` validates a completed archive and can enforce
  the publication gate. It never stores, extracts, installs or renders the pack.
- `POST /api/template-packs/workspaces` pins the uploaded DOCX by SHA-256 and
  creates a revisioned mapping draft.
- `GET /api/template-packs/workspaces` lists metadata-only drafts with
  filter/search/cursor pagination and corrupt-file isolation.
- `GET /api/template-packs/workspaces/{id}` reads a draft without exposing its
  filesystem path.
- `PUT /api/template-packs/workspaces/{id}/mappings/{semantic}` approves one
  discovered, unique anchor and its required field mappings.
- `POST /api/template-packs/workspaces/{id}/mappings/{semantic}/remove` returns a
  semantic to the unmapped state.
- Rename, clone and archive/restore endpoints provide non-destructive lifecycle
  operations with the same optimistic revision guard and audit trail.
- Export/import uses a data-only `.rptdraft` archive with manifest/checksums and
  always assigns a new workspace identity on import.
- Retention is preview-first and moves eligible archived drafts into recoverable
  quarantine. There is no permanent-delete endpoint.

Every mapping command includes `expectedRevision`. A stale editor receives HTTP
`409` instead of overwriting newer work. DOCX sources are content-addressed and
immutable; workspace JSON is written atomically and protected by a checksum.
Reaching 100% mapping changes the draft to `mapping_complete`, but does not make
it publishable until fixture, integrity and visual evidence are produced.

## Pack Builder and isolated version catalog

The backend now contains a deterministic Pack Builder and a revisioned catalog.
The Builder accepts only a `mapping_complete` workspace whose pinned DOCX
checksum still matches, plus trusted fixture, integrity and visual evidence. It
creates the five-file archive, calculates every checksum and immediately runs
the normal pack inspector against its own output.

The catalog provides immutable semantic versions. Installing different bytes
over an existing `packId` + `version` is rejected; callers must publish a new
version. Activation and rollback use optimistic concurrency, keep an audit log,
and verify the stored archive checksum before selection.

Catalog selection is deliberately **not** connected to report generation. API
responses include `selectionIntegrated: false` and `legacyRendererUnchanged:
true`. This lets Template Studio exercise lifecycle and rollback behavior while
the existing full/server/client workflow continues to use only its current
templates and Legacy Renderer.

Additional feature-gated endpoints:

- `GET /api/template-packs/catalog` lists installed versions and the isolated
  Template Studio selection.
- `POST /api/template-packs/catalog/install` installs one publication-ready
  `.rptpack` with an `expectedRevision` guard.
- `POST /api/template-packs/catalog/{packId}/activate` selects an installed
  version in Template Studio.
- `POST /api/template-packs/catalog/{packId}/rollback` records an explicit
  rollback to an installed version.

The Pack Builder itself is not exposed as a public HTTP operation yet. Fixture
and integrity evidence must come from the future Profile Renderer validation
runner rather than booleans supplied by a browser. This prevents a UI client
from self-certifying an untested customer template.

These endpoints do not appear in, or change, the current Configure/Preview/
Generate workflow. Template Studio will call them from a separate experimental
screen in a later phase.

An isolated UI proposal is available at
[`template-studio-prototype.html`](template-studio-prototype.html). It contains
no external assets, forms or API calls and is not bundled into the application.

The recommended enterprise-oriented revision is
[`template-studio-enterprise.html`](template-studio-enterprise.html). It adds a
denser mapping table, version/checksum context, validation evidence, audit and
approval states, explicit Legacy Renderer protection, and consistent dark/light
themes. This file is also a standalone prototype and is not included in the
production frontend build.
