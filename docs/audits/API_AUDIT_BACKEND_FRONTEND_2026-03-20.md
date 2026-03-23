# C2Pro API Audit Report

Date: `2026-03-20`
Scope: `Backend API surface audit + frontend integration audit`
Mode: `Read-only audit; no application code modified`
Auditor: `OpenCode / Team Alpha: Sentinel`

---

## Objective

This audit verifies:

1. Which backend APIs are actually registered and available in code.
2. Whether the APIs visible from the API root match real backend implementation.
3. Which APIs appear to be missing, duplicated, legacy, or path-inconsistent.
4. Whether those backend APIs are connected correctly from the frontend.
5. The real functional role of each API group in the product.

---

## Executive Summary

The backend API surface is broadly present and covers the domains listed from the API root: health, auth, projects, documents, alerts, bulk operations, observability, decision intelligence, HITL, WBS, analysis, MCP, coherence, stakeholders, and approvals.

However, this audit found several important integration and contract issues:

- Backend route coverage is mostly complete, but several paths are inconsistent or legacy-shaped.
- A few visible routes are likely malformed or oddly mounted, especially document parse, coherence, and analysis routes.
- Frontend integration is partial: some domains are well connected (`projects`, `documents`, `observability`, coherence dashboard), while others are missing or broken (`alerts` flat list path, `stakeholders`, `RACI`, `analysis` SSE, `decision-intelligence`, `HITL`, `MCP`, `approvals`).
- Some frontend consumers assume the wrong response shape or wrong URL path even when the backend route exists.
- The API root view is not enough to prove end-to-end correctness; path/shape/auth mismatches still exist behind the listed endpoints.

Overall conclusion:

- Backend API registration status: `Substantially implemented`
- Frontend integration status: `Partial and uneven`
- Missing API risk: `Low for backend existence, medium for usable frontend connectivity`
- Audit recommendation: `Keep backend surface, but normalize path contracts and complete frontend wiring before claiming full API coverage`

---

## Method

- Reviewed router registration in `apps/api/src/main.py`
- Reviewed active router files for each backend domain
- Compared actual routes against the API list supplied by the user
- Reviewed frontend API clients, proxy logic, generated services, hooks, and direct fetch/EventSource usage
- Did not modify application code; only this report was created

---

## Source Of Truth Used In This Audit

Primary backend registration:

- `apps/api/src/main.py:228`
- `apps/api/src/main.py:252`
- `apps/api/src/config.py:262`

Primary frontend integration layer:

- `apps/web/app/api/[...proxy]/route.ts:9`
- `apps/web/config/env.ts:1`
- `apps/web/lib/api/client.ts:6`
- `apps/web/lib/api/config.ts:6`
- `apps/web/orval.config.ts:3`

---

## Backend API Audit

### Registered Backend Surface

By code, the default backend app exposes the user-visible groups plus `/`, with feature-flagged extras for RACI and procurement.

### Backend API Group Review

| Group                 | Visible In API Root | Code Status | Real Use In Project                                                    | Main Evidence                                                           |
| --------------------- | ------------------- | ----------- | ---------------------------------------------------------------------- | ----------------------------------------------------------------------- |
| Root                  | Yes                 | Present     | API landing / basic root response                                      | `apps/api/src/main.py:228`                                              |
| Health                | Yes                 | Present     | Liveness, readiness, worker health, dependency status                  | `apps/api/src/core/routers/health.py:33`                                |
| Auth                  | Yes                 | Present     | Register/login/refresh/profile/password lifecycle                      | `apps/api/src/core/auth/router.py:38`                                   |
| Projects              | Yes                 | Present     | Tenant-scoped project CRUD and project-level operations                | `apps/api/src/projects/adapters/http/router.py:25`                      |
| Documents             | Yes                 | Present     | Upload/list/download/delete and project RAG question answering         | `apps/api/src/documents/adapters/http/router.py:71`                     |
| Alerts                | Yes                 | Present     | Alert creation, review, evidence, resolve, history, bulk review/delete | `apps/api/src/alerts/router.py:30`                                      |
| Bulk Operations       | Yes                 | Present     | Progress polling for async bulk jobs                                   | `apps/api/src/bulk_operations/router.py:19`                             |
| Observability         | Yes                 | Present     | System status, recent analyses, performance snapshot                   | `apps/api/src/core/observability/router.py:9`                           |
| Decision Intelligence | Yes                 | Present     | Orchestrated AI execution flow                                         | `apps/api/src/modules/decision_intelligence/adapters/http/router.py:25` |
| HITL                  | Yes                 | Present     | Review queue, approve/reject/release, SLA escalation                   | `apps/api/src/modules/hitl/adapters/http/router.py:32`                  |
| WBS                   | Yes                 | Present     | WBS tree retrieval and item CRUD/move                                  | `apps/api/src/wbs/adapters/http/router.py:35`                           |
| Analysis              | Yes                 | Present     | Analysis orchestration entrypoint                                      | `apps/api/src/analysis/adapters/http/router.py:13`                      |
| MCP                   | Yes                 | Present     | Controlled DB view/function access and generic MCP execute             | `apps/api/src/core/mcp/router.py:44`                                    |
| Coherence Engine      | Yes                 | Present     | Standalone coherence evaluation                                        | `apps/api/src/coherence/router.py:22`                                   |
| Coherence Dashboard   | Yes                 | Present     | Persisted coherence dashboard projection                               | `apps/api/src/coherence/router.py:33`                                   |
| Stakeholders          | Yes                 | Present     | Stakeholder listing, creation, update, delete                          | `apps/api/src/stakeholders/adapters/http/router.py:35`                  |
| Approvals             | Yes                 | Present     | Approval/reject/correct for AI-generated resources                     | `apps/api/src/stakeholders/adapters/http/approvals_router.py:27`        |

### Backend Findings By Group

#### Health

- `GET /health/live`, `/health/ready`, `/health`, `/health/circuit-breakers`, `/health/worker` all exist
- `GET /api/v1/health/worker` also exists as an alias
- Real use: runtime probes, dependency health, circuit-breaker visibility, Celery worker checks
- Note: `/health` and `/health/ready` are effectively overlapping readiness-style paths

Evidence:

- `apps/api/src/core/routers/health.py:206`
- `apps/api/src/main.py:244`

#### Authentication

- All listed auth endpoints exist
- Hidden extra endpoint found: `GET /api/v1/auth/health`
- Real use: user/company bootstrap and authenticated current-user profile lifecycle

Evidence:

- `apps/api/src/core/auth/router.py:382`

#### Projects

- All listed project endpoints exist
- Real use: project CRUD plus project-scoped bulk operations, export, and budget view
- Note: this router owns several non-core project actions that might later deserve domain splitting

Evidence:

- `apps/api/src/projects/adapters/http/router.py:614`
- `apps/api/src/projects/adapters/http/router.py:668`
- `apps/api/src/projects/adapters/http/router.py:759`
- `apps/api/src/projects/adapters/http/router.py:823`

#### Documents

- All user-listed document capabilities exist in code
- Important path inconsistency found:
  - parse route is `POST /api/v1/{document_id}/parse`
  - expected canonical shape would likely be `POST /api/v1/documents/{document_id}/parse`
- Real use: upload, storage retrieval, delete, parse, and project-level RAG answering

Evidence:

- `apps/api/src/documents/adapters/http/router.py:338`

#### Alerts

- All listed alert routes exist in the active router
- Real use: operational review workflow for analysis/coherence findings
- Important note: active router is `src/alerts/router.py`; an alternate analysis alerts router also exists in code but is not the active public router

Evidence:

- `apps/api/src/alerts/router.py:30`
- `apps/api/src/analysis/adapters/http/alerts_router.py:103`

#### Bulk Operations

- Listed endpoint exists
- Real use: progress polling only; the actual bulk creation/upload actions live elsewhere under project routes

Evidence:

- `apps/api/src/bulk_operations/router.py:19`

#### Observability

- All listed endpoints exist
- Real use: operator-facing backend runtime visibility, not end-user product functionality

Evidence:

- `apps/api/src/core/observability/router.py:24`

#### Decision Intelligence

- Listed endpoint exists
- Real use: execute full decision-intelligence flow from backend orchestration layer

Evidence:

- `apps/api/src/modules/decision_intelligence/adapters/http/router.py:131`

#### HITL

- All listed endpoints exist
- Real use: queue-based human review and release workflow for AI-generated items

Evidence:

- `apps/api/src/modules/hitl/adapters/http/router.py:82`

#### WBS

- All listed endpoints exist
- Real use: WBS browsing and editing
- Important concern: tenant lookup inside this router still appears hardcoded, which makes route registration real but implementation maturity questionable

Evidence:

- `apps/api/src/wbs/adapters/http/router.py:118`

#### Analysis

- Listed endpoint exists
- Real use: document analysis entrypoint
- Important path inconsistency: mounted at `/api/v1/analyze` instead of a namespaced `/api/v1/analysis/...`

Evidence:

- `apps/api/src/analysis/adapters/http/router.py:47`

#### MCP

- All listed MCP endpoints exist
- Real use: controlled DB access surface for AI/agent workflows and admin/runtime introspection

Evidence:

- `apps/api/src/core/mcp/router.py:468`

#### Coherence Engine / Dashboard

- Both listed routes exist
- Real use:
  - `/v0/coherence/evaluate`: direct coherence evaluation
  - `/api/coherence/dashboard/{project_id}`: persisted dashboard projection
- Important path inconsistency: these are outside the dominant `/api/v1` namespace

Evidence:

- `apps/api/src/coherence/router.py:22`
- `apps/api/src/coherence/router.py:118`

#### Stakeholders

- All listed endpoints exist
- Real use: stakeholder CRUD derived from extraction/manual edits
- Path shape is unusual versus REST expectations: `/api/v1/stakeholders/projects/{project_id}` rather than `/api/v1/projects/{project_id}/stakeholders`

Evidence:

- `apps/api/src/stakeholders/adapters/http/router.py:77`

#### Approvals

- Listed endpoint exists
- Real use: approval/rejection/correction flow for AI-generated resources
- Note: implementation is generic at path level but still stakeholder-oriented in code organization

Evidence:

- `apps/api/src/stakeholders/adapters/http/approvals_router.py:61`

---

## Backend Missing / Inconsistent / Risky APIs

### APIs visible from the root but suspicious in backend code

1. `POST /api/v1/{document_id}/parse`
   - Exists, but path shape is likely wrong
   - Should likely be under `/documents/{document_id}/parse`
   - Evidence: `apps/api/src/documents/adapters/http/router.py:338`

2. `POST /api/v1/analyze`
   - Exists, but route namespace is unusually flat
   - Suggests legacy or shortcut mounting
   - Evidence: `apps/api/src/analysis/adapters/http/router.py:47`

3. `POST /v0/coherence/evaluate` and `GET /api/coherence/dashboard/{project_id}`
   - Exist, but versioning and path style are inconsistent with `/api/v1`
   - Evidence: `apps/api/src/coherence/router.py:22`

4. WBS routes
   - Exist, but tenant handling appears hardcoded in implementation
   - Evidence: `apps/api/src/wbs/adapters/http/router.py:118`

### APIs in code not visible in the supplied root list

- `GET /api/v1/auth/health`
- Feature-flagged RACI routes:
  - `GET /api/v1/projects/{project_id}/raci`
  - `PUT /api/v1/assignments`
- Feature-flagged procurement routes when enabled

Evidence:

- `apps/api/src/core/auth/router.py:382`
- `apps/api/src/stakeholders/adapters/http/raci_router.py:76`
- `apps/api/src/procurement/adapters/http/router.py:43`

### APIs from the supplied list that are not outright missing, but do not exist in the most canonical expected form

- No full backend group from the provided list is absent.
- The main issues are path-shape inconsistency rather than total endpoint absence.

---

## Frontend Integration Audit

## Frontend API Access Layers

| Layer                 | Status        | Role                                                       | Evidence                                          |
| --------------------- | ------------- | ---------------------------------------------------------- | ------------------------------------------------- |
| Proxy route           | Present       | Forwards browser calls to backend; special-cases coherence | `apps/web/app/api/[...proxy]/route.ts:9`          |
| Env config            | Present       | Defines base URL handling                                  | `apps/web/config/env.ts:1`                        |
| Axios client          | Present       | Auth + tenant header injection                             | `apps/web/lib/api/client.ts:6`                    |
| Generated client      | Partial/stale | Only partially exported/generated                          | `apps/web/lib/api/generated/index.ts:1`           |
| Custom services/hooks | Present       | Real project/document/coherence/alert usage                | `apps/web/lib/api/index.ts:28`, `apps/web/hooks/` |

## Frontend Connection Matrix

| API Group             | Frontend Status         | Audit Result                                                                       | Evidence                                                                                                           |
| --------------------- | ----------------------- | ---------------------------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------------ |
| Health                | Weak / likely broken    | Frontend expects `/api/v1/health`, backend health is mainly rooted at `/health`    | `apps/web/src/tests/integration/msw/health.test.tsx:5`, `apps/api/src/core/routers/health.py:33`                   |
| Auth                  | Weak / mostly unused    | App auth is Clerk-driven; custom auth client is path-bugged                        | `apps/web/lib/api/auth.ts:90`                                                                                      |
| Projects              | Connected               | Main list/create flows are wired                                                   | `apps/web/hooks/useProjects.ts:7`, `apps/web/app/(app)/projects/new/page.tsx:44`                                   |
| Documents             | Connected               | Upload/list/delete/download are used                                               | `apps/web/hooks/useProjectDocuments.ts:76`, `apps/web/components/features/documents/DocumentUploadDropzone.tsx:63` |
| Alerts                | Partial / broken        | Project alert list is used, but flat alerts endpoint and response shapes are wrong | `apps/web/hooks/useProjectAlerts.ts:74`, `apps/web/hooks/useAlerts.ts:67`                                          |
| Bulk Operations       | Not clearly connected   | No strong frontend evidence found                                                  | -                                                                                                                  |
| Observability         | Connected               | Status and analyses are fetched by frontend                                        | `apps/web/app/(app)/observability/page.tsx:35`                                                                     |
| Decision Intelligence | Not connected           | No frontend usage found                                                            | `apps/api/src/modules/decision_intelligence/adapters/http/router.py:131`                                           |
| HITL                  | Not connected           | No frontend usage found                                                            | `apps/api/src/modules/hitl/adapters/http/router.py:32`                                                             |
| WBS                   | Weak / ambiguous        | Backend exists, frontend page appears mock-oriented                                | `apps/web/app/dashboard/projects/[id]/wbs/page.tsx:33`                                                             |
| Analysis              | Not connected correctly | Frontend expects SSE/progress paths that backend does not expose                   | `apps/web/components/features/analysis/AnalysisProgressTracker.tsx:60`                                             |
| MCP                   | Not connected           | No frontend usage found                                                            | `apps/api/src/core/mcp/router.py:44`                                                                               |
| Coherence Dashboard   | Connected but fragile   | Used in dashboard/project pages; relies on special-case proxy/path handling        | `apps/web/lib/api/generated/services/DashboardService.ts:31`                                                       |
| Stakeholders          | Broken                  | Frontend path does not match backend route shape                                   | `apps/web/hooks/use-stakeholders.ts:76`                                                                            |
| Approvals             | Not connected           | No frontend usage found                                                            | `apps/api/src/stakeholders/adapters/http/approvals_router.py:61`                                                   |

## Frontend Integration Findings

### Correctly or mostly correctly connected

- `projects`
- `documents`
- `observability`
- coherence dashboard (`/api/coherence/dashboard/{project_id}`), but only through the custom proxy rule

### Present in backend but missing from frontend usage

- `decision-intelligence`
- `HITL`
- `MCP`
- `approvals`
- likely `bulk-operations` progress polling as a first-class frontend feature

### Present on both sides but broken or inconsistent

1. Alerts
   - frontend calls flat `GET /alerts`
   - backend does not expose a live flat GET alerts endpoint
   - project alert hooks also assume array payloads while backend returns wrapper objects
   - Evidence:
     - `apps/web/hooks/useAlerts.ts:67`
     - `apps/web/hooks/useProjectAlerts.ts:74`
     - `apps/api/src/alerts/router.py:103`

2. Stakeholders
   - frontend calls `/stakeholders?project_id=...`
   - backend expects `/api/v1/stakeholders/projects/{project_id}`
   - Evidence:
     - `apps/web/hooks/use-stakeholders.ts:77`
     - `apps/api/src/stakeholders/adapters/http/router.py:77`

3. RACI
   - frontend calls `/raci`
   - backend feature-flagged router expects `/projects/{project_id}/raci`
   - Evidence:
     - `apps/web/hooks/useRaci.ts:36`
     - `apps/api/src/stakeholders/adapters/http/raci_router.py:76`

4. Analysis progress / SSE
   - frontend expects non-existent streaming endpoints
   - backend only exposes `POST /api/v1/analyze`
   - Evidence:
     - `apps/web/components/features/analysis/AnalysisProgressTracker.tsx:60`
     - `apps/web/components/features/processing/ProcessingStepper.tsx:80`
     - `apps/api/src/analysis/adapters/http/router.py:47`

5. Health
   - frontend assumptions skew toward `/api/v1/health`
   - backend health root is primarily `/health`
   - Evidence:
     - `apps/web/src/tests/integration/msw/health.test.tsx:5`
     - `apps/api/src/core/routers/health.py:33`

6. Coherence dashboard
   - works through proxy special-casing, but pathing is fragile because backend lives outside `/api/v1`
   - Evidence:
     - `apps/web/app/api/[...proxy]/route.ts:37`
     - `apps/api/src/coherence/router.py:33`

---

## Missing API Assessment

### Backend missing APIs

Strictly from the supplied API-root list:

- No major backend domain is completely missing.
- The main backend concerns are not absence, but path inconsistency and implementation maturity.

### Frontend missing API integrations

The following backend API groups appear unconnected or not meaningfully integrated in the frontend:

- `decision-intelligence`
- `HITL`
- `MCP`
- `approvals`
- likely `bulk-operations` progress polling

The following appear connected but not correctly:

- `alerts`
- `stakeholders`
- `RACI`
- `analysis` progress/SSE
- `health`

---

## Business Use Comments By API Group

| API Group             | Real Use In Project                                             |
| --------------------- | --------------------------------------------------------------- |
| Health                | Runtime probes and operator diagnostics                         |
| Auth                  | User/company lifecycle and current-user identity                |
| Projects              | Core tenant-scoped project management backbone                  |
| Documents             | Contract/document ingestion, storage, and RAG access            |
| Alerts                | Risk/coherence finding review and lifecycle handling            |
| Bulk Operations       | Tracking long-running project-level batch jobs                  |
| Observability         | Engineering/operator visibility into system behavior            |
| Decision Intelligence | AI orchestration entrypoint for higher-level decision workflows |
| HITL                  | Human review gate for AI-generated outputs                      |
| WBS                   | Breakdown structure management for project planning             |
| Analysis              | Document analysis/orchestration trigger                         |
| MCP                   | Controlled backend data access for agent/tool workflows         |
| Coherence Engine      | Contract/project coherence scoring                              |
| Coherence Dashboard   | User-facing summarized coherence health view                    |
| Stakeholders          | Stakeholder extraction and manual stakeholder management        |
| Approvals             | Controlled review of AI-generated resources                     |

---

## Audit Verdict

### Backend

- `Implemented`: yes, across all major visible groups
- `Cleanly normalized`: no
- `Notable risks`: route inconsistency, likely malformed document parse path, legacy/flat analysis path, hardcoded tenant behavior in WBS, mixed versioning in coherence routes

### Frontend

- `Fully connected to backend`: no
- `Strongest coverage`: projects, documents, observability, coherence dashboard
- `Missing or broken integration`: alerts, stakeholders, RACI, analysis streaming, health assumptions, and several complete backend groups with no frontend usage

### Formal conclusion

The backend API catalog visible from the API root is largely real and implemented, but it is not yet fully normalized as a production-quality contract surface. The frontend only consumes part of that surface correctly. Several backend APIs are present but not connected, and several connected APIs are path- or payload-misaligned.

This should be treated as:

- a `backend API existence pass` -> mostly successful
- a `frontend integration pass` -> incomplete and requiring follow-up normalization

---

## Recommended Follow-Up Audit Actions

1. Normalize backend path contracts for:
   - documents parse
   - analysis namespace
   - coherence namespace/versioning
   - stakeholders nesting shape

2. Validate frontend contract alignment for:
   - alerts payload shapes
   - stakeholders paths
   - RACI path usage
   - health endpoint target
   - SSE/progress endpoints for analysis

3. Decide whether these backend groups should be product-connected or intentionally backend-only:
   - MCP
   - HITL
   - approvals
   - decision-intelligence
   - bulk operation polling

4. Run a second-stage contract audit after frontend normalization to confirm:
   - every used frontend path maps to one real backend route
   - every response shape matches actual frontend expectations
   - no special proxy exceptions are hiding broken base-path design

---

## Key Evidence Files

- `apps/api/src/main.py:252`
- `apps/api/src/core/routers/health.py:33`
- `apps/api/src/core/auth/router.py:38`
- `apps/api/src/projects/adapters/http/router.py:25`
- `apps/api/src/documents/adapters/http/router.py:71`
- `apps/api/src/alerts/router.py:30`
- `apps/api/src/core/observability/router.py:9`
- `apps/api/src/modules/decision_intelligence/adapters/http/router.py:25`
- `apps/api/src/modules/hitl/adapters/http/router.py:32`
- `apps/api/src/wbs/adapters/http/router.py:35`
- `apps/api/src/analysis/adapters/http/router.py:13`
- `apps/api/src/core/mcp/router.py:44`
- `apps/api/src/coherence/router.py:22`
- `apps/api/src/stakeholders/adapters/http/router.py:35`
- `apps/api/src/stakeholders/adapters/http/approvals_router.py:27`
- `apps/web/app/api/[...proxy]/route.ts:9`
- `apps/web/config/env.ts:1`
- `apps/web/lib/api/client.ts:6`
- `apps/web/hooks/useProjects.ts:7`
- `apps/web/hooks/useProjectDocuments.ts:76`
- `apps/web/hooks/useProjectAlerts.ts:74`
- `apps/web/hooks/useAlerts.ts:67`
- `apps/web/hooks/use-stakeholders.ts:76`
- `apps/web/hooks/useRaci.ts:36`
- `apps/web/app/(app)/observability/page.tsx:35`
- `apps/web/lib/api/generated/services/DashboardService.ts:31`
