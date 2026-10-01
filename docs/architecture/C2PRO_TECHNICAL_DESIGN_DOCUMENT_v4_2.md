# C2Pro v4.2 — Platform Technical Design Document

> **Document Type:** Canonical Platform Technical Design  
> **Version:** 4.2  
> **Date:** 2026-10-01  
> **Status:** Current  
> **Supersedes:** `C2PRO_TECHNICAL_DESIGN_DOCUMENT_v4_1.md`  
> **Architecture authority:** this TDD + Accepted ADRs  
> **Documentation governance:** `docs/DOCUMENTATION_GOVERNANCE.md`

## 1. Purpose

C2Pro is a multi-tenant contract/project intelligence platform connecting contractual evidence, documents, project controls and human review. AI produces traceable analysis/proposals; material trust transitions remain evidence-backed and human-governed.

This document describes the **landed platform architecture** on the 2026-10-01 baseline after #711 and #758/#759. Product lifecycle, deployment and production qualification are delegated to Product Control rather than duplicated here.

## 2. Sources of authority

- Product lifecycle: `validation/product/c2pro-master-product-control-v1.yaml`.
- Development execution: `.c2pro/control/` and assigned `.c2pro/work/`.
- Architecture: this TDD + Accepted ADRs.
- Implementation: exact `main` commit, migrations, tests, CI and evidence.
- Proposals: specs/plans/issues explicitly marked Proposed/In-flight.

Legacy backlogs/blackboard are cold references, not current worker write targets.

## 3. Runtime topology

### Frontend
- Next.js 16.3.6 / React 19.2.7.
- Node 22 / pnpm 10.
- TypeScript 5.9.
- Clerk browser identity/session.
- TanStack Query/API contracts.
- Vitest + Playwright.
- Sentry instrumentation.

### Backend
- Python 3.11.
- FastAPI 0.141.x + Pydantic v2.
- SQLAlchemy async + Alembic.
- PostgreSQL/Supabase with RLS + pgvector.
- Redis/Upstash.
- Celery asynchronous processing/recovery.
- Cloudflare R2/S3-compatible document storage.
- Presidio/spaCy/regex PII handling.
- Structlog, Sentry, Prometheus, LangSmith.

### AI/orchestration
- Anthropic is the principal configured LLM provider in the current application layer.
- LangChain/adapter boundaries isolate provider-specific calls.
- LangGraph 1.2.10 coordinates the active workflow.
- `langgraph-checkpoint-postgres==3.1.2` persists resumable state.
- Checkpoint schema provisioning is owner/bootstrap work; runtime only verifies readiness and fails closed for an unready configured PostgreSQL backend.

## 4. Identity and tenant boundary

Clerk JWTs are verified by the backend and mapped from Clerk organization/user identity to internal tenant/user records. Tenant-scoped requests establish PostgreSQL tenant context for RLS.

Invariants:
1. external identity is not itself database tenancy;
2. Clerk organization mapping resolves before tenant-scoped data access;
3. RLS is the final database isolation boundary;
4. platform-operator identity is separate and must not become a customer tenant;
5. secrets are never product evidence.

Supabase is the PostgreSQL/platform provider, not the canonical browser authentication provider.

## 5. Document processing authority

The durable processing owner is the single `document_processing_operations` row for a document.

An authority grant binds tenant, document, canonical revision, processing generation, stage, attempt id, owner token, monotonic fencing token and PostgreSQL-clock lease.

A worker may mutate canonical durable state only after re-verifying exact authority **inside the same transaction as the business write**.

`begin_generation` advances generation and fencing identity atomically with reprocess/new-revision reset.

See ADR-026.

## 6. LangGraph checkpoint lineage

Owned analysis does not share one document-wide checkpoint thread.

Canonical thread identity:

`document:{document_id}:g{generation}:f{fencing_token}:analysis`

A stale worker may physically append to its old lineage, but current processing/HITL paths do not name that lineage.

HITL resume persists and uses exact checkpoint identity:
- `thread_id`;
- `checkpoint_ns`;
- `checkpoint_id`;

and records processing-lineage generation/fencing metadata where applicable.

Resume/recovery rejects lineage that no longer matches current review/processing authority. Historical stale operations remain auditable but non-actionable.

The legacy `document:{document_id}:analysis` form is compatibility-only outside normal bound-authority production analysis.

## 7. HITL and trusted state

### Landed baseline
HITL is a durable review/resume boundary with exact decision/review/checkpoint ownership, fencing, recovery and lineage checks.

### In-flight #714
The broader Trusted-State Commit / ProjectGraph / projected Coherence design remains in-flight under #714 / PR #726. Its intended invariants (untrusted candidate, exact reviewed version/hash, commit-once, explicit projection) are **not promoted to Accepted platform behavior by this TDD**.

## 8. Project intelligence model

Accepted v3 architecture is recorded in ADR-013 through ADR-025.

Key red lines include typed/provenance-aware artifacts, temporal/revision lineage, semantic change impact, ProjectGraph/Health separation, one canonical hierarchical WBS for Project Controls and unknown evidence remaining unknown/null.

Implementation/activation status is owned by Product Control, not inferred from ADR acceptance.

## 9. Coherence and Health

Coherence scoring must remain evidence-aware, explainable and null-safe under ADR-009 and related decisions.

UI/API/export paths must preserve distinctions among validated value, unknown/insufficient evidence, trusted canonical result and scenario/projection.

Do not infer v1/v2 activation from this TDD; use Product Control + exact runtime evidence.

## 10. Persistence and schema authority

Alembic under `apps/api/alembic/` is application migration authority. Supabase SQL surfaces support platform/local/security needs as governed by migration runbooks.

Checkpoint schema is provisioned by `apps/api/scripts/checkpoint_bootstrap.py` with owner authority and the pinned checkpoint package. Restricted runtime checkpoint identity does not run DDL.

## 11. Asynchronous processing and recovery

Celery tasks carry bounded processing authority. Recovery rechecks durable state under lock, mints newer fenced authority only when permitted, bounds attempts, rejects stale canonical writes and treats superseded HITL lineage as historical/non-actionable.

## 12. Security baseline

Cross-cutting requirements include RLS, Clerk verification/tenant mapping, PII minimization before provider exposure, bounded MCP/tool capabilities, secret/dependency/code scanning, fail-closed durable-state ownership and auditable human/automated transitions.

Security claims must be tied to exact tests/checks/evidence.

## 13. CI and quality gates

Primary PR CI is `.github/workflows/ci.yml`, with dedicated Secret Scan, Install Drift, Dependency Review/Audit, CodeQL, Product-Control and other domain gates.

The protected-main ruleset is authoritative for exact required contexts.

## 14. Deployment and qualification

Current qualification surfaces include separate Vercel/Railway identities. Successful build/deploy is not equivalent to a qualified end-user journey.

#706/#715 own the deployed production-journey proof. This TDD does not assert those open acceptance gates have passed.

## 15. Documentation maintenance

Platform-composition changes update this TDD. Durable decision/invariant changes require a new/superseding ADR. Product/deployment lifecycle remains in Product Control.
