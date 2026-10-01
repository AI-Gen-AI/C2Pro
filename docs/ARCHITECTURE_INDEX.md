# C2Pro Architecture Documentation Index

> **Version:** 2.0.0  
> **Last Updated:** 2026-10-01  
> **Status:** Current  
> **Purpose:** Canonical navigation and authority map for C2Pro architecture

## Authority entry points

Authority is scoped by concern:

1. `validation/product/c2pro-master-product-control-v1.yaml` — **product programme/lifecycle**.
2. `.c2pro/control/` + assigned `.c2pro/work/` — **development execution/control**.
3. `docs/architecture/C2PRO_TECHNICAL_DESIGN_DOCUMENT_v4_2.md` — **current platform design**.
4. `docs/architecture/decisions/README.md` — **durable architecture decisions**.
5. `docs/product/qualification-evidence-contract-v1.md` + operator runbook — **qualification procedure/evidence**.
6. live workflows/ruleset — **merge/release executable enforcement**.
7. planning/historical evidence — contextual, never a higher authority than the scoped sources above.

## Current platform baseline

| Document | Purpose |
|---|---|
| [TDD v4.2](./architecture/C2PRO_TECHNICAL_DESIGN_DOCUMENT_v4_2.md) | Current platform-wide technical design |
| [ADR index](./architecture/decisions/README.md) | Durable architecture decisions |
| [Flow diagrams](./architecture/FLOW_DIAGRAMS.md) | System flow reference |
| [LangGraph checkpointing](./architecture/LANGGRAPH_CHECKPOINTING.md) | Checkpoint/state persistence reference |
| [Product Control](./product/00-c2pro-master-product-control-v1.md) | Human projection of machine product-control state |
| [Qualification evidence contract](./product/qualification-evidence-contract-v1.md) | Evidence binding/promotion rules |
| [Production qualification runbook](./product/production-qualification-operator-runbook.md) | #715 operator procedure |

## Core architecture sequence

### Foundation and repository structure

- 001 — Modular monolith architecture
- 002 — Supabase for MVP
- 003 — AI architecture
- 004 — Frontend layer rules
- 005 — Three-layer SC test strategy
- 006 — Post-reorganization architecture

### Coherence/runtime decisions

- ADR-004 — Circuit breakers
- ADR-009 — Evidence-oriented Coherence orchestration
- ADR-013 — Typed graph contract/runtime correctness
- ADR-014 — Project State Model
- ADR-015 — Temporal Intelligence
- ADR-016 — Semantic Diff / Change Impact
- ADR-017 — ProjectGraph two-tier orchestration
- ADR-018 — Project Health Engine
- ADR-019 — Alert correlation/action lifecycle
- ADR-020 — HITL workflow
- ADR-021 — Read-model/briefing projection
- ADR-022 — Contract clarity findings
- ADR-023 — Agentic Coherence architecture
- ADR-024 — Single-document activation
- ADR-025 — Canonical Project Controls WBS backbone
- ADR-026 — Trusted-State Commit and exact approval binding

## Architectural invariants

- **Project is the unit of intelligence**, not the individual document.
- **Evidence remains traceable** to real source material.
- **Unknown is not zero**; insufficient evidence is represented honestly.
- **One project = one canonical hierarchical WBS**.
- **Persisted != trusted**.
- **Consequential approval binds the exact reviewed candidate/version/hash**.
- **Pending/rejected candidates do not mutate canonical state**.
- **Production qualification proves the actual composite deployed runtime**.
- **Implementation/merge/deployment/production validation are separate lifecycle states**.

## Current state boundary — 2026-10-01

Verified at audit baseline `main@d41cf3455daa0628c8c338841aa9e6e602d5715b`:

- #714 closed and PR #726 merged.
- PR #733 merged (production acceptance harness implementation landed).
- #715 remains open (production qualification not yet accepted).
- #706 remains open.
- active main ruleset requires `CI Status`, `gitleaks`, `Install Drift Guard`.

For newer lifecycle state, Product Control and GitHub/current executable state take precedence over this dated summary.

## Superseded/historical design

- [TDD v4.1](./architecture/C2PRO_TECHNICAL_DESIGN_DOCUMENT_v4_1.md) — March 2026 platform baseline.
- [TDD v4.0](./architecture/C2PRO_TECHNICAL_DESIGN_DOCUMENT_v4_0.md) — earlier frontend-heavy/supporting baseline.
- `context/archive/legacy/` — superseded design material.
- dated planning/audit documents — point-in-time evidence, not live authority.

## Related indexes

- [Documentation index](./README.md)
- [Architecture section](./architecture/README.md)
- [Runbooks](./runbooks/README.md)
- [Testing](./testing/README.md)

## Changelog

| Version | Date | Changes |
|---|---|---|
| 2.0.0 | 2026-10-01 | Promoted TDD v4.2, added authority hierarchy, ADR-013→026 sequence, Product Control/qualification boundaries and current CI/lifecycle state. |
| 1.1.0 | 2026-03-29 | Previous architecture index baseline. |
