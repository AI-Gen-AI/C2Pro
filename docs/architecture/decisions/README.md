# Architecture Decisions

This directory contains durable architectural decisions for the active C2Pro platform.

An ADR records a **decision and its consequences**. It is not a live task board and does not prove deployment or production validation.

## Foundation set

- [001 Modular monolith architecture](./001-modular-monolith-architecture.md)
- [002 Supabase for MVP](./002-supabase-for-mvp.md)
- [003 AI architecture](./003-ai-architecture.md)
- [004 Frontend layer rules](./004-frontend-layer-rules.md)
- [005 Three-layer SC test strategy](./005-three-layer-sc-test-strategy.md)
- [006 Post-reorganization architecture](./006-post-reorganization-architecture.md)

## Coherence and resilience

- [ADR-004 Circuit breakers](./ADR-004-circuit-breakers.md)
- [ADR-009 Evidence-oriented Coherence orchestration](./ADR-009-evidence-oriented-coherence-orchestration.md)

> ADR-010/011/012 remain reserved/in-flight historical references where existing documents cite them; the v3 architecture canon intentionally begins at ADR-013.

## C2Pro v3 project-intelligence canon

- [ADR-013 Typed Graph Contract & Runtime Correctness](./ADR-013-typed-graph-contract-runtime-correctness.md)
- [ADR-014 Project State Model](./ADR-014-project-state-model.md)
- [ADR-015 Temporal Intelligence Layer](./ADR-015-temporal-intelligence-layer.md)
- [ADR-016 Semantic Diff & Change Impact](./ADR-016-semantic-diff-change-impact-engine.md)
- [ADR-017 ProjectGraph Two-Tier Orchestration](./ADR-017-projectgraph-two-tier-orchestration.md)
- [ADR-018 Project Health Engine](./ADR-018-project-health-engine.md)
- [ADR-019 Alert Correlation & Action Lifecycle](./ADR-019-alert-correlation-action-lifecycle.md)
- [ADR-020 HITL Workflow System](./ADR-020-hitl-workflow-system.md)
- [ADR-021 Read-Model & Briefing Projection](./ADR-021-read-model-briefing-projection.md)
- [ADR-022 Contract Clarity Findings](./ADR-022-contract-clarity-findings.md)
- [ADR-023 Agentic Coherence Architecture](./ADR-023-agentic-coherence-architecture.md)
- [ADR-024 Single-Document Activation](./ADR-024-single-document-activation.md)
- [ADR-025 Canonical Project Controls WBS Backbone](./ADR-025-canonical-project-controls-wbs-backbone.md)
- [ADR-026 Trusted-State Commit & Exact Approval Binding](./ADR-026-trusted-state-commit-and-approval-binding.md)

## Cross-cutting invariants

### Project intelligence

The project is the primary intelligence boundary. Documents are evidence inputs.

### Canonical Project Controls

One project owns one canonical hierarchical WBS. Domain planes attach to that tree or explicitly project-level scope.

### Evidence truthfulness

Unknown/insufficient evidence remains unknown. No blind unknown-to-zero conversion or fabricated evidence locator is allowed.

### Trust boundary

`persisted != trusted`.

Pending/rejected candidates cannot mutate canonical ProjectGraph/Health/Coherence. Consequential approval binds the exact reviewed candidate/version/hash and promotes trusted state idempotently.

### Lifecycle truthfulness

An ADR being accepted, code being merged, a deployment existing, and a production journey being validated are distinct claims.

## Current implementation note

As of 2026-10-01 audit baseline:

- ADR-026/#714 implementation is landed.
- the #715 production-acceptance harness implementation is landed.
- #715 itself remains open pending actual production qualification.
- machine Product Control owns newer lifecycle reconciliation.

## Rejected/prevented patterns

- Document as the sole unit of intelligence.
- Parallel independent WBS authorities.
- Pending AI output mutating official state.
- Generic “approve latest” semantics.
- Fabricated evidence locators.
- Agent mesh as prerequisite for core product value.
- Treating a merged harness as production proof.

## Related

- [Current TDD](../C2PRO_TECHNICAL_DESIGN_DOCUMENT_v4_2.md)
- [Architecture index](../../ARCHITECTURE_INDEX.md)
- [Documentation index](../../README.md)
- [Product Control](../../product/00-c2pro-master-product-control-v1.md)
