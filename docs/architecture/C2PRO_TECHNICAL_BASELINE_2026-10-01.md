# C2Pro Technical Architecture Baseline — 2026-10-01

**Status:** Canonical current-state architecture baseline  
**Baseline main SHA:** `33650a28a930d82a7bd65d98b50981145b3fd1d1`  
**Scope:** implemented architecture and active product-control boundaries, not a product-release claim

> This document describes the architecture that exists or is explicitly governed on the baseline above. It does **not** imply that the complete end-user journey is production validated. Product lifecycle truth remains in `validation/product/c2pro-master-product-control-v1.yaml`.

## 1. Architectural principles

1. **Project is the intelligence boundary.** Documents are evidence inputs to an evolving project state, not isolated products.
2. **Evidence before assertion.** Unsupported state remains unknown/null; it is never converted to zero or a fabricated green state.
3. **One project, one canonical hierarchical WBS.** Budget, schedule, procurement, stakeholders/RACI, alerts, evidence and changes attach to that hierarchy or explicitly to project scope.
4. **HITL review is an exact trust boundary when review is required.** A policy-routed non-gated completion may become trusted without human action; a HITL-gated candidate remains proposed/untrusted until exact review approval.
5. **Processing authority is fenced.** A stale worker or stale checkpoint lineage cannot become current after processing ownership changes.
6. **Health, Coherence and Alerts are distinct signals.** They share the six dimensions but answer different questions.
7. **Qualification evidence is non-authoritative.** CI, deployment and evidence bundles can prove prerequisites; they never self-promote lifecycle state.
8. **Multi-tenancy fails closed.** Tenant isolation, RLS, scoped repositories and auth context are security invariants.

## 2. Current runtime topology

```text
Browser
  │
  ▼
Next.js 16 / React 19 (Vercel)
  │  Clerk auth + organization-scoped token
  ▼
FastAPI 0.141.x (Railway API service)
  │
  ├── PostgreSQL / Supabase
  │     ├── tenant-scoped domain state
  │     ├── RLS
  │     ├── pgvector evidence/retrieval
  │     └── LangGraph Postgres checkpoints
  │
  ├── Redis
  │     ├── Celery broker/runtime coordination
  │     └── bounded cache/event use
  │
  ├── Railway Worker service
  │     └── durable document / analysis processing
  │
  ├── Railway Scheduler service
  │     └── periodic recovery / scheduled work
  │
  ├── Configured object storage
  │     └── R2-compatible implementation is the default code path; runtime provider binding is qualified separately
  │
  └── AI providers through governed adapters
        └── extraction / reasoning / specialist paths
```

The API, worker and scheduler have separate lifecycle ownership even when they share an image. Frontend and backend deployments may legitimately run different commit SHAs; production qualification binds each observed runtime independently.

## 3. Frontend

- **Next.js:** 16.3.6
- **React:** 19.2.7
- **Node:** 22.x
- **Package manager:** pnpm 10+
- **Auth:** Clerk via `@clerk/nextjs`
- **Server/client boundary:** Next.js App Router conventions plus generated API clients/TanStack Query on interactive surfaces
- **State:** Zustand where client-side synchronization is required
- **Testing:** Vitest + Playwright
- **Deployment:** Vercel

### Auth synchronization invariant

Backend auth also accepts Clerk v2 organization claim shapes merged via #781; organization/tenant derivation must remain compatible with both supported Clerk claim forms without weakening tenant validation.


When an organization is active, the organization-scoped, cache-bypassed Clerk token is the token synchronized into the application auth store. Superseded organization token requests are cancelled/ignored before they can overwrite newer organization state. This prevents stale personal or previous-organization tokens from winning a race.

## 4. Backend and persistence

- **FastAPI:** 0.141.1
- **Python:** 3.11+
- **Pydantic:** v2
- **SQLAlchemy:** async 2.x
- **PostgreSQL:** canonical transactional store
- **Supabase:** managed PostgreSQL/RLS platform integration
- **Alembic:** migration authority
- **Celery 5.6:** durable asynchronous execution
- **Redis:** queue/cache/event substrate
- **LangGraph 1.2:** governed graph orchestration
- **LangGraph Postgres checkpointer:** persisted graph checkpoints
- **pgvector:** evidence/retrieval vector support

Repositories do not gain authority merely by writing data. Canonical writes must satisfy tenant, lifecycle, processing-authority and trusted-state invariants.

## 5. Canonical project model

The project aggregate is the unit of intelligence. The principal architectural spine is:

```text
Project
├── Evidence / Documents / Revisions
├── Clauses / Obligations / Findings
├── Canonical WBS
│   ├── Schedule / milestones
│   ├── Budget / cost state
│   ├── Procurement mappings
│   ├── Stakeholders / RACI
│   ├── Alerts / actions
│   └── Evidence / change linkage
├── Project events / snapshots
├── Health
├── Relational Coherence
└── Change / temporal intelligence
```

The canonical invariant is one WBS hierarchy per project; discipline-specific trees are not separate canonical WBSs. Product Control still classifies ADR-025 realization as PARTIAL because complete one-logical-root enforcement and the remaining cross-domain linkages are not yet fully proven.

## 6. Three user-facing intelligence signals

The canonical dimensions are:

`SCOPE · BUDGET · TIME · TECHNICAL · LEGAL · QUALITY`

| Signal | Question | Non-negotiable rule |
|---|---|---|
| Health / coverage | Do we have enough evidence, and what can we truthfully say? | Missing evidence = Unknown/null |
| Coherence | Do reconcilable project facts agree? | High coherence does not mean healthy |
| Alerts | What concrete condition needs attention? | Category is dimensional; trigger is orthogonal |

A project can therefore be highly coherent and still have a critical TIME alert if all evidence consistently proves a delay.

## 7. Trusted-state commit boundary

C2Pro currently has two completion paths and they must not be conflated:

1. **Policy-approved / non-gated completion.** When routing explicitly sets `human_approval_required=False`, the completion hook persists the artifact as `TRUSTED` and may enqueue canonical ProjectGraph without a human review action.
2. **HITL-gated completion.** When human review is required (or the state does not explicitly opt out), the artifact is persisted as `PROPOSED`; canonical ProjectGraph enqueue is blocked until the exact bound candidate is approved/corrected through the review workflow.

ADR-026 governs the second path. For HITL-gated candidates:

- pending review does not mutate trusted state;
- rejected state does not mutate trusted state;
- correction supersedes the prior proposal and must bind the corrected candidate;
- approval commits the exact reviewed candidate exactly once;
- exports default to trusted state unless explicitly labelled as a scenario/projection;
- projected Coherence is hypothetical and visually/semantically distinct from trusted Coherence.

The present `ConfidenceRouter` uses confidence/impact thresholds and can auto-approve high-confidence LOW/MEDIUM-impact items. ADR-020's richer policy intent (including mandatory human review for named consequential decision classes) therefore remains a **partially realized policy boundary**, not something this baseline claims is fully enforced.

See ADR-020 and ADR-026.

## 8. Processing authority and checkpoint lineage

Celery redelivery/recovery is safe only when durable writes and LangGraph checkpoint selection share the same authority model.

A processing generation/attempt owns an authority fence. After takeover or reprocess/revision supersession:

- stale application writes are rejected;
- stale checkpoint lineage cannot be selected as current;
- HITL resumes the exact persisted checkpoint tuple when `checkpoint_id` capture succeeded;
- if no checkpoint ID was captured, thread-only “latest checkpoint” lookup is allowed only within the same authority-scoped attempt lineage and cannot cross an authority boundary.

See ADR-027.

## 9. Production qualification

The production synthetic acceptance harness is intentionally separate from ordinary CI.

It binds:

- canonical repository/main identity;
- independently observed Railway API/Worker/Scheduler identities;
- independently observed Vercel deployment identity;
- dedicated synthetic production tenant/identity;
- real Clerk authentication;
- tenant-scoped durable-state evidence;
- bounded evidence artifacts without secrets.

The evidence bundle is necessary for promotion but cannot promote Product Control by itself. See ADR-028 and `docs/product/qualification-evidence-contract-v1.md`.

## 10. CI/CD and deployment governance

`main` is protected by repository rulesets. Current required checks are:

- `CI Status`
- `gitleaks`
- `Install Drift Guard`

Vercel is **not** a required PR status because ordinary PR branches do not automatically deploy. Automatic Vercel Git deployments are allowlisted to:

- `main`
- `hotfix/**`
- `release-candidate/**`
- `preview/**`

Allowed branches additionally skip Vercel builds when no web/root build input changed. Railway owns backend deployment from the protected production branch.

Operational detail: `docs/runbooks/ci-cd-setup.md`.

## 11. Authority boundaries

Do not use one mixed precedence list for different questions.

### Architecture / design questions

When documents disagree about **what the architecture is intended to be**:

1. accepted ADRs in `docs/architecture/decisions/`;
2. this dated current-state technical baseline;
3. focused current architecture specifications/runbooks;
4. historical TDDs, plans and audit reports.

Product Control records lifecycle/evidence status; it does **not** override an accepted architecture decision.

### Product lifecycle / readiness questions

When asking whether a capability is designed, realized, deployed or production validated:

1. machine Product Control: `validation/product/c2pro-master-product-control-v1.yaml`;
2. guarded human projection: `docs/product/00-c2pro-master-product-control-v1.md`;
3. exact-head CI/deployment/qualification evidence as referenced by the control plane.

### Development execution questions

Current work authority lives under `.c2pro/control/`, `.c2pro/work/` and the machine development controls under `validation/development/`.

Code/CI proves realization evidence; it does not silently rewrite an ADR. If implementation intentionally changes an accepted architecture decision, amend/supersede that ADR explicitly.

## 12. Current non-claims

As of this baseline:

- `#706` remains open: the full production end-user journey is not yet declared operational.
- `#715` remains open: the production synthetic harness exists, but a successful full-journey qualification has not been accepted.
- `#690` remains open: dedicated production qualification identity/tenant evidence remains an external prerequisite.
- `#712` and `#713` remain open fix-forward workstreams.
- No documentation change in this reconciliation promotes P0b/P0c/P0d to `PROD_VALIDATED`.

## 13. Related decisions

- ADR-013 — Typed Graph Contract & Runtime Correctness
- ADR-014 — Project State Model
- ADR-015 — Temporal Intelligence
- ADR-016 — Semantic Diff / Change Impact
- ADR-017 — ProjectGraph orchestration
- ADR-018 — Project Health
- ADR-020 — HITL workflow
- ADR-024 — Single-document activation
- ADR-025 — Canonical WBS
- ADR-026 — Trusted-State Commit
- ADR-027 — Processing Authority / Checkpoint Lineage
- ADR-028 — Production Qualification / Composite Runtime Identity
