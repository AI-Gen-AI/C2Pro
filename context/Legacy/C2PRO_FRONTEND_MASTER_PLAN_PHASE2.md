# C2Pro Frontend Master Plan — Phase 2: Cross-Review & Issue Detection

> **Document:** Multi-Agent Cross-Review Analysis  
> **Version:** 1.0  
> **Date:** 2026-02-09  
> **Status:** Phase 2 Complete — Ready for Phase 3 Consolidation  
> **Input:** Phase 1 — 12 Agent Plans  
> **Methodology:** 6 Independent Cross-Reviewers, each analyzing all 12 plans

---

## === REVIEWER 1: ARCHITECTURE & INTEGRATION CONSISTENCY ===

### Summary of Plans

The 12 agents broadly agree on the foundational architecture (Next.js 15.3 App Router, Server Components by default, PPR incremental, Orval codegen pipeline). However, several significant contradictions and unresolved tensions exist across plans.

**Strengths across all agents:**
- Universal endorsement of Orval codegen as the type-safety backbone — no dissent
- Dual-mode (MSW demo/production) pattern validated by 8 of 12 agents as a key enabler
- Clear consensus on bundle strategy: PDF viewer must be lazy-loaded, no exceptions
- Strong agreement on Zustand vs TanStack Query state boundary

**Weaknesses across all agents:**
- No agent addressed the **monorepo tooling gap**: TDD references `apps/web/` implying a monorepo, but no agent specifies `pnpm workspaces` or Turborepo configuration for Sprint 1
- No agent addressed the **OpenAPI spec source of truth**: where does `openapi.json` live, how is it published, and what triggers `orval --check`?
- Insufficient attention to **i18n/l10n**: C2Pro targets Spain and LATAM markets (Spanish + English) — not a single agent addressed internationalization
- No agent discussed **offline resilience** or **service worker** strategy beyond Agent 12's Sprint 4 checkbox

---

### Flags

[FLAG: **CRITICAL — Auth store contradiction** | Agents 1, 3, 9]
Agent 1 includes `useAuthStore` in Sprint 1 Zustand setup (Week 2, item 6). Agent 3 explicitly demands removal of `stores/auth.ts` ("dangerous dual source of truth"). Agent 9 marks it as "⚠️ Should be REMOVED." The TDD v3.0 itself defines `stores/auth.ts` in the directory structure AND lists `@clerk/nextjs` as a dependency. This creates a direct contradiction in the blueprint — the final plan MUST resolve whether auth tokens live in Zustand or exclusively in Clerk. **Resolution needed: Remove Zustand auth store; use Clerk's `useAuth()` + `getToken()` with a thin wrapper for the Axios interceptor.**

[FLAG: **CRITICAL — Axios interceptor cannot call `useAuth()` hook** | Agent 3]
Agent 3's proposed fix (`const { getToken } = useAuth()` inside Axios interceptor) is **technically invalid**. React hooks cannot be called outside React components or custom hooks. The interceptor runs in plain JavaScript context. **Resolution needed: Use Clerk's `@clerk/nextjs` server-side `auth()` for Server Components, and for client-side Axios, pass a `getToken` function via closure at setup time or use Clerk's `useSession()` token.**

[FLAG: **HIGH — `require()` in Axios interceptor violates ESM** | TDD v3.0, Agent 4]
The TDD v3.0 code blueprint uses `const { useAuthStore } = require('@/stores/auth')` inside the Axios interceptor. This is CommonJS `require()` in an ESM/TypeScript project with Next.js 15. Agent 4's strict typing rules would flag this. **Resolution needed: Refactor interceptor to accept auth getter via factory pattern, not runtime require.**

[FLAG: **HIGH — Presentation→Data layer violation in TDD code** | Agents 4, 9]
Agent 4 forbids Presentation → Data direct access ("use hooks as intermediaries"). However, the TDD's own `CoherencePage` Server Component directly renders `<CoherenceGaugeServer>` which presumably fetches data internally. This is actually the **correct Next.js pattern** (Server Components fetch directly), meaning Agent 4's strict layering rule is too rigid for Server Components. **Resolution needed: Amend the rule — Server Components MAY access the data layer directly; Client Components MUST use hooks.**

[FLAG: **MEDIUM — Barrel exports contradict tree-shaking** | Agent 2, Agent 5]
Agent 2 mandates barrel exports (`index.ts`) for every feature folder. Agent 5's performance focus requires maximum tree-shaking. Barrel exports can defeat tree-shaking if not configured with `sideEffects: false` in package.json and Next.js `optimizePackageImports`. **Resolution needed: Only use barrel exports for the `ui/` component library. Feature components should be imported directly.**

[FLAG: **MEDIUM — Missing monorepo configuration** | Agents 1, 2]
The TDD references `apps/web/` suggesting a monorepo structure, and Agent 2 mentions Turborepo "when adding `@c2pro/ui` package." But no agent defines the root `pnpm-workspace.yaml` or monorepo scripts needed NOW in Sprint 1. If the backend (`apps/api/`) coexists in the same repo, this matters for CI. **Resolution needed: Define minimal monorepo config in Sprint 1.**

---

## === REVIEWER 2: UX & DESIGN CONSISTENCY ===

### Summary of Plans

Agents 6 (UX), 7 (A11y), and 8 (Design Systems) form a coherent UX trilogy, with Agent 11 (AI UX) adding AI-specific patterns. Together they define a comprehensive user experience strategy. However, several UX inconsistencies and missing patterns emerge.

**Strengths:**
- Agent 6's progressive disclosure pattern (Dashboard → Category → Alert → Evidence) is excellent for the target user persona
- Agent 7's triple-encoded severity (color + shape + text) is a best-in-class accessibility pattern
- Agent 8's design token hierarchy (primitive → semantic → component) provides clear governance
- Agent 11's "AI-generated" provenance badge and confidence indicator build user trust appropriately

**Weaknesses:**
- No agent defined the **empty state UX** for a new user with zero projects — the critical first impression
- The **onboarding flow** (Agent 6) references "sample project" but no agent specifies how this works in production mode (pre-seeded data? server-side template?)
- No agent addressed **notification/alert delivery outside the app** (email digests, Slack integration for critical alerts)
- The **command palette** (`cmdk`) is listed in dependencies but no agent defined its behavior, shortcuts, or search scope

---

### Flags

[FLAG: **HIGH — Keyboard shortcuts conflict with accessibility** | Agents 6, 7]
Agent 6 proposes `j/k` for next/prev alert and `a/r` for approve/reject. Agent 7's accessibility analysis doesn't address this. Single-letter keyboard shortcuts WITHOUT modifiers are a **WCAG 2.1 SC 2.1.4 Character Key Shortcuts** violation — they interfere with voice control software and screen readers. **Resolution needed: Require a modifier key (e.g., `Alt+j/k`) or make shortcuts configurable/disableable.**

[FLAG: **HIGH — Primary color used inconsistently across agents** | Agents 7, 8, TDD]
Agent 7 identifies `#00ACC1` as failing WCAG AA contrast (3.1:1) and recommends `#00838F` for text. However, the TDD's `globals.css` defines `--primary: oklch(0.56 0.12 195)` which maps to `#00ACC1`. Agent 8 references the same token hierarchy. The design system's PRIMARY color fails accessibility, but no agent proposes updating the actual CSS variable — they only suggest "use darker variant for text." **Resolution needed: Define TWO primary tokens: `--primary` for backgrounds/decorative use and `--primary-text` for text meeting 4.5:1 contrast.**

[FLAG: **MEDIUM — Undo pattern inconsistency** | Agents 6, 11]
Agent 6 proposes a 5-second undo toast for alert approve/reject (soft-delete pattern). Agent 11's legal disclaimer requires "every AI output shows its evidence." These could conflict — if a user approves an alert, the undo toast fires, but the backend may have already recalculated the Coherence Score. **Resolution needed: Optimistic undo must invalidate the coherence dashboard query on both approve AND undo.**

[FLAG: **MEDIUM — Mobile Evidence Viewer undefined** | Agents 5, 6, 7]
Agent 6 mentions "PDF viewer in full-screen modal" on mobile, and Agent 5 allocates 120KB budget for the Evidence Viewer. Agent 7 doesn't address PDF accessibility on mobile. The split-pane pattern breaks completely on mobile. **Resolution needed: Define explicit mobile Evidence Viewer flow — likely a stacked tab interface (PDF tab / Alerts tab) rather than split pane.**

[FLAG: **MEDIUM — Onboarding "sample project" requires backend support** | Agents 6, 9, 11]
Agent 6's onboarding Step 2 offers "use sample project (reduces time-to-value to 0)." Agent 9 defines `useOnboardingStore` with `sampleProject: boolean`. But in production mode (not demo), where does the sample project data come from? MSW only runs in demo mode. **Resolution needed: Backend must provide a `/api/v1/onboarding/sample-project` endpoint that creates a pre-analyzed project with demo data, OR the frontend routes to demo mode for the sample project only.**

[FLAG: **LOW — Command palette scope undefined** | Agent 8, TDD]
`cmdk` is in the dependency list and Agent 8 lists `command.tsx` in the UI components, but no agent defines: what commands are available, what's searchable (projects? alerts? settings?), or when the palette appears (`Cmd+K`). **Resolution needed: Define command palette scope in Sprint 2 — at minimum: project navigation, theme toggle, and quick filter.**

---

## === REVIEWER 3: STATE MANAGEMENT & DATA FLOW ===

### Summary of Plans

Agent 9 (State Management) provides the most detailed plan, with Agents 3 (Security), 4 (Maintainability), and 11 (AI UX) contributing state-related patterns. The Zustand/TanStack boundary is well-defined. However, several data flow issues remain unresolved.

**Strengths:**
- Hierarchical query key convention (Agent 9) enables precise cache invalidation
- Optimistic update pattern for weight adjustment is correctly implemented with rollback
- SSE → TanStack Query invalidation pattern correctly bridges real-time and cached data
- `staleTime: 60_000` default is appropriate for C2Pro's data characteristics

**Weaknesses:**
- No agent defined error recovery for **partial SSE failures** (e.g., Stage 3 fails, can Stage 4 proceed?)
- The `useFilterStore` resets on page refresh (no persistence) — this may frustrate users who've built complex filter sets
- No agent addressed **cross-tab synchronization** (user has Dashboard open in Tab 1, approves alerts in Tab 2 — Tab 1 should reflect changes)
- Optimistic score recalculation (`recalculateScore(old.subScores, newWeights)`) requires frontend to replicate backend logic — drift risk

---

### Flags

[FLAG: **CRITICAL — SSE stream not authenticated** | Agents 3, 9, 12]
Agent 9's `useDocumentProcessing` creates `new EventSource('/api/v1/projects/${projectId}/process/stream')`. The standard `EventSource` API **does not support custom headers** (no Bearer token). Agent 3 defines Bearer auth for all API calls. This means the SSE endpoint is either unauthenticated (security hole) or requires cookie-based auth (contradicts Agent 3's "Bearer only" model). **Resolution needed: Either (a) use `fetch()` with `ReadableStream` instead of `EventSource` to pass Bearer token, (b) use a short-lived signed URL, or (c) use a polyfill like `eventsource-polyfill` that supports headers.**

[FLAG: **HIGH — Optimistic score recalculation duplicates backend logic** | Agents 5, 9]
Agent 9's optimistic update calls `recalculateScore(old.subScores, newWeights)` on the frontend. This means the weighted-sum formula from the Coherence Engine v2 must be replicated in JavaScript. If the backend formula changes (e.g., non-linear weighting), the frontend shows wrong values until `onSettled` refetch. **Resolution needed: Accept a brief delay (show loading spinner on gauge only) instead of optimistic score recalculation, OR define the formula as a shared constant validated by contract test.**

[FLAG: **HIGH — TanStack Query keys diverge from Orval-generated keys** | Agents 4, 9, 10]
Agent 9 defines manual `queryKeys` object (e.g., `['coherence', 'dashboard', projectId]`). But Orval auto-generates query keys based on the OpenAPI operation IDs. Using BOTH would create duplicate cache entries and invalidation misses. **Resolution needed: Use ONLY Orval-generated query keys. If custom keys are needed, extend via Orval's `override.query.queryKey` config, not a parallel manual system.**

[FLAG: **MEDIUM — SSE processing uses React state, not Zustand** | Agents 9, 4]
Agent 9's `useDocumentProcessing` stores stages in `useState` — component-local state that's lost on unmount. If the user navigates away from the processing page and returns, progress is lost. Agent 4's layering rules would place this in a Zustand store since it's cross-page state. **Resolution needed: Store processing state in Zustand (NOT TanStack Query, since it's real-time transient data, not cacheable server state). Persist `{ projectId, stages, progress }` until processing completes.**

[FLAG: **MEDIUM — Cross-tab cache invalidation not addressed** | Agents 9, 12]
If a user opens C2Pro in two tabs (common for procurement managers comparing projects), mutations in one tab don't propagate to the other. TanStack Query's `refetchOnWindowFocus` is disabled in the config (`refetchOnWindowFocus: false`). **Resolution needed: Either (a) enable `refetchOnWindowFocus: true` for critical queries (coherence dashboard, alerts) or (b) use `BroadcastChannel` to sync invalidation across tabs.**

[FLAG: **LOW — Filter persistence decision** | Agent 9]
`useFilterStore` has no persistence, meaning complex filter selections are lost on refresh. For procurement managers who build specific alert views, this is a UX irritation. **Resolution needed: Add `persist` middleware to `useFilterStore` with session-level storage (not localStorage — don't persist across sessions).**

---

## === REVIEWER 4: PERFORMANCE & BUNDLE ANALYSIS ===

### Summary of Plans

Agent 5 (Performance) provides the primary performance plan, with supporting input from Agent 1 (Speed), Agent 8 (Design System), and Agent 12 (Production). The bundle budgets and rendering strategies are largely sound.

**Strengths:**
- Clear bundle budgets per route group with specific KB limits
- PPR correctly applied only to dashboard routes (not over-applied)
- PDF viewer lazy loading with preload-on-hover is an excellent pattern
- React Compiler enabled with per-component opt-out (`"use no memo"`) is the right approach

**Weaknesses:**
- No agent measured the **actual current bundle size** — all budgets are aspirational
- Tailwind v4's new CSS engine may produce larger CSS output than v3 — no agent quantified this risk
- `@fontsource-variable/inter` (variable font) is ~100KB — significant for FCP but no agent addressed font loading strategy
- Admin portal uses Tremor (3.x) which is a heavy dependency — no lazy loading strategy specified

---

### Flags

[FLAG: **HIGH — Recharts bundle not accounted for in dashboard budget** | Agents 5, 8]
Agent 5 allocates ≤50KB for the dashboard route. The CoherenceGauge uses `RadialBarChart` from Recharts. Recharts core is ~45KB gzipped even with tree-shaking. Combined with React + framework code, the 50KB budget is **impossible** to hit. The TDD notes `optimizePackageImports: ['recharts']` but this doesn't reduce the core bundle enough. **Resolution needed: Either (a) increase dashboard budget to 80KB, (b) use a lightweight chart library (e.g., `unovis` or custom SVG) for the gauge only, or (c) server-render the gauge as a static SVG and only hydrate the interactive parts.**

[FLAG: **HIGH — Font loading strategy missing** | Agents 5, 8, 12]
`@fontsource-variable/inter` (~95KB) and `@fontsource/jetbrains-mono` (~45KB) are loaded at root layout level. That's ~140KB of fonts blocking FCP. No agent specified `font-display: swap`, subset loading, or `next/font` optimization. The TDD uses `@fontsource` instead of `next/font/google` which misses Next.js's built-in font optimization. **Resolution needed: Switch to `next/font/local` with Inter Variable subset (latin only, ~35KB) or at minimum ensure `font-display: swap` is configured.**

[FLAG: **MEDIUM — Tremor admin portal bundle** | Agents 1, 5]
Agent 1 defers admin portal to Sprint 4. Agent 5 allocates ≤80KB for admin. Tremor 3.x imports Recharts internally plus its own component library. Without aggressive tree-shaking, Tremor can add 150KB+ to the admin chunk. Agent 5 mentions "Tremor lazy" but provides no implementation. **Resolution needed: Import Tremor components individually (`import { AreaChart } from '@tremor/react'`) and verify tree-shaking via `next build --analyze`.**

[FLAG: **MEDIUM — PPR + Sentry interaction** | Agents 5, 12]
PPR pre-renders static shells at edge. Sentry's `withSentryConfig` wraps the entire Next.js config. When PPR streams dynamic content, Sentry's automatic wrapping may interfere with streaming, adding latency. **Resolution needed: Test PPR pages with Sentry enabled and measure TTFB delta. If >100ms regression, configure Sentry to exclude PPR routes.**

[FLAG: **MEDIUM — `staleTime: 60_000` too aggressive for Coherence Dashboard** | Agents 5, 9]
After a user uploads documents and processing completes (SSE), they're redirected to the Coherence Dashboard. If TanStack Query serves cached data from 60 seconds ago, the user sees stale scores. Agent 9's SSE handler invalidates queries on `complete`, but there's a race condition if the redirect happens before `onSettled` fires. **Resolution needed: Force `refetchOnMount: 'always'` for the coherence dashboard route, or pass a cache-busting key via URL params after processing.**

[FLAG: **LOW — No web worker strategy for heavy computation** | Agent 5]
Agent 9's optimistic `recalculateScore()` and potential future features (WBS tree manipulation, BOM filtering) could block the main thread. No agent proposed web workers for computation-heavy operations. **Resolution needed: Monitor INP. If any interaction exceeds 200ms, move computation to a web worker.**

---

## === REVIEWER 5: TESTING & QUALITY GAPS ===

### Summary of Plans

Agent 10 (Testing) provides the comprehensive test plan, with Agent 7 (A11y) contributing accessibility testing, and Agent 12 (Production) contributing cross-browser testing. The testing plan from the uploaded `FRONTEND_TESTING_PLAN.md` is a SEPARATE, OLDER document that conflicts with the TDD v3.0.

**Strengths:**
- 192 total tests across unit/integration/E2E is a realistic and achievable target
- MSW-based integration testing validates both modes from a single test suite
- Vitest + RTL + Playwright is the correct modern stack
- Coverage exclusions for generated code and mocks are appropriate

**Weaknesses:**
- No agent addressed **Storybook interaction tests** — a middle ground between unit and E2E that's fast and visual
- No **contract testing** strategy (Pact or similar) to validate Orval-generated types against actual backend responses
- No agent addressed testing the **SSE streaming** pipeline — this is the hardest thing to test and none defined a pattern
- The uploaded `FRONTEND_TESTING_PLAN.md` references Next.js 14, custom JWT auth, and a `lib/api-client.ts` — all OUTDATED vs TDD v3.0

---

### Flags

[FLAG: **HIGH — Testing plan document is outdated and conflicts with TDD v3.0** | Agent 10, FRONTEND_TESTING_PLAN.md]
The uploaded `FRONTEND_TESTING_PLAN.md` references: Next.js 14 (not 15.3), custom JWT auth via `lib/auth.ts` (not Clerk), `lib/api-client.ts` (not Orval-generated), `useLocalStorage` hook (not in TDD), and a flat `app/(dashboard)/projects/[id]/` structure (TDD uses `[projectId]`). **This document must be superseded by Agent 10's plan entirely.** Using it as-is will produce tests for an architecture that no longer exists.

[FLAG: **HIGH — No SSE/streaming test strategy** | Agents 9, 10, 12]
The processing stepper (SSE) is a critical user flow, but Agent 10's test plan allocates only 9 tests to it (5 unit, 3 integration, 1 E2E) with no detail on HOW to test SSE. MSW v2 supports streaming responses (`HttpResponse.stream()`), but no agent showed how. **Resolution needed: Define MSW streaming handler for tests using `HttpResponse` with `ReadableStream` or `@mswjs/interceptors`. Include stage-by-stage assertions and error recovery tests.**

[FLAG: **HIGH — Server Component testing gap** | Agents 4, 10]
Agent 10's integration test directly renders `CoherencePage` — a Server Component with `async` and `await params`. But `@testing-library/react` cannot render async Server Components in `jsdom`. This test as written **will not work**. **Resolution needed: Test Server Components via (a) Playwright E2E against a running app, (b) a dedicated Server Component test utility, or (c) test only the Client Component children in isolation and test the page via E2E.**

[FLAG: **MEDIUM — Test-utils.tsx missing Clerk provider** | Agents 3, 10]
Agent 10's `AllProviders` wrapper includes `QueryClientProvider` and `ThemeProvider` but NOT a Clerk mock. Any component using `useAuth()`, `useUser()`, or `useOrganization()` will fail in tests. **Resolution needed: Add `<ClerkProvider>` mock or use `@clerk/testing` package in test utilities.**

[FLAG: **MEDIUM — Co-located tests vs test directory contradiction** | Agents 2, 10]
Agent 2 mandates "co-located tests — test files live next to their source." Agent 10's examples use `src/tests/integration/coherence-dashboard.test.tsx` — a separate test directory. The uploaded `FRONTEND_TESTING_PLAN.md` uses `__tests__/unit/components/`. Three different conventions. **Resolution needed: Define ONE convention. Recommendation: co-located for unit tests (`ScoreCard.test.tsx`), `src/tests/integration/` for integration, `e2e/` root for Playwright.**

[FLAG: **LOW — 192 tests may be ambitious for 8 weeks with zero starting tests** | Agents 1, 10]
Agent 1 emphasizes speed and warns about solo developer burnout. Agent 10 plans 192 tests. At ~15 minutes per test (including setup and debugging), that's ~48 hours of pure test writing — roughly 6 full workdays. Across 4 sprints, that's feasible but leaves little margin. **Resolution needed: Prioritize tests by critical path. Sprint 1-2: 60 tests (auth, project list, coherence dashboard). Sprint 3-4: 80 tests. Post-launch: remaining 52.**

---

## === REVIEWER 6: SECURITY, COMPLIANCE & PRODUCTION READINESS ===

### Summary of Plans

Agent 3 (Security) provides the primary security analysis, with Agent 11 (AI UX) addressing AI-specific compliance (disclaimer), Agent 12 (Production) covering deployment security, and the Architecture Plan v2.1 defining backend compliance requirements.

**Strengths:**
- Clerk-first auth approach eliminates an entire class of security bugs (token management, session handling, MFA)
- CSP header definition is comprehensive and correctly allows Clerk, R2 storage, and Tailwind inline styles
- PDF watermark approach (Canvas overlay, pointer-events:none, print:hidden) is correct
- Legal disclaimer with mandatory checkboxes meets the Architecture Plan v2.1 §14.4 requirements

**Weaknesses:**
- No agent addressed **GDPR cookie consent** — Clerk sets cookies, Sentry tracks sessions, these require user consent in EU
- No agent defined **Content-Disposition** headers for document downloads (PDF export, CSV export)
- The `beforeSend` PII scrubbing (Agent 12) deletes `user.email` but Sentry may still capture PII in breadcrumbs, error messages, or URL parameters
- No agent addressed **tenant isolation in frontend** — if user switches organizations in Clerk, cached TanStack Query data from the previous tenant must be purged

---

### Flags

[FLAG: **CRITICAL — Tenant data leak on organization switch** | Agents 3, 9]
Clerk supports multi-organization. When a user switches from Tenant A to Tenant B, TanStack Query cache still contains Tenant A's projects, alerts, and coherence data. If the cache serves stale data before refetch, Tenant B's user briefly sees Tenant A's data. **Resolution needed: On organization change event (`useOrganization()` listener), call `queryClient.clear()` to purge ALL cached data before any fetches for the new tenant.**

[FLAG: **HIGH — CSP blocks Sentry replay** | Agents 3, 12]
Agent 3's CSP includes `script-src 'self' 'unsafe-eval' 'unsafe-inline'`. Sentry Replay captures DOM snapshots which may require `worker-src blob:` and additional `connect-src` entries for Sentry's ingest endpoint. Without these, Sentry Replay silently fails. **Resolution needed: Add `worker-src blob: 'self'` and `connect-src ... https://*.ingest.sentry.io` to CSP.**

[FLAG: **HIGH — GDPR consent flow missing** | Agents 3, 11, 12]
C2Pro targets Spain and LATAM (EU jurisdiction). Clerk cookies, Sentry session replay, and OpenTelemetry beacons all require GDPR consent. No agent defined a cookie consent banner or consent management flow. **Resolution needed: Add a cookie consent component (Sprint 1) using a lightweight library like `cookie-consent-js`. Sentry and Clerk should be initialized ONLY after consent is given for non-essential cookies.**

[FLAG: **MEDIUM — PDF watermark uses user email (PII concern)** | Agents 3, 12]
Agent 3 endorses the PDF watermark showing "user email + timestamp." Agent 12's Sentry config strips email from error reports for GDPR. But embedding email in a Canvas overlay means it's visible on screen and in screenshots shared externally. **Resolution needed: Use a pseudonymized identifier (e.g., `user_abc123`) instead of raw email in watermarks. Map to real email only in audit logs.**

[FLAG: **MEDIUM — Rate limiting implementation incomplete** | Agent 3]
Agent 3 proposes "max 10 requests/second per user" on the API client. But the implementation is Axios-based without specifying how to enforce this. Axios doesn't have built-in rate limiting. **Resolution needed: Use `axios-rate-limit` or implement a token bucket in the Axios interceptor. Alternatively, rely entirely on backend rate limiting and handle 429 responses gracefully (Agent 12 already handles this).**

[FLAG: **MEDIUM — Legal disclaimer acceptance not persisted server-side** | Agents 3, 11]
Agent 3 states "Must persist acceptance in backend, not localStorage." Agent 11 shows the disclaimer UI component. But neither agent defines the API endpoint (`POST /api/v1/users/disclaimer-acceptance`) or the query to check acceptance on load. The Architecture Plan v2.1 §14.4 requires checkboxes but doesn't specify the backend contract. **Resolution needed: Define OpenAPI endpoint for disclaimer acceptance (POST to accept, GET to check). Frontend checks on first authenticated load and gates all `(dashboard)` routes until accepted.**

[FLAG: **LOW — Source maps exposure risk** | Agent 12]
The TDD's `withSentryConfig` includes `hideSourceMaps: true`, which is correct. But Agent 12's production checklist marks source maps as "✅ In config" without verifying that `next build` doesn't also emit `.map` files to the public output. **Resolution needed: Verify with `find .next -name '*.map'` after build. If maps exist in static output, add `productionBrowserSourceMaps: false` to next.config.ts.**

---

## Cross-Review Summary: All Flags by Severity

### 🔴 CRITICAL (4 flags — must resolve before Sprint 1)

| # | Flag | Agents | Impact |
|---|------|--------|--------|
| 1 | Auth store contradiction (Zustand vs Clerk) | 1, 3, 9 | Dual source of truth → token desync → auth failures |
| 2 | Axios interceptor cannot call `useAuth()` hook | 3 | Proposed fix is technically impossible → API calls fail |
| 3 | SSE stream not authenticated | 3, 9, 12 | Processing endpoint is a security hole |
| 4 | Tenant data leak on organization switch | 3, 9 | Cross-tenant data exposure → compliance violation |

### 🟠 HIGH (10 flags — must resolve before Sprint 2)

| # | Flag | Agents | Impact |
|---|------|--------|--------|
| 5 | `require()` in ESM Axios interceptor | TDD, 4 | Runtime error in ESM context |
| 6 | Presentation→Data layer rule too rigid for Server Components | 4, 9 | False violations in legitimate code |
| 7 | Keyboard shortcuts violate WCAG 2.1.4 | 6, 7 | Accessibility failure for voice control users |
| 8 | Primary color used inconsistently (contrast failure) | 7, 8, TDD | WCAG AA violation on primary text |
| 9 | Recharts bundle exceeds dashboard budget | 5, 8 | 50KB budget impossible with Recharts |
| 10 | Font loading strategy missing (~140KB blocking FCP) | 5, 8, 12 | LCP regression |
| 11 | Testing plan document outdated | 10, Testing Plan | Tests built for wrong architecture |
| 12 | No SSE/streaming test strategy | 9, 10, 12 | Critical flow untested |
| 13 | Server Component testing is technically impossible as written | 4, 10 | Integration tests will fail |
| 14 | GDPR consent flow missing | 3, 11, 12 | EU compliance violation |

### 🟡 MEDIUM (11 flags — resolve by Sprint 3)

| # | Flag | Agents | Impact |
|---|------|--------|--------|
| 15 | Barrel exports defeat tree-shaking | 2, 5 | Bundle bloat |
| 16 | Missing monorepo configuration | 1, 2 | CI confusion |
| 17 | Undo pattern + Coherence invalidation race | 6, 11 | Stale score display |
| 18 | Mobile Evidence Viewer undefined | 5, 6, 7 | Broken mobile UX |
| 19 | Onboarding sample project requires backend support | 6, 9, 11 | Onboarding dead-ends in production |
| 20 | Optimistic score recalculation duplicates backend logic | 5, 9 | Frontend-backend formula drift |
| 21 | TanStack Query keys diverge from Orval-generated keys | 4, 9, 10 | Cache duplication + invalidation misses |
| 22 | SSE processing state lost on navigation | 9, 4 | User loses progress visibility |
| 23 | Cross-tab cache invalidation not addressed | 9, 12 | Stale data in secondary tabs |
| 24 | Tremor admin portal bundle unoptimized | 1, 5 | Admin route >80KB |
| 25 | `staleTime` too aggressive post-processing | 5, 9 | Stale coherence score after upload |

### 🟢 LOW (6 flags — resolve by Sprint 4 or post-launch)

| # | Flag | Agents | Impact |
|---|------|--------|--------|
| 26 | Test-utils.tsx missing Clerk provider | 3, 10 | Tests crash on auth hooks |
| 27 | Co-located tests vs test directory contradiction | 2, 10 | Developer confusion |
| 28 | 192 tests ambitious for solo developer in 8 weeks | 1, 10 | Test debt accumulation |
| 29 | Command palette scope undefined | 8, TDD | Unused dependency |
| 30 | Filter persistence missing (UX friction) | 9 | Minor usability annoyance |
| 31 | PDF watermark uses raw email (PII) | 3, 12 | GDPR concern for shared screenshots |

---

### Key Contradiction Matrix

| Topic | Agent A says... | Agent B says... | Resolution Direction |
|-------|----------------|----------------|---------------------|
| Auth store | Agent 1: Create it in Sprint 1 | Agent 3: Remove it entirely | **Remove — use Clerk only** |
| Storybook timing | Agent 1: Defer | Agent 8: Sprint 1 | **Sprint 1 for ui/ only, defer features/** |
| Barrel exports | Agent 2: Mandatory everywhere | Agent 5: Tree-shaking concern | **ui/ only, direct imports elsewhere** |
| Layer rules | Agent 4: No direct data access | Next.js pattern: Server Components fetch | **Amend rule for Server Components** |
| Query keys | Agent 9: Manual queryKeys | Orval: Auto-generated | **Orval-generated only** |
| Test location | Agent 2: Co-located | Agent 10: Separate dirs | **Co-located unit, separate integration** |
| Chromatic timing | Agent 1: Sprint 3 | Agent 8: Sprint 3 | **Agreed — Sprint 3** |
| CSP `unsafe-eval` | Agent 3: Include for Clerk | Security best practice: Avoid | **Required by Clerk — document as accepted risk** |

---

> ✅ Phase 2 completed. 31 flags identified (4 critical, 10 high, 11 medium, 6 low). Ready for Phase 3.
