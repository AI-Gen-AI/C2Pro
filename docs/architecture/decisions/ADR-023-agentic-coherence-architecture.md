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

**Router is deterministic-first.** Where routing can be derived from document types / declared specialist capabilities, the Router uses deterministic dispatch; an LLM router is used only where classification genuinely needs it.

**Validators enforce deterministic invariants.** The Input and Output Validator agents assert **deterministic** invariants (schema/contract conformance, ADR-009 honesty rules — null-not-zero, monotonicity, guardrail respected, evidence-traceability). LLM critique **may supplement** them but is **never the sole honesty gate**.

**Model routing.** Deterministic rules first; LLM assist second. Orchestration/critique on Claude; high-throughput specialist extraction + structured function-calling may use the **Hermes LLM family**. Hermes is a **candidate implementation behind the specialist boundary — not an architectural dependency**; a specialist may use any model, or none. Model choice lives behind the specialist contract, per `core/ai/model_router`, and is cost-governed.

**Scoring.** Exactly one canonical aggregator, faithful to the **ADR-009 2026-08-16 governing amendment**: scoring is **graduated, monotonic, and calibratable** — a critical conflict pushes its dimension clearly into a poor/critical band and can never *improve* the score, but **"critical" ≠ automatic zero** (C2Pro detects incoherence, not falsehood). `conflicting_evidence` is a state, decoupled from a numeric zero; detection-certainty scales the *penalty* (higher certainty ⇒ stronger penalty — the current inverted `× certainty` is corrected); a **global critical-risk guardrail** keeps the headline from reading "healthy" with an open critical. #532's ceilings remain an **interim guard** until the unified model passes tests + shadow + calibration. Null-not-zero (§2.1) preserved. The HITL lifecycle (incl. `accepted_variance` / `explained_conflict`) affects subsequent scoring **without erasing** the original detection/evidence/history.

## Alternatives considered

| Option | Verdict | Reason |
|---|---|---|
| Keep exp-baseline scorer + #532 caps | Rejected | Not ADR-009; caps mask a wrong model. |
| Big-bang agent-mesh rewrite now | Rejected | ADR-017 deferred it; high risk, no incremental path, no working substrate to migrate from. |
| Leave Tier-2 off, keep patching `/evaluate` | Rejected | Perpetuates the "starved" engine the audit + ADR-017 both condemn. |
| **Finish/cut-over Tier-2, then agentize incrementally behind a flag** | **Chosen** | Ships real cross-doc value first; agentizes a *working* graph node-by-node with shadow parity; flag-revertible per ADR-017. |

## Phased plan (architecture-first, each phase independently shippable + canaried)

- **Phase 0 — Blueprint (this ADR + audit).** Done.
- **Phase 1 — Make the ratified engine real.** (a) Implement the **single canonical graduated scorer** per the ADR-009 2026-08-16 amendment (conflict ≠ 0; corrected detection-certainty; global critical-risk guardrail; #532 ceilings as interim guard, not final calibration); **converge the four coexisting scorers to one** authoritative path consumed identically by `/evaluate`, persistence, dashboard headline, category scores, audit export, Tier-2, and alerts; define the HITL lifecycle effect on scoring (accepted/explained variance relaxes impact without erasing evidence). (b) Implement **genuine first-class cross-document comparators** (not aggregation): Contract total ↔ Budget total · Contract milestones/deadline ↔ Schedule · Scope ↔ WBS · WBS ↔ Budget · WBS ↔ BOM · BOM ↔ Budget — each producing **traceable evidence** feeding the canonical scoring + alert system. (c) Build the **real multi-metric calibration gate** (critical precision / false-positive-rate / recall, expert-golden comparison, score↔expert correlation, correct null behaviour, drift; MAE as *one* metric, not the sole truth) + **shadow mode**; **do NOT enable `feature_v3_project_graph`** until (b) + the gate are ready, then use the ADR-017 **canary** (10→50→100%), never a direct flip. *Deliverable: the pilot surfaces multiple defensible findings; the flagged dimension scores materially worse — via the canonical model, not a forced constant.* No agent refactor yet.
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
