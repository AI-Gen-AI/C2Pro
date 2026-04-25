# Coherence Score v1 — Pipeline Consolidation + Correctness (Pre-Signature Audit)

## Phase Scope (Read First)

This PRD covers **only the pre-signature audit phase** — the moment a procurement director is preparing to award a multi-million-euro package and needs a defensible Coherence Score on the contract + schedule + budget triplet.

**Explicitly out of scope (future PRDs):**
- **Post-signature / production-phase audit** — continuous monitoring during project execution, change-order detection, claims-precursor alerting. Highly valuable, distinct buyer journey, deferred to its own PRD once v1 is fully shipped and validated.
- **WBS deepening, Stakeholder/RACI maturity, full Decision Intelligence surface** — adjacent capabilities that depend on a stable v1 scoring contract. Defer until this PRD is fully implemented and corpus-validated.

The scope discipline matters: shipping a defensible pre-signature score is the activation moment that gets C2Pro into the procurement-director's workflow. Production-phase capabilities only matter if pre-signature is trustworthy first.

---

## Problem Statement

A procurement director uploading a single contract receives Coherence Score = 100/100 — a perfect score on a tridimensional audit that didn't have the other two dimensions. The pipeline conflates "no high-impact risks found" with "perfect coherence," and a parallel pipeline silently returns the same answer through a different code path. For an audit product whose entire value proposition is defensibility before a multi-million-euro signing decision, default-to-100-on-no-evidence is the exact failure mode that gets auditors fired.

## Evidence

- Direct user report (2026-04-24): uploaded a single contract, received Coherence Score = 100/100 with no warning that the schedule + budget dimensions were absent.
- `apps/api/src/coherence/domain/rules_engine.py:43` — categories initialize to 100, only decrease on explicit violations.
- `apps/api/src/analysis/domain/coherence_derivation.py:112-123` — flags `schedule_within_contract`, `technical_consistent`, `legal_compliant`, `quality_standard_met` default to `True` unless extraction surfaces HIGH/CRITICAL risks in that exact category.
- `apps/api/src/coherence/scoring.py:144` — `ScoringService.calculate_from_signals()` returns `100.0` when the signal list is empty.
- `apps/api/src/coherence/llm_integration.py:409-414` — `analyze_multi_clause_coherence()` returns `overall_coherence_score=100` hardcoded when fewer than 2 clauses exist.
- Two parallel scoring pipelines coexist (LangGraph N8 → `ScoreFromExtractionUseCase`; HTTP `/coherence/evaluate` → 7-node subgraph). Both default to 100 on empty input, by different mechanisms.
- Alert generation infrastructure exists (`coherence/alert_generator.py`, `coherence/services/alerts/generator.py`) with templated messages, severity mapping, fingerprint dedup, and auto-resolve on re-analysis — but is wired to the deprecated flag-based path, not the canonical one.

## Proposed Solution

Consolidate to a single canonical scoring pipeline (`/coherence/evaluate` 7-node subgraph + `ScoringService` exponential decay), replace default-to-100 with explicit `InsufficientEvidence` semantics (`score=null` + reason + `meta_alert`), build out the evaluator registry to a defensible v1 target of 18 (12 deterministic + 6 LLM-backed across the 6 C2Pro categories) behind a domain-layer `LLMRulePort`, persist a `score_version` column with a hard cut-off date (no historical recomputation), wire the existing `AlertGeneratorService` into the canonical pipeline so every finding becomes an actionable alert the director can quote in vendor correspondence, and delete the dead and duplicated code that fragments the architecture today.

## Key Hypothesis

We believe replacing default-to-100 semantics with `InsufficientEvidence` + a 12+6 evaluator registry behind a clean hexagonal port + a `score_version` audit contract + alert-generation-on-every-finding will give procurement directors a Coherence Score they can cite in a >€5M sign-off decision and a set of alerts they can quote back to the vendor.

We'll know we're right when: (a) zero `score=100` results emerge from contract-only uploads in the golden corpus, (b) the corpus shows ≥85% recall on cross-doc contradictions, (c) every detected finding produces a persisted alert with a stable fingerprint that auto-resolves on re-analysis, (d) a procurement-director user can defend the score and forward specific alerts to a vendor by quoting the version + reason fields.

## What We're NOT Building

- **27 evaluators** — aspirational; trim to 18 measured ones for v1, scale post-corpus-validation.
- **Historical recomputation of past scores** — rewrites the audit trail of an audit tool. `score_version` + cut-off only.
- **LangSmith LLM-node spans during canary rollout** — wait for 100% rollout to avoid mixing canary and baseline traces.
- **Post-signature / production-phase monitoring** — change-order detection, continuous re-audit, claims-precursor alerts. Future PRD; the pre-signature score must be trustworthy first.
- **WBS/Stakeholder/RACI deepening, full Decision Intelligence UI surface** — depends on a stable v1 scoring contract. Future PRD.
- **Public-sector tender / pliego compliance** — adjacent and tempting; different workflow (compliance vs. coherence). v2.
- **Residential / consumer contracts, M&A diligence, claims management** — different buyers, different products.
- **Pure clause-by-clause legal review** — Verofika's lane.
- **Sub-30s interactive scoring** — async <10min is the constraint; interactive is a different product.

## Success Metrics

| Metric | Target | How Measured |
|--------|--------|--------------|
| `score=100` on contract-only golden bundles | 0 | Golden corpus regression test (CI) |
| Cross-doc contradiction recall | ≥85% | Golden corpus expected-issues vs. detected-issues, per dimension |
| `score=null` + reason on insufficient evidence | 100% of insufficient cases | Unit + corpus tests |
| Findings → persisted alerts with stable fingerprint | 100% of v1 evaluator outputs | `AlertGeneratorService.process_violations` integration test |
| Auto-resolve correctness on re-analysis | 100% (resolved alert reopens iff violation re-detected) | Re-analysis integration test |
| LLM cost per full audit | <€15–25 | `core/ai/usage_logger.py` per-tenant aggregation |
| Audit latency (full tridimensional) | <10 min p95 | Performance benchmark suite (`scripts/run_performance_benchmarks.py`) |
| Domain-layer infra-import violations | 0 | `import-linter` / grep gate in CI |
| Pipelines actively producing scores | 1 | Code grep + ADR |

## Open Questions

- [ ] Cut-off date for `score_version=v1`: post-merge of consolidation PR, or post-corpus-validation gate?
- [ ] How to surface `score_version` in the dashboard UI without confusing existing users — badge, tooltip, separate filter?
- [ ] LLM rule definitions in `qualitative_rules.yaml` — keep YAML as source of truth or migrate to typed Python registry?
- [ ] `meta_alert` for `InsufficientEvidence`: emit through existing `AlertGeneratorService` template machinery (new `AlertType.AUDIT_INCOMPLETE` + template) or a separate path? Recommend the former — single alert surface, single fingerprint contract.
- [ ] Alert templates currently in Spanish (`alert_generator.py:14-28`) — bilingualize for v1 or defer to v1.1? (User base in Spain + EU EPC market.)
- [ ] Patent priority date (OEPM Spain) — file before or after this PRD ships? (Affects what can be discussed publicly.)

---

## Users & Context

**Primary User**
- **Who**: Procurement Director / Project Procurement Manager at an EPC contractor or industrial project owner, preparing to award a multi-million-euro vendor package.
- **Current behavior**: Manually cross-references contract draft (Legal), Gantt (Planning), and cost plan (Finance) — three documents from three teams, each authored months apart in different systems.
- **Trigger**: Pre-signature anxiety on a >€5M package the day before the sign-off deadline. "I don't trust that the Gantt reflects the contract milestones, which I'm not sure matches the cost line in SAP."
- **Success state**: A defensible, evidence-backed verdict — sign with confidence or push back on specific contradictions before they become claims, change orders, or liquidated damages.

**Job to Be Done**
When I'm preparing to award a multi-million-euro package and I have a contract draft, a project schedule, and a cost plan authored by three different teams over three different months, I want to get a defensible, evidence-backed verdict on whether these three documents tell the same story, so I can either sign with confidence or push back on specific contradictions before they become claims, change orders, or liquidated damages.

**Non-Users**
- Residential/consumer contracts (no cronograma + presupuesto trinity).
- Pure legal review without schedule/budget (Verofika's lane).
- Construction site workers, foremen, subcontractor crews (consume decisions, don't trigger audits).
- Individual freelancers / SMBs without project structure.
- Public-sector pliego compliance in isolation (different workflow — v2 candidate).
- M&A due diligence (different buyer — corporate development, not procurement).
- Post-execution claims management (reactive, not preventive — different competitor).

---

## Solution Detail

### Core Capabilities (MoSCoW)

| Priority | Capability | Rationale |
|----------|------------|-----------|
| Must | Consolidate to single pipeline (`/coherence/evaluate` 7-node + `ScoringService`); deprecate flag-based path | Two pipelines = two scores = no defensible score |
| Must | Replace default-to-100 with `InsufficientEvidence` semantics across both empty-signals and `poor_extraction_quality` | The exact failure mode auditors get fired for |
| Must | `score_version` column + hard cut-off date; no historical recomputation | Audit-trail integrity; legal exposure with paying customers |
| Must | Domain-layer `LLMRulePort`; move `AnthropicWrapper` imports out of `coherence/rules_engine/` and `coherence/llm_integration.py` | Hexagonal purity = TFM defense + future LLM swap |
| Must | Delete `engine_v2.py`, `rules.py`, `service.py`, `services/scoring/calculator.py` | Dead code is corrosive to the architecture argument |
| Must | Build evaluator registry to 18 (12 deterministic + 6 LLM-backed across 6 categories) | 3 today is below the testability floor; 27 is aspirational |
| Must | **Wire `AlertGeneratorService` into the canonical pipeline**: every evaluator finding produces an `AlertCreate` with template + severity + fingerprint; `process_violations` persists with auto-resolve | The director's "push back on specific contradictions" deliverable; infra exists, just needs rewiring to the canonical path |
| Must | **`meta_alert` of type `AUDIT_INCOMPLETE` for `InsufficientEvidence`**, emitted through the same `AlertGeneratorService` (single alert surface, single fingerprint contract) | Converts a null score into an actionable next-step ("supply schedule + budget") that auto-resolves when supplied |
| Must | Extend golden corpus schema with `expected_score_range` and `expected_alerts` (rule_id + count); assert in CI | The bug recurs without regression coverage; alerts must regression-test too |
| Must | LangSmith spans on deterministic nodes with `score_version` tag | Telemetry to validate consolidation; safe during canary |
| Should | Surface `score_version` badge in dashboard UI | User-facing audit clarity |
| Should | Bilingualize alert templates (ES/EN) — currently ES-only | EU EPC market is multilingual; small effort, large credibility gain |
| Could | Per-evaluator false-positive/false-negative metrics on golden corpus runs | Foundation for evaluator pruning + scaling decisions |
| Could | LangSmith data-residency audit before any span goes live | EU-only requirement; verify span attributes carry no contract content |
| Won't (this PRD) | Scale to 27+ evaluators | Without corpus FP/FN data, additions are decoration |
| Won't | LLM-node LangSmith spans during canary | Mixes canary + baseline; wait for 100% rollout |
| Won't | Historical score recomputation | Rewrites audit trail |
| Won't | Production-phase continuous re-audit / change-order detection | Out-of-scope phase; future PRD |
| Won't | WBS/Stakeholder/RACI maturity uplift | Depends on stable v1 scoring; future PRD |

### MVP Scope

The minimum to validate the hypothesis = the four "Must" decisions that land the credibility fix: (1) consolidate, (2) `InsufficientEvidence` semantics, (3) wire `AlertGeneratorService` into canonical path, (4) dead-code delete. With these alone, the score becomes truthful, and findings become actionable alerts the director can act on. Evaluator scaling, boundary cleanup, telemetry, and migration follow but are not gating for the credibility fix.

### User Flow

1. Procurement director uploads contract + schedule + budget (or any subset) via `/analysis/analyze`.
2. LangGraph runs N1–N17 extraction; N8 calls the consolidated `/coherence/evaluate` subgraph (7 nodes: prepare_context → deterministic_evaluate → llm_semantic_evaluate → rag_similarity_check → cross_clause_eval → scoring_arbiter → format_output).
3. `scoring_arbiter` aggregates `FindingSignal` objects via `ScoringService` exponential decay; if signals are insufficient OR `poor_extraction_quality` flag set, returns `score=null` + `reason="insufficient_evidence"` + `missing_dimensions=[...]`.
4. `format_output` invokes `AlertGeneratorService.process_violations(project_id, [AlertCreate(...) for finding in findings])`. New findings → new alerts; recurring findings → existing alerts updated; resolved findings (no longer detected) → auto-resolved.
5. If `InsufficientEvidence`, `format_output` emits a `meta_alert` of type `AUDIT_INCOMPLETE` through the same service ("Audit incomplete — schedule and/or budget not supplied; score withheld until full triplet provided").
6. Dashboard surfaces `score`, `score_version` badge, ranked findings with citations, and persisted alerts (with severity, status, and the templated message the director can copy into vendor correspondence).
7. Director either signs with confidence, pushes back on specific alerts (citing the templated message), or supplies missing dimensions to dissolve the `meta_alert` and obtain a full score.

---

## Technical Approach

**Feasibility**: MEDIUM — bug fix is trivial, consolidation + boundary cleanup + 18-evaluator build is non-trivial, eval harness extension is straightforward, alert wiring is mostly rewiring of existing infrastructure.

**Architecture Notes**
- **Canonical pipeline**: `/coherence/evaluate` HTTP → `coherence/graph/graph.py` (7-node subgraph) → `coherence/scoring.py::ScoringService.calculate_from_signals()`. Main LangGraph N8 rewires to call the same path internally (no parallel implementation).
- **Domain port**: define `LLMRulePort` (Protocol) in `coherence/domain/`; current `AnthropicWrapper` callers move to `coherence/adapters/ai/llm_rule_evaluator.py` and inject via constructor.
- **Evaluator registry**: extend `coherence/rules_engine/registry.py` to 18 entries (12 deterministic + 6 LLM-backed; 3 + 1 per category × 6 categories). YAML rules in `qualitative_rules.yaml` become typed `LLMRuleEvaluator` instances at startup.
- **InsufficientEvidence semantics**: `ScoringService.calculate_from_signals(signals=[])` returns `ScoringResult(score=None, reason="insufficient_evidence", missing_dimensions=[...])`. Same return shape when `poor_extraction_quality` flag is set upstream.
- **Alert generation wiring**: `format_output` node consumes findings + scoring result. For each finding → build `AlertCreate` via existing template machinery (`coherence/alert_generator.py:14-55`) → call `AlertGeneratorService.process_violations()` (which already handles fingerprint dedup + auto-resolve). Add `AlertType.AUDIT_INCOMPLETE` + template for `meta_alert` path. The 18 v1 evaluators each declare their `rule_id` to align with the existing template/severity tables; missing template = build-time error.
- **Persistence**: Alembic migration adds `score_version: enum('v0_flag_based','v1_exponential_decay')` and `score_reason: text NULL` and `score_missing_dimensions: jsonb NULL` to `coherence_results`. `SqlAlchemyCoherenceRepository.save()` writes the version of the pipeline that produced the row. Hard cut-off: rows before cut-off date remain `v0`, immutable.
- **Telemetry**: structured spans on `prepare_context`, `deterministic_evaluate`, `rag_similarity_check`, `cross_clause_eval`, `scoring_arbiter`, `format_output` (skip `llm_semantic_evaluate` until rollout=100%). Every span tagged `score_version`. EU residency audit on span attributes before enabling.

**Technical Risks**

| Risk | Likelihood | Mitigation |
|------|------------|------------|
| Consolidation breaks UI consumers reading from old `coherence_score` field | M | Keep field, write same value, add `score_version` alongside |
| Domain-port refactor introduces regression in LLM rule behavior | M | Snapshot tests on 5 representative rule outputs before refactor |
| 18-evaluator build inflates Claude cost beyond €25/audit | L | Deterministic-first: each evaluator has a deterministic guard before LLM fallback |
| Alert fingerprint changes between v0 and v1 cause spurious "new" alerts on first v1 run | M | One-time backfill of fingerprints OR document that v1 cut-off resets the alert ledger; ADR decision |
| `meta_alert` for `AUDIT_INCOMPLETE` floods inbox if a tenant uploads many partial audits | M | Throttle/group by project_id; existing `AlertGeneratorService` already supports grouping (`SUMMARY_TEMPLATES`) |
| LangSmith span attributes leak contract content (EU residency violation) | M | Allowlist span attribute schema; CI test rejects PRs that add new attributes without review |
| Dead-code deletion removes something an unscanned external module imports | L | Pre-deletion grep + 24h staging window before deploy |
| `score_version` UX confuses customers ("why are old scores different?") | M | Dashboard badge + tooltip; ADR + customer comms ready before cut-off |
| Patent priority date — public discussion of methodology before OEPM filing | M | Defer all public communication of the consolidated methodology until OEPM filed |

---

## Implementation Phases

<!--
  STATUS: pending | in-progress | complete
  PARALLEL: phases that can run concurrently (e.g., "with 3" or "-")
  DEPENDS: phases that must complete first (e.g., "1, 2" or "-")
  PRP: link to generated plan file once created
-->

| # | Phase | Description | Status | Parallel | Depends | PRP Plan |
|---|-------|-------------|--------|----------|---------|----------|
| 1 | Dead-code deletion + ADR | Delete `engine_v2.py`, `rules.py`, `service.py`, `services/scoring/calculator.py`. Single ADR documenting why. | pending | - | - | - |
| 2 | Pipeline consolidation + InsufficientEvidence | Rewire main LangGraph N8 to `/coherence/evaluate` subgraph. Replace default-100 with `score=null` + reason in `ScoringService`, `llm_integration`, and `coherence_derivation`. | pending | - | 1 | - |
| 3 | Domain boundary fix (LLMRulePort) | Define `LLMRulePort` in `coherence/domain/`. Move `AnthropicWrapper` callers to `coherence/adapters/ai/`. Inject via constructor. Snapshot regression tests first. | pending | with 2, 4 | 1 | - |
| 4 | `score_version` migration + ADR | Alembic migration: `score_version`, `score_reason`, `score_missing_dimensions`. Repository writes new fields. Hard cut-off date set. UI badge stub. | pending | with 2, 3 | 1 | - |
| 5 | Evaluator registry expansion to 18 | Build 12 deterministic + 6 LLM-backed evaluators across 6 categories using `LLMRulePort`. Wire into `scoring_arbiter` node. Each declares `rule_id` aligned with alert template tables. | pending | - | 3 | - |
| 6 | Alert generation wiring + `meta_alert` | `format_output` node calls `AlertGeneratorService.process_violations()` for findings. Add `AlertType.AUDIT_INCOMPLETE` + template + severity. Decide alert-ledger v0→v1 transition policy in ADR. | pending | with 5 | 2, 5 | - |
| 7 | Golden corpus extension | Add `expected_score_range` and `expected_alerts` (rule_id + min count) to bundle schema. Author expectations for 15 existing bundles. CI assertion. | pending | with 5, 6 | 2, 4 | - |
| 8 | Telemetry on deterministic nodes | Structured LangSmith spans on 6 of 7 nodes (skip LLM node). `score_version` tag. EU-residency span-attribute audit + allowlist. | pending | with 5, 6, 7 | 2 | - |
| 9 | UX + customer comms for `score_version` and alerts | Dashboard badge + tooltip. Alert-list view shows templated message + severity + status. Customer communication template. Activate cut-off date. | pending | - | 4, 6, 7 | - |

### Phase Details

**Phase 1: Dead-code deletion + ADR**
- **Goal**: Eliminate the architecture-confusing duplicates before any new code lands.
- **Scope**: Delete the four files; one ADR explaining what each was, why it's gone, and the consolidated path's location.
- **Success signal**: `pytest` green; grep shows zero remaining imports; ADR merged.

**Phase 2: Pipeline consolidation + InsufficientEvidence**
- **Goal**: One pipeline, one scoring contract, no false 100s.
- **Scope**: Rewire main LangGraph N8 → 7-node subgraph. Modify `scoring.py:144`, `llm_integration.py:409-414`, and `coherence_derivation.py` flag-defaulting to produce `ScoringResult(score=None, reason=..., missing_dimensions=[...])`. Deprecate `ScoreFromExtractionUseCase`, `CoherenceCalculationService`, flag-based `CoherenceRulesEngine` (mark with deprecation warning, removal in next sprint).
- **Success signal**: Unit tests cover 4 insufficient-evidence cases (no signals, poor extraction quality, single-clause LLM analysis, contract-only upload). Manual upload of contract-only PDF returns `score=null + reason="insufficient_evidence"`.

**Phase 3: Domain boundary fix (LLMRulePort)**
- **Goal**: Pass the hexagonal-purity gate.
- **Scope**: Define port in `coherence/domain/`. Move `AnthropicWrapper` calls into `coherence/adapters/ai/llm_rule_evaluator.py`. Constructor injection at composition root.
- **Success signal**: `import-linter` (or grep CI gate) reports zero infra imports in `coherence/domain/` and `coherence/rules_engine/`. Snapshot tests on 5 representative LLM rule outputs match pre-refactor baseline.

**Phase 4: `score_version` migration + ADR**
- **Goal**: Audit trail integrity preserved across the algorithm change.
- **Scope**: Alembic migration adds `score_version`, `score_reason`, `score_missing_dimensions` columns. `SqlAlchemyCoherenceRepository` writes them. Cut-off date constant in config. UI badge component stub.
- **Success signal**: Migration applies forward + reverses cleanly. ADR explains immutability of pre-cut-off rows.

**Phase 5: Evaluator registry expansion to 18**
- **Goal**: Defensible breadth — 3 deterministic + 1 LLM per category × 6 categories.
- **Scope**: Implement the 12 deterministic evaluators against existing `RuleEvaluator` ABC. Wrap 6 YAML rules as `LLMRuleEvaluator` instances using `LLMRulePort`. Wire all 18 into `registry.py`. `scoring_arbiter` consumes their `FindingSignal` outputs. Each evaluator declares `rule_id` matching the alert template tables (build-time check rejects mismatches).
- **Success signal**: Registry shows 18 entries. Each evaluator has a unit test. Per-category coverage table in ADR.

**Phase 6: Alert generation wiring + `meta_alert`**
- **Goal**: Every finding becomes an actionable, persisted, deduplicated alert; insufficient evidence becomes its own actionable alert.
- **Scope**: `format_output` node converts findings → `AlertCreate` list → `AlertGeneratorService.process_violations()`. Extend `RULE_TITLES`, `TEMPLATES`, `RULE_SEVERITIES` for any v1 evaluator missing entries. Add `AlertType.AUDIT_INCOMPLETE` + template ("Audit incomplete — supply {missing_dimensions} for full Coherence Score") + `MEDIUM` severity. ADR decides v0→v1 alert-ledger transition (recommend: v1 cut-off resets the ledger; old alerts archived but immutable).
- **Success signal**: Integration test: re-running the same audit twice produces zero new alerts (fingerprint dedup works). Re-running after vendor revision auto-resolves the corresponding alert. Contract-only upload produces 1 `AUDIT_INCOMPLETE` meta_alert; supplying schedule + budget auto-resolves it.

**Phase 7: Golden corpus extension**
- **Goal**: Regression coverage for the score AND the alerts, not just the issues.
- **Scope**: Add `expected_score_range: {min, max, reasoning}` and `expected_alerts: [{rule_id, min_count, severity}]` to bundle schema. Author expectations for 15 existing bundles. Update `evals/run_evals.py`. Update CI workflow.
- **Success signal**: CI fails if any bundle's score falls outside expected range OR fails to produce expected alerts. New bundles required to declare ranges or be marked `score_check: skip` with reason.

**Phase 8: Telemetry on deterministic nodes**
- **Goal**: Observability without LangSmith canary collision and without EU-residency leak.
- **Scope**: LangSmith spans on 6 of 7 subgraph nodes (skip `llm_semantic_evaluate`). Allowlist of span attribute schema reviewed for EU residency. `score_version` tag on every span. Alert-creation events emit a span tagged with `rule_id` + `severity` (no contract content).
- **Success signal**: Spans visible in LangSmith for staged audits. Allowlist enforced via CI. Documented in `docs/runbooks/`.

**Phase 9: UX + customer comms for `score_version` and alerts**
- **Goal**: Activate the cut-off and the alert surface without surprising customers.
- **Scope**: Dashboard badge + tooltip explaining the version. Alert-list view: severity sort, status filter, copy-to-clipboard for vendor correspondence. Customer communication template (email + in-app banner). Set cut-off date constant to live value.
- **Success signal**: Internal QA on dashboard. Alert list usable by a non-technical procurement director. Comms reviewed. Cut-off active.

### Parallelism Notes

- Phase 1 must complete first — dead code deletion clarifies the ground for everything else.
- Phases 2, 3, 4 run in parallel after Phase 1 (separate code areas: pipeline rewire, port refactor, schema migration).
- Phases 5, 6, 7, 8 run in parallel after their dependencies clear (5 needs the port; 6 needs new scoring contract + evaluators; 7 needs new scoring contract + migration; 8 needs the consolidated nodes).
- Phase 9 is the closing gate — needs the migration (4), the alert wiring (6), and the corpus assertion (7) green.

---

## Decisions Log

| Decision | Choice | Alternatives | Rationale |
|----------|--------|--------------|-----------|
| Phase scope | Pre-signature audit only; production-phase + WBS/Stakeholder deferred | Single PRD covering all phases | One sharp blade beats two dull ones; pre-signature is the activation moment |
| Pipeline strategy | Consolidate to `/coherence/evaluate` 7-node + `ScoringService` | Keep both; consolidate to flag-based | Exponential-decay path is the architecturally future-proof one; two pipelines = no defensible score |
| Empty-input semantics | `score=null` + reason="insufficient_evidence" + `meta_alert` | Return 0; return 100 (current); raise exception | A null with reason is auditable; 0 implies analysis happened; 100 is the disqualifying bug |
| Alert generation | Wire existing `AlertGeneratorService` into canonical pipeline; `meta_alert` uses same service | Build new alert path; defer alerts to v1.1 | Infrastructure exists; rewiring is small scope, large value; single alert surface = single fingerprint contract |
| Alert ledger v0→v1 transition | v1 cut-off resets the ledger; old alerts archived but immutable | Backfill fingerprints; recompute alerts | Same audit-trail-integrity reasoning as score_version |
| Evaluator count v1 | 18 (12 det + 6 LLM, 3+1 per category × 6) | 27 (aspirational); 3 (current) | 18 fits the testability budget of the current 15-bundle corpus; scale post-FP/FN measurement |
| Backfill strategy | `score_version` column + hard cut-off, no recompute | Recompute all history; recompute on-read | Audit-trail rewrite is legal exposure; recomputation is API cost + canary collision |
| LangSmith spans | Deterministic nodes now, LLM nodes after rollout=100% | All nodes now; none until rollout=100% | Avoids canary/baseline trace mixing; gives consolidation telemetry now |
| Domain boundary | `LLMRulePort` in domain, `AnthropicWrapper` in adapter | Leave current imports | TFM defense + future LLM swap rests on hexagonal purity |
| Dead-code timing | Delete in this PRD (Phase 1), not "later" | Defer to follow-up | Dead code is corrosive to the architecture argument every reviewer encounters |

---

## Research Summary

**Market Context**
- Procurement-Director-as-buyer is undertargeted by existing tools: Verofika (clause-by-clause legal review), SAP Ariba (procurement workflow), Long International + HKA (post-execution claims). The pre-signature tridimensional audit is an open lane.
- Spain public-tender market is adjacent and tempting; deferred to v2 to avoid splitting focus.
- Anthropic-EU GA timing affects data-residency story; track but don't block on.

**Technical Context**
- Active pipeline path is `/coherence/evaluate` 7-node subgraph; main LangGraph N8 calls a parallel flag-based path that is the source of the `score=100` bug.
- `qualitative_rules.yaml` holds 15–20 LLM rule definitions not wired into the main pipeline — the unrealized half of the registry.
- Golden corpus harness (15 bundles, schema-validated, CI workflow) merged 2026-04-21 — does not yet assert score ranges or expected alerts; schema extension is a 2-file change.
- Alert generation infrastructure mature: `AlertGenerator` (templated messages per rule, severity mapping, summary grouping) + `AlertGeneratorService` (persistence, fingerprint dedup, auto-resolve on re-analysis) — wired to deprecated flag-based path; rewiring to canonical path is small scope.
- LangSmith integration is gated behind `LANGSMITH_ROLLOUT_PERCENTAGE` env var with MD5 tenant canary cohorts; deterministic-node spans don't collide with this.
- RLS enforcement strong: `SqlAlchemyCoherenceRepository._apply_tenant_filter()` joins ProjectORM for tenant scoping.
- Dead code present: `engine_v2.py`, `rules.py`, `service.py`, `services/scoring/calculator.py` — none imported, all candidates for Phase 1 deletion.
- Domain boundary violations confirmed at `coherence/rules_engine/llm_evaluator.py:41-43` and `coherence/llm_integration.py:32-39` (AnthropicWrapper imported into the rules domain).

---

*Generated: 2026-04-24*
*Status: DRAFT — needs validation on open questions (cut-off date, UI surface, YAML vs typed registry, meta_alert routing through AlertGeneratorService, alert-template bilingualization, patent timing)*
