# C2Pro Architecture Documentation Index

> **Version:** 2.0.0  
> **Last Updated:** 2026-10-03  
> **Status:** Canonical navigation  
> **Baseline:** `main@314fc39b0b4c25c8c0ca99977314ba1bb9083208`

## Authority by question

Do not use one mixed precedence list for architecture, lifecycle and execution questions.

### Architecture / design

1. accepted ADRs under `docs/architecture/decisions/`;
2. [current technical architecture baseline](./architecture/C2PRO_TECHNICAL_BASELINE_2026-10-01.md);
3. focused current specifications/runbooks;
4. older TDDs/plans as supporting history.

### Product lifecycle / readiness

1. machine Product Control: `validation/product/c2pro-master-product-control-v1.yaml`;
2. guarded human projection: `docs/product/00-c2pro-master-product-control-v1.md`;
3. exact-head CI/deployment/qualification evidence referenced by the control plane.

### Development execution

1. `.c2pro/control/current.yaml`;
2. `.c2pro/control/work-queue.yaml`;
3. work envelopes under `.c2pro/work/`;
4. machine controls under `validation/development/`.

See [Documentation Authority](./DOCUMENTATION_AUTHORITY.md).

## Current architecture spine

| Area | Canonical source | Meaning |
|---|---|---|
| Project aggregate | ADR-014 | Project is the primary intelligence boundary |
| Temporal state | ADR-015 | events/revisions/snapshots |
| Change impact | ADR-016 | semantic diff/change projection |
| Graph orchestration | ADR-017 | governed ProjectGraph execution |
| Project Health | ADR-018 | evidence-backed health/coverage |
| Alerts/actions | ADR-019 | actionable conditions/lifecycle |
| HITL | ADR-020 + ADR-026 | review workflow + exact trusted-state commit |
| Single-document activation | ADR-024 | value from document #1 |
| Project Controls / WBS | ADR-025 | one project → one canonical hierarchical WBS |
| Processing recovery | ADR-027 | authority + checkpoint-lineage fencing |
| Production qualification | ADR-028 | composite runtime identity + non-authoritative evidence |

## Current implementation baseline

[Technical Architecture Baseline — 2026-10-01](./architecture/C2PRO_TECHNICAL_BASELINE_2026-10-01.md)

Key current facts:

- Next.js 16.3.6 / React 19.2.7 frontend on Vercel;
- Clerk organization-scoped authentication;
- FastAPI 0.141.1 backend;
- PostgreSQL/Supabase with RLS and pgvector;
- Redis + Celery worker/scheduler;
- LangGraph + PostgreSQL checkpoints;
- one canonical project WBS;
- trusted-state commit boundary;
- processing/checkpoint fencing;
- composite production runtime qualification.

## Product lifecycle authority

Do not use architecture documents to infer PROD validation.

- machine: `validation/product/c2pro-master-product-control-v1.yaml`
- human: `docs/product/00-c2pro-master-product-control-v1.md`

At the 2026-10-03 revalidation, #706 remains open and no documentation change here promotes P0b/P0c/P0d.

## Supporting / historical documents

| Document | Current role |
|---|---|
| `C2PRO_TECHNICAL_DESIGN_DOCUMENT_v4_1.md` | supporting March-era platform design |
| `C2PRO_TECHNICAL_DESIGN_DOCUMENT_v4_0.md` | supporting frontend design baseline |
| `FLOW_DIAGRAMS.md` | supporting flow reference |
| `LANGGRAPH_CHECKPOINTING.md` | focused checkpointing background; ADR-027 governs current authority fencing |
| `docs/planning/ROADMAP_v2.4.0.md` | historical strategic roadmap, not live lifecycle state |
| `C2PRO_MASTER_BACKLOG.md` | cold/historical backlog compatibility, not product truth |

## Operational architecture

- [CI/CD](./runbooks/ci-cd-setup.md)
- [Database migration authority](./runbooks/RUNBOOK_DATABASE_MIGRATION_AUTHORITY_2026-03-19.md)
- [Auth / Clerk guide](./runbooks/CLERK_AUTH_DEV_PROD_GUIDE.md)
- [HITL resume monitoring](./runbooks/HITL_RESUME_MONITORING.md)

## Audit trail

- [Documentation reconciliation — 2026-10-01](./audits/DOCUMENTATION_RECONCILIATION_2026-10-01.md)
- architecture/product audits remain under `docs/audits/` and are evidence/snapshots, not automatically canonical decisions.

## Changelog

| Version | Date | Change |
|---|---|---|
| 2.0.0 | 2026-10-01 | Rebased authority on Product Control + ADR spine; added current architecture baseline and ADR-026/027/028; downgraded older TDD/roadmap status to supporting/historical. |
| 1.1.0 | 2026-03-29 | Previous governance/index baseline. |
| 1.0.0 | 2026-03-22 | Initial consolidated architecture index. |
