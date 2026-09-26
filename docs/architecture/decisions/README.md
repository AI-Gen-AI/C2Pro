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

## C2Pro v3.0 — Project Intelligence Overlay (ADR-013 → ADR-025)

Canonical set ratified 2026-06-07 by multi-model arbitration (DeepSeek / Codex / Claude / Gemini blueprints + Architecture Challenger verdict; sources in [`docs/audits/`](../../audits/)). Cross-cutting invariant **INV-1 (Evidence & Provenance, tiered)** is defined in ADR-013 and extends the in-flight evidence layer. Later accepted product decisions extend the original set without rewriting its history.

- [ADR-013 Typed Graph Contract & Runtime Correctness Baseline](./ADR-013-typed-graph-contract-runtime-correctness.md) — **P0 Foundation**
- [ADR-014 Project State Model (Canonical Aggregate)](./ADR-014-project-state-model.md) — **P0 Foundation / keystone** · hosts the Future Bounded-Context Reservation Plan (Procurement, Stakeholder)
- [ADR-015 Temporal Intelligence Layer](./ADR-015-temporal-intelligence-layer.md) — **P0 Foundation**
- [ADR-016 Semantic Diff & Change-Impact Engine](./ADR-016-semantic-diff-change-impact-engine.md) — **P0→P1 Core (the wedge)**
- [ADR-017 ProjectGraph Orchestration (Two-Tier, Async)](./ADR-017-projectgraph-two-tier-orchestration.md) — **P1 Core**
- [ADR-018 Project Health Engine](./ADR-018-project-health-engine.md) — **P0/P1 primary product surface; six-dimension Health/Coherence/Alerts clarification 2026-09-13**
- [ADR-019 Alert Correlation & Action Lifecycle](./ADR-019-alert-correlation-action-lifecycle.md) — **P2 Action/HITL differentiation; alert visibility is cross-cutting**
- [ADR-020 HITL Workflow System](./ADR-020-hitl-workflow-system.md) — **P2 Differentiation**
- [ADR-021 Read-Model & Briefing Projection](./ADR-021-read-model-briefing-projection.md) — **P3 · Deferred**
- [ADR-022 Contract Clarity Findings (Health v0, Findings-Only)](./ADR-022-contract-clarity-findings.md) — **P2 · extends ADR-018** · resolves TASK-V3-P1-SCOPE-11
- [ADR-023 Agentic Coherence Architecture](./ADR-023-agentic-coherence-architecture.md) — **Proposed; not required for current product-control activation**
- [ADR-024 Single-Document Activation](./ADR-024-single-document-activation.md) — **Accepted P0b product activation**
- [ADR-025 Canonical Project Controls Backbone — One Hierarchical WBS per Project](./ADR-025-canonical-project-controls-wbs-backbone.md) — **Accepted P1 Product Foundation**

**Critical path:** 013 → 014 → 015 (revisions) → 016 (change) → 018/024 (current-state product) → 025 (canonical Project Controls backbone). ADR-017/023 extend relational/agentic depth but are not allowed to block the user-visible product path.

**Product-control red line:** a project has one canonical hierarchical WBS. Budget, Schedule, Procurement, Stakeholders/RACI, Alerts, Evidence and Changes attach to that tree (or explicitly project-level scope). Discipline branches are not separate WBSs.

**Evidence red line:** `Unknown` remains null/insufficient evidence. Coherence/Health/Alerts may drill down through the WBS only when evidence supports the statement; no blind arithmetic roll-up and no unknown-to-zero conversion.

**Rejected from canon:** Passive Ingestion Mesh as an ADR; full event sourcing; absolute evidence veto; agent-mesh orchestration as a prerequisite for product value; BIM/IFC, mobile field app, native Gantt, Neo4j, NL rules engine, plugin marketplace before validated need.

## Related Sections

- [Architecture index](../README.md)
- [Archived decisions](../../archive/architecture/decisions/)
- [Documentation index](../../README.md)