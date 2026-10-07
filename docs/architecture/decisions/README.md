# Architecture Decisions

**Status:** Canonical ADR catalogue  
**Last reconciled:** 2026-10-01

This directory is the authoritative human catalogue of durable architecture decisions. Product lifecycle status is separate and remains owned by Product Control.

## Foundational decisions

- [001 Modular monolith architecture](./001-modular-monolith-architecture.md)
- [002 Supabase for MVP](./002-supabase-for-mvp.md)
- [003 AI architecture](./003-ai-architecture.md)
- [004 Frontend layer rules](./004-frontend-layer-rules.md)
- [005 Three-layer SC test strategy](./005-three-layer-sc-test-strategy.md)
- [006 Post-reorganization architecture](./006-post-reorganization-architecture.md)

## Coherence-era decisions

- [ADR-001 Coherence dead-code deletion](../adr/ADR-001-coherence-deadcode-deletion.md)
- [ADR-002 Coherence score versioning](../adr/ADR-002-coherence-score-versioning.md)
- [ADR-003 Coherence alert ledger](../adr/ADR-003-coherence-alert-ledger-v0-v1.md)
- [ADR-004 Circuit breakers](./ADR-004-circuit-breakers.md)
- [ADR-009 Evidence-oriented Coherence orchestration](./ADR-009-evidence-oriented-coherence-orchestration.md)

> Historical numbering contains collisions between foundational `004-...` and later `ADR-004`. Do not infer chronology from the number alone. New decisions continue the v3 canon sequence.

## C2Pro v3 / Project Intelligence spine

- [ADR-013 Typed Graph Contract & Runtime Correctness](./ADR-013-typed-graph-contract-runtime-correctness.md)
- [ADR-014 Project State Model](./ADR-014-project-state-model.md)
- [ADR-015 Temporal Intelligence Layer](./ADR-015-temporal-intelligence-layer.md)
- [ADR-016 Semantic Diff & Change-Impact Engine](./ADR-016-semantic-diff-change-impact-engine.md)
- [ADR-017 ProjectGraph Orchestration](./ADR-017-projectgraph-two-tier-orchestration.md)
- [ADR-018 Project Health Engine](./ADR-018-project-health-engine.md)
- [ADR-019 Alert Correlation & Action Lifecycle](./ADR-019-alert-correlation-action-lifecycle.md)
- [ADR-020 HITL Workflow System](./ADR-020-hitl-workflow-system.md)
- [ADR-021 Read-Model & Briefing Projection](./ADR-021-read-model-briefing-projection.md)
- [ADR-022 Contract Clarity Findings](./ADR-022-contract-clarity-findings.md)
- [ADR-023 Agentic Coherence Architecture](./ADR-023-agentic-coherence-architecture.md)
- [ADR-024 Single-Document Activation](./ADR-024-single-document-activation.md)
- [ADR-025 Canonical Project Controls / WBS Backbone](./ADR-025-canonical-project-controls-wbs-backbone.md)
- [ADR-026 Trusted-State Commit Boundary](./ADR-026-trusted-state-commit-boundary.md)
- [ADR-027 Processing Authority & Checkpoint-Lineage Fencing](./ADR-027-processing-authority-checkpoint-lineage.md)
- [ADR-028 Production Qualification & Composite Runtime Identity](./ADR-028-production-qualification-composite-runtime.md)
- [ADR-029 WBS Governance — Implicit Root, Stable Identity, Governed Baselines](./ADR-029-wbs-governance-identity-baseline.md) *(partially supersedes ADR-025)*
- [ADR-030 WBS Intelligence — Immutable Proposals, Dimension-Level Qualification, Domain Profiles](./ADR-030-wbs-intelligence-proposals-qualification-profiles.md) *(conforms to ADR-029; Amendment 1: PC-2b.2 intelligence store)*

## Current critical architecture path

`ADR-013 → ADR-014 → ADR-015 → ADR-016 → ADR-018/024 → ADR-025 → ADR-029 → ADR-030`

Trust and operational correctness cross-cut that path:

`ADR-020 → ADR-026 → ADR-027 → ADR-028`

## Interpretation rules

- **Accepted design != deployed != PROD_VALIDATED.**
- Realization/deployment/prod-validation fields belong to Product Control.
- A merged implementation may satisfy an ADR without proving production user value.
- If implementation intentionally contradicts an accepted ADR, amend/supersede the ADR explicitly.
- Operational CI tuning does not require an ADR unless it changes a durable authority/security boundary.

## Product red lines

- one project → one canonical hierarchical WBS;
- Unknown/null is never coerced to zero/green;
- Health, Coherence and Alerts are different signals;
- pending/rejected AI output cannot mutate trusted canonical state;
- stale processing/checkpoint lineage cannot become current;
- production evidence cannot self-promote Product Control.

## Related

- [Current technical baseline](../C2PRO_TECHNICAL_BASELINE_2026-10-01.md)
- [Architecture index](../../ARCHITECTURE_INDEX.md)
- [Documentation authority](../../DOCUMENTATION_AUTHORITY.md)
- [Archived architecture](../../archive/architecture/)
