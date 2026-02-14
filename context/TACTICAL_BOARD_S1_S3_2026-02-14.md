# C2Pro Tactical Board - S1 to S3

## S1 Tactical Board

| Sprint | Task ID | Owner | Files | Action | Depends On | Exit Evidence ||---|---|---|---|---|---|---|

| S1 | S1-QA-01 | `@qa-agent` | `apps/api/tests/modules/ingestion/domain/test_i1_canonical_ingestion_contract.py` | Remove skips, normalize imports/docstrings, ensure real RED | None | Failing tests for missing/invalid behavior (not syntax/import noise) |
| S1 | S1-QA-02 | `@qa-agent` | `apps/api/tests/modules/ingestion/adapters/test_i2_ocr_table_parsing.py` | Remove skips, keep mocks only for ports, strict RED for fallback/table behavior | None | Failing tests on OCR fallback and table normalization |
| S1 | S1-BE-01 | `@backend-tdd` | `apps/api/src/modules/ingestion/domain/entities.py` | Finalize `IngestionChunk`, `IngestionError`, validators | S1-QA-01 | I1 domain tests green |
| S1 | S1-BE-02 | `@backend-tdd` | `apps/api/src/modules/ingestion/application/ports.py`, `apps/api/src/modules/ingestion/application/services.py` | Stabilize OCR adapter contract, fallback logic, table normalization | S1-QA-02 | I2 tests green |
| S1 | S1-SEC-01 | `@security-agent` | I1/I2 tests + ingestion services | Add/verify no gate bypass and safe trace metadata | S1-BE-01/S1-BE-02 | Security assertions green |
| S1 | S1-DOC-01 | `@docs-agent` | `context/C2PRO_TDD_BACKLOG_v1.0.md`, `context/PLAN_ARQUITECTURA_v2.1.md` | Update progress after green | S1 done | Status rows updated with completion note |

## S2 Tactical Board

| Sprint | Task ID | Owner | Files | Action | Depends On | Exit Evidence ||---|---|---|---|---|---|---|

| S2 | S2-QA-01 | `@qa-agent` | `apps/api/tests/modules/extraction/application/test_i3_clause_extraction_service.py`, extraction domain tests | Remove skips, normalize imports, strict RED for clause normalization and HITL flags | S1 done | Failing tests for I3 behavior |
| S2 | S2-QA-02 | `@qa-agent` | `apps/api/tests/modules/retrieval/domain/test_i4_query_router.py`, `apps/api/tests/modules/retrieval/application/test_i4_hybrid_retrieval_service.py` | Remove skips, deterministic reranker tests, evidence threshold gate tests | S1 done | Failing tests for I4 routing/rerank/gating |
| S2 | S2-BE-01 | `@backend-tdd` | `apps/api/src/modules/extraction/domain/entities.py`, `apps/api/src/modules/extraction/application/ports.py` | GREEN I3: normalization, provenance IDs, ambiguity/manual-validation flags | S2-QA-01 | I3 suite green |
| S2 | S2-BE-02 | `@backend-tdd` | `apps/api/src/modules/retrieval/domain/entities.py`, `apps/api/src/modules/retrieval/application/ports.py` | GREEN I4: intent router, hybrid retrieval, deterministic reranking, evidence gate | S2-QA-02 | I4 suite green |
| S2 | S2-SEC-01 | `@security-agent` | I3/I4 tests + retrieval/extraction services | Verify low-evidence/high-risk outputs require review | S2-BE-01/S2-BE-02 | Security gate assertions green |
| S2 | S2-DOC-01 | `@docs-agent` | `context/C2PRO_TDD_BACKLOG_v1.0.md`, `context/PLAN_ARQUITECTURA_v2.1.md` | Update progress after green | S2 done | Status rows updated with completion note |

## S3 Tactical Board

| Sprint | Task ID | Owner | Files | Action | Depends On | Exit Evidence ||---|---|---|---|---|---|---|

| S3 | S3-QA-01 | `@qa-agent` | `apps/api/tests/modules/graph/domain/test_i5_graph_schema.py`, `apps/api/tests/modules/graph/application/test_i5_graph_builder_service.py` | Remove skips, normalize imports/docstrings, ensure RED for node/edge integrity and duplicate policy | S2 done | Failing tests for duplicate-edge semantics and missing-node edge insertion |
| S3 | S3-QA-02 | `@qa-agent` | `apps/api/tests/modules/coherence/domain/test_i6_coherence_rules.py`, `apps/api/tests/modules/coherence/domain/test_i6_alert_payload_contract.py`, `apps/api/tests/modules/coherence/application/test_i6_coherence_engine_service.py` | Remove skips, strict RED for pure rules, neutral-on-missing-data, alert contract | S2 done | Failing tests for rule behavior + payload standardization |
| S3 | S3-BE-01 | `@backend-tdd` | `apps/api/src/modules/graph/domain/entities.py`, `apps/api/src/modules/graph/domain/services.py`, `apps/api/src/modules/graph/application/ports.py` | Implement graph node/edge entities, duplicate policy (`reject`/`merge`), referential checks before edge persistence | S3-QA-01 | I5 tests green |
| S3 | S3-BE-02 | `@backend-tdd` | `apps/api/src/modules/coherence/domain/entities.py`, `apps/api/src/modules/coherence/domain/rules.py`, `apps/api/src/modules/coherence/application/ports.py` | Implement pure coherence rules and standardized alert payload; enforce neutral behavior when data missing | S3-QA-02 | I6 tests green |
| S3 | S3-SEC-01 | `@security-agent` | I5/I6 tests + coherence/graph services | Verify no bypass of referential validation; verify rule engine remains decoupled from scoring; verify critical/high review flags | S3-BE-01/S3-BE-02 | Security assertions green |
| S3 | S3-DOC-01 | `@docs-agent` | `context/C2PRO_TDD_BACKLOG_v1.0.md`, `context/PLAN_ARQUITECTURA_v2.1.md` | Update completion state and critical progress notes | S3 complete | Status rows updated with `[x] Implemented (Unit Tests & Domain Logic)` |

## Execution Checklist

- [x] `S1-QA-01` unskip and normalize I1 tests.
- [x] `S1-QA-02` unskip and normalize I2 tests.
- [x] `S1-BE-01` make I1 green with typed domain contract.
- [x] `S1-BE-02` make I2 green with OCR fallback + table normalization.
- [x] `S1-SEC-01` validate no bypass and safe observability payloads.
- [x] `S1-DOC-01` update backlog/architecture docs.

- [x] `S2-QA-01` unskip and normalize I3 tests.
- [x] `S2-QA-02` unskip and normalize I4 tests.
- [x] `S2-BE-01` make I3 green (extraction normalization + HITL flags).
- [x] `S2-BE-02` make I4 green (router + hybrid + rerank + evidence gate).
- [x] `S2-SEC-01` verify review gating and tenant-safe behavior.
- [x] `S2-DOC-01` update backlog/architecture docs.

- [x] `S3-QA-01` unskip/normalize I5 tests.
- [x] `S3-QA-02` unskip/normalize I6 tests.
- [x] `S3-BE-01` make I5 green (graph integrity + duplicate policy).
- [x] `S3-BE-02` make I6 green (pure rules + standard alert payload).
- [x] `S3-SEC-01` validate coupling/gating/security invariants.
- [x] `S3-DOC-01` update backlog and architecture plan after green.

---

Last Updated: 2026-02-14

Changelog:

- 2026-02-14: Created consolidated S1-S3 tactical board and execution checklist.
- 2026-02-14: Execution checklist updated to completed for S1, S2, and S3.
