# ADR-023: Agentic Coherence Architecture — Router + Specialist + Validator agents on the Tier-2 spine

**Status:** Proposed
**Date:** 2026-08-16
**Deciders:** Jesús Camacho (VP Engineering) — direction; Fable (Orchestrator) — drafting
**Basis:** `docs/audits/ADR_FAITHFULNESS_AUDIT_2026-08-16.md`; VP direction (specialist + router agents, input/output validation agents, Hermes LLM family, extensibility for new markets); architecture-first sequencing.
**Related / builds on:** ADR-009 (evidence-aware scoring — to be made faithful), ADR-013 (typed graph), ADR-014 (project state), ADR-017 (two-tier orchestration — the substrate this evolves), ADR-018 (health), ADR-019 (alerts). Anonymizer/N2 (PII) for the golden-corpus track.

## Context

The faithfulness audit found: (1) ADR-017's Tier-2 ProjectGraph is **built, wired, and flag-gated OFF**, so the user path runs the "starved" per-document coherence ADR-017 was written to replace; (2) even Tier-2 currently **aggregates** per-document findings rather than **comparing across** documents; (3) the live scorer is an exp-baseline model, **not** ADR-009 §6's state-machine + conflict-penalty aggregator (the pilot score-inversion; #532 was a symptom cap).

The VP direction is to evolve the engine into a **modular multi-agent system** — **router agents** that derive the flow, **specialist agents** per domain, and **validation agents** on both ends — so new checks / markets are added by *registering an agent*, not editing the graph. ADR-017 explicitly **deferred** exactly this ("supervisor-worker / agent-mesh — premature before the temporal spine exists"). The spine now exists; this ADR sequences the evolution **without a big-bang rewrite** and **without ever fabricating a score** (ADR-009 §2.1 invariant is inviolable).

## Decision

Adopt an **agentic topology layered on the ADR-017 Tier-2 substrate**, reached in phases. Target components:

```
ProjectGraph (Tier-2, ADR-017 — the async substrate)
  └─ ROUTER agent(s)         classify project/docs/evidence → derive which specialists run
       ├─ SPECIALIST agents  one per domain (typed contract: evidence in → typed findings+coverage out)
       │    Budget · Time/Schedule · Scope/WBS · Legal · Technical · Quality · Cross-Document
       └─ AGGREGATOR         ADR-009-faithful: state machine + conflict penalty → score (null-safe)
  ── VALIDATOR agents (first-class gates) ──
     Input Validator   docs valid/complete enough to audit? (gate BEFORE analysis)
     Output Validator  score+alerts defensible & ADR-009-consistent? (gate BEFORE persist/present) ← honesty gate
```

**Agent contract (the extensibility keystone).** Every specialist implements one typed interface: `evaluate(evidence_bundle) -> SpecialistResult{ findings[], coverage, applicability, reliability }`. Specialists are **stateless, side-effect-free, and independently testable**; the router dispatches by capability. Adding a market/feature = **register a new specialist** with the router; existing specialists and the aggregator are untouched. This is what makes "expand by adding agents, not editing code" real — but only because the contract + router are invested in first.

**Model routing.** Deterministic rules first; LLM assist second. Orchestration/critique/output-validation on Claude; high-throughput specialist extraction + structured function-calling on the **Hermes LLM family** (candidate — validated per specialist, cost-governed). Model choice lives behind the specialist boundary, per `core/ai/model_router`.

**Scoring.** Exactly one aggregator, **ADR-009-faithful**: a critical cross-document conflict transitions the category to `conflicting_evidence` with a deterministic hard penalty (§6), so the flagged dimension is worst by construction (not by the #532 cap, which is folded in / retired). Null-not-zero (§2.1) preserved.

## Alternatives considered

| Option | Verdict | Reason |
|---|---|---|
| Keep exp-baseline scorer + #532 caps | Rejected | Not ADR-009; caps mask a wrong model. |
| Big-bang agent-mesh rewrite now | Rejected | ADR-017 deferred it; high risk, no incremental path, no working substrate to migrate from. |
| Leave Tier-2 off, keep patching `/evaluate` | Rejected | Perpetuates the "starved" engine the audit + ADR-017 both condemn. |
| **Finish/cut-over Tier-2, then agentize incrementally behind a flag** | **Chosen** | Ships real cross-doc value first; agentizes a *working* graph node-by-node with shadow parity; flag-revertible per ADR-017. |

## Phased plan (architecture-first, each phase independently shippable + canaried)

- **Phase 0 — Blueprint (this ADR + audit).** Done.
- **Phase 1 — Make the ratified engine real.** (a) Implement the ADR-009 §6 state-machine + conflict-penalty aggregator as the authoritative scorer; fold in #532 caps; converge the three scorers to one. (b) Add genuine cross-document comparators (the `DET-CRS-*` family) fed assembled cross-doc data. (c) Finish + **canary cut-over Tier-2** (`feature_v3_project_graph`) with the ADR-009 §8.3 MAE guard real (not stubbed). *Deliverable: the pilot surfaces multiple defensible findings; flagged category scores worst faithfully.* No agent refactor yet.
- **Phase 2 — Introduce the agent contract.** Define `SpecialistResult` + the Router; extract **2 pilot specialists (Budget, Time)** + Router behind the contract, behind a flag, **shadow vs the Tier-2 nodes**; assert parity. *Deliverable: proof the contract works with zero behaviour change.*
- **Phase 3 — Migrate + validate.** Move remaining categories to specialists; add **Input + Output Validator agents** (the honesty gates); introduce **Hermes** for specialist extraction/function-calling with cost governance (throttle/DLQ/concurrency caps per ADR-017).
- **Phase 4 — WBS + cross-doc depth.** **WBS core** (prerequisite feature, reviewed/built separately) as a Scope/WBS specialist; WBS↔BOM and contract↔schedule comparators as first-class specialists.
- **Parallel track (separately planned, own sessions) — Golden corpus.** Anonymized (N2/PII) Abengoa real projects → calibration dataset + the MAE cutover guard + specialist tuning. Uses other models/workers. **Out of scope for the engine phases above.**

## Scope
Agent contract + router; ADR-009-faithful aggregator; cross-document comparators; Tier-2 finish + canary; Input/Output validator agents; Hermes integration behind the specialist boundary with cost governance.

## Out of scope
Abengoa data ingestion/training (separate track); the frontend **budget planned-vs-current-vs-modifications** data-model + UI (parallel product track — required for `DET-BUD-OVERRUN` to have real `current` data, tracked separately); Tier-2 parallelism (serial first per ADR-017).

## Success criteria
1. Pilot surfaces **multiple defensible findings** across dimensions (not 1).
2. A dimension with an open **critical** scores **worst** via the ADR-009 state transition (not via a post-hoc cap).
3. **Zero false findings** on a known-consistent triplet (honesty; ADR-009 §2.1 preserved).
4. A **new specialist can be added without modifying** existing specialists or the aggregator.
5. Cut-over is **canaried (10→50→100%)** and **flag-revertible** with zero data loss (ADR-017 precedent); MAE guard is real.

## Consequences
**Positive:** the headline feature (real cross-doc, LLM-on) goes live via the ratified path; scoring becomes ADR-009-honest; the engine becomes extensible by registration; the honesty gate is explicit.
**Negative / to govern:** two execution paths during migration (flagged); a strict agent contract is mandatory; Hermes/LLM cost must be governed; real test surface requires the golden corpus (parallel track).
