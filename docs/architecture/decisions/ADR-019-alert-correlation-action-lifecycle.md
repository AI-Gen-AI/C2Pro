# ADR-019: Alert Correlation & Action Lifecycle

**Status:** Accepted — P2 (Differentiation) · C2Pro v3.0 canon
**Date:** 2026-06-07
**Deciders:** Jesús Camacho (VP Engineering)
**Basis:** Multi-model arbitration — DeepSeek / Codex / Claude / Gemini v3.0 ADR blueprints + Architecture Challenger verdict.
**Related:** ADR-016 (change impact), ADR-018 (health/coherence project surface), ADR-020 (HITL), ADR-025 (canonical WBS Project Controls backbone). Shares the **"Action & Review" bounded context** and org/role model with ADR-020.

## 2026-10-04 Amendment — Canonical finding identity and durable Alert reconciliation (GOVERNING)

**Status:** Accepted product/architecture decision, 2026-10-04.
**Implementation specification:** `docs/product/b1-canonical-alert-reconciliation-spec-v1-1.md`
**B1 v1.1 merged baseline:** `8efa2af4eec1d29652d853c9c916b0626b895b01` (#828 + #829 + #834 + C3b-1/#838 merged on top of C3a).
**Related:** ADR-009 governing HITL/scoring amendment, ADR-020, ADR-026, ADR-027, #829 (merged evidence addressability), #834 (merged reviewer integrity/durability), #838 (merged C3b-1 materialization), #831 (remaining C3b).

**Implementation state at this amendment.** PR #828 has landed stable same-path Coherence Alert reconciliation: versioned legacy fingerprint recomputation, trusted-current provenance checks, duplicate collapse, preservation of ACKNOWLEDGED/DISMISSED human state, RESOLVED re-open behavior, OPEN-only auto-resolution, tenant/type scoping, and transaction-scoped project advisory locking. PR #829 has landed detector-provenance exposure in the Alerts API/Review Center and verified-only Evidence Viewer deep-links. PR #834 has landed complete review-state persistence, reviewer-attached evidence, fresh-session durability checks and fail-closed bulk-review integrity. This amendment must not cause those capabilities to be reimplemented. It governs the remaining atomicity, cross-revision evidence-basis semantics, legacy ambiguity, disposition-to-score integration and the C3b boundary.

### One canonical reconciliation boundary

Coherence owns typed finding detection and canonical scoring. The Alerts bounded context owns durable finding identity, human disposition and reconciliation. There is exactly one canonical Alert reconciliation boundary; temporal/C3b materialization must call the same boundary rather than introduce parallel semantics.

The reconciler does not compute Coherence, grant trust, or commit its own transaction. The caller supplies trusted authority and owns commit/rollback.

### Finding family vs observation identity

A durable issue has two distinct identities:

- **finding family identity** — the semantic issue family, stable across unchanged reevaluation and, when strong semantic anchors prove continuity, across trusted revisions;
- **observation identity** — the exact trusted evidence basis for the current detected observation.

A revision UUID is evidence/provenance, not automatically family identity. Family identity is versioned and is derived from producer/type, rule code, an explicit rule-identity version, canonical category, trigger and stable semantic anchors. Title, message, severity wording and other presentation text are forbidden family-identity inputs.

A new authoritative revision is a new review basis by default. B1 does not infer that a human disposition remains valid merely because the family remains stable. Any future cross-revision equivalence shortcut requires an explicit, testable equivalence rule.

### Human state is evidence-basis-bound and non-destructive

Machine-owned detection fields may refresh. Human evidence, reviewer, rationale, disposition and history may not be silently erased by reevaluation.

A human disposition records the observation basis that was reviewed.

- same family + same observation preserves the disposition;
- same family + new authoritative observation preserves history but revalidates basis-sensitive disposition;
- a resolved family that genuinely reappears reuses the durable family row/id when continuity is provable and records a reopen transition;
- an incompatible semantic identity/anchor change creates explicit successor/supersession lineage and does not inherit prior human disposition silently.

### Atomicity, scoring order and concurrency

Canonical Coherence persistence and canonical Alert reconciliation must not produce a durable split-brain state.

Typed detector findings are reconciled against durable human dispositions before the canonical score is finalized. The reconciler does not score; it returns the disposition effect needed by the caller to derive the scoring-eligible finding set under ADR-009.

Therefore:

- acknowledged / accepted variance / explained conflict remain scoring-eligible and preserve raw Coherence impact;
- a validated false positive may be excluded before canonical score finalization;
- resolve without changed trusted evidence does not remove documentary score impact.

The owning canonical path persists the resulting Alert state and Coherence result/projection in one transaction. If reconciliation or final score persistence fails, neither becomes newly durable.

Reconciliation remains serialized per tenant/project, deduplicated within one run and idempotent under retry. Lock timeout/failure is fail-closed and retriable, never a fallback to destructive replacement.

### Legacy identity ambiguity fails closed

Versioned fingerprint recomputation is compatibility support, not authority to choose among ambiguous legacy rows. A legacy row may be adopted automatically only when one-to-one semantic ownership is provable. If multiple historical rows could own the same family, destructive reconciliation stops with an explicit legacy-identity conflict until remediation; the implementation must not silently pick the newest/first row or merge reviewer histories.

### Scoring is not user approval

This amendment does not alter ADR-009 scoring semantics. Acknowledge / accepted variance / explained conflict does not improve raw Coherence. Only ADR-009 epistemic changes — false positive, corrected data/extraction, changed trusted evidence, or supersession — may remove/replace the relevant finding and drive recalculation.

B1 also consumes the already-shipped #714 **trusted vs projected Coherence** authority model. The trusted score remains the solid canonical score from trusted evidence. Any hypothetical score resulting from pending score-affecting candidates is provisional/projected, uses the same scorer and `score_version`, is rendered as non-approved, and cannot replace the trusted score or official report value. A pending Alert review that merely acknowledges/confirms an evidence-backed discrepancy does not create a better projection; the discrepancy already belongs in documentary Coherence. Null/unknown remains null and is never converted to 0 or default 100.

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

[executed on device: vmi3226522 (f25c3740-ed77-4837-8d92-d0f9660f9596)]

[executed on device: vmi3226522 (f25c3740-ed77-4837-8d92-d0f9660f9596)]