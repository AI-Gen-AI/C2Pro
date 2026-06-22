# C2PRO Master Backlog - Index & Overview

**Purpose**: High-level project index. Only **pending** work is tracked here.
**Last Updated**: 2026-06-05 (pending-only PM view)
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
| [x] | P0 | `EPIC-ECOA-V2-HOTFIX-AND-CUTOVER` | EPIC-COH-V1-CONSOLIDATION | Coherence Score v2 hotfix/cutover: active-weight guard, adapter fix, frontend null-safe, canonical `score_version`, cache namespacing, per-tenant cutover. | `docs/superpowers/specs/2026-05-25-ecoa-v2-hotfix-and-cutover-design.md` |

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
| ~~P0~~ ✅ | `TASK-COH-V2-HOTFIX-001` | None | Enforce ECOA v2 §14 active-weight guard so insufficient active evidence returns `overall_score=null` with `score_reason="insufficient_active_weight"`. |
| ~~P0~~ ✅ | `TASK-COH-V2-ADAPTER-002` | `TASK-COH-V2-HOTFIX-001` | Fix coherence adapter contract drift and preserve canonical null/score_reason behavior through API diagnostics. |
| ~~P0~~ ✅ | `TASK-COH-V2-FRONTEND-003` | `TASK-COH-V2-HOTFIX-001` | Make frontend score rendering null-safe for insufficient evidence instead of showing misleading numeric scores. |
| ~~P0~~ ✅ | `TASK-COH-V2-VERSIONING-006` | `TASK-COH-V2-HOTFIX-001` | Canonicalize `score_version` to the approved two-value enum and add Alembic backfill. |
| ~~P0~~ ✅ | `TASK-COH-V2-CACHING-007` | `TASK-COH-V2-HOTFIX-001` | Namespace coherence caches by score version and invalidate on tenant cutover flag changes. |
| ~~P1~~ ✅ | `TASK-COH-V2-DOCS-005` | `TASK-COH-V2-HOTFIX-001` | Update ADR-009/OpenAPI/codemap after ECOA v2 hotfix behavior is verified. |
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

---

## Hotfix — Alerts/Analysis Honesty (2026-06-22, PR #162, branch hotfix/alerts-analysis-honesty)

Pre-existing existing-app bugs found during real-contract pilot testing (separate from the flag-OFF v3 thin spine / PR #158). Opus-gate APPROVED; awaiting merge to main. Outcome: a real ADIF-AV contract now yields 14 evidence-grounded risks → alerts, and the Coherence engine works on main for the first time.

COMPLETED (all [x], on the hotfix branch):

| Task | Status | Commit | Summary |
| ---- | ------ | ------ | ------- |
| `[x] TASK-HOTFIX-001` | Done | a0bc2798 | alerts.message schema drift → repair migration 20260620_0001 (ADD COLUMN IF NOT EXISTS + backfill + SET NOT NULL); gate-verified up/down on fresh DB. Fixes alerts list 500. + ORM-columns-match-DB guard test. |
| `[x] TASK-HOTFIX-002` | Done | acdfb8d3 | Risk extractor honest-fail: stop fabricating misattributed risks + inflating confidence when AI tool fails; emit honest empty + DEGRADED. |
| `[x] TASK-HOTFIX-003` | Done | 769908ae | Honest no-text guard: scanned/empty PDF → insufficient_extractable_text instead of silent technical_spec default. |
| `[x] TASK-HOTFIX-004` | Done | 2ee50b0f | /analyze preview honesty: response now persisted=false, mode=preview (it never persists/creates alerts; full pipeline does). |
| `[x] TASK-HOTFIX-005` | Done | b005a577 | Async full-analysis task (documents.analyze_document, routed to document_parsing) + ingestion enqueues it; force_full_pipeline so N17 persist+alerts is reached. |
| `[x] TASK-HOTFIX-006` | Done | 0cfe282e | Celery worker AI tool registration: celery_app now imports src.analysis.adapters.ai.tools (was empty registry → ToolNotFound → fabrication). Guard test asserts registry non-empty. |
| `[x] TASK-HOTFIX-007` | Done | 684846df | API startup: start.sh CRLF→LF (.gitattributes *.sh eol=lf + Dockerfile sed hardening). API back up. |
| `[x] TASK-HOTFIX-008` | Done | d0fbf2d3 | Checkpoint isolation: per-document analysis uses unique per-run thread_id (document:{id}:analysis:{uuid4}) instead of project_id → no stale LangGraph replay. |
| `[x] TASK-HOTFIX-009` | Done | 9f1d9224 | Risk parser shape handling: handle fenced/raw/trailing JSON + container-key + alias variants in _extract_items (LLM returned fenced {"risks":[...]} that recovery dropped). 14 risks now parse + ground. |
| `[x] TASK-HOTFIX-010` | Done | 4e73e79d | Restore REAL coherence modules on main (category_router/segments byte-identical to feat/v3-spine; category_registry real model + Docker-safe YAML path-resolution fix) + regenerate openapi. main coherence was broken (modules never merged). |

FOLLOW-UPS (open):

| Task | Pri | Summary |
| ---- | --- | ------- |
| `[ ] TASK-HOTFIX-F1` | P1 | Apply the category_registry Docker-safe YAML path fix to feat/v3-spine / PR #158 (same latent parents[4/5] bug there; reconverges the branches so #158 doesn't ship Docker-broken coherence). |
| `[ ] TASK-HOTFIX-F2` | P2 | Verify re-analysis SUPERSEDES prior alerts rather than accumulating (alerts went 14→42 once coherence became active); ensure no duplicate alerts across reprocess runs. |
| `[ ] TASK-HOTFIX-F3` | P2 | Confirm pre-existing TASK-V3-017-06 critique-router tests (test_thin_nodes TestCritiqueRouter::test_retry_*) now pass after the critique-routing changes; else keep tracked. |
| `[ ] TASK-HOTFIX-F4` | P2 | KnowledgeGraphAdapter degraded node in stakeholder extraction (import missing; honest-degraded, does not block persistence; absent on feat/v3-spine too). |

---

## Change Log

**2026-06-22**: Hotfix alerts/analysis honesty (PR #162, branch hotfix/alerts-analysis-honesty) — Opus-gate APPROVED, awaiting merge to main. Fixed a 7-layer pre-existing failure chain so a real contract produces grounded output end-to-end: alerts.message migration drift (TASK-HOTFIX-001), risk-extractor honest-fail (002), no-text honesty (003), /analyze preview clarity (004), async analysis trigger (005), Celery worker tool registration — the empty-registry root cause of fabricated risks (006), start.sh CRLF API-startup (007), LangGraph checkpoint isolation (008), risk-parser fenced-JSON shape handling (009 → 14 grounded risks), and restoration of the REAL coherence category-routing modules main was missing (010, + openapi regen). Live: real ADIF-AV contract → 14 grounded risks → alerts; coherence engine now loads on main. Gate independently re-verified the migration up/down on a fresh DB and the coherence-module faithfulness. Filed follow-ups TASK-HOTFIX-F1..F4. NOTE: coherence score still requires the contract+schedule+budget triplet (contract-only honest-null by design). These are existing-app fixes, independent of v3 PR #158 (still pending). No push to main (PR awaiting review).
