# C2Pro Product Programme — P1 Project Controls Addendum

**Status:** Approved product direction; implementation/master-reconciliation pending
**Date:** 2026-09-13
**Authority:** Supplements `00-c2pro-master-product-control-v1.md` until the machine YAML is reconciled under Issue #619.
**Related:** ADR-018, ADR-019, ADR-025, Issue #619.

## Why this addendum exists

The current machine master still records `PWBS-PROJECT-CONTROLS` as P2 and describes it narrowly as Health-v1 schedule/cost/deliverables/WBS/BOM. The approved product model is broader and more structurally important: Project Controls is the backbone that makes Health, Coherence, Alerts, Change, Reporting, Stakeholders and Procurement operate on one consistent project structure.

This addendum records the approved target without fabricating implementation/deployment state. The canonical YAML remains authoritative for machine lifecycle fields until Issue #619 reconciles it and the parity/git-truth gates pass.

## Product North Star — clarified

C2Pro converts changing project evidence into a verifiable project-control model, continuously compares expected vs observed state, explains what changed, highlights what requires attention, and preserves traceability so the user can decide and act.

The product chain is:

`Evidence -> Project Model -> one canonical WBS -> Budget/Schedule/Stakeholders/Procurement -> six project dimensions -> Health + Coherence Score + Alerts -> What Changed -> Reporting -> Actions/communications`.

Technology choices (LLM, graph, agents, vector stores) are implementation details and must not redefine this product chain.

## Canonical Project Controls invariant

A project has **one canonical hierarchical WBS**.

Engineering, Procurement, Construction, Commissioning and similar structures are branches/elements of that WBS, not independent WBSs.

The hierarchy can contain as many levels as required by the project. C2Pro may extract/propose the WBS from contract, BoQ, schedule and other evidence, but the authoritative baseline is human-reviewed.

Budget, Schedule, Procurement Packages, Stakeholders/RACI, Alerts, Evidence and Changes reference nodes of this WBS, except genuinely cross-cutting project-level facts.

See ADR-025 for the governing decision.

## Six user-facing project dimensions

The same six dimensions organize the user-facing project intelligence:

- Scope
- Budget
- Time
- Technical
- Legal
- Quality

They are shared taxonomy, not six independent subsystems.

### Health / evidence coverage

Question: **Do we have enough evidence to assess this dimension?**

Missing/unsupported evidence renders `Unknown / Insufficient evidence`, never fabricated zero or green.

### Coherence Score

Question: **How consistent is the evidence-backed project state?**

The score is visual and must expose dimensional breakdown and coverage. It is only valid where evidence is reconcilable and must never convert unknown dimensions to zero.

A high Coherence Score can coexist with a Critical Alert; for example, every source can consistently prove that a delivery will be seven days late.

### Alerts

Question: **What concrete situation requires attention?**

Alert category is one of the six dimensions. Trigger is orthogonal (`deadline`, `deviation`, `contradiction`, `missing_evidence`, `material_change`, etc.). Where possible alerts compare expected vs observed and retain evidence for both.

Alerts are living state: new evidence may open, update, escalate, resolve or invalidate them.

## WBS + Budget

A WBS node may carry or reference, as evidence allows:

- baseline budget;
- approved changes;
- current approved budget;
- committed cost;
- actual cost;
- forecast / estimate at completion.

Values may roll up hierarchically only when the data supports that aggregation. Unknown is never coerced into zero.

## WBS + Schedule

WBS defines **what work exists**. Schedule defines **when it occurs**.

Activities and milestones link to WBS nodes but are not automatically WBS nodes themselves. Contractual/penalized milestones and delivery evidence can generate `TIME` alerts when expected and observed state diverge.

## WBS + Stakeholders / RACI

Stakeholders are not only names extracted from a contract. Internal and external stakeholders must progressively map to WBS/work-package scope and, where supported, RACI roles.

This becomes the routing basis for alerts, reviews, procurement follow-up and later governed communications.

## WBS + Procurement

Procurement Packages map to WBS nodes; they never instantiate an alternative procurement WBS.

Target flow:

`WBS -> make/buy/contract -> Procurement Package -> Procurement Plan -> BoQ/Scope -> RFQ -> Bid/Review -> Award -> PO/Contract -> Delivery/Expediting -> Change/Closeout`.

Procurement may be a branch in a project's WBS, but procurement packages may also support nodes under Engineering, Construction or other branches.

## Priority / sequencing change

### P0 / active verticals

Continue the currently authorized user-value work without forcing it to wait for the whole Project Controls suite:

- durable evidence/document lifecycle;
- single-document Health activation;
- temporal `What Changed`;
- Current State / Evolution reporting;
- intelligence/evidence quality.

Candidate branch work does not become canonical realization until merged/deployed/validated according to the control plane.

### P1 — Project Controls Backbone

Promote `PWBS-PROJECT-CONTROLS` from **P2 to P1** in the canonical master reconciliation.

P1 target is **not** “build every Project Controls feature now.” It establishes the structural backbone and prevents incompatible future implementations.

P1 scope:

1. enforce one canonical WBS tree / one logical root per project;
2. define WBS baseline/change governance;
3. link Budget and Schedule to WBS nodes;
4. link Stakeholder/RACI relationships to WBS nodes;
5. integrate Alerts/Evidence/Changes with WBS drill-down;
6. support honest six-dimension Health/Coherence drill-down;
7. define evidence-aware roll-up rules before any parent score aggregation.

### P2 — downstream execution

After the backbone is sufficiently real:

- Procurement Plan / BoQ / RFQ / bid/award workflows;
- richer Action ownership/lifecycle;
- HITL automation;
- governed external communications.

Alert **visibility and integration are not deferred to P2**; they are cross-cutting now. Full Action/HITL automation remains later.

## Explicit non-goals now

Do not make the following prerequisites for product value:

- Neo4j;
- GraphRAG;
- ADR-017 L3 impact breadth;
- native Gantt replacement;
- generic agent mesh;
- automatic external communications without HITL;
- sophisticated score aggregation before evidence/materiality rules are validated.

## Master reconciliation required

Issue #619 is the P1 task to update the canonical machine master safely.

Required reconciliation includes:

- `north_star.full_product` clarification;
- add ADR-025 to the v3 canon/realization matrix;
- map ADR-025 to `PROJECT-CONTROLS`;
- `PWBS-PROJECT-CONTROLS.priority: P1`;
- update Project Controls name/user value/exit gate to the canonical WBS backbone;
- move Project Controls from P2 into P1 roadmap planning;
- keep full Action/HITL automation later while treating alert visibility as cross-cutting;
- preserve Procurement dependency on Project Controls;
- preserve all existing realization/deployment/prod-validation truth unless separately evidenced.

The YAML must be edited first, then the human projection regenerated/reconciled, and parity + git-truth gates must pass before merge.
