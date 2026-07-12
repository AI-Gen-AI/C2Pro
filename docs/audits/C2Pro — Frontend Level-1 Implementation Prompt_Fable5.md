# C2Pro — Frontend Level-1 Implementation Prompt (patch-by-patch)

**Date:** 2026-07-04 · **Epic:** `EPIC-FRT-L1-WEDGE` · **Backlog IDs:** `TASK-FRT-175` … `TASK-FRT-197` (registered in `C2PRO_MASTER_BACKLOG.md` and `backlogs/FRT_FRONTEND.md`)
**Source analysis:** `docs/audits/C2Pro — Frontend, Product, Marketing & End-User Analysis_Fable5.md` (2026-07-03). Every patch below cites the evidence that motivated it.

This document is a **self-contained execution prompt**. Feed it to a Claude Code session (or execute patches individually) as:

```text
Implement PATCH <N> (TASK-FRT-<ID>) from docs/audits/C2Pro — Frontend Level-1 Implementation Prompt_Fable5.md. Follow the Ground Rules section exactly.
```

---

## Role

You are a Senior Frontend Engineer working on `apps/web/` (Next.js 16 App Router, React 19, TypeScript strict, Tailwind v4 + shadcn/ui, TanStack Query v5, Zustand, Clerk, Orval-generated API client, Vitest + Playwright + MSW). You make surgical, evidence-based changes. You do not redesign, and you do not expand scope.

## Ground Rules (apply to every patch)

1. **Branching:** one branch per wave (`fix/frt-l1-wave0`, `feat/frt-l1-wave1`, `feat/frt-l1-wave2`) or per patch if asked. Never push to `main` (Husky guard `ALLOW_PUSH_MAIN=1` is reserved for the owner). Conventional commits (`fix:`, `feat:`, `test:`, `refactor:`), **no Co-Authored-By trailers**.
2. **TDD:** for each patch, write/adjust the failing test first (RED), implement (GREEN), then refactor. Colocated tests live next to the file; integration tests in `apps/web/src/tests/integration/`; E2E in `apps/web/src/tests/e2e/`.
3. **Verification before done (run from `apps/web/`):** `pnpm typecheck && pnpm lint && pnpm test:all` (all colocated + integration), plus the patch's own test command. If a patch touches generated-client usage, also `pnpm generate:api:check`.
4. **Honesty principle (project-wide invariant):** never render fabricated values. If real data is unavailable, render an honest placeholder (`—`, "No data yet", hidden section). This mirrors the backend honest-null doctrine (ADR-013).
5. **No new heavy dependencies** without flagging it in the PR description. Prefer what's installed (`sonner`, `cmdk`, `recharts`, `react-pdf` is a *viewer*, not a generator).
6. **Types come from the generated client** (`apps/web/lib/api/generated/**`). Never hand-roll a union that mirrors a backend enum (that is exactly the bug in PATCH 1).
7. **Backlog discipline (MANDATORY per `.claude/rules/CRITICAL_BACKLOG_REQUIREMENT.md`):** when a patch is completed, mark its `TASK-FRT-NNN` as `[x]` in `backlogs/FRT_FRONTEND.md` **and** update the counts + Change Log in `C2PRO_MASTER_BACKLOG.md` with verification evidence (tests run, commands, results). If you discover a new task, register it with an ID immediately.
8. **Scope guard:** if a patch turns out to require backend changes beyond what is listed under "External dependencies", stop, register the backend task, and report — do not improvise API changes.
9. **UI language is English** (one ES string exists today and PATCH 22 removes it).
10. **Known external dependencies (backend, already tracked):** `TASK-DOC-REUPLOAD-005` (PATCH `/documents/{id}/file` returns 500 — re-upload UX), `TASK-COH-BUD-RECON-006` (EN/INR contract totals). Do not block frontend patches on them; degrade honestly.

## Wave map

| Wave | Patches | Gate |
|---|---|---|
| **Wave 0 — P0 (demo blockers)** | 1–9 (`TASK-FRT-175`…`183`) | After Wave 0 the app must survive a live demo: triplet uploadable, no crashes, no fabricated data, real identities, visible progress |
| **Wave 1 — P1 (MVP)** | 10–18 (`TASK-FRT-184`…`192`) | Level-1 loop closes end-to-end in the UI incl. audit-report export; CI protects it |
| **Wave 2 — P2 (private beta)** | 19–23 (`TASK-FRT-193`…`197`) | Trust/polish: reconciliation view, design-system consolidation, onboarding, language, structure |

---

# WAVE 0 — P0 · Demo blockers

---

## PATCH 1 — Typed document upload (the wedge unblocker)

**Backlog ID:** `TASK-FRT-175` · **Priority:** P0 · **Depends on:** —

**Evidence:** `components/features/documents/DocumentUploadDropzone.tsx:81` hardcodes `"CONTRACT"` for every file. `lib/api/index.ts:210-216` declares a hand-rolled union containing `"BOM"` (not a backend value) and missing `"BUDGET"`. Backend requires `document_type: DocumentType = Form(...)` (`apps/api/src/documents/adapters/http/router.py:376`) and routes parsers by it (`composite_file_parser.py:60-92` — an XLSX typed `contract` raises). Generated enum is `contract | schedule | budget | drawing | specification | other` (`lib/api/generated/models/documentType.ts`). `hooks/useProjectDocuments.ts:21-29` maps `budget → 'bom'` for display.

**Files:**
- `apps/web/lib/api/index.ts` (uploadDocument signature)
- `apps/web/components/features/documents/DocumentUploadDropzone.tsx`
- `apps/web/hooks/useProjectDocuments.ts` + `apps/web/types/document.ts`
- `apps/web/app/(app)/projects/[id]/documents/page.tsx` (dialog copy)

**Steps:**
1. `uploadDocument(projectId, file, documentType: DocumentType, …)` — import the generated `DocumentType`; delete the hand-rolled union; pass `documentType` (already lowercase) directly. Remove the `"BOM"` value everywhere.
2. Dropzone becomes a two-step surface: (a) files are **staged** on drop/pick (not uploaded); (b) each staged row shows filename, size, and a `<Select>` of document type, **defaulted by extension** (`.pdf → contract`, `.xlsx/.bc3 → budget`) and always user-overridable (a schedule can be XLSX); (c) an explicit "Upload N file(s)" button uploads sequentially with the chosen type per file. Keep `ALLOWED_EXTENSIONS`, the max-size check, the sr-only live region, and `onUploadComplete`.
3. Fix `documentTypeMap` in `useProjectDocuments.ts`: `budget → 'budget'` (extend `DocumentInfo['type']` in `types/document.ts`; do not silently relabel `other → contract` — map `other → 'other'`).
4. Update the upload dialog description in the documents page to mention the three roles (contract / budget / schedule).

**Tests (RED first):**
- Rewrite `DocumentUploadDropzone.test.tsx`: staging renders one type select per file with the extension-based default; pressing Upload calls `uploadDocument` with the **selected** type per file; a `.docx` file is rejected with the existing message.
- `lib/api/uploadDocument.test.ts`: MSW handler asserts the multipart body contains `document_type=budget` when budget is selected; TypeScript no longer accepts `"BOM"` (compile-time).
- Integration (`src/tests/integration/uploads/`): update the existing upload specs to the staged flow.

**Acceptance criteria:**
- A user can upload one PDF as *contract*, one XLSX as *budget*, one XLSX as *schedule* in a single dialog session, and the three rows appear in the register with the correct type badges (`Budget` shown as Budget, never "Bom").
- No occurrence of `"CONTRACT"`/`"BOM"` literals in upload paths (`grep -rn '"BOM"\|"CONTRACT"' apps/web/lib apps/web/components` → 0 relevant hits).

**Verify:** `pnpm vitest run components/features/documents lib/api/uploadDocument.test.ts && pnpm typecheck`

---

## PATCH 2 — Project Overview: fix Rules-of-Hooks crash + honest metrics

**Backlog ID:** `TASK-FRT-176` · **Priority:** P0 · **Depends on:** —

**Evidence:** `app/(app)/projects/[id]/page.tsx:41-57` returns early on loading/error, then declares 5 `useMemo` (`:63-102`) → "Rendered more hooks than during the previous render" on the loading→data transition. Same file hardcodes `Status: Active` (`:133`) and fabricates `Budget Used = 100 − BUDGET subscore` (`:101`).

**Files:** `apps/web/app/(app)/projects/[id]/page.tsx` (+ its test), `apps/web/app/(app)/projects/[id]/analysis/page.tsx` (same "Budget Pressure" fabrication at `:77,104-108`).

**Steps:**
1. Move all hooks above the conditional returns (or simply drop the `useMemo`s — the computations are trivial derivations; plain consts are fine and remove the hazard permanently).
2. Replace the `Budget Used` / `Budget Pressure` cards with an honest metric: label **"Budget coherence"**, value `sub_scores.BUDGET ?? '—'` (no arithmetic inversion). If null → `—` with tooltip "Requires budget document".
3. Replace hardcoded `Active` badge with the project's real `status` (available via `useProject(id)`); if unavailable, hide the row.

**Tests (RED first):**
- Component test that renders with react-query in `isLoading` state first, then rerenders with data (use a controllable QueryClient / deferred promise): **must not throw**. This is the regression test for the crash.
- Assert the string `Active` is not hardcoded (badge reflects mocked status `draft`), and `Budget coherence` renders `—` when `sub_scores.BUDGET` is absent.

**Acceptance criteria:** Overview loads on a real network waterfall without the error boundary firing; no invented percentages anywhere on Overview/Analysis.

**Verify:** `pnpm vitest run "app/(app)/projects/[id]/page.test.tsx" "app/(app)/projects/[id]/analysis"`

---

## PATCH 3 — Coherence page SSR with real credentials

**Backlog ID:** `TASK-FRT-177` · **Priority:** P0 · **Depends on:** —

**Evidence:** `lib/api/services/http.ts:90-97` — the `server: true` branch only forwards headers if the caller passes them; `app/(app)/projects/[id]/coherence/page.tsx:23` calls `getDashboardSummary(id, { server: true })` with none → unauthenticated backend call for the product's core tab.

**Files:** `apps/web/app/(app)/projects/[id]/coherence/page.tsx`, `apps/web/lib/api/services/http.ts`, `apps/web/lib/api/services/dashboard.ts`.

**Steps:**
1. In the server component: `import { auth } from "@clerk/nextjs/server"; const { getToken } = await auth(); const token = await getToken();`.
2. Thread headers through: `getDashboardSummary(id, { server: true, headers: { Authorization: \`Bearer ${token}\` } })` — extend the `options` passthrough in `dashboard.ts` (it already forwards `options` into `fetchApiJson`; just make sure `headers` survives).
3. If `token` is null (signed-out edge), render the existing error/empty state instead of calling the API.
4. Keep the dev-only `cohV1Scenario` override untouched.

**Tests (RED first):** unit test for `fetchApiJson` server branch asserting provided `Authorization` header reaches `fetch` (mock global fetch); page-level test mocking `@clerk/nextjs/server`'s `auth()` to return a token and asserting the request carried it.

**Acceptance criteria:** With a signed-in session, `/projects/{id}/coherence` renders live data (no "Verify the backend service is available" banner caused by 401). Manual check against local backend documented in the PR.

**Verify:** `pnpm vitest run lib/api/services && pnpm typecheck`

---

## PATCH 4 — Purge fabricated data (alerts, coherence charts, header)

**Backlog ID:** `TASK-FRT-178` · **Priority:** P0 · **Depends on:** —

**Evidence:** `app/(app)/projects/[id]/alerts/page.tsx:25-48` fabricates assignees (`legal.reviewer`, `finance.analyst`, …) and clause refs (`clause-${alert.id}`). `components/coherence/CoherenceClient.tsx:148-155` renders `AlertsDistribution critical={0} high={0} medium={summary.alert_count} low={0}`; `:168` passes `alertCount={0}` per category; `:182` `trend={[]}`. `components/layout/AppHeader.tsx:53` fakes `notificationCount = 3` in demo and hardcodes two notification items (`:165-185`); "View all notifications" (`:198-200`) and Profile/Settings menu items (`:233-239`) do nothing.

**Files:** the three above + `components/features/alerts/AlertReviewCenter.tsx` (make `assignee`/`clauseId` optional in `ReviewAlert`), `components/coherence/CategoryDetail.tsx` (optional trend), `components/coherence/AlertsDistribution.tsx` (accept real counts).

**Steps:**
1. Alerts page: delete `ASSIGNEE_MAP` and the synthesized `clauseId`. Make both fields optional in `ReviewAlert`; `AlertReviewCenter` renders `—` (or hides the column) when absent. If the backend alert carries usable fields (`category`, `evidence_json.evidence_location`), pass those through instead.
2. CoherenceClient: derive the severity distribution from **real** alerts — fetch them client-side with the generated `useListProjectAlertsApiV1ProjectsProjectIdAlertsGet(summary.project_id)` and count by `severity`; per-category `alertCount` = count of alerts whose `category` matches; while loading or on error, render the chart area with an honest skeleton/"No alert data". Remove the `trend` sparkline until real data exists (`CategoryDetail` hides that section when `trend` is empty).
3. AppHeader: `notificationCount = 0` always; delete the hardcoded demo notification items; keep the honest empty message. "View all notifications" → `Link` to `/alerts`; delete the dead Profile/Settings items (keep Sign out) — or wire Settings to `/settings`.
4. Also remove the internal migration banner "Coherence Score v1 is active…" (`CoherenceClient.tsx:61-72`) — internal noise (copy replacement arrives in PATCH 12; here just delete).

**Tests (RED first):** alerts page test asserting no `legal.reviewer`/`clause-` strings render; CoherenceClient test with MSW alerts fixture asserting distribution counts match fixture severities; AppHeader test asserting zero badge without data and that "View all notifications" navigates to `/alerts`.

**Acceptance criteria:** `grep -rn "legal.reviewer\|finance.analyst\|clause-\${" apps/web/app apps/web/components` → 0; every number on the coherence page traces to an API response.

**Verify:** `pnpm vitest run "app/(app)/projects/[id]/alerts" components/coherence components/layout/AppHeader.test.tsx`

---

## PATCH 5 — Real reviewer identity in HITL and evidence actions

**Backlog ID:** `TASK-FRT-179` · **Priority:** P0 · **Depends on:** —

**Evidence:** `app/(app)/projects/[id]/review/page.tsx:177,192` sends `reviewer_name: 'current-user'`; `app/(app)/projects/[id]/evidence/page.tsx:511` sends `resolved_by: "web-evidence-viewer"`. The HITL audit trail — a core differentiator — records a literal string.

**Files:** both pages.

**Steps:**
1. `const { user } = useUser()` (Clerk); build `reviewerName = user?.primaryEmailAddress?.emailAddress ?? user?.id`. Disable Approve/Reject buttons until `user` is loaded (tooltip "Loading your identity…").
2. Use it for `reviewer_name` (approve + reject) and `resolved_by` (evidence resolve). Keep payload shape otherwise identical (backend contract unchanged).

**Tests (RED first):** MSW handlers capture the mutation body; assert it contains the mocked Clerk email, not `current-user`/`web-evidence-viewer`.

**Acceptance criteria:** Review timeline shows the real reviewer ("Approved by jane@acme.com"); the two literals are gone from the codebase.

**Verify:** `pnpm vitest run "app/(app)/projects/[id]/review" "app/(app)/projects/[id]/evidence"`

---

## PATCH 6 — Visible analysis progress + document status polling

**Backlog ID:** `TASK-FRT-180` · **Priority:** P0 · **Depends on:** PATCH 1

**Evidence:** `AnalysisProgressTracker` and `ProcessingStepper` are orphaned (only their tests import them). The Analysis page's "Open Processing Stream" is a `<Link>` to the raw SSE endpoint without token (`analysis/page.tsx:123-127` + `analysis-stream.ts` appends none) — a dead end that dumps JSON/401 in the browser. `useProjectDocuments` never refetches, so upload→processing→analyzed requires manual F5.

**Files:** `apps/web/components/features/analysis/AnalysisProgressTracker.tsx`, `apps/web/app/(app)/projects/[id]/analysis/page.tsx`, `apps/web/app/(app)/projects/[id]/documents/page.tsx`, `apps/web/hooks/useProjectDocuments.ts`.

**Steps:**
1. Simplify `AnalysisProgressTracker` for end users: collapse the 17 nodes into **4 stages** — *Reading documents* (N1–N3), *Extracting & cross-checking* (N4–N11), *Quality review* (N12–N15), *Finalizing* (N16–N17). Keep the SSE wiring (token already read from the auth store), map `stage` events to the 4 buckets, remove the "17-node LangGraph pipeline" copy. Keep the detailed node grid behind a collapsed "Technical detail" disclosure (optional).
2. Mount it in the Analysis page replacing the raw-SSE `<Link>` (delete that button), and as a banner on the Documents page whenever ≥1 document is `uploaded/queued/processing`.
3. Convert `useProjectDocuments` to react-query (`useQuery({ queryKey: ["project-documents", projectId], … })`) with `refetchInterval: (q) => hasInFlightDocs(q.state.data) ? 5000 : false`. Keep the return shape (`documents, loading, error, refetch`) so call-sites don't churn.
4. Security note: do not add the token to the SSE URL in new code paths beyond the existing helper; leave the helper as-is (backend accepts `access_token` today) and file nothing new — the query-param concern is documented in the analysis report §3.

**Tests (RED first):** tracker unit test mapping stage events → 4 buckets; hook test with fake timers asserting refetch happens while a doc is `processing` and stops at `analyzed`; analysis page test asserting the raw endpoint link is gone.

**Acceptance criteria:** After a triplet upload (PATCH 1), the user watches statuses advance to `Analyzed` without refreshing; no navigation to `/api/v1/analysis/.../stream` exists in the UI.

**Verify:** `pnpm vitest run components/features/analysis hooks/useProjectDocuments.test.ts "app/(app)/projects/[id]/analysis"`

---

## PATCH 7 — Fix "Retry processing" (auth + feedback)

**Backlog ID:** `TASK-FRT-181` · **Priority:** P0 · **Depends on:** —

**Evidence:** `app/(app)/projects/[id]/documents/page.tsx:100-115` uses raw `fetch('/api/v1/projects/{id}/documents/{docId}/reprocess', { method: 'POST' })` — no Authorization header (the Next proxy only forwards incoming headers, `app/api/[...proxy]/route.ts:13-33`) → guaranteed 401, and failure goes only to `console.error`.

**Files:** `apps/web/app/(app)/projects/[id]/documents/page.tsx`.

**Steps:** replace with `apiClient.post(\`/projects/${projectId}/documents/${docId}/reprocess\`)`; on failure show a toast (`showToast` from `@/lib/ui/toast` or sonner) with the parsed `detail`; keep the per-row spinner.

**Tests (RED first):** MSW asserts the reprocess request carries `Authorization`; a 500 response produces a visible toast (assert on screen text), not silence.

**Acceptance criteria:** Retry on an `Error` document returns 2xx against the local backend and the row transitions; failures are user-visible.

**Verify:** `pnpm vitest run "app/(app)/projects/[id]/documents"`

---

## PATCH 8 — Landing honesty pass

**Backlog ID:** `TASK-FRT-182` · **Priority:** P0 · **Depends on:** —

**Evidence:** `components/landing-page-content.tsx:70-84` fabricated metrics (94 % / 6x / $2.4M / <30s); `:210` visible "Deploy marker 2026-03-30-a"; `:32` "Get Started" → `/signup` (route doesn't exist; Clerk proxy bounces to sign-in); `:22` Pricing → `#`; `app/layout.tsx:37` tab title "C2Pro v3.0 - Coherence Monitor".

**Files:** `apps/web/components/landing-page-content.tsx` (+ test), `apps/web/app/layout.tsx`.

**Steps:**
1. Delete the stats section (do **not** replace with new invented numbers; when the owner clears pilot-derived claims — e.g., "detected a 2.8 % budget deviation live on a real EPC project" — they can be added with a source note).
2. Remove the deploy-marker span. 3. "Get Started" → `/sign-up`; "Access Real Workspace" → label "Sign in" → `/sign-in`; keep "View Live Demo". 4. Remove the dead Pricing anchor (nav + footer keep only working links). 5. Metadata title → `"C2Pro — Contract Coherence Audit"`; description updated to the triplet promise (contract + budget + schedule).
3. Update hero subhead to the triplet message (from analysis §8): *"C2Pro cross-examines the contract, budget and schedule of your EPC project, flags every contradiction with clause-level evidence, and produces an auditable report your team signs off on."*

**Tests (RED first):** update `landing-page-content.test.tsx`: no `/signup` href, no "Deploy marker", no "94%" text; CTA hrefs assert `/sign-up`, `/sign-in`.

**Acceptance criteria:** Landing contains zero unverifiable claims and zero internal artifacts; every link resolves.

**Verify:** `pnpm vitest run components/landing-page-content.test.tsx app/layout.test.tsx`

---

## PATCH 9 — Dashboard inside the app shell + kill ghost admin redirects

**Backlog ID:** `TASK-FRT-183` · **Priority:** P0 · **Depends on:** —

**Evidence:** `app/page.tsx:8,46` renders `AppDashboardPage` directly at `/` (outside the `(app)` group → **no sidebar/header**); `next.config.mjs:27-37` permanently redirects `/dashboard → /`, making the shell version unreachable; `app/page.tsx:18-24` redirects `c2pro_admin`/`tenant_admin` to `/admin/c2pro`/`/admin/tenant` — routes that don't exist (404 after login). Dashboard empty state (`dashboard/page.tsx:44-47`) is styled as an error and has no CTA.

**Files:** `apps/web/app/page.tsx`, `apps/web/next.config.mjs`, `apps/web/app/(app)/dashboard/page.tsx`, `apps/web/components/layout/AppSidebar.tsx`.

**Steps:**
1. Remove both `/dashboard` redirects from `next.config.mjs`.
2. `app/page.tsx`: authenticated users get `router.replace('/dashboard')` (all roles — delete the `/admin/*` branches until admin surfaces exist); anonymous users keep the landing. Remove the direct `AppDashboardPage` import/render.
3. `AppSidebar.getHref('/dashboard')` returns `/dashboard` (non-demo); `isActive` updated accordingly.
4. Dashboard zero-projects state: neutral (non-destructive) styling, copy *"Start your first coherence audit. Create a project and upload its contract, budget and schedule."* + `Create project` button → `/projects` (opens list with wizard CTA visible).

**Tests (RED first):** root page test — authed render triggers replace to `/dashboard` (mock router) incl. for role `tenant_admin`; dashboard page test renders empty state with the CTA; sidebar test asserts href `/dashboard` and active state on that path. Adjust existing tests relying on the old redirect.

**Acceptance criteria:** Clicking "Dashboard" in the sidebar always lands on a page **with** the sidebar; an admin-role user no longer 404s after login.

**Verify:** `pnpm vitest run app/page.test.tsx "app/(app)/dashboard" components/layout/AppSidebar.test.tsx`

---

# WAVE 1 — P1 · MVP (closes the Level-1 loop)

---

## PATCH 10 — Triplet checklist in Documents + Overview

**Backlog ID:** `TASK-FRT-184` · **Priority:** P1 · **Depends on:** PATCH 1, PATCH 6

**Evidence:** The only triplet guidance lives in a coherence-page banner (`CoherenceClient.tsx:74-101`); Documents gives no signal of what's missing. Analysis §5 step 4, §6.

**Files:** new `apps/web/components/features/documents/TripletChecklist.tsx` (+test); mount in `projects/[id]/documents/page.tsx` (top, above KPIs) and a compact variant on `projects/[id]/page.tsx`.

**Steps:**
1. Component input: the `documents` array (from `useProjectDocuments`). Derivation per slot (`contract`, `budget`, `schedule`): `missing` (no doc of that type) / `processing` (doc exists, status not analyzed) / `ready` (≥1 analyzed). Ignore other types.
2. Render three slot cards with icon + status + per-slot CTA "Upload {type}" that opens the upload dialog with that type pre-selected (extend the dialog/dropzone to accept `defaultType` prop from PATCH 1's staging UI).
3. When all three are `ready`, the checklist collapses into a single success row: "Triplet complete — run the coherence audit" with CTA (wired in PATCH 11; until then link to the Coherence tab).

**Tests (RED first):** derivation unit tests (missing/processing/ready matrix); CTA pre-selects the type in the dialog.

**Acceptance criteria:** A new project's Documents page tells the user exactly which of the three documents is missing at all times.

**Verify:** `pnpm vitest run components/features/documents/TripletChecklist.test.tsx`

---

## PATCH 11 — "Run analysis" / "Evaluate coherence" actions

**Backlog ID:** `TASK-FRT-185` · **Priority:** P1 · **Depends on:** PATCH 6, PATCH 10

**Evidence:** Generated mutations `useAnalyzeDocumentApiV1AnalyzePost` and `useEvaluateProjectCoherenceV0CoherenceEvaluatePost` have **zero call-sites**; the pilot triggered `/api/v1/coherence/evaluate` via curl. There is no way to re-run anything from the UI after correcting a document.

**Files:** `apps/web/app/(app)/projects/[id]/analysis/page.tsx`, `apps/web/app/(app)/projects/[id]/coherence/page.tsx` (client child), possibly a small `hooks/useEvaluateCoherence.ts` wrapper.

**Steps:**
1. **Contract check first (mandatory):** read the generated request models (`ProjectContext`, `AnalyzeRequest`) and the backend routers (`apps/api/src/coherence/**/router*.py`, `analysis` router) to confirm exact payloads — the coherence evaluate endpoint historically accepts a project-scoped evaluation request. Implement against the real contract; if the generated client is stale, run `make openapi && pnpm generate:api` first (and commit the regen separately).
2. Add **"Evaluate coherence"** button (Coherence page header + triplet-complete CTA from PATCH 10): calls the evaluate mutation with the project id, shows pending state, and on success invalidates the coherence dashboard + alerts queries so the score/findings refresh in place. Surface `applicability_summary`-style metadata if returned (informational toast: "Evaluated N clauses, M findings").
3. Add **"Re-run analysis"** on the Analysis page: v1 semantics = reprocess pending/error documents (reuse PATCH 7's endpoint per doc) and/or trigger the document analyze mutation where applicable; while running, show the PATCH 6 tracker.
4. Buttons disabled (with tooltip explaining why) when the triplet is incomplete — reuse TripletChecklist derivation.

**Tests (RED first):** MSW: evaluate mutation fires with the verified payload shape and, on success, the dashboard query refetches (assert via invalidated query mock); disabled-state test when triplet incomplete.

**Acceptance criteria:** After re-uploading a corrected budget, the user can click Evaluate and watch the score change — no curl involved.

**Verify:** `pnpm vitest run "app/(app)/projects/[id]/coherence" "app/(app)/projects/[id]/analysis" && pnpm generate:api:check`

---

## PATCH 12 — Render `categories_v2` (evidence-aware coherence) + humanized copy

**Backlog ID:** `TASK-FRT-186` · **Priority:** P1 · **Depends on:** PATCH 3

**Evidence:** `lib/api/contracts.ts:50-75` fully types `CoherenceV2Payload` (per-category `status`, `evidence_coverage`, `missing_evidence`, `detected_conflicts`, `recommendation`) — grep shows it is never rendered; `lib/api/services/dashboard.ts` doesn't even map `categories_v2` through. The most explainable data in the product is invisible. Also: "AUDIT_INCOMPLETE is active" leaks an internal enum to users (`CoherenceClient.tsx:84`).

**Files:** `apps/web/lib/api/services/dashboard.ts`, new `apps/web/components/coherence/CategoryV2Panel.tsx` (+test), `apps/web/components/coherence/CoherenceClient.tsx`.

**Steps:**
1. Map `categories_v2` through `getDashboardSummary` (nullable; absent when the backend flag is off).
2. `CategoryV2Panel`: one card per category — status chip (reuse `CategoryStatusBadge`, it exists), score or `—`, evidence coverage bar, "Missing evidence: …" list, detected-conflicts count with expandable detail, and the `recommendation` string. Honest-null: hide any field the payload doesn't carry.
3. In `CoherenceClient`, render the panel (replacing the v1 sub-category grid **when** `categories_v2` is present; keep the v1 grid as fallback).
4. Copy: replace "AUDIT_INCOMPLETE is active because…" with *"Score withheld: this audit is missing the **{dims}**. Upload them to unlock the full Coherence Score."* (keep the existing upload CTA).

**Tests (RED first):** service test mapping `categories_v2` through; panel renders a fixture with `insufficient_evidence` + `scored` categories correctly; fallback to v1 grid when payload absent; the string `AUDIT_INCOMPLETE` no longer renders.

**Acceptance criteria:** With a v2-enabled backend response, each category answers "what's missing / what conflicts / what to do" using only backend data.

**Verify:** `pnpm vitest run components/coherence lib/api/services/dashboard.test.ts`

---

## PATCH 13 — HITL queue: project scoping, readable cards, visible errors

**Backlog ID:** `TASK-FRT-187` · **Priority:** P1 · **Depends on:** PATCH 5

**Evidence:** `review/page.tsx:132` fetches the **global** queue (`useListReviewQueueApiV1HitlQueueGet(undefined)`) while the header claims project scope; expanded detail dumps `JSON.stringify(item.item_data)` (`:417`); mutation errors are swallowed (`:181-183,198-200`); no pagination params.

**Files:** `apps/web/app/(app)/projects/[id]/review/page.tsx`, small `components/features/review/ReviewItemCard.tsx` (new).

**Steps:**
1. Check `ListReviewQueueApiV1HitlQueueGetParams` (generated) for a project/status filter. If `project_id` exists → pass it. If not → **stop per Ground Rule 8**: register backend task "HITL queue project filter" with an ID, and meanwhile filter client-side only if items carry a project field; otherwise retitle the page honestly ("Organization review queue") — do not fake scoping.
2. `ReviewItemCard`: human-readable summary derived from `item_data` known shapes (title/summary/category fields — inspect `reviewItemResponseItemData` model), impact + confidence chips, SLA, and a "View evidence" link (`/projects/{id}/evidence?documentId=…` when the item references a document). Raw JSON stays behind a "Raw data" disclosure for power users.
3. Surface mutation errors: render `approveMutation.error`/`rejectMutation.error` inline in the dialog + toast (coordinates with PATCH 17's global handler; here ensure the dialog shows the failure and stays open).
4. Wire pagination (page/page_size params) with a simple "Load more" if supported.

**Tests (RED first):** queue request carries the project param (or documented fallback); card renders human summary not raw JSON by default; a failed approve keeps the dialog open and shows the error.

**Acceptance criteria:** A reviewer sees only the relevant queue, understands each item without reading JSON, and never loses an error.

**Verify:** `pnpm vitest run "app/(app)/projects/[id]/review" components/features/review`

---

## PATCH 14 — Audit Report export v1 (the missing value output)

**Backlog ID:** `TASK-FRT-188` · **Priority:** P1 · **Depends on:** PATCHES 4, 5, 12 (real data + identity)

**Evidence:** No audit-report screen or export exists anywhere. Current "exports": `window.print` popups (projects/evidence), naive CSV, and `budget/page.tsx:192` → `alert("PDF export - implement with jsPDF or similar")`.

**Files:** new `apps/web/app/(app)/projects/[id]/report/page.tsx` + `components/features/report/*` (+tests); `components/layout/ProjectTabs.tsx` (add "Report" tab); `app/(app)/projects/[id]/budget/page.tsx` (remove the alert() button).

**Steps:**
1. Report page composes, from existing endpoints (no new backend): project metadata; Coherence Score + categories (v2 when present); findings/alerts grouped by status (approved / rejected / open) with severity, category, message and evidence reference (page/clause when `evidence_location` exists); HITL decisions with reviewer + timestamp; generation timestamp; document register (the triplet with filenames/types/upload dates).
2. Composition controls: checkboxes for sections (include open findings? include rejected?), then **"Export report"**.
3. Export v1 = dedicated print-optimized route/stylesheet (proper `@media print` CSS: A4, page breaks between sections, header/footer with project + date, no nav) triggered via `window.print()` on that clean route — this is acceptable when done as a real print layout, unlike the current popups — **plus** "Download JSON" of the same composed payload. Add a `// TODO(TASK-BCK backend report endpoint)` seam note. Do not add jsPDF/puppeteer without owner approval (Ground Rule 5).
4. Remove the placeholder PDF button in Budget (point users to the Report tab).

**Tests (RED first):** composition unit tests (grouping by status, evidence refs included when present, honest omission otherwise); page test asserting all sections render from MSW fixtures; the `alert(` literal is gone from budget page.

**Acceptance criteria:** E2E-W5 (see PATCH 18): a user exports a report containing score, approved findings with citations, and reviewer identities. `grep -rn "alert(" apps/web/app` shows no placeholder exports.

**Verify:** `pnpm vitest run "app/(app)/projects/[id]/report" components/features/report "app/(app)/projects/[id]/budget"`

---

## PATCH 15 — Global mutation error surface

**Backlog ID:** `TASK-FRT-189` · **Priority:** P1 · **Depends on:** —

**Evidence:** `hooks/useBudget.ts:127-172` returns `null` + `console.error` on failures; empty `catch {}` blocks in review/evidence pages; users never see failures. (`lib/api/queryClient.ts` currently defines no global error handling.)

**Files:** `apps/web/lib/api/queryClient.ts`, `apps/web/hooks/useBudget.ts`, sweep of `catch {}`/`console.error`-only handlers in `app/(app)/**`.

**Steps:**
1. `createQueryClient`: add `MutationCache({ onError })` → toast (sonner) with parsed axios/fetch `detail` message; queries keep their inline error rendering.
2. Remove swallow patterns: `useBudget` mutations rethrow (page relies on the global toast + inline states); delete redundant try/catch that only logs.
3. Ensure the toaster is mounted app-wide (`components/ui/sonner` in the `(app)` layout if not already).

**Tests (RED first):** a failing mutation through the shared client produces a toast (integration test with MSW 500); `useBudget.createItem` rejection propagates.

**Acceptance criteria:** No user-triggered write can fail silently anywhere in `(app)`.

**Verify:** `pnpm vitest run lib/api hooks/useBudget.test.ts` (add the test file)

---

## PATCH 16 — Navigation focus: hide operator/Phase-2 surface behind flags

**Backlog ID:** `TASK-FRT-190` · **Priority:** P1 · **Depends on:** —

**Evidence:** Sidebar exposes AI Analytics (and Observability is routable) to end users (`AppSidebar.tsx:31-38`); project tabs list 10 items with no active-state (active-state itself is PATCH 20); header has a decorative search input (`AppHeader.tsx:111-118`). Analysis §6 "Foco vs distracción". `FEATURE_RACI_GENERATION` (`config/env.ts:50-51`) is the existing gating pattern to follow.

**Files:** `apps/web/config/env.ts`, `apps/web/components/layout/AppSidebar.tsx`, `apps/web/components/layout/ProjectTabs.tsx`, `apps/web/components/layout/AppHeader.tsx`, the gated pages (redirect when flag off).

**Steps:**
1. New env flags following the RACI pattern: `NEXT_PUBLIC_FEATURE_INTERNAL_DASHBOARDS` (AI Analytics, Observability) and `NEXT_PUBLIC_FEATURE_PHASE2_MODULES` (Stakeholders global + project tab, WBS tab). Default **off**.
2. Sidebar (default): Dashboard, Projects, Alerts, Settings (+ flagged items when on). Project tabs (default): Overview, Documents, Coherence, Alerts, Review, Report, Evidence, Settings (+ WBS/Stakeholders when flag on).
3. Gated routes render a flag-off redirect to the project overview (not a 404), so bookmarks degrade gracefully.
4. Remove the decorative header search input (GlobalSearch wiring is out of scope; component stays for a future task — note it in the PR).

**Tests (RED first):** sidebar/tabs render matrices for both flag states; gated page redirects when off.

**Acceptance criteria:** With default env, the nav contains only Level-1 surface and zero dead controls.

**Verify:** `pnpm vitest run components/layout`

---

## PATCH 17 — Single project-creation flow; remove decorative dialogs

**Backlog ID:** `TASK-FRT-191` · **Priority:** P1 · **Depends on:** —

**Evidence:** Two parallel creation flows (`/projects/new` page and the 3-step wizard in `projects/page.tsx:980-1196`); `PROJECT_TEMPLATES` selection applies nothing (`:105-127,899-906`); batch import only previews (`LazyProjectBatchImportDialog`); page is 1,362 lines.

**Files:** `apps/web/app/(app)/projects/new/page.tsx`, `apps/web/app/(app)/projects/page.tsx`, `apps/web/components/features/projects/LazyProjectDialogs.tsx`, `ProjectTemplatesDialog.tsx`, `ProjectBatchImportDialog.tsx` (+tests).

**Steps:**
1. Keep the wizard as the single flow; `/projects/new` becomes `redirect('/projects?create=1')` and the projects page opens the wizard when that param is present (preserves deep links/tests).
2. Delete Templates and Batch Import dialogs + buttons + their tests (git history preserves them; note in PR). If the owner prefers keeping them, they go behind `FEATURE_PHASE2_MODULES` — default: delete.
3. Extract the wizard into `components/features/projects/CreateProjectWizard.tsx` as part of the removal (starts the god-file split; full split is PATCH 23).

**Tests (RED first):** `/projects/new` redirects; `?create=1` opens the wizard; template/batch strings no longer render.

**Acceptance criteria:** One creation path; `projects/page.tsx` shrinks below ~800 lines.

**Verify:** `pnpm vitest run "app/(app)/projects"`

---

## PATCH 18 — CI gates that protect the wedge

**Backlog ID:** `TASK-FRT-192` · **Priority:** P1 · **Depends on:** PATCHES 1–14 (tests exist to gate)

**Evidence:** `frontend-ci.yml:143` runs `pnpm test` = only `src/tests/integration` (50 of 249 test files); only one Playwright spec gates (`coherence-v1.spec.ts`); `frontend-e2e.yml` sets `NEXT_PUBLIC_API_URL=http://localhost:8000` but starts no backend. The Overview crash shipped under a green pipeline.

**Files:** `.github/workflows/frontend-ci.yml`, `apps/web/package.json`, new `apps/web/src/tests/e2e/journeys/journey-3-wedge.spec.ts`.

**Steps:**
1. frontend-ci: replace the unit step with `pnpm test:all` (colocated + integration). Budget the runtime; if >10 min, split into two parallel jobs (colocated / integration).
2. New Playwright journey `journey-3-wedge.spec.ts` implementing **E2E-W1…W5** from the analysis (§11): typed triplet upload → statuses advance → evaluate → finding→evidence deep link → approve with real identity → export report. Run it against MSW-deterministic handlers (extend `mocks/handlers` for the new endpoints) so it needs no live backend in CI; tag a variant `@real-backend` for the scheduled real-e2e workflow.
3. Add the journey to the CI Playwright step alongside coherence-v1.

**Tests:** the workflow change itself + the journey spec (RED against current main is expected — it gates the wave).

**Acceptance criteria:** Breaking any Level-1 step (upload typing, progress, evaluate, review identity, export) turns frontend-ci red.

**Verify:** `pnpm test:all && pnpm test:e2e -- src/tests/e2e/journeys/journey-3-wedge.spec.ts --project=chromium` locally; then CI run.

---

# WAVE 2 — P2 · Private beta

---

## PATCH 19 — Budget reconciliation block

**Backlog ID:** `TASK-FRT-193` · **Priority:** P2 · **Depends on:** PATCH 12 · **External:** DET-BUD findings shipped (backend PRs #172-#174, merged)

**Evidence:** The pilot's flagship result (stated 654,144,805 vs computed 636,044,805 → 2.8 % deviation, DET-BUD-SUM/DET-BUD-INTERNAL) has no surface in `budget/page.tsx` — the page shows generic planned-vs-actual only.

**Files:** `apps/web/app/(app)/projects/[id]/budget/page.tsx`, new `components/features/budget/ReconciliationCard.tsx` (+test).

**Steps:**
1. Source the reconciliation from budget-category coherence findings (alerts with the DET-BUD evaluator/category and their structured payload) and/or `categories_v2.BUDGET.detected_conflicts` — verify the concrete shape against a live evaluate response first (Ground Rule 8 if absent).
2. `ReconciliationCard`: three figures (Stated total · Computed from line items · Contract base) with source labels, delta % badge (severity-colored via PATCH 20 tokens), honest `—` per missing figure, link to the underlying finding/evidence.
3. Type the budget response properly while here: replace `readNumber/readString` duck-typing with an interface aligned to the backend (regenerate Orval if the endpoint is in the spec).

**Acceptance criteria:** With the pilot dataset, the Budget tab shows 636M vs 654M and the 2.8 % delta with a link to the finding.

**Verify:** `pnpm vitest run components/features/budget "app/(app)/projects/[id]/budget"`

---

## PATCH 20 — Design-system consolidation: severity tokens, EmptyState, active tabs

**Backlog ID:** `TASK-FRT-194` · **Priority:** P2 · **Depends on:** — · **Status:** ✅ Completed 2026-07-09

**Evidence:** ≥4 divergent `getStatusColor`/severity maps using raw Tailwind palettes (`documents:62-73`, `review:61-77`, `budget:238-249`, alerts) vs semantic tokens elsewhere; `ProjectTabs.tsx:36-44` has no active state / `aria-current`; empty states are ad-hoc (dashboard's is styled as an error).

**Files:** new `apps/web/lib/ui/severity.ts` + `apps/web/components/ui/empty-state.tsx` (+tests); `components/layout/ProjectTabs.tsx`; sweep call-sites.

**Steps:**
1. `severity.ts`: single `severityToToken(severity)` and `statusToToken(status)` returning badge/text/bg classes built on the existing CSS vars (`destructive`, `warning`, etc.). Replace all local maps.
2. `EmptyState` (icon, title, description, action) — adopt in dashboard, projects, documents, coherence, review empty paths.
3. ProjectTabs: derive active from `usePathname()`, style + `aria-current="page"`.

**Acceptance criteria:** One severity source of truth (`grep -rn "bg-green-100" apps/web/app` → 0); every list screen has a guided empty state; users can see which project tab is active.

**Verify:** `pnpm vitest run lib/ui components/ui/empty-state.test.tsx components/layout/ProjectTabs.test.tsx`

---

## PATCH 21 — First-run onboarding (mount the orphan) ✅ COMPLETED 2026-07-09

**Backlog ID:** `TASK-FRT-195` · **Priority:** P2 · **Depends on:** PATCH 9

**Evidence:** `OnboardingEntry`, `onboarding-preferences`, `sample-project-bootstrap` exist with tests but are mounted nowhere (grep: test-only imports).

**Files:** `apps/web/app/(app)/dashboard/page.tsx` (or projects page), `components/features/onboarding/*`.

**Steps:** on zero projects + onboarding-not-dismissed (existing preferences module), render `OnboardingEntry` offering "Start with a sample project" (bootstrap module) and "Create your own"; persist dismissal; sample project must flow into the PATCH 10 checklist naturally.

**Acceptance criteria:** A brand-new user reaches populated screens in one click; dismissal sticks across sessions.

**Verify:** `pnpm vitest run components/features/onboarding "app/(app)/dashboard"`

---

## PATCH 22 — Language unification (EN)

**Backlog ID:** `TASK-FRT-196` · **Priority:** P2 · **Depends on:** —

**Evidence:** `lib/api/client.ts:85` toast "Sesión expirada o inválida" (+ "Sin permisos" `:106`); Spanish placeholders in `projects/new/page.tsx:109,135`; rest of UI is English.

**Steps:** translate the two toasts ("Session expired — please sign in again", "You don't have permission to do that"); English placeholders; sweep `grep -rn "Sesión\|Sin permisos\|Constructora\|Edificio" apps/web` to zero. (Full i18n framework explicitly out of scope.)

**Acceptance criteria:** UI renders a single language everywhere; grep clean.

**Verify:** `pnpm vitest run lib/api/client.test.ts && grep -rn "Sesión" apps/web --include="*.ts*" | wc -l` → 0

---

## PATCH 23 — Component-root consolidation + god-file split

**Backlog ID:** `TASK-FRT-197` · **Priority:** P2 · **Depends on:** PATCHES 12, 14, 17 (touch the same files; do this last)

**Evidence:** Three component roots (`components/`, `src/components/`, plus `components/coherence/*` vs `components/features/coherence/*` duplicates — `ScoreCard`/`CoherenceGauge` live in one, their tests in the other); `evidence/page.tsx` = 1,636 lines; placeholders `GlobalSearch`/`CrossModuleNavigator` self-labeled "RED Phase".

**Steps:**
1. Move `src/components/coherence/*` into `components/coherence/`; merge the `features/coherence` duplicates (one canonical copy + colocated tests); fix imports (`@/src/...` → `@/components/...`).
2. Split `evidence/page.tsx` into `EvidenceHeader`, `EvidencePanelTabs`, `RelationshipSection`, `EvidenceExports` under `components/features/evidence/` (pure extraction, no behavior change; delete the "3D Relationship View" and no-op "Evidence Templates" dialog while extracting — analysis §12 P3, owner-approved by this prompt).
3. Delete `GlobalSearch.tsx` and `CrossModuleNavigator.tsx` placeholders (+tests) — register a fresh task if/when real global search is scheduled.
4. Enforce: no file in `apps/web` over 800 lines (`find` check in PR).

**Acceptance criteria:** One component root; `wc -l` max file < 800; all tests still green (`pnpm test:all`).

**Verify:** `pnpm test:all && pnpm typecheck && pnpm lint`

---

## Definition of Done (epic level)

1. All 23 tasks `[x]` in `backlogs/FRT_FRONTEND.md` with evidence; master backlog counts + Change Log updated (Ground Rule 7).
2. `pnpm typecheck && pnpm lint && pnpm test:all && pnpm generate:api:check` green.
3. `journey-3-wedge.spec.ts` (E2E-W1…W5) green in CI.
4. Manual demo script passes against the local stack: create project → upload typed triplet → watch progress → evaluate → open finding evidence → approve as yourself → export the audit report → sign out/in and resume.
5. Zero fabricated data, zero dead controls, zero placeholder exports (`alert(`, print-popups outside the report route).
