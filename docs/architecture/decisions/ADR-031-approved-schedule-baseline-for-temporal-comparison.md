# ADR-031: Approved Schedule Baseline for Temporal Comparison (`APPROVED_BASELINE` basis)

**Status:** Accepted with changes (2026-10-27, owner; two rounds). Docs-only change; no code until #1110 is merged
**Date:** 2026-10-27
**Decision class:** Trust / HITL / temporal-coherence architecture
**Conforms to:** ADR-020 (HITL), ADR-026 (trusted-state commit boundary), ADR-029 (WBS governance: baselines exclude dates; `SCHEDULE ACTIVITY != WBS NODE`), ADR-002 (Coherence score versioning: historical `coherence_results` rows are immutable, no recomputation or backfill) and ADR-009 §F (canonical `score_version` identifiers)
**Amends:** ADR-029 "Later: Schedule Temporal Intelligence" (this ADR is its first slice); supersedes nothing.
**Depends on (PRs):** #1108 (provisional TIME machinery; the "current revision" rule `trusted OR no pending proposal`), #1110 (scoreless durable alert ledger). Independent of #1111, #1109, #1112.

## Context (verified in code at `integration/budget-time-20261024`, `426b7876`)

- The cross-document TIME comparator (`coherence/cross_document/comparators.py`, ~l.345) emits a **confirmed, scoring** `DET-CRS-SCHDEAD` only when the schedule date's `basis == APPROVED_BASELINE`; otherwise it returns the provisional `ADV-SCHDEAD-PROVISIONAL` (an Alert, never a `FindingSignal`, never in the score).
- **Nothing assigns that basis.** The ingestion worker always stamps the finish `SOURCE_OBSERVED_NOT_APPROVED_BASELINE` (`documents/application/schedule_planned_finish.py`), and `assembly._schedule_finish` copies the stamp. Approving the schedule *document* (artifact `TRUSTED`) does not change it. Today a deadline contradiction can never enter the Coherence Score.
- **Name collision.** `AuthorityState.APPROVED_BASELINE` (`wbs/domain/governance.py`) means "a WBS tree baseline was applied" and, by ADR-029 §8, baseline snapshots exclude dates. `BASIS_APPROVED_BASELINE` (`coherence/cross_document/inputs.py`) is a property of a dated source. They are different facts.
- **A confirmed finding alone does not produce a score** (measured, mock AI, triplet fixture; see §Acceptance). The v1 scorer needs `active_weight >= MIN_ACTIVE_WEIGHT = 0.35` with uniform category weights of 1/6 (`domain/v2_constants.py`), i.e. **at least 3 of 6 categories assessed** (2/6 = 0.333 fails). Cross-document signals do not set category coverage, so a confirmed `DET-CRS-SCHDEAD` does not by itself make TIME "assessed".

## Decision

1. **Meaning.** `BASIS_APPROVED_BASELINE` on a schedule finish means: *this exact schedule revision (document_id, revision_id, blob_hash) was approved by a human as the project's temporal baseline.* It is implied neither by document trust (`TRUSTED`) nor by a WBS baseline. Upload/analysis approval ≠ baseline approval.
2. **Storage.** New append-only table `schedule_baseline_approvals`: `tenant_id, project_id, document_id, revision_id, blob_hash, planned_finish_date, source_locator, approved_by, decided_at, review_item_id, supersedes_id, wbs_baseline_id NULL, wbs_tree_digest NULL`. RLS by tenant; immutable. "Current baseline" is derived (latest non-superseded row whose revision is the current revision, below). One Alembic migration (re-verify a single head against `main`) plus Supabase sync.
3. **Who approves.** Human only, through HITL (ADR-020/026): review item type `schedule_baseline`, bound to the exact `revision_id + blob_hash`. AI/service actors cannot create the row (DB constraint, as in ADR-029).
4. **WBS link.** The approval records the current WBS `baseline_id`/`tree_digest` when one exists, as provenance only. A WBS `APPROVED_BASELINE` is not required. Schedule↔WBS alignment stays ADR-029 §10 (never mutates authority).
5. **Validity ("vigente") — one definition system-wide.** A baseline is valid exactly while its revision is the project's *current revision* under the **same rule as #1108**: `current_revision_lateral` with **"trusted, or resolved with no pending PROPOSED artifact"** (including a PROPOSED artifact whose revision binding is NULL on a single-revision document). No schedule-specific variant. Consequences: a new revision that is only PROPOSED or REJECTED neither replaces nor invalidates the baseline; once the new revision becomes the current one, the baseline is no longer valid, the finish reverts to `SOURCE_OBSERVED…` and the finding returns to provisional (fail closed) until a human approves the new revision. Nothing is inherited across revisions. A later WBS baseline does not invalidate it; it marks the WBS link stale.
6. **Read path.** `load_schedule_planned_finish` (`coherence/schedule_clause_builder.py`) keeps validating the observation stamp against `current_revision_lateral`, and additionally looks up the current approval for that exact revision; only then does it set `basis=APPROVED_BASELINE`. The comparator is unchanged.
7. **Coverage is partial when a single cross-document comparator provides it.** A cross-document comparator that *evaluated* (both sources present, sourced, comparable and, for TIME, baseline-approved) marks its category assessed, whether or not it fired; without this rule a confirmed `DET-CRS-SCHDEAD` leaves TIME unassessed and the score unchanged. Because that is one comparator and not a full TIME audit, the coverage it grants is declared **partial**: whenever TIME is assessed only through it, the result carries `evidence_limitations["TIME"] = "TIME evaluada solo por fecha de fin frente a plazo contractual"` (or equivalent wording fixed in implementation), exposed in `EnrichedCoherenceResult.evidence_limitations` and in the `limitations` of the TIME entry of `category_breakdown`. If other TIME evidence also assesses the category, the limitation is not emitted. Implementation must first audit every consumer of `evidence_limitations` that assumes "limitation ⇒ category unassessed" (`v1_unassessed_reasons`, the budget-throttled logic in `scoring_arbiter`, the v2 shadow, the UI), because this is the first limitation attached to an *assessed* category.
8. **`score_version` changes.** Rules 6–7 change what is assessed and what scores, so the Coherence score is no longer comparable with earlier values. A new score version (proposed `coherence-v1.1`) is emitted on every new result and declared in release notes. Per ADR-002, existing rows keep their version and are never recomputed. Implementation scope (verified): `score_version` is a PostgreSQL enum (`coherence_score_version`, values `coherence-v1`/`coherence-v2`, migration `20260526_0001`), so the Slice 1 schema change must also `ALTER TYPE coherence_score_version ADD VALUE`. **A value added this way cannot be used in the same transaction** (PostgreSQL refuses to use a new enum value until the transaction that added it has committed), and Alembic runs a migration inside one transaction. Therefore the enum value goes in its **own migration**, or inside an `autocommit_block()` (`with op.get_context().autocommit_block():`, the pattern already used in `20260516_0003_add_technical_spec_to_document_type_enum.py` and `20260626_0001_add_schedule_to_document_type_enum.py`), and nothing in the same migration (table, constraint, default, backfill) may reference `coherence-v1.1`; the code that emits it ships only after that migration is applied; the `Literal["coherence-v1", "coherence-v2"]` types in `coherence/models.py` (several fields), `SCORE_VERSION_VALUES` in `domain/v2_constants.py`, OpenAPI and the generated web client must be extended; the v2 shadow naming must not collide with the new value; dashboards, reports and persisted snapshots that key on `score_version` must be reviewed.

## Slices

**Sequencing:** after #1110 is merged and after the P1 parsing fix (#1126) and the contract-side CONBUD authority fix, in that order.

**Slice 1 (first PR after #1110):** table + RLS + migration (also the `coherence_score_version` enum value); approval API (human actor, exact binding, idempotent, supersede); read path (rule 6); validity rule (5); coverage rule (7); `score_version` (8); minimal approve action (a button in the schedule document view); tests 1–5 below. Slice 1 alone must satisfy the acceptance criterion.

**Slice 2:** full UI (queue item, baseline badge, history), `ProjectSnapshot` trigger on approval (as `baseline_changed`), What Changed integration, concurrency hardening (concurrent approvals leave one current row), OpenAPI/client polish, E2E journey step.

## Consumers that change

| Consumer | Change | Slice |
|---|---|---|
| `schedule_clause_builder.load_schedule_planned_finish` | Reads the approval, sets the basis. | 1 |
| `cross_document/assembly`, `comparators` | No logic change; new tests. | 1 |
| `coherence/graph/nodes.py` (coverage, provisional/confirmed split) | Coverage rule 7 (partial coverage + `evidence_limitations`); confirmed finding becomes a `FindingSignal`. | 1 |
| Consumers of `evidence_limitations` (`v1_unassessed_reasons`, `scoring_arbiter` throttling, v2 shadow, UI breakdown) | Audit and adapt: a limitation may now sit on an assessed category. | 1 |
| `domain/v2_constants` / `SCORE_VERSION_*`, score surfaces | New score version. | 1 |
| `coherence/alert_generator`, alert mirror, `AlertGeneratorService` | `ADV-SCHDEAD-PROVISIONAL` superseded when baseline approved; observation key includes the approval id; relies on #1110. | 1 |
| `coherence/services/v2/conflict_service` | Verify only (already maps `DET-CRS-SCHDEAD`). | 1 |
| HITL queue/API | `schedule_baseline` review item and decision endpoint. | 1 |
| UI approve button (minimal) | One action on the schedule document. | 1 |
| Full UI, `ProjectSnapshot`, What Changed, E2E | See Slice 2. | 2 |
| OpenAPI / generated client | `make openapi`. | 1–2 |

## Acceptance criterion

**With the baseline approved, the triplet must produce `overall_score != None`.**

Measured on the triplet fixture, **unchanged**, with mock AI (local experiments, `C2PRO_AI_MOCK=1`; the schedule finish stamped `APPROVED_BASELINE` where noted):

| Case | Assessed categories | active_weight | overall_score |
|---|---|---|---|
| Before #1127 (provisional schedule) | SCOPE | 1/6 = 0.167 | None (`insufficient_active_weight`) |
| Before #1127, confirmed `DET-CRS-SCHDEAD` only | SCOPE | 0.167 | None: the signal exists but TIME stays unassessed |
| **After #1127**, provisional schedule | SCOPE (80), LEGAL (80) | 2/6 = 0.333 (< 0.35) | None; no new finding (a 0.1% daily penalty is exactly the configured maximum, a 10% cap is under 15%) |
| After #1127, baseline approved, TIME assessed by rule 7 | SCOPE (80), LEGAL (80), TIME (25.9) | 3/6 = 0.50 | **60.0**; signals `DET-CRS-CONBUD`, `DET-CRS-NEGMARGIN`, `DET-CRS-SCHDEAD` |

Caveats of the measurement: mock AI (the real-AI run of the triplet, tracked separately, records `audit_coverage` and `category_scores` and may add categories, never remove them); the TIME row forces TIME coverage with a local test patch standing in for rule 7, which is not implemented yet; it was run on the ACC-01 integration tree with #1127's change applied, not on `main`.

`DET-CRS-SCHDEAD` alone is **not sufficient**: the v1 scorer needs at least 3 of 6 categories assessed (uniform 1/6 weights, `MIN_ACTIVE_WEIGHT = 0.35`; 2/6 = 0.333 fails). What closes the gap:

1. **Rule 7 (this ADR):** TIME becomes assessed, partially, when the comparator evaluates.
2. **The third dimension is LEGAL, and it comes from #1127** (issue #1126): Spanish penalty clauses are no longer read as `OTHER`, `daily_penalty_pct` and `penalty_cap_pct` are extracted separately and correctly, and the registered `DET-LEG-PENALTY` rule becomes applicable on the triplet's penalty clause ("0,1% diario"). BUDGET stays withheld by design (`STRUCTURED_BUDGET_SOURCE_UNAVAILABLE`, #860) and TECHNICAL gets no evidence from the specification, so neither contributes.

**Decision: the triplet fixture is not extended.** The earlier plan to add a quality clause to the contract is dropped: LEGAL provides the third category from the fixture as it is. (Earlier text in this ADR deferred the fixture decision to the real-AI run; the mock measurement above makes that unnecessary, and the real-AI run is now a confirmation, not a precondition.)

Lowering `MIN_ACTIVE_WEIGHT` below 0.333 to make two categories enough is **rejected**: it is an ADR-009 scoring decision and would let a project score on a third of the audit.

The acceptance test requires rule 7, runs the **untouched** triplet, and asserts that `overall_score` is not None (60.0 in the measurement above, to be re-derived when it is implemented), that it differs from the run without approval, that LEGAL, TIME and SCOPE are the assessed categories, and that the partial-coverage limitation is present.

## Tests that prove a deadline contradiction scores (PostgreSQL integration, extending `test_contract_schedule_completion_flow.py`)

1. Late schedule, not baseline-approved ⇒ only `ADV-SCHDEAD-PROVISIONAL`, score and signals unchanged (exists today; keep).
2. Baseline approved for the current revision ⇒ `DET-CRS-SCHDEAD` in `finding_signals`, TIME assessed (with the partial-coverage limitation), provisional advisory gone, new `score_version`; `overall_score` is not None on the untouched triplet (see §Acceptance criterion).
3. On-time schedule, baseline approved ⇒ no finding, TIME assessed (clean) **and `evidence_limitations["TIME"]` is present with the partial-coverage text** (asserted on the result and on `category_breakdown`).
4. New revision approved/trusted after the baseline ⇒ back to provisional; a merely PROPOSED or REJECTED newer revision ⇒ baseline still valid (rule 5).
5. Approval for a non-current revision, a wrong `blob_hash`, another tenant's project, or by an AI/service actor ⇒ rejected (DB + API); replay idempotent.

Slice 2 adds: concurrent approvals leave one current row; browser journey step "approve the schedule as baseline"; the real-AI harness variant `schedule_approved` flips from `ADV-SCHDEAD-PROVISIONAL` to the confirmed finding.

## Open questions

1. **Why do penalty and liability clauses not make LEGAL assessed?** **Resolved by #1127** (issue #1126, merged 2026-10-28). The analysis below is kept as the record of why; after #1127 the Spanish penalty clause of the triplet makes LEGAL assessed. (Answered at the time by reading code, plus mock experiments and two helper calls on the classifier and percentage parser.)

   LEGAL becomes assessed through one of three routes; none is reached by the triplet in mock:
   - **Deterministic evaluators.** Only three LEGAL evaluators are registered (`DET-LEG-PENALTY`, `DET-LEG-NOTICE`, `DET-LEG-REVIEW`); `WarrantyPeriodEvaluator`, `PaymentTermEvaluator` and `InsuranceExpiryEvaluator` exist in `rules_engine/deterministic.py` but are **not** in `DETERMINISTIC_EVALUATORS`. Each registered one overrides `applicability` and is evaluated only if the clause carries structured inputs: `has_penalty_cap` / `penalty_cap_pct` / `daily_penalty_pct` (penalty), `notice_period_days` (notice), `last_review_date` (review). A category is marked assessed when an evaluator's applicability is `EVALUATED`, whether or not it raises a finding.
   - **Who fills those fields.** (a) Deterministic ingestion (`core/tasks/ingestion_tasks._build_contract_clause_data`) sets `daily_penalty_pct`/`penalty_cap_pct` only when `_infer_contract_clause_type` returns `PENALTY`; that classifier matches **English substrings only** (`penalt`, `liquidated damages`, `delay`, and likewise `payment`, `warranty`, `liability`…). Spanish clauses ("Penalizaciones… penalización… retraso", "Garantía", "Responsabilidad") classify as `OTHER`, so no field is set. Verified by calling the classifier: the triplet's own penalty clause and my probe penalty, liability and warranty clauses all return `OTHER`; the English equivalent returns `PENALTY`. (b) LLM clause enrichment (`coherence/extraction/clause_extractor`, Haiku; schema includes `penalty_cap_pct`, `daily_penalty_pct`, `has_penalty_cap`, `notice_period_days`, `warranty_months`…), which returns `{}` under `C2PRO_AI_MOCK=1`.
   - **Text router and LLM rules.** `CategoryRouter` priors marked only QUALITY in the experiment. With real AI and `low_budget_mode=False`, the LLM rule `R-RESPONSIBILITY-01` (LEGAL) marks LEGAL assessed when it evaluates a clause whose keyword-inferred category is LEGAL.

   Three defects found on the way (filed together as issue #1126, priority P1, fixed by #1127 before Slice 1): the English-only clause-type classifier; `_extract_percentage` reads `0,1%` as 0.01 (10× too large; `0.1%` reads 0.001), a bug for Spanish decimals; and the same percentage is stored as both `daily_penalty_pct` and `penalty_cap_pct`.

   **Would a typical EPC contract satisfy it?** In **mock**: no, for Spanish contracts via ingestion (classifier), and for any contract via enrichment (disabled). With **real AI**: probably yes. A typical EPC states delay damages with a rate and cap, notice periods for claims, defects liability and insurance, so enrichment can populate `daily_penalty_pct`/`penalty_cap_pct`/`has_penalty_cap`/`notice_period_days` regardless of language, and the LLM rule applies to LEGAL-dominant clauses. This is a prediction from reading the code, to be confirmed by the real-AI run of the triplet, but the triplet contract is a 4-clause fixture whose only penalty clause is classified TIME by keyword score (`retraso`, `entrega`), so it may not exercise this even with a real model.
2. Role required to approve a baseline; activity-level dates beyond the project finish; multi-schedule projects; contract completion modifications.

## Alternatives rejected

- **Derive the basis from a WBS `APPROVED_BASELINE`.** Contradicts ADR-029 and lets an unrelated structural approval bless unreviewed dates.
- **Treat a `TRUSTED` schedule document as the baseline.** Silently promotes any approved schedule, including a late one, to a scoring contradiction.
- **A boolean flag in `document_metadata`.** Mutable, not revision-bound, last-writer-wins (#1123); fails ADR-026's exact-binding rule.
- **Lower `MIN_ACTIVE_WEIGHT`.** See acceptance criterion.

## Consequences and risks

- One migration + RLS table (high-blast-radius: migration head, Supabase sync, OpenAPI).
- Confirmed TIME findings start moving the Coherence Score; the score version change makes this explicit but historical comparisons break at the boundary.
- See §Open questions.

## Landing

Docs-only PR adding this file under `docs/architecture/decisions/` (the only exception to the freeze); Slice 1 implementation PR only after #1110 is merged.
