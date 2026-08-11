# Frontend Tasks & Knowledge Base

**Category**: Frontend (FRT)
**Owner Role**: frontend
**Last Updated**: 2026-08-08

**Quick Links**:

- 🏠 [Master Index](../C2PRO_MASTER_BACKLOG.md)
- 📋 [Role Profile](../roles/role_frontend.md)

---

## 0. Status View

**Pending Tasks**: 1

- `TASK-FRT-041` — blocked (requires Clerk dashboard operator access)

**Completed Tasks**: 201

- IDs: `TASK-FRT-001`–`TASK-FRT-040`, `TASK-FRT-042`–`TASK-FRT-202`

**Usage Note**:

- Use this section to see what still needs execution without scanning the full table.
- The detailed register below remains the authoritative task history.

## 1. Active Tasks

| Status | Priority | Task ID        | Depends On | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             | Source                                              |
| ------ | -------- | -------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------- |
| [~]    | P3       | `TASK-FRT-041` | None       | WONT-DO: Clerk free tier does not allow email template customization. Original Clerk templates are retained. Domain c2pro.io is verified. Revisit if plan is upgraded to Clerk Pro. | `docs/runbooks/CLERK_AUTH_DEV_PROD_GUIDE.md`        |

**Statistics**:

- Total: 202 tasks
- Active: 0 (0%)
- Completed: 201 (99.5%)
- WONT-DO: 1 (FRT-041, 0.5%)

---

## 2. Specifications

### EPIC-FRT-L1-WEDGE — Frontend Level-1 Wedge Closure (2026-07-04)

- **Goal**: make the Level-1 journey (create project → upload contract+budget+schedule triplet → visible analysis → coherence findings with real evidence → HITL with real identity → exportable audit report) completable end-to-end from the UI. Today it breaks at upload (type hardcoded to `contract`), has no visible progress, fabricates display data, records HITL decisions as `"current-user"`, and has no report export.
- **Sources**: analysis `docs/audits/C2Pro — Frontend, Product, Marketing & End-User Analysis_Fable5.md` (evidence, §12 backlog) · executable patch-by-patch spec `docs/audits/C2Pro — Frontend Level-1 Implementation Prompt_Fable5.md` (authoritative per-task steps, tests, acceptance criteria, verify commands).
- **Task ↔ patch map**: `TASK-FRT-175`=PATCH 1 (typed upload) · 176=P2 (Overview hooks crash + honest metrics) · 177=P3 (coherence SSR auth) · 178=P4 (purge fabricated data) · 179=P5 (real HITL identity) · 180=P6 (analysis progress + polling) · 181=P7 (retry auth) · 182=P8 (landing honesty) · 183=P9 (dashboard shell + admin redirects) · 184=P10 (triplet checklist) · 185=P11 (run/evaluate actions) · 186=P12 (categories_v2 render) · 187=P13 (HITL scoping/cards) · 188=P14 (audit report export) · 189=P15 (global mutation errors) · 190=P16 (nav flags) · 191=P17 (single creation flow) · 192=P18 (CI wedge gates) · 193=P19 (budget reconciliation) · 194=P20 (severity tokens/EmptyState/tabs) · 195=P21 (onboarding mount) · 196=P22 (EN language) · 197=P23 (component consolidation + god-file split).
- **Definition of Done**: all 23 tasks `[x]` with evidence; `pnpm typecheck && pnpm lint && pnpm test:all && pnpm generate:api:check` green; `journey-3-wedge.spec.ts` (E2E-W1..W5) green in CI; manual demo script passes; zero fabricated data / dead controls / placeholder exports.
- **Review log — 2026-07-04, TASK-FRT-175 (Codex impl, master review: APPROVED)**: reproduced 37/37 focused tests, `pnpm typecheck`, and upload-path literal scan (0 `"BOM"`/`"CONTRACT"` hits); commits `a39b6309` (feat) + `62c509ce` (docs) on `fix/frt-l1-wave0`. Non-blocking polish for later waves: (a) staged-item ids can collide when the same file is staged in two batches (`name-size-lastModified-index` — use `crypto.randomUUID()`); (b) a mid-batch upload failure leaves already-uploaded files staged, so retry would duplicate them (remove items from staging as each succeeds); (c) `transformDocument` still maps `.bc3` files to `pdf` extension for display (`validExtension` array lacks `bc3`).
- **Implementation log — 2026-07-04, TASK-FRT-176 (PATCH 2)**: overview no longer declares hooks after loading/error returns; `Budget Used`/`Budget Pressure` are replaced with honest `Budget coherence` values (`sub_scores.BUDGET` or `—` with `Requires budget document` tooltip); overview status badge uses `useProject(id).data.status` and hides the row when unavailable. Verification: RED focused tests first failed on old fabricated labels/values, then `pnpm vitest run "app/(app)/projects/[id]/page.test.tsx" "app/(app)/projects/[id]/analysis"` -> 2 files / 10 tests passed; `pnpm typecheck` -> passed; `pnpm lint` -> passed; `rg "Budget Used|Budget Pressure|100 -|Active" "apps/web/app/(app)/projects/[id]/page.tsx" "apps/web/app/(app)/projects/[id]/analysis/page.tsx"` -> 0 hits; `rg "useMemo" "apps/web/app/(app)/projects/[id]/page.tsx"` -> 0 hits. `pnpm test:all` remains red on the existing unrelated 15 files / 34 tests already cataloged under TASK-FRT-192.
- **Implementation log — 2026-07-04, TASK-FRT-177 (PATCH 3)**: coherence server page now obtains the Clerk server token via `auth().getToken()`, skips the backend call when no token is available, and forwards `Authorization: Bearer <token>` into `getDashboardSummary(..., { server: true, headers })`; dashboard service options now preserve `headers` through to `fetchApiJson`; dev-only `cohV1Scenario` override remains unchanged. Verification: RED page tests first failed because the service call had no `Authorization` header and still ran with a null token; GREEN `pnpm vitest run lib/api/services "app/(app)/projects/[id]/coherence/page.test.tsx"` -> 4 files / 13 tests passed; requested service slice `pnpm vitest run lib/api/services` -> 3 files / 10 tests passed; `pnpm typecheck` -> passed; `pnpm lint` -> passed. `pnpm test:all` remains red on the existing unrelated 15 files / 34 tests already cataloged under TASK-FRT-192. Manual local-backend browser check not run in this non-interactive patch session.
- **Implementation log — 2026-07-04, TASK-FRT-178 (PATCH 4)**: project alerts no longer synthesize assignees or `clause-${id}` values; `ReviewAlert.assignee` and `ReviewAlert.clauseId` are optional and render honest placeholders when backend data is absent. `CoherenceClient` now derives severity distribution and per-category alert counts from the generated project-alerts query, shows honest loading/no-data states when alert data is unavailable, hides empty trend sparklines, and removes the internal migration banner. `AppHeader` no longer shows fake notification counts/items and links "View all notifications" to `/alerts`; dead Profile/Settings items were removed. Verification: RED focused tests first failed on fabricated alert props, optional placeholder handling, fake notification assertions, and mocked coherence alert counts; GREEN `pnpm vitest run "app/(app)/projects/[id]/alerts" components/coherence components/layout/AppHeader.test.tsx components/features/alerts/AlertReviewCenter.test.tsx` -> 8 files / 50 tests passed; `rg -n "legal\.reviewer|finance\.analyst|clause-\$\{" apps/web/app apps/web/components` -> 0 hits; `rg -n "Coherence Score v1 is active" apps/web/components/coherence/CoherenceClient.tsx` -> 0 hits; `pnpm typecheck` -> passed; `pnpm lint` -> passed; `pnpm generate:api:check` -> passed. `pnpm test:all` remains red on the existing unrelated 15 files / 34 tests already cataloged under TASK-FRT-192.
- **Implementation log — 2026-07-04, TASK-FRT-179 (PATCH 5)**: HITL review approve/reject and evidence alert resolution now derive reviewer identity from Clerk `useUser()` (`primaryEmailAddress.emailAddress` falling back to `user.id`) instead of literal audit-trail strings; identity-dependent action buttons are disabled with "Loading your identity…" while the user is unavailable. Verification: RED focused tests first failed because mutation bodies still sent `current-user` and `web-evidence-viewer`; GREEN `pnpm vitest run "app/(app)/projects/[id]/review" "app/(app)/projects/[id]/evidence"` -> 2 files / 25 tests passed; `rg -n "current-user|web-evidence-viewer" apps/web` -> 0 hits; `pnpm typecheck` -> passed; `pnpm lint` -> passed. `pnpm test:all` remains red on the existing unrelated 15 files / 34 tests already cataloged under TASK-FRT-192.
- **Implementation log — 2026-07-10, TASK-FRT-180 + TASK-FRT-181 (PATCH 6 + PATCH 7)**: `AnalysisProgressTracker` now exposes four user-facing stages while retaining the existing SSE/token helper and optional technical detail; Analysis mounts the tracker and no longer links to the raw process stream; Documents mounts progress while documents are uploaded/queued/processing; `useProjectDocuments` now uses React Query polling while documents are in-flight; Retry processing now uses `apiClient.post` and surfaces failures through `showToast`. Verification: RED focused tests first failed on the old 17-node copy, raw stream link, no polling, raw unauthenticated fetch, and silent retry failure; GREEN `pnpm vitest run components/features/analysis hooks/useProjectDocuments.test.ts "app/(app)/projects/[id]/analysis" "app/(app)/projects/[id]/documents"` -> 4 files / 30 tests passed; `pnpm typecheck` -> passed; `pnpm lint` -> passed. Broader guard `pnpm vitest run "app/(app)/projects/[id]" components/coherence` -> 13 files / 91 tests passed and 3 unrelated failures in untouched budget/settings/wbs tests, matching already-cataloged TASK-FRT-192 debt scope.
- **Implementation log — 2026-07-11, TASK-FRT-184 + TASK-FRT-185 (PATCH 10 + PATCH 11)**: added a reusable contract/budget/schedule `TripletChecklist` with missing/processing/ready states, Documents upload CTAs that preselect the requested document type, a compact Overview variant, and complete-triplet success row. Coherence evaluation and analysis re-run actions now use the generated mutation hooks, invalidate coherence dashboard/project alerts/document queries on success, and stay disabled until the triplet is complete. Contract check: generated coherence still posts `ProjectContext` to `/coherence/evaluate`, while the backend accepts `{ project_id, analysis_id?, clauses?, max_chunks?, low_budget_mode?, include_rag_similarity? }` at `POST /api/v1/coherence/evaluate`; generated analysis posts `AnalyzeRequest` to `/api/v1/analysis/analyze`, while backend accepts `{ project_id, document_id?, analysis_prompt? }`. Verification: RED focused tests first failed on missing triplet/action modules, missing upload preselection, and absent disabled actions; GREEN focused run `pnpm vitest run components/features/documents/TripletChecklist.test.tsx components/features/documents/DocumentUploadDropzone.test.tsx hooks/useProjectCoherenceActions.test.tsx "app/(app)/projects/[id]/documents/page.test.tsx" "app/(app)/projects/[id]/page.test.tsx" "app/(app)/projects/[id]/analysis/page.test.tsx" "app/(app)/projects/[id]/coherence/coherence-actions.test.tsx" "app/(app)/projects/[id]/coherence/page.test.tsx"` -> 8 files / 52 tests passed; `pnpm typecheck` -> passed after generated client restore; `pnpm lint` -> passed; `pnpm generate:api:check` -> passed with no diff failure. Broader guard `pnpm vitest run "app/(app)/projects/[id]" components/coherence` -> 14 files / 96 tests passed and 3 known TASK-FRT-192 failures in untouched budget/settings/wbs tests.
- **Implementation log — 2026-07-11, TASK-FRT-186 (PATCH 12)**: `getDashboardSummary` now maps through the nullable `categories_v2` payload when the backend includes it, and `CoherenceClient` replaces the v1 sub-category grid with an evidence-aware categories panel when v2 category data is available. The panel renders status, score only when present, evidence coverage only when present, missing evidence, conflicts, and recommendation without fabricating defaults. `INSUFFICIENT_EVIDENCE` now uses neutral styling, and `AUDIT_INCOMPLETE` copy now explains that the score is withheld until missing documents are uploaded. Verification: RED focused tests first failed on missing v2 category rendering, missing dashboard mapping, and old `AUDIT_INCOMPLETE` copy; GREEN `pnpm vitest run components/coherence lib/api/services/dashboard.test.ts` -> 7 files / 42 tests passed; requested slice `pnpm vitest run components/coherence "app/(app)/projects/[id]/coherence"` -> 8 files / 41 tests passed; `pnpm typecheck` -> passed; `pnpm lint` -> passed; honesty grep for `?? 0` / `|| 0` in coherence/contracts -> 0 hits. Broader guard `pnpm vitest run "app/(app)/projects/[id]"` still shows only the 3 known TASK-FRT-192 failures in untouched budget/settings/wbs tests.
- **Implementation log — 2026-07-12, TASK-FRT-192 (PATCH 18)**: repaired the stale and hidden frontend test debt before turning on the CI wedge gate. AppSidebar tests now match the current authenticated home (`/dashboard`) and the component route was corrected where it still emitted `/`; RACI tests enable the feature flag the page now requires; settings now asserts the generated-client `expected_version` contract; WBS tests provide route params and an explicit loaded hook fixture; hidden `test:all` drift was aligned for waitlist timers, global documents backend copy, alert/entity/generated-API contracts, analytics sorting, WBS label rendering, and wireframe guard selectors. Frontend CI now runs `pnpm test:all`, and `journey-3-wedge.spec.ts` covers the deterministic typed-triplet -> evaluate -> evidence -> identity-approve -> report-export journey with a skipped `@real-backend` variant. Verification: RED focused debt run first failed 4 files / 14 tests; GREEN focused run passed 4 files / 18 tests; final `pnpm test:all` passed 216 files / 717 tests plus 51 files / 126 tests; `pnpm typecheck` passed; `pnpm lint` passed. Local Playwright execution was blocked before spec execution by missing `CLERK_PUBLISHABLE_KEY` after bypassing an occupied port 3100.
- **Implementation log — 2026-07-12, TASK-FRT-193 (PATCH 19)**: Budget reconciliation is now available on the Budget tab through `ReconciliationCard`, but only when the live `categories_v2.BUDGET` payload contains structured stated/computed/contract totals. Data-shape audit found DET-BUD-SUM/DET-BUD-INTERNAL totals in backend `FindingSignal.raw_data`, while the current dashboard v2 adapter and generated alert response do not reliably expose that raw data. The frontend therefore parses only structured category payloads defensively and renders nothing when totals are absent. `useBudget` now exports typed category breakdown and variance interfaces instead of an anonymous record. Backend follow-up `TASK-BCK-093` tracks first-class typed reconciliation fields. Verification: RED focused tests failed first on missing card/wiring; GREEN `pnpm vitest run components/features/budget "app/(app)/projects/[id]/budget" hooks/useBudget.test.ts` passed 3 files / 6 tests; `pnpm test:all` passed 218 files / 724 tests plus 51 files / 126 tests; `pnpm typecheck` passed; `pnpm lint` passed.
- **Review log — 2026-07-04, TASK-FRT-176 (Codex impl, master review: APPROVED)**: reproduced 10/10 focused tests + `pnpm typecheck` + honesty scans (no `Budget Used`/`Budget Pressure`/`useMemo`/hardcoded `Active` in the touched routes; the single remaining "Budget Pressure" hit is the negative assertion in the analysis test). Empirical RED proof: with the new test suite run against the **old** implementation (selective stash of `page.tsx`), 3 tests fail — including "does not crash when the overview transitions from loading to backend data" — confirming genuine Rules-of-Hooks regression coverage, not test theater. `useProject(id)` correctly registered before the early returns; sub_scores typing hardened to `number | null | undefined`. No new debt introduced.
- **Pre-existing test debt quantified (blocks TASK-FRT-192's `test:all` gate)**: `pnpm test:all` fails **15 files / 34 tests identically on `main` (fc863e25) and on the branch** — RACI page (7), AppSidebar (5), WBSTree contract (6), UsageMetricsTable (4), wireframes WF-03/WF-04 (3), and 1 each in app/page, ProjectTabs, useAlerts, useDocumentEntities, lib/api/index.test, global documents page, project budget/settings/wbs pages. These must be fixed or explicitly quarantined as part of TASK-FRT-192 before `test:all` can become a CI gate.
- **External deps (backend, already tracked)**: `TASK-DOC-REUPLOAD-005` (re-upload PATCH 500), `TASK-COH-BUD-RECON-006` (EN/INR totals). Frontend degrades honestly where these bite.

### TASK-FRT-171 - Production partial failure resilience

- Keep the project overview route renderable when the alerts subrequest fails but the coherence dashboard payload succeeds; use the dashboard alert count as a fallback and show a local panel warning instead of replacing the whole page with an error.

### TASK-FRT-172 - Dashboard return path

- Keep the dashboard overview reversible: the top-level portfolio screen must expose a visible link back to `/projects` before any project drill-down begins.

### TASK-FRT-173 - Upload failure clarity

- If an upload request fails before the file is queued, the UI must say that plainly, distinguish it from a successful queue handoff, and give the user a next step instead of surfacing a raw transport message.

### TASK-FRT-174 - Shared sub-window surface system

- Dialogs, alert dialogs, and sheets should use the same solid elevated surface, foreground color, border treatment, and shadow so secondary windows feel like one system and preserve contrast in both themes.

---

### EPIC-FRT-LANDING-SYNC — c2pro.io Landing × AI-Gen Brand Synchrony (2026-07-06)

**Goal:** c2pro.io serves a crawlable, AI-Gen-branded, honest, bilingual (ES `/` + EN `/en`) landing with a working pilot-waitlist funnel and correct SEO metadata.

**Evidence (2026-07-06):** root `app/page.tsx` is client-gated on `useAuth` → crawlers receive only "Loading..." (verified via live fetch of www.c2pro.io); `components/landing-page-content.tsx` shows fabricated stats (94% detection, $2.4M savings, 6x faster) violating the honesty doctrine (ADR-013) and AI-Gen's "no promete detección perfecta" positioning; dead `#` links (Pricing/Privacy/Terms) + "Deploy marker 2026-03-30-a" debug text; ai-gen.ai's C2Pro pilot-waitlist form captures no leads (its `site.js` intercepts POSTs — "sin backend todavía").

**Brand reference:** AI-Gen Design System v2 "Tech-Editorial B2B Premium" (`AI-Gen-AI/2SB` repo, `assets/site.css`): alabaster `#F7F4ED` / navy `#0B1F3A` / single teal accent `#0F766E`, Source Serif 4 display + Geist + Geist Mono eyebrows, editorial sections, "Vista ilustrativa"-labeled console mockups.

**Owner decisions (2026-07-06):** in-app rewrite (not a separate marketing site); bilingual ES default + `/en`; real waitlist capture on c2pro.io (endpoint CORS-ready so ai-gen.ai's form can POST to it later); `/` stays fully static — authed users get an "Ir al workspace" island instead of an auto-redirect.

**Executable spec:** `docs/audits/C2Pro — Landing AI-Gen Sync Implementation Prompt_Fable5.md` (5 patches, verbatim ES/EN Copy Pack included; Codex executes patch-by-patch, MASTER reviews each).

---

## 3. Lessons Learned

_Lessons learned will be documented here_

---

## 4. Architectural Decisions

_ADRs for this category will be documented here_

---

## 5. Technical Debt

| Debt ID | Description | Impact | Effort | Created |
| ------- | ----------- | ------ | ------ | ------- |

---

## 6. Metrics

- **Total Tasks**: 202
- **Completed**: 201 (99.5%)
- **Average Completion Time**: TBD
- **Test Coverage**: TBD

---

## 7. Audit Reports

### Frontend Integration Test Audit (TASK-REV-FRONTEND-001)

**Date**: 2026-04-07
**Status**: ✅ Stabilized (48/48 Files Passing)

#### Findings:

1. **Root Cause of ERR_INVALID_URL**: Node.js `fetch` implementation in Vitest/JSDOM does not support relative URLs. Any call to `fetch('/api/...')` throws `ERR_INVALID_URL` because it lacks an origin.
2. **Current Fix**: The project implemented a custom MSW shim in `apps/web/src/tests/shims/msw-node.ts` that overrides `global.fetch` and automatically prepends `http://localhost` to relative paths.
3. **act() Warnings**: Many integration tests (Shortcuts, Mobile Evidence) still emit React `act(...)` warnings. These occur when state updates (e.g., from `fireEvent.keyDown` on `window`) are not correctly wrapped or awaited.
4. **Axios Inconsistency**: `vitest.setup.ts` sets `axios.defaults.baseURL = "/api"`. This is relative and will FAIL in Node for any non-mocked request. It currently works only because integration tests predominantly use `fetch`.

#### Recommendations:

- **Stabilization**: Sprint 2 task should be created to wrap failing state updates in `act()` to eliminate console noise and potential race conditions.
- **Consistency**: Update `axios.defaults.baseURL` to `http://localhost/api` in `vitest.setup.ts` to provide a consistent origin for all HTTP clients in the test environment.
- **Maintenance**: Retain the `msw-node.ts` shim until a full migration to a real `msw/node` setup is feasible (currently blocked by ESM/CJS issues).
