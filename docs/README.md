# Documentation Index

This repository now separates documentation by lifecycle and function.

## Current Canonical Areas

- `architecture/`
  - ADRs, diagrams, architecture notes, and the current technical design document.
- `api/`
  - OpenAPI artifacts and API examples.
- `specifications/`
  - Product and technical specifications.
- `runbooks/`
  - Operational and environment procedures.
- `planning/`
  - Active roadmap and planning material that still guides execution.
- `testing/`
  - Test inventories, registries, reports, and active testing roadmaps.
- `audits/`
  - Audit reports that remain useful as reference.
- `coherence_engine/`
  - Domain-specific scoring and engine reference material.
- `performance/`
  - Performance baselines and optimization notes.
- `assets/`
  - Schedules, exported artifacts, and sample contract documents.
- `internal/`
  - Internal lessons learned and non-product-facing reference notes.

## Historical Material

- `archive/`
  - Superseded reports, dated status documents, duplicate copies, archived planning bundles, implementation summaries, and reference-code artifacts that should not be treated as active source.

## Documentation Rules

- Keep only human-facing documentation in `docs/`.
- Keep executable code, tests, SQL, and config in app, infrastructure, or ops folders.
- Archive dated status snapshots instead of leaving them at the top level.
- Prefer one canonical copy of a document. Duplicate variants go to `archive/duplicates/`.
- Use `sandbox/` for standalone experiments or prototype apps that are not part of the canonical documentation tree.
