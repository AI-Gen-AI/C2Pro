# C2Pro Real Data Remediation Checklist

Date: 2026-03-18

Source:

- `docs/audit/REAL_DATA_RUNTIME_AUDIT_2026-03-18.md`

Purpose:

- Convert the runtime audit findings into a prioritized remediation checklist.
- No code changes are included in this document.

## Priority 0: Validation Guardrails

These items reduce the chance of false-positive manual verification before deeper fixes land.

- [x] Define a single mandatory rule for "real data" validation:set.
- [x] Add a documented verification step requiring browser-network confirmation that requests are not intercepted by MSW.
      Verification step:
      Open browser DevTools Network tab on a protected page and confirm data requests are going to the expected real backend path and are not labeled, intercepted, or fulfilled by MSW/mock handlers.
- [x] Add a documented verification step requiring confirmation that protected pages use real backend data, not local fallback arrays.
      Verification step:
      For each protected page under manual review, confirm the rendered records correspond to the backend response payload and that the page is not using any local hardcoded fallback arrays or demo/sample records when the API returns empty or error states.
- [x] Add a documented verification step requiring confirmation that coherence/dashboard values come from persisted project inputs, not hardcoded responses.
      Verification step:
      For any dashboard or coherence view under manual review, confirm the displayed values can be traced to persisted project, document, alert, and analysis data and are not fixed response literals or static placeholder metrics.
- [x] Add a documented verification step requiring persistence checks for alert/project mutations.
      Verification step:
      After any manual create, update, review, resolve, or delete action on projects or alerts, confirm the change persists across page refresh and, where applicable, process restart or a fresh API read, rather than only appearing in the immediate response payload.

## Priority 1: Remove Fake Data From Real Authenticated User Paths

These are the highest-risk runtime blockers because they can mislead normal app usage immediately.

### 1. Real project documents page

- [x] Remove hardcoded `mockDocuments` fallback from `apps/web/app/(app)/projects/[id]/documents/page.tsx`.
- [x] Ensure empty states render only when the backend returns no real documents.
- [x] Verify document page behavior for:
  - no documents
  - uploaded documents present
  - backend error
  - loading state

### 2. Backend project router

- [x] Eliminate `_fake_projects` as a source of truth in `apps/api/src/projects/adapters/http/router.py`.
- [x] Remove runtime dependence on `_fake_wbs_items` for user-visible project subresources.
- [x] Replace "Fake It" project subresource responses with DB-backed implementations or explicit `501/409` style non-ready behavior.
- [x] Verify create/read/update/delete/status/subresource flows against PostgreSQL only.

### 3. Backend alerts router

- [x] Eliminate `_fake_alerts` as runtime state in `apps/api/src/alerts/router.py`.
- [x] Replace fake mutation flows with persistence-backed implementations.
- [x] Ensure review/resolve/evidence/history/delete operations read and write real alert records.
- [x] Verify alert state changes survive process restart.

## Priority 2: Replace Fake Analytics and Derived Views

These endpoints create especially dangerous false confidence because the UI can look complete while using synthetic metrics.

### 4. Coherence dashboard

- [x] Replace fake dashboard output in `apps/api/src/coherence/router.py`.
- [x] Stop importing `_fake_projects` from the projects router.
- [x] Back `GET /api/coherence/dashboard/{project_id}` with persisted project/documents/analysis data.
- [x] Define required source tables and derivation rules for:
      Source tables and derivation rules:
  - `projects`: ownership gate for `project_id` + `tenant_id`; fallback source for `coherence_score` via `projects.coherence_score`; fallback candidate for `last_updated` via `projects.last_analysis_at` and `projects.updated_at`.
  - `analyses`: primary source for dashboard score state. Use the latest persisted analysis for the project ordered by `completed_at DESC NULLS LAST, created_at DESC`. Derive:
    - `coherence_score` from `analyses.coherence_score`
    - `sub_scores` from `analyses.coherence_breakdown`
    - `alert_count` override from `analyses.alerts_count` when present
    - `last_updated` candidate from `analyses.completed_at`, then `analyses.updated_at`
  - `coherence_results`: secondary/fallback source when no persisted analysis score is available. Derive:
    - `coherence_score` from `coherence_results.global_score`
    - `sub_scores` from `coherence_results.category_scores`
    - `last_updated` candidate from latest `coherence_results.calculated_at`
  - `alerts`: runtime count source for persisted alerts via `COUNT(*) WHERE project_id = :project_id`; used as dashboard `alert_count` unless the latest persisted analysis provides a more authoritative `alerts_count`.
  - `documents`: runtime count source for persisted documents via `COUNT(*) WHERE project_id = :project_id`; used as dashboard `document_count`. `documents.updated_at` is also a `last_updated` candidate.
    Final derivation precedence:
  - `coherence_score`: latest persisted `analyses.coherence_score` -> latest `coherence_results.global_score` -> `projects.coherence_score` -> `0`
  - `sub_scores`: latest persisted `analyses.coherence_breakdown` -> latest `coherence_results.category_scores` -> zeroed category map
  - `alert_count`: latest persisted `analyses.alerts_count` when available, otherwise live count from `alerts`
  - `document_count`: live count from `documents`
  - `last_updated`: max of available timestamps from latest analysis (`completed_at`, `updated_at`), latest coherence result (`calculated_at`), project (`last_analysis_at`, `updated_at`), latest document `updated_at`, latest alert `updated_at`
- [x] Verify dashboard values change when real uploads or analyses change.

### 5. MCP execution endpoint

- [x] Audit `apps/api/src/core/mcp/router.py` for fake success responses.
- [x] Replace synthetic completion payloads with real execution against the DB-backed MCP server.
- [x] If not implemented yet, return explicit non-success errors instead of fake success.

## Priority 3: Isolate Demo Mode So It Cannot Be Mistaken For Production-Like Validation

These items reduce operational confusion and protect future audits.

### 6. Frontend demo mode boundary

- [x] Restrict demo mode usage to explicitly intentional entry points only.
- [x] Review `apps/web/app/providers.tsx`, `apps/web/stores/app-mode.ts`, `apps/web/instrumentation.ts`, and `apps/web/mocks/*`.
- [x] Ensure demo/MSW boot cannot happen silently during normal developer runs.
- [x] Make demo mode visibly unmistakable in the app shell and route context.
- [x] Verify that protected production routes cannot silently render demo-backed API results.

### 7. Demo workspace segregation

- [x] Review `/demo` route strategy in `apps/web/middleware.ts` and `apps/web/app/demo/*`.
- [x] Ensure no redirects, auth shims, or route helpers can accidentally move users between real workspace routes and `/demo`.
- [x] Verify that all demo screens carry explicit demo/sample labeling.

## Priority 4: Remove Mocked Business Flows That Resemble Real Upload/Onboarding Success

These are medium risk but highly misleading for demos and local QA.

### 8. Upload flow mocks

- [x] Review `apps/web/mocks/handlers/custom/uploads.ts`.
- [x] Ensure upload success cannot be mistaken for real storage/backend processing in manual validation.
- [x] Decide whether upload mocks should be:
  - demo-only and visibly labeled
  - test-only and not loadable from normal app boot

### 9. Sample-project onboarding mocks

- [x] Review `apps/web/mocks/handlers/custom/onboarding-sample-project.ts`.
- [x] Ensure sample-project creation/readiness cannot be used as evidence of real project bootstrap.
- [x] Label sample-project flows explicitly as non-production/demo paths.

### 10. Document viewer mocks

- [x] Review `apps/web/mocks/handlers/custom/document-viewer.ts`.
- [x] Ensure blank-PDF and generated-entity responses cannot appear in non-demo validation.
- [x] Verify evidence/document rendering uses real downloaded files and extracted entities in production mode.
      Verified status (2026-03-21): complete.
  - Backend now exposes `GET /api/v1/documents/{document_id}/entities`, returning clause-derived persisted entities for the evidence page.
  - Frontend evidence fetching uses the real backend entities route via `apps/web/lib/api/index.ts` and `apps/web/hooks/useDocumentEntities.ts`.
  - `PdfEvidenceViewer` now binds its rendered viewer surface directly to the real document download URL rather than a placeholder-only canvas state.
  - Regression coverage exists in `apps/api/tests/core/test_documents_entities_contract.py`, `apps/web/hooks/__tests__/useDocumentEntities.test.ts`, and `apps/web/components/features/evidence/PdfEvidenceViewer.test.tsx`.

## Priority 5: Remove Inconsistent Routing and Fallbacks That Obscure Reality

These are not always fake-data bugs themselves, but they make debugging and validation less reliable.

Status update (2026-03-21): The API contract remediation pass has already closed several routing/data-shape issues that were directly contributing to false runtime validation risk.

- [x] Alerts contract normalized: backend now exposes canonical tenant-scoped alert listing and frontend consumers unwrap the real `items`/`total` payload shape.
- [x] Stakeholders contract normalized: frontend now calls the real backend project-scoped route instead of a mismatched query-style path.
- [x] Analysis processing contract normalized: backend now exposes a real authenticated SSE processing stream and frontend progress consumers use it.
- [x] Document parse route normalized: canonical route is now `POST /api/v1/documents/{document_id}/parse`, with temporary hidden compatibility alias retained.
- [x] Coherence namespace normalized: canonical backend namespace is now `/api/v1/coherence/*`, with legacy compatibility aliases preserved during transition.
- [x] Follow-up cleanup: `apps/web/components/features/processing/ProcessingStepper.test.tsx` no longer emits the pre-existing React `act(...)` warnings during focused frontend test runs.

### 11. API routing consistency

- [x] Standardize whether frontend data access uses same-origin proxy or direct backend base URL.
      Current state: proxy-first remains the active strategy for browser-facing frontend access; coherence proxy exceptions were normalized to the canonical backend namespace.
- [x] Review dashboard-specific fetch paths that bypass the main proxy strategy.
      Current state: coherence dashboard fetches still use `/api/coherence/*` from the frontend, but the proxy now forwards them to the canonical backend `/api/v1/coherence/*` namespace.
- [x] Ensure auth, tenant, and error behavior are consistent across all data clients.
      Current state: alerts, stakeholders, analysis processing SSE, document parse, and coherence dashboard/evaluate paths were aligned to their real backend contracts. Remaining work is narrower and tracked in the dedicated API remediation checklist.

### 12. Auth and redirect clarity

- [x] Review frontend 401 handling in `apps/web/lib/api/client.ts`.
- [x] Remove legacy redirect behavior that increases ambiguity during auth failures.
- [x] Verify real auth failures cannot be confused with demo-mode or fallback data behavior.
      Current state: the shared Axios client now sends real 401s straight to the canonical `/sign-in` route, avoids legacy `redirect_url` behavior, preserves explicit `/demo/*` routes without masking auth failures in real workspaces, suppresses duplicate 401 redirect/toast noise, and treats `/login` plus `/register` as auth-page aliases to avoid redirect loops. Validation coverage now also includes Clerk token-sync failures, protected-route loading states, and stream-expiry auth behavior.

### 13. Viewer watermark fallback

- [x] Review `apps/web/components/features/evidence/PdfEvidenceViewer.tsx`.
      Review status (2026-03-22): complete.
  - `PdfEvidenceViewer` now only restores session watermark state in explicit demo mode, preventing demo-origin payloads from bleeding into real workspace renders.
  - Real workspace paths now fail closed to an empty watermark payload when no verified demo watermark exists, and the component clears stale session watermark state instead of synthesizing `unverified-production-access`.
  - Regression coverage exists in `apps/web/components/features/evidence/PdfEvidenceViewer.test.tsx` for both demo-state isolation and the no-synthetic-production-watermark behavior.
- [x] Remove demo-oriented watermark payloads from real viewer paths or isolate them to explicit demo mode.

## Priority 6: Reduce Tooling and Generated-Client Confusion

These are lower risk, but they make the repo easier to misread and easier to validate incorrectly.

### 14. Generated API client and schema stubs

- [x] `6.14.1` **Replace openapi.json stub:** Generate a real OpenAPI spec from the backend `/openapi.json` and move it to `apps/web/schema/api.json`.
- [x] `6.14.2` **Orval Mock Isolation:** Update `orval.config.ts` to generate MSW handlers into a `__mocks__` directory that is explicitly ignored in production builds.
      Verified status (2026-03-22): complete.
  - Orval now emits generated MSW handlers into `apps/web/lib/api/generated/__mocks__`.
  - `apps/web/next.config.js` now ignores `__mocks__` resources from production webpack bundles.
  - Regression coverage exists in `apps/web/src/tests/integration/ci/api-generation-drift.integration.test.ts`.
- [x] `6.14.3` **Pydantic Client Sync:** Automate `orval` in CI to prevent contract drift between Pydantic models and the frontend.
      Verified status (2026-03-22): complete.
  - `apps/web/lib/api/client.ts` now exports a callable `orvalApiClient` mutator so generated clients are produced from the checked-in schema without manual patching.
  - `apps/web/package.json` now checks both `lib/api/generated` and `schema/api.json` for drift.
  - `.github/workflows/frontend-ci.yml` now runs the frontend drift check when backend API files change, closing the gap where Pydantic-backed contract changes could bypass frontend generation validation.
  - Orval infinite-query generation was disabled because the current schema parameters do not expose a shared `offset` contract, and leaving it enabled produced invalid generated TypeScript for several endpoints.

### 15. Test-environment contamination controls

- [x] `6.15.1` **Separate Runtime vs Test Env:** Add a `scripts/validate_runtime_env.py` to ensure local manual QA isn't using a `test` database name by accident.
- [x] `6.15.2` **Seeded Identity Isolation:** Ensure `apps/api/tests/conftest.py` identities never bleed into real `tenants` or `users` tables in a shared DB.

### Priority 7: Immediate Implementation Roadmap (NEW)

- [x] **Task 7.1: Global API Base URL Fix:** Force all frontend API calls through `apps/web/lib/api/config.ts` using a single verified `BASE_URL` (Proxy-first).
- [x] **Task 7.2: Fail-Closed PDF Viewer:** Refactor `PdfEvidenceViewer.tsx` to throw a clear "Resource Not Found" error instead of showing the demo watermark when in `production` mode.
- [x] **Task 7.3: Demo Mode Labeling:** Implement a high-contrast "DEMO MODE" banner in the `apps/web/components/layout/Navbar.tsx` that only triggers when `NEXT_PUBLIC_APP_MODE=demo`.

## Suggested Execution Order

Workstream A: user-visible data integrity

1. Remove `mockDocuments` from the real documents page.
2. Replace `_fake_projects` paths in the project router.
3. Replace `_fake_alerts` paths in the alerts router.
4. Replace fake coherence dashboard output.

Workstream B: demo/mock isolation

1. Tighten demo-mode boot and routing boundaries.
2. Isolate upload, onboarding, and document-viewer mocks.
3. Make demo-state labeling impossible to miss.

Workstream C: validation hardening

1. Standardize API routing and auth failure behavior.
2. Remove generated-client/schema ambiguity.
3. Separate manual runtime verification from test/demo environments.

## Completion Criteria

The remediation effort should not be considered complete until all of the following are true:

- [x] No authenticated production route renders hardcoded business records when backend data is empty.
- [x] No core API route returns fake/in-memory business data in normal local runtime.
- [x] Coherence dashboard values derive from persisted project inputs and analysis outputs.
- [x] Demo mode cannot be confused with production-like manual validation.
- [x] Upload, onboarding, and document review flows are verified against real backend/storage behavior.
- [x] Manual QA can prove requests and data come from real sources end to end.
