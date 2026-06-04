# C2PRO Master Backlog - Index & Overview

**Purpose**: High-level project index. Only **pending** work is tracked here.
**Last Updated**: 2026-06-04 (pending-only PM view)
**Archive**: [`backlogs/COMPLETED.md`](backlogs/COMPLETED.md)

> **Navigation**: Quick Navigation → Pending Manifest → Pending by Category.

---

## Quick Navigation

| Category | File | Owner | Pending |
| -------- | ---- | ----- | ------- |
| AI/ML Intelligence | [backlogs/AI_AI_ML_INTELLIGENCE.md](backlogs/AI_AI_ML_INTELLIGENCE.md) | ai | 7 |
| Backend | [backlogs/BCK_BACKEND.md](backlogs/BCK_BACKEND.md) | backend | 13 |
| DevOps | [backlogs/DEV_DEVOPS.md](backlogs/DEV_DEVOPS.md) | devops | 0 |
| Documentation | [backlogs/DOC_DOCUMENTATION.md](backlogs/DOC_DOCUMENTATION.md) | shared | 0 |
| Frontend | [backlogs/FRT_FRONTEND.md](backlogs/FRT_FRONTEND.md) | frontend | 1 |
| Infrastructure | [backlogs/INF_INFRASTRUCTURE.md](backlogs/INF_INFRASTRUCTURE.md) | infra | 5 |
| Planning | [backlogs/PLN_PLANNING.md](backlogs/PLN_PLANNING.md) | planner | 0 |
| Quality Assurance | [backlogs/QA_QUALITY_ASSURANCE.md](backlogs/QA_QUALITY_ASSURANCE.md) | qa | 108 |
| Code Review | [backlogs/REV_CODE_REVIEW.md](backlogs/REV_CODE_REVIEW.md) | reviewer | 0 |
| Security | [backlogs/SEC_SECURITY.md](backlogs/SEC_SECURITY.md) | security | 5 |

---

## Restructured Manifest v3 (Pending Execution Only)

> Historical and WONT-DO items are archived in [`backlogs/COMPLETED.md`](backlogs/COMPLETED.md). This master view is for PM execution only.

| Status | Priority | ID | Dependency | Task | Source |
| ------ | -------- | -- | ---------- | ---- | ------ |
| [ ] | P2 | `EPIC-LC-WORKFLOWS` | DDD-MIGRATION + PHASE-2 | Procurement + RACI + Stakeholder + intelligent WBS flows with EN/ES prompts. Deferred to Phase 2; not on current critical path. | Manifest v3 |
| [ ] | P0 | `EPIC-OPS-DOCFLOW` | EPIC-COVERAGE-GATES | Real document operability gate: upload, parse, anonymize, extract, score, alert, and render through tenant-safe API/UI. | `blackboard/coverage-gates/REAL-DOCUMENT-OPERABILITY-SPEC-PLAN.md` |
| [ ] | P3 | `EPIC-SENTRY-PERF` | TENANT-RLS-HARDENING | Sentry auth alerts remain blocked on operator prerequisites. | Manifest v3 |
| [ ] | P3 | `TASK-FRT-041` | TENANT-RLS-HARDENING | Clerk production email templates; blocked on operator access. | `docs/runbooks/CLERK_AUTH_DEV_PROD_GUIDE.md` |
| [ ] | P0 | `EPIC-ECOA-V2-HOTFIX-AND-CUTOVER` | EPIC-COH-V1-CONSOLIDATION | Coherence Score v2 hotfix/cutover: active-weight guard, adapter fix, frontend null-safe, canonical `score_version`, cache namespacing, per-tenant cutover. | `docs/superpowers/specs/2026-05-25-ecoa-v2-hotfix-and-cutover-design.md` |

## Pending Tasks by Category

> Only `[ ]` items are listed here. For historical task detail, see [`backlogs/COMPLETED.md`](backlogs/COMPLETED.md) or the category backlog files.

### Backend (12 pending)

| Priority | Task ID               | Depends On                       | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                                     |
| -------- | --------------------- | -------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| P0       | `TASK-BCK-051`        | None                             | Investigate live `500` responses on project alerts and project stakeholders by correlating production error references with backend logs and verifying applied Alembic head/schema parity for tenant-hardened tables. Live schema drift was repaired on 2026-05-16 via `20260516_0001`; 2026-05-25 local parity check repaired stale stakeholder contract fixture drift and verified Alembic single head `20260524_0001`; log correlation remains blocked on unavailable production log access. |
| P1 | `TASK-BCK-088` | `TASK-BCK-084` | Design and implement prototype centroid build/cache with pgvector only after embedding-model/dimension decision; validate seed_hash reproducibility and avoid assuming current 1536-dim storage fits `bge-m3`. |
| ~~P1~~ ✅ | `TASK-BCK-089` | `TASK-BCK-086,TASK-BCK-088` | ~~Add ambiguous-chunk `CategoryClassifierNode`~~ **DONE 2026-06-04** — `CategoryClassifierNode` Capa 2 LLM escalation. 22/22 tests green. |
| P1       | `TASK-BCK-063`        | None                             | Persist `parsed_at` when document parsing succeeds: live `GET /api/v1/documents/{document_id}` returns `upload_status="parsed"` with `parsed_at=null`, and the parse use case still contains a placeholder comment instead of a real timestamp update.                                                                                                                                                                                                                                          |
| P0       | `TASK-BCK-064`        | `TASK-BCK-062`                   | Reconcile schedule ingestion with coherence scoring: after a live schedule upload parses successfully and creates WBS items, `/api/v1/coherence/evaluate/diagnostics` still reports `score_missing_dimensions=["schedule"]`, so schedule evidence is not yet contributing to the coherence model.                                                                                                                                                                                               |
| P0 | `TASK-COH-V2-HOTFIX-001` | None | Enforce ECOA v2 §14 active-weight guard so insufficient active evidence returns `overall_score=null` with `score_reason="insufficient_active_weight"`. |
| P0 | `TASK-COH-V2-ADAPTER-002` | `TASK-COH-V2-HOTFIX-001` | Fix coherence adapter contract drift and preserve canonical null/score_reason behavior through API diagnostics. |
| P0 | `TASK-COH-V2-FRONTEND-003` | `TASK-COH-V2-HOTFIX-001` | Make frontend score rendering null-safe for insufficient evidence instead of showing misleading numeric scores. |
| P0 | `TASK-COH-V2-VERSIONING-006` | `TASK-COH-V2-HOTFIX-001` | Canonicalize `score_version` to the approved two-value enum and add Alembic backfill. |
| P0 | `TASK-COH-V2-CACHING-007` | `TASK-COH-V2-HOTFIX-001` | Namespace coherence caches by score version and invalidate on tenant cutover flag changes. |
| P1 | `TASK-COH-V2-DOCS-005` | `TASK-COH-V2-HOTFIX-001` | Update ADR-009/OpenAPI/codemap after ECOA v2 hotfix behavior is verified. |
| P2 | `TASK-BCK-077` | None | Repair Celery task registration/import drift so worker startup includes current analysis/document tasks. |
| P0 | `TASK-COH-V2-CUTOVER-004` | `TASK-COH-V2-HOTFIX-001,TASK-COH-V2-ADAPTER-002,TASK-COH-V2-FRONTEND-003` | Roll out v2 authoritative scoring behind per-tenant flag with shadow MAE guard and canary 10-50-100. |

### Frontend (1 pending)

| Priority | Task ID            | Depends On | Description                                                                           |
| -------- | ------------------ | ---------- | ------------------------------------------------------------------------------------- |
| P3       | `TASK-FRT-041`     | None       | Production email templates and sender verified in Clerk — BLOCKED on operator access. |

### AI / ML Intelligence (7 pending)

| Priority | Task ID | Depends On | Description |
| -------- | ------- | ---------- | ----------- |
| P2 | `TASK-AI-010` | `TASK-216` | Add prompt metadata to LangSmith Hub: owner, description, and tags. |
| P2 | `TASK-AI-011` | `TASK-216` | Implement A/B test config in LangSmith Hub for gradual rollout. |
| P2 | `TASK-AI-040` | None | [PHASE 2 DEFERRED] Multi-language prompt templates in English and Spanish. |
| P2 | `TASK-AI-041` | Planned | [PHASE 2 DEFERRED] Implement Procurement Plan flow with LangChain. |
| P2 | `TASK-AI-042` | Planned | [PHASE 2 DEFERRED] Implement RACI flow with LangChain. |
| P2 | `TASK-AI-043` | Planned | [PHASE 2 DEFERRED] Implement Stakeholder Resolution flow with LangChain. |
| P2 | `TASK-AI-049` | `TASK-BCK-060`, Swagger flow audit | [PHASE 2 DEFERRED] Draft intelligent WBS proposal with evidence, hierarchy validation, uncertainty, and HITL gates. |

### Infrastructure (5 pending)

| Priority | Task ID | Depends On | Description |
| -------- | ------- | ---------- | ----------- |
| P2 | `TASK-INF-008` | None | [PHASE 2 DEFERRED] Multi-language prompt templates in English and Spanish. |
| P2 | `TASK-INF-009` | Planned | [PHASE 2 DEFERRED] Implement Procurement Plan flow with LangChain. |
| P2 | `TASK-INF-010` | Planned | [PHASE 2 DEFERRED] Implement RACI flow with LangChain. |
| P2 | `TASK-INF-011` | Planned | [PHASE 2 DEFERRED] Implement Stakeholder Resolution flow with LangChain. |
| P3 | `TASK-INF-055` | DevOps/operator access | Monitor auth failures in Sentry; blocked on Sentry DSN and alert destination setup. |

### Quality Assurance (108 pending)

| Priority | Task ID | Depends On | Description |
| -------- | ------- | ---------- | ----------- |
| P1 | `EPIC-QA-SWAGGER-MANUAL-VERIFICATION` | Live Swagger environment | Real Swagger endpoint audit across the open `TASK-QA-214..321` operation tasks. Each row remains pending until executed live through Swagger with outcome notes in `backlogs/QA_QUALITY_ASSURANCE.md`. |

### Security (5 pending)

| Priority | Task ID | Depends On | Description |
| -------- | ------- | ---------- | ----------- |
| P1 | `TASK-SEC-012` | None | Add SQL RLS test `supabase/tests/09_clause_embeddings_rls.sql` covering cross-tenant isolation and fail-closed behavior. |
| P1 | `TASK-SEC-013` | None | Add auth guard to cookie consent endpoints: `POST/GET/PATCH /compliance/cookies/consent`. |
| P1 | `TASK-SEC-014` | None | Persist disclaimer acceptance to DB instead of in-process memory so multi-pod deployments remain correct. |
| P1 | `TASK-SEC-015` | None | Use `SecretStr` for `secret_channel_token` and `secret_channel_vault_token` in `config.py`. |
| P2 | `TASK-SEC-016` | None | Guard `VaultKvBundleProvider.load_bundle` against malformed `bundle_ref` values without `:`. |

### Cross-Category

No pending cross-category tasks in this view. Historical items are archived in [backlogs/COMPLETED.md](backlogs/COMPLETED.md).
