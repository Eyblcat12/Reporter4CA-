# Hardening for large local/team workloads

## Decision boundary

Reporter Pro must remain capable of producing reports for environments approaching
50,000 assets. Resource protection therefore cannot be implemented as a small fixed
row limit. The project will measure real workload cost first and use configurable,
machine-aware protection where possible.

Plugin sandboxing is explicitly deferred. Plugins remain an open extension feature for
trusted local/team code; a future server-mode design must reassess that trust model.

## Existing safeguards

- Import files default to 50 MB and can be configured from 1–512 MB.
- Report rows default to 50,000 and can be configured from 100–500,000.
- One report job runs at a time and two additional jobs may wait.
- DOCX templates are limited to 20 MB.
- Jobs support cooperative cancellation and temporary-file cleanup.
- A 122-minute soak test passed without timeouts, unexpected failures or deduplication errors.

These values are safety defaults, not evidence that every 50,000-row report type meets
the desired latency and memory targets.

## Research plan before changing limits

### Workload matrix

Benchmark 1,000, 10,000, 25,000 and 50,000 assets for `full`, `summary`, `technical`
and asset-specific report types. Include clean data, finding-heavy data, long notes,
IoC/MITRE metadata and templates containing images.

Capture for every run:

- Import/validation/generation/finalization duration.
- Process baseline, peak and final RSS.
- Python heap peak and growth.
- Temporary and final DOCX size.
- Table, paragraph, relationship and media counts.
- Cancellation latency and temporary-file cleanup result.

### Protection model

Prefer three layers instead of one hard limit:

1. **Structural validation:** reject malformed or impossible inputs regardless of size.
2. **Soft workload warning:** estimate cost from rows, report type, notes and media; let the
   user continue on a suitable workstation.
3. **Configurable emergency ceiling:** retain an environment override for genuinely unsafe
   requests, with the effective value visible in the UI and logs.

### Likely optimizations

- Avoid retaining duplicate normalized row collections across import and generation.
- Process validation and rule evaluation in chunks where semantic results remain identical.
- Add cancellation checkpoints inside large table-generation loops, not only between phases.
- Store lightweight job telemetry rather than full request copies after completion.
- Consider splitting very large inventories into appendices or multiple documents only as an
  explicit output option, never silently.

## Acceptance criteria

- A 50,000-asset benchmark completes on the agreed reference workstation or produces an
  actionable preflight warning before starting.
- Peak memory and output-size measurements are recorded for every benchmark profile.
- Cancellation is acknowledged within a measured, documented interval.
- No partial output or temporary DOCX remains after cancellation or failure.
- Default limits are changed only from benchmark evidence, never from an arbitrary estimate.
