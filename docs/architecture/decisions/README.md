# Architecture Decisions

This section contains the active architecture decision records for the current repository state.

## Current ADR Set

- [001 Modular monolith architecture](./001-modular-monolith-architecture.md)
- [002 Supabase for MVP](./002-supabase-for-mvp.md)
- [003 AI architecture](./003-ai-architecture.md)
- [004 Frontend layer rules](./004-frontend-layer-rules.md)
- [005 Three-layer SC test strategy](./005-three-layer-sc-test-strategy.md)
- [006 Post-reorganization architecture](./006-post-reorganization-architecture.md)
- [ADR-004 Circuit breakers](./ADR-004-circuit-breakers.md)
- [ADR-009 Coherence Score v2 — Evidence-Aware, Explainable, Bottom-Up](./ADR-009-evidence-oriented-coherence-orchestration.md)

> **Reserved (in-flight, not yet filed):** ADR-010 (Evidence Maturity), ADR-011 (Evidence Intelligence), ADR-012 (deferred) are referenced in `CHANGELOG.md` / `CLAUDE.md`. The v3.0 canon starts at ADR-013 to avoid collision.

## C2Pro v3.0 — Project Intelligence Overlay (ADR-013 → ADR-022)

Canonical set ratified 2026-06-07 by multi-model arbitration (DeepSeek / Codex / Claude / Gemini blueprints + Architecture Challenger verdict; sources in [`docs/audits/`](../../audits/)). Cross-cutting invariant **INV-1 (Evidence & Provenance, tiered)** is defined in ADR-013 and extends the in-flight evidence layer.

- [ADR-013 Typed Graph Contract & Runtime Correctness Baseline](./ADR-013-typed-graph-contract-runtime-correctness.md) — **P0 Foundation**
- [ADR-014 Project State Model (Canonical Aggregate)](./ADR-014-project-state-model.md) — **P0 Foundation / keystone** · hosts the Future Bounded-Context Reservation Plan (Procurement, Stakeholder)
- [ADR-015 Temporal Intelligence Layer](./ADR-015-temporal-intelligence-layer.md) — **P0 Foundation**
- [ADR-016 Semantic Diff & Change-Impact Engine](./ADR-016-semantic-diff-change-impact-engine.md) — **P0→P1 Core (the wedge)**
- [ADR-017 ProjectGraph Orchestration (Two-Tier, Async)](./ADR-017-projectgraph-two-tier-orchestration.md) — **P1 Core**
- [ADR-018 Project Health Engine](./ADR-018-project-health-engine.md) — **P1 Core**
- [ADR-019 Alert Correlation & Action Lifecycle](./ADR-019-alert-correlation-action-lifecycle.md) — **P2 Differentiation**
- [ADR-020 HITL Workflow System](./ADR-020-hitl-workflow-system.md) — **P2 Differentiation**
- [ADR-021 Read-Model & Briefing Projection](./ADR-021-read-model-briefing-projection.md) — **P3 · Deferred**
- [ADR-022 Contract Clarity Findings (Health v0, Findings-Only)](./ADR-022-contract-clarity-findings.md) — **P2 · extends ADR-018** · resolves TASK-V3-P1-SCOPE-11

**Critical path:** 013 → 014 → 015 (revisions) → 016 (L1) → 017 → 018 (v0).
**Build gate:** the canon is *ratified*, not simultaneously funded. Build the **Thin Spine** (013–018 v0) first; everything after Month 3 (019, 020, 018-v1, 021) is gated behind one real Contract Manager using the Change-Impact loop weekly.
**Architectural red line:** no new module unless it strengthens **Time, Change, Health, Evidence, or Action**.
**Rejected from canon:** Passive Ingestion Mesh as an ADR; "Change Intelligence" as a standalone ADR; full event sourcing; absolute evidence veto; agent-mesh orchestration; BIM/IFC, mobile field app, native Gantt, Neo4j, NL rules engine, plugin marketplace.

## Related Sections

- [Architecture index](../README.md)
- [Archived decisions](../../archive/architecture/decisions/)
- [Documentation index](../../README.md)
