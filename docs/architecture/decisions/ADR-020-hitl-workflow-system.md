# ADR-020: HITL Workflow System

**Status:** Accepted — P2 (Differentiation) · C2Pro v3.0 canon
**Date:** 2026-06-07
**Deciders:** Jesús Camacho (VP Engineering)
**Basis:** Multi-model arbitration — DeepSeek / Codex / Claude / Gemini v3.0 ADR blueprints + Architecture Challenger verdict.
**Related:** ADR-017 (graph routes here), ADR-019 (alerts → review). Shares the **"Action & Review" bounded context** with ADR-019.

## Context

HITL is a sound *technical* interrupt (`langgraph.types.interrupt`, resumable via the Postgres checkpointer) but **not an enterprise workflow**: routing thresholds are hardcoded (`confidence < 0.5`), there are no role queues, no audit-grade trail, and — critically — **human corrections do not feed back into AI quality.**

## Decision

Productize the existing interrupt seed, **scoped deliberately narrow at launch.**

- **One queue first — Contract Manager.** Route change-impact findings (ADR-016/019) to a single review queue. Additional persona queues are phased, not v3.0-core.
- **Policy-driven routing:** replace the hardcoded `< 0.5` with per-tenant / per-doc-type confidence·impact policy.
- **Dispute-grade audit trail:** every action records who / when / what changed / why / before-after / evidence seen / model-or-rule version.
- **Active-learning loop (the moat, in v3.0 core):** every human correction becomes a **golden-corpus candidate** (wire `ai_feedback/` → the existing golden harness) and an evaluation/regression case. Track AI-human alignment; re-evaluate when it drops below threshold.
- **Automation boundary:** auto-approve low-risk summarization/retrieval; **require a human** for contractual-risk classification, change-order impact, schedule-baseline changes, cost-exposure estimates, and executive reporting.
- **Operational guard:** alert on the `except → interrupt` fallback path so an infra blip routing everything to humans does not silently bury reviewers.

## Alternatives considered

| Option | Verdict | Reason |
|---|---|---|
| One queue + policy routing + audit + learning loop | **Chosen** | Delivers the moat (learning loop) and enterprise trust without over-building. |
| Full 5-persona suite + multi-step approval chains + SLA matrix at launch | **Rejected for v3.0-core** | "Persona queues, approval chains, audit, active learning, escalation are 4 distinct products" — launching all at once with no volume means no adoption (Challenger). Phased instead. |
| Keep technical interrupt as-is | **Rejected** | Not enterprise-grade; wastes the strongest existing differentiator. |

## Consequences

**Positive:** enterprise-grade trust + a **compounding quality flywheel** (the durable moat); corrections improve the system over time.
**Negative:** requires a minimal role model (shared with ADR-019) and a review UI; active-learning requires golden-corpus write access and regression triggers.

## Scope
Contract-Manager review queue; policy-driven routing; dispute-grade audit trail; HITL-correction → golden-corpus → regression loop; automation-boundary policy; fallback-path alerting.

## Out of scope (phased, not v3.0-core)
The 5-persona queue set; configurable multi-step approval chains; the full SLA-escalation matrix.

## Dependencies
ADR-017, ADR-019.

## Success criteria
- A Contract Manager reviews, corrects, and approves a change-impact in **< 2 minutes**.
- Every human correction generates a golden case in CI; the regression suite grows weekly.
- AI-human alignment is tracked and visible; routing thresholds are tenant-configurable (no hardcoded `0.5`).

## Implementation note
**Month 6**, gated behind the Month-3 pilot. The active-learning loop is in-scope for v3.0-core; persona/approval breadth is explicitly deferred.
