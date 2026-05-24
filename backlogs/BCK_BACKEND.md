# Backend Tasks & Knowledge Base

**Category**: Backend (BCK)
**Owner Role**: backend
**Last Updated**: 2026-05-24

**Quick Links**:

- 🏠 [Master Index](../C2PRO_MASTER_BACKLOG.md)
- 📋 [Role Profile](../roles/role_backend.md)

---

## 0. Status View

**Pending Tasks**: 2

**Completed Tasks**: 54

- IDs: `TASK-BCK-001`–`TASK-BCK-033`, `TASK-BCK-035`–`TASK-BCK-049`, `TASK-BCK-052`–`TASK-BCK-054`

> Active runtime defects are tracked below; completed history remains archived in [COMPLETED.md](./COMPLETED.md).

---

## 1. Active Tasks

| Status | Priority | Task ID | Depends On | Description | Source |
| ------ | -------- | ------- | ---------- | ----------- | ------ |
| [ ] | P0 | `TASK-BCK-051` | None | Investigate live `500` responses on project alerts and project stakeholders by correlating production error reference IDs with backend logs and verifying applied Alembic head/schema parity for tenant-hardened tables. Live drift repaired 2026-05-16 through `20260516_0001`; remaining blocker is unavailable production log access for reference-ID correlation. | Production report 2026-05-15 |
| [x] | P0 | `TASK-BCK-052` | None | Fix `/api/v1/analysis/analyze` LangGraph `InvalidUpdateError` caused by duplicated parallel fan-out/join writes to shared keys such as `project_id` after successful parsing. `[x] Implemented (True Multi-Source Fan-In + Branch State Isolation)` | Swagger verification 2026-05-17 |
| [x] | P1 | `TASK-BCK-053` | None | Stop fresh `/api/v1/analysis/analyze` requests from reusing project-level LangGraph checkpoint threads and replaying prior workflow messages into later analyses. `[x] Implemented (Fresh Analysis Thread Isolation)` | Swagger verification 2026-05-17 |
| [x] | P0 | `TASK-BCK-054` | None | Restore live `/api/v1/coherence/evaluate` by fixing the tracing/state contract mismatch, satisfying the current LangSmith SDK `inputs` contract, and making coherence telemetry fail open instead of blocking scoring. `[x] Implemented (Coherence Tracing Contract + Fail-Open Telemetry)` | Swagger verification 2026-05-17 |
| [x] | P0 | `TASK-BCK-055` | None | Fix project bulk-WBS contract drift: `/projects/{project_id}/wbs/bulk` now persists tenant-scoped procurement WBS rows, and `/projects/{project_id}/wbs` immediately returns them with preserved parent hierarchy. | Swagger verification 2026-05-17 |
| [ ] | P0 | `TASK-BCK-060` | `TASK-BCK-055` | Reconcile `/projects/{project_id}/wbs` response with its published tree/coverage contract; current live payload is flat (`items` + `total_items`) even though docs promise hierarchy + coverage. | Swagger verification 2026-05-17 |
| [x] | P0 | `TASK-BCK-061` | None | Restore document upload availability by aligning the running DB with the tenant-hardened documents schema; applied pending migrations through `20260517_0002`, verified `documents.tenant_id`, and live Swagger schedule upload returned 202 again. | Swagger verification 2026-05-17 |
| [x] | P0 | `TASK-BCK-062` | None | Upgrade Excel schedule parsing to handle realistic schedule workbooks with title rows, discoverable header rows, and Spanish header aliases; also stop surfacing malformed schedule shape as HTTP 500. Completed 2026-05-17 with live Swagger proof and WBS-level mapping fix. | Swagger verification 2026-05-17 |
| [ ] | P1 | `TASK-BCK-063` | None | Persist `parsed_at` on successful parse so document detail and history reflect the completed parse event instead of returning `null` after `upload_status="parsed"`. | Swagger verification 2026-05-17 |
| [ ] | P0 | `TASK-BCK-064` | `TASK-BCK-062` | Wire parsed schedule evidence into coherence scoring so a successfully parsed schedule with generated WBS no longer leaves the coherence model reporting missing `schedule` dimension. | Swagger verification 2026-05-17 |
| [x] | P1 | `TASK-BCK-065` | None | Translate upstream RAG provider throttling/failures into controlled API responses instead of raw HTTP 500 tracebacks when embeddings calls return `429`. Completed 2026-05-18: provider 429 now returns retryable `503` JSON, and a document id placed in the project id path returns tenant-scoped `404` before calling embeddings. | Swagger verification 2026-05-18 |
| [x] | P1 | `TASK-BCK-066` | None | Align observability status route auth with live middleware so Swagger sends bearer auth correctly while the routes remain private end-to-end. Completed 2026-05-17 by exposing `HTTPBearer` on the observability router and verifying authenticated live `GET /status` + `GET /analyses` both return `200`. | Swagger verification 2026-05-17 |
| [x] | P0 | `TASK-BCK-067` | `TASK-BCK-062` | Make schedule parsing idempotent for schedule-derived activity projections, without treating the schedule as the canonical WBS. Same-source generated activity rows now update instead of inserting duplicates; live reparse of `f04d4f22-684f-4874-b93b-dc5436ef720b` returned `202 parsed`. | Swagger verification 2026-05-18 |
| [x] | P1 | `TASK-BCK-068` | `TASK-BCK-065` | Restore RAG answer completion after provider credit: direct tenant-scoped `document_chunks` retrieval replaces stale `match_documents`, Excel schedule rows are ingested into RAG chunks, LangSmith telemetry fails open, and schedule end-date questions can be answered extractively if the configured Anthropic model is unavailable. Live proof returned `200` with answer `2015-01-02`. | Swagger verification 2026-05-18/19 |
| [x] | P1 | `TASK-BCK-069` | `TASK-BCK-068` | Extend RAG answer resilience for non-date schedule questions: equipment-purchase questions now answer extractively from retrieved schedule task chunks when Anthropic generation returns model `404`, and generation failures without deterministic fallback map to controlled retryable `503` instead of traceback `500`. Live proof returned `200` with two transformer items. | Swagger verification 2026-05-19 |
| [x] | P1 | `TASK-BCK-070` | `TASK-BCK-068` | Ingest parsed contract clause payloads into RAG so contract questions are not starved by schedule-only chunks. Live finding: penalty question returned only schedule sources because the contract document had 210 clauses but zero rows in `document_chunks`; repair adds clause/text payload normalization and unit coverage. Live QA still needs API restart plus contract reparse/reindex before closing `TASK-QA-263`. | Swagger verification 2026-05-23 |
| [x] | P1 | `TASK-BCK-071` | `TASK-BCK-070` | Improve RAG penalty answer fallback so retrieved contract damages evidence is not discarded when the LLM abstains with `No lo encuentro en el documento`. Deterministic fallback now summarizes `recover damages`, `decrease in the Contract Price`, and risk/cost/responsibility evidence from contract chunks. | Swagger verification 2026-05-23 |
| [x] | P1 | `TASK-BCK-072` | None | Expose bearer auth in OpenAPI for protected alerts routes. Live Swagger `GET /api/v1/alerts/projects/{project_id}` omitted `Authorization` and hit middleware `401`; alerts routers now declare `HTTPBearer` via `security_scheme`. | Swagger verification 2026-05-23 |
| [x] | P0 | `TASK-BCK-073` | None | Restore analysis AI tool execution contract. Live Swagger `POST /api/v1/analysis/analyze` returned HTTP 200 but functionally failed with `Tool 'risk_extraction' executed: failed`; logs showed `_execute_impl() got an unexpected keyword argument 'tenant_id'`. Risk and WBS extraction tools now accept the keyword contract used by `BaseTool`. | Swagger verification 2026-05-23 |
| [x] | P0 | `TASK-BCK-074` | `TASK-BCK-073` | Repair the Analysis ⇄ HITL seam. Live Swagger extracted risks but stopped with `analysis_id=null` because critique used legacy AIService cost control without constructor DB, HITL auto-approved rows still triggered LangGraph interrupt, and resume updated checkpoint state without invoking the graph. | Swagger verification 2026-05-23 |
| [x] | P0 | `TASK-BCK-075` | None | Repair API startup failure from split Alembic heads after main sync. Docker startup failed before app boot with `Multiple head revisions are present for given argument 'head'`; added no-op merge revision `20260524_0001` joining `20260516_0004` and `20260517_0002`. | Docker startup verification 2026-05-24 |
| [x] | P0 | `TASK-BCK-076` | `TASK-BCK-074` | Repair API startup failure from LangGraph reserved channel `checkpoint_id`. Docker moved past Alembic, then failed compiling the analysis graph with `ValueError: Channel name 'checkpoint_id' is reserved`; removed that key from `ProjectState` and kept `thread_id` as the HITL resume correlation key. | Docker startup verification 2026-05-24 |
| [x] | P0 | `TASK-BCK-055` | None | Coherence Score™ Structured Extraction Layer — complete. `clause_extractor.py` (combined schema, UUID-safe DB cache, `_load_cache()` validity check requiring at least one `_ALL_REQUIRED_KEYS` field), integrated into `prepare_context` in `nodes.py`. Cache check bug fixed: ingestion metadata `{source, category, affected_categories}` was treated as a cache hit; fixed to require real extracted field. Verified: extraction now fires Haiku LLM calls and enriches `clause.data`. `deterministic_findings_count` rose from 8 → 31. | 2026-05-17 |
| [x] | P1 | `TASK-BCK-056` | None | Fix `AnthropicWrapper` calling `self.anonymizer_service.anonymize_document()` on `AnonymizationService` (wrong API). Swapped to `PiiAnonymizerService` from `core.privacy.anonymizer` which has the correct `anonymize_document()` sync API returning `AnonymizedResult` with `.mapping` and `.anonymized_text`. | 2026-05-17 |
| [x] | P1 | `TASK-BCK-057` | BCK-055 | Category-targeted RAG retrieval: replaced `ORDER BY created_at LIMIT 50` with 6 keyword-filtered SQL queries (10 clauses per category: LEGAL/TIME/BUDGET/TECHNICAL/QUALITY/SCOPE). Penalty, warranty, notice, and deliverable clauses previously invisible now surface. `deterministic_findings_count` 13 → 31. | 2026-05-17 |
| [x] | P1 | `TASK-BCK-058` | BCK-055 | DET-TIM-STATUS false positive guard: rule was firing 7 times on payment/price clauses because ingestion stamped `status: at_risk` on non-TIME clauses. Added `infer_category(clause) not in ("TIME", "SCHEDULE")` guard. Moved `infer_category` + `CATEGORY_KEYWORDS` to `rules_engine/category_utils.py` to break circular import. Schedule category score: 65 → 100. | 2026-05-17 |
| [x] | P1 | `TASK-BCK-059` | BCK-058 | DET-TEC-SPEC / DET-QUA-STANDARD / DET-QUA-INSPECT false positive guards: DET-TEC-SPEC was firing 25 times (preamble, party names, payment terms) because it checked `clause.data.get("category")` ingestion metadata. Replaced with `infer_category(clause) != "TECHNICAL"` guard. DET-QUA-STANDARD and DET-QUA-INSPECT got `infer_category not in ("QUALITY","TECHNICAL")` guards. Test clauses updated to use unambiguous keyword-rich text. | 2026-05-17 |
| [x] | P0 | `TASK-BCK-060` | BCK-055 | Honest coherence scoring: ApplicabilityState (Open/Closed additive method on RuleEvaluator), per-evaluator applicability overrides (12 deterministic + LLM SKIPPED_DISABLED), per-category coverage_map with OR-merge reducer, HeuristicBaselineProvider (80-90 risk-flexed band), coverage-aware calculate_detailed (decay from baseline, global = mean(assessed) x assessed/6 coverage penalty), three-state CategoryBreakdown (unassessed=null / assessed_clean=baseline / assessed_findings). Eliminates fabricated 100/0 subcategory scores; unassessed dimensions return null + drag global score. 104 coherence unit tests green. Branch feat/honest-coherence-scoring. | Design+plan 2026-05-17 |

## 2. Specifications

### TASK-BCK-075 — Alembic split-head startup repair

- Live finding: `docker compose up -d api celery-worker` failed because `c2pro-api` was unhealthy before startup. Logs showed Alembic aborting with `Multiple head revisions are present for given argument 'head'`.
- Root cause: the main synchronization merged two independent migration chains: production hotfix head `20260516_0004` and local Swagger/schema head `20260517_0002`.
- Repair: add no-op merge revision `20260524_0001_merge_hotfix_and_swagger_heads.py` with `down_revision=("20260516_0004", "20260517_0002")`.
- Verification: `TS-QA-SWAGGER-MIGRATION-001` first failed with two heads, then passed after the merge revision; `alembic heads` reports only `20260524_0001 (head)`.

### TASK-BCK-076 — LangGraph reserved checkpoint channel startup repair

- Live finding: after `TASK-BCK-075`, Docker startup advanced past Alembic but failed during FastAPI lifespan while compiling the analysis graph: `ValueError: Channel name 'checkpoint_id' is reserved`.
- Root cause: `TASK-BCK-074` added `checkpoint_id` to `ProjectState`, which LangGraph treats as a reserved runtime channel name.
- Repair: remove `checkpoint_id` from the graph state schema and from HITL item payload/metadata generation. Preserve `thread_id`, which is sufficient for the resume correlation used by `RunnableConfig.configurable.thread_id`.
- Verification: graph compile failed before the patch with the reserved-channel error, then `test_workflow_compile_does_not_use_reserved_checkpoint_channel` and the HITL auto-approval regression passed.

### TASK-BCK-074 — Analysis ⇄ HITL seam repair

- Live finding: after `TASK-BCK-073`, `/api/v1/analysis/analyze` returned real risks with `confidence_score=0.9`, but still returned `analysis_id=null`, `human_approval_required=true`, and `critique_notes=Automatic critique inconclusive.`
- Root causes:
  1. graph critique still uses legacy `AIService`; when constructed without a DB session it failed before using the tenant-scoped session cost-controller path;
  2. `human_interrupt_node` ignored the `ReviewStatus.APPROVED` returned by HITL routing, so auto-approved items still interrupted before `save_to_db`;
  3. HITL review items lacked workflow correlation metadata from analysis state;
  4. `ResumeWorkflowUseCase` called `aupdate_state()` but did not call `ainvoke()` to continue the LangGraph run loop.
- Repair: defer legacy `AIService` cost control to the tenant-scoped session path when constructor DB is absent, propagate `thread_id` into analysis state and HITL metadata, continue immediately on auto-approved HITL decisions, and call `ainvoke(None, config)` after approval state injection.
- Verification: `TS-QA-SWAGGER-ANALYSIS-002` green via focused unit and HITL resume integration tests. Live Swagger needs container reload before QA closes `TASK-QA-309`/`TASK-QA-306`.

### TASK-BCK-073 — Analysis AI tool execution contract repair

- Live cause: `BaseTool._execute_with_retry()` invokes subclass implementations with keyword arguments: `input_data=...`, `tenant_id=...`, and `ai_response=...`.
- Defect: `RiskExtractionTool._execute_impl()` and `WBSExtractionTool._execute_impl()` named the second parameter `_tenant_id`, so Python rejected the `tenant_id` keyword after the expensive LLM call had already completed.
- User-visible symptom: `/api/v1/analysis/analyze` returned HTTP `200` with `risks=[]`, `confidence_score=0`, `human_approval_required=true`, and message `Tool 'risk_extraction' executed: failed`.
- Repair: align both tool method signatures to `tenant_id: UUID | None` and add regression coverage that executes both tools through `BaseTool.execute()` with deterministic Anthropic stubs.
- Acceptance: `TS-QA-SWAGGER-ANALYSIS-001` passes and Swagger QA can rerun `TASK-QA-309` after API restart.

### TASK-BCK-054 — Coherence tracing/state contract repair

- Live cause: `traced_coherence_node()` dereferences `state.tenant_id`, but `CoherenceGraphState` has no direct `tenant_id` field; tenant identity currently lives in `state.config.tenant_id`.
- Why it matters: every coherence node wrapped by tracing can fail before business logic runs, so `/api/v1/coherence/evaluate` is not operable even when request data is valid.
- Chosen repair: preserve one canonical tenant source on `CoherenceGraphState` by exposing a read-only `tenant_id` accessor that delegates to `config.tenant_id`; this keeps observability code simple while avoiding duplicate mutable tenant state.
- Acceptance:
  1. tracing can read tenant/project metadata from a real `CoherenceGraphState`;
  2. the core coherence endpoint returns `200` in Swagger for the current parsed project;
  3. no tenant-filtering or graph behavior is weakened.
- Follow-on defect found during real verification: after the state accessor fix, live execution advanced to a second `500` because `LangSmithClient.start_span()` no longer satisfied the installed SDK signature (`Client.create_run()` requires `inputs`).
- Final repair shape:
  1. expose read-only `CoherenceGraphState.tenant_id -> config.tenant_id`;
  2. pass `inputs={}` when creating LangSmith spans;
  3. make span start/update/end telemetry fail open so observability cannot take down coherence evaluation.

### TASK-BCK-055 — Project bulk WBS fake-write / real-read drift

- Live cause: `bulk_create_wbs()` in the projects router is explicitly labeled `GREEN PHASE implementation using "Fake It" pattern` and only validates/counts request items; it does not persist them.
- Contradicting contract: `GET /api/v1/projects/{project_id}/wbs` reads from the real WBS repository, so the same live flow reports `created_count=4` followed by an empty tree.
- Why it matters: bulk creation currently gives a false success signal and cannot seed later WBS workflows.
- Acceptance:
  1. bulk WBS creation persists tenant-scoped rows or is removed from the public contract;
  2. a successful bulk create is visible through `GET /wbs`;
  3. parent-child hierarchy remains valid for the persisted rows.
- Resolution 2026-05-17:
  1. `bulk_create_wbs()` now writes validated rows through `SQLAlchemyWBSRepository.bulk_create_from_dicts(...)` inside the same tenant-scoped DB path used by the read endpoint;
  2. the repository now preserves incoming `parent_code` so hierarchy survives persistence;
  3. regression proof: `apps/api/tests/projects/test_projects_router.py::TestBulkWBSCompatibilityEndpoint::test_bulk_create_wbs_items_are_visible_from_wbs_read_endpoint`;
  4. live proof on project `25916ab2-03a3-4df5-bf5f-1f8dde07fb8c`: POST bulk created `9` + `9.1`, and immediate GET `/wbs` returned `total_items=2`, `codes=9,9.1`, `parent_9_1=9`.

### TASK-BCK-060 — Project WBS route contract mismatch

- Live finding: `GET /api/v1/projects/{project_id}/wbs` now returns persisted rows, but the payload is still flat: `{"project_id", "items", "total_items"}`.
- Why this is a contract bug:
  1. Swagger says “Returns all WBS items with their hierarchy and coverage information”;


### TASK-BCK-068 — RAG answer completion after provider credit

- Live finding: after OpenAI credit was added, `/api/v1/projects/{project_id}/rag/answer` moved past embeddings and failed on `match_documents(uuid, uuid, vector, unknown)` because the running database only exposes `match_documents(project_id uuid, embedding vector, match_count integer)`.
- Repair shape:
  1. retrieve directly from `document_chunks` with explicit `tenant_id` and `project_id` predicates instead of relying on the stale database function;
  2. convert parsed Excel schedule rows into searchable RAG text so schedule workbooks populate `document_chunks`;
  3. make LangSmith span creation/end fail open so telemetry credentials cannot break RAG answers;
  4. add an extractive schedule end-date fallback for date questions when the configured Anthropic generation model is unavailable.
- Live proof: reparse of schedule document `f04d4f22-684f-4874-b93b-dc5436ef720b` created 5 RAG chunks; `POST /api/v1/projects/25916ab2-03a3-4df5-bf5f-1f8dde07fb8c/rag/answer` returned `200` with `La fecha de finalización del proyecto es 2015-01-02.`.

### TASK-BCK-069 — RAG equipment fallback and generation-provider error containment

- Live finding: the next Swagger RAG question, `what are the main equipment to purchase, just say two of them`, retrieved schedule chunks correctly but still failed with raw HTTP `500` because Anthropic rejected configured model `claude-sonnet-4-20250514` with provider `404`.
- Repair shape:
  1. keep the normal LLM answer path first;
  2. when generation fails, try deterministic extractive answers from retrieved chunks;
  3. add equipment extraction from schedule `Task:` entries such as `Fabricación de transformador 100 MVA`;
  4. if no deterministic answer exists, convert generation failure to `RagProviderUnavailableError` so the router returns controlled retryable `503`.
- Live proof: `POST /api/v1/projects/25916ab2-03a3-4df5-bf5f-1f8dde07fb8c/rag/answer` returned `200` with `Transformador 100 MVA; Transformador 25/31.5 MVA.` and schedule sources.


### TASK-BCK-070 — Contract clauses missing from RAG chunks

- Live finding: `POST /api/v1/projects/25916ab2-03a3-4df5-bf5f-1f8dde07fb8c/rag/answer` with `waht could be the penalty` returned `200` but all five sources were `document_type=schedule`. Database inspection showed only schedule chunks in `document_chunks`; contract `f6543818-b7a6-4357-8f48-43238a4f8a65` was parsed and had 210 `clauses` rows but zero RAG chunks.
- Repair shape: extend `SqlAlchemyRagIngestionService` payload normalization beyond `text_blocks` and `schedule` to include parsed `clauses` plus generic `full_text`/`text`/`raw_text` fallbacks.
- Verification: `pytest apps/api/tests/unit/adapters/documents/test_composite_rag.py::TestRagIngestionServiceAdvanced -q` -> `4 passed`. Live Swagger verification remains open until the API is restarted and the contract is reparsed/reindexed.


### TASK-BCK-071 — RAG penalty answer fallback after contract retrieval

- Live finding: after contract chunks were available, `POST /api/v1/projects/25916ab2-03a3-4df5-bf5f-1f8dde07fb8c/rag/answer` with `what are the liquidated damages or delay penalties for the contractor?` retrieved only `document_type=contract` sources, including `recover damages` and `decrease in the Contract Price`, but the answer still returned `No lo encuentro en el documento.`
- Repair shape: if the LLM answer is the configured no-answer phrase, run deterministic extractive fallback before returning. Add a contract damages fallback for penalty/delay/damages questions that summarizes retrieved evidence without inventing a percentage.
- Verification: `pytest apps/api/tests/unit/adapters/documents/test_rag_service_provider_errors.py apps/api/tests/unit/adapters/documents/test_composite_rag.py::TestRagIngestionServiceAdvanced -q` -> `11 passed`. Live Swagger needs API restart before this behavior appears.


### TASK-BCK-072 — Alerts Swagger bearer auth contract

- Live finding: Swagger call to `GET /api/v1/alerts/projects/25916ab2-03a3-4df5-bf5f-1f8dde07fb8c` generated curl without `Authorization` and returned `401 {"detail":"Not authenticated","reason_code":"missing_or_invalid_token"}`.
- Root cause: alerts routers relied on tenant/user dependencies and middleware but did not advertise `HTTPBearer` in OpenAPI, so Swagger did not attach the authorized token.
- Repair: add `dependencies=[Depends(security_scheme)]` to both alerts routers, matching the previous observability-route fix.
- Verification: `pytest apps/api/tests/core/test_alerts_http_dependencies.py apps/api/tests/core/test_observability_http_dependencies.py -q` -> `4 passed`.

### TASK-BCK-061 — Document upload blocked by unapplied tenant hardening migration

- Live finding: `POST /api/v1/projects/{project_id}/documents` failed on `2026-05-17` with `UndefinedColumnError: column "tenant_id" of relation "documents" does not exist`.
- Root cause confirmed locally: the running DB is at Alembic head `20260510_0001`, while code already expects direct `documents.tenant_id` and migration `20260517_0002_harden_documents_clauses_chunks_rls.py` adds/backfills that column.
- Resolution: applied pending migrations through `20260517_0002`, verified `documents.tenant_id` exists, and the same Swagger schedule upload returned `202` with document `f04d4f22-684f-4874-b93b-dc5436ef720b`.

### TASK-BCK-062 — Real schedule workbook rejected by brittle Excel parser

- Live finding: `POST /api/v1/documents/{document_id}/parse` failed on uploaded schedule `Cronograma.xlsx`.
- Actual workbook shape: row 1 is a merged title block; the real table header is row 10 with Spanish labels `ID`, `WBS`, `Actividad`, `Duración (días)`, `Inicio`, `Fin`, `Predecesoras`, `Recursos clave`.
- Current parser limitation: it only inspects row 1 and only accepts English `task`, `start date`, `end date`.
- Product implication: the schedule lane is not yet credible for real construction files; Phase 1 cannot honestly mark schedule analysis green until this parser accepts realistic workbooks and reports format issues as controlled validation failures.
- Follow-up discovered during live verification: `TASK-BCK-063` is needed because successful parse currently updates status but leaves `parsed_at` null, which weakens downstream history/evidence integrity.
  2. the route summary says “Get Project WBS Tree” and promises “Hierarchical WBS tree with children”;
  3. implementation calls `GetWBSTreeUseCase(...)` but discards that result, then returns `ListWBSItemsUseCase(...)` instead.
- Acceptance:
  1. either return the documented tree + coverage shape, or change the public schema/docs so they truthfully describe a flat list;
  2. no duplicate `/wbs` contracts should compete for the same path;
  3. Swagger verification must prove the final public contract exactly.

---

## 2. Completed Task IDs (summary)

| Task ID        | Description                                              | Completed     |
| -------------- | -------------------------------------------------------- | ------------- |
| `TASK-BCK-001` | Dependencies injected via FastAPI / service constructors | 2026-04-04    |
| `TASK-BCK-002` | Retire legacy `app/dashboard/`                           | 2026-02-19    |
| `TASK-BCK-003` | Remove `_Default*Service` dummy implementations          | 2026-02-19    |
| `TASK-BCK-004` | LangGraph nodes wrap existing use cases                  | 2026-02-19    |
| `TASK-BCK-005` | HITL real service implementation                         | 2026-02-19    |
| `TASK-BCK-006` | Verifier produces JSON for dashboarding                  | 2026-04-04    |
| `TASK-BCK-007` | Fix Alembic WBS uniqueness migration                     | 2026-04-04    |
| `TASK-BCK-008` | Repair clause-embeddings Alembic revision chain          | 2026-04-04    |
| `TASK-BCK-009` | Fix Railway LangGraph checkpointer psycopg regression    | 2026-04-04    |
| `TASK-BCK-010` | Remove internal constructor fallback wiring              | 2026-02-19    |
| `TASK-BCK-011` | dashboard→app/(app)/ migration plan                      | 2026-04-01    |
| `TASK-BCK-012` | Canonical route parity under app/(app)/                  | 2026-04-01    |
| `TASK-BCK-013` | Preserve /dashboard compatibility                        | 2026-04-01    |
| `TASK-BCK-014` | Retire app/dashboard/                                    | 2026-04-01    |
| `TASK-BCK-015` | Migrate Playwright tests off /dashboard/ paths           | 2026-04-01    |
| `TASK-BCK-016` | Replace canonical route re-exports                       | 2026-04-01    |
| `TASK-BCK-017` | OpenSpec follow-up change creation support               | 2026-04-04    |
| `TASK-BCK-018` | AUTH_BOOTSTRAP_ALLOW_FALLBACK_EMERGENCY config           | 2026-04-07    |
| `TASK-BCK-019` | Prevent Clerk personal-tenant collisions                 | 2026-04-04    |
| `TASK-BCK-020` | Reconcile document adapter contract quality issues       | 2026-05-08    |
| `TASK-BCK-021` | Supabase RLS, composite indexes, pg_stat_statements      | 2026-04-03    |
| `TASK-BCK-022` | Wire TriggerDocumentAnalysisUseCase to Celery            | 2026-04-05    |
| `TASK-BCK-023` | Document update re-trigger flow                          | 2026-04-06    |
| `TASK-BCK-024` | HITL workflow resume mechanism after approval            | 2026-04-06    |
| `TASK-BCK-025` | Real notification delivery (email/Slack/webhook)         | 2026-04-06    |
| `TASK-BCK-026` | Unify AlertGenerator with pipeline save_to_db_node       | 2026-04-06    |
| `TASK-BCK-027` | Reconcile two orchestration systems (deleted unused)     | 2026-04-06    |
| `TASK-BCK-028` | E2E tests for document→LangChain→alerts flow             | 2026-04-06    |
| `TASK-BCK-029` | WBS API endpoint with nested set model                   | 2026-04-06    |
| `TASK-BCK-030` | Authenticated test fixtures for HITL resume tests        | 2026-04-06    |
| `TASK-BCK-031` | LangGraph checkpoint restoration for HITL resume         | 2026-04-06    |
| `TASK-BCK-032` | Monitoring/metrics for workflow resumption               | 2026-04-21    |
| `TASK-BCK-033` | HITL resume API in OpenAPI spec                          | 2026-04-21    |
| `TASK-BCK-035` | Fix duplicate index in Alert model (DuplicateTableError) | 2026-04-06    |
| `TASK-BCK-036` | Fix syntax error in monitoring.py:175                    | 2026-04-06    |
| `TASK-BCK-037` | Update conftest.py for all security models               | 2026-04-06    |
| `TASK-BCK-038` | Implement AIUsageLogORM with schema parity               | 2026-04-06    |
| `TASK-BCK-039` | Gate 4 traceability: sync AuditLogORM                    | 2026-04-06    |
| `TASK-BCK-040` | Ruff linting debt resolution (257→0 violations)          | 2026-05-08    |
| `TASK-BCK-041` | Ruff ARG audit — tenant_id/user_id review                | 2026-05-08    |
| `TASK-BCK-042` | DLQ admin endpoints (GET+POST /api/v1/admin/dlq)         | 2026-04-27    |
| `TASK-BCK-043` | WBS integration tests relocated to tests/integration/    | 2026-04-21    |
| `TASK-BCK-044` | Flaky SLA calculator test fixed with freezegun           | 2026-04-21    |
| `TASK-BCK-045` | Railway alerts import crash (ModuleNotFoundError)        | 2026-04-10    |
| `TASK-BCK-046` | Project status update contract fix                       | 2026-04-11    |
| `TASK-BCK-047` | Document reprocess and status mapping fix                | 2026-04-11    |
| `TASK-BCK-048` | Production alerts route + upload CORS parity             | 2026-04-11    |
| `TASK-BCK-049` | Direct upload Clerk token + error CORS fix               | 2026-04-11    |
| `TASK-BCK-051` | Production alerts/stakeholders 500 triage              | Pending       |
| `TASK-BCK-052` | Analysis graph parallel state merge fix                | 2026-05-17    |
| `TASK-BCK-053` | Fresh analysis checkpoint isolation                    | 2026-05-17    |
| `TASK-BCK-054` | Coherence tracing contract + fail-open telemetry       | 2026-05-17    |
| `TASK-BCK-055` | Coherence structured extraction layer                  | 2026-05-17    |
| `TASK-BCK-056` | AnthropicWrapper anonymizer API mismatch fix           | 2026-05-17    |
| `TASK-BCK-057` | Category-targeted RAG retrieval (6-category SQL)       | 2026-05-17    |
| `TASK-BCK-058` | DET-TIM-STATUS false positive guard                    | 2026-05-17    |
| `TASK-BCK-059` | DET-TEC-SPEC / DET-QUA-* category guards               | 2026-05-17    |
