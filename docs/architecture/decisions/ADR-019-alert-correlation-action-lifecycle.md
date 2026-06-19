# ADR-019: Alert Correlation & Action Lifecycle

**Status:** Accepted — P2 (Differentiation) · C2Pro v3.0 canon
**Date:** 2026-06-07
**Deciders:** Jesús Camacho (VP Engineering)
**Basis:** Multi-model arbitration — DeepSeek / Codex / Claude / Gemini v3.0 ADR blueprints + Architecture Challenger verdict.
**Related:** ADR-016 (change impact), ADR-018 (health deltas), ADR-020 (HITL). Shares the **"Action & Review" bounded context** and org/role model with ADR-020.

## Context

Alerts today are reactive, document-centric, uncorrelated, and impact-free. Ten document inconsistencies on the same milestone become ten alerts instead of one decision. Information overload is the named adoption killer.

## Decision

Transform findings → a small number of correlated, owned **`ActionItem`s** (term chosen deliberately over the blueprints' "Decision object", which the Challenger flagged as premature abstraction).

- **Correlation (start simple):** two rules first — *group-by-revision* (all changes from one revision → one change-impact item) and *group-by-shared-entity* (findings on the same milestone/clause/WBS node → one item). Causal-chain correlation is a later refinement.
- **Prioritization:** rank by `severity × confidence × impact`; dedupe across re-runs; suppress unchanged items and items with a pending change order.
- **Required fields:**
  ```python
  class ActionItem(BaseModel):
      severity: Literal["info","low","medium","high","critical"]
      confidence: float
      impact_area: list[Literal["contract","schedule","cost","risk","governance"]]
      affected_objects: list[ProjectObjectRef]
      evidence_refs: list[EvidenceRef]        # INV-1 — critical items gated
      recommended_action: str
      owner_stakeholder_id: UUID | None        # → reservation seam (ADR-014)
      due_at: datetime | None
      escalation_path: list[UUID]              # stakeholder refs
      correlation_group: UUID
      status: Literal["open","in_review","accepted","rejected","resolved","suppressed"]
  ```
- **Org/role model:** a **minimal** role model is built here (owners/escalation need it). This is the shared seam the future Stakeholder-Intelligence domain extends (ADR-014 reservation).

## Alternatives considered

| Option | Verdict | Reason |
|---|---|---|
| `ActionItem` + 2 correlation rules to start | **Chosen** | Concrete; reduces noise immediately; avoids premature taxonomy. |
| "Decision object" abstraction up front | **Rejected** | Premature; invent the concept only after real UX (Challenger). |
| Merge entirely with HITL into one ADR | **Rejected** | Correlation (engine) and human review (workflow) have distinct state; kept as two ADRs **bound under one context** with a shared lifecycle and **both scoped to one persona/queue at launch**. |

## Consequences

**Positive:** alerts become accountable actions; enables the daily-use loop and the Morning Briefing.
**Negative:** correlation quality depends on entity resolution (ADR-016) being solid; owner auto-assignment depends on org-model maturity (start manual); suppression rules must be transparent.

## Scope
`ActionItem` model; 2 correlation rules; severity×confidence×impact ranking; dedupe/suppress; minimal org/role model; INV-1 gating on critical items.

## Out of scope
The "Decision object" abstraction; full correlation taxonomy; owner auto-assignment before org model matures; multi-persona breadth (see ADR-020).

## Dependencies
ADR-016, ADR-018.

## Success criteria
- One contract revision generates **one** change-impact `ActionItem`, not 50 findings.
- Top-N daily ranking is stable across re-runs (dedupe/suppression verified).
- Critical items without evidence are withheld (`needs_review`), per INV-1.

## Implementation note
**Month 6**, gated behind the Month-3 pilot signal. Launches scoped to the Contract-Manager persona alongside ADR-020.
