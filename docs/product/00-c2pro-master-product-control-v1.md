# C2Pro Master Product Programme Control — v1

**Status:** Reconciliation snapshot (read-only) · **Date:** 2026-08-27
**reconciled_against_main_sha:** `85caa0ccd0739127b279c93a9c6e979f0e340d21` (repo baseline this reconciliation ran against — main after #576 P0b-L4-3 and #577 — **not** a live "current main" claim) · **deployed_runtime_sha:** `UNVERIFIED` (confirm via Railway deploy log)
**Machine-readable source of truth:** [`validation/product/c2pro-master-product-control-v1.yaml`](../../validation/product/c2pro-master-product-control-v1.yaml)

> This is the **PRODUCT** control plane — *what C2Pro is and how far each capability is realized*.
> It is **distinct from** the **development-execution** plane in [`.c2pro/`](../../.c2pro) (work-queue, roles,
> review-policy, authority gates). Execution authority, merges, and runtime mutations remain governed by
> `.c2pro/control` (**human merge; no direct main/prod mutation**). This plane is the target/state ledger
> those work-envelopes are measured against — **not** a competing execution plane.

> **Control integrity:** the block below is **generated from the YAML** (`check_control_parity.py --emit`).
> The checker parses the YAML, **validates every ADR/WBS status against the per-field enums**, and compares
> these exact values against the YAML — a contradictory or missing value **fails**. **Edit the YAML first**,
> then re-emit this block. Do not hand-edit it.

<!-- CANONICAL-CONTROL:START (generated from the YAML by validation/product/check_control_parity.py --emit; do not hand-edit) -->
```control
reconciled_against_main_sha=85caa0ccd0739127b279c93a9c6e979f0e340d21
deployed_runtime_sha=UNVERIFIED
reliability_operability_baseline=CLOSED
product_value_delivered=false
current_product_wedge_id=P0b-single-document-health-activation
coherence.global_authoritative_cutover=NO
legacy_coverage.unmapped_open_legacy_items=0
adr.ADR-018.realization=WIRED
adr.ADR-018.deployment=DEPLOYED
adr.ADR-018.prod_validation=NOT_VALIDATED
adr.ADR-024.realization=WIRED
adr.ADR-024.deployment=NONE
adr.ADR-024.prod_validation=NONE
p0b.done_digest=9ae6adf0a63af690
p0b.invariant_ids=INV-1,INV-UX,INV-COH
p0b.slice.P0b-L4-1.status=DONE
p0b.slice.P0b-L4-2.status=DONE
p0b.slice.P0b-L4-3.status=DONE
p0b.slice.P0b-L4-4.status=PARTIAL
p0b.slice.P0b-L4-5.status=BLOCKED
p0b.residual_ids=P0b-R1-EVIDENCE-GRANULARITY
p0b.residual.P0b-R1-EVIDENCE-GRANULARITY.status=PLANNED
p0b.residual.P0b-R1-EVIDENCE-GRANULARITY.blocks=P0b-L4-5
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

**C2Pro is continuous, evidence-backed project & procurement intelligence** for construction/infrastructure contracts: **Health + relational Coherence + Change/Time intelligence + Risk + Alerts/Actions/HITL + Project Controls (schedule/cost/deliverables/WBS/BOM) + Procurement workflows (RfQ/BoQ/RACI/comms) + Executive intelligence (PMO reporting / Morning Briefing / portfolio).** Every surface is evidence-backed and honest: **Unknown renders null — never a fabricated zero/green** (INV-1, ADR-018). Coherence (ADR-009) is **one relational input** — the Contract subscore, available only with **≥2 reconcilable documents**; never the whole product, never a single-document headline.

**Current product wedge = P0b — Single-document Health activation** (`current_product_wedge_id: P0b-single-document-health-activation`; ADR-024 → ADR-018): value from document #1 (per-category coverage + intrinsic findings + `missing_data` + gap alerts + Health Vector). The wedge is the **entry point** to the North Star above, **not its definition**.

## 2. Current production position (honest — three separate facts)

- **`reconciled_against_main_sha`** = `85caa0cc` — the repo baseline this reconciliation was performed against (main after #576 / #577); **not** a live "current main" value (that is Git-derived and drifts on every merge).
- **`deployed_runtime_sha`** = **UNVERIFIED** — do **not** infer from main; confirm via the Railway deploy log (service `c2pro-api`/production). Equal to main **only** if Railway rebuilt after the #570 merge.
- **`observed_production_evidence`** (read-only, independent of any SHA): kuwait2 doc `c510de21` enqueue→worker→**SUCCESS** on the dedicated Railway Redis; `coherence_results` **15/15 rows `coherence-v1`** (0 v2); `coherence_v2_shadow` **1 row** (2026-08-07); `alerts.severity` = `public.alertseverity` (#567); ADR-004 circuit breakers in prod logs.

**P0a — Reliability & Operability Baseline = CLOSED** (`reliability_operability_baseline: CLOSED`). **`product_value_delivered: false`.** This proves the *plumbing*, not the *product*.

❌ **Not delivered to the user:** six-category Health decomposition from one document, per-category `{state, findings, missing_data}`, actionable gap alerts, user-visible Health Vector / score / findings / time / reporting. **Reliability ≠ product value.** The value the product exists to deliver (ADR-024 → ADR-018) is still open code work (P0b).

## 3. Corrected current claims (history preserved; current state corrected)

| Stale claim | Where | Corrected truth |
|---|---|---|
| "Phase 1 COMPLETE / functional for end users" | **Canonical** `C2PRO_MASTER_BACKLOG.md` lines 11–13 (main) | P0a reliability baseline CLOSED; product value NOT delivered. Legacy master now carries a **cold-reference banner** pointing here. |
| "All 18 ADRs / zero unimplemented" | Canonical backlog lines 15–17 (main) | ADRs are **accepted design**, not realized (§4). The "18-ADR audit" predates ADR-023/024 and conflates 3 ADR namespaces (§4a). |
| "No open code work for end users" | Phase 1 Completion Certificate | Single-document activation **is** the open work — P0b vertical epic — plus v2 cutover, Change-Impact wedge, Alerts/HITL, Procurement, Reporting. |

> **Correction (E):** an earlier draft claimed these strings survive only in non-canonical worktrees/archive. That was **false** — they are in the canonical backlog on `main`. They are preserved as history and now flagged by a banner.

## 4a. ADR namespaces (three overlapping numberings)

- **v3-canon** — `docs/architecture/decisions/ADR-004,009,013..024` (the v3.0 spine).
- **Foundational** — `docs/architecture/decisions/001..006` (modular-monolith, supabase, ai-arch, frontend-rules, test-strategy, post-reorg).
- **Coherence-era** — `docs/architecture/adr/ADR-001..003` (dead-code / versioning / alert-ledger; superseded by ADR-009).
- **Collision:** ADR-004 is **both** `004-frontend-layer-rules` **and** `ADR-004-circuit-breakers`. (Defect D8.)

## 4. ADR realization matrix (four separate status fields — pure enums; no compound)

Per-field enums (YAML `status_enums`): **design** ∈ {Accepted, Proposed, Implemented, Deferred}; **realization** ∈ {DESIGNED, SCAFFOLDED, WIRED, DEPLOYED, PARTIAL}; **deployment** ∈ {NONE, PARTIAL, DEPLOYED, BLOCKED, SHADOW_INERT}; **prod-validation** ∈ {NONE, PARTIAL, NOT_VALIDATED, PROD_VALIDATED}. v1/v2 are **structural subtracks**, never a compound string.

| ADR (ns) | Design | Realization | Deployment | Prod-valid | Key gap |
|---|---|---|---|---|---|
| 001 modular-monolith (found.) | Accepted | DEPLOYED | DEPLOYED | PROD_VALIDATED | — |
| 002 supabase-mvp (found.) | Accepted | DEPLOYED | DEPLOYED | PROD_VALIDATED | — |
| 003 ai-architecture (found.) | Accepted | DEPLOYED | DEPLOYED | PROD_VALIDATED | — |
| 004 frontend-layer-rules (found.) | Accepted | DEPLOYED | DEPLOYED | PROD_VALIDATED | collides w/ ADR-004 CB |
| 005 three-layer-test (found.) | Accepted | DEPLOYED | NONE | PROD_VALIDATED | — |
| 006 post-reorg (found.) | Accepted | DEPLOYED | DEPLOYED | PROD_VALIDATED | — |
| ADR-001 coherence-deadcode (coh-era) | Accepted | DEPLOYED | DEPLOYED | PROD_VALIDATED | historical |
| ADR-002 coherence-score-versioning (coh-era) | Accepted | DEPLOYED | DEPLOYED | PROD_VALIDATED | 15/15 prod rows `coherence-v1` |
| ADR-003 coherence-alert-ledger (coh-era) | Accepted | DEPLOYED | DEPLOYED | PROD_VALIDATED | — |
| ADR-004 circuit-breakers (v3) | Implemented | DEPLOYED | DEPLOYED | PROD_VALIDATED | collides w/ 004-frontend |
| **ADR-009 coherence (v3)** | Accepted *(v2-locked; DEMOTED)* | **PARTIAL** | **PARTIAL** | **PARTIAL** | v2 global cutover not demonstrated (§4b) |
| &nbsp;&nbsp;↳ ADR-009 **v1 subtrack** | — | DEPLOYED | DEPLOYED | PROD_VALIDATED | 15/15 prod rows v1 |
| &nbsp;&nbsp;↳ ADR-009 **v2 subtrack** | — | SCAFFOLDED | **SHADOW_INERT** | NONE | 0 v2 headlines in prod |
| ADR-013 typed-graph (v3) | Accepted | WIRED | DEPLOYED | PARTIAL | residual 017-06 |
| ADR-014 project-state (v3) | Accepted | DEPLOYED | DEPLOYED | PROD_VALIDATED | 014-08 residual |
| ADR-015 temporal (v3) | Accepted | SCAFFOLDED | PARTIAL | NONE | snapshots **inert** (Beat gap, P1-OPS) |
| ADR-016 change-impact (v3) | Accepted | SCAFFOLDED | NONE | NONE | L3 stub; not wired |
| ADR-017 projectgraph (v3) | Accepted | SCAFFOLDED | **BLOCKED** | NONE | flag-gated OFF; Tier-2 MAE stub |
| **ADR-018 health (v3, primary)** | Accepted *(PROMOTED P0-NOW)* | **WIRED** | DEPLOYED | **NOT_VALIDATED** | not surfaced; `coherence_subscore=None`; ADR-024 absent |
| ADR-019 alerts-actions (v3) | Accepted | SCAFFOLDED | NONE | NONE | build-gated |
| ADR-020 hitl (v3) | Accepted | SCAFFOLDED | PARTIAL | NONE | build-gated (spoofing fixed) |
| ADR-021 briefing (v3) | Deferred | SCAFFOLDED | NONE | NONE | deferred |
| ADR-022 contract-clarity (v3) | Accepted | WIRED | DEPLOYED | NOT_VALIDATED | not surfaced via activation |
| ADR-023 agentic (v3) | **Proposed** | DESIGNED | NONE | NONE | not built |
| **ADR-024 single-doc-activation (v3)** | Accepted *(VP 2026-08-22)* | **WIRED** | NONE | NONE | L4-1…L4-3 merged (domain → real single-doc assessment → N8 → `analyses.result_json` → lineage → `HealthVector.single_document_coverage`); L4-4 exposure **PARTIAL**. Open: **per-clause evidence granularity** + dedicated API acceptance + **L4-5 UI/prod validation** |

## 4b. Coherence runtime reconciliation (proven, read-only — observed history vs routing capability)

Bounded **read-only** production reconciliation performed 2026-08-27 (SELECT-only on prod `tcxedmnvebazcsaridge` + code path `coherence/router.py`). **Distinguish observed persisted history from routing capability** — do **not** claim v1 is the only scorer that *can* persist a headline:

- **`global_authoritative_cutover`: NO** — global authoritative v2 cutover has **not** been demonstrated.
- **`observed_persisted_history`: 15/15 V1** (`coherence_results`, 2026-08-07 → 2026-08-16).
- **`observed_v2_persisted_headlines`: 0.**
- **`canonical_canary`: ENABLED_FOR_1_TENANT** — ADR-017 scorer-substitution is a *routing capability* that **can** substitute the in-response headline for the enrolled tenant.
- **`v2_enabled_tenants`: 6** (shadow path flag); **`v2_orchestrator_shadow`: INERT_IN_OBSERVED_DATA** (`coherence_v2_shadow` = 1 historical row, 2026-08-07).
- **Legacy global-v2-authoritative claim: `NOT SUPPORTED BY CURRENT PROD EVIDENCE`.**

Supporting facts: global `COHERENCE_V2_SHADOW_MODE` default `True`, but the shadow guard needs **per-tenant v2 flag AND** the global setting (`router.py:848-851`); scorer path `router.py:741` `evaluate_coherence_async` (**v1**); canonical-canary (763) + v2 shadow (841) default OFF per tenant; `is_project_graph_enabled` per-tenant default off. **ADR-009 realization is therefore recorded PARTIAL** (v1 DEPLOYED+PROD_VALIDATED / v2 SCAFFOLDED-SHADOW_INERT); reconciliation **COMPLETE**.

## 5. Capability planes (8)

`ACT-HEALTH` · `COHERENCE-XDOC` · `TEMPORAL-CHANGE` · `ALERTS-ACTIONS-HITL` · `PROJECT-CONTROLS` · `PROCUREMENT` · `EXEC-REPORTING` · `OPS-TRUST`. (ADR mapping in the YAML.)

## 6. Product WBS (L2 epic per plane; realization = single enum; P0b→L4)

| WBS ID | Plane | Pri | Realization | Work | Exit gate (evidence-for-DONE) |
|---|---|---|---|---|---|
| **PWBS-ACT-HEALTH** | ACT-HEALTH | P0b | **PARTIAL** | **ACTIVE** | P0b-L4-5 PROD_VALIDATED (§7) |
| PWBS-COHERENCE-XDOC | COHERENCE-XDOC | P1 | **PARTIAL** *(v1 DEPLOYED / v2 SHADOW_INERT)* | PLANNED | v2 cutover (MAE+canary) or explicit v1-keep; cross-doc findings on ≥2-doc project |
| PWBS-TEMPORAL-CHANGE | TEMPORAL-CHANGE | P1 | **SCAFFOLDED** | PLANNED | snapshot capture running (Beat) + Change-Impact Report |
| PWBS-ALERTS-ACTIONS-HITL | ALERTS-ACTIONS-HITL | P2 | **SCAFFOLDED** | DEFERRED | build-gate lifted; ActionItem→CM HITL queue in prod |
| PWBS-PROJECT-CONTROLS | PROJECT-CONTROLS | P2 | **PARTIAL** | PLANNED | Health-v1 dims surfaced honest-null |
| PWBS-PROCUREMENT | PROCUREMENT | P2 | **PARTIAL** | PLANNED | EPIC-PROC2 5 tasks; RfQ/BoQ used in prod |
| PWBS-EXEC-REPORTING | EXEC-REPORTING | P3 | **SCAFFOLDED** | DEFERRED | Morning Briefing / portfolio read in prod |
| PWBS-OPS-TRUST | OPS-TRUST | P0 | **DEPLOYED** | **ACTIVE** | P0a CLOSED; P1-OPS Beat closed |

> **Work ≠ Realization** (`work_status` is a separate enum; **DEPLOYED ≠ CLOSED**): e.g. **PWBS-OPS-TRUST** is technically **DEPLOYED** yet `work_status`=**ACTIVE** because the P1-OPS Celery Beat gap is still open. Progressive elaboration: only **PWBS-ACT-HEALTH (P0b)** is decomposed to L4 now. Later epics keep **stable L2 IDs + deps + priority + ADRs + user value + realization + exit gate**; they are **not** prematurely decomposed to tasks.

## 7. P0b vertical contract (all slices + exit gates defined before slice 1)

**DONE (production evidence):** upload one document → 6-category decomposition → per-category `{state, findings, missing_data}` → actionable gap alerts → Health Vector → persisted + read via API → **user-visible UI/report**. Unknown ⇒ null (never fabricated). Coherence unavailable as a headline until **≥2 reconcilable documents**.

**Invariants (`p0b.invariant_ids: INV-1,INV-UX,INV-COH`):** INV-1 honest-null · **INV-UX**: backend null → UI **"Unknown / Insufficient evidence"**, **never 0%** (0 only when an evidence-backed scorer genuinely returns zero) · **INV-COH**: `coherence_subscore` stays **NULL** while <2 reconcilable docs.

| Slice | Status | Scope | Exit gate |
|---|---|---|---|
| **L4-1** category_coverage (pure domain) | **DONE** | `compute_category_coverage()` + `gap_alerts()`; PRESENT \| INSUFFICIENT_EVIDENCE | RED→GREEN unit: covered=PRESENT; absent=INSUFFICIENT_EVIDENCE + gap alert; all-present=0 gaps; empty=6 gaps; INV-1; ruff+mypy green |
| **L4-2** wire intake→classification→coverage | **DONE** | one doc's clauses → per-category `{state, findings(022+intrinsic), missing_data}`; **CROSS findings preserved separately**, never attributed to a canonical category | integration: real doc → coverage; contract-only ⇒ TECHNICAL/BUDGET/TIME insufficient |
| **L4-3** persist the single-document assessment into the Health Vector | **DONE** | **N8** computes `SingleDocumentCoverage` **once** from canonical `Clause[]` + `FindingSignal[]`; versioned artifact in `analyses.result_json`; `graph.completed` carries **`analysis_id` lineage only**; SnapshotWriter persists **`HealthVector.single_document_coverage`** as a **non-rollup** product/evidence surface. **No new Contract/Documentation numeric formula**; `coherence_subscore` stays **NULL**; honest-null lineage precedence enforced. | assessment persisted + read back **without re-running CategoryRouter**; six assessments + missing_data + gaps + CROSS survive round-trip; legacy/unknown-version/malformed lineage ⇒ `None` (never empty-known); composite scoring unchanged; replay idempotent |
| **L4-4** read API | **PARTIAL** | `GET /api/v1/projects/{project_id}/health` already returns `HealthVector`, so `single_document_coverage` is **already exposed** through the existing response contract and generated OpenAPI; **dedicated API acceptance + consumer validation remain pending**. | authenticated GET returns decomposition+gaps+vector; Unknown=null (never 0) |
| **L4-5** UI/report | **BLOCKED** | per-category view + gap alerts; null → "Unknown / Insufficient evidence" | **PROD**: upload one doc → UI shows per-category state/findings/missing_data + gap alerts + Health Vector; Unknown≠0%; Coherence absent until ≥2 docs |

**Open residuals (`p0b.residual_ids`)**

| Residual | Status | Priority | Blocks | Production truth | Required resolution |
|---|---|---|---|---|---|
| **P0b-R1-EVIDENCE-GRANULARITY** — per-clause evidence granularity | **PLANNED** | **P0** | **P0b-L4-5** | `_build_coherence_clauses()` emits **one whole-document canonical `Clause`**, so evidence is document-level/coarse, per-category `evidence_count` is effectively 0/1, and **real CROSS generation cannot occur** (`_build_category_cross_pairs` returns `[]` for a single clause) even though the CROSS transport is implemented and tested. | **Audit and reuse** existing clause/section extraction + persistence; adapt existing evidence into **multiple stable `coherence.models.Clause` records**; preserve stable evidence IDs / lineage. **No parallel parser.** |

> `slice_status` **DONE** means the slice met its **code/merge exit gate** — it does **not** mean P0b is PROD_VALIDATED. The vertical's DONE still requires **L4-5 production evidence** (`p0b_exit_gate`).

> **Correction (H), as implemented:** L4-3 does **not** "close `coherence_subscore=None`" — with one document relational Coherence **must remain null**. As built, L4-3 also does **not** feed Contract/Documentation numerically: that mapping was **deliberately deferred** (no formula from the six ADR-024 categories onto the seven ADR-018 dimensions), and the assessment is carried as a **non-rollup** surface instead. Real coherence becomes a conditional Contract input **after** the ≥2-document eligibility is met.

**Reuse (not rebuild):** `CoherenceCategory` (SCOPE/BUDGET/TIME/TECHNICAL/LEGAL/QUALITY), `HealthNullReason.INSUFFICIENT_EVIDENCE`, `assemble_health_vector`, ADR-022 findings, the clause classifier, RAG/extraction.

## 8. Zero-loss legacy mapping — `unmapped_open_legacy_items = 0`

Every OPEN legacy item maps to a Product WBS ID, DEV/OPS, or DEFERRED/WONT-DO:

| Open legacy item | Maps to | Disposition |
|---|---|---|
| EPIC-PROC2 (5 tasks) | PWBS-PROCUREMENT | P2; build-gated |
| EPIC-AI Phase 2 | PWBS-COHERENCE-XDOC | DEFERRED (awaiting Phase-1 adoption) |
| TASK-FRT-041 | WONT-DO | Clerk free-tier |
| EPIC-COH-AGENTIC (ADR-023) | PWBS-COHERENCE-XDOC | P1/P2; real authoritative scorer |
| EPIC-ECOA-V2-CUTOVER (reopened) | PWBS-COHERENCE-XDOC | OPEN — cutover not demonstrated (0/15 v2); P1 decision |
| EPIC-V3-019-020 (ADR-019/020) | PWBS-ALERTS-ACTIONS-HITL | P2; build-gated |
| EPIC-V3-021 (ADR-021) | PWBS-EXEC-REPORTING | P3 DEFERRED |
| TASK-V3-013-07/08/09 residuals | DEV/OPS | absorbed into thin-spine; verify closed |
| P1-OPS Celery Beat gap | PWBS-OPS-TRUST | OPS; blocks ADR-015 temporal |
| TASK-DOC-REUPLOAD-005 | PWBS-OPS-TRUST | reupload PATCH 500 (pilot residual) |
| TASK-COH-BUD-RECON-006 | PWBS-COHERENCE-XDOC | contract 628M cross-check (deferred) |
| Dependabot / mypy / Sonar (DEV-*) | DEV/OPS | hygiene; non-product |

## 9. Master defects

D1 product-value gap · D2 ADR-018 WIRED-not-validated · D3 ADR-024 unbuilt · D4 coherence v2 global cutover not demonstrated (0/15) / 017 flag-off / 016 L3 stub · D5 temporal snapshots inert (Beat) · D6 stale claims in the **canonical** backlog (banner added) · D7 no product-programme control plane (these files) · D8 ADR numbering ambiguous across three namespaces (ADR-004 collision).

## 10. Risks

R1 reliability-as-completion · R2 coherence/calibration revival as headline · R3 P0b scope creep · R4 honest-null erosion (null≠0%) · R5 dual-control drift · R6 MD/YAML divergence (mitigated by the value-exact + enum-validated parity checker).

## 11. Governance & authority separation

- **Product plane (this):** state ledger + exit gates. Read-only reconciliation; grants no execution authority.
- **Development-execution plane (`.c2pro/`):** work-envelopes, roles, review-policy, `authority: {direct_main_mutation:false, production_runtime:false, merge:human_merge}`.
- **Legacy reference (cold):** `C2PRO_MASTER_BACKLOG.md`, `backlogs/BCK_*.md`, PR/CI history — retained as reference, **not** the product source of truth (now banner-flagged).

## 12. PR disposition & next authorized action

- **#572** — REBUILT clean: rebased onto `origin/main`; **only** documentation/control changes (2 control files + parity checker + parity tests + legacy banner). The 6 Celery files (already in main via #569) are gone.
- **#571** — **HOLD → amend**: re-scope to "P0a Reliability & Operability Baseline CLOSED" (not "product baseline complete") + register the **P0b vertical epic** (PWBS-ACT-HEALTH). Do not merge until re-scoped after #572 approval.

**Next:** (1) **MASTER review** of #572 + this reconciliation; (2) on approval, Reconciler amends #571; (3) then, under `.c2pro` governed dev, implement **P0b-L4-1** (`category_coverage`) RED-first.

*No product code, runtime, or production mutation was performed in this reconciliation (read-only prod SELECTs only).*
