# Coherence Score™ v2 Redesign Blueprint (Evidence-Aware, Explainable, Industry-Ready)

**Date:** 2026-05-24  
**Scope:** C2Pro repository analysis + target architecture for production rollout  
**Critical invariant:** **Missing evidence must NEVER generate score = 0.**

---

## 1) Problem diagnosis

### 1.1 Where the current implementation fails

After reviewing the active coherence pipeline, there are three systemic issues:

1. **Coverage and coherence are mixed into one number**, so missing dimensions can depress score outcomes instead of being reported explicitly.
2. **Legacy deterministic path still allows hard zero in category logic** (e.g., budget severe deviation sets category score to `0`) without explicit “evaluation sufficiency” metadata.
3. **Frontend fallback behavior can visually collapse unknown to zero**, especially when nullable scores are rendered as `0` in chart defaults.

### 1.2 Concrete code hotspots

- `ScoringService._calculate_detailed_with_coverage()` computes global score as `mean_assessed * coverage_ratio`, which penalizes missing categories by construction. This violates “lack of evidence is not incoherence.” (`apps/api/src/coherence/scoring.py`)
- `CoherenceRulesEngine.evaluate()` sets category scores to numeric defaults only, with no `status` state machine (`scored`, `insufficient_evidence`, etc.). (`apps/api/src/coherence/domain/rules_engine.py`)
- `ScoreCalculator.calculate()` reads missing category via `.get(category, 100)` and cannot distinguish “not evaluated” from “perfect.” (`apps/api/src/coherence/domain/rules_engine.py`)
- UI fallback `const score = data.coherence_score ?? 0;` can produce misleading visuals. (`apps/web/components/coherence/DashboardClient.tsx`)
- Use-case DTO flow (`CalculateCoherenceUseCase`) currently transports raw integer category scores only; no evidence count/confidence/state metadata. (`apps/api/src/coherence/application/use_cases/calculate_coherence.py`)

### 1.3 File classification / category mapping observations

- Document typing exists in `documents` domain (`DocumentType.SCHEDULE`, `BUDGET`, `TECHNICAL_SPEC`, `QUALITY`, `SCOPE`). (`apps/api/src/documents/domain/models.py`)
- Ingestion maps clause types to coherence categories through deterministic mapping (`LEGAL`, `TIME`, `BUDGET`, `TECHNICAL`, etc.). (`apps/api/src/core/tasks/ingestion_tasks.py`)
- This mapping is workable but **insufficient for evidence quality scoring**, OCR quality gates, and applicability detection.
- Canonical v2 category set remains six dimensions: `SCOPE`, `BUDGET`, `QUALITY`, `TECHNICAL`, `LEGAL`, `TIME`.

### 1.4 Architectural limitations

- No first-class **category status lifecycle**.
- No separation of **coherence vs evidence coverage vs confidence**.
- No structured provenance contract (evidence spans, extraction quality, conflict sets).
- Incomplete support for incremental uploads and longitudinal recalculation with explainable deltas.

---

### 1.5 Local validation of code hotspots (verified)

Validated directly in the repository:

1. `apps/api/src/coherence/scoring.py` contains `_calculate_detailed_with_coverage()` and computes `global_score = round(mean_assessed * coverage_ratio, 1)` (coverage currently penalizes coherence).
2. `apps/api/src/coherence/domain/rules_engine.py` contains `ScoreCalculator.calculate()` using `category_scores.get(category, 100)` default.
3. `apps/web/components/coherence/DashboardClient.tsx` contains `const score = data.coherence_score ?? 0;` fallback.

These checks confirm the migration rationale is grounded in current code behavior.

### 1.6 Additional path validation (verified)

Validated directly in repository tree:

1. `apps/api/src/coherence/application/use_cases/calculate_coherence.py` exists.
2. `apps/api/src/coherence/application/dtos/coherence_dtos.py` exists.

This confirms that the referenced use-case/DTO migration touchpoints are real and implementation planning is anchored to current paths.

## 2) Conceptual redesign

### 2.1 Category state model (mandatory)

Each category must have a status in:

- `scored`
- `insufficient_evidence`
- `not_applicable`
- `conflicting_evidence`
- `error`
- `pending_documents` (operational state for progressive workflows)

### 2.2 Semantics of numeric score

- `score` is nullable.
- `score = 0` is valid **only when**:
  1. `status == scored`
  2. `evidence_count >= min_evidence_threshold`
  3. category coherence is critically contradictory/poor.
- If status is not `scored`, score MUST be `null`.

### 2.3 Triple-axis evaluation

For each category compute independently:

1. **Coherence** (0-100, nullable)
2. **Evidence Coverage** (0-1)
3. **Confidence** (0-1)

This unlocks fair scoring for partial uploads and enterprise explainability.

---

## 3) Scoring methodology

### 3.1 Per-category evaluation pipeline

1. Collect candidate evidence (clauses, tables, entities, dates, amounts, obligations).
2. Validate quality gates (OCR confidence, parser integrity, dedupe, language support).
3. Determine applicability (`not_applicable` when category truly out-of-scope).
4. If applicable but below minimum evidence -> `insufficient_evidence`.
5. Detect cross-document contradictions -> `conflicting_evidence` with conflict set.
6. If evaluable, run rules/LLM hybrid and output `scored` with rationale + trace.

### 3.2 Recommended per-category output

- `status`
- `score` (nullable)
- `confidence`
- `coverage`
- `evidence_count`
- `conflict_count`
- `missing_required_evidence[]`
- `rationale`
- `references[]`

### 3.3 Global model: dual-score contract

- **Coherence Score™**: weighted mean over **only scored categories**.
- **Completeness Score™**: weighted coverage ratio over expected/applicable categories.

Do not collapse these into one number.

---

## 4) Mathematical model evaluation (MVP-focused)

For MVP and near-term enterprise pilots, adopt only:

1. **Weighted averages over scored categories** (transparent and auditable).
2. **Confidence-adjusted diagnostics** (for ranking reliability, not fabricating coherence).
3. **Evidence normalization for coverage/completeness** (cross-project comparability).

Deferred models (Bayesian, regression, fuzzy, graph-native probabilistic scoring) are explicitly out-of-scope for this phase and should not consume sprint capacity until v2 telemetry is stable.

**Hard constraint:** no mathematical model may transform unknown/missing evidence into a coherence score, and never into `0`.

## 5) Alert framework

### 5.1 Alert taxonomy

- `missing_evidence`
- `low_confidence`
- `conflicting_evidence`
- `critical_incoherence`
- `processing_error`
- `data_quality_issue`

### 5.2 Severity levels

- `info`: expected incompleteness (early upload stage)
- `warning`: low confidence / partial coverage
- `high`: strong conflicts requiring review
- `critical`: severe incoherence with high confidence

### 5.3 Trigger examples

- No budget files + applicable project: `missing_evidence` warning.
- OCR avg < threshold: `data_quality_issue` warning.
- Milestone dates mismatch contract dates: `conflicting_evidence` high.
- Deterministic+LLM converge on contradiction with high confidence: `critical_incoherence` critical.

### 5.4 UI behavior

- Show alerts next to each category status badge.
- Missing evidence should display as amber/blue “Needs docs”, not red failure.

---

## 6) Global score calculation

### 6.1 Recommended equations

Let `C` = set of categories with `status=scored`, and `A` = set of applicable categories.

- `CoherenceScore = Σ(w_i * s_i) / Σ(w_i) for i in C`
- `CompletenessScore = Σ(w_i * coverage_i) / Σ(w_i) for i in A`
- `ConfidenceIndex = Σ(w_i * confidence_i) / Σ(w_i) for i in C`

### 6.2 Rules

- If `|C| = 0`: `CoherenceScore = null`, reason=`insufficient_evidence`.
- Never multiply coherence by coverage ratio (that penalizes unknown).
- Exclude `not_applicable` from denominator.

### 6.3 Default category weights (v2 baseline)

For initial rollout, keep compatibility with current production intuition and reporting:

| Category | Weight |
|---|---:|
| SCOPE | 0.20 |
| BUDGET | 0.20 |
| QUALITY | 0.15 |
| TECHNICAL | 0.15 |
| LEGAL | 0.15 |
| TIME | 0.15 |

Notes:
- Weights are applied only over `status=scored` categories for Coherence Score™.
- `not_applicable` categories are excluded from denominator normalization.
- Tenant-specific weight customization can be phase-2, gated behind governance controls.

### 6.4 Minimum evidence thresholds by category (v2 baseline)

| Category | Min evidence | Baseline rationale |
|---|---:|---|
| BUDGET | 3 | Contract + budget artifact + BOQ/cashflow evidence. |
| TIME | 2 | Contract dates + schedule/timeline artifact. |
| SCOPE | 2 | Contract scope clauses + SOW/WBS evidence. |
| TECHNICAL | 2 | Technical specification + BOM/engineering evidence. |
| LEGAL | 1 | Contract/legal clauses can be sufficient initial basis. |
| QUALITY | 2 | Quality specification + certification/HSE evidence. |

These thresholds are rollout defaults; calibration may adjust them after shadow telemetry.

---

## 7) Production JSON schema (proposed)

```json
{
  "project_id": "string",
  "version": "coherence-v2",
  "generated_at": "ISO-8601",
  "global": {
    "coherence_score": 78.4,
    "completeness_score": 0.61,
    "confidence_index": 0.73,
    "status": "partial",
    "score_reason": "scored_categories_only",
    "scored_categories": 4,
    "applicable_categories": 6
  },
  "categories": [
    {
      "category": "BUDGET",
      "status": "insufficient_evidence",
      "score": null,
      "confidence": 0.22,
      "coverage": 0.15,
      "evidence_count": 1,
      "evidence_references": [
        {"document_id": "doc_123", "page": 4, "span_id": "sp_9"}
      ],
      "rationale": "No structured financial tables detected.",
      "detected_conflicts": [],
      "missing_evidence": ["bill_of_quantities", "cost_breakdown", "cashflow"],
      "alerts": [
        {"code": "MISSING_BUDGET_EVIDENCE", "severity": "warning", "confidence": 0.93}
      ],
      "recommendation": "Upload budget workbook or BOQ.",
      "calculation_metadata": {
        "weight": 0.2,
        "min_evidence_threshold": 3,
        "evaluated_rules": [],
        "model_version": "coh-v2.0.0"
      }
    }
  ]
}
```

---

## 8) Frontend recommendations

1. **Status badges per category**: `Scored`, `Needs Evidence`, `N/A`, `Conflict`, `Error`.
2. **Tri-panel card** per category: Score | Coverage | Confidence.
3. **Explicit null score display**: render a dedicated “Pending evidence” gauge-empty state (not numeric), with info icon and tooltip explaining why score is unavailable.
4. **Evidence trace drawer** with page/snippet/source linkage.
5. **Progressive upload banner**: “4/6 categories evaluable” + CTA “Upload missing documents”.
6. **Gauge null-state policy (required)**: show skeleton/empty gauge and coverage progress instead of plotting `0/100`.
7. **Conflict diff UI** for contradictory milestones/obligations.

---

## 9) Backend implementation plan

### 9.1 Affected modules

- `apps/api/src/coherence/scoring.py`
- `apps/api/src/coherence/domain/rules_engine.py`
- `apps/api/src/coherence/application/use_cases/calculate_coherence.py`
- `apps/api/src/coherence/application/dtos/coherence_dtos.py`
- `apps/api/src/core/tasks/ingestion_tasks.py`
- `apps/web/components/coherence/DashboardClient.tsx`

### 9.2 Refactor boundaries

- **Evidence Service**: evidence extraction quality + coverage computation.
- **Category Aggregator (new)**: consumes rule signals from existing RuleEvaluators/Rule Registry (R1–R20) and determines `status`, `score`, `coverage`, `confidence`, and conflict metadata per category.
- **Important compatibility rule**: RuleEvaluators are preserved (not replaced). Flow is `Rules -> Signals -> Category Aggregator -> Triple-axis Output`.
- **Aggregation Service**: global coherence/completeness/confidence.
- **Alert Service**: taxonomy-driven alert generation.

### 9.3 Migration strategy

1. Add v2 DTOs/tables with backward-compatible adapters.
2. Dual-run v1 and v2 in shadow mode (feature flag).
3. Add Alembic migration for `analyses.coherence_breakdown` JSONB contract evolution + backfill for historical analyses.
4. Provide v1->v2 response adapter to preserve public API compatibility during transition.
5. Compare distributions + business review (shadow mode 2-3 weeks with calibration dataset).
6. Switch UI to v2 response contract.
7. Deprecate v1 numeric-only contract with rollback runbook update (CE-P0-06 extension).

### 9.4 Pseudocode

```python
for category in CATEGORIES:
    evidence = evidence_service.collect(category, project_docs)
    applicability = applicability_service.check(category, project_context)

    if not applicability.is_applicable:
        emit(category, status="not_applicable", score=None)
        continue

    if evidence.count < thresholds[category]:
        emit(category, status="insufficient_evidence", score=None)
        continue

    conflicts = conflict_service.detect(category, evidence)
    if conflicts.hard_conflict:
        emit(category, status="conflicting_evidence", score=None)
        alert_service.emit("CRITICAL_CONFLICT", severity="critical") if conflicts.critical else None
        continue

    score, confidence = evaluator.score(category, evidence)
    emit(category, status="scored", score=score, confidence=confidence)
```

---

## 10) Test strategy

### Unit tests
- Status transitions (`insufficient_evidence` != 0).
- Zero-score guardrails (only `scored` + threshold met).
- Coverage/confidence calculations.

### Integration tests
- Incremental upload progression (contract only → +schedule → +budget).
- Contradictory doc conflict detection.
- OCR low-quality handling.

### Evaluation datasets
- Golden corpus with labelled states per category.
- Edge corpus: duplicates, multilingual, noisy OCR, partial sets.

### Regression safeguards
- Contract tests for JSON schema.
- Snapshot tests for explainability payloads.
- Distribution monitoring for score drift.

---

## 11) Risks and tradeoffs

- Potential terminology drift with academic paper wording (“tripolar” vs operational triple-axis).
- More states increase UX complexity.
- Confidence can be misinterpreted as truth probability.
- Graph conflict detection may increase compute cost.
- Dual scoring requires product education.
- Repository root technical debt can increase migration conflict risk (`temp_conflicting_frontend_files/`, `tmp-gh-artifacts/`, legacy agent docs).

Mitigation: align paper lexicon to the production triple-axis contract before publication; release with strong tooltips, glossary, and audit logs. Open a pre-migration cleanup ticket and complete root hygiene before implementation branch cut.

### 11.1 Academic alignment note (tripolar vs triple-axis)

To avoid conceptual confusion:

- **Tripolar algorithm** (temporal + technical + economic) refers to bid/procurement analytical methodology (separate layer).
- **Triple-axis scoring contract** (coherence + completeness + confidence) refers to Coherence Score™ evaluation output semantics.

Both can coexist: one is decision-analysis methodology, the other is scoring/reporting contract.

---

## 12) Final recommended architecture

### Implement immediately (Phase 1)

1. Introduce status machine + nullable category score.
2. Decouple coherence/completeness/confidence.
3. Replace global formula with scored-category normalization.
4. Introduce alert taxonomy for missing/conflicting evidence.
5. Remove UI `?? 0` defaults where score can be unknown.

### Delivery effort estimate (planning baseline)

- Backend Category Aggregator + status machine: **~1 sprint**
- Alembic migration + v1/v2 adapter + rollback updates: **~0.5 sprint**
- Shadow mode + dual-run telemetry on calibration dataset: **~2–3 calendar weeks**
- Frontend null-score gauge state + coverage UX: **~0.5 sprint**

Total execution envelope: **~2 sprints + 2–3 weeks shadow telemetry**.

### Defer to Phase 2+

- Bayesian/regression calibration.
- Graph-native consistency scoring across all documents.
- Tenant-adaptive weighting based on longitudinal outcomes.

### Strategic outcome

This v2 framework turns Coherence Score™ into an **auditable evidence intelligence system** rather than a single opaque number. It is fair with partial data, robust under uncertainty, and suitable for enterprise standardization.
