# ADR-Faithfulness Audit — Coherence Engine (2026-08-16)

**Author:** Fable (Orchestrator), autonomous session
**Scope:** Does the built coherence engine implement the ratified ADRs (ADR-009 scoring, ADR-017 two-tier orchestration)? Triggered by a contract-manager review of the live "Bombeo Mandem" pilot report that surfaced a score-vs-findings inversion and a shallow audit (1 finding on a full triplet).
**Verdict:** **Partially. The two most important coherence ADRs are diverged or dormant.** The pilot's shallow, previously-inverted report is a direct symptom, not a mystery bug.

---

## Executive summary

| ADR | Intended | Built state | Severity | Fix direction |
|---|---|---|---|---|
| **ADR-017** two-tier cross-doc orchestration | Tier-1 per-doc → typed `DocumentArtifact` → **Tier-2 ProjectGraph** async: align → **real cross-doc coherence (6 cats, many docs, LLM-on)** → diff → health → alerts → HITL | **Built + wired, FLAG-GATED OFF** (`feature_v3_project_graph`, `coherence_v2_enabled=False`). User-facing `/evaluate` runs the **old per-request path** the ADR calls "starved". | **CRITICAL** | Finish + canary-cut-over Tier-2; make it a true cross-doc *comparison*, not an aggregation. |
| **ADR-017** (depth) cross-doc *comparison* | Compare entities/values **across** documents (contract total vs budget sum, contract dates vs schedule) | Tier-2 `cross_doc_coherence` only **aggregates** per-document `coherence_findings` + `extracted_risks` and re-scores; `align_entities` exists but the coherence node does not compare across artifacts. | **HIGH** | Add real cross-document comparators (the `DET-CRS-*` family, fed assembled cross-doc data). |
| **ADR-009** §6 conflict aggregator | A critical conflict → `status=conflicting_evidence`, deterministic hard penalty (critical → 0) | Live scorer (`scoring.py::ScoringService`) uses an **exp-baseline model** with no conflict→state transition; a critical alert barely moved the score (82.4). Fixed only by a **cap band-aid** (#532). | **HIGH** | Implement the ADR-009 state-machine + conflict-penalty as the authoritative model; fold #532's caps into it. |
| **ADR-009** scoring-model unity | One canonical scorer | **Four** coexisting implementations: `scoring.py::ScoringService` (exp-baseline + #532 caps, **LIVE** on `/evaluate`), `domain/subscore_calculator.py` (penalty, `critical=-30`), `services/v2/category_aggregator.py` (`base×severity×evidence_certainty`, `critical=0.1`, shadow), `domain/category_state_machine.py` (states). | **HIGH** | Converge to ONE canonical **graduated** scorer per the ADR-009 2026-08-16 amendment (conflict ≠ 0); delete/quarantine the rest; one path across evaluate/persist/dashboard/export/Tier-2/alerts. |
| **ADR-009** detection certainty | Higher certainty ⇒ stronger penalty | v2 `adjusted = base × severity × evidence_certainty` is **inverted** — a *less*-certain conflict scores *lower* (harsher), only partly masked by a 0.90 floor in `conflict_service.py`. | **MEDIUM** | Correct so certainty scales the *penalty* (more certain ⇒ lower score); propose + test before impl. |
| **ADR-009** conflict → 0 (2026-08-16 decision) | A critical conflict ≠ automatic zero | v2 `critical=0.1` multiplier drives a critical to ~near-zero; the §6 body reads conflict→0. | **HIGH (superseded)** | Per the 2026-08-16 governing amendment: graduated score, `conflicting_evidence` decoupled from zero; #532 ceilings interim. |
| **ADR-009** §8.3 MAE cutover guard | MAE > 15 vs calibration set auto-blocks the flag | Conflict detection + MAE guard reported stubbed/hardcoded (v2 ~45%). Shadow "live" is a v1-translation shell. | **MEDIUM** | Real conflict service + MAE guard before any cutover. |
| **ADR-009** §2.1 null-not-zero | Absence of evidence NEVER = 0 | **Faithful.** TECHNICAL renders `null`/"Insufficient evidence"; frontend does not `?? 0`. | OK | Preserve. |

**Bottom line:** the successor architecture you ratified (ADR-017) is ~45% complete and switched off; the live engine is the exact "starved, per-document" path ADR-017 was written to replace; and the live scorer is not the ADR-009 model. The pilot behaviour is fully explained by these three facts.

---

## Evidence

### 1. ADR-017 Tier-2 is built, wired, and OFF
- Graph exists with the exact ADR-017 spine: `apps/api/src/analysis/adapters/graph/project_graph.py` nodes `load_current_artifacts → align_entities → cross_doc_coherence → change_impact → health → snapshot_delta → alerts → hitl`.
- Wired: `analysis/factories/orchestrator_factory.py` → `persist_artifact_and_enqueue_project_graph(result)` → `core/tasks/project_graph_tasks.py::enqueue_project_graph` (async Celery), governed by `project_graph_governance.py`.
- Gated: `project_graph.py::is_project_graph_enabled(tenant_id)` checks flag `feature_v3_project_graph`; `config.py` `coherence_v2_enabled=False` default.
- The **user path** (`coherence/router.py::evaluate_project_coherence`) calls `evaluate_coherence_async(clauses, …)` directly — the per-request "starved" path, independent of Tier-2.

### 2. Tier-2 aggregates, it does not compare
- `project_graph.py::_aggregate_cross_doc_inputs` builds signals from each `artifact.extracted_risks` + `artifact.coherence_findings`, then `cross_doc_coherence` calls `evaluate_coherence_async([], project_id, seed_signals=…, seed_coverage=…)`. It re-scores **per-document findings aggregated together** — there is no node that forms a cross-document *pair* (contract value vs budget sum vs schedule date) for the LLM or a comparator. The genuine cross-doc deltas depend on the deterministic `DET-CRS-*` rules, which need assembled cross-document data that is not built (only `DET-BUD-SUM`/`DET-CRS-BUDCON` had its BOM-vs-contract data assembled → the 1 pilot finding).

### 3. Live scorer ≠ ADR-009 §6
- ADR-009 §6 pseudocode: `if conflicts.hard_conflict: emit(status="conflicting_evidence", score = 0 if critical else 30)`.
- Live `scoring.py::_calculate_detailed_with_coverage`: `score = baseline × e^(−λ·density)` with `HeuristicBaselineProvider` giving a clean-elsewhere category the **HIGH (90)** baseline. The DET-BUD-SUM *critical* only decayed Budget 90→82.4, and dragged the clean categories to 80 — the inversion the pilot showed. No `conflicting_evidence` transition fires. #532 added monotonic severity caps to force correct ordering, but that patches the *symptom*; the ADR-009-faithful behaviour is a state transition + deterministic penalty.
- The LLM applicability gate (`coherence/graph/nodes.py`) only evaluates `(clause, rule)` when `rule_category == infer_category(clause)` → single-category, no cross-category/cross-doc semantic checks. Structurally cannot produce the audit depth ADR-017 promises.

---

## What this means for the roadmap
The "deeper audit" is **not new invention** — it is **(a) finish + cut over ADR-017 Tier-2**, **(b) make it a true cross-document comparator**, and **(c) make the scorer ADR-009-faithful**. The specialist+router **agent** evolution (VP direction, Hermes) is exactly what ADR-017 *deferred* ("supervisor-worker / agent-mesh — a useful mid-term evolution, premature before the temporal spine exists"). Sequence and design are in **ADR-023** (companion). Honesty invariant (ADR-009 §2.1) is preserved throughout — no dimension is ever scored without evidence.
