# C2Pro v4.2 — Platform Technical Design Document

> **Document Type:** Canonical Platform Technical Design  
> **Version:** 4.2  
> **Date:** 2026-10-01  
> **Status:** Current  
> **Supersedes:** v4.1 as the primary platform-wide technical design  
> **Audit baseline:** `main@d41cf3455daa0628c8c338841aa9e6e602d5715b`  
> **Audience:** Engineering, QA, DevOps, Security, Product, Architecture Review

---

## 1. Purpose

This document is the current platform-wide architectural baseline for C2Pro.

It does not replace detailed ADRs, product-control contracts, implementation plans, runbooks or historical evidence. It defines how those sources fit together and records the platform architecture that is already landed or explicitly accepted.

Historical documents remain valid evidence of the state at their date. They must not be silently rewritten to look current.

## 2. Authority and read order

Use the following order when sources appear to disagree:

1. **Machine-enforced product control**
   - `validation/product/c2pro-master-product-control-v1.yaml`
   - parity/validation code under `validation/product/`
2. **Accepted ADRs**
   - `docs/architecture/decisions/`
3. **This TDD**
   - platform-wide architecture and authority map
4. **Current specifications / product contracts**
   - `docs/product/`, `docs/specifications/`, current design specs
5. **Operational runbooks**
   - `docs/runbooks/`
6. **Testing and CI contracts**
   - workflows + validation code are executable truth; docs explain them
7. **Planning documents**
   - future/authorized implementation intent, not proof of landed behavior
8. **Historical audits/evidence**
   - point-in-time evidence; never current authority unless explicitly promoted

Task/status documents must not override machine-backed lifecycle state, accepted ADR semantics, or executable CI/runtime contracts.

## 3. Product architecture

C2Pro is a multi-tenant contract and project intelligence platform. Its architectural unit of reasoning is the **project**, not an isolated document.

The current product direction is:

`Evidence → Project State → Canonical WBS / Project Controls → Health / Coherence / Change / Alerts / HITL → governed decisions`

Key product invariants:

- evidence remains traceable to real source material;
- unknown/insufficient evidence is represented as unknown, never fabricated as zero;
- one project owns one canonical hierarchical WBS (ADR-025);
- pending AI output may be persisted for audit without becoming trusted canonical state;
- human approval of consequential output binds to the exact reviewed candidate/version/hash;
- official state and exports use trusted/canonical values, not hypothetical projections.

## 4. Repository architecture

C2Pro is a monorepo centered on:

| Surface | Path | Responsibility |
|---|---|---|
| Backend API | `apps/api` | FastAPI, domain/application/adapters, persistence, AI orchestration |
| Frontend | `apps/web` | Next.js product UI, Clerk auth, typed API consumption, E2E |
| Product control | `validation/product` + `docs/product` | machine lifecycle/control + human projection |
| CI / security | `.github/workflows` + validation tests | merge/release quality gates |
| Architecture | `docs/architecture` | TDD, ADRs, diagrams, architecture notes |
| Evidence | `evidence/` | immutable qualification/release evidence where applicable |

Backend code follows modular-monolith / bounded-context principles with domain, application, ports and adapters separation where implemented. Cross-context coupling through private ORM/domain internals is discouraged; shared contracts and explicit ports are preferred.

## 5. Project-state and temporal architecture

ADR-014 establishes `ProjectState` as the canonical aggregate/read model.

Documents are evidence-bearing inputs. Project intelligence is built from versioned entities, events/snapshots and typed projections rather than treating each document as an independent product universe.

Temporal/change semantics are governed by ADR-015/016. ProjectGraph orchestration is governed by ADR-017.

## 6. ProjectGraph and orchestration

The architecture remains two-tier:

1. **Document-level processing** produces typed, persisted candidate artifacts.
2. **Project-level processing** aligns project evidence and derives cross-document intelligence.

ProjectGraph is asynchronous and must not make upload latency depend on full project synthesis.

A critical refinement landed after the original ADR-017 design: **persisted does not mean trusted**. HITL-gated candidate output must not mutate canonical ProjectGraph/Health/Coherence until the trust boundary is satisfied.

See ADR-026.

## 7. Trusted-State Commit boundary

The canonical trust flow is:

`UNTRUSTED INPUT → candidate/proposal → durable evidence → review/verification → exact approval binding → TRUSTED COMMIT → canonical projections`

Rules:

- proposed/rejected/superseded candidates do not become canonical merely because they are persisted;
- approval/correction binds the exact candidate identity, version and digest/hash;
- stale or substituted approval fails closed;
- trusted commit is idempotent/exactly-once at the semantic boundary;
- canonical readers consume trusted state;
- ProjectGraph/Health/Coherence are recomputed/promoted from trusted evidence, not from an unreviewed proposal.

Implementation for #714 has landed on main. Production qualification of the broader #706 journey is a separate lifecycle concern.

## 8. Trusted vs projected Coherence

When pending review candidates exist:

- **trusted_score** is canonical;
- **projected_score** is hypothetical and explicitly non-canonical;
- projections must use the same canonical scoring engine/version, not ad-hoc subtraction;
- no projection may be silently substituted for official state;
- null/insufficient-evidence semantics remain authoritative.

## 9. Canonical Project Controls / WBS

ADR-025 establishes:

> One project → one canonical hierarchical WBS.

Budget, Schedule, Procurement, Stakeholders/RACI, Alerts, Evidence and Changes attach to that hierarchy or explicitly to project-level scope.

Parallel WBS stores must not become independent competing authorities.

## 10. Authentication and tenancy

Clerk is the user-facing authentication provider. C2Pro tenant/org mapping must remain explicit and fail closed.

Tenant safety relies on agreement between:

- authenticated tenant/org context;
- application authorization;
- tenant-scoped repository access;
- PostgreSQL RLS / database capability boundaries.

Cross-tenant leakage is release-blocking.

## 11. Production topology and qualification

Current production architecture uses separate deployment planes/providers. Qualification must prove the **actual composite runtime** exercised rather than assume all planes share one SHA.

The #715 harness is landed, but #715 remains open until controlled production qualification is executed and accepted.

Production qualification rules include:

- manual/protected execution;
- exact provider-observed Railway API/Worker/Scheduler identities;
- exact Vercel production identity;
- canonical production-host validation before credentials are entered;
- dedicated synthetic Clerk org/user/tenant;
- committed fixture + SHA-256 binding;
- read-only durable verification where required;
- no customer tenant access;
- no arbitrary filesystem output paths;
- bounded, non-secret evidence;
- fail closed on identity/tenant/fixture mismatch;
- implementation of the harness does not equal production validation.

See `docs/product/production-qualification-operator-runbook.md`.

## 12. CI and merge governance

As of the audit baseline, the active `main` ruleset requires:

- `CI Status`
- `gitleaks`
- `Install Drift Guard`

The consolidated `.github/workflows/ci.yml` is the primary PR CI graph. Supporting workflows include CodeQL, dependency review/audit, product-control guard, release/evaluation and production-qualification workflows.

Documentation must not refer to retired `tests.yml`, `frontend-ci.yml` or `e2e-security-tests.yml` as current required merge workflows.

Required-check truth lives in the repository ruleset and current workflow definitions.

## 13. Product-control boundary

Product Control is not ordinary Markdown status prose.

The machine source is:

`validation/product/c2pro-master-product-control-v1.yaml`

The human projection is:

`docs/product/00-c2pro-master-product-control-v1.md`

Rules:

- edit machine source first;
- regenerate/validate the projection;
- do not hand-edit generated canonical control blocks;
- branch completion, merge, deployment and production validation are separate states;
- evidence is necessary for promotion but does not autonomously promote lifecycle state.

## 14. Security principles

- least privilege by default;
- no secrets in source/evidence/logs;
- immutable or append-only evidence where required;
- exact identity binding for consequential operations;
- fail closed on ambiguous authority;
- human review for consequential contract/project decisions;
- no Sonar/QG/baseline manipulation to manufacture green status;
- supply-chain actions pinned where policy requires;
- dependency/install drift guarded explicitly.

## 15. Documentation lifecycle

Documents are classified as:

- **Canonical active:** current TDD, accepted ADRs, machine-backed product control, active runbooks/specs.
- **Planning:** authorized intent that may not yet be landed.
- **Historical evidence:** dated audits, release evidence, superseded TDDs and implementation reports.
- **Working context:** temporary analysis/session material; never authority.

Do not rewrite historical evidence to make it current. Create a new canonical revision or update the current canonical document.

## 16. Current architecture status — 2026-10-01

Verified against repository/GitHub state at the audit baseline:

- #714 is closed and PR #726 is merged: Trusted-State Commit architecture is landed.
- PR #733 is merged: the #715 production-acceptance harness implementation is landed.
- #715 remains open: production qualification itself is not yet proven/accepted.
- #706 remains open: the full production end-user goal is not closed by harness implementation alone.
- R17 bounded Sonar/hotspot cleanup is closed; quality cleanup must remain separate from functional lifecycle promotion.

Any newer machine Product Control reconciliation supersedes this dated status section.

## 17. Superseded documents

- v4.1 remains the March 2026 architecture baseline.
- v4.0 remains a historical/supporting frontend-heavy design reference.
- dated production-readiness reports remain historical unless explicitly promoted.

## 18. Maintenance

Update this TDD only for platform-wide architectural changes.

Use ADRs for durable architectural decisions, runbooks for operator procedures, Product Control for lifecycle authority, and evidence bundles for proof.

---

## Changelog

| Version | Date | Change |
|---|---|---|
| 4.2 | 2026-10-01 | Reconciled current project-state/WBS architecture, trusted-state boundary, production qualification, Product Control authority, CI ruleset and documentation lifecycle. |
| 4.1 | 2026-03-29 | Previous platform-wide baseline. |
