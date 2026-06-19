# ADR-016: Semantic Diff & Change-Impact Engine

**Status:** Accepted — P0→P1 (Core Product / the wedge) · C2Pro v3.0 canon
**Date:** 2026-06-07
**Deciders:** Jesús Camacho (VP Engineering)
**Basis:** Multi-model arbitration — DeepSeek / Codex / Claude / Gemini v3.0 ADR blueprints + Architecture Challenger verdict.
**Related:** ADR-014 (entities), ADR-015 (revisions), ADR-013 INV-1 (evidence gate); impact propagation executes inside ADR-017.

## Context

Revisions are not compared. In EPC the value is almost entirely in the **delta** — "what changed between Rev C and Rev D of the contract, and what does it conflict with across the schedule and budget." This object does not exist today. Every audit names the **Change-Impact Report as the strongest, unowned market wedge.**

## Decision

A layered engine producing a typed `ChangeSet`, evidence-gated per INV-1:

- **Layer 1 — Structural diff** (deterministic, cheap, always-on): clause / row / line-item add·remove·modify, keyed on **stable anchors** (`clause_id`, `cost_code`, `activity_id`). Handles contracts, schedules, and budgets via keyed structural comparison — **no LLM**.
- **Layer 2 — Semantic diff** (LLM, gated, **modified-pairs only**): classifies the *meaning* and severity of a change ("penalty cap 5%→10%", "milestone pushed 12 days"). Cost-controlled by never sending whole documents.
- **Layer 3 — Cross-document impact**: propagates each change across the entity graph (Clause → WBS → Budget → Obligation). **Executes inside ADR-017 (ProjectGraph)**, not here.

**Scope of change types:** contracts (clause/obligation/deadline/penalty/payment/risk-allocation), schedules (milestone/duration/dependency/float/baseline), budgets (line/quantity/unit-price/contingency), RFIs (scope-changing clarifications), change orders (cost/time/scope/approval).

```python
class SemanticChange(BaseModel):
    object_type: Literal["clause","milestone","budget_item","rfi","change_order"]
    change_type: Literal["added","removed","modified","superseded","conflict_introduced"]
    before: dict | None
    after: dict | None
    semantic_summary: str
    severity: Literal["info","low","medium","high","critical"]
    confidence: float
    match_confidence: float          # anchor-resolution confidence (see below)
    evidence_refs: list[EvidenceRef] # INV-1
```

**Output — the Change-Impact Report** (the product's signature artifact): *what changed · why it matters · what it conflicts with · impact estimate (honest null when inputs missing) · confidence · evidence · recommended action · HITL routing.*

### Make-or-break: anchor / entity-ID stability across revisions
The hardest, most underestimated dependency (named by both Claude and the Challenger): semantic diff is worthless if entity identity cannot be maintained across revisions. **This ADR's scope explicitly includes an anchor-resolution strategy:** deterministic keys first (clause numbers, cost codes, activity IDs), confidence-scored fuzzy fallback second, with a `match_confidence` on every change. **No change ships above the `weak` evidence tier without a resolved anchor.** If parsers cannot emit stable anchors for a document type, that type is deferred — not faked.

## Alternatives considered

| Option | Verdict | Reason |
|---|---|---|
| Layered structural → semantic → impact | **Chosen** | Cost-controlled by construction; structural layer is deterministic and cheap; LLM only on changed pairs. |
| LLM-only diff (whole documents) | **Rejected** | Cost/latency blowout; low precision; no deterministic floor. |
| "Change Intelligence" as a separate ADR | **Rejected** | It is the composition of this ADR's output + ADR-017 impact + ADR-015 delta record — an orphan with no distinct state (Claude). |

## Consequences

**Positive:** converts "scores a document" into "watches a project"; the demo no incumbent (Primavera/Procore/Aconex) can give; feeds Health (ADR-018) and Alerts (ADR-019).
**Negative:** anchor resolution is genuinely hard — budget the engineering there; impact precision must be confidence-banded with honest nulls to avoid fabricated €/day figures.

## Scope
L1 structural diff (contracts first); L2 semantic diff (modified pairs); typed `ChangeSet`; anchor-resolution + `match_confidence`; evidence-gated Change-Impact Report. Extension to schedule/budget/RFI/CO as parsers/anchors allow.

## Out of scope
L3 cross-document impact math (ADR-017); fabricated impact figures without inputs; document types whose parsers cannot emit stable anchors (deferred, not faked).

## Dependencies
ADR-014, ADR-015, INV-1 (ADR-013).

## Success criteria
- A contract revision yields an evidence-cited `ChangeSet` naming specific clause changes and ≥1 cross-document conflict.
- Changes below the anchor-confidence threshold are flagged `needs_review`, never asserted as fact.
- L1 runs with zero LLM cost; L2 cost scales with number of *modified* pairs only.

## Implementation note
Thin-Spine, **Month 2** for L1 (contracts) → first Change-Impact Report. L2 semantic diff gated behind the Month-3 pilot signal.
