# Backend Tasks & Knowledge Base

**Category**: Backend (BCK)
**Owner Role**: backend
**Last Updated**: 2026-06-03

**Quick Links**:

- 🏠 [Master Index](../C2PRO_MASTER_BACKLOG.md)
- 📋 [Role Profile](../roles/role_backend.md)

---

## 0. Status View

**Pending Tasks**: 10

**Completed Tasks**: 61

- IDs: `TASK-BCK-001`–`TASK-BCK-033`, `TASK-BCK-035`–`TASK-BCK-049`, `TASK-BCK-052`–`TASK-BCK-054`, `TASK-BCK-062`–`TASK-BCK-064`, `TASK-BCK-089`

> Active runtime defects are tracked below; completed history remains archived in [COMPLETED.md](./COMPLETED.md).

---

## 1. Active Tasks

| Status | Priority | Task ID                      | Depends On                                        | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                  | Source                                 |
| ------ | -------- | ---------------------------- | ------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ | -------------------------------------- |
| [ ]    | P0       | `TASK-BCK-051`               | None                                              | Investigate live `500` responses on project alerts and project stakeholders by correlating production error reference IDs with backend logs and verifying applied Alembic head/schema parity for tenant-hardened tables. Live drift repaired 2026-05-16 through `20260516_0001`; 2026-05-25 local parity check repaired a stale stakeholder contract fixture missing `tenant_id` and verified Alembic single head `20260524_0001`; remaining blocker is unavailable production log access for reference-ID correlation.                                                                                                                                                                                                                                                                                                                                                                                                                                      | Production report 2026-05-15           |
| [x]    | P1       | `TASK-BCK-063`               | None                                              | Persist `parsed_at` on successful parse. `[x] Verified + test repaired 2026-06-04` — Implementation was already correct (`parse_document_use_case.py` step 8 passes `parsed_at=datetime.now(UTC)` to `update_status`). Root cause of null: `test_parse_document_updates_parsed_at` mock fixture was missing `update_metadata` in spec, so the success path threw `AttributeError` before reaching `update_status(parsed_at=...)`. Fix: added `update_metadata=AsyncMock()` to `mock_repository` fixture. 3/3 tests green, ruff clean.                                                                                                                                                                                                                                                                                                                                                                                                                     | Swagger verification 2026-05-17        |
| [x]    | P0       | `TASK-BCK-064`               | `TASK-BCK-062`                                    | Wire parsed schedule evidence into coherence scoring. `[x] Fixed 2026-06-04` — Root cause: `DocumentType.SCHEDULE="schedule"` but registry `doc_type_priors` uses key `"schedule_gantt"`. `_seed_coverage_from_category_router()` passed the raw DB value to `router.route()`, so no prior floor (0.75) was applied; schedule rows (task names/dates) lacked enough coherence vocabulary to clear the threshold, leaving TIME unassessed. Fix: added `_DB_DOC_TYPE_TO_REGISTRY = {"schedule": "schedule_gantt", "budget": "budget_boq"}` mapping in `coherence/graph/graph.py`; normalize before routing. Same fix preventively covers the `budget`→`budget_boq` gap. Suite `TS-UD-COH-SCH-001`: **7/7 green**, ruff clean. Files: `src/coherence/graph/graph.py`, `tests/coherence/test_schedule_coverage_routing.py`.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                          | Swagger verification 2026-05-17        |
| [x] | P1 | `TASK-BCK-088` | `TASK-BCK-084` | Implement prototype centroid build/cache only after embedding dimension decision; current pgvector path expects 1536 dims, so `bge-m3` requires explicit compatibility check or migration. Owner: Gemini bake-off/spec tests. `[x] Implemented (Centroid build/cache + explicit dimension guard)` — `category_centroids` table (`(category, embedding_model, score_version)` unique key + `seed_hash`, `vector(1536)`) via migration `20260603_0019`; `CentroidBuilderService.ensure_centroids_built` (seed_hash reproducibility, L2-normalized mean, hash-mismatch rebuild, idempotent skip). **Embedding-model decision recorded:** OpenAI `text-embedding-3-small` (1536) chosen for pgvector compatibility (SPEC §9.2 empirical bake-off bypassed for v1 — swappable via the composite key, no migration). **Compatibility guard (two-layer):** (a) `_KNOWN_MODEL_DIMS` pre-flight reject of known incompatible-dim models before any embedding call; (b) name-independent post-embedding length backstop aborting before pgvector INSERT. Verified 2026-06-03: `pytest tests/coherence/test_centroid_builder.py` = **8/8 green**, ruff clean. Builder intentionally unwired pending `TASK-BCK-089` (Capa 2 consumer). | `SPEC_category_routing_coherence_v1.md` §9.2 |
| [x] | P1 | `TASK-BCK-089` | `TASK-BCK-086,TASK-BCK-088` | Add `CategoryClassifierNode` for ambiguous chunks only; clear chunks must not call LLM and classifier returns multi-label relevance scores. `[x] Implemented (Capa 2 LLM escalation)` — `CategoryClassifierNode` service + `ChunkClassificationResult` frozen dataclass in `apps/api/src/coherence/application/services/category_classifier_node.py`. Ambiguity gate: `escalate_low < relevance < escalate_high` (strict bounds) per category. LLM called at most once per ambiguous chunk via `AITaskType.CLASSIFICATION` (Haiku, low_budget_mode=True). Scores clamped to [0,1]; merge rule: LLM overrides only ambiguous categories, clear/low categories keep Capa 1 score. Graceful degradation on LLM error or JSON parse failure → returns Capa 1 scores unchanged with `was_escalated=False`. Suite `TS-UD-COH-CCN-001`: **22/22 green**, ruff clean. Verified 2026-06-04. | `SPEC_category_routing_coherence_v1.md` §D3 |
| [ ]    | P0       | `TASK-COH-V2-HOTFIX-001`     | None                                              | EPIC-ECOA-V2 Phase A — v1 scoring §14 active-weight guard. Replace `mean × coverage_ratio` collapse in `apps/api/src/coherence/scoring.py:397-400`; when `active_weight < MIN_ACTIVE_WEIGHT (0.35)` return `score=None, reason="insufficient_active_weight"`. Widen `EnrichedCoherenceResult.overall_score`, `DashboardSummary.global_score`, `.coherence_score` to nullable (the score fields to `float \| None`). Propagate `score_reason` through router. Branch `fix/coherence-v1-active-weight-guard`.                                                                                                                                                                                                                                                                                                                                                                                                                                                  | Spec 2026-05-25                        |
| [ ]    | P0       | `TASK-COH-V2-ADAPTER-002`    | `TASK-COH-V2-HOTFIX-001`                          | EPIC-ECOA-V2 Phase B — fix `apps/api/src/coherence/adapters/v1_to_v2.py:65-96` partial-coverage branch: classify null `sub_scores` as `CategoryStatus.INSUFFICIENT_EVIDENCE` (not silent drop), compute real `active_weight` from `DEFAULT_CATEGORY_WEIGHTS`, apply §14 guard. Ships inside HOTFIX-001 PR.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                   | Spec 2026-05-25                        |
| [ ]    | P0       | `TASK-COH-V2-FRONTEND-003`   | `TASK-COH-V2-HOTFIX-001`                          | EPIC-ECOA-V2 Phase C — frontend null-safe rendering per ADR-009 §18. Remove `?? 0`/`\|\| 0` on all score paths under `apps/web/components/coherence/**`; null score → "Pending evidence" neutral state (no red, no zero); CI grep guard. Vitest + Playwright E2E. Branch `feat/coherence-frontend-null-safe`. **No UI flag**.                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                                | Spec 2026-05-25                        |
| [ ]    | P0       | `TASK-COH-V2-VERSIONING-006` | `TASK-COH-V2-HOTFIX-001`                          | EPIC-ECOA-V2 Phase F — mandatory `score_version` on every surface: DB columns, Pydantic DTOs (`models.py:241,282,350`, `application/dtos/coherence_dtos.py:61`), graph nodes (`graph/nodes.py:876`, `graph/graph.py:253,302`), telemetry, shadow logs (`services/v2/shadow_runner.py:115`), CSV/PDF/XLS exports, cache keys, frontend (`apps/web/lib/api/contracts.ts`). Canonical 2-value enum `"coherence-v1"`/`"coherence-v2"`. Alembic backfill of NULL + `"v0_flag_based"` + `"v1_exponential_decay"` → `"coherence-v1"` (blind, no row inspection). CI contract test fails if any Pydantic model with `Coherence`/`Dashboard` in name lacks `score_version`. Branch `feat/coherence-score-version-canonical`.                                                                                                                                                                                                                                          | Spec 2026-05-25 §5                     |
| [ ]    | P0       | `TASK-COH-V2-CACHING-007`    | `TASK-COH-V2-VERSIONING-006`                      | EPIC-ECOA-V2 Phase G — cache namespace versioning. New module `apps/api/src/coherence/cache_keys.py` is sole producer of keys (format `coherence:{version}:{namespace}:{tenant_id}:{project_id}[:{suffix}]`); CI grep ban on ad-hoc `f"coherence:..."` literals outside that module. New `apps/api/src/coherence/cache_invalidation.py` for `on_flag_flip`/`on_result_persisted`/`on_deploy` handlers. New one-shot purge script `apps/api/scripts/invalidate_coherence_cache.py` (dry-run + apply modes) run at Phase A deploy. Integration test `test_flag_toggle_cache_invalidation.py`. Branch `feat/coherence-cache-namespacing`.                                                                                                                                                                                                                                                                                                                       | Spec 2026-05-25 §6                     |
| [ ]    | P1       | `TASK-COH-V2-DOCS-005`       | `TASK-COH-V2-HOTFIX-001`                          | EPIC-ECOA-V2 Phase E — rename malformed `worktrees/sentry-perf/w5b-benchmarks/docs/architecture/adr/ADR-009-` → `ADR-009-evidence-oriented-coherence-orchestration.md` via `git mv`; status `Proposed` → `Accepted` with date; regenerate `docs/api/openapi.yaml` via `make openapi` after Phase A merges; update codemap; CHANGELOG entries for A/B/C/F/G. No new task-specific .md files per `.claude/rules/DOCUMENTATION_STRUCTURE.md`. Branch `docs/coherence-adr-009-accepted`.                                                                                                                                                                                                                                                                                                                                                                                                                                                                         | Spec 2026-05-25                        |
| [ ]    | P2       | `TASK-BCK-077`               | None                                              | Pre-existing test infra failures uncovered during ECOA v2 Phase A+B review. (a) LangGraph tracer `KeyError: 'parent'` blocks `tests/coherence/test_regression.py` end-to-end and scenario tests; (b) `tests/coherence/test_scoring_v3.py` compares `ScoringResult` to floats via `pytest.approx` instead of `.score` attribute; (c) some scoring tests hit real Anthropic API (401 auth) instead of mock when `C2PRO_AI_MOCK=1` is set but the LLM evaluator path bypasses the mock. Confirmed NOT introduced by Phase A (CR verdict 2026-05-26). Source: tdd-guide report + code-reviewer verdict.                                                                                                                                                                                                                                                                                                                                                          | CR 2026-05-26                          |
| [ ]    | P1       | `TASK-COH-V2-CUTOVER-004`    | `-001 -003 -006 -007`                             | EPIC-ECOA-V2 Phase D — make v2 authoritative behind per-tenant flag. **D.0 audit verdict (2026-05-26): EXISTS_PARTIAL** — extend `Tenant.settings: JSONB` at `apps/api/src/core/auth/models.py:100` using alerts pattern (`apps/api/src/alerts/adapters/persistence/tenant_repository.py:27-33`). Extract shared `apps/api/src/core/feature_flags/tenant_flags_service.py`. Read order: `tenant.settings.get("feature_flags", {}).get("coherence_v2_enabled", settings.coherence_v2_enabled)`. Remove `apps/api/src/config.py:319` deferred-comment seam. Telemetry: `coherence.v2_path_used`, `coherence.v1_v2_score_delta`. Canary 10→50→100% over 3 days with shadow-MAE ≤ 15 auto-block (Sentry P1 = 0, p95 latency regression < 30%, v2_authoritative error rate < 0.5%). Branches `feat/coherence-v2-authoritative-canary` (D.0 audit memo) then `feat/coherence-v2-authoritative` (D.1+). architect + security-reviewer + database-reviewer required. | Spec 2026-05-25 §8                     |

## 2. Specifications

### TASK-BCK-083..089 — Coherence Category Routing v1

- Critical decision: routing and scoring are separate; priors/coverage decide what is assessed, findings decide score impact.
- Naming decision: registry may use `SCHEDULE`, but coherence boundary maps to existing `TIME`; do not mix silently.
- First shippable slice: registry loader + prior-floor deterministic router, no embeddings/LLM yet.
- Parallel plan: Codex orchestrates/integrates, Gemini handles registry validation and tests, DeepSeek handles router/segmentation spike.
- Known risk: current pgvector infrastructure expects 1536 dimensions; do not assume `bge-m3` fits without migration/bake-off.
- Centroid RLS decision for TASK-BCK-088: use nullable `tenant_id` with RLS enabled. v1 rows are global (`tenant_id IS NULL`) and service-written only; reads may include global rows plus current-tenant rows for future tenant overrides. Do not create a no-tenant table.
- Boundary contract:
  - Registry category enum is `LEGAL|SCOPE|BUDGET|SCHEDULE|TECHNICAL|QUALITY`.
  - Coherence graph/scoring category enum remains `LEGAL|SCOPE|BUDGET|TIME|TECHNICAL|QUALITY|CROSS`.
  - Only one explicit adapter may translate `SCHEDULE -> TIME`; no inline silent mapping in evaluators, scoring, prompts, or persistence.
  - Router output is relevance/coverage evidence: `category`, `score`, `source_breakdown`, `status`, `segment_id`, `chunk_id`, evidence pointers. It must not emit `FindingSignal` directly.
  - N4 risk bridge remains finding evidence only. It can seed `FindingSignal`s and coverage, but it is not the category router.
  - `coverage_map` receives assessed categories from routing and evaluators; scoring still consumes findings and existing `ScoringService`.
  - `InsufficientEvidence` is a first-class router/coherence state, not a missing key.
- Agent handoff:
  - Gemini Code (`TASK-BCK-084`): create failing registry tests first; validate schema, regex compilation, thresholds, priors, version fields, and category naming. Do not implement embeddings.
  - DeepSeek (`TASK-BCK-085`): produce segment/chunk domain contracts and structural segmentation tests. Do not split on English `schedule`.
  - DeepSeek + Codex (`TASK-BCK-086`): implement deterministic router over priors + structural + lexicon only; embeddings and LLM remain blocked for later tasks.
  - Codex (`TASK-BCK-087`): integrate router relevance into coherence coverage after T084-T086 are green.
- TASK-BCK-087 result: `evaluate_coherence()` and `evaluate_coherence_async()` now seed `coverage_map` from `CategoryRouter` before graph execution. This only marks assessed categories; it does not create `FindingSignal`s. Contract priors now keep `LEGAL` assessed_clean even when the N4 risk bridge has no extracted risk evidence.

### TASK-BCK-081 — AI Budget Reset Timestamp Normalization

- Root cause: `CostControllerService.check_budget_availability()` used timezone-aware UTC for `Tenant.ai_spend_last_reset`.
- Persistence contract: `tenants.ai_spend_last_reset` is `DateTime`/`TIMESTAMP WITHOUT TIME ZONE`, matching other legacy tenant timestamps.
- Fix: added `_utcnow_naive()` in `apps/api/src/core/ai/cost_controller.py` and assigned naive UTC on monthly budget reset.
- Regression: `TS-UD-AI-COST-001` in `apps/api/tests/core/ai/test_cost_controller_swarm.py` asserts reset timestamps have `tzinfo is None`.
- Verification: focused RED failed on aware UTC; after fix, `python -m pytest apps/api/tests/core/ai/test_cost_controller_swarm.py -q` passed 35 tests and `ruff check` returned 0 errors.

### TASK-BCK-082 — Risk Extraction Deterministic Fallback

- Root cause: live Swagger analysis no longer hit the budget timestamp DB error, but `risk_extraction` consumed max-token LLM responses, validated to no risk items, retried, and left `extracted_risks=[]`.
- Fix: set `RiskExtractionTool.retry_policy` to zero retries for empty-extraction validation failures and added N4 fallback from `risk_extractor_node()` to `DeterministicRiskRulesService` when the AI tool leaves a non-empty contract without risks.
- Coverage: `TS-QA-SWAGGER-ANALYSIS-001` now proves N4 fills deterministic risks after AI tool failure and that `risk_extraction` performs only one wrapper call for empty validation failures.
- Language coverage: deterministic fallback recognizes Spanish contract terms for penalties, payment, warranty, schedule, and technical/specification risks.
- Traceability: deterministic fallback now derives `source_quote` and `source_text_snippet` from verbatim source sentences that match each risk category's trigger terms, avoiding placeholder citations rejected by critique.
- Verification: `python -m pytest apps/api/tests/unit/analysis/test_ai_tool_execution_contract.py apps/api/tests/unit/analysis/graph/test_thin_nodes.py -q` passed 34 tests and `ruff check` returned 0 errors.

### TASK-CE-F1-01 — EvidenceClaim + SourceRef + VerificationStatus + LocatorQuality (ADR-011 Phase 1)

- Implemented the universal evidence claim contract per ADR-011 §4.
- `Dimension` (str, Enum): SCOPE|BUDGET|TIME|TECHNICAL|LEGAL|QUALITY — independent of CoherenceCategory, mapping at boundary layer.
- `LocatorQuality` (str, Enum): EXACT|APPROXIMATE|MISSING — input to verification state transitions, not a second multiplier.
- `VerificationStatus` (str, Enum): VERIFIED|UNCERTAIN|UNSUPPORTED|FABRICATION_SUSPECTED.
- `SourceRef` (frozen dataclass): document_id, page, char_start/end, quote, locator_quality.
- `EvidenceClaim` (frozen dataclass): 13 fields + `certainty_effective` @property.
- Module: `apps/api/src/evidence/domain/models.py`.
- Suite: TS-UD-EVI-CLM-001.

### TASK-CE-F1-02 — EvidenceMaturityLayer (ADR-010 Phase 1)

- Implemented the EML contracts per ADR-010 §3-4.
- `EvidenceMaturityLevel` (int, Enum): 0-5 normalized invariant scale; composition per profile.
- `DocumentPresence` (frozen dataclass): document_type (reuses DocumentType), count, latest_uploaded_at.
- `EvidenceMaturityReport` (frozen dataclass): project_id, level, level_name, ladder_version, cross_validation_capability, present_types, missing_for_next_level, next_level_unlocks, computed_at.
- `cross_validation_capability` is named deliberately to avoid collision with `evidence_coverage` (ADR-011).
- Module: `apps/api/src/evidence/domain/models.py`.
- Suite: TS-UD-EVI-EML-001.

### TASK-CE-F1-03 — Test suite (immutability + serialization + certainty_effective matrix)

- 25 tests, all green (`pytest --no-header -p no:asyncio`).
- `TestImmutability` (4): FrozenInstanceError on EvidenceClaim, EMR, SourceRef, DocumentPresence.
- `TestSerialization` (4): dataclasses.asdict() round-trip + JSON serialization.
- `TestCertaintyEffective` (9): Full matrix — VERIFIED(×1.0), UNCERTAIN(×0.6), UNSUPPORTED(×0.2), FABRICATION_SUSPECTED(0.0), verification_deferred uses UNCERTAIN, locator_quality NOT a second multiplier, default status is UNCERTAIN.
- `TestEnumExhaustiveness` (4): Exact cardinality for all 4 enums.
- `TestDefaults` (1): ADR-012 hooks default to inert (human_verified=False, human_certainty=None, etc.).
- File: `apps/api/tests/modules/evidence/domain/test_evidence_contracts.py`.
- Suite: TS-UD-EVI-CTS-001.

### TASK-CE-F2-01 — LEGAL pilot extraction adapter (ADR-011/ADR-012 Phase 2A.1)

- Implemented isolated LEGAL extraction boundary under `apps/api/src/evidence/legal/`.
- Supported pilot claim types: `payment_terms`, `late_fees_penalties`, and `liability_cap`.
- Contractual value schemas default all missing fields to `None`; no currency, term, cap, rate, or percentage is fabricated.
- Schema and envelope failures emit `ProcessingError` outside the `EvidenceClaim` stream; structural errors never map to `FABRICATION_SUSPECTED`.
- Wrong dimensions and unknown claim types emit `OutOfScopeEvent`, `logger.warning`, and `evidence.claims.out_of_scope` metrics.
- Phase 2A shadow claims are always `VerificationStatus.UNCERTAIN` with `verification_trace={"phase": "2A_shadow", "cvc_disabled": True}`.
- Verification: `pytest apps/api/tests/modules/evidence/legal -q` passed 58/58 after adding traceability coverage; `pytest apps/api/tests/modules/evidence -q` passed 83/83.
- Suite: TS-UD-EVI-LEGAL-001.

### TASK-CE-F2A3-01 — DB Round-trip Certification (ADR-011 Phase 2A.3.1)

- Alembic cycle: `upgrade head` → `downgrade -1` → `upgrade head` verified against real Postgres `c2pro_test`.
- Migration `20260529_0001` creates `evidence_claims` and `evidence_extraction_events` shadow tables.
- ORM models registered in `alembic/env.py` for autogenerate discovery.
- `SqlAlchemyEvidenceShadowRepository` persists the adapter's three output channels (claims, processing_errors, out_of_scope) as write-only shadow data.
- 7 integration tests (`tests/modules/evidence/persistence/test_evidence_persistence_roundtrip.py`):
  - `test_full_roundtrip_cardinality`: 4 claims + 3 events.
  - `test_claims_channel_populated`: lifecycle_status=shadow, dimension=LEGAL, cvc_disabled=True, all claims within [0,1] ranges.
  - `test_events_channel_populated`: 2 out_of_scope (wrong_dimension + unknown_claim_type) + 1 processing_error (schema_validation_error).
  - `test_shared_extraction_run_id`: Same run_id across claims and events.
  - `test_jsonb_null_preservation`: Schedule 4 silent fields remain null, not absent or defaulted.
  - `test_db_enum_constraints_enforced`: Invalid dimension rejected at DB level.
  - `test_db_range_constraints_enforced`: Negative algorithmic_certainty rejected at DB level.
- Verification: `pytest ...test_evidence_persistence_roundtrip.py` → 7/7 passed (201.46s).
- Suite: TS-INT-DB-EVI-SHADOW-001.
- NOT connected to Celery, NOT read by Coherence Engine, NOT touching scoring.

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

### TASK-BCK-062 — Real schedule workbook rejected by brittle Excel parser ✅ DONE 2026-06-04

- `[x] Verified 2026-06-04` — `ExcelFileParser._find_schedule_headers` now scans all rows (not just row 1) and accepts Spanish aliases (`actividad`/`inicio`/`fin`/`duración (días)`). Suite `TS-UD-DOC-XLS-001` (`test_parse_schedule_discovers_spanish_header_row_after_title_block`) covers the exact `Cronograma.xlsx` scenario with title block + Spanish header at row 4. 9/9 tests green. Backlog status was never updated after the fix landed.
- Live finding: `POST /api/v1/documents/{document_id}/parse` failed on uploaded schedule `Cronograma.xlsx`.
- Actual workbook shape: row 1 is a merged title block; the real table header is row 10 with Spanish labels `ID`, `WBS`, `Actividad`, `Duración (días)`, `Inicio`, `Fin`, `Predecesoras`, `Recursos clave`.
- Current parser limitation: it only inspects row 1 and only accepts English `task`, `start date`, `end date`.
- Product implication: the schedule lane is not yet credible for real construction files; Phase 1 cannot honestly mark schedule analysis green until this parser accepts realistic workbooks and reports format issues as controlled validation failures.
- Follow-up discovered during live verification: `TASK-BCK-063` is needed because successful parse currently updates status but leaves `parsed_at` null, which weakens downstream history/evidence integrity. 2. the route summary says “Get Project WBS Tree” and promises “Hierarchical WBS tree with children”; 3. implementation calls `GetWBSTreeUseCase(...)` but discards that result, then returns `ListWBSItemsUseCase(...)` instead.
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

| Task ID         | Description                                              | Completed                                  |
| --------------- | -------------------------------------------------------- | ------------------------------------------ |
| `TASK-BCK-001`  | Dependencies injected via FastAPI / service constructors | 2026-04-04                                 |
| `TASK-BCK-002`  | Retire legacy `app/dashboard/`                           | 2026-02-19                                 |
| `TASK-BCK-003`  | Remove `_Default*Service` dummy implementations          | 2026-02-19                                 |
| `TASK-BCK-004`  | LangGraph nodes wrap existing use cases                  | 2026-02-19                                 |
| `TASK-BCK-005`  | HITL real service implementation                         | 2026-02-19                                 |
| `TASK-BCK-006`  | Verifier produces JSON for dashboarding                  | 2026-04-04                                 |
| `TASK-BCK-007`  | Fix Alembic WBS uniqueness migration                     | 2026-04-04                                 |
| `TASK-BCK-008`  | Repair clause-embeddings Alembic revision chain          | 2026-04-04                                 |
| `TASK-BCK-009`  | Fix Railway LangGraph checkpointer psycopg regression    | 2026-04-04                                 |
| `TASK-BCK-010`  | Remove internal constructor fallback wiring              | 2026-02-19                                 |
| `TASK-BCK-011`  | dashboard→app/(app)/ migration plan                      | 2026-04-01                                 |
| `TASK-BCK-012`  | Canonical route parity under app/(app)/                  | 2026-04-01                                 |
| `TASK-BCK-013`  | Preserve /dashboard compatibility                        | 2026-04-01                                 |
| `TASK-BCK-014`  | Retire app/dashboard/                                    | 2026-04-01                                 |
| `TASK-BCK-015`  | Migrate Playwright tests off /dashboard/ paths           | 2026-04-01                                 |
| `TASK-BCK-016`  | Replace canonical route re-exports                       | 2026-04-01                                 |
| `TASK-BCK-017`  | OpenSpec follow-up change creation support               | 2026-04-04                                 |
| `TASK-BCK-018`  | AUTH_BOOTSTRAP_ALLOW_FALLBACK_EMERGENCY config           | 2026-04-07                                 |
| `TASK-BCK-019`  | Prevent Clerk personal-tenant collisions                 | 2026-04-04                                 |
| `TASK-BCK-020`  | Reconcile document adapter contract quality issues       | 2026-05-08                                 |
| `TASK-BCK-021`  | Supabase RLS, composite indexes, pg_stat_statements      | 2026-04-03                                 |
| `TASK-BCK-022`  | Wire TriggerDocumentAnalysisUseCase to Celery            | 2026-04-05                                 |
| `TASK-BCK-023`  | Document update re-trigger flow                          | 2026-04-06                                 |
| `TASK-BCK-024`  | HITL workflow resume mechanism after approval            | 2026-04-06                                 |
| `TASK-BCK-025`  | Real notification delivery (email/Slack/webhook)         | 2026-04-06                                 |
| `TASK-BCK-026`  | Unify AlertGenerator with pipeline save_to_db_node       | 2026-04-06                                 |
| `TASK-BCK-027`  | Reconcile two orchestration systems (deleted unused)     | 2026-04-06                                 |
| `TASK-BCK-028`  | E2E tests for document→LangChain→alerts flow             | 2026-04-06                                 |
| `TASK-BCK-029`  | WBS API endpoint with nested set model                   | 2026-04-06                                 |
| `TASK-BCK-030`  | Authenticated test fixtures for HITL resume tests        | 2026-04-06                                 |
| `TASK-BCK-031`  | LangGraph checkpoint restoration for HITL resume         | 2026-04-06                                 |
| `TASK-BCK-032`  | Monitoring/metrics for workflow resumption               | 2026-04-21                                 |
| `TASK-BCK-033`  | HITL resume API in OpenAPI spec                          | 2026-04-21                                 |
| `TASK-BCK-035`  | Fix duplicate index in Alert model (DuplicateTableError) | 2026-04-06                                 |
| `TASK-BCK-036`  | Fix syntax error in monitoring.py:175                    | 2026-04-06                                 |
| `TASK-BCK-037`  | Update conftest.py for all security models               | 2026-04-06                                 |
| `TASK-BCK-038`  | Implement AIUsageLogORM with schema parity               | 2026-04-06                                 |
| `TASK-BCK-039`  | Gate 4 traceability: sync AuditLogORM                    | 2026-04-06                                 |
| `TASK-BCK-040`  | Ruff linting debt resolution (257→0 violations)          | 2026-05-08                                 |
| `TASK-BCK-041`  | Ruff ARG audit — tenant_id/user_id review                | 2026-05-08                                 |
| `TASK-BCK-042`  | DLQ admin endpoints (GET+POST /api/v1/admin/dlq)         | 2026-04-27                                 |
| `TASK-BCK-043`  | WBS integration tests relocated to tests/integration/    | 2026-04-21                                 |
| `TASK-BCK-044`  | Flaky SLA calculator test fixed with freezegun           | 2026-04-21                                 |
| `TASK-BCK-045`  | Railway alerts import crash (ModuleNotFoundError)        | 2026-04-10                                 |
| `TASK-BCK-046`  | Project status update contract fix                       | 2026-04-11                                 |
| `TASK-BCK-047`  | Document reprocess and status mapping fix                | 2026-04-11                                 |
| `TASK-BCK-048`  | Production alerts route + upload CORS parity             | 2026-04-11                                 |
| `TASK-BCK-049`  | Direct upload Clerk token + error CORS fix               | 2026-04-11                                 |
| `TASK-BCK-051`  | Production alerts/stakeholders 500 triage                | Blocked 2026-05-25 - production log access |
| `TASK-BCK-052`  | Analysis graph parallel state merge fix                  | 2026-05-17                                 |
| `TASK-BCK-053`  | Fresh analysis checkpoint isolation                      | 2026-05-17                                 |
| `TASK-BCK-054`  | Coherence tracing contract + fail-open telemetry         | 2026-05-17                                 |
| `TASK-BCK-055`  | Coherence structured extraction layer                    | 2026-05-17                                 |
| `TASK-BCK-056`  | AnthropicWrapper anonymizer API mismatch fix             | 2026-05-17                                 |
| `TASK-BCK-057`  | Category-targeted RAG retrieval (6-category SQL)         | 2026-05-17                                 |
| `TASK-BCK-058`  | DET-TIM-STATUS false positive guard                      | 2026-05-17                                 |
| `TASK-BCK-059`  | DET-TEC-SPEC / DET-QUA-\* category guards                | 2026-05-17                                 |
| `TASK-CE-F2-01` | LEGAL pilot extraction adapter                           | 2026-05-29                                 |
