# C2Pro v4.1 — Platform Technical Design Document

> **Document Type:** Canonical Platform Technical Design
> **Version:** 4.1
> **Date:** 2026-03-29
> **Status:** Current
> **Supersedes:** `docs/architecture/C2PRO_TECHNICAL_DESIGN_DOCUMENT_v4_0.md` as the primary platform-wide technical design
> **Audience:** Engineering, QA, DevOps, Security, Product, Architecture Review Board

---

## 1. Purpose

This document is the platform-wide technical design baseline for C2Pro.

It replaces the earlier frontend-heavy v4.0 document as the primary technical design reference and aligns architecture guidance with the current repository and delivery state.

This document must be read together with:

- `C2PRO_MASTER_BACKLOG.md`
- `docs/architecture/decisions/006-post-reorganization-architecture.md`
- `docs/testing/PHASE4_TDD_IMPLEMENTATION_ROADMAP.md`
- `docs/testing/C2PRO_TEST_SUITES_INDEX_v1.1.md`

---

## 2. Governance and Source-of-Truth Rules

### 2.1 Delivery Governance

- `C2PRO_MASTER_BACKLOG.md` is the single source of truth for all open work.
- Any newly discovered task must be added there with a stable ID.
- Any completed task must be marked complete there when the implementing change lands.
- Supporting documents may describe scope, evidence, or history, but they do not own task state.

### 2.2 Technical Governance

- This document is the canonical platform-wide technical design.
- ADR-006 is the canonical repo-structure and post-reorganization architecture baseline.
- The v4.0 document remains useful as a detailed frontend implementation reference, but it is no longer the primary platform design document.

### 2.3 Current Project State

- C2Pro is a monorepo with `apps/api` and `apps/web`.
- Delivery status is approximately 90% complete.
- The architecture is mature enough for release-candidate hardening; the remaining work is concentrated in release execution, evidence, and targeted hardening rather than core platform invention.

---

## 3. Platform Scope

C2Pro is a multi-tenant SaaS platform for contract intelligence, proposal management, procurement intelligence, stakeholder mapping, and coherence analysis.

Core capability chain:

`Upload -> Anonymize -> Extract -> Analyze -> Coherence`

Major product surfaces:

- Contract and document ingestion
- Clause extraction and normalization
- Analysis and coherence scoring
- WBS and procurement intelligence
- Stakeholder and RACI intelligence
- AI evaluation and release-gate validation

---

## 4. Monorepo Structure

### 4.1 Primary Apps

| Surface | Path | Role |
|---------|------|------|
| Backend API | `apps/api` | FastAPI, domain modules, persistence, AI orchestration, tests |
| Frontend Web | `apps/web` | Next.js application, auth, UI, API consumption, testing |

### 4.2 Canonical Backend Shape

The backend follows a modular-monolith pattern with hexagonal boundaries:

- `domain/`: pure business logic
- `ports/`: public interfaces via `Protocol` or abstract contracts
- `application/`: use cases and orchestration
- `adapters/`: HTTP, persistence, external integrations

Cross-cutting infrastructure is hosted under `apps/api/src/core`.

### 4.3 Canonical Frontend Shape

The frontend uses:

- Next.js App Router
- Clerk-backed authentication
- React Query for server state
- Zustand for selected client-side state
- generated and typed API clients

Demo mode is a mode, not a separate app.

---

## 5. Architectural Principles

### 5.1 Multi-Tenant Safety

- `tenant_id` enforcement is mandatory in all tenant-scoped repository access.
- PostgreSQL RLS and application tenant context must agree.
- Cross-tenant leakage is a release-blocking defect class.

### 5.2 Contract Traceability

- `clauses` is the security and traceability source of truth for downstream contract-derived intelligence.
- Generated or inferred entities must remain evidence-linked where required by the pipeline.

### 5.3 TDD Discipline

- Backend changes follow strict `RED -> GREEN -> REFACTOR`.
- Tests define the contract first.
- Documentation and backlog updates are part of completion, not optional cleanup.

### 5.4 Bounded Context Integrity

- Modules do not import each other’s ORM models or private domain internals.
- Inter-module communication happens through shared public contracts, shared kernel types, or event mechanisms.

---

## 6. Platform Capabilities by Layer

### 6.1 Backend Platform

Key backend domains currently present in `apps/api/src` include:

- `documents`
- `coherence`
- `projects`
- `procurement`
- `stakeholders`
- `analysis`
- `alerts`
- `golden`
- `mcp`
- `core`

Key backend responsibilities:

- JWT and tenant-context enforcement
- async persistence patterns
- document processing and extraction flows
- LangGraph orchestration and checkpointing
- golden regression and evaluation tooling

### 6.2 Frontend Platform

Key frontend responsibilities:

- authenticated product shell
- typed consumption of backend contracts
- alert, coherence, project, stakeholder, and evidence views
- release-safe demo behavior through interception rather than duplicate feature logic

### 6.3 AI and Evaluation Platform

AI platform responsibilities include:

- orchestration reliability
- checkpoint persistence
- evidence-aware outputs
- golden dataset regression
- explainability and release gating

---

## 7. Cross-Cutting Standards

### 7.1 Backend

- Python 3.11+
- strict typing
- FastAPI thin routers
- SQLAlchemy async patterns
- Pydantic v2
- repository and service boundaries aligned with hexagonal design

### 7.2 Frontend

- typed API integration
- route and provider consistency
- no demo/prod logic drift in feature components
- test coverage at unit, integration, and E2E layers

### 7.3 Security

- tenant isolation
- auth correctness
- release-gate evidence
- least-privilege integration assumptions
- explicit review for high-impact AI outputs

---

## 8. Current Delivery Focus

The current phase is not foundational design. It is controlled completion.

Primary near-term focus:

- close remaining release blockers from `C2PRO_MASTER_BACKLOG.md`
- finish final release evidence and signoff work
- continue golden evaluation expansion
- preserve architecture consistency while shipping targeted improvements

---

## 9. Relationship to v4.0

`docs/architecture/C2PRO_TECHNICAL_DESIGN_DOCUMENT_v4_0.md` remains a valid supporting reference for:

- frontend implementation details
- earlier App Router decisions
- provider and client patterns
- UI testing and accessibility details

It should no longer be treated as the sole technical design for the full platform.

---

## 10. Document Maintenance Rules

- Update this document when platform-wide architecture or governance changes.
- Update `C2PRO_MASTER_BACKLOG.md` when task status changes.
- Do not create competing status registers.
- If a document introduces active work, that work must also be recorded in the master backlog.

---

## Changelog

| Version | Date | Change |
|---------|------|--------|
| 4.1 | 2026-03-29 | Created platform-wide technical design and aligned governance to a single canonical backlog. |
