# C2Pro Master Product Programme Control — v1

**Status:** Reconciliation snapshot (read-only) · **Date:** 2026-09-13 · **Schema:** v6  
**reconciled_against_main_sha:** `454637863c502f6825d158af551511e0e9996d14` · **deployed_runtime_sha:** `UNVERIFIED`  
**Machine source of truth:** [`validation/product/c2pro-master-product-control-v1.yaml`](../../validation/product/c2pro-master-product-control-v1.yaml)

> This document is the human projection of the machine product-control plane. It does not grant execution authority. Direct `main`, merge and production mutation remain governed outside this document.

> **Control integrity:** edit the YAML first, then regenerate/compare the canonical block with `validation/product/check_control_parity.py`. Branch completion never implies deployment or production validation.

<!-- CANONICAL-CONTROL:START (generated from the YAML by validation/product/check_control_parity.py --emit; do not hand-edit) -->
```control
reconciled_against_main_sha=454637863c502f6825d158af551511e0e9996d14
deployed_runtime_sha=UNVERIFIED
reliability_operability_baseline=CLOSED
product_value_delivered=false
current_product_wedge_id=P0b-single-document-health-activation
coherence.global_authoritative_cutover=NO
legacy_coverage.unmapped_open_legacy_items=0
project_controls.invariant=one_project_one_canonical_hierarchical_wbs
product_semantics.canonical_dimensions=SCOPE,BUDGET,TIME,TECHNICAL,LEGAL,QUALITY
wbs.PWBS-PROJECT-CONTROLS.priority=P1
adr.ADR-018.realization=WIRED
adr.ADR-018.deployment=DEPLOYED
adr.ADR-018.prod_validation=NOT_VALIDATED
adr.ADR-024.realization=WIRED
adr.ADR-024.deployment=NONE
adr.ADR-024.prod_validation=NONE
adr.ADR-025.realization=PARTIAL
adr.ADR-025.deployment=PARTIAL
adr.ADR-025.prod_validation=NONE
p0b.done_digest=b43576250582d032
p0b.invariant_ids=INV-1,INV-UX,INV-COH
p0b.next_slice=P0b-L4-5
p0b.slice.P0b-L4-1.status=DONE
p0b.slice.P0b-L4-2.status=DONE
p0b.slice.P0b-L4-3.status=DONE
p0b.slice.P0b-L4-4.status=DONE
p0b.slice.P0b-L4-5.status=ACTIVE
p0b.residual_ids=P0b-R1-EVIDENCE-GRANULARITY,P0b-R2-CROSS-DATA-CONTRACT
p0b.residual.P0b-R1-EVIDENCE-GRANULARITY.status=RESOLVED
p0b.residual.P0b-R1-EVIDENCE-GRANULARITY.blocking=NON_BLOCKING
p0b.residual.P0b-R2-CROSS-DATA-CONTRACT.status=PLANNED
p0b.residual.P0b-R2-CROSS-DATA-CONTRACT.blocking=NON_BLOCKING
wbs.PWBS-ACT-HEALTH.realization=PARTIAL
wbs.PWBS-ACT-HEALTH.work_status=ACTIVE
wbs.PWBS-COHERENCE-XDOC.realization=PARTIAL
wbs.PWBS-COHERENCE-XDOC.work_status=PLANNED
wbs.PWBS-TEMPORAL-CHANGE.realization=SCAFFOLDED
wbs.PWBS-TEMPORAL-CHANGE.work_status=PLANNED
wbs.PWBS-ALERTS-ACTIONS-HITL.realization=SCAFFOLDED
wbs.PWBS-ALERTS-ACTIONS-HITL.work_status=DEFERRED
wbs.PWBS-PROJECT-CONTROLS.realization=PARTIAL
wbs.PWBS-PROJECT-CONTROLS.work_status=PLANNED
wbs.PWBS-PROCUREMENT.realization=PARTIAL
wbs.PWBS-PROCUREMENT.work_status=PLANNED
wbs.PWBS-EXEC-REPORTING.realization=SCAFFOLDED
wbs.PWBS-EXEC-REPORTING.work_status=DEFERRED
wbs.PWBS-OPS-TRUST.realization=DEPLOYED
wbs.PWBS-OPS-TRUST.work_status=ACTIVE
```
<!-- CANONICAL-CONTROL:END -->

## 1. Product North Star

**C2Pro is continuous, evidence-backed project and procurement intelligence.** The target journey is not merely document analysis: evidence enters a governed project model, that model is structured by **one canonical hierarchical WBS per project**, Project Controls link cost/time/stakeholders/procurement to that structure, and Health / Coherence / Alerts / Change / Reporting turn those facts into decisions.

The invariant introduced by **ADR-025** is explicit:

> **One project → one canonical hierarchical WBS.** Engineering, Procurement, Construction, Commissioning or any other discipline are branches/levels of that WBS, never independent WBSs. Budget, Schedule, Procurement, Stakeholders/RACI, Alerts, Evidence and Changes reference WBS nodes or an explicit project-level scope.

This resolves the earlier ambiguity that could have led the product toward parallel discipline WBS structures.

## 2. Current production truth

Three facts remain deliberately separate:

- `reconciled_against_main_sha = 454637863c502f6825d158af551511e0e9996d14` — repository baseline used for this reconciliation.
- `deployed_runtime_sha = UNVERIFIED` — no inference from `main` or from candidate branches.
- `product_value_delivered = false` — P0a reliability is closed, but the current end-user product wedge is not yet PROD_VALIDATED.

The immediate user-value gap is still **P0b-L4-5**: production evidence that one uploaded document reaches a truthful six-category Health surface with findings, missing evidence and actionable gaps.

## 3. Three product signals that must not be conflated

C2Pro keeps one shared user-facing dimensional vocabulary:

`SCOPE · BUDGET · TIME · TECHNICAL · LEGAL · QUALITY`

But it uses that vocabulary for **three different questions**:

| Signal | Question | Critical semantic rule |
|---|---|---|
| **Health / coverage** | Do we have enough evidence, and what can we truthfully say about project condition? | Missing evidence = `Unknown/null`, never 0/green. |
| **Coherence Score** | Do the reconcilable project documents/state agree with each other? | Coverage must be disclosed; unsupported dimension = Unknown. High coherence does **not** imply healthy project. |
| **Alerts** | What concrete condition needs attention? | `category` is one of the six dimensions; `trigger` is orthogonal (`deadline`, `deviation`, `contradiction`, `missing_evidence`, `material_change`, ...). |

Example: all documents may consistently prove a 7-day delay. **Coherence can be high while TIME carries a critical alert.** This is intentional.

## 4. ADR realization — current truth

The reconciliation adds **ADR-025 Canonical Project Controls / WBS Backbone** without overstating realization.

| ADR | Design | Realization | Deployment | Prod validation | Current meaning |
|---|---|---|---|---|---|
| ADR-009 Coherence | Accepted | PARTIAL | PARTIAL | PARTIAL | v1 historical production evidence; global authoritative v2 cutover not demonstrated. |
| ADR-015 Temporal | Accepted | SCAFFOLDED | PARTIAL | NONE | revision/event/snapshot structures exist; production temporal journey remains incomplete. |
| ADR-016 Change Impact | Accepted | SCAFFOLDED | NONE | NONE | semantic diff contracts exist; end-to-end runtime/user journey not on main. |
| ADR-017 ProjectGraph | Accepted | SCAFFOLDED | BLOCKED | NONE | feature-gated/off for the canonical path. |
| ADR-018 Health | Accepted | WIRED | DEPLOYED | NOT_VALIDATED | Health backend exists; P0b user-visible production validation remains open. |
| ADR-019 Alerts/Actions | Accepted | SCAFFOLDED | NONE | NONE | alert/action domain partial; full correlation/action automation remains later. |
| ADR-020 HITL | Accepted | SCAFFOLDED | PARTIAL | NONE | partial workflow; not yet the live Project Controls action loop. |
| ADR-021 Briefing | Deferred | SCAFFOLDED | NONE | NONE | executive briefing/portfolio stays later. |
| ADR-022 Contract Clarity | Accepted | WIRED | DEPLOYED | NOT_VALIDATED | findings path exists; not user/prod validated. |
| ADR-023 Agentic Coherence | Proposed | DESIGNED | NONE | NONE | roadmap/design only. |
| ADR-024 Single-document Activation | Accepted | WIRED | NONE | NONE | L4-1..L4-4 code/merge complete; L4-5 active. |
| **ADR-025 Canonical Project Controls WBS Backbone** | **Accepted** | **PARTIAL** | **PARTIAL** | **NONE** | nested-set WBS exists, but one-root invariant and cross-domain links are not proven. |

For ADR-025, the repository already has meaningful partial substrate: a project-scoped nested-set `wbs_nodes` hierarchy with parent/depth, date and budget fields. What does **not** yet exist as proven product truth is the complete Project Controls backbone: exactly one canonical root/tree, baseline/change governance, and linked Budget/Schedule/Stakeholder/Procurement/Alert/Evidence/Change semantics.

## 5. Product WBS after #619 reconciliation

| Product WBS | Pri | Realization | Work | What it means now |
|---|---:|---|---|---|
| **PWBS-ACT-HEALTH** | P0b | PARTIAL | ACTIVE | Finish P0b-L4-5 and prove the one-document Health journey in production. |
| **PWBS-COHERENCE-XDOC** | P1 | PARTIAL | PLANNED | Evidence-backed project consistency with six-dimensional breakdown and coverage. |
| **PWBS-TEMPORAL-CHANGE** | P1 | SCAFFOLDED | PLANNED | Durable lineage + What Changed / Change Impact. |
| **PWBS-PROJECT-CONTROLS** | **P1** | **PARTIAL** | **PLANNED** | **One canonical WBS + Budget + Schedule + Stakeholders/RACI + alert/evidence/change drill-down.** |
| PWBS-ALERTS-ACTIONS-HITL | P2 | SCAFFOLDED | DEFERRED | The P2 scope is richer correlation, ownership, Action lifecycle and HITL — **not** basic alert visibility. |
| PWBS-PROCUREMENT | P2 | PARTIAL | PLANNED | Plan → WBS packages → BoQ/RFQ → bid/award → governed updates/comms. |
| PWBS-EXEC-REPORTING | P3 | SCAFFOLDED | DEFERRED | Current-state candidate first; executive briefing/portfolio later. |
| PWBS-OPS-TRUST | P0 | DEPLOYED | ACTIVE | Reliability/trust baseline plus remaining temporal/durability qualification. |

### Project Controls P1 exit gate

The P1 backbone is not complete just because `wbs_nodes` exists. It is complete only when the product can prove:

1. exactly one canonical WBS tree per project;
2. Budget allocations/actuals link to WBS nodes and roll up honestly;
3. Schedule activities/milestones link to WBS nodes — **Schedule is not the WBS**;
4. Stakeholders/RACI link to WBS responsibility/escalation;
5. Procurement packages reference WBS work packages rather than instantiate another WBS;
6. Alerts, Evidence and Changes attach to WBS nodes or explicit project scope;
7. roll-ups preserve Unknown/null and material leaf risks instead of blind averaging;
8. a production user journey proves project → WBS → cost/time/stakeholder/alerts/evidence drill-down.

## 6. P0b vertical contract remains the immediate product gate

`P0b-L4-1` DONE · `L4-2` DONE · `L4-3` DONE · `L4-4` DONE · **`L4-5` ACTIVE**.

**P0b done means production evidence**, not code completion: upload one real document → six categories → `{state, findings, missing_data}` → actionable gap alerts → Health Vector → API → user-visible UI/report. Unknown is null, never fabricated zero/green. Relational Coherence remains unavailable as a headline until enough reconcilable evidence exists.

Residuals remain honest:

- `P0b-R1-EVIDENCE-GRANULARITY` = RESOLVED / NON_BLOCKING.
- `P0b-R2-CROSS-DATA-CONTRACT` = PLANNED / P1 / NON_BLOCKING.

## 7. Active candidate lanes — do not confuse branch work with product truth

Four current lanes may advance the product materially, but none changes canonical lifecycle state until merge/deploy/prod-validation gates are met:

| Lane | Branch | Canonical interpretation |
|---|---|---|
| Durable Documents | `feat/product-durable-document-plane` | Candidate durable R2/revision/delete work; no production claim yet. |
| P0c What Changed | `feat/product-p0c-temporal-intelligence` | Candidate temporal/change user journey; main remains SCAFFOLDED. |
| P0d Reporting | `feat/product-p0d-reporting` | Candidate Current State Report; Evolution still depends on temporal interface. |
| Product Intelligence Quality | `feat/product-intelligence-quality` | Candidate cross-cutting truth/quality improvements. |

This preserves a hard boundary: **candidate ≠ merged ≠ deployed ≠ PROD_VALIDATED**.

## 8. Roadmap — reviewed from end to end

### P0a — Reliability & Operability Baseline — CLOSED

The plumbing exists and is useful, but reliability is not product completion.

### P0b — Single-document Health — ACTIVE / PARTIAL

Immediate objective: prove the first user-value loop in production. A user uploads a contract and receives truthful six-category coverage/findings/gap alerts rather than a wall of technical processing state.

### P0c — What Changed / Temporal Change — CANDIDATE_UNMERGED

The next user question after initial understanding is: **what changed since the previous revision, and what does that affect?** The candidate lane must produce durable lineage and a user-readable change timeline/report, not only domain objects.

### P0d — Current State Reporting — CANDIDATE_UNMERGED

The report should consolidate authoritative source state with honest-null semantics. Current State is useful before full Evolution; Evolution becomes real once the temporal/change interface exists.

### P1 — Project Controls Backbone + Coherence + alert visibility — PLANNED

This is now the structural priority after/alongside the active P0 verticals. It turns C2Pro from a document-intelligence surface into a **project-management intelligence system**:

`Evidence → Project model → ONE WBS → Budget / Schedule / Stakeholders / Procurement → Health / Coherence / Alerts → Change → Reporting`

Alert **visibility/integration** belongs in this P1 user flow. The full Action/HITL automation programme does not.

### P2 — Procurement execution + richer Actions/HITL + governed communications — PLANNED

Once the project structure is stable, procurement can be generated and maintained against real WBS work packages:

`Procurement Plan → package → BoQ/RFQ → bids → evaluation/award → updates → stakeholder communications`

Stakeholder intelligence becomes operational here: responsibility and communication can be routed by WBS/RACI, with external supplier/client communication governed and auditable. Consequential actions remain HITL-gated.

### P3 — Executive / PMO / Portfolio intelligence — DEFERRED

Only after Current State, Evolution and Project Controls are trustworthy should C2Pro produce portfolio-level roll-ups, briefings and executive summaries. Those surfaces must preserve evidence/coverage and must never turn unknown child state into false green portfolio numbers.

## 9. End-user target journey

The reviewed target flow is:

1. Create/open a project and upload contract, budget, schedule, technical, quality and legal evidence as it becomes available.
2. C2Pro classifies evidence into the six dimensions and immediately shows Health coverage, findings and missing evidence.
3. Subsequent revisions trigger **What Changed** with durable lineage and impact context.
4. **Current State Report** consolidates authoritative project truth without synthetic values.
5. The **canonical WBS** provides the stable project structure; Budget, Schedule and Stakeholder/RACI views attach to it.
6. **Coherence** shows whether evidence-backed project state agrees; **Alerts** show concrete deadline/deviation/contradiction/missing-evidence conditions and drill into the affected WBS.
7. Procurement Plan derives packages from WBS work; BoQ/RFQ/bids/award/update flow follows.
8. WBS/RACI ownership routes internal actions and governed external supplier/client communications; HITL protects consequential decisions.
9. PMO/executive/portfolio views roll up Current State + Evolution + Project Controls + Actions with evidence-aware semantics.

That is the product destination against which new implementation should be judged.

## 10. Decision guards

The following are now product red lines:

- **No multiple WBSs for one project.** Multiple hierarchical levels/branches are correct; parallel canonical WBSs are not.
- **Schedule ≠ WBS.** Schedule activities/milestones link to WBS nodes.
- **Procurement package ≠ WBS.** Procurement references WBS nodes.
- **Health ≠ Coherence ≠ Alerts.** Same dimensions, different semantics.
- **Alert category ≠ trigger.** Category is dimensional; trigger is the reason the alert exists.
- **Unknown/null ≠ zero.** No blind averaging or synthetic green at WBS/project/portfolio level.
- **Candidate branch ≠ delivered product.** Lifecycle fields move only on evidence.

## 11. Remaining product defects / risks

The reconciliation closes the **planning ambiguity** around Project Controls, but not its implementation. Important open risks remain:

- P0b user value is not yet production-validated.
- Coherence v2 global authoritative cutover remains unproven.
- Temporal/change runtime qualification remains incomplete on `main`.
- ADR-025 is only PARTIAL: one-root and cross-domain linkage are still implementation work.
- Procurement before Project Controls would create rework and risk a parallel work-breakdown model.
- High coherence must never suppress visible critical alerts.
- WBS/project roll-ups must remain evidence/coverage-aware.

## 12. Next authorized sequence

1. **Finish P0b-L4-5 and production-validate the first-user Health journey.**
2. Continue the isolated durability, P0c, P0d and intelligence-quality candidate lanes under merge/deploy/prod gates.
3. Treat **Project Controls / ADR-025 as P1**: enforce the canonical WBS invariant and define Budget/Schedule/Stakeholder/Alert/Evidence/Change linkage contracts.
4. Keep alert visibility in the P1 experience; keep full correlated Action ownership/HITL in P2.
5. Build Procurement only on top of the canonical Project Controls backbone.
6. Extend reporting to executive/portfolio only when the underlying Current State + Evolution + controls are trustworthy.

**No direct `main` or production mutation is authorized by this reconciliation. Human-reviewed merge remains mandatory.**
