# Frontend Tasks & Knowledge Base

**Category**: Frontend (FRT)
**Owner Role**: frontend
**Last Updated**: 2026-07-04

**Quick Links**:

- 🏠 [Master Index](../C2PRO_MASTER_BACKLOG.md)
- 📋 [Role Profile](../roles/role_frontend.md)

---

## 0. Status View

**Pending Tasks**: 12

- IDs: `TASK-FRT-041` (blocked — requires Clerk dashboard operator access)
- IDs: `TASK-FRT-182`-`TASK-FRT-197` — **EPIC-FRT-L1-WEDGE** (Level-1 wedge closure, 2026-07-04). Wave 0/P0: 182-183 · Wave 1/P1: 186-192 pending · Wave 2/P2: 193-197. Patch-by-patch executable spec: `docs/audits/C2Pro — Frontend Level-1 Implementation Prompt_Fable5.md`
- IDs: `TASK-FRT-198`-`TASK-FRT-202` — **EPIC-FRT-LANDING-SYNC** (c2pro.io landing × AI-Gen brand synchrony, 2026-07-06). Single wave P1: 198-202 complete. Patch-by-patch executable spec: `docs/audits/C2Pro — Landing AI-Gen Sync Implementation Prompt_Fable5.md`

**Completed Tasks**: 186

- IDs: `TASK-FRT-001`-`TASK-FRT-040`, `TASK-FRT-042`-`TASK-FRT-181`, `TASK-FRT-184`-`TASK-FRT-185`, `TASK-FRT-198`-`TASK-FRT-202`

**Usage Note**:

- Use this section to see what still needs execution without scanning the full table.
- The detailed register below remains the authoritative task history.

## 1. Active Tasks

| Status | Priority | Task ID        | Depends On | Description                                                                                                                                                                                                                                                                                                                                                                                                                                                                                             | Source                                              |
| ------ | -------- | -------------- | ---------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- | --------------------------------------------------- |
| [x]    | P0       | `TASK-FRT-175` | None       | Typed document upload: per-file type selector (contract/budget/schedule/…) defaulted by extension; kill hardcoded `"CONTRACT"` in `DocumentUploadDropzone.tsx:81`; align `uploadDocument` union with generated `DocumentType` (remove `BOM`, add `budget`); fix `budget→bom` display mapping. Unblocks the triplet — the product wedge. `[x] Implemented (Typed Staged Upload + Generated DocumentType)` | `Fable5 L1 Prompt — PATCH 1` |
| [x]    | P0       | `TASK-FRT-176` | None       | Fix Rules-of-Hooks crash in project Overview (`useMemo` after early returns → crash on loading→data); remove hardcoded `Status: Active` and fabricated `Budget Used = 100−subscore` (honest `Budget coherence` value or `—`); same fix on Analysis page. `[x] Implemented (Overview Hooks + Honest Budget Coherence)` | `Fable5 L1 Prompt — PATCH 2` |
| [x]    | P0       | `TASK-FRT-177` | None       | Coherence page SSR with real credentials: thread Clerk server token into `fetchApiJson({server:true})` (today it sends no Authorization/tenant headers → core tab 401s). `[x] Implemented (Clerk Server Token Forwarding)` | `Fable5 L1 Prompt — PATCH 3` |
| [x]    | P0       | `TASK-FRT-178` | None       | Purge fabricated UI data: fake assignees + synthesized `clause-${id}` (project alerts), fabricated severity distribution / `alertCount=0` / empty trend (CoherenceClient), fake notifications + dead menu items (AppHeader), internal "v1 active" banner. Real data or honest placeholder. `[x] Implemented (Fabricated UI Data Purge)` | `Fable5 L1 Prompt — PATCH 4` |
| [x]    | P0       | `TASK-FRT-179` | None       | Real reviewer identity: HITL approve/reject and evidence resolve send Clerk user email/id instead of literals `"current-user"` / `"web-evidence-viewer"`; buttons disabled until identity loaded. Audit-trail integrity. `[x] Implemented (Clerk Reviewer Identity)` | `Fable5 L1 Prompt — PATCH 5` |
| [x]    | P0       | `TASK-FRT-180` | `TASK-FRT-175` | Visible analysis progress: simplify orphaned `AnalysisProgressTracker` to 4 user-facing stages, mount on Analysis + Documents; convert `useProjectDocuments` to react-query with polling while docs in-flight; delete the raw-SSE `<Link>` dead end. ✅ Implemented 2026-07-11 on `feat/frt-l1-wave0-cont` (PR #186, MASTER-approved): 4-stage tracker mounted on Analysis+Documents, react-query polling 5s while docs in-flight, raw-SSE link removed. 34 focused tests green, typecheck/lint clean. | `Fable5 L1 Prompt — PATCH 6` |
| [x]    | P0       | `TASK-FRT-181` | None       | Fix "Retry processing": raw `fetch` sends no Authorization (guaranteed 401, silent failure) → use `apiClient.post` + visible error toast. ✅ Implemented 2026-07-11 on `feat/frt-l1-wave0-cont` (PR #186, MASTER-approved): retry via apiClient.post with toast on failure + refetch on success. | `Fable5 L1 Prompt — PATCH 7` |
| [x]    | P0       | `TASK-FRT-182` | None       | Landing honesty pass: remove fabricated metrics (94%/6x/$2.4M/<30s) and visible deploy marker; fix `Get Started → /signup` (dead) to `/sign-up`; remove dead Pricing anchor; retitle tab (`C2Pro — Contract Coherence Audit`); triplet-focused hero subhead. ✅ Superseded/absorbed 2026-07-09 by EPIC-FRT-LANDING-SYNC (TASK-FRT-198/200/202): landing rebuild removed all fabricated metrics + deploy marker (grep 0 hits for `94%|2.4M|6x Faster|Deploy marker`), replaced old nav/CTAs (0 hits `/signup`, 0 dead `#` anchors), retitled via app/layout.tsx metadata. PR #183 merged 2026-07-10; live on c2pro.io. | `Fable5 L1 Prompt — PATCH 8` |
| [ ]    | P0       | `TASK-FRT-183` | None       | Dashboard inside the app shell: drop the `/dashboard→/` permanent redirect, authed `/` redirects to `/dashboard` (renders with sidebar/header); delete ghost `/admin/*` role redirects (404 today); guided zero-projects empty state with Create CTA. ⚠️ Descoped 2026-07-10: the 'authed `/` redirects to `/dashboard`' sub-item is SUPERSEDED by the owner-approved EPIC-FRT-LANDING-SYNC design (static public `/`, no auth auto-redirect, 'Ir al workspace' header island). Admin bounces already relocated to `/dashboard` (PATCH 1, merged). Remaining scope: dashboard inside app shell (sidebar/header) + guided zero-projects empty state with Create CTA. | `Fable5 L1 Prompt — PATCH 9` |
| [x]    | P1       | `TASK-FRT-184` | `TASK-FRT-175`, `TASK-FRT-180` | Triplet checklist (contract/budget/schedule slots: missing/processing/ready) on Documents + compact variant on Overview; per-slot CTA opens upload dialog with type preselected; success row when complete. ✅ Implemented 2026-07-11 on `feat/frt-l1-wave1-a`: reusable triplet checklist, Documents upload preselection, and Overview compact state. | `Fable5 L1 Prompt — PATCH 10` |
| [x]    | P1       | `TASK-FRT-185` | `TASK-FRT-180`, `TASK-FRT-184` | "Evaluate coherence" + "Re-run analysis" actions wired to the never-used generated mutations (`useEvaluateProjectCoherence…`, analyze/reprocess); verify request contract first; invalidate dashboard/alerts queries on success; disabled until triplet complete. ✅ Implemented 2026-07-11 on `feat/frt-l1-wave1-a`: generated mutation hooks wired through guarded actions, dashboard/alerts/documents invalidated on success, and actions disabled until the triplet is complete. | `Fable5 L1 Prompt — PATCH 11` |
| [ ]    | P1       | `TASK-FRT-186` | `TASK-FRT-177` | Render `categories_v2` (typed in `contracts.ts:50-75`, never displayed): per-category status, evidence coverage, missing evidence, conflicts, recommendation; map through `getDashboardSummary`; humanize `AUDIT_INCOMPLETE` copy. | `Fable5 L1 Prompt — PATCH 12` |
| [ ]    | P1       | `TASK-FRT-187` | `TASK-FRT-179` | HITL queue project scoping (pass project param or honest retitle; register backend task if filter missing), human-readable `ReviewItemCard` with evidence link (raw JSON behind disclosure), visible mutation errors, pagination. | `Fable5 L1 Prompt — PATCH 13` |
| [ ]    | P1       | `TASK-FRT-188` | `TASK-FRT-178`, `TASK-FRT-179`, `TASK-FRT-186` | Audit Report export v1: new `/projects/[id]/report` tab composing score + categories + findings by status + evidence refs + HITL decisions with reviewers; print-optimized A4 route + JSON download; remove `alert()` PDF placeholder in Budget. The product's value output. | `Fable5 L1 Prompt — PATCH 14` |
| [ ]    | P1       | `TASK-FRT-189` | None       | Global mutation error surface: `MutationCache.onError` → toast in `createQueryClient`; remove swallow patterns (`catch {}`, `console.error`-only in useBudget etc.). No silent write failures anywhere. | `Fable5 L1 Prompt — PATCH 15` |
| [ ]    | P1       | `TASK-FRT-190` | None       | Navigation focus: flags `NEXT_PUBLIC_FEATURE_INTERNAL_DASHBOARDS` (AI Analytics/Observability) + `NEXT_PUBLIC_FEATURE_PHASE2_MODULES` (Stakeholders/WBS), default off; prune sidebar/project tabs to Level-1 surface; remove decorative header search input. | `Fable5 L1 Prompt — PATCH 16` |
| [ ]    | P1       | `TASK-FRT-191` | None       | Single project-creation flow: `/projects/new` → `redirect('/projects?create=1')` opening the wizard; delete decorative Templates + Batch Import dialogs; extract `CreateProjectWizard` component (starts god-file split). | `Fable5 L1 Prompt — PATCH 17` |
| [ ]    | P1       | `TASK-FRT-192` | `TASK-FRT-175`…`TASK-FRT-188` | CI wedge gates: `pnpm test:all` in frontend-ci (today only 50/249 test files gate); new `journey-3-wedge.spec.ts` (E2E-W1..W5: typed triplet → progress → evaluate → evidence → identity-approve → export) MSW-deterministic + `@real-backend` variant. | `Fable5 L1 Prompt — PATCH 18` |
| [ ]    | P2       | `TASK-FRT-193` | `TASK-FRT-186` | Budget reconciliation block: Stated vs Computed vs Contract totals with delta % (pilot: 636M vs 654M = 2.8%) sourced from DET-BUD findings / `categories_v2.BUDGET`; replace duck-typed budget response with real types. | `Fable5 L1 Prompt — PATCH 19` |
| [ ]    | P2       | `TASK-FRT-194` | None       | Design-system consolidation: single `severityToToken`/`statusToToken` source (kill ≥4 divergent raw-Tailwind maps), shared `EmptyState` component, ProjectTabs active state + `aria-current`. | `Fable5 L1 Prompt — PATCH 20` |
| [ ]    | P2       | `TASK-FRT-195` | `TASK-FRT-183` | Mount orphaned onboarding: `OnboardingEntry` + sample-project bootstrap on first login (zero projects, not dismissed); persist dismissal. | `Fable5 L1 Prompt — PATCH 21` |
| [ ]    | P2       | `TASK-FRT-196` | None       | Language unification (EN): translate `"Sesión expirada o inválida"` / `"Sin permisos"` toasts and Spanish form placeholders; grep-clean. Full i18n out of scope. | `Fable5 L1 Prompt — PATCH 22` |
| [ ]    | P2       | `TASK-FRT-197` | `TASK-FRT-186`, `TASK-FRT-188`, `TASK-FRT-191` | Component-root consolidation (merge `src/components` + `features/coherence` duplicates into one canonical root), split 1,636-line evidence page, delete `GlobalSearch`/`CrossModuleNavigator` RED-phase placeholders + 3D view/no-op templates; enforce <800 lines/file. | `Fable5 L1 Prompt — PATCH 23` |

#### EPIC-FRT-LANDING-SYNC — c2pro.io Landing × AI-Gen Brand Synchrony (2026-07-06)

| Status | Priority | ID | Depends On | Description | Source |
|--------|----------|----|------------|-------------|--------|
| [x]    | P1       | `TASK-FRT-198` | None       | Root route restructure: `/` + `/en` server-rendered landing (SEO fix — crawlers currently receive only "Loading..."), Clerk auth island ("Ir al workspace"), admin-bounce relocated to `/dashboard`, "Deploy marker" debug text removed. ✅ Completed 2026-07-08: `/` and `/en` build as static routes; `/en` is public in middleware; `/` HTML contains landing markup, "Iniciar sesión", and "Unirse al piloto" with no auth spinner; signed-in users see "Ir al workspace"; `c2pro_admin` dashboard visits replace-navigate to `/admin/c2pro`; `tenant_admin` still replace-navigates to `/admin/tenant`; explicit fabricated metric scaffold removed; deploy marker scan clean. | `Fable5 Landing Prompt — PATCH 1` |
| [x]    | P1       | `TASK-FRT-199` | None       | AI-Gen Design System v2 tokens as additive `brand-*` `@theme` block, self-hosted Source Serif 4 + Geist/Geist Mono fonts (no Google CDN), landing primitives (Eyebrow/Display/SectionShell/BrandButton/PilotBadge/CheckList) + Reveal (reduced-motion safe). ✅ Completed 2026-07-09: added bundled `geist` + `@fontsource-variable/source-serif-4`, additive brand tokens, landing font exports, server-compatible primitives, reduced-motion-aware Reveal, and landing barrel exports; `fonts.googleapis` scan clean; build passes with no live-page consumption yet. | `Fable5 Landing Prompt — PATCH 2` |
| [x]    | P1       | `TASK-FRT-200` | `TASK-FRT-198`, `TASK-FRT-199` | Landing rebuild with verbatim ES/EN Copy Pack: hero + honest console mock (real DET-BUD-SUM 2.8% example, "Vista ilustrativa"), tridimensional audit, human-supervision band, 4-step protocol, origin & limits ("Qué no hace"), navy waitlist shell, ecosystem footer → ai-gen.ai; deletes fabricated-stats scaffold (94%/$2.4M/6x). ✅ Completed 2026-07-08: rebuilt `/` and `/en` with the Copy Pack, labeled illustrative console, waitlist mailto shell for PATCH 4, AI-Gen external links with `rel="noopener"`, no dead `href="#"`, and old fabricated-claim scan clean. | `Fable5 Landing Prompt — PATCH 3` |
| [x]    | P1       | `TASK-FRT-201` | `TASK-FRT-200` | Pilot waitlist funnel: `waitlist_signups` table (Alembic + Supabase mirror, RLS enabled deny-all, unique email), `/api/waitlist` route handler (zod, honeypot, per-IP throttle, CORS allowlist for ai-gen.ai whose current form captures no leads), bilingual client form with RGPD consent. ✅ Completed 2026-07-08: added additive waitlist migrations, server-only PostgREST route with zod validation/CORS/honeypot/throttle/idempotent upsert, bilingual form mounted into the navy waitlist shell, and server-only env template notes. | `Fable5 Landing Prompt — PATCH 4` |
| [x]    | P1       | `TASK-FRT-202` | `TASK-FRT-200` | SEO: per-locale metadata + canonical/hreflang (`/` es, `/en` en), JSON-LD Organization (parentOrganization AI-Gen) + SoftwareApplication (no invented ratings), `sitemap.ts`/`robots.ts`, `opengraph-image.tsx` (navy/teal brand card), brand `themeColor #0B1F3A`. ✅ Completed 2026-07-09: added locale metadata for `/` and `/en`, reciprocal canonical/hreflang alternates, landing JSON-LD, sitemap/robots routes, generated `opengraph-image`, and `themeColor #0B1F3A`; build output lists `/`, `/en`, `/opengraph-image`, `/robots.txt`, and `/sitemap.xml` as static routes; old app title scan clean. | `Fable5 Landing Prompt — PATCH 5` |

| [ ]    | P3       | `TASK-FRT-041` | None       | Production email templates and sender verified in Clerk `[-] Blocked: Requires operator Clerk dashboard access. Verification checklist in docs/runbooks/CLERK_AUTH_DEV_PROD_GUIDE.md (TASK-1177). Steps: (1) Verify sender email is noreply@c2pro.app with verified domain, (2) Customize sign-in/sign-up/reset templates with C2Pro branding, (3) Test email delivery from production instance.` | `docs/runbooks/CLERK_AUTH_DEV_PROD_GUIDE.md`        |
| [x]    | P1       | `TASK-FRT-172` | None       | Add an explicit return path from the dashboard portfolio overview to the Projects list so users are not stranded after entering Dashboard. `[x] Implemented (Dashboard Navigation Recovery)` | `User report 2026-05-16` |
| [x]    | P1       | `TASK-FRT-173` | `TASK-BCK-053` | Replace raw document-upload failure copy with a plain-language state that tells the user the file was not queued and what to do next. `[x] Implemented (Upload Failure Clarity)` | `User report 2026-05-16` |
| [x]    | P1       | `TASK-FRT-174` | None       | Standardize dialogs, alert dialogs, and sheets on one high-contrast elevated surface so sub-windows remain readable and visually consistent across the app. `[x] Implemented (Shared Sub-Window Surface System)` | `User report 2026-05-16` |

**Statistics**:

- Total: 202 tasks
- Active: 16 (7.9%)
- Completed: 186 (92.1%)
- Blocked: 1 (0.5%)

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
- **Completed**: 182 (90.1%)
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
