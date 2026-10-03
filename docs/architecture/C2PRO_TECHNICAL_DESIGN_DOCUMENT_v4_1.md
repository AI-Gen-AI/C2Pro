# C2Pro v4.1 — Platform Technical Design Document

> **Lifecycle:** Supporting historical design — not the current architecture authority.  
> Current synthesis: `docs/architecture/C2PRO_TECHNICAL_BASELINE_2026-10-01.md`; accepted decisions: `docs/architecture/decisions/`. Reclassified 2026-10-01.


> **Document Type:** Historical platform technical-design snapshot
> **Version:** 4.1
> **Date:** 2026-03-29
> **Historical status:** Current as of 2026-03-29; supporting only after 2026-10-01
> **Historical relationship:** superseded v4.0 in March 2026; now itself superseded as current authority by the 2026-10-01 technical baseline + accepted ADRs
> **Audience:** Engineering, QA, DevOps, Security, Product, Architecture Review Board

---

## 1. Purpose

This document records the platform-wide technical-design baseline as understood on 2026-03-29. It remains useful for historical rationale and implementation context, but it does not define current lifecycle state or override later ADRs.

For current interpretation, start with:

- `docs/DOCUMENTATION_AUTHORITY.md`
- `docs/architecture/C2PRO_TECHNICAL_BASELINE_2026-10-01.md`
- `docs/architecture/decisions/README.md`
- `validation/product/c2pro-master-product-control-v1.yaml` when lifecycle status matters

---

## 2. Governance and Source-of-Truth Rules

### 2.1 Delivery Governance — historical note

The March 2026 backlog-governance model described by earlier revisions is superseded. Current execution authority is the single-writer `.c2pro/` control plane; Product Control owns programme lifecycle state.

### 2.2 Technical Governance — current interpretation

Accepted ADRs and the dated current technical baseline take precedence over this document. This file must not be used to override later trust, WBS, temporal, qualification or deployment decisions.

### 2.3 Historical project-state snapshot

The monorepo statement (`apps/api` + `apps/web`) remains structurally useful. Completion percentages and release-readiness language from the March snapshot are historical and must not be treated as current status.

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
