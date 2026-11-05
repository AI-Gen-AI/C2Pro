# C2Pro Master Product Programme Control — v1

**Status:** Reconciliation snapshot (read-only) · **Date:** 2026-10-05 · **Schema:** v8
**reconciled_against_main_sha:** `1b1ccd94046d02ada077c989aa19047ebb6e0bf8` · **deployed_runtime_sha:** `UNVERIFIED`
**Machine source of truth:** [`validation/product/c2pro-master-product-control-v1.yaml`](../../validation/product/c2pro-master-product-control-v1.yaml)

> This document is the human projection of the machine product-control plane. It does not grant execution authority. Direct `main`, merge and production mutation remain governed outside this document.

> **Control integrity:** edit the YAML first, then regenerate/compare the canonical block with `validation/product/check_control_parity.py`. Branch completion never implies deployment or production validation.

<!-- CANONICAL-CONTROL:START (generated from the YAML by validation/product/check_control_parity.py --emit; do not hand-edit) -->
```control
reconciled_against_main_sha=1b1ccd94046d02ada077c989aa19047ebb6e0bf8
deployed_runtime_sha=UNVERIFIED
reliability_operability_baseline=CLOSED
product_value_delivered=true
current_product_wedge_id=P0c-what-changed-production-qualification
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

**Active product wedge:** P0c What Changed / Temporal Change production qualification. P0b remains the accepted product-value baseline; this planning-focus change does not self-promote P0c deployment or production-validation state.

## 2. Current production truth

Three facts remain deliberately separate:

- `reconciled_against_main_sha = 1b1ccd94046d02ada077c989aa19047ebb6e0bf8` — current repository baseline after #866 reconciled the B1/correctness closure onto main. This is repository/control truth only; the accepted P0b runtime remains the earlier qualified composite.
- `deployed_runtime_sha = UNVERIFIED` — retained as a legacy singleton because production is composite. The accepted P0b binding is Railway backend `5491e36c8f71113540c65ddd9fa7fc5e45a01f27` / API deployment `f976eb47-c2aa-4b02-a0c6-25e555d4405b` (SUCCESS) plus Vercel frontend `84842677adb7046ea24b0e92fc5aaa3ee20565b0` / deployment `dpl_3Lv1u6UtwWUQvVrhdckiqfZc4SHg` (READY).
- A1 run **#55 / 37195954713** passed identity/runtime/auth/tenant preflight. A2 run **#56 / 37196092728** passed the full production browser journey, durable verifier, evidence-bundle build and evidence validator.
- The accepted P0b bundle is `evidence/product-qualification/p0b-prod-gh-37196092728-1.yaml`, SHA-256 `d6031d454ac40f30a84a1b9c30f4f5d97ef285d7eb9e8d047a0af97148f6281b`.
- `product_value_delivered = true` remains grounded only in the accepted **P0b single-document Health** evidence. The active qualification focus is now P0c; this does not claim that P0c/P0d, global Coherence, Project Controls, Procurement or the complete North Star are delivered.
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

### 2.6 B1 implementation closure and correctness reconciliation — 2026-10-05

Repository control is reconciled to `main@23b963a50a7de7a4096063808a7f361f9df84ba1` without changing the accepted production-runtime binding.

- **B1 runtime implementation is closed at repository/CI level.** #842, #840, #853, #858 and #857 establish family/observation identity, honest projected subscores, validated false-positive canonical rescoring, transaction-aware review and exact snapshot/replay wiring. #832 records the governing v1.2 implementation-closure / acceptance boundary.
- **B1-12 remains PENDING.** Green CI and merged code do not prove the complete Alerts + Coherence user journey on an exact deployed runtime.
- **#817** adds document-first processing-authority locking with real two-session PostgreSQL race coverage; it is correctness evidence, not lifecycle promotion.
- Schedule ingestion no longer mutates canonical WBS state. Schedule remains a linked temporal domain, never WBS identity.
- **#863/#862** removes the destructive Budget→BOM NULL-source sweep: ordinary parse/reparse can replace only rows explicitly owned by the current source document. Manual/ownership-unknown BOM rows are preserved.
- **#864** separately tracks machine-extracted Stakeholder provenance so automatic extraction cannot masquerade as human approval.
- P0b remains exactly the accepted run #56 wedge. **P0c and P0d remain REQUIRED** and must earn their own exact-runtime evidence.

No deployment or PROD_VALIDATED field is promoted by this reconciliation.

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

**Approved non-blocking ADR-025 evolution — Risk Register (#836).** Project Controls will later absorb a canonical Risk Register / governed Risk Assessment capability by evolving the existing N4/`RiskItem` extraction path. It stays on the same canonical project/WBS backbone; there is no parallel risk WBS and no autonomous agent that defines canonical risk truth. The future contract separates risk likelihood/probability, impact and exposure from Coherence certainty/materiality, preserves Unknown/null, and links treatment/owner/residual risk to Evidence, Alerts and Changes. This is an accepted architecture direction only and does not advance realization, deployment or production-validation state; B1/C3b continue independently.

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

1. **Preserve P0b truth.** Run #56 / 37196092728 and its hash-bound bundle remain the accepted P0b evidence. Later merges neither demote nor extend that production-validation scope.
2. **#867 B1-12 acceptance may proceed in parallel.** Runtime implementation is closed; B1-12 still requires its own exact-runtime Alerts + Coherence acceptance evidence.
3. **#686 P0c What Changed:** rebind the exact live Railway backend + Vercel frontend immediately before execution, then qualify the two-revision real user journey. Failed runs are evidence and never justify manual production repair.
4. **#687 P0d Current State:** only after accepted P0c evolution, qualify authoritative Current State, six-category Health parity, honest null, API/UI/export parity and reproducibility on the governed project.
5. **Reconcile before P1.** PASS evidence does not self-promote Product Control. After P0c/P0d evidence review, reconcile lifecycle state explicitly.
6. **Enter Project Controls through PC-1/PC-2:** one logical canonical WBS under all supported write paths, then WBS baseline/change governance. Schedule remains linked to WBS and Procurement consumes WBS packages; neither creates parallel hierarchy.
7. **Correctness follow-ups remain explicit:** #864 stakeholder provenance is P1; #839 Risk Register direction is retained but must be reapplied to current Product Control; DEV-15 hygiene follows correctness/control work.
8. **Fail closed throughout:** do not weaken auth/RLS/HITL/trust, fabricate evidence, coerce Unknown to zero, or infer deployment/PROD_VALIDATED from merge/CI.

**No direct `main` or production mutation is authorized by this reconciliation. Human-reviewed merge remains mandatory.**


## 13. Owner-approved Product Quality + HITL workstream — PQ-HITL-2026-01 (2026-10-08)

**Approval:** owner APPROVED the improvement priorities and governed task-by-task implementation. **Implementation as of 2026-10-08:** ACTIVE / PARTIAL; some bounded slices are MERGED with verified green CI, but **none of the 01-09 tasks is fully product-accepted or PROD_VALIDATED**. Task 10 stays DEFERRED. This section reflects `product_quality_hitl_2026_10_08` in the YAML machine source of truth; it grants no HITL production decision, deployment, forced reprocess or P0c/P0d promotion.

**Epic:** [#936](https://github.com/AI-Gen-AI/C2Pro/issues/936). **Problem evidence:** 2026-10-08 read-only synthetic B review; exactly seven per-risk `clause_ref/confidence` null values while `confidence_score=0.9` is artifact-level; a false contract-corruption/ambiguity assertion on §5.2; persisted revision-bound A=9 and B=7 clauses incorrectly presented as "0 extracted" under unresolved trusted-current; all-or-nothing review card; graph shows "moderate" and "Model-backed" without corresponding current trustworthy evidence.

**Mapping policy:** The product MASTER has **exactly eight** canonical Product WBS planes. This cross-cutting campaign creates **no ninth WBS**; every task maps to an existing plane. Review foundations are governed by ADR-020/026, evidence truth by ADR-022/013/015/016, source linking by #713, P0c by #686 and Risk Register scope by #836. Existing P2 rich Actions/HITL priority is **not** silently globally promoted by the urgent P0 integrity defects.

| Task / GitHub issue | Priority / existing PWBS | Planned scope | Exit test / acceptance |
|---|---|---|---|
| [PQ-HITL-01 / #937](https://github.com/AI-Gen-AI/C2Pro/issues/937) | P0 / `PWBS-ACT-HEALTH` | Ground critique against contractual source; distinguish genuine corruption from ordinary terms and valid titles. | Adversarial fixtures for LD/However/Conversely, §5.2, correct/missing legal source references. |
| [PQ-HITL-02 / #938](https://github.com/AI-Gen-AI/C2Pro/issues/938) | P0 / `PWBS-ACT-HEALTH` | Evidence citation bindings, per-risk optional clause_ref and honest per-risk confidence. | Risk-confidence is distinct from document confidence and Coherence; unknown stays null. |
| [PQ-HITL-03 / #939](https://github.com/AI-Gen-AI/C2Pro/issues/939) | P0 / `PWBS-OPS-TRUST` | Explain trusted-current unresolved vs persisted historical/proposed revision evidence. | A=9 clauses, B=7 clauses shown in scoped read-only panels; no proposed-to-trusted leakage; history never says 0 extracted misleadingly. |
| [PQ-HITL-04 / #940](https://github.com/AI-Gen-AI/C2Pro/issues/940) | P1 / `PWBS-ALERTS-ACTIONS-HITL` | Per-finding decision/audit/corrections plus guarded final exact-candidate settlement. | Fail-closed on stale digest/row/thread/fence; no partial TRUSTED; independent ADR/design review. |
| [PQ-HITL-05 / #941](https://github.com/AI-Gen-AI/C2Pro/issues/941) | P1 / `PWBS-ALERTS-ACTIONS-HITL` | Readable executive summary, segmented findings and evidence-first reviewing UX. | Review one issue at a time, source next to explanation, accessible states, final sign-off distinct. |
| [PQ-HITL-06 / #942](https://github.com/AI-Gen-AI/C2Pro/issues/942) | P1 / `PWBS-OPS-TRUST` | Verified source deep-links and multi-clause provenance. | Clause/quote/revision exact highlight or explicit fallback; coordinate with #713. |
| [PQ-HITL-07 / #943](https://github.com/AI-Gen-AI/C2Pro/issues/943) | P1 / `PWBS-ALERTS-ACTIONS-HITL` | Separately display extracted data, AI risk findings, alerts and graph links; truthful confidence/priority. | No 'moderate' from zero alerts; deterministic copy not 'Model-backed'; no fake data. |
| [PQ-HITL-08 / #944](https://github.com/AI-Gen-AI/C2Pro/issues/944) | P1 / `PWBS-TEMPORAL-CHANGE` | Revision-aware evidence history and What Changed timeline semantics. | Uploaded/parsed/extracted/proposed/review-needed/trusted distinct; #686 acceptance independent. |
| [PQ-HITL-09 / #945](https://github.com/AI-Gen-AI/C2Pro/issues/945) | P0 / `PWBS-OPS-TRUST` | Golden negative+positive cases and independent quality acceptance gates. | Regression QA includes §5.2 hallucination, 9+7 unresolved scope, null confidence, stale checkpoints and no fake P0c PASS. |
| [PQ-HITL-10 / #946](https://github.com/AI-Gen-AI/C2Pro/issues/946) | P2 / `PWBS-ALERTS-ACTIONS-HITL` | Advanced cross-evidence 2D/3D graph and exploration (deferred). | Only after trusted-source/evidence graph semantics proven; 3D optional. |

### 13.1 Dependency graph and execution waves

- **W0 correctness + RED regression baseline:** #937 (grounded critique), #938 (clause/evidence/confidence), #939 (truthful current/proposed/historical viewport), #945 (golden adversarial tests).
- **W1 governed contracts:** #940 (granular item-level HITL and atomic final settlement) depends on #937/#938; #942 (source addressability) depends on #938.
- **W2 UX / projection:** #941 (summary-first review) depends on #939/#940/#942; #943 (graph/alerts semantics) depends on #938/#939; #944 (history/evolution parity) depends on #939/#942.
- **W3 product assurance:** #945 cross-checks the implemented surfaces in focused backend/frontend/integration/E2E and independent review. CI green is necessary but never a production validation claim.
- **W4 optional/deferred:** #946 advanced 2D/3D graph depends on #938/#939/#942/#943/#944/#945; no 3D-first distraction while user-visible semantics are wrong.

**First bounded implementation candidate:** #939. Its scope is read-only honest evidence-state presentation and version-scoped retrieval; it does **not** require changing the HITL resume machine. Issue #937 may run as an independent backend-quality lane once exact module/fixtures are frozen.

### 13.2 Acceptance and safety invariants

1. An extraction with 9 stored A clauses + 7 stored B clauses cannot be falsely called "0 extracted" solely because current trusted projection is intentionally unresolved. Scope and state labels must distinguish `TRUSTED_CURRENT`, `PROPOSED`, `HISTORICAL`, `UNRESOLVED`, `NOT_EXTRACTED`, and `LOAD_ERROR`.
2. Model critique must provide verifiable, revision-bound sources, avoid fabricated placeholder corruption, and permit `UNKNOWN` and reviewer correction. No model claim is promoted to a verified finding solely because the critic wrote it.
3. `RiskItem.confidence`, whole-document `confidence_score`, evidence-confidence, severity/likelihood, Health, Coherence and Alerts are different concepts. No synthetic score or source reference.
4. Per-finding `CONFIRMED/CORRECTED/DISMISSED/NEEDS_INFO` choices create an audit trail and possibly a new immutable candidate. They **never** cause partial `TRUSTED` state. Final human settlement is a separate approval over exact candidate hash/version, review row, thread/checkpoint and live generation/fence with idempotency.
5. In a graph with no active linked alerts, priority is `UNKNOWN` absent independent evidence, not "moderate"; any deterministic generated explanation is labeled as such rather than "Model-backed".
6. Every source citation must resolve to exact semantic evidence, verified source span or honest document fallback, otherwise explicit unresolved; support multi-clause risks and version-scoped access.
7. Preserve P0b accepted evidence, no direct main writes or autonomous merges; no implicit privilege grants, secret access, production data repair, forced review approval or revision-B reprocessing. #686 keeps `P0C_QUALIFICATION=PENDING` until its own independent evidence validator and explicit Product Control reconciliation; #687 remains blocked.
8. Implementation states advance independently through `PLANNED → PR/CI → MERGED → DEPLOYED → PROD_VALIDATED` (only when separately evidenced), not by owner approval of a roadmap.

**Design question to freeze before coding #940:** if quality defects are found, individual corrections compose a new **immutable version**. The existing per-document HITL pause must not be auto-transformed into per-item acceptance or bypassed. Approval behavior, legacy review compatibility, lock ordering and exact fence consistency require a dedicated reviewed decision record/ADR.

### 13.3 Verified execution checkpoint — 2026-10-08

**State of the code, not the production lifecycle:** repository `main` after #949: `9144777ff8dc4a76a1b203a9707da84a7d0c2020`. Merged PR evidence: [#947](https://github.com/AI-Gen-AI/C2Pro/pull/947) (MASTER), [#948](https://github.com/AI-Gen-AI/C2Pro/pull/948) (honest empty-state copy), [#950](https://github.com/AI-Gen-AI/C2Pro/pull/950) (bounded source to critic), [#954](https://github.com/AI-Gen-AI/C2Pro/pull/954) (collapsible *unverified* critique observations), [#949](https://github.com/AI-Gen-AI/C2Pro/pull/949) (honest graph priority and deterministic provenance label). Each was merged only after its own full PR CI concluded green with an exact-head safeguard. **MERGED is not DEPLOYED or PROD_VALIDATED.**

| Task | Current delivery state | What is demonstrably missing |
|---|---|---|
| **01** #937 | **PARTIAL**, #950 merged | Typed, auditable critique claim → exact source-span validation, justified positive/negative corruption fixtures |
| **02** #938 | **ACTIVE / HOLD**, [#953](https://github.com/AI-Gen-AI/C2Pro/pull/953) CI green, **unmerged** | Calibrated confidence provenance; multi-clause citation mapping; confidence-routing policy and reviewer capacity; integration compatibility |
| **03** #939 | **PARTIAL**, #948 merged | Real read-only selector/projection distinguishing A=9/B=7 and trusted-current, RLS/API/UX parity |
| **04** #940 | **ACTIVE DESIGN**, [review contract](https://github.com/AI-Gen-AI/C2Pro/issues/940#issuecomment-6050088142) | Tenant-scoped append-only per-finding decisions, correction candidate versioning, exact atomic final settlement |
| **05** #941 | **PARTIAL**, #954 merged | Evidence-linked executive summary, individual review actions and E2E; expandable prose is not granular HITL |
| **06** #942 | **PLANNED** | Verified source→clause/revision/page/span deep-links, honest unresolved fallback |
| **07** #943 | **PARTIAL**, #949 merged | Full extracted entities / contractual risk / active alert taxonomy and integrated trusted/proposed scoping |
| **08** #944 | **PLANNED** | Exact lifecycle timeline and What Changed API↔UI semantics including pending/needs_review |
| **09** #945 | **PLANNED** | Independent golden tests, security/concurrency regressions, product-quality acceptance |
| **10** #946 | **DEFERRED** | 2D/3D advanced evidence graph; not part of P0 exit |

**Critical HOLD for #953:** RiskExtractionCandidate lacks actual per-risk confidence values; replacing invented 0.9 with `null` forces the N12 human-review path for unassessed contract risks. This is the truthful fail-closed option, but without a measured-confidence producer and capacity/routing design it may pause virtually every contract. [#938 technical finding](https://github.com/AI-Gen-AI/C2Pro/issues/938#issuecomment-6050160395). No merge on green CI alone until independent operational review, exact-case tests and policy decision. No fabricated score or silent bypass is an acceptable workaround.

### 13.4 GOAL — observable finished product, not a count of PRs

A reviewer opens a revision-specific contract analysis and can:

1. **See an accurate executive overview**: number of risks, critique observations, evidence quality and pending decisions, each distinctly labeled `PROPOSED`, `TRUSTED`, `HISTORICAL`, `UNKNOWN` or `NOT_EXTRACTED` as supported. A=9/B=7 stored clauses must never be confused with zero trusted-current clauses.
2. **Inspect each observation independently**: factual claim, AI interpretation, verified original contract quote with exact clause/revision locator or an honest unresolved indicator, impact/category and why it matters. Ordinary `LD`, `However`, `Conversely`, the valid title and §5.2 fourteen-day obligation must not be called corrupt without verified contradiction.
3. **Record each human decision separately**: confirm, dismiss, request info or propose a correction, with reviewer identity, evidence, reason and immutable audit/CAS, without promoting individual observations into trusted state.
4. **Settle the exact final candidate**: compose any corrections into an immutable new version/hash, explicitly approve or reject the whole candidate only after blocking findings are addressed, then resume under the original tenant/row/thread/checkpoint/generation/fence trust controls. Stale/replayed approvals fail closed.
5. **Navigate useful evidence and timeline**: extracted entities/clauses, AI risks, approved active alerts, linked relationships, changes and historical snapshots are semantically distinct. Missing evidence never invents a risk, score, change or moderate priority. Review and UI are usable on mobile.
6. **Pass independent quality and production qualification**: adversarial golden fixtures + backend/FE/security/RLS/concurrency/E2E all green; accepted synthetic end-user demonstration; separate `#686 P0c` five-evidence assertions and, only then, `#687 P0d` Current State assertions on exact deployed identity, with explicit Product Control review. A green PR never substitutes for these gates.

**Implementation sequence (dependency-bound; no invented target date):**

- **G1 — Code truth:** #949 merged; #948/#950/#954 preserved. Rebase remaining work against current main only after verifying diff and regression.
- **G2 — Confidence/source policy:** #938/#953 measured-vs-unmeasured risk policy and workload gate; #937 typed source-validation and #945 RED+GREEN adversarial fixtures. Preserve accepted ADR-020/026 controls.
- **G3 — Evidence truth:** #939 real tenant-scoped historical/proposed/trusted viewer; #942 exact/multi-clause source addresses and no fabricated PDF highlights.
- **G4 — Granular review authority:** #940 design/ADR freeze, append-only finding decision ledger, tenant-scoped RLS, CAS/idempotency, versioned corrections, explicit whole-candidate settlement through existing N13 trust boundary.
- **G5 — Operator experience:** #941 summary/evidence-linked per-item UI; #943 complete graph taxonomy and honest priority; #944 lifecycle timeline and What Changed parity.
- **G6 — Quality/acceptance:** #945 golden/negative/positive + independent review, followed by a separately authorized, bounded production qualification of #686 (no B reprocess/forced approval) and then #687. Product Control alone can authorize any lifecycle promotion. #946 is deferred.

**GOAL current status: IN PROGRESS / NOT COMPLETE / NOT PROD_VALIDATED.** The real synthetic revision B remains paused awaiting appropriate human review; no retroactive edit, blind acceptance, synthetic evidence promotion or 3D-first diversion is authorized.


**Related operational issue:** [#686 P0c](https://github.com/AI-Gen-AI/C2Pro/issues/686) remains on HITL review hold for existing synthetic revision B; no automatic retry or approval is within this campaign.

### 13.5 GOAL por horizontes — corto, medio y largo (actualización 2026-10-08)

El **GOAL definitivo** no es cerrar issues o sumar PR: es que una persona profesional pueda convertir contratos y documentación real en decisiones de compras/proyectos **justificadas, trazables, seguras y útiles**, sin presentar texto inventado, puntuaciones sin evidencia o candidatos `PROPOSED` como `TRUSTED`. Los horizontes siguientes representan **hitos y dependencias**, no fechas de entrega prometidas. Son el espejo de `product_quality_hitl_2026_10_08.goal_horizons` del MASTER YAML.

| Horizonte | Capacidad objetivo | Criterio de salida |
|---|---|---|
| **CORTO — integridad del análisis + HITL seguro** | Cada riesgo/observación puede verse contra su revisión y evidencia original; confianza no medida sigue `UNKNOWN`; un humano puede preparar y auditar decisiones por hallazgo sin conceder confianza parcial. | Pruebas negativas/positivas sobre evidencia, fuente, tenant/RLS, identidad humana, CAS/idempotencia, digest, generación/fence/checkpoint; CI verde y revisión de seguridad independiente. |
| **MEDIO — recorrido completo de operador + P0/P1 cualificado** | Resumen contractual legible, fuentes navegables, corrección versionada, revisión individual y **firma humana final del candidato completo**; What Changed/Current State y Project Controls/Coherence integrados. | E2E de contratos y revisiones reales, validación adversarial; #686 P0c con evidencias reales y solo después #687 P0d; WBS único y autorizado. |
| **LARGO — C2Pro como SaaS de ejecución** | Desde contrato/proyecto al plan de compras, paquetes WBS, BoQ/RFQ, comparación de ofertas, adjudicación, seguimiento y visión PMO/portfolio. | Pilotos reales y métricas de calidad/valor, multi-tenancy y seguridad, operación duradera, gobierno de comunicaciones y acciones; escalado solo tras evidencias. |

**Corto (próximos gates, no plazo fijo).** Cerrar técnicamente #937 (críticas N12 tipadas, citas originales verificadas, casos adversariales §5.2) y #938/#953 (confianza por riesgo **realmente medida** y política HITL que no sature la operación; #953 permanece en HOLD pese a CI verde). Demostrar en #939 el acceso real a cláusulas A=9 y B=7 sin mezclarlas con la proyección confiable. En #940, completar la autoridad de escritura de decisiones: roles humanos y tenant autenticados, caso real PostgreSQL `NO BYPASSRLS`, operaciones simultáneas CAS/idempotencia, pertenencia verificable del riesgo al candidato y protección del control de generación/fence. Preparar los primeros golden tests #945. **No exponer endpoint de escritura por el mero hecho de que el writer exista: #980 exige autorización por proyecto, concurrencia real y revisión de seguridad antes de habilitarlo.**

**Medio (integración y aceptación).** Producir un candidato corregido **nuevo e inmutable**, exigir decisión final humana de **todo el hash/version exactos** a través de #714/#758/N13, y completar la interfaz por hallazgo (#941). Resolver evidencias navegables por cláusula/revisión/span con degradación honesta (#942), separar entidades/riesgos/alertas reales (#943) y hacer coherente la línea temporal de vida de revisiones (#944). Pasar QA independiente #945 y cualificar por separado #686 P0c y después #687 P0d; desarrollar P1 Project Controls sobre **una sola WBS**, baseline/change, presupuesto, cronograma, stakeholders y Coherence multicapa. Ningún PASS de CI otorga `PROD_VALIDATED`.

**Largo (visión de producto).** Habilitar P2 Procurement sobre la única autoridad WBS (Procurement Plan, BoQ, RFQ, ofertas, evaluación, adjudicación, obligaciones y acciones), comunicaciones y aprobaciones con HITL; P3 ejecutivo/PMO y portfolio con informes y trazabilidad. Validar en pilotos los ahorros y calidad reales **sin prometer porcentajes no medidos**. El grafo 2D/3D #946 sigue opcional y diferido hasta demostrar valor para el operador.

**Checkpoint exacto del código:** a fecha 2026-10-08 están **MERGED** las PR #956 (evidencia read-only), #961 (contrato dominio HITL), #962 (localizador literal de citas, **no** certificación jurídica), #966 (esquema de auditoría), #970 (writer provisional no enroutado), #971 (pertenencia de riesgo al candidato), #974 (candidato propuesto vivo y pertenencia) y #975 (identidad de revisor autenticado), y #977 (candidato exacto derivado de la revisión del servidor, sin endpoint HTTP). Todos son **cortes parciales**, no producto desplegado/validado. [#967](https://github.com/AI-Gen-AI/C2Pro/pull/967) está CLOSED UNMERGED, sustituida por #970; [#977](https://github.com/AI-Gen-AI/C2Pro/pull/977) está MERGED (commit `fadb59a3`), tras CI verde y revisión independiente de Claude sobre las dependencias reales; el futuro endpoint #980 sigue bloqueado por política de acceso por proyecto y pruebas adversariales RLS/CAS. [#953](https://github.com/AI-Gen-AI/C2Pro/pull/953) sigue DRAFT/HOLD por operabilidad de confianza nula. El issue #940 se muestra CLOSED, pero **sus criterios completos no han sido verificados**: la clasificación de producto sigue ACTIVE/PARTIAL hasta corregir dicha discrepancia.

**Invariantes invariables:** ocho planes Product WBS, `PROPOSED ≠ TRUSTED`; confianza no medida = UNKNOWN; cita localizada no valida interpretación legal; sin autoaprobación ni aprobación parcial; sin reprocess o aceptación artificial de B; sin cambios de producción ni estado `PROD_VALIDATED` por merge; #686 y #687 solo tras sus evidencias independientes. Véase [programa #936](https://github.com/AI-Gen-AI/C2Pro/issues/936).


### 13.6 Plan de entrega por subtareas — QUÉ antes de CÓMO (propuesta 2026-10-08)

**Autoridad:** espejo de `product_quality_hitl_2026_10_08.delivery_specification` en [MASTER machine](../../validation/product/c2pro-master-product-control-v1.yaml), con [SDD de ejecución y aceptación](./pq-hitl-2026-01-delivery-spec-v1.md). **Pendiente de fusionar/revisar: este texto no constituye actividad aceptada en main.** Se mantienen los 10 padres PQ-HITL existentes (#937–#946) y ocho Product WBS, sin crear una WBS/épica paralela.

**North Star:** revisión documental específica → fuente contractual trazable y crítica sin alucinaciones → acciones humanas por hallazgo con razón/identidad/auditoría → candidato PROPOSED corregido e inmutable → aprobación final independiente de candidato completo y hash exacto → Health, Coherence, What Changed y Current State coherentes y honestos. Los horizontes Project Controls/Coherence → Procurement → PMO siguen sujetos a sus PWBS y autoridad independientes.

**Protocolo de planificación:** primero identificar el resultado/criterio de salida y su categoría FEATURE/DEFECT/SECURITY/QA/INFRA/PRODUCT DECISION; después formalizar Given/When/Then y SDD/ADR si procede, dividir unidades >4 días o que crucen nuevas autoridades, verificar dependencias y WORK válido, ejecutar RED→GREEN→REFACTOR, obtener QA+security+revisión principal independiente, y reconciliar la tarea. Una PR sólo aporta evidencia; MERGED no significa ACCEPTED ni PROD_VALIDATED.

| Subtarea / parent issue | Producto/deliverable | Rol · tamaño · prioridad | Estado | Test de aceptación |
|---|---|---|---|---|
| PQ-HITL-09.1 / [#945](https://github.com/AI-Gen-AI/C2Pro/issues/945) | QA GOLDEN FIXTURE BASELINE | qa · M · P0 | MERGED_UNACCEPTED | Synthetic §5.2, LD, However, valid title, 183d, 5% of EUR 132500 and A9/B7 with exact expected findings and UNKNOWN semantics; deterministic RED before future changes; older draft fixes remain unqualified. |
| PQ-HITL-01.1 / [#937](https://github.com/AI-Gen-AI/C2Pro/issues/937) | CRITIQUE OK OBSERVATION FAIL CLOSED | implementation_lead · S · P0 | IN_REVIEW_UNMERGED | N12 OK + nonempty source-located but UNVERIFIED quality claim cannot auto-trust; typed quote reaches N13 and bounded retry feedback; UI clearly unverified; unit+FE+exact-head CI. |
| PQ-HITL-01.2 / [#937](https://github.com/AI-Gen-AI/C2Pro/issues/937) | CRITIQUE SEMANTIC CLAIM GROUNDING | implementation_lead · M · P0 | BLOCKED | Claim truth distinct from quote location; §5.2 cost/time interpreted correctly; genuine source corruption vs normal English discriminated; contradictory/unknown routed, never VERIFIED from literal match. |
| PQ-HITL-01.3 / [#937](https://github.com/AI-Gen-AI/C2Pro/issues/937) | RETRY AND FALSE POSITIVE QUALIFICATION | qa · S · P0 | PLANNED | Measure grounded concern recall/false corruption labels, retry convergence, bounded feedback; record unsupported findings and no silent passing after exhausted retry. |
| PQ-HITL-02.1 / [#938](https://github.com/AI-Gen-AI/C2Pro/issues/938) | RISK CLAUSE EVIDENCE LINKS | implementation_lead · M · P0 | PLANNED | Each risk has exact revision-bound clause/quote/source binding or explicit unresolved; no made-up clause_ref; persist and query tenant-scoped. |
| PQ-HITL-02.2 / [#938](https://github.com/AI-Gen-AI/C2Pro/issues/938) | CONFIDENCE PROVENANCE AND CAPACITY | orchestrator · M · P0 | BLOCKED | Decide calibrated per-risk confidence producer OR explicit UNKNOWN with bounded human workload and safe routing; quantify review load on fixtures; keep #953 HOLD until governance sign-off. |
| PQ-HITL-02.3 / [#938](https://github.com/AI-Gen-AI/C2Pro/issues/938) | MULTICLAUSE RISK TRACEABILITY | implementation_lead · M · P0 | PLANNED | One risk can point to 6.1+6.3+6.4 independently without fabricating geometry, surviving version switch and candidate hash replay. |
| PQ-HITL-03.1 / [#939](https://github.com/AI-Gen-AI/C2Pro/issues/939) | REVISION SCOPED READ PROOF | qa · S · P0 | IN_PROGRESS | Read-only tenant-scoped A=9 B=7 parsed clauses appear as historical/proposed; 0 trusted-current must not show '0 extracted'; API/UI count parity and no cross-tenant leak. |
| PQ-HITL-03.2 / [#939](https://github.com/AI-Gen-AI/C2Pro/issues/939) | TRUSTED PROPOSED EMPTY STATES | implementation_lead · S · P0 | PLANNED | TRUSTED_CURRENT/PROPOSED/HISTORICAL/UNRESOLVED/NOT_EXTRACTED/LOAD_ERROR distinct; relogin and bad-network states tested without promoting proposed Health/Coherence. |
| PQ-HITL-04.1 / [#940](https://github.com/AI-Gen-AI/C2Pro/issues/940) | DECISION STATE MACHINE SDD AND ADR | orchestrator · M · P0 | BLOCKED | Freeze per-risk and critique types, CONFIRMED/CORRECTION_PROPOSED/DISMISSED/NEEDS_INFO, immutable versions, atomic final approval authority, migration/backward compatibility and threat model; independent principal design review. |
| PQ-HITL-04.2 / [#940](https://github.com/AI-Gen-AI/C2Pro/issues/940) | NONBYPASS LEDGER DB PRINCIPAL | implementation_lead · M · P0 | IN_REVIEW_UNMERGED | Separately authenticated dedicated LOGIN+pool, NO BYPASSRLS/createrole/replication/parameter trigger bypass; real PostgreSQL positive/negative, tenant GUC boundary, existing-event replay; no prod grants without owner authorization. |
| PQ-HITL-04.3 / [#940](https://github.com/AI-Gen-AI/C2Pro/issues/940) | LEDGER CONCURRENT CAS REPLAY | qa · M · P0 | BLOCKED | Real DB concurrent same/different idempotency keys, stale row/digest/gen/fence/checkpoint, cross-tenant denial, actual seeded replay and conflict semantics; no trust promotion. |
| PQ-HITL-04.4 / [#940](https://github.com/AI-Gen-AI/C2Pro/issues/940) | FINDING DECISION HTTP PROJECT ACL | implementation_lead · M · P1 | BLOCKED | Every human finalize_v3 entry point (including legacy /hitl/resume and approve) requires server-derived reviewer identity, project/Contract Manager ACL, candidate membership, typed request and 403/409/422 negative tests; keep disabled until safe principal. |
| PQ-HITL-04.5 / [#940](https://github.com/AI-Gen-AI/C2Pro/issues/940) | IMMUTABLE CORRECTION COMPOSER | implementation_lead · M · P1 | BLOCKED | Append actions, derive new immutable proposed candidate under source review-row lock and expected_ledger_revision CAS; reject/recompute if an event R+1 intervenes before A-to-B supersession; preserve lineage and idempotent ADR-020 approved-correction golden handoff, never auto-promote models. |
| PQ-HITL-04.6 / [#940](https://github.com/AI-Gen-AI/C2Pro/issues/940) | FINAL EXACT CANDIDATE SETTLEMENT | implementation_lead · M · P0 | BLOCKED | Separate authenticated human whole-candidate sign-off #714/#758 binds exact row/hash/version/thread/checkpoint/gen/fence and expected_ledger_revision; same locked transaction verifies all terminal finding decisions; atomic commit or no TRUSTED, replay/reject/fault fail closed. |
| PQ-HITL-05.1 / [#941](https://github.com/AI-Gen-AI/C2Pro/issues/941) | REVIEW CARD SOURCE WITNESS UX | implementation_lead · S · P1 | IN_REVIEW_UNMERGED | Show typed claim/quote/location/revision/unverified in review card by default, no JSON requirement and no false per-item action; FE tests for located and unavailable. |
| PQ-HITL-05.2 / [#941](https://github.com/AI-Gen-AI/C2Pro/issues/941) | INDIVIDUAL REVIEW ACTION UI | implementation_lead · M · P1 | BLOCKED | Per-item evidence left/actions right with confirmed/corrected/dismissed/needs-info, reason mandatory where needed, keyboard/focus/permissions/offline, no bulk auto-approval. |
| PQ-HITL-05.3 / [#941](https://github.com/AI-Gen-AI/C2Pro/issues/941) | EXEC SUMMARY AND FINAL SIGNOFF UX | implementation_lead · M · P1 | BLOCKED | Show pending/accepted/unknown/source quality and corrected candidate diff, separate final approve/reject only when every blocking decision resolved; E2E walkthrough. |
| PQ-HITL-06.1 / [#942](https://github.com/AI-Gen-AI/C2Pro/issues/942) | SOURCE LOCATOR CONTRACT | implementation_lead · M · P1 | PLANNED | Freeze revision/clause/span/page/bbox hierarchy with exact->raw span->document fallback->unresolved; forged refs denied with tenant ACL; no made-up page. |
| PQ-HITL-06.2 / [#942](https://github.com/AI-Gen-AI/C2Pro/issues/942) | SOURCE DOCUMENT DEEP LINKS | implementation_lead · M · P1 | BLOCKED | Click citation resolves to same revision and verified span or labeled fallback; multi-clause URLs work across A/B; 404 and permission states tested. |
| PQ-HITL-07.1 / [#943](https://github.com/AI-Gen-AI/C2Pro/issues/943) | ENTITIES RISKS ALERTS TAXONOMY | implementation_lead · S · P1 | PLANNED | Extracted clause/entity vs interpreted risk vs active alert separated, unknown priority not moderate due zero links, deterministic provenance honestly labeled. |
| PQ-HITL-07.2 / [#943](https://github.com/AI-Gen-AI/C2Pro/issues/943) | GRAPH RELATIONSHIP TRUST SCOPE | qa · M · P1 | BLOCKED | No ghost graph edge/node, 0 alerts != 0 risks, trusted graph excludes proposed, proposed preview explicitly untrusted; API/UI snapshots and tests. |
| PQ-HITL-08.1 / [#944](https://github.com/AI-Gen-AI/C2Pro/issues/944) | REVISION EVENT TIMELINE PARITY | implementation_lead · M · P1 | PLANNED | Uploaded/parsed/extracted/proposed/review pending/rejected/trusted states shown per source revision; no historical '0 clauses' lie, relogin stable. |
| PQ-HITL-08.2 / [#944](https://github.com/AI-Gen-AI/C2Pro/issues/944) | WHAT CHANGED TO CURRENT STATE CONSISTENCY | qa · M · P1 | BLOCKED | What Changed and Current State agree on source/revision/proposed-vs-trusted; P0c #686 qualified separately before P0d #687, no B replay as test shortcut. |
| PQ-HITL-09.2 / [#945](https://github.com/AI-Gen-AI/C2Pro/issues/945) | SECURITY AND ADVERSARIAL REGRESSION | security · M · P0 | BLOCKED | Run tenant/RLS, prompt injection, stale checkpoint, duplicate decision, candidate hash, forged refs, false confidence/graph, no partial TRUSTED tests with exact result evidence AFTER all producing features are implemented; rerun on their final integrated heads. |
| PQ-HITL-09.3 / [#945](https://github.com/AI-Gen-AI/C2Pro/issues/945) | GOLDEN OPERATOR END TO END | qa · M · P0 | BLOCKED | Realistic contract journey upload->extract->review each finding->correct->separate final approval->Current State and Coherence, verify persistent relogin, unknowns and #686/#687 sequencing. |
| PQ-HITL-09.4 / [#945](https://github.com/AI-Gen-AI/C2Pro/issues/945) | PRODUCT ACCEPTANCE AND RELEASE PACKET | orchestrator · S · P0 | BLOCKED | Release evidence binds implementation task IDs, exact merged SHA, CI, independent principal, E2E, deployment SHA, open defects and owner UAT decision; no self-PROD_VALIDATED. |
| PQ-HITL-10.1 / [#946](https://github.com/AI-Gen-AI/C2Pro/issues/946) | ADVANCED GRAPH OPTIONAL SPIKE | specialist · S · P2 | DEFERRED | Only after measured user benefit of 2D+ accessible graph; 3D requires separate owner choice and no phantom links. |

**Asignación vinculada al MASTER (2026-10-09, sin nuevo backlog):** `PQ-HITL-03.1` / #939 queda **IN_PROGRESS**, responsable funcional **QA**: #956/#996/#997/#999 fusionadas como cortes parciales y no aceptados (#999 commit `4ea4c11d`, CI y Codex PASS, Railway SUCCESS); SQL de solo lectura confirma A=9/B=7 vinculadas al tenant/proyecto/documento y B PROPOSED sin TRUSTED activo. Falta prueba integrada de API/interfaz autenticadas, ACL real por proyecto/RLS y persistencia tras relogin; aceptación de 03.1 pendiente. `PQ-HITL-04.4` / [#980](https://github.com/AI-Gen-AI/C2Pro/issues/980) queda asignada a **implementation_lead**, **BLOCKED** hasta completar 04.1/04.3 y revisión de seguridad: Clerk es la autoridad de altas/invitaciones/miembros/roles de organización, sin nueva administración de usuarios C2Pro; C2Pro retiene exclusivamente ACL por proyecto/contrato/revisión y capacidades humanas `REVIEWER`/`APPROVER` sujetas a autorización explícita. Comprobar plan real de Clerk, derivación de rol (actual provisión USER y multi-organización), y proteger **todas** las rutas approve/reject/resume antes de habilitar escrituras. No permisos de producción, mutaciones de B, ni aceptación de producto implícita.

**Orden de gates y bifurcaciones:**

- **G0 — criterio antes que código:** 09.1 goldens sintéticos; descubrimiento aislado 02.2 confianza/capacidad; 03.1 API/UI read-only posible en paralelo.
- **G1 — veracidad:** 01.1→01.2→01.3; 02.1→02.3; 03.1→03.2. #953 permanece HOLD por riesgo de saturación HITL.
- **G2 — autoridad:** 04.1 SDD/ADR → 04.2 login/DB RLS → 04.3 concurrencia/replay → 04.4 API ACL. No habilitar writer con privilegios ni endpoint simplemente porque la PR pase.
- **G3 — experiencia completa:** 06.1→06.2 fuentes; 04.5→04.6 corrección/finalización; 05.1→05.2→05.3 UX; 07/08 semántica del grafo y línea temporal.
- **G4 — validación:** 09.2 seguridad → 09.3 E2E de producto → 09.4 Product Control/UAT. #686 P0c → #687 P0d son cualificaciones productivas separadas; revisión B HITL sigue pendiente.

**Registro de defectos, sin desviar el trabajo:**

| ID | Asociado | Severidad / estado | Cierre exigido |
|---|---|---|---|
| DEF-PQ-001 | 01.1 · [#960](https://github.com/AI-Gen-AI/C2Pro/pull/960) | P0 confianza · REMEDIATION_UNVERIFIED | `OK` con observación no pasa a trusted; feedback y source llegan a retry/N13, regresiones exact-head. |
| DEF-PQ-002 | 04.2 · [#985](https://github.com/AI-Gen-AI/C2Pro/pull/985) | P0 seguridad · REMEDIATION_UNVERIFIED | Login realmente restringido/pool, no trigger bypass, replay real y tests PG15/RLS/CAS. |
| DEF-PQ-003 | 02.2 · [#953](https://github.com/AI-Gen-AI/C2Pro/pull/953) | P1 diseño · OPEN/HOLD | Confidence por riesgo realmente medida y política humana sostenible, nunca confidence inventada. |
| DEF-PQ-004 | 03.1 · #939 | P1 verificación · OPEN | Prueba operador A=9/B=7 por revisión sin transformar PROPOSED en trusted ni afirmar 0 extraídas. |
| DEF-PQ-005 | 04.4 · [#940](https://github.com/AI-Gen-AI/C2Pro/issues/940) / [#988](https://github.com/AI-Gen-AI/C2Pro/pull/988) | P0 autorización · OPEN_SECURITY_HOLD | Las rutas de APPROVE y REJECT (`/hitl/resume`, `/queue/.../approve` y `/queue/.../reject`) deben exigir actor auténtico y project/Contract Manager ACL; tenant-only es insuficiente; tests negativos. |
| DEF-PQ-006 | 04.6 · [#940](https://github.com/AI-Gen-AI/C2Pro/issues/940) / [#988](https://github.com/AI-Gen-AI/C2Pro/pull/988) | P0 concurrencia · OPEN_CONCURRENCY_HOLD | La primera promoción a TRUSTED ocurre en N17 antes de finalize_v3: validar universo exhaustivo de hallazgos y expected_ledger_revision en ese primer commit o rediseñar la transacción; test concurrente. |
| DEF-PQ-007 | 04.5 · [#940](https://github.com/AI-Gen-AI/C2Pro/issues/940) / [#988](https://github.com/AI-Gen-AI/C2Pro/pull/988) | P0 concurrencia · OPEN_CONCURRENCY_HOLD | Composición A→B con revisión R del ledger debe bloquear la review row y comprobar CAS: una corrección R+1 invalida B y obliga recomponer; test real con dos transacciones. |

**Norma de bugs:** P0 bloquea sólo su ruta dependiente; P1 se repara acotadamente o se descompone; P2 se aparca. Incidencias de CI se diagnostican como infraestructura/flake/regresión, sin saltar gates. Máximo dos ciclos de diagnóstico sin hipótesis validable antes de BLOCKED y escalado. Cada defecto lleva reproducción, expected/observed, prioridad, parent task, responsable, aceptación y prueba. WIP: 1 tarea de integración material por workspace + hasta 2 lanes QA/especificación separadas.

**Roles y autoridad:** según `agents.md` raíz y `.c2pro/roles`: orchestrator, implementation_lead, qa, security, independent_reviewer, specialist. `roles/role_planner.md` y blackboard son históricos. `.c2pro/control/current.yaml` sigue `reconciled_idle`: un Product issue/PR/CI **no** sustituye WORK envelope ni autorización de workspace. Antes de ejecución, el dueño de `.c2pro` debe asignar `.c2pro/work/` válido y verificar workspace/branch/base SHA; si el esquema Product aún no lo permite, `EXECUTION_BLOCKED_WORK_ENVELOPE` con escalado al planner. DEV-14 es deuda non-blocking únicamente para otros trabajos con envelope válido, jamás waiver. Revisión independiente para merge; CI != aprobación. Sin changes PROD, reprocess/aprobación de B, noveno Product WBS o despliegue.
