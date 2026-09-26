# C2Pro Master Product Programme Control — v1

**Status:** Reconciliation snapshot (read-only) · **Date:** 2026-09-26 · **Schema:** v7  
**reconciled_against_main_sha:** `1aecb4cf7ca454088e26046bb2ae8fa6b11bc518` · **deployed_runtime_sha:** `UNVERIFIED`  
**Machine source of truth:** [`validation/product/c2pro-master-product-control-v1.yaml`](../../validation/product/c2pro-master-product-control-v1.yaml)

> This document is the human projection of the machine product-control plane. It does not grant execution authority. Direct `main`, merge and production mutation remain governed outside this document.

> **Control integrity:** edit the YAML first, then regenerate/compare the canonical block with `validation/product/check_control_parity.py`. Branch completion never implies deployment or production validation.

<!-- CANONICAL-CONTROL:START (generated from the YAML by validation/product/check_control_parity.py --emit; do not hand-edit) -->
```control
reconciled_against_main_sha=1aecb4cf7ca454088e26046bb2ae8fa6b11bc518
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
adr.ADR-024.deployment=PARTIAL
adr.ADR-024.prod_validation=NONE
adr.ADR-025.realization=PARTIAL
adr.ADR-025.deployment=NONE
adr.ADR-025.prod_validation=NONE
p0b.done_digest=b43576250582d032
p0b.invariant_ids=INV-1,INV-UX,INV-COH
p0b.next_slice=P0b-L4-5
wbs.PWBS-EXEC-REPORTING.current_state.realization=WIRED
wbs.PWBS-EXEC-REPORTING.current_state.deployment=NONE
wbs.PWBS-EXEC-REPORTING.current_state.prod_validation=NONE
qualification.P0b.status=REQUIRED
qualification.P0b.bundle_ref=NONE
qualification.P0b.evidence_digest=NONE
qualification.P0b.targets_digest=4e87140a2424a0aa
qualification.P0c.status=REQUIRED
qualification.P0c.bundle_ref=NONE
qualification.P0c.evidence_digest=NONE
qualification.P0c.targets_digest=460b46a6bd750f0d
qualification.P0d.status=REQUIRED
qualification.P0d.bundle_ref=NONE
qualification.P0d.evidence_digest=NONE
qualification.P0d.targets_digest=5d60e81c739dc1ea
p0b.slice.P0b-L4-1.status=DONE
p0b.slice.P0b-L4-2.status=DONE
p0b.slice.P0b-L4-3.status=DONE
p0b.slice.P0b-L4-4.status=DONE
p0b.slice.P0b-L4-5.status=PARTIAL
p0b.residual_ids=P0b-R1-EVIDENCE-GRANULARITY,P0b-R2-CROSS-DATA-CONTRACT
p0b.residual.P0b-R1-EVIDENCE-GRANULARITY.status=RESOLVED
p0b.residual.P0b-R1-EVIDENCE-GRANULARITY.blocking=NON_BLOCKING
p0b.residual.P0b-R2-CROSS-DATA-CONTRACT.status=PLANNED
p0b.residual.P0b-R2-CROSS-DATA-CONTRACT.blocking=NON_BLOCKING
wbs.PWBS-ACT-HEALTH.realization=WIRED
wbs.PWBS-ACT-HEALTH.work_status=ACTIVE
wbs.PWBS-COHERENCE-XDOC.realization=PARTIAL
wbs.PWBS-COHERENCE-XDOC.work_status=PLANNED
wbs.PWBS-TEMPORAL-CHANGE.realization=WIRED
wbs.PWBS-TEMPORAL-CHANGE.work_status=ACTIVE
wbs.PWBS-ALERTS-ACTIONS-HITL.realization=PARTIAL
wbs.PWBS-ALERTS-ACTIONS-HITL.work_status=DEFERRED
wbs.PWBS-PROJECT-CONTROLS.realization=PARTIAL
wbs.PWBS-PROJECT-CONTROLS.work_status=ACTIVE
wbs.PWBS-PROCUREMENT.realization=PARTIAL
wbs.PWBS-PROCUREMENT.work_status=PLANNED
wbs.PWBS-EXEC-REPORTING.realization=PARTIAL
wbs.PWBS-EXEC-REPORTING.work_status=ACTIVE
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

- `reconciled_against_main_sha = 1aecb4cf7ca454088e26046bb2ae8fa6b11bc518` — repository baseline used for this reconciliation.
- `deployed_runtime_sha = UNVERIFIED` — intentionally retained as a legacy singleton: production is now observed as a composite runtime with Railway backend `386cbbce74b2653a6039fdddd9fc9719c43b9ff9` (SUCCESS) and Vercel frontend `6186f2a06fb3957562aa338742f18838fac5993a` (READY). #678 records plane-specific non-authoritative evidence; #681 owns Product-Control promotion integration.
- `product_value_delivered = false` — P0a reliability is closed and several product lanes are now wired on `main`, but the north-star P0b journey is still not PROD_VALIDATED.

### 2.1 What changed since the 2026-09-13 reconciliation

The previous control snapshot was anchored to `454637863c502f6825d158af551511e0e9996d14`. Current `main` is **276 commits ahead**. Material product changes include:

- **P0b-L4-5:** the release-ready six-category Health UI/report implementation merged through #630. The PR explicitly states `PROD_VALIDATED=NO`; merge/release-readiness therefore advances realization, not the production exit gate.
- **Durable Documents:** immutable tenant/project/document revision-object addressing is now on `main` (`fa58102d`).
- **P0c What Changed:** revision-bound events, semantic change projection, timeline/change-detail API and What Changed UI are on `main` (`d93ad4b5`).
- **P0d Current State:** domain projection, API, six-category Health parity, export and UI are on `main`.
- **ADR-025 Project Controls:** `wbs_nodes` is now the application-authoritative WBS store; parallel legacy writes are blocked; RACI/BOM/MCP and schedule/spend consumers are reconciled to the canonical WBS. The real production predecessor schema exposed a migration defect; #631 repaired it.
- **HITL:** #633/#638/#641/#646/#650 materially hardened pause/resume, exact review identity, fenced recovery and final-decision audit idempotency.
- **Trust/operability:** Next.js security moved to 16.3.6 (#654), the blocking E2E gate now runs against the production Next runtime (#655), and CRITICAL severity is preserved end-to-end (#656).
- **Qualification evidence:** #678 is merged. P0b/P0c/P0d evidence bundles are machine-validated, historically bound and explicitly non-authoritative; Product Control still owns lifecycle promotion.
- **Deployment identity:** Railway backend Watch Paths are live-proven (`#678` and `#699` main commits were `SKIPPED` while backend-changing #697 deployed). Vercel frontend filtering is merged via #699; live skip verification is pending the current Vercel daily-quota reset.

None of those facts permits collapsing the current production deployment into one repository SHA. The immediate user-value gap remains **P0b-L4-5 production evidence**: one uploaded document must reach a truthful six-category Health surface with findings, missing evidence and actionable gaps across the exact backend/frontend deployments exercised.

### 2.2 Qualification Control v1 — evidence is necessary, never self-promoting

Schema v7 adds a compact Product-Control integration for P0b, P0c and P0d. Detailed runtime/scenario/assertion evidence remains in the non-authoritative Phase-A bundles introduced by #678. Product Control stores only the qualification status, accepted bundle reference/hash and the fixed capability → lifecycle mapping.

Initial state is deliberately non-promoted:

- **P0b:** `REQUIRED`; no accepted bundle. A future PASS may support ADR-024 `prod_validation_status=PROD_VALIDATED` plus P0b-L4-5 `DONE`. ADR-018 is intentionally not auto-promoted.
- **P0c:** `REQUIRED`; no accepted bundle. A future PASS maps atomically to ADR-015 and ADR-016 production validation.
- **P0d:** `REQUIRED`; no accepted bundle. Qualification maps only to `PWBS-EXEC-REPORTING.current_state`; the deferred `executive_portfolio` subtrack remains independent.

A valid PASS evidence bundle may exist without changing lifecycle state. Conversely, if any mapped lifecycle target is promoted, the control checker fails closed unless the compact lane is PASS and references a hash-matching, capability-matching Phase-A PASS bundle. Merge/CI/deployment metadata alone cannot perform the transition.


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

The 2026-09-26 reconciliation advances **realization** where merged code now proves wiring, while deliberately leaving deployment/production validation conservative.

| ADR | Design | Realization | Deployment | Prod validation | Current meaning |
|---|---|---|---|---|---|
| ADR-009 Coherence | Accepted | PARTIAL | PARTIAL | PARTIAL | v1 historical production evidence; global authoritative v2 cutover still not demonstrated. |
| ADR-015 Temporal | Accepted | **WIRED** | PARTIAL | NONE | revision/event/snapshot structures plus revision-bound worker events, timeline/change-detail HTTP and UI are on main; current journey is not PROD_VALIDATED. |
| ADR-016 Change Impact | Accepted | **WIRED** | NONE | NONE | semantic diff, change projection/orchestration and What Changed UI are on main; deployment evidence remains open. |
| ADR-017 ProjectGraph | Accepted | SCAFFOLDED | BLOCKED | NONE | feature-gated/off for the canonical path. |
| ADR-018 Health | Accepted | WIRED | DEPLOYED | NOT_VALIDATED | Health backend exists; P0b user-visible production validation remains open. |
| ADR-019 Alerts/Actions | Accepted | SCAFFOLDED | NONE | NONE | alert/action domain partial; full correlation/action automation remains later. |
| ADR-020 HITL | Accepted | **WIRED** | PARTIAL | NONE | real review/approval plus V3 fenced resume/recovery and idempotent final-decision audit are wired; the latest hardened runtime is not independently PROD_VALIDATED. |
| ADR-021 Briefing | Deferred | SCAFFOLDED | NONE | NONE | executive briefing/portfolio stays later; P0d Current State is tracked separately as an implemented subtrack. |
| ADR-022 Contract Clarity | Accepted | WIRED | DEPLOYED | NOT_VALIDATED | findings path exists; not user/prod validated. |
| ADR-023 Agentic Coherence | Proposed | DESIGNED | NONE | NONE | roadmap/design only. |
| ADR-024 Single-document Activation | Accepted | WIRED | **PARTIAL** | NONE | L4-1..L4-5 implementation is merged/release-ready; real production incidents reached HITL, but the full Health outcome is not PROD_VALIDATED. |
| **ADR-025 Canonical Project Controls WBS Backbone** | **Accepted** | **PARTIAL** | **NONE** | **NONE** | canonical runtime WBS authority and several cross-domain references are now on main; one-logical-root/baseline/linkage completion and production proof remain open. |

ADR-025 has moved beyond “nested-set substrate only”: runtime application writes target `wbs_nodes`; the legacy WBS stores are write-blocked; RACI and BOM references point to the canonical nodes; MCP views consume the same hierarchy; schedule clauses and spend derive from it. What remains unproven is the complete Project Controls exit gate: one logical root under every write path, baseline/change governance, complete Budget/Schedule/Stakeholder/Procurement/Alert/Evidence/Change semantics and a production user journey.

## 5. Product WBS — 2026-09-26 reconciliation

| Product WBS | Pri | Realization | Work | What it means now |
|---|---:|---|---|---|
| **PWBS-ACT-HEALTH** | P0b | **WIRED** | ACTIVE | L4-1..L4-5 implementation is on main; production done-definition remains the gate. |
| **PWBS-COHERENCE-XDOC** | P1 | PARTIAL | PLANNED | Evidence-backed project consistency with six-dimensional breakdown and coverage; authoritative v2 cutover remains unresolved. |
| **PWBS-TEMPORAL-CHANGE** | P1 | **WIRED** | **ACTIVE** | What Changed runtime/API/UI is on main; deployment and production qualification remain open. |
| **PWBS-PROJECT-CONTROLS** | **P1** | **PARTIAL** | **ACTIVE** | Canonical WBS authority and several links are wired; complete controls contract and production journey remain open. |
| PWBS-ALERTS-ACTIONS-HITL | P2 | **PARTIAL** | DEFERRED | Underlying HITL runtime is materially hardened; richer correlation/ownership/Action lifecycle remains P2. |
| PWBS-PROCUREMENT | P2 | PARTIAL | PLANNED | Plan/WBS/BoM pieces exist; end-to-end Plan/RfQ/BoQ/comms remains incomplete and downstream of canonical Project Controls. |
| PWBS-EXEC-REPORTING | P3 | **PARTIAL** | **ACTIVE** | Current State is wired on main; executive/PMO/portfolio remains scaffolded/deferred. |
| PWBS-OPS-TRUST | P0 | DEPLOYED | ACTIVE | Reliability/trust baseline plus remaining deployment/durability qualification. |

### Project Controls P1 exit gate

P1 is now **ACTIVE/PARTIAL**, but not complete merely because canonical authority exists. Completion still requires:

1. exactly one logical canonical WBS root/tree per project under every supported write path;
2. WBS baseline/change governance;
3. Budget allocations/actuals link to WBS nodes and roll up honestly;
4. Schedule activities/milestones link to WBS nodes — **Schedule is not the WBS**;
5. Stakeholders/RACI link to WBS responsibility/escalation;
6. Procurement packages reference WBS work packages rather than instantiate another WBS;
7. Alerts, Evidence and Changes attach to WBS nodes or explicit project scope;
8. roll-ups preserve Unknown/null and material leaf risks instead of blind averaging;
9. a production user journey proves project → WBS → cost/time/stakeholder/alerts/evidence/change drill-down.

## 6. P0b vertical contract remains the immediate product gate

`P0b-L4-1` DONE · `L4-2` DONE · `L4-3` DONE · `L4-4` DONE · **`L4-5` PARTIAL**.

The distinction is important: **the L4-5 implementation is merged and release-ready, but the slice is not DONE because its exit gate is production evidence.** PR #630 explicitly recorded `PROD_VALIDATED=NO`.

P0b done still means: upload one real document → six categories → `{state, findings, missing_data}` → actionable gap alerts → Health Vector → API → user-visible UI/report on the deployed runtime. Unknown is null, never fabricated zero/green. Relational Coherence remains unavailable as a headline until enough reconcilable evidence exists.

Residuals remain honest:

- `P0b-R1-EVIDENCE-GRANULARITY` = RESOLVED / NON_BLOCKING.
- `P0b-R2-CROSS-DATA-CONTRACT` = PLANNED / P1 / NON_BLOCKING.

## 7. Implementation lanes — merged is still not deployed

The old candidate-lane view is stale. The controlling distinction is now **merged/wired ≠ deployed ≠ PROD_VALIDATED**.

| Lane | Current control state | Canonical interpretation |
|---|---|---|
| Durable Documents | MERGED_MAIN_NOT_PROD_VALIDATED | immutable revision-object storage semantics are on main; deployed runtime remains unverified. |
| P0c What Changed | WIRED_ON_MAIN_NOT_PROD_VALIDATED | temporal/change runtime, API and UI are on main; no production-validation claim. |
| P0d Reporting | WIRED_ON_MAIN_NOT_PROD_VALIDATED | Current State domain/API/UI/export are on main; executive/portfolio remains later. |
| Product Intelligence Quality | RECONCILIATION_REQUIRED | historical candidate branch is no longer active; main contains related quality changes, but lane-level closure is not independently asserted. |

This preserves the hard lifecycle boundary: **candidate/branch < merged/wired < deployed < PROD_VALIDATED**.

## 8. Roadmap — reconciled 2026-09-26

### P0a — Reliability & Operability Baseline — CLOSED

The plumbing exists and is useful, but reliability is not product completion.

### P0b — Single-document Health — ACTIVE / PROD_VALIDATION_PENDING

The first user-value loop is implemented and release-ready. The remaining gate is not more feature coding by default; it is deployment qualification and production evidence for the truthful six-category Health journey.

### P0c — What Changed / Temporal Change — WIRED_ON_MAIN / NOT_PROD_VALIDATED

The temporal/change path is no longer a future candidate. Revision-bound events, semantic change projection, timeline/detail API and What Changed UI exist on main. The next maturity step is runtime/deployment qualification, not rebuilding the lane.

### P0d — Current State Reporting — WIRED_ON_MAIN / NOT_PROD_VALIDATED

Current State reporting is implemented on main with authoritative domain sources, honest-null semantics, six-category Health parity, export and UI. Executive/portfolio reporting remains later.

### P1 — Project Controls Backbone + Coherence + alert visibility — ACTIVE / PARTIAL

P1 has started materially: one canonical WBS store is now runtime authority and several RACI/BOM/schedule/spend consumers are reconciled. Remaining work is the actual Project Controls contract and experience:

`Evidence → Project model → ONE WBS → Budget / Schedule / Stakeholders / Procurement → Health / Coherence / Alerts → Change → Reporting`

The authoritative Coherence v2 decision/cutover remains a separate open P1 concern. Alert **visibility/integration** belongs in P1; the richer Action/HITL automation programme remains P2 even though its runtime substrate is now substantially hardened.

### P2 — Procurement execution + richer Actions/HITL + governed communications — PLANNED

Once the Project Controls backbone is complete, procurement packages can derive from real WBS work packages:

`Procurement Plan → package → BoQ/RFQ → bids → evaluation/award → updates → stakeholder communications`

### P3 — Executive / PMO / Portfolio intelligence — DEFERRED

Current State exists earlier, but portfolio-level roll-ups and executive briefing remain downstream of validated Evolution + Project Controls and must preserve evidence/coverage semantics.

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

### Causal failure hierarchy gate

Qualification records failures in execution chronology: the first user-visible
or product-causal failure is **PRIMARY**; later failures are classified as
**SECONDARY**, **CASCADE**, or **INCIDENTAL**. A later, more severe-looking
error must not replace the primary boundary without evidence that it caused
that earlier failure.

### Evidence addressability contract

Every user-visible evidence reference must resolve end-to-end: Finding →
Evidence Reference → stable Evidence ID → Evidence Resolver → representable UI
target → observable active/highlighted state. Target types are extensible and
include **CLAUSE**, **DOCUMENT_SPAN**, **STAKEHOLDER**, **RACI**, **WBS**,
**ALERT**, **CHANGE**, and **OTHER**. Resolution degrades only in this order:
exact semantic target, raw clause/span, source document with an explanation,
then an explicit unresolved state; it must never silently select nothing.

`EVIDENCE_REFERENCE_EMITTED ⇒ EVIDENCE_TARGET_RESOLVABLE`

`EVIDENCE_TARGET_RESOLVABLE ⇒ UI_ACTIVE_TARGET_OBSERVABLE`

## 11. Remaining product defects / risks

The largest planning defect in the old snapshot was no longer missing code; it was **stale lifecycle classification**. The remaining substantive risks are:

- P0b is merged/release-ready but still not PROD_VALIDATED; declaring it DONE would conflate merge with user-value proof.
- P0c and P0d are wired on main but remain deployment/prod-validation work.
- Coherence v2 global authoritative cutover remains unproven.
- ADR-025 canonical authority is real, but one-logical-root enforcement, baseline/change governance and complete cross-domain linkage/drill-down remain PARTIAL.
- The real production predecessor schema already disproved the assumption that clean scratch migrations fully represent production history; deployment qualification must include real predecessor-shape evidence.
- HITL has materially hardened, but the latest V3 runtime must not be assumed deployed solely because it is merged.
- Procurement before the remaining Project Controls contract closes would still create rework.
- High coherence must never suppress visible critical alerts.
- WBS/project roll-ups must remain evidence/coverage-aware.
- High-velocity parallel lanes can stale the MASTER quickly; each planning milestone should reconcile against an exact `main` SHA.

## 12. Next authorized sequence

1. **Immediate P0 — production qualification, not another feature lane:** deploy/qualify the current hardened `main` and close P0b-L4-5 with evidence for the truthful single-document Health journey.
2. **Qualify what is already built:** prove P0c What Changed and P0d Current State on the deployed runtime; do not recreate them as candidate work.
3. **P1 Project Controls — ACTIVE/PARTIAL:** finish one-logical-root enforcement, WBS baseline/change governance and complete Budget/Schedule/Stakeholder/Alert/Evidence/Change linkage plus user drill-down.
4. **P1 Coherence:** make the authoritative v2 cutover decision independently from Health and preserve coverage/Unknown semantics.
5. Keep alert visibility/integration in P1; keep richer Action ownership/correlation/HITL automation in P2 despite the hardened HITL substrate.
6. Build Procurement only on top of the completed canonical Project Controls backbone.
7. Extend reporting to executive/portfolio only when Current State + Evolution + Project Controls are trustworthy.
8. **Control-plane discipline:** reconcile this YAML/Markdown pair against an exact `main` SHA whenever a material product lane merges; branch completion never advances deployment or PROD_VALIDATED automatically.

**No direct `main` or production mutation is authorized by this reconciliation. Human-reviewed merge remains mandatory.**
