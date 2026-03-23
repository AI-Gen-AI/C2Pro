# C2Pro Real Data Runtime Audit

Date: 2026-03-18

Scope:

- Detect runtime paths that can show fake, demo, mock, seeded, placeholder, or in-memory data instead of real backend data, uploaded documents, or persisted analysis results.
- Focus on manual/local runs of the current app and API.
- No code was modified for this audit. This file is the only artifact created.

Method:

- Direct code inspection across `apps/web` and `apps/api`
- Repo-wide search for `demo`, `fake`, `mock`, `msw`, `seed`, `sample`, `placeholder`, and `in-memory`
- Parallel sub-audits for frontend runtime, backend runtime, and test/tooling contamination risk

## Executive Summary

The repo currently contains multiple production-adjacent runtime paths that can surface non-real data during local/manual validation.

Primary blockers:

- Frontend global demo mode can swap the app to MSW-backed seeded data.
- The real authenticated project documents page has a hardcoded mock fallback.
- Several backend API routers still use in-memory "Fake It" implementations instead of persisted state.
- The coherence dashboard endpoint is hardcoded and not backed by uploaded documents or computed analysis.
- Alert mutation flows can appear to succeed without persisting real alert state.

This means a manual test can appear successful while exercising fake data on either side of the stack unless the environment and endpoint path are verified carefully.

Status update (2026-03-20):

- The coherence dashboard is now derived from persisted `analyses` and `coherence_results` data.
- MCP execute paths and MCP operational persistence have been moved onto DB/Redis-backed flows.
- Alert mutation routes now enforce authenticated admin authorization.

The sections below remain useful as a dated audit snapshot, but the items above should no longer be treated as open runtime findings.

## High Severity Findings

### 1. Frontend demo mode can replace real APIs with seeded MSW data

Files:

- `apps/web/stores/app-mode.ts`
- `apps/web/app/providers.tsx`
- `apps/web/instrumentation.ts`
- `apps/web/mocks/browser.ts`
- `apps/web/mocks/node.ts`
- `apps/web/mocks/data/seed.ts`
- `apps/web/mocks/handlers/custom/demo-data.ts`
- `apps/web/.env.local`

What happens:

- `NEXT_PUBLIC_APP_MODE=demo` flips the frontend into demo mode.
- The main app provider starts MSW as part of normal runtime boot, not just tests.
- Seeded demo tenant, user, projects, documents, alerts, stakeholders, WBS items, and auth responses are loaded automatically.
- Core endpoints such as `/api/v1/projects`, `/api/v1/projects/:id/documents`, `/api/v1/alerts`, `/api/v1/stakeholders`, and auth endpoints are intercepted and answered from fake data.

Risk:

- A local manual run can look fully functional while never reading real backend state.
- Upload, auth, and project validation can be falsely considered complete.

Evidence:

- `apps/web/stores/app-mode.ts`: mode derives directly from `NEXT_PUBLIC_APP_MODE`
- `apps/web/app/providers.tsx`: demo mode starts `@/mocks/browser`
- `apps/web/mocks/browser.ts` and `apps/web/mocks/node.ts`: both call `seedDemoData()`
- `apps/web/mocks/data/seed.ts`: seeds fake tenant/user/project/document/alert data
- `apps/web/mocks/handlers/custom/demo-data.ts`: intercepts core project/document/alert/auth APIs

### 2. Real authenticated documents page falls back to hardcoded mock documents

File:

- `apps/web/app/(app)/projects/[id]/documents/page.tsx`

What happens:

- The page defines `mockDocuments`.
- It renders `documents.length > 0 ? documents : mockDocuments`.

Risk:

- A user can open a real protected route and see fake documents even when no real documents exist or the backend payload is empty.
- This is a direct runtime data-integrity issue in a non-demo route.

### 3. Project API router still relies on in-memory fake state for normal operations

File:

- `apps/api/src/projects/adapters/http/router.py`

What happens:

- The router keeps `_fake_projects` and `_fake_wbs_items` as module-level in-memory stores.
- It reads from and mutates `_fake_projects` after create/read/update/delete flows.
- Several project subresource flows use explicit "Fake It" implementations.

Risk:

- Normal local API usage can read or mutate in-memory state instead of treating PostgreSQL as the single source of truth.
- Successful responses can be disconnected from real uploaded/persisted project state.

Evidence:

- `_fake_projects` declared around lines `141-147`
- Create/read cache into fake store around `208`, `227`, `256`
- Update/delete/status/subresource flows continue to use `_fake_projects` around `346`, `375`, `464`, `485`, `568`, `642`, `782`, `859`
- Fake WBS item storage around `551` and later request handling

### 4. Coherence dashboard endpoint returns hardcoded fake analytics

File:

- `apps/api/src/coherence/router.py`

What happens:

- `GET /api/coherence/dashboard/{project_id}` is documented in the file itself as a "Fake It" implementation.
- It imports `_fake_projects` from the projects router.
- It returns hardcoded metrics like:
  - `coherence_score: 78`
  - fixed `sub_scores`
  - `alert_count: 0`
  - `document_count: 0`
  - fixed timestamp

Risk:

- The dashboard can appear valid while not using uploaded documents, extracted clauses, or real analysis results.
- This is a direct blocker for any claim that the coherence dashboard is backed by real inputs.

### 5. Alert mutation flows are mostly in-memory and fake

File:

- `apps/api/src/alerts/router.py`

What happens:

- The router uses `_fake_alerts` as in-memory state.
- Create, review, bulk review, evidence attachment, resolve, history, and delete flows operate on fake data.

Risk:

- Manual API or frontend testing can appear to update alert state successfully without persisting real alert records.
- Only reading the UI is not enough to confirm real alert persistence.

Evidence:

- `_fake_alerts` defined near line `29`
- Fake-it flow markers and in-memory mutation paths around `122`, `141`, `216`, `229`, `259`, `296`, `327`, `337`, `361`, `396`

### 6. MCP execution endpoint can return synthetic success

Resolution update (2026-03-20): this finding has been addressed by replacing remaining synthetic `/api/v1/mcp/execute` paths with DB-backed execution and by persisting MCP operational controls.

File:

- `apps/api/src/core/mcp/router.py`

What happens:

- `POST /api/v1/mcp/execute` contains a fake contract path.
- Some allowed operations return empty data or synthetic completion without hitting the real DB-backed MCP server.

Risk:

- Manual API checks can falsely conclude the MCP/DB integration is working.

## Medium Severity Findings

### 7. Sample-project onboarding is mock-backed in demo mode

Files:

- `apps/web/mocks/handlers/custom/onboarding-sample-project.ts`
- `apps/web/mocks/handlers/index.ts`

What happens:

- Demo mode returns fabricated sample-project IDs and readiness state such as `proj_sample_001`.

Risk:

- Users can conclude onboarding created a valid project when the flow only exercised MSW.

### 8. Document viewer can render a fake PDF and generated demo entities

File:

- `apps/web/mocks/handlers/custom/document-viewer.ts`

What happens:

- Download returns a blank synthetic PDF.
- Entities are generated from demo clause data.

Risk:

- Evidence/document review flows can appear to work even when no real file or real extraction exists.

### 9. Upload API behavior is mock-backed in demo mode

File:

- `apps/web/mocks/handlers/custom/uploads.ts`

What happens:

- Upload start, chunk, and finalize flows are simulated in memory.

Risk:

- A local user can believe a document upload exercised the backend and storage layer when it only hit MSW.

### 10. Dedicated `/demo` workspace carries full sample business data

Files:

- `apps/web/contexts/demo-mode.tsx`
- `apps/web/middleware.ts`
- `apps/web/app/demo/...`
- `apps/web/components/layout/DemoBanner.tsx`

What happens:

- The app exposes a public `/demo` section with sample projects, alerts, documents, stakeholders, and clauses.

Risk:

- This is intentional, but it is close enough to the main app that link, redirect, or user confusion could invalidate manual verification.

### 11. Bulk operations progress uses in-memory shared store

Files:

- `apps/api/src/bulk_operations/store.py`
- `apps/api/src/bulk_operations/router.py`

What happens:

- Job state is tracked in module memory only.

Risk:

- Progress or completion can appear valid without durable worker-backed execution.

### 12. Procurement snapshot path contains deterministic placeholder planning data

Files:

- `apps/api/src/modules/procurement/application/ports.py`
- `apps/api/src/modules/procurement/adapters/persistence/snapshot_repository.py`

What happens:

- Placeholder procurement planning content is used while DB mapping is incomplete.

Risk:

- If these paths are hit from live routes, users can receive synthetic planning outputs.

## Low Severity Findings

### 13. Generated API schema/client placeholders can mislead developers

Files:

- `apps/web/openapi.json`
- `apps/web/lib/api/generated/models/index.ts`
- `apps/web/orval.config.ts`

What happens:

- `openapi.json` is currently a stub with title `C2Pro API (Stub)`.
- Generated models file explicitly says types are placeholders until client generation runs.
- Orval config is set up with `mock: { type: "msw", useExamples: true }`.

Risk:

- This does not itself change runtime data, but it normalizes mock-first workflows and can confuse API validation.

### 14. Cache and event layers can silently fall back to in-memory behavior

Files:

- `apps/api/src/core/cache.py`
- related event-bus fallback code

What happens:

- Redis/cache infrastructure can fall back to in-memory behavior.

Risk:

- Not a direct fake business-data source, but it reduces confidence that local runs match production persistence and event behavior.

### 15. Test fixtures seed deterministic auth and external-service placeholders

File:

- `apps/api/tests/conftest.py`

What happens:

- Test env bootstraps mock Supabase keys, mock Anthropic credentials, test JWT settings, and deterministic auth fixtures.

Risk:

- Appropriate for tests, but risky if test-oriented env/config is reused during manual validation.

## Findings Most Likely To Mislead Manual Validation

Highest probability of false confidence during local testing:

1. `NEXT_PUBLIC_APP_MODE=demo` enabling MSW and seeded demo data
2. `apps/web/app/(app)/projects/[id]/documents/page.tsx` using `mockDocuments`
3. `apps/api/src/coherence/router.py` returning hardcoded dashboard analytics
4. `apps/api/src/projects/adapters/http/router.py` using `_fake_projects`
5. `apps/api/src/alerts/router.py` using `_fake_alerts`

## Validation Rules For "Real Data Only" Runs

Any manual verification should be considered invalid unless all of the following are true:

- Frontend runs with `NEXT_PUBLIC_APP_MODE=production` or no demo flag
- Browser requests are confirmed not to be intercepted by MSW
- Project/document pages show backend-returned records, not local fallback arrays
- Coherence dashboard is proven to come from persisted uploads and analysis, not `GET /api/coherence/dashboard/{project_id}` fake output
- Alert mutations are verified against persistence, not just response payloads

## Recommended Remediation Order

1. Remove hardcoded fallback data from real authenticated routes first.
2. Replace backend fake/in-memory project and alert flows with persistence-backed implementations.
3. Replace the fake coherence dashboard with a real read model based on uploaded documents and analysis outputs.
4. Isolate demo mode more aggressively so it cannot be mistaken for production-like manual validation.
5. Separate generated client mocks/stubs from runtime app configuration and developer defaults.

## Final Conclusion

The repo is not yet safe to treat as "real data only" in local/manual verification without additional controls.

The most serious issues are not test-only scaffolding. They are runtime-adjacent code paths in:

- frontend demo/MSW boot
- real authenticated frontend route fallbacks
- backend project router
- backend alerts router
- backend coherence dashboard

Until those are removed or isolated, a manual success in the UI or API is not enough to prove the system is operating on real uploaded and persisted data.
