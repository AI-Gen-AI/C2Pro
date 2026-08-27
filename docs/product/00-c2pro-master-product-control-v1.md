# C2Pro Master Product Programme Control — v1

**Status:** Reconciliation snapshot (read-only) · **Date:** 2026-08-27
**repository_main_sha:** `9c48f4f94d0a5719561916b956f8a78b2129a250` · **deployed_runtime_sha:** `UNVERIFIED` (do not infer from main — confirm via Railway deploy log)
**Machine-readable source of truth:** [`validation/product/c2pro-master-product-control-v1.yaml`](../../validation/product/c2pro-master-product-control-v1.yaml)

> This is the **PRODUCT** control plane — *what C2Pro is and how far each capability is realized*.
> It is **distinct from** the **development-execution** plane in [`.c2pro/`](../../.c2pro) (work-queue, roles,
> review-policy, authority gates). Execution authority, merges, and runtime mutations remain governed by
> `.c2pro/control` (**human merge; no direct main/prod mutation**). This plane is the target/state ledger
> those work-envelopes are measured against — **not** a competing execution plane.
>
> **Control integrity:** this Markdown is a **human projection** of the YAML. The fields in the YAML's
> `parity.critical_fields` MUST match here; `validation/product/check_control_parity.py` asserts it so the
> two controls cannot silently diverge. **Edit the YAML first**, then reflect into this file.

## 1. Product North Star

**C2Pro is continuous, evidence-backed project & procurement intelligence** for construction/infrastructure contracts: **Health + relational Coherence + Change/Time intelligence + Risk + Alerts/Actions/HITL + Project Controls (schedule/cost/deliverables/WBS/BOM) + Procurement workflows (RfQ/BoQ/RACI/comms) + Executive intelligence (PMO reporting / Morning Briefing / portfolio).** Every surface is evidence-backed and honest: **Unknown renders null — never a fabricated zero/green** (INV-1, ADR-018). Coherence (ADR-009) is **one relational input** — the Contract subscore, available only with **≥2 reconcilable documents**; never the whole product, never a single-document headline.

**Current product wedge = P0b — Single-document Health activation** (ADR-024 → ADR-018): value from document #1 (per-category coverage + intrinsic findings + `missing_data` + gap alerts + Health Vector). The wedge is the **entry point** to the North Star above, **not its definition**.

## 2. Current production position (honest — three separate facts)

- **`repository_main_sha`** = `9c48f4f9` (main tip after #570).
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

## 4. ADR realization matrix (four separate status fields; no compound values)

Vocabulary: **DESIGNED · SCAFFOLDED · WIRED · DEPLOYED · PROD_VALIDATED · DEFERRED · BLOCKED · NONE · PARTIAL**. Columns: **Design / Realization / Deployment / Prod-validation**.

| ADR (ns) | Design | Realization | Deployment | Prod-valid | Key gap |
|---|---|---|---|---|---|
| 001 modular-monolith (found.) | Accepted | DEPLOYED | DEPLOYED | PROD_VALIDATED | — |
| 002 supabase-mvp (found.) | Accepted | DEPLOYED | DEPLOYED | PROD_VALIDATED | — |
| 003 ai-architecture (found.) | Accepted | DEPLOYED | DEPLOYED | PROD_VALIDATED | — |
| 004 frontend-layer-rules (found.) | Accepted | DEPLOYED | DEPLOYED | PROD_VALIDATED | number collides w/ ADR-004 CB |
| 005 three-layer-test (found.) | Accepted | DEPLOYED | NONE | PROD_VALIDATED | — |
| 006 post-reorg (found.) | Accepted | DEPLOYED | DEPLOYED | PROD_VALIDATED | — |
| ADR-001 coherence-deadcode (coh-era) | Accepted | DEPLOYED | DEPLOYED | PROD_VALIDATED | historical |
| ADR-002 coherence-score-versioning (coh-era) | Accepted | DEPLOYED | DEPLOYED | PROD_VALIDATED | 15/15 prod rows `coherence-v1` |
| ADR-003 coherence-alert-ledger (coh-era) | Accepted | DEPLOYED | DEPLOYED | PROD_VALIDATED | — |
| ADR-004 circuit-breakers (v3) | Implemented | DEPLOYED | DEPLOYED | PROD_VALIDATED | number collides w/ 004-frontend |
| **ADR-009 coherence v1 (v3)** | Accepted (v2-locked; **DEMOTED**) | DEPLOYED | DEPLOYED | PROD_VALIDATED | relational Contract subscore |
| ADR-009 coherence **v2 track** | — | SCAFFOLDED | **SHADOW_INERT** | NONE | 0 v2 headlines in prod; cutover=NO (§4b) |
| ADR-013 typed-graph (v3) | Accepted P0 | WIRED | DEPLOYED | PARTIAL | residual 017-06 |
| ADR-014 project-state (v3) | Accepted P0 | DEPLOYED | DEPLOYED | PROD_VALIDATED | 014-08 residual |
| ADR-015 temporal (v3) | Accepted P0 | SCAFFOLDED | PARTIAL | NONE | snapshots **inert** (Beat gap, P1-OPS) |
| ADR-016 change-impact (v3) | Accepted P0→P1 | SCAFFOLDED | NONE | NONE | L3 stub; not wired |
| ADR-017 projectgraph (v3) | Accepted P1 | SCAFFOLDED | **BLOCKED** | NONE | flag-gated OFF; Tier-2 MAE stub |
| **ADR-018 health (v3, primary)** | Accepted **PROMOTED P0-NOW** | **WIRED** | DEPLOYED | **NOT_VALIDATED** | not surfaced; `coherence_subscore=None`; ADR-024 absent |
| ADR-019 alerts-actions (v3) | Accepted P2 | SCAFFOLDED | NONE | NONE | build-gated |
| ADR-020 hitl (v3) | Accepted P2 | SCAFFOLDED | PARTIAL | NONE | build-gated (spoofing fixed) |
| ADR-021 briefing (v3) | Deferred P3 | SCAFFOLDED | NONE | NONE | deferred |
| ADR-022 contract-clarity (v3) | Accepted P2 | WIRED | DEPLOYED | NOT_VALIDATED | not surfaced via activation |
| ADR-023 agentic (v3) | **Proposed** | DESIGNED | NONE | NONE | not built |
| **ADR-024 single-doc-activation (v3)** | Accepted (VP 2026-08-22) | **DESIGNED** | NONE | NONE | **no `category_coverage`/gap-alert — this is P0b** |

## 4b. Coherence runtime reconciliation (proven, read-only — not assumed)

Bounded **read-only** production reconciliation performed 2026-08-27 (SELECT-only on prod `tcxedmnvebazcsaridge` + code path `coherence/router.py`):

- **Persisted scorer:** `coherence_results` = **15/15 `coherence-v1`** (2026-08-07 → 2026-08-16); **0 v2**.
- **v2 shadow:** `coherence_v2_shadow` = **1 row**, last **2026-08-07** — inert.
- **Flag enrollment (26 tenants):** `coherence_v2_enabled`=**6**, `canonical_canary`=**1**, `llm_crosscheck`=**1**.
- **Global setting:** `COHERENCE_V2_SHADOW_MODE` default `True`; shadow guard needs **per-tenant v2 flag AND** the global setting (`router.py:848-851`).
- **Scorer path:** `router.py:741` `evaluate_coherence_async` (**v1**); canary (763) + v2 shadow (841) **default OFF**.

**Verdict:** legacy "v2 authoritative / cut over" = **FALSE**; "v1 live / v2 shadow / cutover NO" = **CONFIRMED**. ADR-009 runtime realization is therefore recorded as **v1 DEPLOYED+PROD_VALIDATED / v2 SCAFFOLDED-SHADOW_INERT** (reconciliation **COMPLETE**, not `RECONCILIATION_REQUIRED`).

## 5. Capability planes (8)

`ACT-HEALTH` · `COHERENCE-XDOC` · `TEMPORAL-CHANGE` · `ALERTS-ACTIONS-HITL` · `PROJECT-CONTROLS` · `PROCUREMENT` · `EXEC-REPORTING` · `OPS-TRUST`. (ADR mapping in the YAML.)

## 6. Product WBS (L2 epic per plane; progressive elaboration — P0b→L4 now)

| WBS ID | Plane | Pri | Deps | ADRs | Realization | Exit gate (evidence-for-DONE) |
|---|---|---|---|---|---|---|
| **PWBS-ACT-HEALTH** | ACT-HEALTH | P0b | — | 024/018/022 | DESIGNED | P0b-L4-5 PROD_VALIDATED (§7) |
| PWBS-COHERENCE-XDOC | COHERENCE-XDOC | P1 | ACT-HEALTH | 009/017/023 | DEPLOYED v1 / SCAFFOLDED v2 | v2 cutover (MAE+canary) or explicit v1-keep; cross-doc findings on ≥2-doc project |
| PWBS-TEMPORAL-CHANGE | TEMPORAL-CHANGE | P1 | ACT-HEALTH | 015/016 | SCAFFOLDED | snapshot capture running (Beat) + Change-Impact Report |
| PWBS-ALERTS-ACTIONS-HITL | ALERTS-ACTIONS-HITL | P2 | TEMPORAL/ACT | 019/020 | SCAFFOLDED/DEFERRED | build-gate lifted; ActionItem→CM HITL queue in prod |
| PWBS-PROJECT-CONTROLS | PROJECT-CONTROLS | P2 | ACT-HEALTH | 018 | PARTIAL | Health-v1 dims surfaced honest-null |
| PWBS-PROCUREMENT | PROCUREMENT | P2 | PROJECT-CONTROLS | — | PARTIAL | EPIC-PROC2 5 tasks; RfQ/BoQ used in prod |
| PWBS-EXEC-REPORTING | EXEC-REPORTING | P3 | ALERTS/HITL | 021 | SCAFFOLDED/DEFERRED | Morning Briefing / portfolio read in prod |
| PWBS-OPS-TRUST | OPS-TRUST | P0 | — | 004 | DEPLOYED | P0a CLOSED; P1-OPS Beat closed |

> Progressive elaboration: only **PWBS-ACT-HEALTH (P0b)** is decomposed to L4 now. Later epics keep **stable L2 IDs + deps + priority + ADRs + user value + realization + exit gate**; they are **not** prematurely decomposed to tasks.

## 7. P0b vertical contract (all slices + exit gates defined before slice 1)

**DONE (production evidence):** upload one document → 6-category decomposition → per-category `{state, findings, missing_data}` → actionable gap alerts → Health Vector → persisted + read via API → **user-visible UI/report**. Unknown ⇒ null (never fabricated). Coherence unavailable as a headline until **≥2 reconcilable documents**.

**Invariants:** INV-1 honest-null · **INV-UX**: backend null → UI **"Unknown / Insufficient evidence"**, **never 0%** (0 only when an evidence-backed scorer genuinely returns zero) · **INV-COH**: `coherence_subscore` stays **NULL** while <2 reconcilable docs.

| Slice | Scope | Exit gate |
|---|---|---|
| **L4-1** category_coverage (pure domain) | `compute_category_coverage()` + `gap_alerts()`; PRESENT \| INSUFFICIENT_EVIDENCE | RED→GREEN unit: covered=PRESENT; absent=INSUFFICIENT_EVIDENCE + gap alert; all-present=0 gaps; empty=6 gaps; INV-1; ruff+mypy green |
| L4-2 wire intake→classification→coverage | one doc's clauses → per-category `{state, findings(022+intrinsic), missing_data}` | integration: real doc → coverage; contract-only ⇒ TECHNICAL/BUDGET/TIME insufficient |
| **L4-3** Health Vector + persist (**Contract/Documentation only**) | feed Contract + Documentation HealthSignals from single-doc coverage; snapshot persist. **Does NOT populate `coherence_subscore`** — it stays **NULL** for one document. Coherence becomes a Contract input **only once ≥2 reconcilable docs exist** (eligibility-gated). | HealthVector persisted w/ honest-null dims; **`coherence_subscore=NULL` asserted for single-doc**; no fabricated composite |
| L4-4 read API | GET project health → decomposition + gap alerts + Health Vector | authenticated GET returns decomposition+gaps+vector; Unknown=null (never 0) |
| L4-5 UI/report | per-category view + gap alerts; null → "Unknown / Insufficient evidence" | **PROD**: upload one doc → UI shows per-category state/findings/missing_data + gap alerts + Health Vector; Unknown≠0%; Coherence absent until ≥2 docs |

> **Correction (H):** L4-3 does **not** "close `coherence_subscore=None`". With one document, relational Coherence **must remain null**; L4-3 wires only Contract/Documentation evidence. Real coherence becomes a conditional Contract input **after** the ≥2-document eligibility is met.

**Reuse (not rebuild):** `CoherenceCategory` (SCOPE/BUDGET/TIME/TECHNICAL/LEGAL/QUALITY), `HealthNullReason.INSUFFICIENT_EVIDENCE`, `assemble_health_vector`, ADR-022 findings, the clause classifier, RAG/extraction.

## 8. Zero-loss legacy mapping — `unmapped_open_legacy_items = 0`

Every OPEN legacy item maps to a Product WBS ID, DEV/OPS, or DEFERRED/WONT-DO:

| Open legacy item | Maps to | Disposition |
|---|---|---|
| EPIC-PROC2 (5 tasks) | PWBS-PROCUREMENT | P2; build-gated |
| EPIC-AI Phase 2 | PWBS-COHERENCE-XDOC | DEFERRED (awaiting Phase-1 adoption) |
| TASK-FRT-041 | WONT-DO | Clerk free-tier |
| EPIC-COH-AGENTIC (ADR-023) | PWBS-COHERENCE-XDOC | P1/P2; real authoritative scorer |
| EPIC-ECOA-V2-CUTOVER (reopened) | PWBS-COHERENCE-XDOC | OPEN — cutover not done (0/15 v2); P1 decision |
| EPIC-V3-019-020 (ADR-019/020) | PWBS-ALERTS-ACTIONS-HITL | P2; build-gated |
| EPIC-V3-021 (ADR-021) | PWBS-EXEC-REPORTING | P3 DEFERRED |
| TASK-V3-013-07/08/09 residuals | DEV/OPS | absorbed into thin-spine; verify closed |
| P1-OPS Celery Beat gap | PWBS-OPS-TRUST | OPS; blocks ADR-015 temporal |
| TASK-DOC-REUPLOAD-005 | PWBS-OPS-TRUST | reupload PATCH 500 (pilot residual) |
| TASK-COH-BUD-RECON-006 | PWBS-COHERENCE-XDOC | contract 628M cross-check (deferred) |
| Dependabot / mypy / Sonar (DEV-*) | DEV/OPS | hygiene; non-product |

## 9. Master defects

D1 product-value gap · D2 ADR-018 WIRED-not-validated · D3 ADR-024 unbuilt · D4 coherence v2 not cutover (0/15) / 017 flag-off / 016 L3 stub · D5 temporal snapshots inert (Beat) · D6 stale claims in the **canonical** backlog (banner added) · D7 no product-programme control plane (these files) · D8 ADR numbering ambiguous across three namespaces (ADR-004 collision).

## 10. Risks

R1 reliability-as-completion · R2 coherence/calibration revival as headline · R3 P0b scope creep · R4 honest-null erosion (null≠0%) · R5 dual-control drift · R6 MD/YAML divergence (mitigated by the parity checker).

## 11. Governance & authority separation

- **Product plane (this):** state ledger + exit gates. Read-only reconciliation; grants no execution authority.
- **Development-execution plane (`.c2pro/`):** work-envelopes, roles, review-policy, `authority: {direct_main_mutation:false, production_runtime:false, merge:human_merge}`.
- **Legacy reference (cold):** `C2PRO_MASTER_BACKLOG.md`, `backlogs/BCK_*.md`, PR/CI history — retained as reference, **not** the product source of truth (now banner-flagged).

## 12. PR disposition & next authorized action

- **#572** — REBUILT clean: rebased onto `origin/main`; **only** documentation/control changes (2 control files + parity checker + legacy banner). The 6 Celery files (already in main via #569) are gone.
- **#571** — **HOLD → amend**: re-scope to "P0a Reliability & Operability Baseline CLOSED" (not "product baseline complete") + register the **P0b vertical epic** (PWBS-ACT-HEALTH). Do not merge until re-scoped after #572 approval.

**Next:** (1) **MASTER review** of #572 + this reconciliation; (2) on approval, Reconciler amends #571; (3) then, under `.c2pro` governed dev, implement **P0b-L4-1** (`category_coverage`) RED-first.

*No product code, runtime, or production mutation was performed in this reconciliation (read-only prod SELECTs only).*
