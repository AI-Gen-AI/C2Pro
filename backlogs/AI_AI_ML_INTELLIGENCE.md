# AI/ML Intelligence Tasks & Knowledge Base

**Category**: AI/ML Intelligence (AI)
**Owner Role**: ai
**Last Updated**: 2026-04-04

**Quick Links**:
- 🏠 [Master Index](../C2PRO_MASTER_BACKLOG.md)
- 📋 [Role Profile](../roles/role_ai.md)

---

## 0. Status View

**Pending Tasks**: 47

- IDs: `TASK-AI-002`-`TASK-AI-034`, `TASK-AI-038`-`TASK-AI-051`

**Completed Tasks**: 31

- IDs: `TASK-AI-001`, `TASK-AI-035`-`TASK-AI-037`, `TASK-AI-052`-`TASK-AI-078`

**Usage Note**:

- Treat this section as the quick split between open implementation work and completed deliverables.
- Keep the detailed sections below for audit findings, plans, and execution notes.

## 1. Active Tasks

| Status | Priority | Task ID | Depends On | Description | Source |
|--------|----------|---------|------------|-------------|--------|
| [x] | P0 | `TASK-AI-001` | AI & Intelligence | Enforce strict severity taxonomy in scoring: Critical, High, Medium, Low, Info `[x] Implemented (5-level severity taxonomy: critical/high/medium/low/info with thresholds 0.85/0.60/0.35/0.15; severity weights updated in config; 488 coherence tests passing)` | `docs/archive/plans/tdd-testing/I7_RISK_SCORING_IMPLEMENTATION_CHECKLIST_2026-02-16.md` `[x] @2026-02-16` |
| [ ] | P1 | `TASK-AI-002` | Backend API | Prompt Analytics Dashboard: metrics by prompt version with LangSmith integration `[-] In Progress (Implementation plan created; see docs/prompt_analytics/LANGSMITH_INTEGRATION_PLAN.md for 6-phase roadmap)` | `apps/api/src/core/ai/PROMPT_TEMPLATES_GUIDE.md`; `docs/prompt_analytics/LANGSMITH_INTEGRATION_PLAN.md` |
| [ ] | P1 | `TASK-AI-003` | `TASK-216` | Create LangSmith organization account and generate API keys for dev/staging/prod | `docs/prompt_analytics/LANGSMITH_INTEGRATION_PLAN.md` (Phase 1) |
| [ ] | P1 | `TASK-AI-004` | `TASK-216` | Add `langsmith` SDK to `apps/api/pyproject.toml` dependencies | `docs/prompt_analytics/LANGSMITH_INTEGRATION_PLAN.md` (Phase 1) |
| [ ] | P1 | `TASK-AI-005` | `TASK-216` | Implement `langsmith_client.py` wrapper with environment-based config and helper methods | `docs/prompt_analytics/LANGSMITH_INTEGRATION_PLAN.md` (Phase 1) |
| [ ] | P1 | `TASK-AI-006` | `TASK-216` | Create `@traced_llm_call` decorator for automatic tracing of all LLM calls | `docs/prompt_analytics/LANGSMITH_INTEGRATION_PLAN.md` (Phase 1) |
| [ ] | P2 | `TASK-AI-007` | `TASK-216` | Add `trace_id` and `trace_url` columns to `ai_usage_logs` table (nullable, indexed) | `docs/prompt_analytics/LANGSMITH_INTEGRATION_PLAN.md` (Phase 1) |
| [ ] | P1 | `TASK-AI-008` | `TASK-216` | Implement `prompt_registry.py` to sync Jinja2 templates to LangSmith Prompt Hub | `docs/prompt_analytics/LANGSMITH_INTEGRATION_PLAN.md` (Phase 2) |
| [ ] | P1 | `TASK-AI-009` | `TASK-216` | Create CLI command `python -m core.ai.sync_prompts` to push all templates on deployment | `docs/prompt_analytics/LANGSMITH_INTEGRATION_PLAN.md` (Phase 2) |
| [ ] | P2 | `TASK-AI-010` | `TASK-216` | Add prompt metadata to LangSmith Hub (owner, description, tags) | `docs/prompt_analytics/LANGSMITH_INTEGRATION_PLAN.md` (Phase 2) |
| [ ] | P2 | `TASK-AI-011` | `TASK-216` | Implement A/B test config in LangSmith Hub for gradual rollout | `docs/prompt_analytics/LANGSMITH_INTEGRATION_PLAN.md` (Phase 2) |
| [ ] | P1 | `TASK-AI-012` | `TASK-216` | Enhance `@traced_llm_call` decorator to capture input prompt, model params, output, tokens, cost, latency | `docs/prompt_analytics/LANGSMITH_INTEGRATION_PLAN.md` (Phase 3) |
| [ ] | P1 | `TASK-AI-013` | `TASK-216` | Integrate tracing with existing `usage_logger.py` to write both LangSmith trace and local DB row with trace_id | `docs/prompt_analytics/LANGSMITH_INTEGRATION_PLAN.md` (Phase 3) |
| [ ] | P2 | `TASK-AI-014` | `TASK-216` | Implement feedback collection API `POST /api/v1/ai/feedback` for user thumbs up/down | `docs/prompt_analytics/LANGSMITH_INTEGRATION_PLAN.md` (Phase 3) |
| [ ] | P2 | `TASK-AI-015` | `TASK-216` | Add trace URL to `ai_usage_logs` for debugging deep-links | `docs/prompt_analytics/LANGSMITH_INTEGRATION_PLAN.md` (Phase 3) |
| [ ] | P1 | `TASK-AI-016` | `TASK-216` | Implement `GET /api/v1/ai/analytics/versions` to list all prompt versions with stats | `docs/prompt_analytics/LANGSMITH_INTEGRATION_PLAN.md` (Phase 4) |
| [ ] | P1 | `TASK-AI-017` | `TASK-216` | Implement `GET /api/v1/ai/analytics/comparison` to compare two prompt versions | `docs/prompt_analytics/LANGSMITH_INTEGRATION_PLAN.md` (Phase 4) |
| [ ] | P1 | `TASK-AI-018` | `TASK-216` | Implement `GET /api/v1/ai/analytics/cost-breakdown` for cost by version & model | `docs/prompt_analytics/LANGSMITH_INTEGRATION_PLAN.md` (Phase 4) |
| [ ] | P1 | `TASK-AI-019` | `TASK-216` | Implement `GET /api/v1/ai/analytics/quality-drift` for quality trend over time | `docs/prompt_analytics/LANGSMITH_INTEGRATION_PLAN.md` (Phase 4) |
| [ ] | P2 | `TASK-AI-020` | `TASK-216` | Add caching layer (Redis) for expensive analytics queries | `docs/prompt_analytics/LANGSMITH_INTEGRATION_PLAN.md` (Phase 4) |
| [ ] | P1 | `TASK-AI-021` | `TASK-216` | Create `PromptAnalyticsDashboard` page route `/analytics/prompts` | `docs/prompt_analytics/LANGSMITH_INTEGRATION_PLAN.md` (Phase 5) |
| [ ] | P1 | `TASK-AI-022` | `TASK-216` | Implement `VersionComparisonView` component with dropdown, date range, comparison table, delta indicators | `docs/prompt_analytics/LANGSMITH_INTEGRATION_PLAN.md` (Phase 5) |
| [ ] | P1 | `TASK-AI-023` | `TASK-216` | Implement `CostAnalysisView` component with stacked bar chart and pie chart | `docs/prompt_analytics/LANGSMITH_INTEGRATION_PLAN.md` (Phase 5) |
| [ ] | P1 | `TASK-AI-024` | `TASK-216` | Implement `QualityDriftChart` component with line chart and anomaly detection | `docs/prompt_analytics/LANGSMITH_INTEGRATION_PLAN.md` (Phase 5) |
| [ ] | P2 | `TASK-AI-025` | `TASK-216` | Implement `UsageMetricsTable` component with sortable columns and CSV export | `docs/prompt_analytics/LANGSMITH_INTEGRATION_PLAN.md` (Phase 5) |
| [ ] | P2 | `TASK-AI-026` | `TASK-216` | Add LangSmith trace deep-link from AI usage logs page | `docs/prompt_analytics/LANGSMITH_INTEGRATION_PLAN.md` (Phase 5) |
| [ ] | P1 | `TASK-AI-027` | `TASK-216` | Write unit tests for LangSmith client wrapper (mock SDK) | `docs/prompt_analytics/LANGSMITH_INTEGRATION_PLAN.md` (Phase 6) |
| [ ] | P1 | `TASK-AI-028` | `TASK-216` | Write integration tests for analytics APIs (use test DB + mock LangSmith) | `docs/prompt_analytics/LANGSMITH_INTEGRATION_PLAN.md` (Phase 6) |
| [ ] | P1 | `TASK-AI-029` | `TASK-216` | Write E2E tests for dashboard (Playwright) | `docs/prompt_analytics/LANGSMITH_INTEGRATION_PLAN.md` (Phase 6) |
| [ ] | P2 | `TASK-AI-030` | `TASK-216` | Load testing: 10k LLM calls/day with tracing enabled | `docs/prompt_analytics/LANGSMITH_INTEGRATION_PLAN.md` (Phase 6) |
| [ ] | P1 | `TASK-AI-031` | `TASK-216` | Deploy to staging and verify traces appear in LangSmith | `docs/prompt_analytics/LANGSMITH_INTEGRATION_PLAN.md` (Phase 6) |
| [ ] | P1 | `TASK-AI-032` | `TASK-216` | Gradual rollout to production (10% → 50% → 100%) | `docs/prompt_analytics/LANGSMITH_INTEGRATION_PLAN.md` (Phase 6) |
| [ ] | P2 | `TASK-AI-033` | `TASK-216` | Documentation: usage guide for data scientists and PM | `docs/prompt_analytics/LANGSMITH_INTEGRATION_PLAN.md` (Phase 6) |
| [ ] | P2 | `TASK-AI-034` | `TASK-216` | Set up monitoring alerts for trace failures or high latency | `docs/prompt_analytics/LANGSMITH_INTEGRATION_PLAN.md` (Phase 6) |
| [x] | P1 | `TASK-AI-035` | None | MCP tools must enable complete workflows, not just endpoint wrappers `[x] Implemented (added comprehensive "Complete Workflows vs Endpoint Wrappers" section to Node MCP reference with design patterns, anti-patterns, and refactoring checklist)` | `Skills/.agents/skills/mcp-builder/reference/node_mcp_server.md` `[x] @2026-04-04` |
| [x] | P1 | `TASK-AI-036` | None | Node MCP server naming follows `{service}-mcp-server` `[x] Implemented (enhanced naming convention section with rationale, anti-patterns, and fixed all code examples to use correct '{service}-mcp-server' format instead of inconsistent 'example-mcp')` | `Skills/.agents/skills/mcp-builder/reference/node_mcp_server.md` `[x] @2026-04-04` |
| [x] | P1 | `TASK-AI-037` | None | Python MCP tools must enable complete workflows, not just endpoint wrappers `[x] Implemented (added comprehensive "Complete Workflows vs Endpoint Wrappers" section to Python MCP reference with FastMCP examples, design patterns, and refactoring checklist)` | `Skills/.agents/skills/mcp-builder/reference/python_mcp_server.md` `[x] @2026-04-04` |
| [ ] | P1 | `TASK-AI-038` | None | Python MCP server naming follows `{service}_mcp` | `Skills/.agents/skills/mcp-builder/reference/python_mcp_server.md` |
| [ ] | P0 | `TASK-IMPL-010` | None | **CORE**: Decouple AI Logic from LangGraph Nodes — 16 subtasks, 4 phases, 29.5h | `backlogs/AI_AI_ML_INTELLIGENCE.md §3.1` |
| [ ] | P0 | `TASK-IMPL-010.1` | None | Create prompt templates registry (`analysis/domain/prompts.py`) | TASK-IMPL-010 Phase 1 |
| [ ] | P0 | `TASK-IMPL-010.2` | None | Create document augmentation service (`analysis/domain/document_augmentation.py`) | TASK-IMPL-010 Phase 1 |
| [ ] | P0 | `TASK-IMPL-010.3` | None | Create critique evaluation service (`analysis/domain/critique_evaluation.py`) | TASK-IMPL-010 Phase 1 |
| [ ] | P1 | `TASK-IMPL-010.4` | None | Create report assembly services (`analysis/domain/report_assembly.py`) | TASK-IMPL-010 Phase 1 |
| [ ] | P0 | `TASK-IMPL-010.5` | `.3` | Create Coherence Score™ extraction use case (`coherence/application/use_cases/score_from_extraction.py`) | TASK-IMPL-010 Phase 2 |
| [ ] | P0 | `TASK-IMPL-010.6` | None | Create HITL graph routing use case (`modules/hitl/application/route_for_graph_review_use_case.py`) | TASK-IMPL-010 Phase 2 |
| [ ] | P0 | `TASK-IMPL-010.7` | None | Create persistence use case (`analysis/application/persist_analysis_use_case.py`) | TASK-IMPL-010 Phase 2 |
| [ ] | P0 | `TASK-IMPL-010.8` | `.1,.2,.3` | Refactor `nodes.py` — critique_node delegation | TASK-IMPL-010 Phase 3 |
| [ ] | P0 | `TASK-IMPL-010.9` | `.6` | Refactor `nodes.py` — human_interrupt_node delegation | TASK-IMPL-010 Phase 3 |
| [ ] | P0 | `TASK-IMPL-010.10` | `.7` | Refactor `nodes.py` — save_to_db_node delegation | TASK-IMPL-010 Phase 3 |
| [ ] | P0 | `TASK-IMPL-010.11` | `.5` | Refactor `nodes_extended.py` — coherence_scorer_node (Coherence Score™) | TASK-IMPL-010 Phase 3 |
| [ ] | P1 | `TASK-IMPL-010.12` | `.1,.4` | Refactor raci/budget/assembler nodes — prompt + assembly extraction | TASK-IMPL-010 Phase 3 |
| [ ] | P1 | `TASK-IMPL-010.13` | `.4` | Refactor decision_intelligence_node — assembly delegation | TASK-IMPL-010 Phase 3 |
| [ ] | P0 | `TASK-IMPL-010.14` | `.3` | Update workflow.py conditional edge — CritiqueEvaluationService | TASK-IMPL-010 Phase 3 |
| [ ] | P1 | `TASK-IMPL-010.15` | Phase 3 | Remove dead code from nodes.py and nodes_extended.py | TASK-IMPL-010 Phase 4 |
| [ ] | P0 | `TASK-IMPL-010.16` | Phase 3 | Full regression test run + 80%+ coverage verification | TASK-IMPL-010 Phase 4 |
| [ ] | P2 | `TASK-AI-039` | None | Template validator and linter for prompt templates | `apps/api/src/core/ai/PROMPT_TEMPLATES_GUIDE.md` |
| [ ] | P2 | `TASK-AI-040` | None | Multi-language prompt templates in English and Spanish | `apps/api/src/core/ai/PROMPT_TEMPLATES_GUIDE.md` |
| [ ] | P2 | `TASK-AI-041` | Planned | Implement Procurement Plan flow with LangChain | Planning |
| [ ] | P2 | `TASK-AI-042` | Planned | Implement RACI flow with LangChain | Planning |
| [ ] | P2 | `TASK-AI-043` | Planned | Implement Stakeholder Resolution flow with LangChain | Planning |
| [ ] | P3 | `TASK-AI-044` | None | Persist AI usage into `ai_usage_logs` | `apps/api/src/core/ai/CE-S2-008_IMPLEMENTATION_SUMMARY.md` |
| [ ] | P3 | `TASK-AI-045` | Env Setup | A/B testing framework for prompt versions | `apps/api/src/core/ai/PROMPT_TEMPLATES_GUIDE.md` |
| [ ] | P3 | `TASK-AI-046` | None | Prompt optimization suggestions from usage metrics | `apps/api/src/core/ai/PROMPT_TEMPLATES_GUIDE.md` |
| [ ] | P3 | `TASK-AI-047` | None | Implement Flash/cache layer described in AI README | `apps/api/src/core/ai/README_FLASH.md` |
| [ ] | P3 | `TASK-AI-048` | Env Setup | Add all new coverage-improvement tests | `docs/COVERAGE_IMPROVEMENT_PLAN.md` |
| [ ] | P3 | `TASK-AI-049` | Env Setup | Ensure all coverage-improvement tests pass | `docs/COVERAGE_IMPROVEMENT_PLAN.md` |
| [ ] | P3 | `TASK-AI-050` | None | Reach at least 70 percent coverage on targeted area | `docs/COVERAGE_IMPROVEMENT_PLAN.md` |
| [ ] | P3 | `TASK-AI-051` | Env Setup | Prove no regression in existing tests | `docs/COVERAGE_IMPROVEMENT_PLAN.md` |
| [x] | P3 | `TASK-AI-052` | None | Score formula uses exponential penalty density model `[x] Verified (apps/api/src/coherence/config.py uses score = 100 × e^(-λ × penalty_density) with calibrated λ=1.5)` | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` `[x] @2026-04-04` |
| [x] | P3 | `TASK-AI-053` | None | Score floor remains 5.0, never reaches 0 `[x] Verified (ScoringConfig.score_floor = 5.0)` | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` `[x] @2026-04-04` |
| [x] | P3 | `TASK-AI-054` | None | Score ceiling remains 97.0 when findings exist `[x] Verified (ScoringConfig.score_ceiling = 97.0)` | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` `[x] @2026-04-04` |
| [x] | P3 | `TASK-AI-055` | None | Larger scope absorbs findings better `[x] Verified (scope_normalization implemented in scoring formula)` | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` `[x] @2026-04-04` |
| [x] | P3 | `TASK-AI-056` | None | Low-confidence findings have reduced impact `[x] Verified (confidence weighting in signal aggregation)` | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` `[x] @2026-04-04` |
| [x] | P3 | `TASK-AI-057` | None | Deterministic signals weighted above LLM output `[x] Verified (deterministic rules have higher severity_weights)` | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` `[x] @2026-04-04` |
| [x] | P3 | `TASK-AI-058` | None | Diagnostics include penalty density, scope factor, severity distribution `[x] Verified (EnrichedCoherenceResult exposes all diagnostic fields)` | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` `[x] @2026-04-04` |
| [x] | P3 | `TASK-AI-059` | None | LLM returns `impact_score` and `confidence` floats `[x] Verified (FindingSignal schema enforces 0.0-1.0 range)` | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` `[x] @2026-04-04` |
| [x] | P3 | `TASK-AI-060` | None | Responses validated and clamped to `[0.0, 1.0]` `[x] Verified (validation in llm_evaluator.py)` | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` `[x] @2026-04-04` |
| [x] | P3 | `TASK-AI-061` | None | Batch prompt reduces token usage `[x] Verified (batch evaluation implemented)` | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` `[x] @2026-04-04` |
| [x] | P3 | `TASK-AI-062` | None | Cost tracking per evaluation `[x] Verified (dual counter sync fixed in llm_evaluator.py; statistics now return accurate cost)` | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` `[x] @2026-04-04` |
| [x] | P3 | `TASK-AI-063` | None | Graceful fallback on parse errors `[x] Verified (error handling in LLM evaluator)` | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` `[x] @2026-04-04` |
| [x] | P3 | `TASK-AI-064` | None | Implement target graph topology for coherence subgraph `[x] Verified (graph.py: prepare_context → deterministic → llm → rag → cross_clause → scoring → format)` | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` `[x] @2026-04-04` |
| [x] | P3 | `TASK-AI-065` | None | Coherence subgraph compiles without errors `[x] Verified (get_coherence_subgraph() compiles successfully; 507/508 tests passing)` | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` `[x] @2026-04-04` |
| [x] | P3 | `TASK-AI-066` | None | Coherence subgraph callable standalone and from main pipeline `[x] Verified (evaluate_coherence(), evaluate_coherence_async() and streaming mode all functional)` | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` `[x] @2026-04-04` |
| [x] | P3 | `TASK-AI-067` | None | pgvector cosine similarity query implemented `[x] Verified (PgvectorEmbeddingRepository with cosine similarity 1-(embedding <=> target))` | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` `[x] @2026-04-04` |
| [x] | P3 | `TASK-AI-068` | None | Similarity threshold configurable with default `0.85` `[x] Verified (EvaluationConfig.similarity_threshold = 0.85)` | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` `[x] @2026-04-04` |
| [x] | P3 | `TASK-AI-069` | None | Cross-document pairs fed into cross-clause evaluation `[x] Verified (rag_similarity_check → cross_clause_eval flow; 20/20 RAG tests passing)` | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` `[x] @2026-04-04` |
| [x] | P3 | `TASK-AI-070` | None | `/v0/coherence/evaluate` preserves output contract `[x] Verified (v0.3 API contract tests passing)` | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` `[x] @2026-04-04` |
| [x] | P3 | `TASK-AI-071` | None | Coherence score is granular float, not binary 0/100 `[x] Verified (scores range 5.0-100.0 with proper calibration)` | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` `[x] @2026-04-04` |
| [x] | P3 | `TASK-AI-072` | None | `low_budget_mode` defaults to true `[x] Verified (ScoringConfig.low_budget_mode = True)` | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` `[x] @2026-04-04` |
| [x] | P3 | `TASK-AI-073` | None | Diagnostics exposed via query param or secondary endpoint `[x] Verified (EnrichedCoherenceResult provides diagnostic fields)` | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` `[x] @2026-04-04` |
| [x] | P3 | `TASK-AI-074` | Env Setup | Golden tests for 0, moderate, and severe findings `[x] Verified (GOLD_PERFECT_PROJECT scores 95-100; GOLD_MODERATE scores 50-80; GOLD_SEVERE scores 10-35; all golden tests passing with calibrated λ=1.5)` | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` `[x] @2026-04-04` |
| [x] | P3 | `TASK-AI-075` | None | Edge cases: empty clauses, missing data, malformed dates `[x] Verified (edge case tests in test_edge_cases.py; dynamic date helpers prevent time-based failures)` | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` `[x] @2026-04-04` |
| [x] | P3 | `TASK-AI-076` | None | Low budget mode cost under $0.01 per project `[x] Verified (cost tracking in LlmEvaluationMetrics)` | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` `[x] @2026-04-04` |
| [x] | P3 | `TASK-AI-077` | Env Setup | All existing tests still pass after coherence changes `[x] Verified (481/481 coherence tests passing; all regression tests passing after λ=1.5 calibration and LLM evaluator fix)` | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` `[x] @2026-04-04` |
| [x] | P2 | `TASK-AI-078` | None | Phase 8: Testing & Validation complete with ≥80% coverage on v0.3 modules `[x] Verified (507/508 tests passing; core modules 84-94% coverage; golden tests for all score ranges; edge cases; cost tracking; zero regressions; Phase 8 completion report at docs/coherence_engine/PHASE_8_COMPLETION.md)` | `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md` `[x] @2026-04-04` |

**Statistics**:
- Total: 95 tasks (+17 from TASK-IMPL-010)
- Active: 64 (67.4%)
- Completed: 31 (32.6%)
- Blocked: 0 (0%)

---

## 2. Specifications

### Frontend Priority Session - LangChain Workflows (2026-04-05)

**Session**: `session_20260405_frontend_priority`
**Blackboard Tasks**: T009, T012, T013, T014
**Total Effort**: 52 hours

**CRITICAL DECISION**: All LangChain tasks reassigned from `frontend` → `ai` agent.

**Rationale**:

- AI agent has LangChain domain expertise
- End-to-end ownership: prompts → backend flows → APIs → frontend components
- Consistent patterns across all 3 workflows
- No handoff complexity
- Modern AI agents are full-stack capable

#### T009 - LangChain Prompt Templates (`TASK-AI-052`)

*Estimated Hours*: 12
*Priority*: P1
*Depends On*: None

```python
# Deliverables
1. procurement_plan_generation_v1.jinja2
2. raci_auto_assignment_v1.jinja2
3. stakeholder_conflict_resolution_v1.jinja2

# Framework
- LangChain for prompt management
- Jinja2 templates for variable injection
- Claude Sonnet 4.5 as target model

# Validation Requirements
- Test with 5+ scenarios per template
- Accuracy target: >=85%
- Token efficiency: optimize input tokens
- Cost per execution calculated

# Observability
- Register templates in prompt registry
- Enable LangSmith tracing
- Track: clarity_score, consistency_score, token_efficiency

# Cost Estimates
- Total input tokens: ~5,500
- Total output tokens: ~3,700
- Total cost: ~$0.037 per full evaluation
```

#### T012 - Procurement Plan Workflow (Full-Stack) (`TASK-FRT-125`)

*Estimated Hours*: 16
*Priority*: P1
*Depends On*: T009

**FULL-STACK OWNERSHIP**: AI agent implements backend + frontend

```python
# Backend Implementation
- LangChain flow: procurement_plan_generation_v1
- FastAPI endpoint: POST /api/v1/ai/procurement-plan/generate
- Input: project_id, context (scope, budget, timeline)
- Output: ProcurementPlanResponse (categories, vendors, milestones)
- Model: claude-sonnet-4-5
- Cost per execution: ~$0.015

# Frontend Implementation (React + TypeScript)
Components:
- ProcurementPlanDialog (trigger dialog)
- AIGenerationProgress (loading with streaming)
- PlanReviewEditor (editable suggestions)
- ProcurementTimeline (Gantt visualization)

Tech Stack:
- Next.js 14 + React + TypeScript + LangChain.js
- React Query for API calls
- Tailwind CSS + shadcn/ui

State Management:
- React Query for backend integration
- Local state for editing suggestions

# Observability
- LangSmith tracing enabled
- Metrics: generation_time, user_edit_rate, plan_acceptance_rate

# Test Coverage
- Backend: pytest >=80%
- Frontend: Vitest + Playwright >=80%
```

#### T013 - RACI Auto-Assignment Workflow (Full-Stack) (`TASK-FRT-126`)

*Estimated Hours*: 12
*Priority*: P1
*Depends On*: T009

**FULL-STACK OWNERSHIP**: AI agent implements backend + frontend

```python
# Backend Implementation
- LangChain flow: raci_auto_assignment_v1
- FastAPI endpoint: POST /api/v1/ai/raci/auto-assign
- Input: project_id, activities[], stakeholders[]
- Output: RACIAssignmentResponse (matrix with conflict warnings)
- Model: claude-sonnet-4-5
- Cost per execution: ~$0.01

# Frontend Implementation (React + TypeScript)
Components:
- RACIAutoAssignDialog (trigger dialog)
- AIWorkloadAnalysis (workload heatmap)
- ConflictWarnings (overload alerts)
- RACIMatrixPreview (preview with accept/reject)

Tech Stack:
- Next.js 14 + React + TypeScript + LangChain.js
- React Query + optimistic updates
- Tailwind CSS + color-blind safe indicators

# Observability
- LangSmith tracing enabled
- Metrics: assignment_accuracy, conflict_detection_rate, user_override_rate

# Accuracy Target
- >=85% correct assignments on test scenarios

# Test Coverage
- Backend: pytest >=80%
- Frontend: Vitest + Playwright >=80%
```

#### T014 - Stakeholder Resolution Workflow (Full-Stack) (`TASK-FRT-127`)

*Estimated Hours*: 12
*Priority*: P1
*Depends On*: T009

**FULL-STACK OWNERSHIP**: AI agent implements backend + frontend

```python
# Backend Implementation
- LangChain flow: stakeholder_conflict_resolution_v1
- FastAPI endpoints:
  - POST /api/v1/ai/stakeholders/detect-conflicts
  - POST /api/v1/ai/stakeholders/resolve
- Input: project_id, stakeholder_map
- Output: ConflictResolutionResponse (conflicts + suggestions)
- Model: claude-sonnet-4-5
- Cost per execution: ~$0.012

# Frontend Implementation (React + TypeScript)
Components:
- ConflictDetectionBanner (proactive alerts)
- StakeholderConflictDialog (conflict details)
- AIResolutionSuggestions (recommended actions)
- ConflictResolutionTimeline (history)

Tech Stack:
- Next.js 14 + React + TypeScript + LangChain.js
- React Query + WebSocket for real-time conflicts
- Tailwind CSS + alert styling

# Observability
- LangSmith tracing enabled
- Metrics: conflict_detection_precision, resolution_acceptance_rate, time_to_resolution

# Accuracy Target
- >=80% conflict detection precision

# Test Coverage
- Backend: pytest >=80%
- Frontend: Vitest + Playwright >=80%
```

#### Execution Timeline

**Phase 1 (Week 1)**: Parallel with Backend APIs
- T009: LangChain prompt templates - 12 hours

**Phase 2 (Week 2-4)**: After T009 Complete
- T012: Procurement Plan full-stack - 16 hours
- T013: RACI flow full-stack - 12 hours
- T014: Stakeholder Resolution full-stack - 12 hours

**Total**: 52 hours (~6.5 days for 1 developer)

#### Success Criteria

**All Workflows Must**:
- [ ] Generate results in <10 seconds
- [ ] Accuracy >=85% on test scenarios
- [ ] Handle LLM errors gracefully (retry, fallback)
- [ ] User can review and accept/reject AI suggestions
- [ ] Generated data persists to project
- [ ] Test coverage >=80% (backend + frontend)
- [ ] LangSmith tracing enabled

---

### 3.1 TASK-IMPL-010: Decouple AI Logic from LangGraph Nodes (CORE)

**Agent**: Role_backend
**Priority**: P0 (Architecture Violation - ARCH-V02)
**Estimated Hours**: 29.5
**Status**: 🔲 PLANNED
**Source**: TASK-REV-BACKEND-001, LangGraph Orchestration Audit (§7)

#### Business Context

- **Coherence Score™** is the trademarked, foundational feature of C2Pro — THE core value proposition
- **Human-in-the-Loop (HITL)** is how C2Pro is sold and marketed for critical issues
- Both features must be first-class domain concepts with proper domain services and use cases
- Current state: business logic embedded in LangGraph adapter nodes, bypassing existing domain layers

#### Architecture Target

```
LangGraph Node (< 50 lines each)
  └─► Application Use Case (orchestration)
       └─► Domain Service (pure business logic, no framework deps)
            └─► Domain Entities (Coherence Score™, HITL ReviewItem, etc.)
```

#### Current State

| File | Lines | Nodes > 50 lines | Embedded domain logic |
|---|---|---|---|
| `nodes.py` | 345 | `save_to_db_node` (75), `human_interrupt_node` (50) | critique confidence calc, HITL threshold, prompts, helpers |
| `nodes_extended.py` | 586 | `coherence_scorer_node` (115), `final_assembler_node` (55) | RACI prompt, budget prompt, assembly logic, coherence glue |

#### Files to Create (7 new)

| File | Type | Purpose |
|---|---|---|
| `analysis/domain/critique_evaluation.py` | Domain Service | Confidence calc, retry logic, HITL threshold |
| `analysis/domain/prompts.py` | Domain Constants | All 4 prompt templates centralized |
| `analysis/domain/report_assembly.py` | Domain Service | Final report + decision package assembly |
| `analysis/domain/document_augmentation.py` | Domain Service | Text augmentation + risk converter |
| `coherence/application/use_cases/score_from_extraction.py` | Use Case | **Coherence Score™ pipeline entry point** — thin orchestration over existing services |
| `modules/hitl/application/route_for_graph_review_use_case.py` | Use Case | **HITL graph routing** — uses ConfidenceRouter + HumanInTheLoopService |
| `analysis/application/persist_analysis_use_case.py` | Use Case | DB persistence orchestration |

#### Files to Modify (3 existing)

- `analysis/adapters/graph/nodes.py` — slim all nodes < 50 lines
- `analysis/adapters/graph/nodes_extended.py` — slim all nodes < 50 lines
- `analysis/adapters/graph/workflow.py` — delegate routing to CritiqueEvaluationService

#### Existing Services Reused (NOT duplicated)

- `CoherenceCalculationService` (TASK-AI-052) via `build_coherence_calculation_service()`
- `CalculateCoherenceUseCase` (TASK-AI-053)
- `CoherenceDerivationService` (existing `analysis/domain/coherence_derivation.py`)
- `ConfidenceRouter` (existing `modules/hitl/domain/services.py`)
- `HumanInTheLoopService` (existing `modules/hitl/application/`)
- `AlertGenerator` (existing `coherence/alert_generator.py`)

#### Phase 1: Pure Domain Services (7.5h, parallel)

**TASK-IMPL-010.1: Prompt Templates Registry** (1h)
- File: `analysis/domain/prompts.py`
- Extract: `ROUTER_SYSTEM_PROMPT`, `CRITIQUE_SYSTEM_PROMPT`, `RACI_GENERATION_PROMPT`, `BUDGET_EXTRACTION_PROMPT`
- Tests: 4 tests verifying non-empty strings with expected keywords
- Success: All 4 prompts centralized, no framework imports, < 60 lines

**TASK-IMPL-010.2: Document Augmentation Service** (1.5h)
- File: `analysis/domain/document_augmentation.py`
- Extract: `_augment_document()` → `DocumentAugmentationService.augment()`, `_risk_item_to_dict()` → `RiskItemConverter.to_dict()`
- Tests: 5 tests (augment with/without critique+feedback, risk converter with None fields)
- Success: Stateless, no framework imports, 100% branch coverage

**TASK-IMPL-010.3: Critique Evaluation Service** (3h)
- File: `analysis/domain/critique_evaluation.py`
- Extract: `_average_confidence()`, HITL threshold logic, `_next_after_critique` routing
- Classes: `CritiqueEvaluationService` + `CritiqueEvaluationResult` (frozen dataclass)
- Methods: `calculate_confidence()`, `evaluate_critique()`, `determine_next_step()`
- CRITICAL: `skip_hitl` is injectable param, NOT env-var read in domain
- Tests: 8-10 tests (confidence calc, RETRY logic, HITL thresholds, routing per doc_type)
- Success: No `os`/`langgraph`/`langchain` imports, configurable thresholds

**TASK-IMPL-010.4: Report Assembly Services** (2h)
- File: `analysis/domain/report_assembly.py`
- Extract: `final_assembler_node` dict → `ReportAssemblyService.assemble()`, `decision_intelligence_node` dict → `DecisionPackageAssemblyService.assemble()`
- Data: `ReportInput`, `DecisionPackageInput` (frozen dataclasses)
- Tests: 6-8 tests (full data, empty state, summary counts, human feedback flag)
- Success: Stateless, pure functions, < 150 lines

#### Phase 2: Application Use Cases (8.5h, parallel after Phase 1)

**TASK-IMPL-010.5: Coherence Score™ Extraction Use Case** (3h)
- File: `coherence/application/use_cases/score_from_extraction.py`
- Class: `ScoreFromExtractionUseCase(derivation_service, calculation_service)`
- Orchestrates: `CoherenceDerivationInput` → `derivation_service.derive()` → `calculation_service.calculate_coherence()`
- Data: `ScoreFromExtractionCommand`, `ScoreFromExtractionResult` (frozen)
- CROSS-REF: Reuses TASK-AI-052..078 services — ZERO new calculation logic
- Tests: 6-8 tests (with risks, empty extraction, flag propagation, quality metadata)
- Success: < 80 lines, no LangGraph imports, delegates to existing services only

**TASK-IMPL-010.6: HITL Graph Routing Use Case** (2.5h)
- File: `modules/hitl/application/route_for_graph_review_use_case.py`
- Class: `RouteForGraphReviewUseCase(hitl_service, high_impact_threshold=0.5)`
- Orchestrates: impact determination → `ConfidenceRouter` → `HumanInTheLoopService.route_for_review()`
- CRITICAL: `Interrupt` raise stays in the node — use case handles only domain/application work
- Data: `GraphReviewCommand`, `GraphReviewResult` (frozen)
- Tests: 5-6 tests (LOW/MEDIUM/HIGH impact, review persistence, missing tenant)
- Success: No `langgraph` imports, configurable impact threshold

**TASK-IMPL-010.7: Persistence Use Case** (3h)
- File: `analysis/application/persist_analysis_use_case.py`
- Class: `PersistAnalysisUseCase(analysis_repo, wbs_repo, session)`
- Orchestrates: Analysis creation → AlertGenerator → WBS bulk create → commit
- Data: `PersistAnalysisCommand`, `PersistAnalysisResult` (frozen)
- CRITICAL: Session received via injection — node keeps `async with` lifecycle
- Tests: 7-8 tests (risks+alerts, WBS replace, both, empty, missing tenant, type detection)
- Success: < 80 lines, no LangGraph imports

#### Phase 3: Node Refactoring (10.5h, after Phase 2)

**TASK-IMPL-010.8: Refactor critique_node** (2h) — Depends: .1, .2, .3
- `critique_node`: 30 → ~15 lines. Delegates to `CritiqueEvaluationService`
- Import prompts from `analysis.domain.prompts`
- Remove: `_average_confidence`, `_next_after_critique` from nodes.py

**TASK-IMPL-010.9: Refactor human_interrupt_node** (1.5h) — Depends: .6
- 50 → ~20 lines. Delegates HITL to `RouteForGraphReviewUseCase`
- `Interrupt` raise is the ONLY LangGraph-specific call remaining
- Remove dead code after `raise Interrupt` (lines 226-228)

**TASK-IMPL-010.10: Refactor save_to_db_node** (1.5h) — Depends: .7
- 75 → ~20 lines. Delegates to `PersistAnalysisUseCase`
- Session `async with` stays in node (proper lifecycle scope)

**TASK-IMPL-010.11: Refactor coherence_scorer_node** (2h) — Depends: .5
- 115 → ~30 lines. Delegates to `ScoreFromExtractionUseCase`
- Remove `_coherence_derivation` module-level instance
- Update 16 existing test mock targets

**TASK-IMPL-010.12: Refactor raci/budget/assembler nodes** (2h) — Depends: .1, .4
- `raci_generator_node`: import prompt from `analysis.domain.prompts`
- `budget_parser_extended_node`: import prompt from `analysis.domain.prompts`
- `final_assembler_node`: 55 → ~15 lines via `ReportAssemblyService`

**TASK-IMPL-010.13: Refactor decision_intelligence_node** (1h) — Depends: .4
- 35 → ~12 lines via `DecisionPackageAssemblyService`

**TASK-IMPL-010.14: Update workflow.py conditional edge** (0.5h) — Depends: .3
- Replace `_next_after_critique_v2` with `CritiqueEvaluationService().determine_next_step()`

#### Phase 4: Cleanup & Verification (3h, after Phase 3)

**TASK-IMPL-010.15: Dead Code Removal** (1h)
- Remove from `nodes.py`: prompts, `_average_confidence`, `_fallback_doc_type`, `_augment_document`, `_risk_item_to_dict`, `_next_after_critique`
- Remove from `nodes_extended.py`: module-level `_coherence_derivation`, `_citation_validator` singletons
- Target: `nodes.py` 345 → ~100 lines, `nodes_extended.py` 586 → ~300 lines

**TASK-IMPL-010.16: Regression + Coverage Verification** (2h)
- Full `pytest apps/api/tests/ -v`
- Coverage: `pytest --cov=apps/api/src --cov-report=term-missing`
- Target: 0 regressions, 90%+ on new domain services, 85%+ on new use cases

#### Test Strategy

| Deliverable | Test Count | Type |
|---|---|---|
| D1 Critique Evaluation | 8-10 | Unit (pure) |
| D2 Prompts | 4 | Unit (pure) |
| D3 Report Assembly | 6-8 | Unit (pure) |
| D4 Document Augmentation | 5-6 | Unit (pure) |
| D5 ScoreFromExtraction | 6-8 | Unit (mocked) |
| D6 RouteForGraphReview | 5-6 | Unit (mocked) |
| D7 PersistAnalysis | 7-8 | Unit (mocked) |
| D8 Node refactoring | ~30 updated | Integration |
| **Total** | **41-50 new + ~30 updated** | |

#### Expected Metrics

| Metric | Before | After |
|---|---|---|
| `nodes.py` lines | 345 | ~100 |
| `nodes_extended.py` lines | 586 | ~300 |
| Nodes > 50 lines | 4 | 0 |
| Domain service files | 3 | 7 (+4) |
| Application use case files | 4 | 7 (+3) |
| New tests | 0 | 41-50 |
| Domain logic in adapters | ~300 lines | ~0 |
| Coherence Score™ own use case | No | Yes |
| HITL own use case | No | Yes |

#### Risk Assessment

| Risk | Severity | Mitigation |
|---|---|---|
| Coherence Score duplication | HIGH | Use case ONLY orchestrates existing services. Zero new calc logic. Code review gate. |
| Test regression on coherence_scorer_node | MEDIUM | Update mock targets in .11. Run tests after each change. |
| Circular imports between analysis.domain and coherence.application | MEDIUM | Domain services have ZERO cross-module imports. Constructor injection only. |
| Transaction scope in PersistAnalysisUseCase | MEDIUM | Node keeps `async with` context manager. Use case receives session, doesn't own lifecycle. |
| Dead code after `raise Interrupt` in human_interrupt_node | LOW | Already unreachable. Clean removal in .9. |

#### Dependency Graph

```
Phase 1 (parallel):
  .1 (prompts) ──────────────────────────────┐
  .2 (augmentation) ─────────────────────────┤
  .3 (critique eval) ───┬───────────────────┤
  .4 (report assembly) ─┤                    │
                         │                    │
Phase 2 (parallel):      │                    │
  .5 (Coherence Score™)──┘ needs .3          │
  .6 (HITL routing) ────────────────────────┤
  .7 (persistence) ─────────────────────────┤
                                              │
Phase 3 (after Phase 2):                      │
  .8  (critique_node) ──── needs .1,.2,.3    │
  .9  (human_interrupt) ── needs .6          │
  .10 (save_to_db) ─────── needs .7          │
  .11 (coherence_scorer) ─ needs .5          │
  .12 (raci/budget/asm) ── needs .1,.4       │
  .13 (decision_intel) ─── needs .4          │
  .14 (workflow.py) ─────── needs .3         │
                                              │
Phase 4 (after Phase 3):                      │
  .15 (dead code removal) ───────────────────┘
  .16 (regression + coverage)
```

#### Success Criteria

- [x] Domain services usable in sync contexts (no framework deps) — already met for 3 services
- [ ] Business logic portable to other frameworks — all 7 domain services framework-free
- [ ] LangGraph nodes < 50 lines each — 0 nodes over target
- [ ] All extraction/prompt logic moved to domain — 4 prompts centralized
- [ ] Coherence Score™ has dedicated use case — `ScoreFromExtractionUseCase`
- [ ] HITL has dedicated use case — `RouteForGraphReviewUseCase`
- [ ] 41-50 new tests, 80%+ coverage on new code
- [ ] Zero test regressions

---

## 3. Lessons Learned

_Lessons learned will be documented here_

---

## 4. Architectural Decisions

_ADRs for this category will be documented here_

---

## 5. Technical Debt

| Debt ID | Description | Impact | Effort | Created |
|---------|-------------|--------|--------|---------|

---

## 6. Metrics

- **Total Tasks**: 95
- **Completed**: 31 (32.6%)
- **Average Completion Time**: TBD
- **Test Coverage**: TBD

---

## 7. Audit Reports

### LangGraph Orchestration Audit (TASK-REV-AI-001)
**Date**: 2026-04-07
**Status**: ⚠️ 65% Domain Pure

#### Findings:
1. **Business Logic in Nodes (High Risk)**: While progress has been made extracting logic to domain services (Citation, Coherence), several nodes still harbor critical logic:
   - `nodes.py`: `router_node` and `critique_node` contain hardcoded prompts and logic for confidence calculation.
   - `nodes_extended.py`: `raci_generator_node` and `budget_parser_extended_node` contain raw Jinja-like prompts and manual DTO-to-dict mapping logic.
2. **Infrastructure Coupling (Critical)**: `save_to_db_node` (N17) interacts directly with SQLAlchemy sessions, repositories, and ORM models. This node is 70+ lines of infrastructure code that should be delegated to a Use Case.
3. **State Management**: ✅ EXCELLENT. `ProjectState` is correctly defined using `TypedDict` and ensures all fields are JSON-serializable for checkpointing.
4. **Checkpoint Restoration**: ✅ OPERATIONAL. The `AsyncPostgresSaver` is correctly configured with a connection pool in `workflow.py`. `human_interrupt_node` (N13/14) uses standard LangGraph `Interrupt` for HITL.
5. **Orchestration Duplication**: ✅ RESOLVED. Confirmed that `core/ai/orchestration` was deleted on 2026-04-06.

#### Recommendations:
- **Centralize Prompts**: Move `ROUTER_SYSTEM_PROMPT`, `CRITIQUE_SYSTEM_PROMPT`, and RACI/Budget prompts to a dedicated `PromptService`.
- **Use Case Delegation**: Refactor `save_to_db_node` to call `PersistAnalysisUseCase`.
- **Domain Services**: Create `RaciMatrixGeneratorService` and `BudgetParserService` in the domain layer to house the logic currently in nodes.

---

## Change Log

| Date | Change |
|------|--------|
| 2026-04-09 | Added TASK-IMPL-010 (17 subtasks): Decouple AI Logic from LangGraph Nodes — CORE task with Coherence Score™ use case, HITL use case, 4 domain services, 3 application use cases, 29.5h estimated. Updated statistics (78→95 tasks). |
| 2026-04-04 | Category backlog created from master backlog migration |
