# Quality Assurance Backlog

**Category**: Quality Assurance (QA)
**Owner Role**: qa
**Last Updated**: 2026-05-17

**Quick Links**:
- 🏠 [Master Index](../C2PRO_MASTER_BACKLOG.md)

---

## Status View

**Pending Tasks**: 102 active endpoint checks remain under `EPIC-QA-SWAGGER-MANUAL-VERIFICATION`.

**Completed QA / Audit Tasks**

- `TASK-REV-QUALITY-001`
- `TASK-REV-QUALITY-002`
- `TASK-QA-077`
- `TASK-QA-080`
- `TASK-QA-082`
- `TASK-QA-098`
- `TASK-QA-099`
- `TASK-QA-102`
- `TASK-QA-103`
- `TASK-1480`
- `TASK-QA-200`..`TASK-QA-213` (EPIC-QA-CONTRACT-COVERAGE complete @2026-05-08)

---

## Reference: Ruff Linting Debt Classification (TASK-REV-QUALITY-001)

**Status**: ✅ OK (Debt Classified)
**Date**: 2026-04-07
**Auditor**: Role_reviewer (Gemini CLI)

The audit of 82 remaining Ruff errors has been completed. The errors have been classified into 4 tiers to guide remediation efforts.

### Error Classification Summary

| Tier | Category | Count (Approx) | Action |
| :--- | :--- | :---: | :--- |
| **TIER 1** | Obligatory `# noqa` | 15 | Add `# noqa` with specific codes. |
| **TIER 2** | Real Bugs / Unused Logic | 12 | Fix unused logic (mostly `tenant_id` omissions). |
| **TIER 3** | False Positives | 5 | Ignore or slightly refactor to clarify for linter. |
| **TIER 4** | Code Smells / Debt | 50+ | Incremental cleanup; mostly imports and formatting. |

### Tier 1 - Obligatory `# noqa` (Framework Callbacks)

These errors are caused by required method signatures from SQLAlchemy or FastAPI that don't use all arguments.

- **SQLAlchemy Events**:
    - `core/auth/models.py`: `generate_tenant_slug(mapper, ...)` - `mapper` is unused but required by signature.
    - `core/database.py`: `_receive_before_cursor_execute` and `_receive_after_cursor_execute` - `cursor`, `statement`, `parameters`, `context`, `executemany` are mostly unused but required.
    - `core/database.py`: `_initialize_tenant_guc` - `connection_record` is unused.

### Tier 2 - Real Bugs / Unused Logic

- **Tenant Isolation Omissions**:
    - `alerts/application/use_cases/create_alert_use_case.py`: `tenant_id` is passed but NOT used in the `Alert` domain entity or repository call. **CRITICAL: potential tenant isolation bypass.**
    - `analysis/adapters/ai/tools/risk_extraction_tool.py`: `tenant_id` unused.
    - `analysis/adapters/ai/tools/wbs_extraction_tool.py`: `tenant_id` unused.
    - `documents/application/list_project_documents_use_case.py`: `tenant_id` unused.
- **Logic Bugs**:
    - `alerts/application/use_cases/list_alerts_use_case.py`: `status_enum = AlertStatus(severity)` — **BUG**: Uses `severity` variable to initialize `AlertStatus`. Should use `status`.
    - `alerts/application/ports/project_repository.py`: Undefined name `Project`. Missing import.

### Tier 3 - False Positives

- `analysis/domain/coherence_derivation.py`: `UP038` - Ruff suggests `int | float` for `isinstance`, but this is unsafe in some Python versions.
- `coherence/graph/nodes.py`: `F401` - Reports `PgvectorEmbeddingRepository` as unused, but it's used in type hint or dynamic dispatch.

### Tier 4 - Code Smells (Design Debt)

- **Import Debt**: Massively unsorted imports in `alerts` and `core` modules (`I001`).
- **Unused Imports**: `F401` errors in multiple routers.
- **Whitespace**: `W293` in `core/auth/token_revocation.py` and `core/database.py`.
- **Simplification**: `SIM108` in `core/database.py`.

---

## Reference: ORM Models Audit (TASK-REV-QUALITY-002)

**Status**: ✅ Classified (Gate 4 Traceability debt documented)
**Date**: 2026-04-07
**Auditor**: Role_reviewer (Gemini CLI)

### Migration vs. ORM Inventory

| Table Name | Migration File | ORM Model Found? | Status |
| :--- | :--- | :---: | :---: |
| `clause_embeddings` | `20260401_0001` | ❌ No | **CRITICAL** |
| `document_chunks` | `20260315_0001` | ❌ No | **CRITICAL** |
| `stakeholder_alerts`| `20260319_0004` | ❌ No | **HIGH** |
| `bom_revisions` | `20260319_0004` | ❌ No | **HIGH** |
| `procurement_plan_snapshots` | `20260319_0004` | ❌ No | **HIGH** |
| `knowledge_graph_nodes` | `20260319_0005` | ❌ No | **MEDIUM** |
| `knowledge_graph_edges` | `20260319_0005` | ❌ No | **MEDIUM** |
| `checkpoints` | `20260320_0001` | ❌ No | **LOW** (LangGraph) |
| `audit_logs` | `20260319_0003` | ✅ Yes | **MISMATCH** |
| `ai_usage_logs` | `20260319_0003` | ✅ Yes | **DRIFT** |

### Key Findings

**ORM-M01**: `SQLAlchemyAuditRepository` fields mismatch `audit_logs` schema — audit trail persistence is broken.

**ORM-M02**: `PgvectorEmbeddingRepository` and `RagService` interact with `clause_embeddings`/`document_chunks` via raw SQL — bypasses type safety and Gate 4 traceability.

**ORM-M03**: `AIUsageLogORM` includes `trace_id`/`trace_url` columns absent from migration `20260319_0003`.

---

## Reference: TASK-QA-077 + TASK-1480 Test Stabilization

**Status**: ✅ COMPLETE — Date: 2026-04-30 (PR #93)

- `TASK-QA-077`: Added `freezegun.freeze_time` to SLA boundary tests.
- `TASK-1480`: Wrapped state-changing React `fireEvent` calls in `act()` in `AlertReviewCenter.test.tsx` and `AlertUndoToast.test.tsx`.

---

## Reference: TASK-QA-098 E2E Complete User Journey Validation

**Status**: ✅ VALIDATION COMPLETE / ❌ ACCEPTANCE FAILED (coverage ~35%, below 85% target)
**Date**: 2026-04-08

Key defects found and fixed during validation:
1. Document persistence timestamp mismatch (naive vs aware UTC)
2. Alerts review persistence timestamp mismatch
3. Missing alert lifecycle history on create
4. Stale alert list contract in E2E suite

Acceptance criteria still not met: measured coverage ~35% (requires >=85%), 2/5 journey checks remain environment-skipped.

---

## Reference: TASK-QA-103 Modules Suite Stabilization

**Status**: ✅ COMPLETE — Date: 2026-04-09

- HITL resume workflow stabilized with deterministic dependency overrides.
- Procurement WBS tree root filtering fixed (`IS NULL` vs Python `is None`).
- Final result: `1450 passed, 2 skipped`.

---

## Reference: EPIC-QA-CONTRACT-COVERAGE

**Status**: ✅ COMPLETE @2026-05-08
**Planner**: MASTER (Opus 4.7) — W7 planning deliverable

All 14 subtasks (TASK-QA-200..213) complete:

**Track A — Schemathesis (Backend)**
- QA-200: `schemathesis` added, conftest with auth/tenant hooks, smoke tests ✅
- QA-201: Auth, projects, documents router suites ✅
- QA-202: Analysis, coherence, alerts, hitl router suites ✅
- QA-203: WBS, procurement, stakeholders router suites ✅
- QA-204: Observability, AI feedback, admin/DLQ, frontend-support router suites ✅
- QA-205: OpenAPI drift gate CI workflow ✅
- QA-206: conftest.py refactored ≤700 LOC, fixtures extracted ✅

**Track B — Wireframe TCs (Frontend)**
- QA-207: Wireframe coverage tracker + CI hook ✅
- QA-208: WF-01 dashboard + WF-02 projects TCs ✅
- QA-209: WF-03 evidence-viewer TCs ✅
- QA-210: WF-04 alerts TCs ✅
- QA-211: WF-05 stakeholders + WF-06 RACI TCs ✅

**Track C — Report Pipeline (Infra)**
- QA-212: Quality report renderer + composite action ✅
- QA-213: Workflow wiring + PR comment gate ✅

---

---

## EPIC-QA-SWAGGER-MANUAL-VERIFICATION — Real Swagger Endpoint Audit

**Status**: ACTIVE — started 2026-05-17  
**Purpose**: Manually verify every unique Swagger operation end-to-end with live evidence, not mock assumptions.  
**Rules**: mark only after a real Swagger execution; record exact HTTP outcome and a brief note when behavior is surprising.

### Live audit board

| Status | Task ID | Group | Method | Endpoint | Result / brief note |
| --- | --- | --- | --- | --- | --- |
| [ ] | `TASK-QA-214` | Public / Health | `GET` | `/` |  |
| [ ] | `TASK-QA-215` | Public / Health | `GET` | `/api/v1/health/worker` |  |
| [ ] | `TASK-QA-216` | Public / Health | `GET` | `/health/live` |  |
| [ ] | `TASK-QA-217` | Public / Health | `GET` | `/health/ready` |  |
| [ ] | `TASK-QA-218` | Public / Health | `GET` | `/health/circuit-breakers` |  |
| [ ] | `TASK-QA-219` | Public / Health | `GET` | `/health` |  |
| [ ] | `TASK-QA-220` | Public / Health | `GET` | `/health/worker` |  |
| [ ] | `TASK-QA-221` | Public / Health | `GET` | `/api/v1/health/live` |  |
| [ ] | `TASK-QA-222` | Public / Health | `GET` | `/api/v1/health/ready` |  |
| [ ] | `TASK-QA-223` | Public / Health | `GET` | `/api/v1/health/circuit-breakers` |  |
| [ ] | `TASK-QA-224` | Public / Health | `GET` | `/api/v1/health` |  |
| [x] | `TASK-QA-225` | Authentication | `POST` | `/api/v1/auth/register` | 201 verified in Swagger on 2026-05-17. |
| [ ] | `TASK-QA-226` | Authentication | `POST` | `/api/v1/auth/login` |  |
| [ ] | `TASK-QA-227` | Authentication | `POST` | `/api/v1/auth/refresh` |  |
| [ ] | `TASK-QA-228` | Authentication | `GET` | `/api/v1/auth/me` |  |
| [ ] | `TASK-QA-229` | Authentication | `PUT` | `/api/v1/auth/me` |  |
| [ ] | `TASK-QA-230` | Authentication | `POST` | `/api/v1/auth/logout` |  |
| [ ] | `TASK-QA-231` | Authentication | `POST` | `/api/v1/auth/change-password` |  |
| [x] | `TASK-QA-232` | Projects | `GET` | `/api/v1/projects/health` | 200 verified in Swagger; public projects health check returned `status=ok`, `service=projects`. |
| [x] | `TASK-QA-233` | Projects | `GET` | `/api/v1/projects/stats` | 200 verified in Swagger; tenant stats returned 1 draft construction project. |
| [x] | `TASK-QA-234` | Projects | `POST` | `/api/v1/projects` | Verified; created project 25916ab2-03a3-4df5-bf5f-1f8dde07fb8c. |
| [x] | `TASK-QA-235` | Projects | `GET` | `/api/v1/projects` | 200 verified in Swagger; returned the single tenant project with expected pagination metadata. |
| [x] | `TASK-QA-236` | Projects | `GET` | `/api/v1/projects/{project_id}` | 200 verified in Swagger; returned the expected tenant project and `ETag: "v1"`. |
| [x] | `TASK-QA-237` | Projects | `PUT` | `/api/v1/projects/{project_id}` | 200 verified in Swagger; full update persisted description change and advanced version 1→2. |
| [x] | `TASK-QA-238` | Projects | `PATCH` | `/api/v1/projects/{project_id}` | 428 verified without precondition; 200 verified with `expected_version=2`, description persisted, version 2→3, `ETag: "v3"`. |
| [ ] | `TASK-QA-239` | Projects | `DELETE` | `/api/v1/projects/{project_id}` |  |
| [x] | `TASK-QA-240` | Projects | `GET` | `/api/v1/projects/{project_id}/summary` | 200 verified in Swagger; compact summary returned expected project data plus 15 open alerts from prior analyses. |
| [x] | `TASK-QA-241` | Projects | `PATCH` | `/api/v1/projects/{project_id}/status` | 200 verified in Swagger; status changed draft→active and version advanced 3→4. |
| [ ] | `TASK-QA-242` | Projects | `POST` | `/api/v1/projects/{project_id}/documents/bulk` |  |
| [x] | `TASK-QA-243` | Projects | `POST` | `/api/v1/projects/{project_id}/wbs/bulk` | 201 verified in Swagger; atomic hierarchy payload created 4 WBS items with valid parent-child relationships and zero failures. |
| [x] | `TASK-QA-244` | Projects | `POST` | `/api/v1/projects/{project_id}/export` | 202 verified in Swagger; async export accepted with job/export id `62f6bc31-490d-4b08-8c81-cc449a13594a`. |
| [x] | `TASK-QA-245` | Projects | `GET` | `/api/v1/projects/{project_id}/budget` | 200 verified in Swagger; returned zero operational budget because endpoint aggregates procurement budget items, not project header estimates. |
| [ ] | `TASK-QA-246` | WBS | `GET` | `/api/v1/projects/{project_id}/wbs` | Persistence now works after `TASK-BCK-055`, but endpoint is not yet contract-clean: live payload is flat (`items` + `total_items`) while Swagger promises hierarchy + coverage; blocked by `TASK-BCK-060`. |
| [ ] | `TASK-QA-247` | WBS | `POST` | `/api/v1/projects/{project_id}/wbs/items` |  |
| [ ] | `TASK-QA-248` | WBS | `PATCH` | `/api/v1/projects/{project_id}/wbs/items/{item_id}` |  |
| [ ] | `TASK-QA-249` | WBS | `DELETE` | `/api/v1/projects/{project_id}/wbs/items/{item_id}` |  |
| [ ] | `TASK-QA-250` | WBS | `GET` | `/api/v1/projects/{project_id}/wbs/items/{item_id}` |  |
| [ ] | `TASK-QA-251` | WBS | `POST` | `/api/v1/projects/{project_id}/wbs/items/{item_id}/move` |  |
| [x] | `TASK-QA-252` | Documents | `POST` | `/api/v1/projects/{project_id}/documents` | 202 verified again on 2026-05-17 after `TASK-BCK-061`; live schedule upload accepted as document `f04d4f22-684f-4874-b93b-dc5436ef720b`. |
| [x] | `TASK-QA-253` | Documents | `GET` | `/api/v1/projects/{project_id}/documents` | 200 verified on 2026-05-17; project list shows both parsed documents with correct count `2`. |
| [ ] | `TASK-QA-254` | Documents | `PATCH` | `/api/v1/documents/{document_id}/file` |  |
| [ ] | `TASK-QA-255` | Documents | `GET` | `/api/v1/documents/{document_id}` | Functional `200` verified on 2026-05-17 for schedule document, but response exposed `parsed_at=null` after successful parse; keep open until `TASK-BCK-063` is fixed. |
| [ ] | `TASK-QA-256` | Documents | `DELETE` | `/api/v1/documents/{document_id}` |  |
| [ ] | `TASK-QA-257` | Documents | `GET` | `/api/v1/documents/{document_id}/history` | Functional `200` verified on 2026-05-17, but history only shows upload because successful parse leaves `parsed_at` null; keep open until `TASK-BCK-063` is fixed. |
| [x] | `TASK-QA-258` | Documents | `GET` | `/api/v1/documents/{document_id}/relationship-explanation` | 200 verified on 2026-05-17 for schedule document; response is internally consistent with current architecture (`0` clauses, `0` linked alerts, empty citations). |
| [ ] | `TASK-QA-259` | Documents | `GET` | `/api/v1/documents/{document_id}/entities` | Functional `200` verified on 2026-05-17 for schedule document, but response is `[]`; for schedules the decisive extraction proof must come from downstream WBS creation, not this generic entities projection. |
| [x] | `TASK-QA-260` | Documents | `GET` | `/api/v1/documents/{document_id}/download` | 200 verified on 2026-05-17 for schedule document; binary download returned with expected attachment headers and `12131` bytes. |
| [x] | `TASK-QA-261` | Documents | `POST` | `/api/v1/documents/{document_id}/parse` | Verified 2026-05-17 with live real schedule workbook after `TASK-BCK-062`: `202 parsed` for `f04d4f22-684f-4874-b93b-dc5436ef720b`. Re-verified 2026-05-18 after `TASK-BCK-067`: same Excel schedule can be parsed again without duplicate generated activity `500`. |
| [x] | `TASK-QA-262` | Documents | `POST` | `/api/v1/projects/{project_id}/documents/{document_id}/reprocess` | 202 verified on 2026-05-17; document requeued successfully with new task id. |
| [ ] | `TASK-QA-263` | Documents | `POST` | `/api/v1/projects/{project_id}/rag/answer` | Schedule-only questions were 200 after `TASK-BCK-068`/`TASK-BCK-069`, but contract penalty question on 2026-05-23 returned only schedule sources. DB confirmed contract `f6543818-b7a6-4357-8f48-43238a4f8a65` has 210 clauses and zero `document_chunks`; `TASK-BCK-070` adds contract clause RAG ingestion. Contract sources now return after reparse, but answer abstained despite damages evidence; `TASK-BCK-071` adds damages fallback. Keep open until API restart + penalty question returns a non-abstaining contract-based answer. |
| [ ] | `TASK-QA-264` | Alerts | `GET` | `/api/v1/alerts/workspace-settings` |  |
| [ ] | `TASK-QA-265` | Alerts | `PUT` | `/api/v1/alerts/workspace-settings` |  |
| [ ] | `TASK-QA-266` | Alerts | `POST` | `/api/v1/alerts` |  |
| [ ] | `TASK-QA-267` | Alerts | `GET` | `/api/v1/alerts/projects/{project_id}` | First live Swagger check returned `401 missing_or_invalid_token` because OpenAPI did not advertise bearer auth and Swagger omitted `Authorization`; fixed by `TASK-BCK-072`. Re-test after API restart. |
| [ ] | `TASK-QA-268` | Alerts | `GET` | `/api/v1/alerts/tenant` |  |
| [ ] | `TASK-QA-269` | Alerts | `POST` | `/api/v1/alerts/{alert_id}/review` |  |
| [ ] | `TASK-QA-270` | Alerts | `POST` | `/api/v1/alerts/bulk-review` |  |
| [ ] | `TASK-QA-271` | Alerts | `POST` | `/api/v1/alerts/{alert_id}/resolve` |  |
| [ ] | `TASK-QA-272` | Alerts | `POST` | `/api/v1/alerts/bulk-resolve` |  |
| [ ] | `TASK-QA-273` | Alerts | `GET` | `/api/v1/alerts/{alert_id}/history` |  |
| [ ] | `TASK-QA-274` | Alerts | `DELETE` | `/api/v1/alerts/{alert_id}` |  |
| [ ] | `TASK-QA-275` | Alerts | `GET` | `/api/v1/projects/{project_id}/alerts` |  |
| [ ] | `TASK-QA-276` | Alerts | `GET` | `/api/projects/{project_id}/alerts` |  |
| [x] | `TASK-QA-277` | Bulk / Observability / AI | `GET` | `/api/v1/bulk-operations/{job_id}/progress` | 200 verified in Swagger for export job; returned coherent processing state, though the flow appears intentionally minimal/fake at present. |
| [x] | `TASK-QA-278` | Bulk / Observability / AI | `GET` | `/api/v1/observability/status` | 200 verified live after `TASK-BCK-066`; route remains private and OpenAPI now advertises bearer auth so Swagger can send `Authorization`. |
| [x] | `TASK-QA-279` | Bulk / Observability / AI | `GET` | `/api/v1/observability/analyses` | 200 verified live after `TASK-BCK-066`; same observability router fix now advertises bearer auth and returns tenant-filtered analysis rows. |
| [ ] | `TASK-QA-280` | Bulk / Observability / AI | `GET` | `/api/v1/observability/performance/snapshot` |  |
| [ ] | `TASK-QA-281` | Bulk / Observability / AI | `POST` | `/api/v1/ai/feedback` |  |
| [ ] | `TASK-QA-282` | Bulk / Observability / AI | `GET` | `/api/v1/ai/analytics/cost` |  |
| [ ] | `TASK-QA-283` | Bulk / Observability / AI | `GET` | `/api/v1/ai/analytics/versions` |  |
| [ ] | `TASK-QA-284` | Bulk / Observability / AI | `GET` | `/api/v1/ai/analytics/comparison` |  |
| [ ] | `TASK-QA-285` | Bulk / Observability / AI | `GET` | `/api/v1/ai/analytics/quality-drift` |  |
| [ ] | `TASK-QA-286` | Admin / Frontend Support | `GET` | `/api/v1/admin/dlq` |  |
| [ ] | `TASK-QA-287` | Admin / Frontend Support | `POST` | `/api/v1/admin/dlq/{dlq_id}/retry` |  |
| [ ] | `TASK-QA-288` | Admin / Frontend Support | `POST` | `/api/v1/compliance/cookies/consent` |  |
| [ ] | `TASK-QA-289` | Admin / Frontend Support | `GET` | `/api/v1/compliance/cookies/consent` |  |
| [ ] | `TASK-QA-290` | Admin / Frontend Support | `PATCH` | `/api/v1/compliance/cookies/consent` |  |
| [ ] | `TASK-QA-291` | Admin / Frontend Support | `GET` | `/api/v1/projects/{project_id}/gates/gate-8/disclaimer/status` |  |
| [ ] | `TASK-QA-292` | Admin / Frontend Support | `POST` | `/api/v1/projects/{project_id}/gates/gate-8/disclaimer/accept` |  |
| [ ] | `TASK-QA-293` | Admin / Frontend Support | `POST` | `/api/v1/onboarding/sample-project/start` |  |
| [ ] | `TASK-QA-294` | Admin / Frontend Support | `GET` | `/api/v1/onboarding/sample-project/ready` |  |
| [ ] | `TASK-QA-295` | Admin / Frontend Support | `POST` | `/api/v1/onboarding/sample-project/retry` |  |
| [ ] | `TASK-QA-296` | Admin / Frontend Support | `GET` | `/api/v1/onboarding/sample-project/telemetry` |  |
| [ ] | `TASK-QA-297` | Admin / Frontend Support | `GET` | `/api/v1/security/secret-channel/clerk` |  |
| [ ] | `TASK-QA-298` | Decision Intelligence / HITL | `POST` | `/api/v1/decision-intelligence/execute` |  |
| [ ] | `TASK-QA-299` | Decision Intelligence / HITL | `POST` | `/api/v1/hitl/route` |  |
| [ ] | `TASK-QA-300` | Decision Intelligence / HITL | `GET` | `/api/v1/hitl/queue` |  |
| [ ] | `TASK-QA-301` | Decision Intelligence / HITL | `GET` | `/api/v1/hitl/queue/{item_id}` |  |
| [ ] | `TASK-QA-302` | Decision Intelligence / HITL | `POST` | `/api/v1/hitl/queue/{item_id}/approve` |  |
| [ ] | `TASK-QA-303` | Decision Intelligence / HITL | `POST` | `/api/v1/hitl/queue/{item_id}/reject` |  |
| [ ] | `TASK-QA-304` | Decision Intelligence / HITL | `POST` | `/api/v1/hitl/queue/{item_id}/release` |  |
| [ ] | `TASK-QA-305` | Decision Intelligence / HITL | `POST` | `/api/v1/hitl/escalate` |  |
| [ ] | `TASK-QA-306` | Decision Intelligence / HITL | `POST` | `/api/v1/hitl/resume/{review_id}` | Backend seam fixed in `TASK-BCK-074`: approve path now updates state and invokes LangGraph; pending live Swagger rerun with a pending review item carrying checkpoint metadata. |
| [ ] | `TASK-QA-307` | Decision Intelligence / HITL | `GET` | `/api/v1/settings/notifications` |  |
| [ ] | `TASK-QA-308` | Decision Intelligence / HITL | `POST` | `/api/v1/settings/notifications` |  |
| [ ] | `TASK-QA-309` | Analysis / MCP / Coherence / Approvals | `POST` | `/api/v1/analysis/analyze` | Reopened 2026-05-23: live call returned HTTP 200 but functional failure (`Tool 'risk_extraction' executed: failed`, empty risks, confidence 0). Initial tool root cause fixed in `TASK-BCK-073`; follow-on Analysis ⇄ HITL seam fixed in `TASK-BCK-074` after live rerun showed real risks but `analysis_id=null`/critique inconclusive. Pending API restart and live Swagger rerun. |
| [ ] | `TASK-QA-310` | Analysis / MCP / Coherence / Approvals | `GET` | `/api/v1/analysis/projects/{project_id}/process/stream` |  |
| [ ] | `TASK-QA-311` | Analysis / MCP / Coherence / Approvals | `POST` | `/api/v1/mcp/query-view` |  |
| [ ] | `TASK-QA-312` | Analysis / MCP / Coherence / Approvals | `POST` | `/api/v1/mcp/call-function` |  |
| [ ] | `TASK-QA-313` | Analysis / MCP / Coherence / Approvals | `GET` | `/api/v1/mcp/views` |  |
| [ ] | `TASK-QA-314` | Analysis / MCP / Coherence / Approvals | `GET` | `/api/v1/mcp/functions` |  |
| [ ] | `TASK-QA-315` | Analysis / MCP / Coherence / Approvals | `GET` | `/api/v1/mcp/rate-limit-status` |  |
| [ ] | `TASK-QA-316` | Analysis / MCP / Coherence / Approvals | `POST` | `/api/v1/mcp/execute` |  |
| [x] | `TASK-QA-317` | Analysis / MCP / Coherence / Approvals | `POST` | `/api/v1/coherence/evaluate` | 200 verified again on 2026-05-17 after contract + schedule ingestion; live overall_score `37.8` with 16 alerts and category breakdown. |
| [x] | `TASK-QA-318` | Analysis / MCP / Coherence / Approvals | `POST` | `/api/v1/coherence/evaluate/diagnostics` | 200 verified on 2026-05-17; diagnostics exposed `score_missing_dimensions=["schedule"]` despite successful schedule parse + WBS creation, creating `TASK-BCK-064`. |
| [x] | `TASK-QA-319` | Analysis / MCP / Coherence / Approvals | `GET` | `/api/v1/coherence/dashboard/{project_id}` | 200 verified on 2026-05-17; dashboard matches fresh evaluation (`38`, `v1_exponential_decay`) and confirms persistent `score_missing_dimensions=["schedule"]` defect tracked by `TASK-BCK-064`. |
| [ ] | `TASK-QA-320` | Analysis / MCP / Coherence / Approvals | `GET` | `/api/coherence/dashboard/{project_id}` |  |
| [ ] | `TASK-QA-321` | Analysis / MCP / Coherence / Approvals | `PATCH` | `/api/v1/approvals/{resource_type}/{resource_id}` |  |

### Execution order

1. Public/health and auth bootstrap.
2. Core project/document flow.
3. Coherence, analysis, dashboard, and RAG.
4. Alerts, HITL, decision intelligence, then remaining admin/support surfaces.

### Defect policy

- A failing endpoint gets a dedicated backend/frontend follow-up task immediately if root cause is product code.
- An endpoint blocked only by missing test data keeps its QA task open with the exact blocker noted.
- Duplicate Swagger tags do not create duplicate tasks; this board tracks unique method + path operations.
