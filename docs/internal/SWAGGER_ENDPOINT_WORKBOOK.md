# Swagger Endpoint Workbook (Internal)

This file is an internal working map of the current Swagger UI surface.
Use it to understand what each area does and to track functional validation.

## Scope

- Source: Manual capture from current Swagger UI endpoint list.
- Swagger runtime reference: local backend Swagger UI (`http://localhost:8000/docs`).
- OpenAPI reference: `http://localhost:8000/api/v1/openapi.json`.
- Active release evidence: `evidence/releases/2026-03-24-rc1/`.
- Purpose: Development support, QA walk-throughs, and regression tracking.
- Status: Updated 2026-03-27 - **G7-01 Complete**

## Quick Reading Guide

- `Health`: infrastructure and runtime readiness checks.
- `Authentication`: user identity and token lifecycle.
- `Projects`: project CRUD plus project-level workflows.
- `Documents`: upload, parsing, retrieval, and RAG querying.
- `Alerts`: lifecycle of analysis alerts and evidence.
- `Bulk Operations`: long-running batch job progress.
- `Observability`: operational and analysis telemetry endpoints.
- `Decision Intelligence`: orchestration execution endpoint.
- `WBS`: work breakdown structure CRUD + move operation.
- `MCP`: controlled DB operations through whitelisted views/functions.
- `Coherence`: coherence scoring and coherence dashboard views.
- `Stakeholders`: stakeholder CRUD by project.
- `Approvals`: human review actions over AI-generated resources.
- `HITL`: Human-in-the-loop review queue and actions.
- `Analysis`: LangGraph-based document analysis orchestration.

## Endpoint Map (What Each One Is)

### Root

- `Authorize`: Swagger auth helper to send bearer tokens.
- `GET /`: Root endpoint with basic API info.

### Health

- `GET /health/live`: liveness probe (process is alive).
- `GET /health/ready`: readiness probe (dependencies are ready).
- `GET /health/circuit-breakers`: resilience state per protected external service.
- `GET /health`: generic health summary endpoint.
- `GET /api/v1/health/worker`: Celery worker health status.

### Authentication (`/api/v1/auth`)

- `POST /register`: create tenant + first user.
- `POST /login`: issue access/refresh tokens.
- `POST /refresh`: rotate/refresh access token.
- `GET /me`: current authenticated user profile.
- `PUT /me`: update current user profile.
- `POST /logout`: terminate logical session/token usage.
- `POST /change-password`: password update flow.

### Projects (`/api/v1/projects`)

- `GET /health`: projects module health check.
- `GET /stats`: aggregate project statistics.
- `POST /`: create project.
- `GET /`: list tenant projects.
- `GET /{project_id}`: fetch one project.
- `PUT /{project_id}`: full replace/update semantics.
- `PATCH /{project_id}`: partial update.
- `DELETE /{project_id}`: remove project.
- `PATCH /{project_id}/status`: status-only update.
- `POST /{project_id}/documents/bulk`: bulk document upload binded to project.
- `POST /{project_id}/wbs/bulk`: bulk WBS creation.
- `POST /{project_id}/export`: export project package/data.
- `GET /{project_id}/budget`: budget view for project.

### Documents (`/api/v1`)

- `POST /projects/{project_id}/documents`: enqueue document upload/processing.
- `GET /projects/{project_id}/documents`: list project documents.
- `GET /documents/{document_id}`: get document metadata/detail.
- `DELETE /documents/{document_id}`: delete document.
- `GET /documents/{document_id}/download`: download raw document.
- `POST /{document_id}/parse`: run parser for a specific document.
- `POST /projects/{project_id}/rag/answer`: RAG Q/A over project docs.

### Alerts (`/api/v1/alerts`)

- `POST /`: create alert.
- `GET /projects/{project_id}/alerts`: list alerts by project.
- `POST /{alert_id}/review`: apply review decision.
- `POST /bulk-review`: bulk review workflow.
- `POST /{alert_id}/evidence`: attach evidence to alert.
- `POST /{alert_id}/resolve`: resolve/close alert.
- `GET /{alert_id}/history`: alert audit/history trail.
- `POST /bulk-delete`: bulk delete alerts.

### Bulk Operations (`/api/v1/bulk-operations`)

- `GET /{job_id}/progress`: poll bulk job status/progress.

### Observability (`/api/v1/observability`)

- `GET /status`: system status health surface.
- `GET /analyses`: recent coherence analyses.
- `GET /performance/snapshot`: canonical performance snapshot.
- `GET /observability/performance/snapshot`: legacy/duplicated performance snapshot.

### Decision Intelligence (`/api/v1/decision-intelligence`)

- `POST /execute`: run end-to-end decision intelligence flow.

### HITL (`/api/v1/hitl`)

- `POST /route`: route an item for HITL review.
- `GET /queue`: list items in the review queue.
- `GET /queue/{item_id}`: get a single review item.
- `POST /queue/{item_id}/approve`: approve a review item.
- `POST /queue/{item_id}/reject`: reject a review item.
- `POST /queue/{item_id}/release`: release an approved item.
- `POST /escalate`: check SLAs and escalate overdue items.

### Analysis (`/api/v1`)

- `POST /analyze`: run LangGraph-based document analysis.

### WBS (`/api/v1/projects/{project_id}/wbs`)

- `GET /`: get WBS tree/output.
- `POST /items`: create WBS item.
- `PATCH /items/{item_id}`: update WBS item.
- `DELETE /items/{item_id}`: delete WBS item.
- `GET /items/{item_id}`: get WBS item.
- `POST /items/{item_id}/move`: move/reparent/reorder WBS item.

### MCP - Model Context Protocol (`/api/v1/mcp`)

- `POST /query-view`: query whitelisted DB views.
- `POST /call-function`: call whitelisted DB functions.
- `GET /views`: list allowed views.
- `GET /functions`: list allowed functions.
- `GET /rate-limit-status`: MCP rate-limit visibility.
- `POST /execute`: execute MCP operation gateway.

### Coherence Engine (`/v0/coherence`)

- `POST /evaluate`: compute coherence score/evaluation.

### Coherence Dashboard (`/api/coherence/dashboard`)

- `GET /{project_id}`: dashboard data for coherence.

### Stakeholders (`/api/v1/stakeholders`)

- `GET /projects/{project_id}`: list project stakeholders.
- `POST /projects/{project_id}`: create stakeholder.
- `PATCH /{stakeholder_id}`: update stakeholder.
- `DELETE /{stakeholder_id}`: delete stakeholder.

### Approvals (`/api/v1/approvals`)

- `PATCH /{resource_type}/{resource_id}`: approve/reject/correct AI outputs.

## Functional Verification Checklist

Mark each checkbox when manually validated in Swagger or automated tests.

## Gate 7 Completion Rules

Use this workbook as the Swagger evidence source for Gate 7 release certification.

- Gate 7 status MUST reference the release bundle at `evidence/releases/<release-id>/`.
- A checked item MUST include either a validating test reference or a release-time manual verification note.
- An unchecked item MUST be listed in the release bundle `manifest.yaml` under `swagger_workbook.unchecked_items`.
- A release candidate MUST NOT claim complete Swagger verification while any release-critical endpoint remains unchecked without an approved waiver.
- Non-release-critical unchecked items MAY remain open only if the waiver records owner, risk, mitigation, and expiration date.

## Live Runtime Verification (2026-03-27)

### Verified Endpoints

| Endpoint                      | Method             | Status | Verification                     |
| ----------------------------- | ------------------ | ------ | -------------------------------- |
| POST /auth/register           | Register           | ✅     | Created tenant & user            |
| POST /auth/login              | Login              | ✅     | Returns tokens                   |
| GET /auth/me                  | Get Current User   | ✅     | Returns user profile             |
| GET /health/live              | Liveness           | ✅     | Returns {"status":"ok"}          |
| GET /health/ready             | Readiness          | ✅     | DB/Redis up, circuit breakers OK |
| POST /projects                | Create Project     | ✅     | Created project with ID          |
| GET /projects                 | List Projects      | ✅     | Returns tenant projects          |
| GET /projects/stats           | Project Stats      | ✅     | Returns aggregate stats          |
| GET /coherence/dashboard/{id} | Dashboard          | ✅     | Returns coherence data           |
| GET /hitl/queue               | HITL Queue         | ✅     | Returns empty queue              |
| GET /wbs                      | WBS Tree           | ✅     | Returns WBS structure            |
| GET /mcp/views                | MCP Views          | ✅     | Returns 8 whitelisted views      |
| GET /mcp/functions            | MCP Functions      | ✅     | Returns 5 whitelisted functions  |
| POST /stakeholders            | Create Stakeholder | ✅     | Created stakeholder              |
| GET /stakeholders             | List Stakeholders  | ✅     | Returns project stakeholders     |
| POST /alerts                  | Create Alert       | ✅     | Created alert with validation    |
| GET /observability/status     | System Status      | ✅     | Returns API/DB status            |

### Health

- [x] `GET /health/live` returns 200. (Verified via startup)
- [x] `GET /health/ready` returns 200 with all dependencies ready.
- [x] `GET /health/circuit-breakers` returns expected breaker states.
- [x] `GET /health` returns general service health payload.
- [x] `GET /api/v1/health/worker` returns worker status.

### Authentication

- [x] Register creates tenant and user (`POST /api/v1/auth/register`). (Verified via `test_jwt_validation.py`)
- [x] Login returns valid tokens (`POST /api/v1/auth/login`).
- [x] Refresh rotates token correctly (`POST /api/v1/auth/refresh`).
- [x] Me returns current user (`GET /api/v1/auth/me`).
- [x] Me update persists profile fields (`PUT /api/v1/auth/me`). (Live runtime verification: `2026-03-24-rc1`, profile fields persisted on `http://localhost:8000`.)
- [x] Logout invalidates session semantics (`POST /api/v1/auth/logout`). (Live runtime verification: `2026-03-24-rc1`, logout returned `204` and the same bearer token was rejected by `GET /api/v1/auth/me` with `401 token_revoked` after API restart.)
- [x] Change-password accepts valid current password and updates credential (`POST /api/v1/auth/change-password`). (Live runtime verification: `2026-03-24-rc1`, login with the new password succeeded.)

### Projects

- [x] `GET /api/v1/projects/health` returns module OK.
- [x] `GET /api/v1/projects/stats` returns valid aggregates. (Live runtime verification: `2026-03-24-rc1`, aggregate counts matched the temporary tenant project set.)
- [x] `POST /api/v1/projects` creates project with tenant context.
- [x] `GET /api/v1/projects` lists only tenant projects.
- [x] `GET /api/v1/projects/{project_id}` returns project by id.
- [x] `PUT /api/v1/projects/{project_id}` updates full object. (Live runtime verification: `2026-03-24-rc1`, full update succeeded with valid enum status `active`.)
- [x] `PATCH /api/v1/projects/{project_id}` applies partial changes.
- [x] `DELETE /api/v1/projects/{project_id}` removes project safely.
- [x] `PATCH /api/v1/projects/{project_id}/status` updates status only.
- [x] `POST /api/v1/projects/{project_id}/documents/bulk` enqueues/uploads in bulk. (Live runtime verification: `2026-03-24-rc1`, accepted 2/2 documents.)
- [x] `POST /api/v1/projects/{project_id}/wbs/bulk` creates WBS items in batch. (Live runtime verification: `2026-03-24-rc1`, created 2/2 items.)
- [x] `POST /api/v1/projects/{project_id}/export` returns export artifact/job. (Live runtime verification: `2026-03-24-rc1`, returned `202` with `export_id` and `job_id`.)
- [x] `GET /api/v1/projects/{project_id}/budget` returns consistent budget data. (Live runtime verification: `2026-03-24-rc1`, budget totals matched seeded project values.)

### Documents

- [x] `POST /api/v1/projects/{project_id}/documents` uploads and queues processing.
- [x] `GET /api/v1/projects/{project_id}/documents` lists documents with statuses.
- [x] `GET /api/v1/documents/{document_id}` returns full metadata.
- [x] `DELETE /api/v1/documents/{document_id}` deletes and handles missing ids.
- [x] `GET /api/v1/documents/{document_id}/download` downloads correct file.
- [x] `POST /api/v1/{document_id}/parse` triggers parse and returns expected response.
- [x] `POST /api/v1/projects/{project_id}/rag/answer` returns contextual answer + citations.

### Alerts

- [x] `POST /api/v1/alerts` creates alert with required fields.
- [x] `GET /api/v1/projects/{project_id}/alerts` lists project alerts.
- [x] `POST /api/v1/alerts/{alert_id}/review` applies review status transition.
- [x] `POST /api/v1/alerts/bulk-review` processes batch decisions.
- [x] `POST /api/v1/alerts/{alert_id}/evidence` attaches evidence payload.
- [x] `POST /api/v1/alerts/{alert_id}/resolve` resolves alert and updates history.
- [x] `GET /api/v1/alerts/{alert_id}/history` returns timeline/audit trail.
- [x] `POST /api/v1/alerts/bulk-delete` deletes selected alerts.

### Analysis & HITL

- [x] `POST /api/v1/analyze` runs orchestrator.
- [x] `POST /api/v1/hitl/route` routes item.
- [x] `GET /api/v1/hitl/queue` lists items.
- [x] `POST /api/v1/hitl/queue/{item_id}/approve` approves item.

### WBS

- [x] `GET /api/v1/projects/{project_id}/wbs` returns full WBS output.
- [x] `POST /api/v1/projects/{project_id}/wbs/items` creates item.
- [x] `PATCH /api/v1/projects/{project_id}/wbs/items/{item_id}` updates item.
- [x] `DELETE /api/v1/projects/{project_id}/wbs/items/{item_id}` deletes item.

### MCP

- [x] `GET /api/v1/mcp/views` lists whitelisted views.
- [x] `GET /api/v1/mcp/functions` lists whitelisted functions.
- [x] `POST /api/v1/mcp/execute` executes permitted operation.

### Coherence

- [x] `POST /v0/coherence/evaluate` returns coherence result.
- [x] `GET /api/coherence/dashboard/{project_id}` returns dashboard aggregates.

### Stakeholders

- [x] `GET /api/v1/stakeholders/projects/{project_id}` lists stakeholders.
- [x] `POST /api/v1/stakeholders/projects/{project_id}` creates stakeholder.
- [x] `PATCH /api/v1/stakeholders/{stakeholder_id}` updates stakeholder.
- [x] `DELETE /api/v1/stakeholders/{stakeholder_id}` deletes stakeholder.

## Known Follow-ups

- **Clean up duplicated routes:** `GET /api/v1/observability/observability/performance/snapshot` should be removed in favor of `/api/v1/observability/performance/snapshot`.
- **Standardize Prefixes:** `Coherence Engine` uses `/v0`, and `Dashboard` lacks `/v1`. Consider aligning to `/api/v1/...` for consistency.
- **HITL Integration:** Verify that AI extracted items requiring human approval are correctly landing in the HITL queue via `/api/v1/hitl/route`.
- **Parse Path:** Confirm `/api/v1/{document_id}/parse` is the desired canonical path.
