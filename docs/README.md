# C2Pro Documentation Index

This directory is organized by **authority and lifecycle**, not simply by file age.

## Start here

1. [Architecture index](./ARCHITECTURE_INDEX.md)
2. [Platform TDD v4.2](./architecture/C2PRO_TECHNICAL_DESIGN_DOCUMENT_v4_2.md)
3. [Architecture decisions](./architecture/decisions/README.md)
4. [Master Product Control](./product/00-c2pro-master-product-control-v1.md)
5. [Qualification evidence contract](./product/qualification-evidence-contract-v1.md)
6. [Production qualification operator runbook](./product/production-qualification-operator-runbook.md)
7. [Runbooks](./runbooks/README.md)
8. [Testing](./testing/README.md)

## Authority model

| Class | Location | Authority |
|---|---|---|
| Product Control machine state | `validation/product/` | Product programme/lifecycle authority |
| Development control machine state | `.c2pro/control/` + `.c2pro/work/` | Development execution/write authority |
| Architecture decisions | `architecture/decisions/` | Durable architecture authority |
| Platform TDD | `architecture/C2PRO_TECHNICAL_DESIGN_DOCUMENT_v4_2.md` | Current platform-wide design |
| Product/spec contracts | `product/`, `specifications/` | Durable functional/qualification contracts |
| Runbooks | `runbooks/` | Operator procedure |
| Testing | `testing/` | Test strategy/registry |
| Planning | `planning/` | Intent/plan; not proof of landed behavior |
| Audits/evidence | `audits/`, `evidence/` | Point-in-time evidence |
| Archive | `archive/` | Superseded/non-current material |

## Current canonical areas

- `architecture/` — TDDs, ADRs, diagrams and architecture notes.
- `product/` — Product Control projection and production/qualification contracts.
- `api/` — OpenAPI artifacts and API references.
- `specifications/` — durable product and technical specifications.
- `runbooks/` — operational/environment procedures.
- `testing/` — test inventories, registries and strategy.
- `planning/` — roadmap/plans that still guide authorized future work.
- `audits/` — dated audit evidence; do not treat old findings as current without re-verification.
- `performance/` — baselines and performance notes.
- `internal/` — internal policy/reference.

## Historical material

Historical documents should normally stay unchanged. Their date and context are part of the evidence.

Examples:

- superseded TDDs;
- completed implementation plans;
- dated production-readiness reports;
- old release evidence;
- archived session/audit material.

When current architecture changes, create/update the current canonical document rather than rewriting old evidence.

## Documentation rules

- Prefer one canonical owner per concern; do not pretend one file owns product, development, architecture and runtime truth simultaneously.
- Treat `C2PRO_MASTER_BACKLOG.md`, `backlogs/*.md` and `blackboard.json` as legacy/cold references under the single-writer control policy.
- Do not create task-specific report sprawl.
- Do not hand-edit generated Product Control canonical blocks.
- Do not use planning docs as proof that a feature is landed.
- Do not use a merged implementation PR as proof of production validation.
- Verify workflow names and required checks against the live repository/ruleset.
- If sources conflict, follow the authority hierarchy in `.claude/rules/DOCUMENTATION_STRUCTURE.md`.
