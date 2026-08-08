# AI/ML Intelligence Tasks & Knowledge Base

**Category**: AI/ML Intelligence (AI)
**Owner Role**: ai
**Last Updated**: 2026-05-09

**Quick Links**:
- 🏠 [Master Index](../C2PRO_MASTER_BACKLOG.md)
- 📋 [Role Profile](../roles/role_ai.md)

---

## 0. Status View

**Pending Tasks**: 6

- Blocked (human access required): `TASK-AI-010`, `TASK-AI-011` (LangSmith Hub dashboard)
- Deferred Phase 2: `TASK-AI-040`..`TASK-AI-043`, `TASK-AI-049` (LangChain flows, including intelligent WBS proposal design)

**Completed Tasks**: 94 (94%) — see COMPLETED.md

**Usage Note**:

- Treat this section as the quick split between open implementation work and completed deliverables.
- Keep the detailed sections below for audit findings, plans, and execution notes.

## 1. Active Tasks

| Status | Priority | Task ID | Depends On | Description | Source |
|--------|----------|---------|------------|-------------|--------|
| [ ] | P2 | `TASK-AI-010` | `TASK-216` | Add prompt metadata to LangSmith Hub (owner, description, tags) | `docs/prompt_analytics/LANGSMITH_INTEGRATION_PLAN.md` (Phase 2) |
| [ ] | P2 | `TASK-AI-011` | `TASK-216` | Implement A/B test config in LangSmith Hub for gradual rollout | `docs/prompt_analytics/LANGSMITH_INTEGRATION_PLAN.md` (Phase 2) |
| [ ] | P2 | `TASK-AI-040` | None | [PHASE 2 DEFERRED] Multi-language prompt templates in English and Spanish | `apps/api/src/core/ai/PROMPT_TEMPLATES_GUIDE.md` |
| [ ] | P2 | `TASK-AI-041` | Planned | [PHASE 2 DEFERRED] Implement Procurement Plan flow with LangChain | Planning |
| [ ] | P2 | `TASK-AI-042` | Planned | [PHASE 2 DEFERRED] Implement RACI flow with LangChain | Planning |
| [ ] | P2 | `TASK-AI-043` | Planned | [PHASE 2 DEFERRED] Implement Stakeholder Resolution flow with LangChain | Planning |
| [ ] | P2 | `TASK-AI-049` | `TASK-BCK-060`, completed Swagger flow audit | [PHASE 2 DEFERRED] Draft intelligent WBS proposal: LLM-assisted generation/review contract with evidence, hierarchy validation, uncertainty, and HITL approval gates | Swagger verification / user direction 2026-05-17 |

**Statistics**:
- Total: 100 tasks
- Active: 7 (7%) — TASK-AI-010/011 (human access), TASK-AI-040..043 + TASK-AI-049 (Phase 2)
- Completed: 94 (94%)
- Blocked: 2 (TASK-AI-010/011 — human dashboard access required)

---

## 2. Specifications

### Frontend Priority Session - LangChain Workflows (Phase 2 Reference)

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

#### T009 - LangChain Prompt Templates (`TASK-AI-040`)

*Estimated Hours*: 12
*Priority*: P2 (Phase 2)
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

#### T012 - Procurement Plan Workflow (Full-Stack) (`TASK-AI-041`)

*Estimated Hours*: 16
*Priority*: P2 (Phase 2)
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

# Observability
- LangSmith tracing enabled
- Metrics: generation_time, user_edit_rate, plan_acceptance_rate

# Test Coverage
- Backend: pytest >=80%
- Frontend: Vitest + Playwright >=80%
```

#### T013 - RACI Auto-Assignment Workflow (Full-Stack) (`TASK-AI-042`)

*Estimated Hours*: 12
*Priority*: P2 (Phase 2)
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

# Observability
- LangSmith tracing enabled
- Metrics: assignment_accuracy, conflict_detection_rate, user_override_rate

# Accuracy Target
- >=85% correct assignments on test scenarios

# Test Coverage
- Backend: pytest >=80%
- Frontend: Vitest + Playwright >=80%
```

#### T014 - Stakeholder Resolution Workflow (Full-Stack) (`TASK-AI-043`)

*Estimated Hours*: 12
*Priority*: P2 (Phase 2)
*Depends On*: T009

#### T015 - Intelligent WBS Proposal (`TASK-AI-049`)

*Estimated Hours*: 8
*Priority*: P2 (Phase 2)
*Depends On*: `TASK-BCK-060`, completed Swagger flow audit

*Intent*: Treat WBS as a project-control artifact, not a disposable LLM output. Before implementation, define the proposal for an assisted WBS lane that can derive candidate structure from contracts and project context while staying explainable and reviewable.

*Required Proposal Scope*:
- Inputs: project metadata, parsed contract clauses, existing WBS, alerts, and user intent.
- Outputs: hierarchical candidate WBS, parent-child integrity, source evidence per item, confidence/uncertainty, and explicit delta against the current structure.
- Controls: deterministic validation first, confidence scoring, LangGraph fallback extraction when workbook/document structure is ambiguous, duplicate detection, human approval gates, and tenant-safe persistence boundaries.
- Integration points: procurement, RACI, coherence, approvals, and future analytics.
- Evaluation: completeness, traceability, hierarchy validity, editability, and false-positive risk.

*Why deferred*: Phase 1 must first prove the current project/document/coherence flow and repair the live WBS contract so Phase 2 is designed on truthful foundations.

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

# Observability
- LangSmith tracing enabled
- Metrics: conflict_detection_precision, resolution_acceptance_rate, time_to_resolution

# Accuracy Target
- >=80% conflict detection precision

# Test Coverage
- Backend: pytest >=80%
- Frontend: Vitest + Playwright >=80%
```

#### Execution Timeline (Phase 2)

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
- **Completed**: 89 (93.7%)
- **Active/Deferred**: 6 (6.3%)
- **Test Coverage**: TBD

---

## 7. Audit Reports

### LangGraph Orchestration Audit (TASK-REV-AI-001)
**Date**: 2026-04-07
**Status**: ✅ RESOLVED (TASK-IMPL-010 complete)

#### Findings (historical):
1. **Business Logic in Nodes (High Risk)**: While progress has been made extracting logic to domain services (Citation, Coherence), several nodes still harbored critical logic:
   - `nodes.py`: `router_node` and `critique_node` contained hardcoded prompts and logic for confidence calculation.
   - `nodes_extended.py`: `raci_generator_node` and `budget_parser_extended_node` contained raw Jinja-like prompts and manual DTO-to-dict mapping logic.
2. **Infrastructure Coupling (Critical)**: `save_to_db_node` (N17) interacted directly with SQLAlchemy sessions, repositories, and ORM models.
3. **State Management**: ✅ EXCELLENT. `ProjectState` is correctly defined using `TypedDict`.
4. **Checkpoint Restoration**: ✅ OPERATIONAL. `AsyncPostgresSaver` correctly configured.
5. **Orchestration Duplication**: ✅ RESOLVED. `core/ai/orchestration` was deleted on 2026-04-06.

#### Resolution:
- TASK-IMPL-010 (all 16 subtasks) completed 2026-04-20. All domain services extracted, nodes slimmed to <50 lines, zero test regressions.

---
