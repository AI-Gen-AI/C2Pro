# Backend Tasks & Knowledge Base

**Category**: Backend (BCK)
**Owner Role**: backend
**Last Updated**: 2026-08-08

**Quick Links**:

- 🏠 [Master Index](../C2PRO_MASTER_BACKLOG.md)
- 📋 [Role Profile](../roles/role_backend.md)

---

## 0. Status View

**Pending Tasks**: 19 across 2 active epics

- `EPIC-MYPY-STRICT`: `TASK-BCK-095` (in-progress, Wave 1), `TASK-BCK-096` (Wave 2 partial — awaiting Fable integration), `TASK-BCK-097`–`TASK-BCK-113` (Waves 3–7, not started), `TASK-DEV-006` (promotion gate — after BCK-113 + QA-323)
- `EPIC-PROC2`: `EPIC-PROC2-001`–`EPIC-PROC2-005` — BUILD-GATE deferred (≥1 Contract Manager must use Change-Impact loop weekly)

**Completed Tasks**: 100+ — see [COMPLETED.md](./COMPLETED.md)

> IDs: `TASK-BCK-001`–`TASK-BCK-049`, `TASK-BCK-051`–`TASK-BCK-094`, `TASK-COH-V2-HOTFIX-001`, `TASK-COH-V2-ADAPTER-002`, `TASK-COH-V2-FRONTEND-003`, `TASK-COH-V2-VERSIONING-006`, `TASK-COH-V2-CACHING-007`, `TASK-COH-V2-DOCS-005`, `TASK-COH-V2-CUTOVER-004`, `TASK-CE-F2-01`, `TASK-OPS-DOCFLOW-019`

---

## 1. Active Tasks

No standalone one-off tasks are pending. All active backend work is tracked in the two epics below.

---

## 2. EPIC-MYPY-STRICT — Backend strict-typing burn-down (umbrella TASK-DEV-006)

**Goal**: `mypy src` → 0 errors with the full backend dependency set, then promote `backend-typecheck` to a required CI gate. Baseline: 1,357 errors / 300 files. Strict mode stays ON; **no** blanket ignores, `ignore_errors`, `Any` expansion, exclusions, or relaxed strictness. A `mypy-baseline.txt` ratchet (TASK-DEV-031 ✅) blocks NEW errors while existing ones burn down by bounded context.

**Work-package limits (every implementation commit)**: ≤10 production files or ~80 starting diagnostics; `arg-type`/`call-arg`/`attr-defined`/`assignment`/`operator`/`no-any-return` each need individual review; tenant + behavioral changes require RED tests first; record before/after totals, per-error-code counts, affected files, targeted tests, and zero new out-of-scope errors.

**Error taxonomy (baseline)**: type-arg ~304, arg-type ~231, no-untyped-def ~228, attr-defined ~115, assignment ~77, call-arg ~75, no-any-return ~65, operator ~62, no-untyped-call ~61. Largest areas: core 312, coherence 192, analysis 186, procurement 181, documents 172.

**High-signal defects (TASK-BCK-095, RED tests first)**: un-awaited repo coroutine `documents/application/use_cases.py:52`; 9 repository implementations incompatible with their ports (e.g. `INotificationService`, `IDocumentRepository`); branded `TenantId` (NewType) bypassed by raw `UUID` at boundaries (`documents/application/upload_document_use_case.py:105`); missing/reversed tenant/ID positional args; 3 duplicate definitions; LangSmith call treated as returning a value; invalid `type: ignore` at `coherence/scoring.py:829`; 17 stale `type: ignore`; missing SMTP settings attrs in `modules/hitl/adapters/http/dependencies.py`.

### WBS (dependency-ordered)

| ID | Owner | Wave | Scope | Depends on | Status |
|---|---|---|---|---|---|
| TASK-DEV-031 | DevOps | 0 | CI dep parity + `mypy-baseline.txt` ratchet + trustworthy exit reporting | TASK-DEV-003 | ✅ Done |
| TASK-BCK-095 | Backend/Security | 1 | High-signal probable defects (RED tests first) | TASK-DEV-031 | 🔄 In Progress |
| TASK-BCK-096 | Backend | 2 | Shared typing foundations: TenantId boundaries, generic contracts, explicit re-exports, approved stubs | TASK-BCK-095 | 🔄 Partial |
| TASK-BCK-097 | Backend | 3 | Documents domain ports/DTOs | TASK-BCK-096 | — |
| TASK-BCK-098 | Backend | 3 | Procurement domain ports/DTOs | TASK-BCK-096 | — |
| TASK-BCK-099 | Backend | 3 | Analysis domain ports/DTOs | TASK-BCK-097, TASK-BCK-098 | — |
| TASK-BCK-100 | Backend | 3 | Coherence domain ports/DTOs + typed scoring payloads | TASK-BCK-096 | — |
| TASK-BCK-101 | Backend | 4 | Documents persistence adapters | TASK-BCK-097 | — |
| TASK-BCK-102 | Backend | 4 | Procurement SQLAlchemy 2 Mapped modernization + persistence | TASK-BCK-098 | — |
| TASK-BCK-103 | Backend | 4 | Analysis persistence adapters + port covariance | TASK-BCK-099 | — |
| TASK-BCK-104 | Backend | 4 | Coherence/embedding persistence + mandatory tenant filtering | TASK-BCK-100 | — |
| TASK-BCK-105 | Backend | 5 | Documents application services + use cases | TASK-BCK-101 | — |
| TASK-BCK-106 | Backend | 5 | Procurement application services + use cases | TASK-BCK-102 | — |
| TASK-BCK-107 | Backend | 5 | Analysis application services + use cases | TASK-BCK-103, TASK-BCK-105, TASK-BCK-106 | — |
| TASK-BCK-108 | Backend | 5 | Coherence application services + use cases | TASK-BCK-104 | — |
| TASK-BCK-109 | Backend/Security | 6 | Core auth, tenant, security, middleware typing | TASK-BCK-095, TASK-BCK-096 | — |
| TASK-BCK-110 | Backend | 6 | Core cache, events, DLQ, task infrastructure | TASK-BCK-096 | — |
| TASK-BCK-111 | Backend/AI | 6 | Core AI, observability, LangSmith, MCP, external SDK validation | TASK-BCK-096, TASK-BCK-110 | — |
| TASK-BCK-112 | Backend | 7 | HTTP routers, dependencies, factories, composition edge | TASK-BCK-105…TASK-BCK-111 | — |
| TASK-BCK-113 | Backend | 7 | Remaining mechanical leaf cleanup + full-tree convergence to zero | TASK-BCK-112 | — |
| TASK-QA-322 | QA | — | Per-wave mypy ratchet + risk-proportionate regression certification | TASK-DEV-031 | ✅ Done 2026-07-18 |
| TASK-QA-323 | QA | — | Independent zero-error / full-suite / live-CI certification | TASK-BCK-113, TASK-QA-322 | ✅ Done 2026-07-19 |
| TASK-DEV-006 | DevOps | — | Promote `backend-typecheck` to required + close umbrella | TASK-QA-323 | — |

### TASK-BCK-095 execution log

- **Stakeholder approval tenant-isolation slice (in progress, TS-UA-STK-UC-001):** RED tests prove the authenticated tenant must cross the HTTP/use-case boundary and be supplied unchanged to both `IStakeholderRepository.get_by_id` and `update`. The use case normalizes the boundary UUID once with `require_tenant_id`; `TASK-BCK-095` remains open for the other high-signal defects in this wave.
- **Persistence review extension:** `SqlAlchemyStakeholderRepository.update` and Stakeholder `refresh` now select by the compound stakeholder ID + tenant ID boundary. Unscoped `session.get` calls in delete and RACI update/refresh paths remain pending under the still-open `TASK-BCK-095`; they are intentionally excluded from this approval-path slice.
- **Project knowledge-graph tenant propagation (in progress, TS-UAD-PER-GRP-001):** RED tests proved graph construction omitted the authenticated tenant from stakeholder, clause, and RACI repository reads. `ProjectKnowledgeGraph` now normalizes the tenant once and supplies it to every stakeholder, WBS, risk, clause, and RACI read. The focused Mypy diagnostic count for this adapter fell from 13 inherited findings to 8; remaining DTO and return-typing debt stays in later EPIC waves.
- **Document creation async persistence (in progress, TS-UD-DOC-DOC-001):** RED tests reproduced the discarded `IDocumentRepository.add` coroutine and missing exception propagation. `CreateDocumentUseCase.execute` is now async, normalizes its DTO tenant once with `require_tenant_id`, and awaits `add`; focused tests pass 3/3 and direct Mypy output no longer reports the use-case `unused-coroutine` or raw UUID-to-`TenantId` errors. `TASK-BCK-095` remains open for the other high-signal defects.
- **Document refresh tenant isolation (in progress, TS-E2E-SEC-TNT-001):** RED tests proved `SqlAlchemyDocumentRepository.refresh` used unscoped primary-key `session.get` for both `Document` and `Clause`. All production callers pass domain entities that already carry `tenant_id`, so the port now declares `Document | Clause` and the adapter selects by the entity's compound ID + tenant ID without changing caller behavior. Focused isolation tests pass 10/10 and Ruff passes; `TASK-BCK-095` remains open.
- **LangSmith native run lifecycle (in progress, TS-AI-LANGSMITH-001):** RED tests reproduced that LangSmith 0.10.2 `Client.create_run` returns `None`, leaving decorators without a span handle, while the wrapper's `end_run` method does not exist in that SDK. The wrapper now owns a stable UUID handle, supplies it to `create_run(id=...)`, and completes the same run through `update_run` with a UTC end time, error string, and outputs. Fail-open behavior is preserved; focused lifecycle/decorator/coherence tests pass 15/15 and Ruff passes. `TASK-BCK-095` remains open.
- **HITL SMTP settings wiring (in progress, TS-I11-HITL-HTTP-001):** RED proved that complete canonical lowercase SMTP settings still left email disabled because the dependency layer read nonexistent uppercase attributes; a second RED test prevented constructing an invalid email service without a sender. The provider now requires `smtp_host` plus `smtp_from`, uses the existing lowercase fields, normalizes absent credentials for unauthenticated SMTP, and retains log fallback when host or sender is absent. Focused dependency/router tests pass 16/16 and Ruff passes; targeted Mypy has only the inherited stale ignore at line 45 and no SMTP argument diagnostics. `TASK-BCK-095` remains open.

### TASK-BCK-096 execution log

- **Type-contract core lane (completed, TS-UT-CORE-TYP-001 / TS-E2E-SEC-TNT-001):** Added recursive `JsonValue`/`JsonDict` aliases and applied them to genuine Analysis JSON port contracts; orchestration state remains `dict[str, Any]` because it contains LangChain messages and domain objects and is not JSON. Extended `require_tenant_id` to parse serialized UUID strings, then normalized tenant identity once at snapshot, health HTTP, project-graph, artifact-completion, and document-analysis task boundaries. `ProjectStateRepository.get`, `IProjectSnapshotRepository.latest/list_since`, and all `IDocumentArtifactRepository` methods now require `TenantId`, with matching adapters/application services. Four bounded commits each passed focused RED/GREEN tests, Ruff, and the canonical ratchet (`baseline=1406 current=1327 new=0 fixed=79` on Windows). **Do not promote downstream Wave 3 dependencies until Fable integrates and verifies the complete Wave 2 set.**

---

## 3. EPIC-LC-WORKFLOWS / EPIC-PROC2 — Procurement Suite (Phase 2)

**Gate**: ≥1 Contract Manager uses the Change-Impact loop weekly before beginning Phase 2 work (same BUILD-GATE as v3).

**Source of truth**: `docs/audits/C2Pro — Technical, Product & Execution Improvement Proposal_Fable5.md`

### Live-state audit (2026-07-02, Fable5)

| Component | State | Notes |
|---|---|---|
| Procurement Plan | EXISTS, gated OFF | `feature_rfq_generation=False` in `config.py:319`; code in `procurement/domain/procurement_plan_generator.py` + `build_procurement_plan_use_case.py` |
| WBS identification | EXISTS + wired | `wbs_router` always on; `procurement/wbs_generator_service.py` |
| BoM generation | EXISTS + live | `generate_bom_use_case.py`; feeds DET-BUD reconciliation |
| RfQ generator | MISSING | Flag exists (`feature_rfq_generation`), zero RFQ/quotation code |
| BoQ (Bill of Quantities) | MISSING | BoM ≠ BoQ; BoQ is line-item pricing for tender/tender packages |
| Stakeholder communications | MISSING | Extraction + RACI + power/interest exist; comms workflows do not |

### Sub-tasks (registered 2026-08-08)

| ID | Priority | Gate | Description | Scope |
|---|---|---|---|---|
| `EPIC-PROC2-001` | P2 | BUILD-GATE | Un-gate Procurement Plan: flip `feature_rfq_generation=True` in config + tenant-flag pattern, wire backend API endpoint, add UI entry point. | `procurement/`, `config.py`, `apps/web/` |
| `EPIC-PROC2-002` | P2 | BUILD-GATE + PROC2-001 | RfQ generator: RfQ domain model (scope, quantities, requirements from WBS/contract), LLM extraction with EN/ES prompts, tenant-scoped `rfq_items` table (Alembic + RLS), API endpoint + OpenAPI spec. | `procurement/rfq/`, `alembic/` |
| `EPIC-PROC2-003` | P2 | BUILD-GATE + PROC2-001 | BoQ generator: BoQ model (priced line items from WBS+BoM+contract), EN/ES LLM extraction, `boq_items` table (Alembic + RLS), API endpoint. | `procurement/boq/`, `alembic/` |
| `EPIC-PROC2-004` | P2 | BUILD-GATE + PROC2-001 | Stakeholder communications module: comms templates (meeting/report/notification), distribution planning (stakeholder × comms channel matrix), `stakeholder_comms` table (Alembic + RLS), API endpoint. | `stakeholders/comms/`, `modules/hitl/` |
| `EPIC-PROC2-005` | P3 | BUILD-GATE + PROC2-004 | RACI automation: extend existing RACI extraction to propose role assignments from stakeholder map; human-approval step before committing. | `raci/`, `modules/hitl/` |

### Dependencies for Phase 2 start

1. **Phase 1 wedge live with weekly use** (BUILD-GATE criterion) — document operability + coherence scoring proven with ≥1 real Contract Manager.
2. **DDD-MIGRATION gate** — Procurement domain already follows hexagonal structure; no new migration needed before starting PROC2-001.
3. **v3 BUILD-GATE** — Action & Review Loop (EPIC-V3-019/020) required before full RACI automation (EPIC-PROC2-005) since the HITL queue is a shared seam.

---

## 4. Completed Task IDs (reference)

| Task ID | Description | Completed |
| --- | --- | --- |
| `TASK-BCK-001`–`TASK-BCK-049` | Initial domain, WBS, DI, migrations, LangGraph, HITL, alerting, lint, tests | 2026-02-19 – 2026-05-08 |
| `TASK-BCK-051` | Production 500 triage | WONT-DO 2026-08-08 |
| `TASK-BCK-052`–`TASK-BCK-059` | LangGraph parallel-state fix, checkpoint isolation, coherence tracing, structured extraction layer, AnthropicWrapper fix, RAG category targeting, DET guards | 2026-05-17 |
| `TASK-BCK-060`–`TASK-BCK-077` | WBS contract reconciliation, RAG provider errors, idempotency, clause chunks, penalty fallback, alerts auth, analysis tool contract, HITL seam, Alembic merge heads | 2026-05-17 – 2026-06-07 |
| `TASK-BCK-083`–`TASK-BCK-094` | Evidence contracts, LEGAL pilot, centroid builder, Capa 2 LLM classifier, Supabase mirror backfill (33 tables), budget reconciliation fields, OpenAPI operation ID dedup | 2026-05-09 – 2026-08-07 |
| `TASK-COH-V2-HOTFIX-001` | v1 scoring §14 active-weight guard (`mean × coverage_ratio` → null when `active_weight < 0.35`) | 2026-05-26 |
| `TASK-COH-V2-ADAPTER-002` | v1→v2 adapter partial-coverage fix (INSUFFICIENT_EVIDENCE classification, real per-category weights) | 2026-05-26 |
| `TASK-COH-V2-FRONTEND-003` | Frontend null-safe rendering (ADR-009 §18; CI grep guard on `?? 0`) | 2026-07-10 |
| `TASK-COH-V2-VERSIONING-006` | Mandatory `score_version` canonical 2-value enum on all surfaces | 2026-07-11 (PR #190) |
| `TASK-COH-V2-CACHING-007` | Cache namespace versioning + `on_flag_flip`/`on_result_persisted`/`on_deploy` handlers | 2026-07-11 (PR #196) |
| `TASK-COH-V2-DOCS-005` | ADR-009 rename → `ADR-009-evidence-oriented-coherence-orchestration.md`, status Accepted, CHANGELOG | 2026-08-08 (PR #472) |
| `TASK-COH-V2-CUTOVER-004` | Per-tenant v2 flag + canary 10→50→100% with shadow-MAE auto-block | 2026-08-07 (PRs #462/#464) |
| `TASK-CE-F2-01` | LEGAL pilot extraction adapter | 2026-05-29 |
| `TASK-OPS-DOCFLOW-019` | GitHub CI Alembic bootstrap repair (unsafe `ALTER TYPE ADD VALUE` → recreate migration) | 2026-05-27 |
