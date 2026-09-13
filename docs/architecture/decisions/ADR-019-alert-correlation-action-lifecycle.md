# ADR-019: Alert Correlation & Action Lifecycle

**Status:** Accepted — P2 (Differentiation) · C2Pro v3.0 canon
**Date:** 2026-06-07
**Deciders:** Jesús Camacho (VP Engineering)
**Basis:** Multi-model arbitration — DeepSeek / Codex / Claude / Gemini v3.0 ADR blueprints + Architecture Challenger verdict.
**Related:** ADR-016 (change impact), ADR-018 (health/coherence project surface), ADR-020 (HITL), ADR-025 (canonical WBS Project Controls backbone). Shares the **"Action & Review" bounded context** and org/role model with ADR-020.

## 2026-09-13 Amendment — Alert category taxonomy and Project Controls attachment (GOVERNING)

**Status:** Accepted product decision, 2026-09-13.

Alerts are already a product capability and must remain aligned with the same six project dimensions used by the user-facing project surface:

- `SCOPE`
- `BUDGET`
- `TIME`
- `TECHNICAL`
- `LEGAL`
- `QUALITY`

### Category and trigger are separate

The alert **category** answers *which project dimension is affected*. The alert **trigger** answers *why the alert exists*.

Typical triggers include, without becoming a second top-level taxonomy:

- `missing_evidence`;
- `deadline`;
- `deviation`;
- `contradiction`;
- `material_change`.

Examples:

- a penalized delivery milestone with no confirming delivery evidence is primarily `TIME`, potentially with a linked legal consequence;
- a forecast above the currently approved budget is `BUDGET`;
- conflicting technical requirements are `TECHNICAL` even when the trigger is `contradiction`.

### Expected vs observed

Where applicable, an alert should retain an auditable comparison:

- expected state;
- observed state;
- source evidence for the expectation;
- source evidence for the observation;
- severity/status and temporal evolution.

Alerts may open, update, escalate, resolve or be dismissed as new project evidence arrives. Re-running an unchanged input must not fabricate a new alert.

### WBS attachment

Where an alert is specific to a work package, milestone, budget package or procurement package, it should reference the corresponding node in the **single canonical hierarchical WBS** defined by ADR-025. Truly cross-cutting findings remain project-scoped.

Stakeholder/RACI relationships linked to that WBS node become the future routing seam for ownership, review and governed communications. External communication remains HITL-governed.

### Priority distinction

This amendment does **not** automatically promote the entire Action/HITL workflow to P1. Alert visibility and six-dimension integration are cross-cutting product requirements now; full ActionItem ownership/automation/HITL remains sequenced separately according to evidence of user value.

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

> **Compatibility note:** the historical `impact_area` field above predates the governing six-dimension product taxonomy. Implementations should migrate/adapter-map user-facing alert category to `SCOPE/BUDGET/TIME/TECHNICAL/LEGAL/QUALITY` rather than expose the old `contract/schedule/cost/risk/governance` list as the primary product taxonomy.

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
ADR-016, ADR-018, ADR-025.

## Success criteria
- One contract revision generates **one** change-impact `ActionItem`, not 50 findings.
- Top-N daily ranking is stable across re-runs (dedupe/suppression verified).
- Critical items without evidence are withheld (`needs_review`), per INV-1.
- User-facing alert category is one of `SCOPE/BUDGET/TIME/TECHNICAL/LEGAL/QUALITY`; trigger is a separate field/concept.
- Work-package-specific alerts can resolve to the canonical WBS node and evidence that caused them.

## Implementation note
**Month 6**, gated behind the Month-3 pilot signal. Launches scoped to the Contract-Manager persona alongside ADR-020.