# C2Pro Documentation Structure — MUST FOLLOW

**Authority:** `docs/DOCUMENTATION_AUTHORITY.md`  
**Reconciled:** 2026-10-01

## Core rule

Do not create a second source of truth.

C2Pro intentionally uses different authorities for different concerns:

- **Product programme state:** `validation/product/c2pro-master-product-control-v1.yaml` + guarded human projection.
- **Development execution:** `.c2pro/control/` + work envelopes.
- **Architecture decisions:** `docs/architecture/decisions/`.
- **Current architecture synthesis:** `docs/architecture/C2PRO_TECHNICAL_BASELINE_2026-10-01.md`.
- **Operations:** focused runbooks under `docs/runbooks/`.
- **Historical evidence:** audit/archive material.

## Where new documentation belongs

Create a standalone document only when it has a durable purpose:

- ADR → `docs/architecture/decisions/`
- current architecture baseline/note → `docs/architecture/`
- product control/evidence contract → `docs/product/`
- operational procedure → `docs/runbooks/`
- dated audit/reconciliation evidence → `docs/audits/`
- temporary session notes → working/control-plane location; archive when no longer active

Do **not** create completion-summary Markdown for every task. PR/issue/CI history is normally sufficient implementation evidence.

## Backlogs and blackboard

`C2PRO_MASTER_BACKLOG.md`, `backlogs/*.md` and legacy blackboard material are historical/compatibility sources. They are **not** the current product or execution authority.

Do not route new canonical status into them merely because older instructions did so.

## Architecture changes

A material architecture change must either:

1. conform to an existing accepted ADR; or
2. amend/supersede/create an ADR.

Never silently rewrite architecture through code plus an implementation summary.

## Status claims

Words such as `complete`, `production ready`, `deployed`, `validated` and `operational` must use the owning control-plane vocabulary and evidence.

Merge/CI/deploy != PROD_VALIDATED.

## Historical preservation

Prefer reclassification/archival over deletion. Preserve rationale and auditability, but make lifecycle/authority explicit so historical text cannot masquerade as current truth.
