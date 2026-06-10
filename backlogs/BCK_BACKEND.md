# Backend Tasks & Knowledge Base

**Category**: Backend (BCK)
**Owner Role**: backend
**Last Updated**: 2026-06-09

**Quick Links**:

- 🏠 [Master Index](../C2PRO_MASTER_BACKLOG.md)
- 📋 [Role Profile](../roles/role_backend.md)

---

## 0. Status View

**Pending Tasks**: 2

**Completed Tasks**: 55

- IDs: `TASK-BCK-001`–`TASK-BCK-033`, `TASK-BCK-035`–`TASK-BCK-049`, `TASK-BCK-052`–`TASK-BCK-054`

> Active runtime defects are tracked below; completed history remains archived in [COMPLETED.md](./COMPLETED.md).

---

## 1. Active Tasks

| Status | Priority | Task ID | Depends On | Description | Source |
| ------ | -------- | ------- | ---------- | ----------- | ------ |
| [ ] | P0 | `TASK-BCK-051` | None | Investigate live `500` responses on project alerts and project stakeholders by correlating production error reference IDs with backend logs and verifying applied Alembic head/schema parity for tenant-hardened tables. Live drift repaired 2026-05-16 through `20260516_0001`; 2026-05-25 local parity check repaired a stale stakeholder contract fixture missing `tenant_id` and verified Alembic single head `20260524_0001`; remaining blocker is unavailable production log access for reference-ID correlation. | Production report 2026-05-15 |
| [x] | P0 | `TASK-OPS-DOCFLOW-019` | `TASK-OPS-DOCFLOW-012,TASK-COH-V2-VERSIONING-006` | Repair GitHub `Real Document Operability` bootstrap failure. Fixed `20260526_0001` to recreate `coherence_score_version` instead of using unsafe `ALTER TYPE ... ADD VALUE` in the same transaction, updated `verify_migration_health.py` to parse merge revisions, and verified bootstrap reaches Alembic head `20260526_0001`. `[x] Implemented (Alembic Bootstrap Repair)` | GH Actions run 26538263766 |
| [x] | P0 | `TASK-BCK-052` | None | Fix `/api/v1/analysis/analyze` LangGraph `InvalidUpdateError` caused by duplicated parallel fan-out/join writes to shared keys such as `project_id` after successful parsing. `[x] Implemented (True Multi-Source Fan-In + Branch State Isolation)` | Swagger verification 2026-05-17 |
| [x] | P1 | `TASK-BCK-053` | None | Stop fresh `/api/v1/analysis/analyze` requests from reusing project-level LangGraph checkpoint threads and replaying prior workflow messages into later analyses. `[x] Implemented (Fresh Analysis Thread Isolation)` | Swagger verification 2026-05-17 |
| [x] | P0 | `TASK-BCK-054` | None | Restore live `/api/v1/coherence/evaluate` by fixing the tracing/state contract mismatch, satisfying the current LangSmith SDK `inputs` contract, and making coherence telemetry fail open instead of blocking scoring. `[x] Implemented (Coherence Tracing Contract + Fail-Open Telemetry)` | Swagger verification 2026-05-17 |
| [x] | P0 | `TASK-BCK-055` | None | Fix project bulk-WBS contract drift: `/projects/{project_id}/wbs/bulk` now persists tenant-scoped procurement WBS rows, and `/projects/{project_id}/wbs` immediately returns them with preserved parent hierarchy. | Swagger verification 2026-05-17 |
| [x] | P0 | `TASK-BCK-060` | `TASK-BCK-055` | Reconcile `/projects/{project_id}/wbs` response with its published tree/coverage contract; current live payload is flat (`items` + `total_items`) even though docs promise hierarchy + coverage. Completed 2026-05-25: route now returns root hierarchy in `items`, `coverage`, `alerts`, and legacy `total_items`. | Swagger verification 2026-05-17 |
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
| [x] | P0 | `TASK-BCK-090` | `TASK-BCK-074` | Repair `/api/v1/analysis/analyze` persistence failure where generated risk alerts omitted the legacy non-null `alerts.message` column and Postgres rejected `save_to_db` with `NotNullViolationError`. `[x] Implemented (alert message persistence compatibility)` | Swagger verification 2026-06-07 |
| [x] | P0 | `TASK-BCK-055` | None | Coherence Score™ Structured Extraction Layer — complete. `clause_extractor.py` (combined schema, UUID-safe DB cache, `_load_cache()` validity check requiring at least one `_ALL_REQUIRED_KEYS` field), integrated into `prepare_context` in `nodes.py`. Cache check bug fixed: ingestion metadata `{source, category, affected_categories}` was treated as a cache hit; fixed to require real extracted field. Verified: extraction now fires Haiku LLM calls and enriches `clause.data`. `deterministic_findings_count` rose from 8 → 31. | 2026-05-17 |
| [x] | P1 | `TASK-BCK-056` | None | Fix `AnthropicWrapper` calling `self.anonymizer_service.anonymize_document()` on `AnonymizationService` (wrong API). Swapped to `PiiAnonymizerService` from `core.privacy.anonymizer` which has the correct `anonymize_document()` sync API returning `AnonymizedResult` with `.mapping` and `.anonymized_text`. | 2026-05-17 |
| [x] | P1 | `TASK-BCK-057` | BCK-055 | Category-targeted RAG retrieval: replaced `ORDER BY created_at LIMIT 50` with 6 keyword-filtered SQL queries (10 clauses per category: LEGAL/TIME/BUDGET/TECHNICAL/QUALITY/SCOPE). Penalty, warranty, notice, and deliverable clauses previously invisible now surface. `deterministic_findings_count` 13 → 31. | 2026-05-17 |
| [x] | P1 | `TASK-BCK-058` | BCK-055 | DET-TIM-STATUS false positive guard: rule was firing 7 times on payment/price clauses because ingestion stamped `status: at_risk` on non-TIME clauses. Added `infer_category(clause) not in ("TIME", "SCHEDULE")` guard. Moved `infer_category` + `CATEGORY_KEYWORDS` to `rules_engine/category_utils.py` to break circular import. Schedule category score: 65 → 100. | 2026-05-17 |
| [x] | P1 | `TASK-BCK-059` | BCK-058 | DET-TEC-SPEC / DET-QUA-STANDARD / DET-QUA-INSPECT false positive guards: DET-TEC-SPEC was firing 25 times (preamble, party names, payment terms) because it checked `clause.data.get("category")` ingestion metadata. Replaced with `infer_category(clause) != "TECHNICAL"` guard. DET-QUA-STANDARD and DET-QUA-INSPECT got `infer_category not in ("QUALITY","TECHNICAL")` guards. Test clauses updated to use unambiguous keyword-rich text. | 2026-05-17 |
| [x] | P0 | `TASK-BCK-060` | BCK-055 | Honest coherence scoring: ApplicabilityState (Open/Closed additive method on RuleEvaluator), per-evaluator applicability overrides (12 deterministic + LLM SKIPPED_DISABLED), per-category coverage_map with OR-merge reducer, HeuristicBaselineProvider (80-90 risk-flexed band), coverage-aware calculate_detailed (decay from baseline, global = mean(assessed) x assessed/6 coverage penalty), three-state CategoryBreakdown (unassessed=null / assessed_clean=baseline / assessed_findings). Eliminates fabricated 100/0 subcategory scores; unassessed dimensions return null + drag global score. 104 coherence unit tests green. Branch feat/honest-coherence-scoring. | Design+plan 2026-05-17 |
| [ ] | P0 | `TASK-COH-V2-HOTFIX-001` | None | EPIC-ECOA-V2 Phase A — v1 scoring §14 active-weight guard. Replace `mean × coverage_ratio` collapse in `apps/api/src/coherence/scoring.py:397-400`; when `active_weight < MIN_ACTIVE_WEIGHT (0.35)` return `score=None, reason="insufficient_active_weight"`. Widen `EnrichedCoherenceResult.overall_score`, `DashboardSummary.global_score`, `.coherence_score` to nullable (the score fields to `float \| None`). Propagate `score_reason` through router. Branch `fix/coherence-v1-active-weight-guard`. | Spec 2026-05-25 |
| [ ] | P0 | `TASK-COH-V2-ADAPTER-002` | `TASK-COH-V2-HOTFIX-001` | EPIC-ECOA-V2 Phase B — fix `apps/api/src/coherence/adapters/v1_to_v2.py:65-96` partial-coverage branch: classify null `sub_scores` as `CategoryStatus.INSUFFICIENT_EVIDENCE` (not silent drop), compute real `active_weight` from `DEFAULT_CATEGORY_WEIGHTS`, apply §14 guard. Ships inside HOTFIX-001 PR. | Spec 2026-05-25 |
| [ ] | P0 | `TASK-COH-V2-FRONTEND-003` | `TASK-COH-V2-HOTFIX-001` | EPIC-ECOA-V2 Phase C — frontend null-safe rendering per ADR-009 §18. Remove `?? 0`/`\|\| 0` on all score paths under `apps/web/components/coherence/**`; null score → "Pending evidence" neutral state (no red, no zero); CI grep guard. Vitest + Playwright E2E. Branch `feat/coherence-frontend-null-safe`. **No UI flag**. | Spec 2026-05-25 |
| [ ] | P0 | `TASK-COH-V2-VERSIONING-006` | `TASK-COH-V2-HOTFIX-001` | EPIC-ECOA-V2 Phase F — mandatory `score_version` on every surface: DB columns, Pydantic DTOs (`models.py:241,282,350`, `application/dtos/coherence_dtos.py:61`), graph nodes (`graph/nodes.py:876`, `graph/graph.py:253,302`), telemetry, shadow logs (`services/v2/shadow_runner.py:115`), CSV/PDF/XLS exports, cache keys, frontend (`apps/web/lib/api/contracts.ts`). Canonical 2-value enum `"coherence-v1"`/`"coherence-v2"`. Alembic backfill of NULL + `"v0_flag_based"` + `"v1_exponential_decay"` → `"coherence-v1"` (blind, no row inspection). CI contract test fails if any Pydantic model with `Coherence`/`Dashboard` in name lacks `score_version`. Branch `feat/coherence-score-version-canonical`. | Spec 2026-05-25 §5 |
| [ ] | P0 | `TASK-COH-V2-CACHING-007` | `TASK-COH-V2-VERSIONING-006` | EPIC-ECOA-V2 Phase G — cache namespace versioning. New module `apps/api/src/coherence/cache_keys.py` is sole producer of keys (format `coherence:{version}:{namespace}:{tenant_id}:{project_id}[:{suffix}]`); CI grep ban on ad-hoc `f"coherence:..."` literals outside that module. New `apps/api/src/coherence/cache_invalidation.py` for `on_flag_flip`/`on_result_persisted`/`on_deploy` handlers. New one-shot purge script `apps/api/scripts/invalidate_coherence_cache.py` (dry-run + apply modes) run at Phase A deploy. Integration test `test_flag_toggle_cache_invalidation.py`. Branch `feat/coherence-cache-namespacing`. | Spec 2026-05-25 §6 |
| [ ] | P1 | `TASK-COH-V2-DOCS-005` | `TASK-COH-V2-HOTFIX-001` | EPIC-ECOA-V2 Phase E — rename malformed `worktrees/sentry-perf/w5b-benchmarks/docs/architecture/adr/ADR-009-` → `ADR-009-evidence-oriented-coherence-orchestration.md` via `git mv`; status `Proposed` → `Accepted` with date; regenerate `docs/api/openapi.yaml` via `make openapi` after Phase A merges; update codemap; CHANGELOG entries for A/B/C/F/G. No new task-specific .md files per `.claude/rules/DOCUMENTATION_STRUCTURE.md`. Branch `docs/coherence-adr-009-accepted`. | Spec 2026-05-25 |
| [ ] | P2 | `TASK-BCK-077` | None | Pre-existing test infra failures uncovered during ECOA v2 Phase A+B review. (a) LangGraph tracer `KeyError: 'parent'` blocks `tests/coherence/test_regression.py` end-to-end and scenario tests; (b) `tests/coherence/test_scoring_v3.py` compares `ScoringResult` to floats via `pytest.approx` instead of `.score` attribute; (c) some scoring tests hit real Anthropic API (401 auth) instead of mock when `C2PRO_AI_MOCK=1` is set but the LLM evaluator path bypasses the mock. Confirmed NOT introduced by Phase A (CR verdict 2026-05-26). Source: tdd-guide report + code-reviewer verdict. | CR 2026-05-26 |
| [ ] | P1 | `TASK-COH-V2-CUTOVER-004` | `-001 -003 -006 -007` | EPIC-ECOA-V2 Phase D — make v2 authoritative behind per-tenant flag. **D.0 audit verdict (2026-05-26): EXISTS_PARTIAL** — extend `Tenant.settings: JSONB` at `apps/api/src/core/auth/models.py:100` using alerts pattern (`apps/api/src/alerts/adapters/persistence/tenant_repository.py:27-33`). Extract shared `apps/api/src/core/feature_flags/tenant_flags_service.py`. Read order: `tenant.settings.get("feature_flags", {}).get("coherence_v2_enabled", settings.coherence_v2_enabled)`. Remove `apps/api/src/config.py:319` deferred-comment seam. Telemetry: `coherence.v2_path_used`, `coherence.v1_v2_score_delta`. Canary 10→50→100% over 3 days with shadow-MAE ≤ 15 auto-block (Sentry P1 = 0, p95 latency regression < 30%, v2_authoritative error rate < 0.5%). Branches `feat/coherence-v2-authoritative-canary` (D.0 audit memo) then `feat/coherence-v2-authoritative` (D.1+). architect + security-reviewer + database-reviewer required. | Spec 2026-05-25 §8 |

## 2. Specifications

### TASK-V3-013-03/04/05/06 — ADR-013 Runtime Trust graph contracts

- Scope: additive Runtime Trust changes only. Procurement and Stakeholder Intelligence domains remain future scope; N6 is only wrapped as an existing analysis material node.
- Repair: added `tests/contract/test_graph_node_contracts.py` and wired it into `.github/workflows/tests.yml`; typed analysis graph channels with frozen ADR-013 contracts plus a `node_results` channel.
- Runtime behavior: N6 stakeholder extraction, N8 coherence scoring, and N10 knowledge graph failures now return `NodeResult(status=failed, error=ErrorRecord(...))` and attempt to persist a `processing_error` row in `evidence_extraction_events` instead of silently returning indistinguishable empty results.
- Second pass: N17 save, N4/N5 extractor tools, N12 critique, N13/N14 HITL routing, N6/N8 skip paths, N9 budget typing, N15 citations, coherence honest-null fallback, documentation-health signal, INV-1 scaffold, and Runtime Trust hygiene tests completed under ADR-013 with focused commits on `feat/v3-spine`.
- Third pass: integration-review blocker IR-1 fixed by keeping N4/N5/N9/N15 contract validation at producer boundaries while storing dict-shaped `model_dump(mode="python")` payloads for existing N8/N11/N17 consumers; IR-2 fixed by wiring documentation-health signal population at N16 final assembly. Verification: TASK-V3-013-11 compiled populated-data graph regression + ADR-013 focused suite passed (65 tests).
- N8 coherence contract: the seeded `seed_signals`/`seed_coverage` call is explicit and covered by tests; old test doubles now accept the same signature.
- LLM gate: N8 no longer hardcodes `low_budget_mode=True`; it resolves `feature_v3_coherence_llm` through `core/feature_flags`/settings and fail-closes to low-budget mode when the flag cannot be resolved.
- Verification: RED showed hardcoded `low_budget_mode=True`, missing CI gate, and absent runtime-trust helpers; GREEN passed `apps/api/tests/contract/test_graph_node_contracts.py`, `apps/api/tests/unit/analysis/test_runtime_trust_graph_nodes.py`, and focused existing graph-node suites.

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

### TASK-BCK-090 — Analysis alert message persistence compatibility

- Live finding: Swagger `POST /api/v1/analysis/analyze` advanced through risk extraction and failed during LangGraph task `save_to_db` with `asyncpg.exceptions.NotNullViolationError: null value in column "message" of relation "alerts"`.
- Root cause: the live `alerts` table still enforces legacy non-null `message`, while the current analysis persistence mapper and ORM model only populated `title` and `description`.
- Repair: map `Alert.message` to the legacy table column, default it from `description` when omitted, and explicitly persist `message=description` in analysis, coherence, and alerts repository creation paths.
- Verification: `TS-QA-SWAGGER-ANALYSIS-003` first failed with missing `message`, then passed after the mapper/model repair. Full DB-backed alert contract verification is pending local Postgres availability.

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
- 2026-05-25 completion: `GET /api/v1/projects/{project_id}/wbs` now uses the already-computed procurement WBS tree, returns root items with recursive `children`, includes a `coverage` summary (`total_items`, budget/date/alert counts, completion average), preserves `alerts: []`, and keeps `total_items` for legacy clients.
- Verification: RED `pytest apps/api/tests/projects/test_projects_router.py::TestBulkWBSCompatibilityEndpoint::test_bulk_create_wbs_items_are_visible_from_wbs_read_endpoint -vv -q` failed with missing `coverage`; GREEN targeted test passed, then `pytest apps/api/tests/projects/test_projects_router.py::TestBulkWBSCompatibilityEndpoint apps/api/tests/modules/wbs/adapters/test_wbs_http_dependencies.py -q` passed `3/3`. Full `apps/api/tests/projects/test_projects_router.py -q` timed out after 244s before producing a result.


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

### TASK-COH-V2-HOTFIX-001 — v1 scoring §14 active-weight guard + reason propagation

- **TM scope:** Coherence Score™ is a registered C2Pro differentiator.
- **Bug repro (must turn null after fix):** `POST /api/v1/coherence/evaluate/diagnostics` with a 2-document SCOPE-only project returns `overall_score=15`, `score_reason="assessed_clean"`. Must return `overall_score=null`, `score_reason="insufficient_active_weight"`.
- **Root cause:** `apps/api/src/coherence/scoring.py:397-400` computes `global = mean_assessed × coverage_ratio`. SCOPE-only → `90 × 1/6 = 15`. ADR-009 §1 P1 forbids this formula; §14 mandates returning `null` when `active_weight < MIN_ACTIVE_WEIGHT (0.35)`.
- **Implementation diff outline:**
  1. `apps/api/src/coherence/scoring.py:397-400` — compute `active_weight = sum(DEFAULT_CATEGORY_WEIGHTS[c] for c in assessed) / sum(DEFAULT_CATEGORY_WEIGHTS.values())`; if `< MIN_ACTIVE_WEIGHT` return `ScoringDiagnostics(score=None, reason="insufficient_active_weight", missing_dimensions=unassessed, category_scores=…)`. Otherwise weighted mean over assessed (no coverage multiplier).
  2. `apps/api/src/coherence/scoring.py:407-428` — `assessed_clean` only when all 6 assessed AND no findings (not partial).
  3. `apps/api/src/coherence/models.py:264-268` — `EnrichedCoherenceResult.overall_score: float | None`; relax Field constraints.
  4. `apps/api/src/coherence/models.py:343-344` — `DashboardSummary.global_score`, `.coherence_score: float | None` (widened per orchestrator decision 2026-05-26).
  5. `apps/api/src/coherence/router.py:511-525` — persist `global_score=None` when enriched score is None.
  6. `apps/api/src/coherence/router.py:708-725` — propagate `score_reason` from ORM through `DashboardSummary`.
  7. New telemetry: `coherence.score_reason_emitted` when `overall_score is None`.
- **TDD test list (RED first):**
  - `apps/api/tests/coherence/test_scoring_min_active_weight.py` — SCOPE-only → None+reason; SCOPE+BUDGET (0.50) → numeric; all 6 + no findings → numeric (not `assessed_clean` collapse); `poor_extraction_quality=True` unchanged.
  - `apps/api/tests/coherence/test_router_score_reason_propagation.py` — `score_reason` survives router; `DashboardSummary` reflects.
  - `apps/api/tests/coherence/test_enriched_overall_score_nullable.py` — model accepts `None`.
  - `apps/api/tests/integration/coherence/test_diagnostics_partial_coverage.py` — the user's bug repro turns null.
- **Code-reviewer checklist:** no `mean × coverage_ratio` arithmetic; `MIN_ACTIVE_WEIGHT` imported from `domain/v2_constants.py`; no `?? 0`/`or 0`/`if x else 0` on scores; `score_reason` + `score_missing_dimensions` flow end-to-end; no mutation; existing scoring tests updated not deleted.
- **Acceptance:** all new tests GREEN; `pytest apps/api/tests/coherence/ -x` GREEN; bug repro returns `null`. **No `score_version` rename yet** (TASK-COH-V2-VERSIONING-006 handles).
- **Branch:** `fix/coherence-v1-active-weight-guard` (also contains TASK-COH-V2-ADAPTER-002). **No `main` push.**
- **Source:** `docs/superpowers/specs/2026-05-25-ecoa-v2-hotfix-and-cutover-design.md`, plan §A.

### TASK-COH-V2-ADAPTER-002 — v1→v2 adapter partial-coverage fix

- **Ships inside TASK-COH-V2-HOTFIX-001 PR.**
- **Root cause:** `apps/api/src/coherence/adapters/v1_to_v2.py:65-96` has only two branches (no sub_scores / all numeric). The partial case (e.g. `{SCOPE: 90, BUDGET: null, …}`) falls into the all-numeric branch with hardcoded `active_weight = 1.0`, silently dropping nulls and echoing v1's bad number into `categories_v2`.
- **Implementation:**
  1. Iterate `DEFAULT_CATEGORY_WEIGHTS` instead of `sub_scores.items()`.
  2. Numeric sub_score → `CategoryV2(status=CategoryStatus.SCORED, coherence_score=value, …)`.
  3. Null sub_score → `CategoryV2(status=CategoryStatus.INSUFFICIENT_EVIDENCE, coherence_score=None, …)`.
  4. `active = [c for c in cats if c.status is SCORED]`; `active_weight = sum(weights[c] for c in active) / sum(weights.values())`.
  5. If `active_weight < MIN_ACTIVE_WEIGHT` → `GlobalV2(coherence_score=None, status="insufficient_active_weight", score_reason="insufficient_active_weight", active_weight=active_weight)`.
  6. Else → weighted mean over active only (delegate to `GlobalAggregatorV2` if no circular import; otherwise inline math).
- **TDD test list:**
  - `apps/api/tests/coherence/test_v1_to_v2_adapter.py` (extend):
    - SCOPE-only `{SCOPE: 90, others: None}` → 5×INSUFFICIENT_EVIDENCE + 1×SCORED, `active_weight ≈ 0.20`, `global.coherence_score=None`, `status="insufficient_active_weight"`.
    - All numeric → unchanged behavior (scored, weight 1.0).
    - `{SCOPE: 90, BUDGET: 80, others: None}` → `active_weight ≈ 0.50`, `status="partial"`, weighted mean.
- **Code-reviewer checklist:** real per-category weights (no `1.0` hardcode); `INSUFFICIENT_EVIDENCE` used for nulls; `MIN_ACTIVE_WEIGHT` import (single SoT); Suite ID referenced.
- **Acceptance:** 3 new tests GREEN; flipping `coherence_v2_enabled=True` (manually for verification) over the user's SCOPE-only repro now yields `categories_v2.global.coherence_score is None`.
- **Source:** plan §B.

### TASK-COH-V2-FRONTEND-003 — Frontend null-safe rendering (ADR-009 §18)

- **Goal:** UI never renders `null` as `0` or red. Null = neutral "Pending evidence" state.
- **Files (apps/web):**
  - `components/coherence/DashboardClient.tsx:111-117` — `buildDashboardRows` keeps null `score` (no filter/coerce); rows render `—`.
  - `:136-145` — `barData`/`radarData` typed `score: number | null`.
  - `:147-149` — `catEntries` sort: nulls last, no `a - b` coercion.
  - `:180-182` — PDF row renders `score ?? "—"`.
  - `:239-253` — XLS cells use String type when null.
  - `components/coherence/BreakdownChart.tsx` — accept null bars (muted/striped).
  - `components/coherence/RadarView.tsx` — handle null axis values.
  - `components/coherence/ScoreCard.tsx` — verify `score: number | null`.
  - `lib/api/contracts.ts` — `coherence_score`, `global_score`, sub_scores values typed `number | null`; `score_version: 'coherence-v1' | 'coherence-v2'`.
  - `src/components/coherence/ScoreVersionBadge.tsx` — already exists per planner audit; confirm renders 2-value enum, extend in F.
- **CI guard:** grep for `\?\? 0\b` / `\|\| 0\b` / `Number\(` under `apps/web/**/coherence*` — fail build on match.
- **TDD test list:**
  - `apps/web/components/coherence/DashboardClient.test.tsx` (extend): `coherence_score=null` → empty state renders, no gauge; PDF/XLS write `—` not `0`; mixed `sub_scores` → no NaN.
  - `apps/web/components/coherence/CoherenceEmptyState.test.tsx` (extend): `reason="insufficient_active_weight"` → specific copy citing ADR-009 §14.
  - `apps/web/e2e/coherence-partial-coverage.spec.ts` (new Playwright): upload 1 doc → dashboard shows empty state, no `15`, no `0`.
- **Code-reviewer checklist:** no `?? 0`/`|| 0`/`Number(x) || 0` on score paths; chart components accept `number | null`; empty state uses exact ADR-009 §18 copy; **no UI flag**; no `console.log`.
- **Branch:** `feat/coherence-frontend-null-safe`. **No `main` push.**
- **Source:** plan §C.

### TASK-COH-V2-VERSIONING-006 — Mandatory `score_version` everywhere

- **Canonical enum (closed):** `"coherence-v1"` (exponential-decay engine with §14 guard), `"coherence-v2"` (ECOA v2 aggregator authoritative). Deprecated values backfilled blindly: `NULL` + `"v0_flag_based"` + `"v1_exponential_decay"` → `"coherence-v1"`.
- **Surfaces (must carry `score_version`):**
  - ORM enum: `apps/api/src/coherence/adapters/persistence/models.py:83-87`.
  - Pydantic models: `apps/api/src/coherence/models.py:241, 282, 350` — `Literal["coherence-v1", "coherence-v2"]`, required.
  - DTOs: `apps/api/src/coherence/application/dtos/coherence_dtos.py:61`.
  - Graph: `apps/api/src/coherence/graph/nodes.py:876`, `graph/graph.py:253, 302` — import constant from `domain/v2_constants.py`.
  - Telemetry: `tests/unit/core/observability/test_coherence_tracing.py:107` (`"v1"` → `"coherence-v1"`).
  - Shadow logs: `services/v2/shadow_runner.py:115` — emit both v1 and v2 versions explicitly, not echo.
  - Exports: `apps/web/components/coherence/DashboardClient.tsx:235-269` (PDF/XLS) add Score Version row.
  - Cache keys: embedded as namespace prefix via TASK-COH-V2-CACHING-007.
  - Frontend contracts: `apps/web/lib/api/contracts.ts`.
- **New module:** `apps/api/src/coherence/domain/v2_constants.py` exports `SCORE_VERSION_V1 = "coherence-v1"`, `SCORE_VERSION_V2 = "coherence-v2"`.
- **Alembic migration:** `apps/api/alembic/versions/20260526_0001_coherence_score_version_canonical.py` — adds `"coherence-v2"`, renames `"v1_exponential_decay"` → `"coherence-v1"`, drops `"v0_flag_based"` after backfill of NULL + legacy rows. Upgrade + downgrade both tested.
- **TDD test list:**
  - `apps/api/tests/contract/test_score_version_required.py` (new CI contract test) — walks all Pydantic models in `src.coherence.**` whose name contains `Coherence` or `Dashboard`; asserts `score_version` field present and typed `Literal[...]` with canonical 2 values.
  - `apps/api/tests/coherence/test_score_version_canonical.py` — `CoherenceResult(score_version="v0_flag_based")` raises ValidationError.
  - `apps/api/tests/integration/coherence/test_alembic_score_version_rename.py` — up/down idempotent; backfill correctness.
- **Code-reviewer checklist:** single canonical constant; no string literals `"v1_exponential_decay"`/`"v0_flag_based"`/`"v1"` survive in `apps/api/src/`; CI contract test RED before fix, GREEN after; Alembic up + down both tested.
- **Acceptance:** CI contract test enforces presence on every relevant Pydantic model; all surfaces carry the value; migration applied clean on staging.
- **Branch:** `feat/coherence-score-version-canonical`. **No `main` push.** Requires `security-reviewer` (DB column rename).
- **Source:** plan §F, spec §5.

### TASK-COH-V2-CACHING-007 — Cache namespace versioning + invalidation

- **Goal:** cache keys carry `score_version`; flag flips invalidate stale tenant cache; Phase A deploy purges all coherence keys (semantics changed).
- **New module:** `apps/api/src/coherence/cache_keys.py` — single function `key(*, namespace: Literal["dashboard","diagnostics","aggregate","export"], version: Literal["coherence-v1","coherence-v2"], tenant_id: UUID, project_id: UUID, suffix: str | None = None) -> str`. Format: `coherence:{version}:{namespace}:{tenant_id}:{project_id}[:{suffix}]`. Unknown namespace raises.
- **New module:** `apps/api/src/coherence/cache_invalidation.py` — handlers `on_flag_flip(tenant_id)`, `on_result_persisted(tenant_id, project_id)`, `on_deploy()`. Uses Redis `UNLINK` (non-blocking) not `DEL`. Idempotent.
- **New script:** `apps/api/scripts/invalidate_coherence_cache.py` — one-shot purge `coherence:*` at Phase A deploy time. Dry-run mode (`--dry-run`) logs key count and exits 0 without unlinking. Safe to run multiple times.
- **CI guard:** ruff custom rule OR `.github/workflows/lint.yml` grep step bans `f"coherence:` literals in `apps/api/src/` outside `cache_keys.py`. Fails build on match.
- **TDD test list:**
  - `apps/api/tests/coherence/test_cache_keys.py` — happy path; suffix appended; unknown namespace raises.
  - `apps/api/tests/ci/test_no_adhoc_coherence_keys.py` — greps `apps/api/src/**` for `f"coherence:` outside `cache_keys.py`; 0 matches required.
  - `apps/api/tests/integration/coherence/test_flag_toggle_cache_invalidation.py` — flip flag for tenant T → `UNLINK coherence:*:*:T:*` executed; subsequent request recomputes; other tenants' keys untouched.
- **Telemetry:** `coherence.cache_invalidated{tenant_id, trigger, keys_unlinked}`.
- **Code-reviewer checklist:** all cache reads/writes via `cache_keys.key()`; `UNLINK` not `DEL`; telemetry emitted with counts; idempotent handler; purge script has `--dry-run`.
- **Acceptance:** 5 tests GREEN; CI ban check enforced; staging dry-run of purge logs key count cleanly.
- **Branch:** `feat/coherence-cache-namespacing`. **No `main` push.** Requires `security-reviewer` (Redis blast-radius review).
- **Source:** plan §G, spec §6.

### TASK-COH-V2-DOCS-005 — ADR-009 status + OpenAPI regen + codemap

- **Actions:**
  1. `git mv worktrees/sentry-perf/w5b-benchmarks/docs/architecture/adr/ADR-009-` → `ADR-009-evidence-oriented-coherence-orchestration.md` (filename currently ends in a literal dash — broken).
  2. `docs/architecture/decisions/009-coherence-score-v2-evidence-aware.md` — status `Proposed` → `Accepted` with date 2026-05-26 and revision history line.
  3. `make openapi` after Phase A merges; commit clean `docs/api/openapi.yaml` diff. **Do not hand-edit `openapi.yaml`** (CLAUDE.md gotcha).
  4. Update `CLAUDE.md` "Active Analysis Pipeline" N8 row to point at new `cache_keys.py`, `score_version` enum, and removal of `mean × coverage_ratio` formula.
  5. `CHANGELOG.md` root entries for Phases A/B/C/F/G/D.
- **No new task-specific .md files** per `.claude/rules/DOCUMENTATION_STRUCTURE.md`.
- **Acceptance:** clean OpenAPI diff committed; ADR status Accepted with revision history; codemap reflects post-fix state.
- **Branch:** `docs/coherence-adr-009-accepted`. Agent: `doc-updater` (Haiku).
- **Source:** plan §E.

### TASK-COH-V2-CUTOVER-004 — Make ECOA v2 authoritative behind per-tenant flag

- **D.0 audit verdict (2026-05-26): EXISTS_PARTIAL** — reuse, do not build new infra.
  - Global mechanism: `apps/api/src/core/middleware/feature_flags.py:25-37` — `require_feature(flag_name)` reads `getattr(settings, flag_name, False)`.
  - Per-tenant column: `apps/api/src/core/auth/models.py:100` — `Tenant.settings: Mapped[dict] = mapped_column(JSONB, default=dict)`, already used by alerts module (sub-key `alerts_workspace`) at `apps/api/src/alerts/adapters/persistence/tenant_repository.py:27-33`.
  - Pattern to extend: `tenant.settings.get("feature_flags", {}).get("coherence_v2_enabled", settings.coherence_v2_enabled)`.
  - Gap: extract shared `apps/api/src/core/feature_flags/tenant_flags_service.py` so alerts + coherence don't duplicate get/set boilerplate.
  - Seam to remove: `apps/api/src/config.py:319` comment `# Per-tenant override is deferred — single global toggle for now.`
- **Prerequisites (gate, must be GREEN before D.1):** Phases A/B/C/F/G merged to `main` (via PRs, no direct pushes); shadow MAE ≤ 5 over rolling 7-day window; zero Sentry P1 events tagged `coherence.shadow.*` in last 48h.
- **D.1 implementation:**
  1. `apps/api/src/coherence/router.py:736-756` — replace global flag check with `coherence_v2_enabled_for_tenant(tenant_id)`.
  2. New `apps/api/src/coherence/feature_flags.py` — wrapper around `tenant_flags_service`.
  3. `apps/api/src/coherence/services/v2/orchestrator.py` — authoritative path when flag ON; result conforms to existing `DashboardSummary` contract (top-level scores + `categories_v2` both populated from v2 aggregator).
  4. Telemetry: `coherence.v2_path_used{tenant_id, path∈{v1_only,v2_shadow,v2_authoritative}, score_version}` and `coherence.v1_v2_score_delta{tenant_id, delta_abs, delta_signed, v1_status, v2_status}`.
- **Canary rollout (3 days):**
  - 10% of tenants (hashed `tenant_id`) → 24h burn; auto-block if shadow MAE > 15 OR `v2_authoritative` error rate > 0.5% OR p95 latency regression > 30%.
  - 50% → 24h; same guards.
  - 100% → 24h burn; same guards.
  - GA: flag default → True, manual sign-off.
- **TDD test list:**
  - `apps/api/tests/coherence/test_v2_authoritative_path.py` — flag ON → v2 score; flag OFF → v1 unchanged; flag ON + SCOPE-only → `None`/`coherence-v2`/`insufficient_active_weight`.
  - `apps/api/tests/coherence/test_telemetry_v2_path.py` — events emitted with correct tags.
  - `apps/api/tests/integration/coherence/test_per_tenant_flag_flip.py` — flag flip → next request uses new path AND cache invalidated (covered by CACHING-007).
- **Code-reviewer checklist:** central tenant-flag helper (no scattered `getattr(settings, …)`); both `categories_v2` AND top-level fields populated; `score_version="coherence-v2"` deterministic; telemetry tags carry `tenant_id` only (no PII); shadow comparison still runs in parallel during canary; rollback documented in PR.
- **Branches:** `feat/coherence-v2-authoritative-canary` (D.0 audit memo only) then `feat/coherence-v2-authoritative` (D.1+). **No `main` push.**
- **Required reviewers:** `architect` (tenant flag plumbing), `security-reviewer` (tenant isolation, telemetry PII), `database-reviewer` (no migration; JSONB read/write only).
- **Source:** plan §D, spec §8.

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
| `TASK-BCK-051` | Production alerts/stakeholders 500 triage              | Blocked 2026-05-25 - production log access |
| `TASK-BCK-052` | Analysis graph parallel state merge fix                | 2026-05-17    |
| `TASK-BCK-053` | Fresh analysis checkpoint isolation                    | 2026-05-17    |
| `TASK-BCK-054` | Coherence tracing contract + fail-open telemetry       | 2026-05-17    |
| `TASK-BCK-055` | Coherence structured extraction layer                  | 2026-05-17    |
| `TASK-BCK-056` | AnthropicWrapper anonymizer API mismatch fix           | 2026-05-17    |
| `TASK-BCK-057` | Category-targeted RAG retrieval (6-category SQL)       | 2026-05-17    |
| `TASK-BCK-058` | DET-TIM-STATUS false positive guard                    | 2026-05-17    |
| `TASK-BCK-059` | DET-TEC-SPEC / DET-QUA-* category guards               | 2026-05-17    |
