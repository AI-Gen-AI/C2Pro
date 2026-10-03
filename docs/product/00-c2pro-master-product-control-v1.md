# C2Pro Master Product Programme Control — v1

**Status:** Reconciliation snapshot (read-only) · **Date:** 2026-10-03 · **Schema:** v7  
**reconciled_against_main_sha:** `9893cd42049c3cd2bbf9e8d891df0725b35ef082` · **deployed_runtime_sha:** `UNVERIFIED`  
**Machine source of truth:** [`validation/product/c2pro-master-product-control-v1.yaml`](../../validation/product/c2pro-master-product-control-v1.yaml)

> This document is the human projection of the machine product-control plane. It does not grant execution authority. Direct `main`, merge and production mutation remain governed outside this document.

> **Control integrity:** edit the YAML first, then regenerate/compare the canonical block with `validation/product/check_control_parity.py`. Branch completion never implies deployment or production validation.

<!-- CANONICAL-CONTROL:START (generated from the YAML by validation/product/check_control_parity.py --emit; do not hand-edit) -->
```control
reconciled_against_main_sha=9893cd42049c3cd2bbf9e8d891df0725b35ef082
deployed_runtime_sha=UNVERIFIED
reliability_operability_baseline=CLOSED
product_value_delivered=false
current_product_wedge_id=P0b-single-document-health-activation
coherence.global_authoritative_cutover=NO
legacy_coverage.unmapped_open_legacy_items=0
project_controls.invariant=one_project_one_canonical_hierarchical_wbs
product_semantics.canonical_dimensions=SCOPE,BUDGET,TIME,TECHNICAL,LEGAL,QUALITY
wbs.PWBS-PROJECT-CONTROLS.priority=P1
adr.ADR-018.design=Accepted
adr.ADR-018.realization=WIRED
adr.ADR-018.deployment=DEPLOYED
adr.ADR-018.prod_validation=NOT_VALIDATED
adr.ADR-024.design=Accepted
adr.ADR-024.realization=WIRED
adr.ADR-024.deployment=PARTIAL
adr.ADR-024.prod_validation=NONE
adr.ADR-025.design=Accepted
adr.ADR-025.realization=PARTIAL
adr.ADR-025.deployment=NONE
adr.ADR-025.prod_validation=NONE
adr.ADR-026.design=Accepted
adr.ADR-026.realization=WIRED
adr.ADR-026.deployment=NONE
adr.ADR-026.prod_validation=NONE
adr.ADR-027.design=Accepted
adr.ADR-027.realization=WIRED
adr.ADR-027.deployment=NONE
adr.ADR-027.prod_validation=NONE
adr.ADR-028.design=Accepted
adr.ADR-028.realization=SCAFFOLDED
adr.ADR-028.deployment=NONE
adr.ADR-028.prod_validation=NONE
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

- `reconciled_against_main_sha = 9893cd42049c3cd2bbf9e8d891df0725b35ef082` — current repository baseline after #780 plus the later docs/CI-only #798–#800 changes.
- `deployed_runtime_sha = UNVERIFIED` — intentionally retained as a legacy singleton because production is composite. The latest #715 dispatch binding records Railway backend commit `314fc39b0b4c25c8c0ca99977314ba1bb9083208` with API `37d1fe0b-4223-4654-806a-23b6d2b73264`, Worker `7ee88c11-596a-4188-b378-14502659b806` and Scheduler `96d11273-0af9-4691-b013-42296a247906` previously observed SUCCESS; Vercel production commit `12b7f09edc0e1cf864906268ddc5b8e75d3f8a4c` with deployment `dpl_FgMfbquSUcyBgPVw2SdetDe7UZQ1` previously observed READY. Backend and frontend SHAs legitimately differ; #715 A1 must independently re-verify every provider identity before mutation.
- Railway staged changes were last observed clear (`stagedChanges=null`; historical pending row `changes=[]`). This remains an A1 fail-closed precondition rather than assumed truth.
- Fresh API logs report `coherence_analysis=True`; this proves production Coherence is enabled, but does not by itself prove the separate per-tenant ADR-017 ProjectGraph gate.
- `product_value_delivered = false` — P0a reliability is closed and several product lanes are now wired on `main`, but the north-star P0b journey is still not PROD_VALIDATED.

### 2.1 What changed in the 2026-10-01 reconciliation

Since the 2026-09-27 control snapshot, repository realization advanced materially while production-validation state remains deliberately conservative:

- **#781** merged backend support for Clerk v2 organization claim shapes while preserving tenant-validation semantics.

- **#711** durable processing/recovery work is closed.
- **#758** closes the LangGraph checkpoint-lineage authority defect found during independent review: stale processing lineage cannot become selectable as current after takeover/reprocess.
- **#714 / PR #726** trusted-state commit and projected-Coherence implementation is merged/closed after the lineage fence was integrated. Pending/rejected candidates remain non-authoritative; approval binds exact reviewed state.
- **#715 / PR #733** production synthetic acceptance harness implementation is merged. **#715 remains open** because implementing the harness is not the same as executing and accepting the full production journey.
- **#775** closes Clerk organization-token synchronization races so stale personal/previous-organization token work cannot overwrite current organization auth state.
- **#779** bounds automatic Vercel Git deployments to `main`, `hotfix/**`, `release-candidate/**` and `preview/**`; ordinary PRs remain governed by GitHub CI without consuming automatic preview quota.
- R17 Sonar/security-hotspot cleanup is complete. This improves repository quality/security posture but does not count as product-value validation.

Still open for the end-user GOAL:

- **#706** full production end-user journey;
- **#715** accepted full production qualification;
- **#690** dedicated non-customer production qualification identity/tenant evidence;
- **#712** truthful lifecycle fix-forward;
- **#713** evidence-locator truthfulness fix-forward.

Therefore `product_value_delivered=false` and P0b/P0c/P0d qualification lanes remain unchanged. No merge, CI, deployment or documentation event in this reconciliation self-promotes lifecycle state.

### 2.2 Revalidation on 2026-10-03

After the 2026-10-01 snapshot, `main` advanced by 38 commits to `314fc39b0b4c25c8c0ca99977314ba1bb9083208`.

- **#782-#787 / #715** harden the production-qualification path around Railway identity observation, tenant RLS context, bounded Clerk preflight waits and canonical production authentication. **#715 remains open**; these merges are harness/runtime hardening, not accepted qualification.
- **#790 / #789** moves SSE bearer handling behind the same-origin server proxy and rejects bearer tokens in query strings.
- **#793 / #792** ensures an explicit `human_approval_required=True` reaches the router as HIGH impact, so confidence cannot auto-approve a state that already requires human review. The broader LOW/MEDIUM non-gated policy path still exists when no explicit human requirement is set.
- **#706, #715, #690, #712 and #713 remain open**. #792 is also still open pending acceptance/closure.

No Product-Control lifecycle field is promoted by this revalidation.

### 2.3 Post-#780 master reconciliation — 2026-10-03

Current repository control is rebound to `main@9893cd42049c3cd2bbf9e8d891df0725b35ef082`.

- **#780** is merged and Line B's documentation/authority reconciliation is closed.
- **#690** is closed from production synthetic run #30: dedicated tenant/identity, no customer data, real production auth and tenant-isolation preflights passed.
- Run #30 later failed at the HITL seam. **#793** is merged/deployed as the runtime fix, while **#792 stays open** until the next #715 full production journey proves the explicit-human boundary in production.
- **#798** is README-only local-DB documentation; **#799/#800** are CI-efficiency/hygiene changes. None changes end-user runtime semantics or Product-Control lifecycle state.
- The next bounded product work is therefore **#715 A1 → A2**, not additional prerequisite or documentation work.

No lifecycle field is promoted by this reconciliation.

### 2.4 Qualification Control v1 — evidence is necessary, never self-promoting

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

The 2026-10-03 revalidation preserves **realization** advances where merged code proves wiring, while deliberately leaving deployment/production validation conservative.

| ADR | Design | Realization | Deployment | Prod validation | Current meaning |
|---|---|---|---|---|---|
| ADR-009 Coherence | Accepted | PARTIAL | PARTIAL | PARTIAL | v1 historical production evidence; global authoritative v2 cutover still not demonstrated. |
| ADR-015 Temporal | Accepted | **WIRED** | PARTIAL | NONE | revision/event/snapshot structures plus revision-bound worker events, timeline/change-detail HTTP and UI are on main; current journey is not PROD_VALIDATED. |
| ADR-016 Change Impact | Accepted | **WIRED** | NONE | NONE | semantic diff, change projection/orchestration and What Changed UI are on main; deployment evidence remains open. |
| ADR-017 ProjectGraph | Accepted | SCAFFOLDED | BLOCKED | NONE | feature-gated/off for the canonical path. |
| ADR-018 Health | Accepted | WIRED | DEPLOYED | NOT_VALIDATED | Health backend exists; P0b user-visible production validation remains open. |
| ADR-019 Alerts/Actions | Accepted | SCAFFOLDED | NONE | NONE | alert/action domain partial; full correlation/action automation remains later. |
| ADR-020 HITL | Accepted | **WIRED** | PARTIAL | NONE | real review/approval plus V3 fenced resume/recovery and idempotent final-decision audit are wired; #793 prevents confidence from bypassing an explicit `human_approval_required=True` boundary, while high-confidence LOW/MEDIUM non-gated items can still auto-approve when no explicit human requirement exists. ADR-020's broader consequential-decision policy remains only partially realized. |
| ADR-021 Briefing | Deferred | SCAFFOLDED | NONE | NONE | executive briefing/portfolio stays later; P0d Current State is tracked separately as an implemented subtrack. |
| ADR-022 Contract Clarity | Accepted | WIRED | DEPLOYED | NOT_VALIDATED | findings path exists; not user/prod validated. |
| ADR-023 Agentic Coherence | Proposed | DESIGNED | NONE | NONE | roadmap/design only. |
| ADR-024 Single-document Activation | Accepted | WIRED | **PARTIAL** | NONE | L4-1..L4-5 implementation is merged/release-ready; real production incidents reached HITL, but the full Health outcome is not PROD_VALIDATED. |
| **ADR-025 Canonical Project Controls WBS Backbone** | **Accepted** | **PARTIAL** | **NONE** | **NONE** | canonical runtime WBS authority and several cross-domain references are now on main; one-logical-root/baseline/linkage completion and production proof remain open. |
| **ADR-026 Trusted-State Commit Boundary** | **Accepted** | **WIRED** | **NONE** | **NONE** | #714 trusted-state commit/projected-Coherence semantics are merged; no deployed-runtime or full production-journey validation is claimed. |
| **ADR-027 Processing Authority & Checkpoint Lineage** | **Accepted** | **WIRED** | **NONE** | **NONE** | #711/#758 authority and checkpoint-lineage fencing are merged; deployment/production acceptance stays under #706/#715. |
| **ADR-028 Production Qualification / Composite Runtime** | **Accepted** | **SCAFFOLDED** | **NONE** | **NONE** | #715/#733 harness and provider-identity/evidence contracts are merged; #690 prerequisite is closed from run #30 identity/tenant evidence; #715 full-journey acceptance remains open and is the acceptance vehicle for #792. |

ADR-025 has moved beyond “nested-set substrate only”: runtime application writes target `wbs_nodes`; the legacy WBS stores are write-blocked; RACI and BOM references point to the canonical nodes; MCP views consume the same hierarchy; schedule clauses and spend derive from it. What remains unproven is the complete Project Controls exit gate: one logical root under every write path, baseline/change governance, complete Budget/Schedule/Stakeholder/Procurement/Alert/Evidence/Change semantics and a production user journey.

## 5. Product WBS — 2026-10-01 reconciliation

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
- High-velocity parallel lanes can stale Product Control quickly; each planning milestone should reconcile against an exact `main` SHA.

## 12. Next authorized sequence

1. **#690 prerequisite is complete.** Run #30 proved the dedicated non-customer production tenant/identity and real production auth preflight. Do not reopen it unless contradictory production evidence appears.
2. **Line A / #715 — A1 identity preflight:** run the non-mutating production identity/provider preflight on the current composite production binding. A1 must PASS before any product mutation.
3. **Line A / #715 — A2 full production journey:** only after A1 PASS, execute `AUTH → PROJECT → UPLOAD → PARSE/EXTRACT → ANALYSIS → EVIDENCE → REVIEW_REQUIRED → exactly one addressable review item → explicit UI approval → ANALYZED → HEALTH → REFRESH/RELOGIN → read-only durable verification` with `require_hitl=true`.
4. **#792 acceptance is bound to A2:** close #792 only if A2 proves no confidence-only automatic approval, one explicit durable human decision/correction, same governed lineage and no duplicate trusted/durable effects.
5. **#712/#713 remain acceptance/fix-forward authorities:** their landed lifecycle/evidence fixes must be exercised by A2. Administrative openness does not block A1.
6. **Fail closed:** on the first failing seam, stop and remediate only that bounded defect. Do not weaken auth/RLS/HITL, substitute expected provider IDs for observation, accept fixture mismatch, or manually repair production state.
7. **Return evidence to Line B:** A2 PASS returns one bounded non-secret bundle for explicit P0b Product-Control reconciliation. PASS never self-promotes lifecycle state.
8. **Only after explicit P0b reconciliation:** qualify P0c/P0d where their own evidence contracts pass, then stop/reconcile before authorizing P1 Project Controls or downstream Procurement.

**No direct `main` or production mutation is authorized by this reconciliation. Human-reviewed merge remains mandatory.**
