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
  -> Profile Renderer (implemented domain-only; not selected by Generate)
```

Current safeguards:

- `AUTO_REPORT_TEMPLATE_PACKS` defaults to `1`, so the authoring Studio is part
  of the local/team tool. Setting it to `0` is an emergency API isolation switch.
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

The nested `template.docx` package receives a second independent safety pass:
bounded entry count/expanded size/compression ratio, duplicate and unsafe path
checks, encryption/symlink rejection, and denial of `DOCTYPE`/`ENTITY`
declarations in OOXML parts. Pack JSON is also bounded by nesting depth and node
count so malformed inputs return a controlled validation error.

## Stable anchors

The preferred anchor order is:

1. Word content control with a stable tag;
2. Word bookmark with a stable name;
3. explicit `{{UPPER_SNAKE_CASE}}` token as a compatibility fallback.

Heading text and table order are not stable identifiers. A customer may rename a
heading or move a table during document editing, so neither should be the primary
mapping key.

The analyzer recommendation is a ranking aid, not an allowlist. Template Studio
offers every discovered content control, bookmark and token that occurs exactly
once, so a customer-specific name can be mapped manually after review. Ambiguous
anchors are excluded, and the same anchor cannot be assigned to two semantic
blocks; both the UI and backend enforce this ownership rule.

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
4. Profile Renderer implemented alongside the Legacy Renderer. **Domain complete;
   API/job/UI/Generate integration remains disabled.**
5. Per-pack fixtures, golden DOCX comparison, performance benchmark and rollback.
6. Opt-in release only after legacy regression and pack-specific gates pass.

The first phase intentionally makes no database migration and exposes no new
selection in the production UI. This keeps Reporter Pro usable throughout the
development cycle.

## Experimental API boundary

These endpoints return `404` only when the emergency switch
`AUTO_REPORT_TEMPLATE_PACKS=0` is set before starting the backend:

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
  discovered, unique, currently unassigned anchor and its required field mappings.
- `POST /api/template-packs/workspaces/{id}/mappings/{semantic}/remove` returns a
  semantic to the unmapped state.
- Rename, clone and archive/restore endpoints provide non-destructive lifecycle
  operations with the same optimistic revision guard and audit trail.
- Export/import uses a data-only `.rptdraft` archive with manifest/checksums and
  always assigns a new workspace identity on import.
- Retention is preview-first and moves eligible archived drafts into recoverable
  quarantine. There is no permanent-delete endpoint.
- Publication uses a backend-owned two-pass workflow: create a baseline run,
  review and approve its exact DOCX SHA-256, run again against that approved
  baseline, then publish the exact successful second-pass artifact.

Every mapping command includes `expectedRevision`. A stale editor receives HTTP
`409` instead of overwriting newer work. DOCX sources are content-addressed and
immutable; workspace JSON is written atomically and protected by a checksum.
Reaching 100% mapping changes the draft to `mapping_complete`, but does not make
it publishable until fixture, integrity and visual evidence are produced.

The experimental React route mirrors this boundary. `Template mới` first reads
only a non-empty `.docx` no larger than 20 MiB, calls the read-only analyzer and
shows structural facts with `0%` approved mapping. Workspace creation remains a
separate explicit action; changing the source or report type invalidates the
analysis result. A created draft is opened only inside Template Studio and is
not added to the default template selector or Generate workflow.
The mapping inspector then lists all unique anchors, ranks analyzer suggestions
first, marks anchors already owned by another semantic and requires an explicit
`Duyệt ánh xạ` action. Draft edits are local until approval so exploratory choices
cannot silently change workspace revision or audit history.

The production sidebar exposes **Template Studio** and its isolated route
`/?view=template-studio`. The repository-level `.env` enables the authoring APIs
with `AUTO_REPORT_TEMPLATE_PACKS=1` by default. This availability does not place
any Template Pack in the production selector or connect it to Preview/Generate.

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
- `GET /api/template-packs/catalog/recovery` verifies primary/checkpoint metadata
  and every referenced pack payload, then returns a one-time state-bound token
  only when recovery is safe.
- `POST /api/template-packs/catalog/recovery` restores that exact checkpoint;
  stale tokens and incomplete/corrupt payload sets are rejected.
- `POST /api/template-packs/workspaces/{id}/validation-runs` creates a baseline
  candidate or a second-pass run against an approved baseline.
- `GET /api/template-packs/workspaces/{id}/validation-runs` lists sealed run
  metadata for session recovery, marks records stale after workspace changes and
  reports corrupt records without exposing storage paths.
- `GET /api/template-packs/workspaces/{id}/validation-runs/{runId}/artifact`
  downloads the checksum-bound DOCX for review.
- `POST .../{runId}/approve-baseline` records reviewer approval for the exact
  first-pass artifact checksum.
- `POST .../{runId}/publish` rechecks workspace and catalog revisions and then
  installs only the exact successful second-pass result.

The Pack Builder is reachable only through this trusted publication workflow.
It never accepts fixture/integrity/visual booleans from a browser. Server-owned
records bind workspace revision/hash, template hash, fixture signatures,
structural baseline, artifact SHA-256 and reviewer identity before a
publication-ready pack can be created.

Catalog index writes are sealed with a SHA-256 over canonical metadata. Before a
new revision becomes the primary index, the previous valid revision is retained
as a bounded checkpoint. Recovery is preview-first and explicit; it never treats
a syntactically valid index as recoverable unless every referenced `.rptpack`
exists and matches its catalog checksum.

Catalog reads and mutations also hold an OS byte-range lock with a bounded wait.
This extends revision safety across separate Reporter Pro backend processes on
Windows and POSIX systems; a busy catalog returns a controlled retryable error
instead of allowing concurrent index replacement.

## Isolated Profile Renderer v1

The backend contains a declarative Profile Renderer that can render a
publication-ready pack from one accepted normalized snapshot. It supports the
semantic renderer catalog for all six report types, validates report type and
the pinned template checksum, reports the exact failing semantic/anchor, emits a
traceability manifest, and supports progress, cooperative cancellation and
atomic temporary-file cleanup.

This is currently a domain/test capability only. No API, background job, UI,
catalog selection or production Generate path calls it. It never imports or
falls back to the Legacy Renderer. TS-12 now validates its output, but completing
a domain render alone does not make a customer pack selectable.

## Backend-owned validation runner

TS-12 adds a two-pass validation runner without exposing a browser-controlled
`passed=true` contract:

1. A 100%-mapped workspace creates a deterministic `mapping_complete` candidate
   pack. The candidate is deliberately non-publishable and cannot be installed.
2. The Profile Renderer renders the accepted fixture snapshot and the runner
   checks semantic/row counts, asset/finding/evidence values, unresolved tokens,
   renderer provenance and the structural DOCX snapshot.
3. The first run establishes a structural baseline artifact. A later run must
   match that reviewed baseline with no heading/table/numbering/relationship/
   media/section differences.
4. A human reviewer approves the exact DOCX checksum. The resulting evidence is
   bound to the validation run, artifact hash, structural hash, reviewer and
   timestamp before the final publishable pack can be built.

Generated tables carry invisible semantic captions so a structural difference
can identify the mapped block that changed. TS-14 exposes validation and publish
through the feature-gated Template Studio API and stores artifacts in an
isolated checksum-protected store. Production Generate selection still does not
call this workflow.

## Isolated pack Preview/diff

TS-13 adds a bounded process-local preview cache whose identity includes pack ID,
semantic version, complete pack SHA-256, template SHA-256, accepted request
signature, prepared content signature and renderer version. A cache entry cannot
be reused when either the pack bytes or normalized input changes—even if the pack
version string is unchanged.

Each preview exposes the original-template and rendered-document structural
snapshots plus a bounded readable diff. Generate promotion returns the exact
preview bytes only when every identity component and the artifact checksum still
match. This proves Preview/Generate content parity without a second render.

The service is still domain-only. It has no route, job, browser cache, dropdown
selection or connection to the production Generate workflow.

These endpoints do not appear in, or change, the current Configure/Preview/
Generate workflow. Template Studio will call them from a separate experimental
screen in a later phase.

## Reproducible synthetic pilot templates

The repository includes three customer-data-free DOCX fixtures under
`tests/fixtures/template_studio/synthetic_templates/`. They cover `full`,
`server_only`, and `client_only`, use distinct mixtures of token, bookmark, and
content-control anchors, and are reproducible from a committed generator and
checksum manifest.

The regression suite drives every fixture through read-only analysis, explicit
100% mapping, two-pass structural validation, publishable pack construction,
isolated Preview, and byte-for-byte Generate promotion. These fixtures authorize
the authoring subsystem to be available in the tool; they do not authorize a
Template Pack in the production Generate selector. A customer template must
repeat its own visual, compatibility, recovery, and performance pilot before
that separate opt-in integration decision.

An isolated UI proposal is available at
[`template-studio-prototype.html`](template-studio-prototype.html). It contains
no external assets, forms or API calls and is not bundled into the application.

The recommended enterprise-oriented revision is
[`template-studio-enterprise.html`](template-studio-enterprise.html). It adds a
denser mapping table, version/checksum context, validation evidence, audit and
approval states, explicit Legacy Renderer protection, and consistent dark/light
themes. This file is also a standalone prototype and is not included in the
production frontend build.
