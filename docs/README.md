# C2Pro Documentation Index

**Status:** Canonical navigation  
**Last reconciled:** 2026-10-03

Before using any document as a source of truth, read [Documentation Authority and Lifecycle](./DOCUMENTATION_AUTHORITY.md).

## Canonical entry points

### Product programme

- Machine authority: `validation/product/c2pro-master-product-control-v1.yaml`
- Human projection: [Master Product Programme Control](./product/00-c2pro-master-product-control-v1.md)
- Qualification evidence contract: [Product Qualification Evidence v1](./product/qualification-evidence-contract-v1.md)

### Architecture

- [Architecture index](./ARCHITECTURE_INDEX.md)
- [Current technical architecture baseline](./architecture/C2PRO_TECHNICAL_BASELINE_2026-10-01.md)
- [Architecture decisions / ADR catalogue](./architecture/decisions/README.md)

### Development control

- Machine hot state: `.c2pro/control/current.yaml`
- Machine open queue: `.c2pro/control/work-queue.yaml`
- Development control docs: `docs/architecture/development/`

### Operations

- [Runbooks index](./runbooks/README.md)
- [CI/CD runbook](./runbooks/ci-cd-setup.md)

## Documentation areas

- `architecture/` — current baseline, ADRs, diagrams and architecture notes.
- `product/` — programme-control human projection and product evidence contracts.
- `api/` — generated/reference OpenAPI artifacts and API examples.
- `specifications/` — functional/technical specifications.
- `runbooks/` — operational procedures and environment guidance.
- `testing/` — test strategy, inventories and registries.
- `audits/` — dated audits and reconciliation evidence.
- `coherence_engine/` — domain-specific Coherence design/reference.
- `performance/` — performance baselines and optimization notes.
- `assets/` — schedules and supporting artifacts.
- `internal/` — internal operational reference material.
- `planning/` — plans/roadmaps that must carry a date/status; not a live product-state authority.
- `archive/` — superseded, duplicate or historical material.

## Lifecycle rules

- Product status lives in Product Control, not in a README or old roadmap.
- Accepted architecture decisions live in `architecture/decisions/`.
- Historical TDDs/plans may remain for traceability but are subordinate to accepted ADRs and the current baseline.
- A merged PR proves repository realization, not deployment or production validation.
- A successful deployment proves runtime presence, not user-value acceptance.
- A qualification evidence bundle is necessary for promotion but cannot promote itself.

## Current reconciliation

The repository-wide documentation reconciliation originated on 2026-10-01 and was revalidated against current `main` on 2026-10-03. Its audit trail is recorded at:

[DOCUMENTATION_RECONCILIATION_2026-10-01.md](./audits/DOCUMENTATION_RECONCILIATION_2026-10-01.md)

It intentionally preserves historical evidence while removing ambiguity about which artifacts are current authority.
