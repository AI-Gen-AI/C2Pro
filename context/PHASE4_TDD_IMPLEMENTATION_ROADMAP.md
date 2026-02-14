# C2Pro — Phase 4 TDD Implementation Roadmap

> **Versión:** 1.1  
> **Fecha Original:** 2026-02-01  
> **Última Actualización:** 2026-02-14  
> **Estado:** EN EJECUCIÓN — Increments I1-I10 en implementación activa

## Purpose

This roadmap converts the approved AI Master Plan into an incremental, test-first delivery plan for C2Pro's AI core.

It enforces:

- strict TDD (fail -> pass -> refactor)
- traceability from each capability to tests
- mandatory human-in-the-loop controls
- legal-safe behavior (not legal advice)
- LangSmith observability at every critical step

---

## Implementation Status (2026-02-14)

| Increment | Capability                   | Status           | Test Suite Location                         |
| --------- | ---------------------------- | ---------------- | ------------------------------------------- |
| **I1**    | Canonical Ingestion Contract | ✅ Tests written | `tests/` root + `apps/api/tests/modules/`   |
| **I2**    | OCR + Table Parsing          | ✅ Tests written | `tests/` root                               |
| **I3**    | Clause Extraction            | ✅ Tests written | `tests/` root                               |
| **I4**    | Hybrid RAG Retrieval         | ✅ Tests written | `apps/api/tests/modules/retrieval/`         |
| **I5**    | Graph RAG Schema             | ✅ Tests written | `tests/` root                               |
| **I6**    | Coherence Rule Engine        | ✅ Tests written | `tests/` root + `apps/api/tests/coherence/` |
| **I7**    | Risk Scoring                 | ✅ Tests written | `tests/` root                               |
| **I8**    | WBS/BOM Generation           | ✅ Tests written | `tests/` root                               |
| **I9**    | Procurement Intelligence     | ✅ Tests written | `tests/` root                               |
| **I10**   | Stakeholder + RACI           | ✅ Tests written | `tests/` root                               |
| **I11**   | Human-in-the-Loop            | ✅ Tests written | `tests/` root                               |
| **I12**   | LangSmith Observability      | ✅ Tests written | `tests/` root                               |
| **I13**   | E2E Decision Support         | ✅ Tests written | `tests/` root                               |
| **I14**   | Governance/Safety            | ✅ Tests written | `tests/` root                               |

> **Note:** All 14 increment test files exist. Implementation (Green Phase) status varies.  
> See `TEST_SUITE_REPORT.md` for file path details.

---

## Master Plan Traceability Matrix

| Capability (AI Master Plan)                  | Primary Test Suites                                       | Increment(s) |
| -------------------------------------------- | --------------------------------------------------------- | ------------ |
| Document ingestion + normalization           | ingestion unit/integration/contract tests                 | I1, I2       |
| Clause extraction + obligation normalization | extraction unit/integration/eval tests                    | I3           |
| Hybrid RAG retrieval                         | retrieval unit/integration/eval tests                     | I4           |
| Graph RAG schema + relationships             | graph schema + relationship tests                         | I5           |
| Contract vs reality coherence checks         | coherence rule tests + integration tests                  | I6           |
| Risk scoring + Coherence Score               | scoring unit/integration tests                            | I7           |
| WBS/BOM generation                           | generation unit/integration/eval tests                    | I8           |
| Procurement intelligence                     | planning tests                                            | I9           |
| Stakeholder + RACI intelligence              | stakeholder and mapping tests                             | I10          |
| Human-in-the-loop validation                 | review queue + SLA tests                                  | I11          |
| LangSmith observability + drift              | trace + evaluation tests                                  | I12          |
| End-to-end explainable decision support      | E2E scenario tests                                        | I13          |
| Governance/safety/legal safeguards           | policy tests (hallucination/source/confidence/disclaimer) | I14          |

---

## TDD Increments

## I1 — Canonical Ingestion Contract

1. **Tests to write first**
   - Contract test: each chunk must include `doc_id`, `version_id`, `page`, `bbox`, `source_hash`, `confidence`.
   - Unit test: blank pages produce zero chunks.
   - Unit test: malformed document returns typed ingestion error.
2. **Expected failures**
   - Missing chunk schema/validator.
   - Parser returns incomplete provenance fields.
3. **Minimal implementation to pass**
   - Introduce canonical `IngestionChunk` DTO + validation.
   - Implement defensive parser wrappers returning typed errors.
4. **Refactoring opportunities**
   - Centralize schema validators for reuse in extraction pipeline.
5. **Observability hooks (LangSmith)**
   - Trace ingestion run with `doc_id`, `version_id`, parser backend, failure reason.
6. **Human-in-the-loop checkpoints**
   - Route ingestion failures or low OCR confidence docs to manual preprocessing queue.

## I2 — OCR + Table Parsing Reliability

1. **Tests to write first**
   - Integration test: scanned PDF returns text + bbox + confidence.
   - Integration test: table extraction preserves row/column counts on fixture tables.
   - Regression test: OCR fallback engages when primary OCR confidence below threshold.
2. **Expected failures**
   - No fallback strategy.
   - Table parser collapses merged cells incorrectly.
3. **Minimal implementation to pass**
   - Add OCR adapter interface + primary/fallback strategy.
   - Add table normalization rules with header reconciliation.
4. **Refactoring opportunities**
   - Isolate OCR provider adapters behind stable interface.
5. **Observability hooks (LangSmith)**
   - Log OCR provider choice, confidence histograms, table extraction score.
6. **Human-in-the-loop checkpoints**
   - Reviewer confirms low-confidence table reconstructions.

## I3 — Clause Extraction + Normalization

1. **Tests to write first**
   - Unit test: clause boundary detection with numbered and nested clauses.
   - Integration test: extraction preserves clause IDs and obligation actors.
   - Contract test: normalized clause schema (type, modality, due date, penalty linkage).
2. **Expected failures**
   - Clause extractor not respecting chunk boundaries.
   - Missing confidence flags for ambiguous clauses.
3. **Minimal implementation to pass**
   - Implement deterministic pre-parser + LLM-assisted extraction pass.
   - Add confidence scoring and ambiguity flagging.
4. **Refactoring opportunities**
   - Pull prompt templates into versioned prompt registry.
5. **Observability hooks (LangSmith)**
   - Capture prompt version, retrieved context, extracted clause entities.
6. **Human-in-the-loop checkpoints**
   - Mandatory validation for ambiguous/high-impact clauses.

## I4 — Hybrid RAG Retrieval Correctness

1. **Tests to write first**
   - Unit test: query router selects retrieval strategy by intent.
   - Integration test: top-k includes expected clause and evidence chunk.
   - Eval test: recall@5 and groundedness thresholds on curated corpus.
2. **Expected failures**
   - Vector-only retrieval misses exact legal language.
   - Reranker absent or not deterministic.
3. **Minimal implementation to pass**
   - Implement keyword + vector hybrid retrieval with reranking.
   - Add evidence threshold gate.
4. **Refactoring opportunities**
   - Shared retrieval API for analyzers and explainers.
5. **Observability hooks (LangSmith)**
   - Log retrieved IDs, rerank scores, miss reasons.
6. **Human-in-the-loop checkpoints**
   - If evidence threshold fails, require reviewer before downstream decision output.

## I5 — Graph Schema + Relationship Integrity

1. **Tests to write first**
   - Unit test: valid node/edge creation for Clause→Obligation→WBS→BOM→Cost→Stakeholder.
   - Unit test: duplicate edge behavior (merge or reject) is explicit.
   - Integration test: graph build from extraction output with referential integrity.
2. **Expected failures**
   - Undefined duplicate-edge semantics.
   - Missing required nodes before edge insertion.
3. **Minimal implementation to pass**
   - Implement graph relationship entity + uniqueness policy.
   - Add referential validation prior to persistence.
4. **Refactoring opportunities**
   - Declarative graph constraints to avoid hard-coded rules.
5. **Observability hooks (LangSmith)**
   - Track edge creation/rejection decisions and constraint violations.
6. **Human-in-the-loop checkpoints**
   - Review queue for high-impact broken linkages (e.g., payment milestone disconnected).

## I6 — Coherence Rule Engine (Contract vs Reality)

1. **Tests to write first**
   - Unit tests for schedule mismatch, budget mismatch, execution variance, scope-procurement mismatch.
   - Integration test: neutral result when required data missing.
   - Contract test: standardized alert payload format.
2. **Expected failures**
   - Rule logic mixed with scoring logic.
   - Inconsistent alert payloads.
3. **Minimal implementation to pass**
   - Implement pure rule engine producing normalized alerts only.
4. **Refactoring opportunities**
   - Rule registry by project phase/discipline.
5. **Observability hooks (LangSmith)**
   - Per-rule execution traces and trigger evidence.
6. **Human-in-the-loop checkpoints**
   - Review flagged critical coherence conflicts.

## I7 — Risk Scoring + Coherence Score Aggregation

1. **Tests to write first**
   - Unit tests for weighted score aggregation and severity mapping.
   - Unit tests for tenant/project specific score profiles.
   - Integration test for deterministic outputs with same alert set.
2. **Expected failures**
   - Non-deterministic score outcomes.
   - Cross-tenant weight leakage.
3. **Minimal implementation to pass**
   - Implement scoring service consuming normalized alerts from I6.
4. **Refactoring opportunities**
   - Externalize score configs and enforce schema validation.
5. **Observability hooks (LangSmith)**
   - Log score components and final score with explanation object.
6. **Human-in-the-loop checkpoints**
   - High-severity risk clusters require explicit reviewer acknowledgment.

## I8 — WBS/BOM Generation

1. **Tests to write first**
   - Unit tests for WBS node validity and BOM unit normalization.
   - Integration test: doc set -> WBS/BOM candidates with confidence.
   - Eval test against labeled fixtures.
2. **Expected failures**
   - Hallucinated tasks/materials without evidence.
   - Unit mismatch (e.g., kg vs ton) not normalized.
3. **Minimal implementation to pass**
   - Implement evidence-constrained generator.
   - Block low-confidence generation from auto-accept path.
4. **Refactoring opportunities**
   - Shared normalization library for units and nomenclature.
5. **Observability hooks (LangSmith)**
   - Capture generated item -> evidence links and confidence.
6. **Human-in-the-loop checkpoints**
   - Engineering reviewer approves generated WBS/BOM before publication.

## I9 — Procurement Planning Intelligence

1. **Tests to write first**
   - Unit tests for lead-time calculations (calendar + business-day variants).
   - Integration test: BOM + vendor data -> procurement plan.
   - Edge test: missing vendor data triggers fallback and warning.
2. **Expected failures**
   - Undefined tolerance windows for lead-time acceptance.
   - Fallback path silently used without warning.
3. **Minimal implementation to pass**
   - Implement planner with explicit tolerance configuration and fallback tagging.
4. **Refactoring opportunities**
   - Strategy pattern for region/vendor-specific lead-time models.
5. **Observability hooks (LangSmith)**
   - Record lead-time assumptions and fallback events.
6. **Human-in-the-loop checkpoints**
   - Procurement lead approves fallback-derived plan lines.

## I10 — Stakeholder Resolution + RACI Inference

1. **Tests to write first**
   - Unit tests for stakeholder entity resolution and canonical IDs.
   - Unit tests for RACI role constraints (single accountable rule by task).
   - Integration test: contract statements -> RACI matrix with confidence.
2. **Expected failures**
   - Duplicate party entities across docs/vendors.
   - Ambiguous actor mapping not escalated.
3. **Minimal implementation to pass**
   - Implement entity resolution rules + ambiguity flags.
   - Implement RACI generator with validation.
4. **Refactoring opportunities**
   - Reusable party resolution service across contract and procurement domains.
5. **Observability hooks (LangSmith)**
   - Trace party merge decisions and RACI conflict warnings.
6. **Human-in-the-loop checkpoints**
   - PMO/legal operations validate ambiguous stakeholder mappings.

## I11 — Human-in-the-Loop Workflow Enforcement

1. **Tests to write first**
   - Unit tests: confidence gate routing.
   - Integration tests: high-impact outputs blocked pending review.
   - SLA tests: overdue items trigger escalation path.
2. **Expected failures**
   - High-impact items bypass review.
   - No escalation for stale review tasks.
3. **Minimal implementation to pass**
   - Implement review queue service, SLA timers, escalation hooks.
4. **Refactoring opportunities**
   - Decouple policy engine from queue transport.
5. **Observability hooks (LangSmith)**
   - Trace gate decisions, reviewer actions, and SLA breaches.
6. **Human-in-the-loop checkpoints**
   - Explicit `approved_by` and `approved_at` required for release.

## I12 — LangSmith Observability + Evaluation Harness

1. **Tests to write first**
   - Unit tests for trace envelope completeness.
   - Integration tests for run creation + correlated step IDs.
   - Eval regression tests for extraction/retrieval/coherence drifts.
2. **Expected failures**
   - Missing trace context in async paths.
   - No drift alarm thresholds configured.
3. **Minimal implementation to pass**
   - Implement LangSmith adapter with required metadata and async exception annotation.
4. **Refactoring opportunities**
   - Common instrumentation middleware for all agents.
5. **Observability hooks (LangSmith)**
   - Full run lineage + dataset-based performance snapshots.
6. **Human-in-the-loop checkpoints**
   - Ops review for drift alerts before model/prompt rollout.

## I13 — End-to-End Decision Intelligence Flow

1. **Tests to write first**
   - E2E: upload docs -> coherence score + risks + evidence links.
   - E2E: low-confidence or missing-source output cannot be finalized.
   - E2E: reviewer approval unlocks final decision package.
2. **Expected failures**
   - Missing citations in final narrative.
   - No explicit state separation (AI hypothesis vs validated finding).
3. **Minimal implementation to pass**
   - Orchestrate LangGraph end-to-end state machine with gating states.
4. **Refactoring opportunities**
   - Consolidate repeated state transition guards.
5. **Observability hooks (LangSmith)**
   - Trace full DAG with stage-level durations and failure nodes.
6. **Human-in-the-loop checkpoints**
   - Final decision pack only generated after mandatory sign-off.

## I14 — Governance & Safety Hardening (Mandatory)

1. **Tests to write first**
   - Hallucination detection test: claims without evidence must be blocked.
   - Missing source test: output without citation fails policy check.
   - Low-confidence output test: auto-publication denied.
   - Mandatory human validation test: high-impact legal/contract interpretations blocked pending approval.
   - Legal disclaimer test: disclaimer always present in UI/API output payload.
2. **Expected failures**
   - Uncited claims reaching output layer.
   - Disclaimer absent in some channels.
3. **Minimal implementation to pass**
   - Implement safety policy engine + output guard middleware.
   - Inject legal disclaimer in all response renderers.
4. **Refactoring opportunities**
   - Centralized policy DSL for safety/governance rules.
5. **Observability hooks (LangSmith)**
   - Log policy decision reason codes and blocked output snapshots.
6. **Human-in-the-loop checkpoints**
   - Compliance officer approval required for policy overrides.

---

## Mandatory Safety Test Pack (Cross-Cutting)

These tests are non-optional and run in CI for every increment after I6:

- Hallucination detection
- Missing source rejection
- Low-confidence gating
- Human validation enforcement
- Legal disclaimer enforcement

---

## Recommended Delivery Sequence

1. I1-I3 foundation (ingestion + extraction)
2. I4-I5 knowledge layer (retrieval + graph)
3. I6-I7 reasoning core (rules + scoring)
4. I8-I10 planning intelligence (WBS/BOM/procurement/RACI)
5. I11-I12 control plane (human workflow + observability)
6. I13-I14 production hardening (E2E + governance)

---

## Definition of Done (Program Level)

A capability is done only if:

1. Failing tests were written first.
2. Minimal implementation turns tests green.
3. Refactor keeps tests green.
4. LangSmith traces exist for key decisions.
5. Human-in-the-loop gate is enforced where applicable.
6. Output includes evidence and legal-safe disclaimer.

---

## Legal Disclaimer Requirement (Always-On)

All user-facing outputs must include:

> "C2Pro provides AI-assisted project intelligence for operational decision support. It does not provide legal advice. All legal, contractual, and commercial conclusions require qualified human review and approval."

This is validated through automated tests in I14 and enforced through runtime policy middleware.

---

## Next Step Prompt

Do you want to start implementation with a specific vertical (**contracts, WBS, procurement, or end-to-end**), or generate the **full test backlog** first?
