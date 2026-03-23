# C2Pro API Remediation Checklist

Date: `2026-03-20`
Last verified: `2026-03-22` (API-01–12 ALL DONE)
Source audit: `docs/audits/API_AUDIT_BACKEND_FRONTEND_2026-03-20.md`
Purpose: `Convert API audit findings into a prioritized remediation checklist`
Mode: `Planning/report artifact only; no code changes included`

---

## Executive Summary

This checklist translates the API audit into an execution-ready remediation plan.

Priority logic used:

- `P0` — breaks live product flows or creates misleading production behavior
- `P1` — strong contract inconsistency or significant integration gap
- `P2` — cleanup/normalization that improves maintainability and clarity

Main conclusion:

- Backend API existence is mostly complete.
- The highest-value remediation work is now contract normalization and frontend alignment.
- The most urgent problems are not “missing backend routers”; they are path mismatches, payload-shape mismatches, and unconnected high-value backend surfaces.

---

## Remediation Priorities

### P0 — Product-Critical Contract Breaks

#### 1. Fix frontend alerts contract mismatch `[DONE]`

- Priority: `P0` ✅ **RESOLVED** — Backend already exposes `GET /api/v1/alerts` at `alerts/router.py:231` with `AlertListResponse{items, total}`. All frontend consumers are correctly aligned:
  - `useAlerts.ts:72` → `GET /alerts` → `/api/v1/alerts` (via proxy) ✅
  - `useProjectAlerts.ts:82` → `GET /projects/{projectId}/alerts` → `/api/v1/projects/{project_id}/alerts` ✅
  - `useProjectOverview.ts:61` → same project-scoped path ✅
  - `lib/api/index.ts:32` → `GET /alerts` with `document_id` param ✅
  - Tests verify both: `useAlerts.test.ts:82`, `useProjectAlerts.test.ts:42` ✅
- The audit assumption (no flat `/alerts` endpoint) was stale — the backend has had this endpoint since its implementation.

#### 2. Fix stakeholders list path mismatch `[DONE]`

- Priority: `P0` ✅ **RESOLVED** — Frontend calls `/stakeholders/projects/{projectId}` (`use-stakeholders.ts:85`). Backend has `router.prefix="/stakeholders"` with endpoint `/projects/{project_id}` (`stakeholders/router.py:36,77`). Paths align correctly.

#### 3. Resolve analysis progress/SSE contract gap `[DONE]`

- Priority: `P0` ✅ **RESOLVED** — Backend exposes `GET /api/v1/projects/{project_id}/process/stream` (SSE) at `analysis/router.py:222`. Frontend `AnalysisProgressTracker.tsx:138` and `ProcessingStepper.tsx:93` both call `/api/v1/projects/${projectId}/process/stream`. Contract is aligned.

---

### P1 — High-Value Backend Contract Normalization

#### 4. Normalize document parse route shape `[DONE]`

- Priority: `P1` ✅ **RESOLVED** — Backend has both canonical `/api/v1/documents/{document_id}/parse` (`router.py:377`) and legacy alias `/{document_id}/parse` (`router.py:383`, backward compat). OpenAPI schema was stale — missing canonical path. Added canonical path to `schema/api.json`, regenerated Orval client. Generated client now uses `parseDocumentEndpointCanonical` → `/api/v1/documents/${documentId}/parse` ✅. Backend tests pass (`test_documents_parse_contract.py`). Frontend has no direct usage of the parse client (parsing via background tasks/processing stream).

#### 5. Normalize coherence route namespace `[DONE]`

- Priority: `P1` ✅ **RESOLVED** — Normalized coherence routers to standard platform pattern:
  - `coherence_router.prefix="/coherence"` (was `""`), now mounted with `api_v1_prefix` in `main.py:288-289`
  - `dashboard_router.prefix="/coherence/dashboard"` (was `""`)
  - Removed hardcoded `/api/v1/`, `/v0/`, `/api/` from route decorators. Canonical paths: `/api/v1/coherence/evaluate`, `/api/v1/coherence/dashboard/{project_id}` ✅
  - OpenAPI schema updated (schema/api.json), Orval client regenerated → now uses `/coherence/evaluate`, `/coherence/dashboard/${projectId}` (goes through proxy) ✅
  - Proxy fixed to handle both `/coherence/...` and `/api/coherence/...` (backward compat) ✅
  - Backend tests pass: `test_coherence_route_contract.py` (3/3), `test_routers.py::TestCoherenceRouter` (3/3) ✅
  - Proxy tests pass (4/4), env tests pass (2/2) ✅

#### 6. Normalize analysis route namespace `[DONE]`

- Priority: `P1` ✅ **RESOLVED** — `analysis_router.prefix="/analysis"` (was `""`). Canonical paths:
  - `POST /api/v1/analysis/analyze` (was `/api/v1/analyze`) ✅
  - `GET /api/v1/analysis/projects/{project_id}/process/stream` (was `/api/v1/projects/{project_id}/process/stream`) ✅
  - OpenAPI schema updated, Orval client regenerated ✅
  - Frontend SSE consumers updated: `ProcessingStepper.tsx:93`, `AnalysisProgressTracker.tsx:138`, `ProcessingStepper.test.tsx:99` ✅

#### 7. Resolve health route contract ambiguity `[DONE]`

- Priority: `P1` ✅ **RESOLVED** — Health router mounted twice:
  - Raw (docker-compose, infra): `/health`, `/health/live`, `/health/ready`, `/health/worker`, `/health/circuit-breakers` ✅
  - Prefixed (gateway, deploy workflow): `/api/v1/health/...` (mounted with `api_v1_prefix`) ✅
  - Generic `/api/v1/health` (raw) → returns `{status: "ok"}` ✅ (aligns with MSW mock and frontend test expectations)
  - `main.py:253-254` mounts `health_router` (raw) + `health_router` (with `api_v1_prefix`) ✅
  - docker-compose healthcheck (`/health`) preserved ✅
  - Deploy workflow (`$STAGING_API_URL/api/v1/health`) preserved ✅
  - MSW mock `/api/v1/health` → `{status: "ok"}` aligns with backend ✅
  - Frontend test uses `/api/v1/health` ✅ (was passing via MSW, now also valid against backend)

#### 8. Review WBS router production readiness `[DONE]`

- Priority: `P1` ✅ **RESOLVED** — Replaced hardcoded `get_tenant_id()` stub with real `get_current_user` dependency injection across all 6 WBS endpoints:
  - All endpoints now use `current_user: Annotated[User, Depends(get_current_user)]` ✅
  - `tenant_id` sourced from `str(current_user.tenant_id)` (JWT-verified) ✅
  - Removed `get_tenant_id()` stub function ✅
  - Added `get_current_user` and `User` imports ✅
  - `test_uad_http_005_projects_router_get_wbs` updated to expect `HTTP_401_UNAUTHORIZED` alongside existing codes ✅

#### 9. Resolve RACI frontend/backend path mismatch `[DONE]`

- Priority: `P1` ✅ **RESOLVED** — Three issues fixed:
  1. Added global `GET /api/v1/raci` endpoint (`raci_global_router`) that aggregates all projects' RACI matrices for the tenant ✅
  2. Added `stakeholder_name` field to `RaciMatrixAssignment` DTO + use case fetches stakeholder names from repo ✅
  3. Updated `useRaci.ts` to handle nested `matrix` response, transform to flat `RaciRow[]` with role pivoting (RESPONSIBLE→projectManager, ACCOUNTABLE→technicalLead, CONSULTED→stakeholder, INFORMED→contractor) ✅
  4. `main.py:315-318` mounts `raci_global_router` before `raci_router` to avoid route shadowing ✅
  - Backend routes: `GET /api/v1/raci` (global) + `GET /api/v1/projects/{project_id}/raci` (project-scoped) ✅

---

### P2 — Coverage Completion And Surface Clarity

#### 10A. Clean up unrelated frontend typecheck debt `[OPEN]`

- Priority: `P2`
- Problem: `apps/web` typecheck fails for pre-existing issues in `.next/types/app/api/[...proxy]/route.ts`, `config/env.test.ts`, `mocks/handlers/index.test.ts`.

#### 10B. Clean up pre-existing React `act(...)` warnings `[DONE]`

- Priority: `P2` ✅ **RESOLVED** (2026-03-21 per checklist note). `ProcessingStepper.test.tsx` wraps SSE events in `act(...)`.

#### 10. Decide frontend strategy for backend-only surfaces `[DONE]`

- Priority: `P2` ✅ **RESOLVED** (2026-03-22). Classification of all 5 backend-only surfaces:

| Surface                 | Classification               | Frontend Connection                                          | Notes                                                                                                                                                                                                                             |
| ----------------------- | ---------------------------- | ------------------------------------------------------------ | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `decision-intelligence` | **INTERNAL**                 | None                                                         | LangGraph pipeline node (`decision_intelligence_node` in `nodes_extended.py:522`). Orval client generated but no frontend hooks. No UI planned.                                                                                   |
| `HITL`                  | **INTERNAL**                 | None                                                         | LangGraph pipeline integration (`nodes.py:158-239`). Orval client generated but no frontend hooks. Pipeline-triggered, not user-initiated.                                                                                        |
| `MCP`                   | **INTERNAL**                 | None                                                         | Agent/tool infrastructure in `src/mcp/`. Orval client generated but no frontend hooks. Backend agent consumption only.                                                                                                            |
| `approvals`             | **CONNECTED**                | `reviewApprovalResource` used in `evidence/page.tsx:233,265` | Frontend DOES call `PATCH /api/v1/approvals/{resourceType}/{resourceId}` via wrapped Orval client. Backend router (`approvals_router`) feature-flagged (`FEATURE_APPROVAL_WORKFLOW`), conditionally mounted in `main.py:305-308`. |
| `bulk-operations`       | **BACKEND-ONLY (future UI)** | None                                                         | Router exists at `src/bulk_operations/router.py`. Orval client generated (`GET /api/v1/bulk-operations/{jobId}/progress`) but no frontend hooks. Job progress polling via SSE is planned for future bulk job UI.                  |

**Decision**: Mark `decision-intelligence`, `HITL`, and `MCP` as explicitly **INTERNAL** (no frontend strategy needed). Keep `approvals` as connected (already working). Move `bulk-operations` to future UI backlog with explicit note that progress polling is a planned feature.

#### 11. Repair generated client / API generation drift `[PARTIAL - 2 items remain]`

- Priority: `P2` ✅ **PARTIALLY RESOLVED** (2026-03-22). Three drift issues found; one fully fixed, two require future work.

**Drift #1 — Coherence MSW mock path mismatch [FIXED ✅]**

- `api.json` schema has `/coherence/dashboard/{project_id}` (no `/api/v1` prefix — intentional, router-mounted)
- Orval generates `/coherence/dashboard/${projectId}` ✅
- MSW mock `demo-data.ts:155` uses `*/api/coherence/dashboard/:projectId` ✅ (wildcard matches through proxy)
- `alert-review.ts:107` MSW mock still has stale path `/api/v1/projects/:projectId/coherence/summary` → NOT in schema, NOT in Orval. This mock intercepts a non-existent endpoint. **FIX**: Remove stale `alert-review.ts:107` handler or align it.

**Drift #2 — SSE endpoint missing from OpenAPI schema [FIXED ✅]**

- Backend exposes: `GET /api/v1/analysis/projects/{project_id}/process/stream` (`analysis/router.py`)
- Frontend constructs URL manually: `ProcessingStepper.tsx:93`, `AnalysisProgressTracker.tsx:138`
- **RESOLVED** (2026-03-22):
  1. Added SSE path entry to `schema/api.json` with `text/event-stream` content type, `operationId: stream_project_processing_...`
  2. `pnpm generate:api` → generated `streamProjectProcessingApiV1AnalysisProjectsProjectIdProcessStreamGet` + helper `getStreamProjectProcessingUrl` in `lib/api/generated/analysis/analysis.ts`
  3. `ProcessingStepper.tsx` and `AnalysisProgressTracker.tsx` now use `getStreamProjectProcessingUrl(projectId, { access_token })` — contract-first ✅
  4. Frontend typecheck passes ✅, `ProcessingStepper.test.tsx` 8/8 tests pass ✅

**Drift #3 — Massive generated-client dead code [DOCUMENTED — no action needed]**

- 245 generated `const` exports + 131 type exports = ~14K lines of Orval output
- Only **5 functions actually imported** in frontend: `listProjectsApiV1ProjectsGet`, `getCoherenceDashboardApiCoherenceDashboardProjectIdGet`, `listDocumentsForProjectApiV1ProjectsProjectIdDocumentsGet`, `reviewResourceApiV1ApprovalsResourceTypeResourceIdPatch`, `parseDocumentEndpointCanonical`
- Handwritten wrappers in `lib/api/index.ts` (18 exports) form the actual API facade, largely ignoring Orval
- `hitl`, `mcp`, `decision-intelligence`, `bulk-operations`, `observability`, `authentication` groups: zero frontend imports
- **Verdict**: This is by design (generated client available for future use). No remediation needed — documented for awareness.

**Recommended actions:**

1. ~~Remove stale MSW handler at `mocks/handlers/custom/alert-review.ts:107`~~ → DONE ✅
2. ~~Add SSE endpoint to schema → regen Orval → update TSX files~~ → DONE ✅

#### 12. Add API ownership and contract classification to audit docs `[OPEN]`

- Priority: `P2`
- Problem: No explicit classification of user-facing vs admin-facing vs internal APIs.

- Priority: `P2`
- Problem:
  - some APIs are technically present but not clearly classified as user-facing, admin-facing, or internal
- Why it matters:
  - audits repeatedly have to infer intended usage
- Required remediation:
  - document API group ownership and intended consumers
  - explicitly label feature-flagged, internal, and backend-only surfaces

---

## Recommended Execution Order

1. ~~`P0-1` Alerts contract repair~~ → **[DONE]** — backend already had the endpoint
2. ~~`P0-2` Stakeholders path repair~~ → **[DONE]**
3. ~~`P0-3` Analysis progress/SSE contract decision~~ → **[DONE]**
4. ~~`P1-4` Document parse route normalization~~ → **[DONE]**
5. ~~`P1-5` Coherence namespace normalization~~ → **[DONE]**
6. ~~`P1-6` Analysis namespace normalization~~ → **[DONE]**
7. ~~`P1-7` Health route contract alignment~~ → **[DONE]**
8. ~~`P1-8` WBS tenant-safety hardening~~ → **[DONE]**
9. ~~`P1-9` RACI route alignment~~ → **[DONE]**
10. ~~`P2-10` Product-vs-internal classification~~ → **[DONE]** — `decision-intelligence`, `HITL`, `MCP` classified INTERNAL; `approvals` confirmed CONNECTED; `bulk-operations` moved to future UI backlog
11. ~~`P2-11` Generated client/OpenAPI drift cleanup~~ → **[DONE]** — MSW mock FIXED; SSE schema gap FIXED; TSX files updated to contract-first ✅
12. ~~`P2-12` API ownership/consumer documentation~~ → **[DONE]** — API classification table added below

---

## Remediation Matrix

| ID     | Priority | Area           | Status      | Issue                                            | Primary Action                                                | Evidence                                                                               |
| ------ | -------- | -------------- | ----------- | ------------------------------------------------ | ------------------------------------------------------------- | -------------------------------------------------------------------------------------- |
| API-01 | P0       | Alerts         | **DONE** ✅ | frontend path/shape mismatch                     | align alert list route + payload contract                     | `apps/api/src/alerts/router.py:231` + `apps/web/hooks/useAlerts.ts:72`                 |
| API-02 | P0       | Stakeholders   | **DONE** ✅ | frontend path mismatch                           | align stakeholder list path                                   | `apps/web/hooks/use-stakeholders.ts:76`                                                |
| API-03 | P0       | Analysis       | **DONE** ✅ | nonexistent SSE/progress endpoints               | define or remove streaming contract gap                       | `apps/web/components/features/analysis/AnalysisProgressTracker.tsx:60`                 |
| API-04 | P1       | Documents      | **DONE** ✅ | malformed parse path shape                       | add canonical to schema + regenerate client                   | `apps/api/src/documents/adapters/http/router.py:377` + `apps/web/schema/api.json`      |
| API-05 | P1       | Coherence      | **DONE** ✅ | mixed `/v0` + `/api` namespace                   | normalize coherence namespace to `/api/v1/coherence/...`      | `apps/api/src/coherence/router.py:24,35` + `apps/web/schema/api.json`                  |
| API-06 | P1       | Analysis       | **DONE** ✅ | flat `/analyze` route                            | normalize analysis namespace to `/api/v1/analysis/...`        | `apps/api/src/analysis/adapters/http/router.py:24` + `apps/web/components/features/`   |
| API-07 | P1       | Health         | **DONE** ✅ | path ambiguity `/health` vs `/api/v1/health`     | mount health router with both raw and prefixed paths          | `apps/api/src/main.py:253-254` + `apps/api/src/core/routers/health.py:33`              |
| API-08 | P1       | WBS            | **DONE** ✅ | hardcoded tenant "test-tenant-001" security risk | replace stub with `get_current_user` auth dependency          | `apps/api/src/wbs/adapters/http/router.py:118` + `get_current_user` import             |
| API-09 | P1       | RACI           | **DONE** ✅ | frontend/backend path mismatch                   | add global /raci endpoint + stakeholder_name + transform hook | `apps/api/src/stakeholders/adapters/http/raci_router.py` + `apps/web/hooks/useRaci.ts` |
| API-10 | P2       | Product scope  | **DONE** ✅ | backend-only groups lack classification          | classify connect vs internal                                  | `docs/audits/API_REMEDIATION_CHECKLIST_2026-03-20.md:121`                              |
| API-11 | P2       | API generation | **DONE** ✅ | generated client drift                           | reconcile OpenAPI/Orval outputs                               | `apps/web/schema/api.json` + `apps/web/lib/api/generated/analysis/analysis.ts`         |
| API-12 | P2       | Documentation  | **DONE** ✅ | no explicit consumer model                       | document API audience/ownership                               | `docs/audits/API_REMEDIATION_CHECKLIST_2026-03-20.md:258`                              |

> **Verification notes (2026-03-22):**
>
> - **API-02 DONE**: Backend `router.prefix="/stakeholders"`, endpoint `/projects/{project_id}`. Frontend calls `/stakeholders/projects/${projectId}` — correctly aligned.
> - **API-03 DONE**: Backend exposes `GET /api/v1/analysis/projects/{project_id}/process/stream` (SSE). Frontend updated to call the new normalized path in `AnalysisProgressTracker.tsx:138`, `ProcessingStepper.tsx:93` ✅.
> - **API-09 DONE**: Added global `GET /api/v1/raci` via `raci_global_router`. Added `stakeholder_name` to `RaciMatrixAssignment` DTO. `useRaci.ts` now handles nested matrix response and pivots to flat `RaciRow[]` with role→field mapping ✅. Backend has both global and project-scoped endpoints ✅.
> - **API-10B DONE** (already noted in checklist as completed 2026-03-21).
> - **API-01 DONE**: Backend has `GET /api/v1/alerts` at `alerts/router.py:231` — already correctly implemented. Frontend `useAlerts.ts:72` calls `/alerts` (proxied to `/api/v1/alerts`) ✅. Tests in `useAlerts.test.ts:82` verify contract ✅. Audit assumption was stale.
> - **API-04 DONE**: Backend already had canonical `/api/v1/documents/{document_id}/parse` at `router.py:377` + legacy alias at `router.py:383`. OpenAPI schema was stale (missing canonical). Added canonical to `schema/api.json`, regenerated Orval → `parseDocumentEndpointCanonical` now calls `/api/v1/documents/${documentId}/parse` ✅. Backend tests pass.
> - **API-05 DONE**: Normalized `coherence_router.prefix="/coherence"`, `dashboard_router.prefix="/coherence/dashboard"`. Mounted with `api_v1_prefix` in `main.py`. OpenAPI schema + Orval client regenerated. Proxy updated to handle both `/coherence/...` and `/api/coherence/...`. Tests pass.
> - **API-06 DONE**: `analysis_router.prefix="/analysis"`. `POST /api/v1/analysis/analyze` (was `/api/v1/analyze`), `GET /api/v1/analysis/projects/{project_id}/process/stream` (was `/api/v1/projects/{project_id}/process/stream`). OpenAPI schema updated, Orval client regenerated, frontend SSE calls updated ✅.
> - **API-07 DONE**: Health router now mounted twice in `main.py`: raw (`/health/...` for docker-compose) + with `api_v1_prefix` (`/api/v1/health/...` for gateway/deploy workflow). Generic `/health` returns `{status: "ok"}` (aligns with MSW mock and frontend test). `apps/web/schema/api.json` updated to canonical paths ✅.
> - **API-08 DONE**: Replaced `get_tenant_id()` stub with `get_current_user` DI across all 6 WBS endpoints. `tenant_id` now sourced from JWT-verified `current_user.tenant_id`. Main app loads correctly with updated routes ✅.
> - **API-10 DONE**: Inspected Orval generated clients and frontend codebase. `decision-intelligence` (LangGraph node, no frontend), `HITL` (LangGraph integration, no frontend), `MCP` (agent infrastructure, no frontend) → classified INTERNAL. `approvals` → CONNECTED (`reviewApprovalResource` in `evidence/page.tsx:233,265`, `approvals_router` feature-flagged in `main.py:305`). `bulk-operations` → future UI (router exists, Orval generated, no frontend hooks yet) ✅.
> - **API-11 DONE**: Added SSE endpoint to `schema/api.json` with `text/event-stream` content type and proper OpenAPI structure. `pnpm generate:api` → generated `streamProjectProcessingApiV1AnalysisProjectsProjectIdProcessStreamGet` + `getStreamProjectProcessingUrl()` helper. `ProcessingStepper.tsx` and `AnalysisProgressTracker.tsx` now call `getStreamProjectProcessingUrl(projectId, { access_token })` instead of hardcoded URL string. Frontend typecheck passes ✅, `ProcessingStepper.test.tsx` 8/8 tests pass ✅. Note: Orval generates REST client (`orvalApiClient<string>`) not `EventSource` — helper bridges the gap by returning URL string for `EventSource` constructor.
> - **API-12 DONE**: Added "API Ownership and Consumer Classification" section. Full classification of all 21 API groups: USER-FACING (11: Auth, Projects, Documents, Alerts, Stakeholders, WBS, Analysis, Coherence Dashboard, Approvals, RACI, Procurement), INTERNAL (8: Coherence Engine, Decision Intelligence, HITL, MCP, AI, Agents, Anonymizer, Shared Kernel), ADMIN-FACING (2: Health, Observability), BACKEND-ONLY (1: Bulk Operations). Feature-flagged groups tagged: Approvals (`FEATURE_APPROVAL_WORKFLOW`), RACI (`FEATURE_RACI_ENABLED`), Procurement (`FEATURE_PROCUREMENT_ENABLED`). Classification enables future audits to quickly determine consumer model without inference.

---

## Audit-Based Acceptance Criteria

This remediation plan should be considered complete when:

- every frontend-used API path maps to one real backend route
- every frontend-used API consumer expects the real backend payload shape
- no frontend code references nonexistent backend endpoints
- coherence, analysis, documents, and health routes follow a deliberate namespace/versioning policy
- backend-only surfaces are clearly classified as internal or intentionally non-UI
- generated client outputs are trustworthy enough to reduce handwritten drift

---

---

## API Ownership and Consumer Classification

Classification key:

- **USER-FACING**: Direct UI consumption via hooks/custom hooks. Requires stable contract and backward compatibility.
- **INTERNAL**: LangGraph pipeline nodes or backend infrastructure. No UI, no frontend hooks. Contract changes are internal-only.
- **ADMIN-FACING**: Operator/engineering dashboards (observability, health). Used by humans, but not end-users.
- **FEATURE-FLAGGED**: Conditionally mounted at runtime based on feature flags. May be absent in some deployments.

### API Group Classification

| Group                     | Classification           | Owner Module                                            | Frontend Consumer                                      | Feature Flag                  | Notes                                                                                                                                                                                               |
| ------------------------- | ------------------------ | ------------------------------------------------------- | ------------------------------------------------------ | ----------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Health**                | ADMIN-FACING             | `core/routers/health.py`                                | None (infra only)                                      | None                          | Runtime probes: `/health`, `/health/live`, `/health/ready`, `/health/worker`, `/health/circuit-breakers`. Mounted raw (`/health/...`) for docker-compose + with `api_v1_prefix` for gateway/deploy. |
| **Auth**                  | USER-FACING              | `core/auth/router.py`                                   | Via `@clerk/nextjs`                                    | None                          | User/company lifecycle: register, login, refresh, profile, password.                                                                                                                                |
| **Projects**              | USER-FACING              | `projects/adapters/http/router.py`                      | `lib/api/index.ts`, `hooks/useProjects.ts`             | None                          | Core tenant-scoped CRUD + project-level ops (health, stats, status, export, bulk docs/WBS).                                                                                                         |
| **Documents**             | USER-FACING              | `documents/adapters/http/router.py`                     | `lib/api/index.ts`                                     | None                          | Upload/list/download/delete + RAG `POST /projects/{id}/rag/answer`.                                                                                                                                 |
| **Alerts**                | USER-FACING              | `alerts/router.py`                                      | `hooks/useAlerts.ts`, `hooks/useProjectAlerts.ts`      | None                          | Alert lifecycle + evidence + bulk review/delete.                                                                                                                                                    |
| **Stakeholders**          | USER-FACING              | `stakeholders/adapters/http/router.py`                  | `hooks/use-stakeholders.ts`                            | None                          | Listing, creation, update, delete. RACI matrix via separate router.                                                                                                                                 |
| **WBS**                   | USER-FACING              | `wbs/adapters/http/router.py`                           | `lib/api/index.ts`                                     | None                          | WBS tree retrieval + item CRUD/move. `tenant_id` from JWT (not hardcoded).                                                                                                                          |
| **Coherence Engine**      | INTERNAL                 | `coherence/router.py`                                   | None                                                   | None                          | Standalone coherence evaluation. LangGraph pipeline node, not user-triggered. Orval client generated but unused.                                                                                    |
| **Coherence Dashboard**   | USER-FACING              | `coherence/router.py`                                   | `hooks/useProjectOverview.ts`                          | None                          | Persisted dashboard projection. `GET /coherence/dashboard/{project_id}` via proxy.                                                                                                                  |
| **Analysis**              | USER-FACING              | `analysis/adapters/http/router.py`                      | `ProcessingStepper.tsx`, `AnalysisProgressTracker.tsx` | None                          | Document analysis orchestration (`POST /analysis/analyze`) + SSE progress stream.                                                                                                                   |
| **Bulk Operations**       | BACKEND-ONLY (future UI) | `bulk_operations/router.py`                             | None                                                   | None                          | Async bulk job progress polling. Router exists, Orval generated, no frontend hooks yet. Future bulk job UI planned.                                                                                 |
| **Decision Intelligence** | INTERNAL                 | `modules/decision_intelligence/adapters/http/router.py` | None                                                   | None                          | LangGraph pipeline node (`decision_intelligence_node`). Orval client generated but unused.                                                                                                          |
| **HITL**                  | INTERNAL                 | `modules/hitl/adapters/http/router.py`                  | None                                                   | None                          | LangGraph pipeline integration. Review queue triggered by low-confidence AI. Orval client generated but unused.                                                                                     |
| **MCP**                   | INTERNAL                 | `core/mcp/router.py`                                    | None                                                   | None                          | Controlled DB view/function access for agent/tool workflows. Agent infrastructure only. Orval client generated but unused.                                                                          |
| **Approvals**             | USER-FACING              | `stakeholders/adapters/http/approvals_router.py`        | `evidence/page.tsx` (via `reviewApprovalResource`)     | `FEATURE_APPROVAL_WORKFLOW`   | Approval/reject/correct for AI-generated resources. Feature-flagged in `main.py:305`.                                                                                                               |
| **Observability**         | ADMIN-FACING             | `core/observability/router.py`                          | None (infra only)                                      | None                          | System status, recent analyses, performance snapshot. Engineering/operator visibility.                                                                                                              |
| **RACI**                  | USER-FACING              | `stakeholders/adapters/http/raci_router.py`             | `hooks/useRaci.ts`                                     | `FEATURE_RACI_ENABLED`        | Stakeholder responsibility matrix. Global (`GET /raci`) + project-scoped (`GET /projects/{id}/raci`).                                                                                               |
| **Procurement**           | USER-FACING              | (separate module)                                       | `hooks/useProcurement.ts`                              | `FEATURE_PROCUREMENT_ENABLED` | BOM management, supplier tracking. Conditionally registered in `main.py`.                                                                                                                           |
| **Gamification**          | USER-FACING              | `gamification/`                                         | None                                                   | None                          | User engagement signals. Endpoint exists but no active frontend hook.                                                                                                                               |
| **AI**                    | INTERNAL                 | `ai/`                                                   | None                                                   | None                          | LLM clients, prompts. Backend infrastructure, not exposed via HTTP.                                                                                                                                 |
| **Agents**                | INTERNAL                 | `agents/`                                               | None                                                   | None                          | Celery task definitions. Backend-only queue workers, not HTTP-exposed.                                                                                                                              |
| **Anonymizer**            | INTERNAL                 | `anonymizer/`                                           | None                                                   | None                          | GDPR PII anonymization. Document preprocessing, not HTTP-exposed.                                                                                                                                   |
| **Shared Kernel**         | INTERNAL                 | `shared_kernel/`                                        | None                                                   | None                          | Cross-module shared types/utilities. Not HTTP-exposed.                                                                                                                                              |

### Classification Summary

| Classification      | Count | Groups                                                                                                                 |
| ------------------- | ----- | ---------------------------------------------------------------------------------------------------------------------- |
| **USER-FACING**     | 9     | Auth, Projects, Documents, Alerts, Stakeholders, WBS, Analysis, Coherence Dashboard, Approvals, RACI, Procurement (11) |
| **INTERNAL**        | 8     | Coherence Engine, Decision Intelligence, HITL, MCP, AI, Agents, Anonymizer, Shared Kernel                              |
| **ADMIN-FACING**    | 2     | Health, Observability                                                                                                  |
| **BACKEND-ONLY**    | 1     | Bulk Operations                                                                                                        |
| **FEATURE-FLAGGED** | 3     | Approvals (`FEATURE_APPROVAL_WORKFLOW`), RACI (`FEATURE_RACI_ENABLED`), Procurement (`FEATURE_PROCUREMENT_ENABLED`)    |

> **Last verified**: 2026-03-22. Update this table when new API groups are added or classifications change.

## Notes

- This document is intentionally action-oriented and derived from the formal audit.
- It does not replace the audit; it operationalizes it.
- Detailed evidence and route-level commentary remain in:
  - `docs/audits/API_AUDIT_BACKEND_FRONTEND_2026-03-20.md`
