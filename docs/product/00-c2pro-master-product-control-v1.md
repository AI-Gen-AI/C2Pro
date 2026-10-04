# C2Pro Master Product Programme Control — v1

**Status:** Reconciliation snapshot (read-only) · **Date:** 2026-10-04 · **Schema:** v8
**reconciled_against_main_sha:** `c41ff69bcabd87da1a606b125bd9cc37184bc7cc` · **deployed_runtime_sha:** `UNVERIFIED`
**Machine source of truth:** [`validation/product/c2pro-master-product-control-v1.yaml`](../../validation/product/c2pro-master-product-control-v1.yaml)

> This document is the human projection of the machine product-control plane. It does not grant execution authority. Direct `main`, merge and production mutation remain governed outside this document.

> **Control integrity:** edit the YAML first, then regenerate/compare the canonical block with `validation/product/check_control_parity.py`. Branch completion never implies deployment or production validation.

<!-- CANONICAL-CONTROL:START (generated from the YAML by validation/product/check_control_parity.py --emit; do not hand-edit) -->
```control
reconciled_against_main_sha=c41ff69bcabd87da1a606b125bd9cc37184bc7cc
deployed_runtime_sha=UNVERIFIED
reliability_operability_baseline=CLOSED
product_value_delivered=true
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
adr.ADR-024.prod_validation=PROD_VALIDATED
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
p0b.next_slice=NONE
wbs.PWBS-EXEC-REPORTING.current_state.realization=WIRED
wbs.PWBS-EXEC-REPORTING.current_state.deployment=NONE
wbs.PWBS-EXEC-REPORTING.current_state.prod_validation=NONE
qualification.P0b.status=PASS
qualification.P0b.bundle_ref=evidence/product-qualification/p0b-prod-gh-37196092728-1.yaml
qualification.P0b.evidence_digest=d6031d454ac40f30
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
p0b.slice.P0b-L4-5.status=DONE
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

- `reconciled_against_main_sha = c41ff69bcabd87da1a606b125bd9cc37184bc7cc` — current repository baseline after #824 (persisted alert review), #823 (Lane C temporal impact/trust seam) and #826 (production-acceptance Evidence hard-refresh rate-limit handling). Those later merges are implementation/harness state only; the accepted P0b runtime remains the earlier qualified composite.
- `deployed_runtime_sha = UNVERIFIED` — retained as a legacy singleton because production is composite. The accepted P0b binding is Railway backend `5491e36c8f71113540c65ddd9fa7fc5e45a01f27` / API deployment `f976eb47-c2aa-4b02-a0c6-25e555d4405b` (SUCCESS) plus Vercel frontend `84842677adb7046ea24b0e92fc5aaa3ee20565b0` / deployment `dpl_3Lv1u6UtwWUQvVrhdckiqfZc4SHg` (READY).
- A1 run **#55 / 37195954713** passed identity/runtime/auth/tenant preflight. A2 run **#56 / 37196092728** passed the full production browser journey, durable verifier, evidence-bundle build and evidence validator.
- The accepted P0b bundle is `evidence/product-qualification/p0b-prod-gh-37196092728-1.yaml`, SHA-256 `d6031d454ac40f30a84a1b9c30f4f5d97ef285d7eb9e8d047a0af97148f6281b`.
- `product_value_delivered = true` means the **current P0b single-document Health wedge** has proven production user value. It does not claim that P0c/P0d, global Coherence, Project Controls, Procurement or the complete North Star are delivered.
- Two OPS residuals remain explicit: best-effort `ai_usage_logs` telemetry currently hits a production-schema `model_name` drift, and the high-volume acceptance run reached Railway's log-rate limit. Neither invalidated the product journey; both require separate operational follow-up.

### 2.1 What changed in the 2026-10-01 reconciliation

Since the 2026-09-27 control snapshot, repository realization advanced materially while production-validation state remained deliberately conservative at that dated checkpoint. **This subsection is historical and is superseded by §2.5 for current P0b qualification truth:**

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

After the 2026-10-01 snapshot, `main` advanced by 38 commits to `314fc39b0b4c25c8c0ca99977314ba1bb9083208`. **This is a historical 2026-10-03 revalidation; its open/closed statements are not current authority and are superseded by §2.5.**

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

Current qualification state:

- **P0b:** `PASS`; accepted bundle `evidence/product-qualification/p0b-prod-gh-37196092728-1.yaml`. The fixed atomic targets are now ADR-024 `prod_validation_status=PROD_VALIDATED` plus P0b-L4-5 `DONE`. ADR-018 is intentionally **not** auto-promoted because its broader Health-engine scope exceeds this bounded qualification.
- **P0c:** `REQUIRED`; no accepted bundle. A future PASS maps atomically to ADR-015 and ADR-016 production validation.
- **P0d:** `REQUIRED`; no accepted bundle. Qualification maps only to `PWBS-EXEC-REPORTING.current_state`; the deferred `executive_portfolio` subtrack remains independent.
- P0b has no fabricated follow-on slice: `p0b.next_slice=NONE` is legal only because every P0b L4 slice is `DONE`.

A valid PASS evidence bundle never auto-promotes lifecycle state. This reconciliation performs the explicit reviewed P0b transition; future promotions remain fail-closed unless the compact lane is PASS and references a hash-matching, capability-matching Phase-A PASS bundle.




### 2.5 P0b production acceptance — 2026-10-04

Line A is closed from the canonical production proof:

- **A1 #55 / 37195954713:** PASS.
- **A2 #56 / 37196092728:** PASS across AUTH → PROJECT → UPLOAD → PARSE/EXTRACT → ANALYSIS → REVIEW_REQUIRED → explicit UI approval → ANALYZED → HEALTH → EVIDENCE → REFRESH/RELOGIN → durable read-only verification.
- Durable uniqueness: one document/revision, one approved review, one `hitl.correction`, one `FINALIZED_APPROVED` resume operation, one `graph.completed`, one `graph_completed` Health snapshot, six assessments.
- Qualification artifact `11301371769` passed the canonical evidence validator; the committed YAML bundle is hash-bound in Product Control.
- #715 and #792 are closed. #706 now moves from production-journey execution to Product-Control reconciliation/closure.
- #712 and #713 remain separate fix-forward/acceptance authorities for scenarios not exhaustively covered by the bounded P0b run.

This is the first explicit Product-Control promotion from production evidence for the current wedge. It does not promote P0c, P0d, ADR-018, global Coherence or P1.

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
| ADR-018 Health | Accepted | WIRED | DEPLOYED | NOT_VALIDATED | The bounded P0b single-document Health wedge passed production run #56; broader ADR-018 Health-engine validation remains independently open. |
| ADR-019 Alerts/Actions | Accepted | SCAFFOLDED | NONE | NONE | alert/action domain partial; full correlation/action automation remains later. |
| ADR-020 HITL | Accepted | **WIRED** | PARTIAL | NONE | real review/approval plus V3 fenced resume/recovery and idempotent final-decision audit are wired; #793 prevents confidence from bypassing an explicit `human_approval_required=True` boundary, while high-confidence LOW/MEDIUM non-gated items can still auto-approve when no explicit human requirement exists. ADR-020's broader consequential-decision policy remains only partially realized. |
| ADR-021 Briefing | Deferred | SCAFFOLDED | NONE | NONE | executive briefing/portfolio stays later; P0d Current State is tracked separately as an implemented subtrack. |
| ADR-022 Contract Clarity | Accepted | WIRED | DEPLOYED | NOT_VALIDATED | findings path exists; not user/prod validated. |
| ADR-023 Agentic Coherence | Proposed | DESIGNED | NONE | NONE | roadmap/design only. |
| ADR-024 Single-document Activation | Accepted | WIRED | **PARTIAL** | **PROD_VALIDATED** | P0b run #56 / `37196092728` completed the bounded production Health journey with a hash-bound PASS bundle; broader ADR-018 Health scope is not auto-promoted. |
| **ADR-025 Canonical Project Controls WBS Backbone** | **Accepted** | **PARTIAL** | **NONE** | **NONE** | canonical runtime WBS authority and several cross-domain references are now on main; one-logical-root/baseline/linkage completion and production proof remain open. |
| **ADR-026 Trusted-State Commit Boundary** | **Accepted** | **WIRED** | **NONE** | **NONE** | #714 trusted-state commit/projected-Coherence semantics are merged; no deployed-runtime or full production-journey validation is claimed. |
| **ADR-027 Processing Authority & Checkpoint Lineage** | **Accepted** | **WIRED** | **NONE** | **NONE** | #711/#758 authority and checkpoint-lineage fencing are merged; the P0b run exercised this path successfully, but ADR-027 is not a fixed P0b promotion target and retains its independent lifecycle state. |
| **ADR-028 Production Qualification / Composite Runtime** | **Accepted** | **SCAFFOLDED** | **NONE** | **NONE** | The #715/#733 qualification mechanism was exercised successfully by A1 #55 and A2 #56; #715/#792 are closed. ADR-028 is not a fixed P0b promotion target, so this acceptance does not self-promote its lifecycle fields. |

ADR-025 has moved beyond “nested-set substrate only”: runtime application writes target `wbs_nodes`; the legacy WBS stores are write-blocked; RACI and BOM references point to the canonical nodes; MCP views consume the same hierarchy; schedule clauses and spend derive from it. What remains unproven is the complete Project Controls exit gate: one logical root under every write path, baseline/change governance, complete Budget/Schedule/Stakeholder/Procurement/Alert/Evidence/Change semantics and a production user journey.

## 5. Product WBS — 2026-10-01 reconciliation

| Product WBS | Pri | Realization | Work | What it means now |
|---|---:|---|---|---|
| **PWBS-ACT-HEALTH** | P0b | **WIRED** | ACTIVE | L4-1..L4-5 are DONE and the bounded P0b production done-definition passed; broader Health work remains independently governed. |
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

## 6. P0b vertical contract — accepted production baseline

`P0b-L4-1` DONE · `L4-2` DONE · `L4-3` DONE · `L4-4` DONE · **`L4-5` DONE**.

PR #630 historically recorded `PROD_VALIDATED=NO` when implementation alone existed. That historical boundary is now superseded by A1 #55 + A2 #56 and the accepted hash-bound bundle; no merge or deployment event by itself performed the promotion.

The accepted P0b done-definition remains: upload one real document → six categories → `{state, findings, missing_data}` → actionable gap alerts → Health Vector → API → user-visible UI/report on the deployed runtime. Unknown is null, never fabricated zero/green. Relational Coherence remains unavailable as a headline until enough reconcilable evidence exists.

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

### P0b — Single-document Health — PROD_VALIDATED / CLOSED

The first user-value loop is production-qualified by A1 #55 and A2 #56. The accepted hash-bound P0b bundle closes L4-5 and promotes only ADR-024; P0c/P0d, broader ADR-018 Health, global Coherence and P1 remain independently governed.

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
