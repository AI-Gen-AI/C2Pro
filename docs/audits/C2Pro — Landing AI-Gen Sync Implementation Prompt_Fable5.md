# C2Pro — Landing × AI-Gen Brand Sync Implementation Prompt (patch-by-patch)

**Date:** 2026-07-06 · **Epic:** `EPIC-FRT-LANDING-SYNC` · **Backlog IDs:** `TASK-FRT-198` … `TASK-FRT-202` (registered in `C2PRO_MASTER_BACKLOG.md` and `backlogs/FRT_FRONTEND.md`)
**Brand reference:** the live https://www.ai-gen.ai site — repo `AI-Gen-AI/2SB`, local `C:\Users\esus_\Documents\2SB\02_PROYECTOS\03-AI-Gen` (static HTML; `assets/site.css` = **AI-Gen Design System v2 "Tech-Editorial B2B Premium"**). c2pro.io must read as the product arm of that ecosystem.

This document is a **self-contained execution prompt**. Feed it to a Codex/Claude session as:

```text
Implement PATCH <N> (TASK-FRT-<ID>) from docs/audits/C2Pro — Landing AI-Gen Sync Implementation Prompt_Fable5.md. Follow the Ground Rules section exactly.
```

## Why this epic exists (evidence)

1. **SEO-dead landing:** `apps/web/app/page.tsx` is a client component gated on `useAuth()` — crawlers receive only "Loading..." (verified via live fetch of https://www.c2pro.io on 2026-07-06). The real landing markup (`components/landing-page-content.tsx`) never reaches the initial HTML.
2. **Brand contradiction:** the current landing shows **fabricated stats** ("94% Risk Detection Rate", "$2.4M Avg. Savings", "6x Faster Review", "<30s Analysis Time") and "Join enterprise teams…" copy. ai-gen.ai's entire positioning — and this repo's honesty doctrine (ADR-013, honest-null) — is *"no promete detección perfecta"*, pilot-in-validation, human-validated. The marketing page is the one surface where the honesty principle is currently most violated.
3. **Scaffold quality:** dead `href="#"` links (Pricing, Privacy, Terms, Contact), a debug "Deploy marker 2026-03-30-a" badge in the footer, generic shadcn look disconnected from the AI-Gen brand (Source Serif 4 + Geist, alabaster/navy/teal editorial system).
4. **Broken shared funnel:** ai-gen.ai's C2Pro pilot waitlist form does **not capture leads** — `assets/site.js` intercepts the POST because no backend exists (comment: *"Forms — sin backend todavía"*). c2pro.io (a real Next.js app with Supabase) is the natural home of the single waitlist endpoint for both sites.

## Role

You are a Senior Frontend Engineer working on `apps/web/` (Next.js 16 App Router, React 19, TypeScript strict, Tailwind v4 + shadcn/ui, Clerk, Vitest + MSW). For PATCH 4 you also touch `apps/api/alembic/` + `supabase/migrations/` (one additive migration). You make surgical, evidence-based changes; you do not redesign the product app, and you do not expand scope.

## Ground Rules (apply to every patch)

1. **Branch:** `feat/frt-landing-sync`, created from the tip of `fix/frt-l1-wave0` (this epic shares `apps/web/app/page.test.tsx` with wave0; if wave0 is already merged to `main`, branch from `main`). Never push to `main`. Conventional commits, **no Co-Authored-By trailers**.
2. **TDD:** failing test first (RED), implement (GREEN), refactor. Colocated tests next to files.
3. **Verification before done (from `apps/web/`):** `pnpm typecheck && pnpm lint` + the patch's own `Verify` command. `pnpm test:all` has pre-existing debt (15 files / 34 tests, cataloged under `TASK-FRT-192`) — the gate is: **no NEW failures** vs. that baseline.
4. **Honesty principle (hard invariant):** the landing must contain **zero fabricated metrics or claims**. Product visuals must carry the "Vista ilustrativa / Illustrative view" label. The only number allowed in the mockup is the real pilot-derived example (636 M vs 654 M → 2.8 % deviation, DET-BUD-SUM) and it stays inside the clearly-labeled illustrative console.
5. **Copy is provided verbatim** in the Copy Pack below (ES + EN). Do not invent, "improve", or re-translate copy. Typos in the pack may be fixed if flagged in the report.
6. **New deps pre-approved for this epic only:** `zod`, `geist`, `@fontsource-variable/source-serif-4`. Nothing else without flagging.
7. **Blast-radius guard:** landing code lives in `apps/web/components/landing/**` + `apps/web/app/page.tsx` + `apps/web/app/en/**` + `apps/web/app/api/waitlist/**`. Do not modify product-app components, the shadcn theme values, or `app/(app)/**` except where a patch explicitly lists it. New Tailwind tokens are **namespaced `brand-*`** and additive.
8. **Bilingual exception:** the landing is ES (default, `/`) + EN (`/en`). This is a deliberate exception to the "UI language is English" rule of the L1 prompt — the **product app** remains English-only.
9. **Backlog discipline (MANDATORY per `.claude/rules/CRITICAL_BACKLOG_REQUIREMENT.md`):** on completing a patch, mark its `TASK-FRT-NNN` `[x]` in `backlogs/FRT_FRONTEND.md` **and** append verification evidence to the `C2PRO_MASTER_BACKLOG.md` Change Log.
10. **Self-hosted fonts only** (RGPD): no Google Fonts CDN requests. Fonts ship bundled (`geist` package + Fontsource files resolved at build).

## Wave map

| Wave | Patches | Gate |
|---|---|---|
| **Single wave — P1** | 1–5 (`TASK-FRT-198`…`202`) | c2pro.io serves a crawlable, AI-Gen-branded, honest bilingual landing with a working pilot-waitlist funnel and correct SEO metadata |

Recommended order: 1 → 2 → 3 → 4 → 5. (1 and 2 are independent; 3 depends on both; 4–5 depend on 3.)

---

# PATCH 1 — Root route restructure: server-rendered landing + `/en` + auth island

**Backlog ID:** `TASK-FRT-198` · **Priority:** P1 · **Depends on:** —

**Evidence:** `apps/web/app/page.tsx` is `'use client'`, waits on `useAuth()` before rendering `LandingPageContent`, inlines `AppDashboardPage` for authed users, and client-redirects admins. Crawlers see the `isLoading` spinner only. The proxy matcher (`apps/web/proxy.ts:41`) excludes `$` (root) from middleware, so **server-side `auth()` is NOT available at `/`** — do not try to call it there.

**Design decision (approved by owner):** `/` becomes a **static server component** that always renders the landing. Authenticated users are *not* auto-forwarded; the header shows "Ir al workspace" via a client island (Linear/Vercel pattern). This keeps root fully static and avoids proxy-matcher surgery.

**Files:**
- `apps/web/app/page.tsx` (rewrite: server component)
- `apps/web/app/en/page.tsx` (new)
- `apps/web/components/landing/landing-auth-buttons.tsx` (new, client)
- `apps/web/components/landing-page-content.tsx` (minimal edits only — full rewrite is PATCH 3)
- `apps/web/app/(app)/dashboard/page.tsx` (only if admin-bounce must move — see step 4)
- `apps/web/proxy.ts` (add `/en` to public routes)
- Tests: `apps/web/app/page.test.tsx` (rewrite), `apps/web/app/en/page.test.tsx` (new)

**Steps:**
1. Rewrite `app/page.tsx` as a **server component** (no `'use client'`, no hooks) that renders `<LandingPageContent locale="es" />`. Delete the `AppDashboardPage` import, the spinner branches, and the `useRouter` redirects. (PATCH 3 replaces `LandingPageContent` wholesale; for now add an optional `locale?: 'es' | 'en'` prop it may ignore.)
2. Create `app/en/page.tsx` server component rendering `<LandingPageContent locale="en" />`. Add `"/en"` to `isPublicRoute` in `proxy.ts` (the matcher already lets middleware run on `/en`; being in the public list prevents `auth.protect()`).
3. New client component `components/landing/landing-auth-buttons.tsx`: uses Clerk's `<SignedIn>` / `<SignedOut>` (from `@clerk/nextjs`). SignedOut → ghost link "Iniciar sesión" (`/login`) + primary CTA anchor "Unirse al piloto" (`#waitlist`). SignedIn → primary link "Ir al workspace" (`/dashboard`). Accepts a `labels` prop so PATCH 3 can feed locale copy; default labels = the ES strings. Swap it into the current nav in `landing-page-content.tsx`, replacing the static Sign In / Get Started buttons.
4. **Preserve admin routing:** `rg -n "admin/c2pro|admin/tenant" apps/web` — if the role-based bounce (`c2pro_admin → /admin/c2pro`, `tenant_admin → /admin/tenant`) exists **only** in the old root page, move that check into `app/(app)/dashboard/page.tsx` (client-side, it already runs under `(app)` with auth context). If it already exists in `(app)` layout/dashboard, just delete it with the old root code.
5. While in `landing-page-content.tsx`, delete the footer "Deploy marker 2026-03-30-a" `<span>` (debug text in production).
6. Do NOT add `auth()` / `currentUser()` to `/` or `/en` — the matcher excludes them and it would break the static render.

**Tests (RED first):**
- Rewrite `app/page.test.tsx`: renders without any auth-context mock, asserts hero text is present in the initial render (no "Loading..."), and asserts the module does **not** import `AppDashboardPage` (e.g. static assertion via `rg` in the verify step, plus a render test).
- New `app/en/page.test.tsx`: renders and shows landing content.
- `landing-auth-buttons.test.tsx`: with Clerk mocked signed-out → "Iniciar sesión" visible; signed-in → "Ir al workspace" visible (mock `@clerk/nextjs`'s `SignedIn`/`SignedOut` as conditional passthroughs).
- Admin-bounce test in its new home (mock role `c2pro_admin` → replace-navigate `/admin/c2pro`).

**Acceptance criteria:**
- `curl` (or `next build` + inspect) of `/` returns the landing markup in the HTML body — no auth spinner.
- Signed-in users see "Ir al workspace" in the header at `/`; signed-out see "Iniciar sesión".
- An authenticated `c2pro_admin` who navigates to `/dashboard` still ends at `/admin/c2pro`.
- `rg -n "Deploy marker" apps/web` → 0 hits.

**Verify:** `pnpm vitest run app/page.test.tsx app/en components/landing && pnpm typecheck && pnpm lint`

---

# PATCH 2 — AI-Gen Design System v2 tokens, fonts, landing primitives

**Backlog ID:** `TASK-FRT-199` · **Priority:** P1 · **Depends on:** —

**Evidence:** AI-Gen DS v2 (`03-AI-Gen/assets/site.css`): alabaster `#F7F4ED` base, navy `#0B1F3A`/`#081628`/`#08172B`, ink `#111827`, muted `#667085`/`#98A2B3`, lines `#D8DEE6`/`#E7EAF0`, single teal accent `#0F766E` (dark `#115E59`, soft `#DDF5F1`, ink `#0E6A62`, bright `#5FC9BD`, on-navy `#8FD8CF`), state colors warning `#F8E8C8`/`#8A6D2F`, risk `#F4D7D7`/`#9B3B3B`; on-navy text `#E7EEF6`/`#94A3B8`. Type: Source Serif 4 (display, weight 500, tight leading), Geist (sans), Geist Mono (eyebrow labels, `0.74rem`, `letter-spacing:0.18em`, uppercase). Radius 14px, max-width 1200px, 8px spacing, generous section padding (`clamp(64px,11vw,128px)`).

**Files:**
- `apps/web/app/globals.css` (additive `@theme` block only)
- `apps/web/components/landing/fonts.ts` (new)
- `apps/web/components/landing/primitives.tsx` (new) + `primitives.test.tsx`
- `apps/web/components/landing/reveal.tsx` (new, client) + test
- `apps/web/package.json` (deps: `geist`, `@fontsource-variable/source-serif-4`)

**Steps:**
1. `pnpm add geist @fontsource-variable/source-serif-4` (pre-approved).
2. `fonts.ts`: export `GeistSans`, `GeistMono` from the `geist` package (`geist/font/sans`, `geist/font/mono`) and import `@fontsource-variable/source-serif-4` CSS; export a `landingFontClasses` string combining the Geist `.variable` classes. Define `--font-brand-display: 'Source Serif 4 Variable', Georgia, 'Times New Roman', serif` (via the `@theme` block below). No Google Fonts `<link>` anywhere.
3. `globals.css`: append an **additive** `@theme` block (comment header `/* Landing brand tokens — AI-Gen DS v2 (EPIC-FRT-LANDING-SYNC) */`) defining `--color-brand-*` for every color listed in Evidence (`brand-alabaster`, `brand-paper`, `brand-ink`, `brand-slate`, `brand-muted`, `brand-muted-2`, `brand-navy`, `brand-navy-2`, `brand-navy-panel`, `brand-line`, `brand-line-soft`, `brand-accent`, `brand-accent-dark`, `brand-accent-soft`, `brand-accent-ink`, `brand-accent-bright`, `brand-accent-on-navy`, `brand-warning-soft`, `brand-warning-ink`, `brand-risk-soft`, `brand-risk-ink`, `brand-on-navy`, `brand-on-navy-muted`) plus `--font-brand-display`. Touch **nothing** in the existing theme.
4. `primitives.tsx` — small presentational components (server-compatible, typed props, no state):
   - `Eyebrow` — Geist Mono, uppercase, tracking-[0.18em], `text-brand-accent-ink` (`text-brand-accent-on-navy` inside navy via prop `onNavy`).
   - `Display` / `H2` — Source Serif, weight 500, tight leading/tracking (`text-5xl md:text-7xl` for Display, fluid).
   - `SectionShell` — `<section>` with `id`, max-w-[1200px] container, py `clamp`, `variant: 'alabaster' | 'paper' | 'navy'`.
   - `BrandButton` — `variant: 'primary' | 'ghost' | 'outline'`, sizes sm/lg, teal primary with hover `brand-accent-dark`, arrow-icon slot (inline SVG identical to ai-gen.ai's 16×16 arrow).
   - `PilotBadge` — pill, dot, text (used for "Programa piloto · en validación").
   - `CheckList` / `CheckItem` — teal check SVG + text (matches ai-gen.ai `.bullets`/`.checks`).
5. `reveal.tsx` — client component: IntersectionObserver adds `in` state (threshold 0.1), renders children in a `div` with `opacity-0 translate-y-3 transition` → visible when `in`; **must respect `prefers-reduced-motion`** (skip transform/transition via CSS media query) and render content visible when JS is off (progressive enhancement: initial styles applied via a `.js`-gated class or `motion-safe:` utilities only).
6. No usage in the live pages yet (PATCH 3 consumes these) — but export everything from `components/landing/index.ts`.

**Tests (RED first):** render tests for each primitive (role/text/class assertions: Eyebrow uppercase + mono, BrandButton variants, SectionShell navy variant applies `bg-brand-navy`), Reveal test (mock IntersectionObserver: hidden → visible on intersect; with `matchMedia` reduced-motion mock → no motion classes).

**Acceptance criteria:**
- `pnpm build` succeeds; no visual change on any existing product page (tokens are additive + namespaced).
- `rg -n "fonts.googleapis" apps/web` → 0 hits.
- Primitives render with brand tokens (`bg-brand-navy`, `text-brand-accent-ink` utilities resolve).

**Verify:** `pnpm vitest run components/landing && pnpm typecheck && pnpm lint && pnpm build`

---

# PATCH 3 — Landing rebuild: sections + bilingual Copy Pack

**Backlog ID:** `TASK-FRT-200` · **Priority:** P1 · **Depends on:** `TASK-FRT-198`, `TASK-FRT-199`

**Evidence:** current `landing-page-content.tsx` (fabricated stats section, generic features, dead links) vs. the ai-gen.ai structure (`03-AI-Gen/c2pro.html`): hero + illustrative console, human-supervision band, 4-step protocol, origin & limits, navy waitlist, ecosystem footer.

**Files:**
- `apps/web/components/landing/copy.ts` (new — the Copy Pack below, typed)
- `apps/web/components/landing/landing-page.tsx` (new composition root)
- `apps/web/components/landing/sections/landing-header.tsx` (client: mobile menu + auth island from PATCH 1)
- `apps/web/components/landing/sections/hero.tsx` + `console-mock.tsx`
- `apps/web/components/landing/sections/dimensions.tsx`
- `apps/web/components/landing/sections/supervision.tsx`
- `apps/web/components/landing/sections/how-it-works.tsx`
- `apps/web/components/landing/sections/origin-limits.tsx`
- `apps/web/components/landing/sections/waitlist-section.tsx` (static shell; the live form arrives in PATCH 4 — render the copy + a `mailto:info@ai-gen.ai` fallback link where the form will mount)
- `apps/web/components/landing/sections/landing-footer.tsx`
- `apps/web/app/page.tsx` + `apps/web/app/en/page.tsx` (swap to `<LandingPage locale>`)
- **Delete** `apps/web/components/landing-page-content.tsx` (and update `app/page.test.tsx` accordingly)

**Steps:**
1. `copy.ts`: `interface LandingCopy` + `export const landingCopy: Record<'es' | 'en', LandingCopy>` containing the Copy Pack **verbatim**. All section components consume copy via props — zero hardcoded strings inside sections.
2. Compose `landing-page.tsx`: `<div className={landingFontClasses + ' bg-brand-alabaster text-brand-ink'}>` → Header, Hero (alabaster), Dimensions (`#producto`, paper band), Supervision (`#supervision`, alabaster), HowItWorks (`#como-funciona`, paper band), OriginLimits (`#origen`, alabaster), Waitlist (`#waitlist`, navy), Footer (navy-2). Anchor ids are locale-invariant (same ids on `/en`).
3. Header: C2Pro wordmark (text, Source Serif, with `·` + "AI-Gen" micro-tag linking https://www.ai-gen.ai), nav anchors (Producto / Cómo funciona / Origen / Piloto — from copy), auth island, mobile menu (client, `useState`, focus-trapped dialog or simple full-screen panel with `aria-expanded`, Escape-close).
4. Hero: `PilotBadge` + `Display` H1 + lead + primary CTA (`#waitlist`) + secondary outline CTA (`/demo/coherence-v1`) + trust note (check icon). Right panel: `console-mock.tsx` — decorative `aria-hidden="true"` console styled after ai-gen.ai's `.console` (bar with 3 dots + title + badges "Vista ilustrativa"/"Human approval queue"; body = 4 document rows with status badges + evidence box quoting the DET-BUD-SUM example; foot = validation line + "Pending approval" badge). Content from copy (it is locale-dependent).
5. Dimensions: eyebrow + H2 + prose (mentions **Coherence Score™** — keep the ™), 3 cards (Contrato/Cronograma/Presupuesto) on paper with `brand-line` borders, then the 6 dimension chips (Geist Mono, small, bordered pills).
6. Supervision: split layout — left eyebrow/H2/prose, right `CheckList` of 3 bullets (bold lead-ins per copy).
7. HowItWorks: eyebrow + H2 + lead + 4 numbered steps (`01`–`04` in Geist Mono accent, then bold title + one-liner) in a 4-col grid (stacks on mobile).
8. OriginLimits: eyebrow + H2 + two columns: "Parte del ecosistema AI-Gen" (with `<a href="https://www.ai-gen.ai" rel="noopener">ai-gen.ai</a>` link, teal, underlined) and "Qué no hace" (the honesty block — verbatim).
9. Waitlist section (navy): left = eyebrow/H2/lead + 3 checks; right = form card **shell** (`bg-brand-navy-panel`, border `on-navy` line) rendering title + the fallback `mailto:` link; PATCH 4 mounts the real form here.
10. Footer (navy-2): brand block (C2Pro + tagline + ecosystem line linking ai-gen.ai), 3 link columns from copy (Producto / AI-Gen / Contacto — AI-Gen column links to `https://www.ai-gen.ai/services`, `/lab`, `/dossier`, `/about`; the site uses `cleanUrls`), bottom row: `© 2026 C2Pro · Parte de AI-Gen.ai`, legal links to `https://www.ai-gen.ai/aviso-legal`, `/privacidad`, `/cookies`, and the **language switch** (`/` ↔ `/en`, plain links labeled "EN" / "ES").
11. Wrap section blocks in `Reveal` (motion-safe only). Single `<h1>` per page; sections use `<h2>`/`<h3>`; landmarks: `<header> <main> <footer>` + `<nav aria-label>`.
12. Delete `landing-page-content.tsx`; update `app/page.tsx` / `app/en/page.tsx` to render `<LandingPage locale="es" | "en" />`.

**Tests (RED first):**
- `landing-page.test.tsx`: renders ES → asserts H1 "Tres documentos. Una sola verdad.", pilot badge, waitlist H2, footer legal links point at ai-gen.ai, **no fabricated-stat strings** (`94%`, `$2.4M`, `6x Faster` must NOT appear); renders EN → "Three documents. One single truth." etc.
- `console-mock.test.tsx`: has `aria-hidden`, contains "Vista ilustrativa" (ES) / "Illustrative view" (EN), contains the 2,8 % evidence line.
- Header test: mobile menu opens/closes, nav anchors present, lang switch href correct per locale.
- Update `app/page.test.tsx` / `app/en/page.test.tsx` for new copy.
- Axe smoke (if `vitest-axe` present; otherwise assert landmark roles + single h1).

**Acceptance criteria:**
- `/` is fully ES, `/en` fully EN, identical structure, both server-rendered.
- Zero occurrences of the old fabricated stats/copy: `rg -n "94%|2\.4M|6x Faster|Join enterprise|Access Real Workspace" apps/web` → 0 hits.
- All links resolve (no `href="#"` anywhere on the landing); external ai-gen.ai links carry `rel="noopener"`.
- Lighthouse (manual, dev build ok): LCP element = hero H1 text, no CLS from fonts (`display: swap` via next/font + fontsource defaults).

**Verify:** `pnpm vitest run components/landing app/page.test.tsx app/en && pnpm typecheck && pnpm lint`

---

# PATCH 4 — Pilot waitlist funnel: table (RLS) + `/api/waitlist` + form

**Backlog ID:** `TASK-FRT-201` · **Priority:** P1 · **Depends on:** `TASK-FRT-200`

**Evidence:** ai-gen.ai's form fields (`03-AI-Gen/c2pro.html:181-204`): name, company, role, email, volume (`under_20 | 20_100 | over_100`), RGPD consent — currently captured **nowhere** (`site.js` stub). Security baseline (`CLAUDE.md`): every new table needs RLS. Dual migration systems: Alembic authoritative + `supabase/` mirror. **Alembic single-head discipline** (a past dual-head incident crash-looped deploys — new revision's `down_revision` must be the current head, verify with `alembic heads` → exactly one).

**Files:**
- `apps/api/alembic/versions/<rev>_add_waitlist_signups.py` (new)
- `supabase/migrations/<ts>_add_waitlist_signups.sql` (mirror)
- `apps/web/app/api/waitlist/route.ts` (new)
- `apps/web/components/landing/waitlist-schema.ts` (new, shared zod schema)
- `apps/web/components/landing/sections/waitlist-form.tsx` (new, client) — mounted into the PATCH 3 shell (replace the mailto fallback)
- `apps/web/proxy.ts` (add `"/api/waitlist"` to `isPublicRoute` — **without this, `auth.protect()` blocks the endpoint**)
- `apps/web/.env.example` (or the web env template that exists): document `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `WAITLIST_ALLOWED_ORIGINS`
- Tests: `route.test.ts`, `waitlist-form.test.tsx`

**Steps:**
1. **Migration** (Alembic, then mirror SQL for Supabase CLI): table `waitlist_signups`:
   - `id uuid PK default gen_random_uuid()`, `created_at timestamptz not null default now()`, `name text not null`, `company text not null`, `role text`, `email text not null`, `volume text` with `CHECK (volume IN ('under_20','20_100','over_100'))`, `consent boolean not null`, `locale text`, `source text not null default 'c2pro.io'`, `user_agent text`.
   - `UNIQUE (email)` **plain column constraint** (the handler lowercases/trims email before insert — PostgREST `on_conflict=email` needs a real constraint, not an expression index).
   - `ALTER TABLE waitlist_signups ENABLE ROW LEVEL SECURITY;` — **zero policies** (deny-all for anon/authenticated; the service role bypasses RLS). Downgrade drops the table.
2. `waitlist-schema.ts` (shared client/server): zod object — `name` 1..120, `company` 1..120, `role` optional ≤120, `email` `.email()` ≤254 (transform: trim + lowercase), `volume` optional enum, `consent` `z.literal(true)`, `locale` optional `'es'|'en'`, `website` (honeypot) `z.literal('')`.
3. `route.ts` (`POST` + `OPTIONS`):
   - CORS: allowlist from `WAITLIST_ALLOWED_ORIGINS` (default `https://www.ai-gen.ai,https://ai-gen.ai`). Same-origin requests have no `Origin` mismatch problem; if `Origin` present and allowed → echo it in `Access-Control-Allow-Origin` + `Vary: Origin`; `OPTIONS` returns 204 with `Access-Control-Allow-Methods: POST` + `Access-Control-Allow-Headers: Content-Type`. Disallowed cross-site origins get no CORS headers (browser blocks the response; do not 403 same-origin traffic that lacks Origin).
   - Parse JSON body → zod. **Honeypot filled → return `{ success: true }` 200 without inserting** (don't tip off bots). Validation failure → 400 `{ success: false, error: <flattened field errors> }` (no internals leaked).
   - Best-effort throttle: module-level `Map<ip, timestamps[]>` sliding window, max 5 requests / 10 min per IP (`x-forwarded-for` first hop) → 429. Comment honestly that this is per-instance best-effort.
   - Insert via PostgREST fetch (no supabase-js dep): `POST ${SUPABASE_URL}/rest/v1/waitlist_signups` with headers `apikey` + `Authorization: Bearer ${SUPABASE_SERVICE_ROLE_KEY}`, `Prefer: resolution=merge-duplicates,return=minimal`, query `?on_conflict=email` → duplicate submits are idempotent 200s. Store `locale`, `user_agent` (from headers), `source` (`'c2pro.io'` or `'ai-gen.ai'` when the Origin is theirs).
   - Missing env vars → 503 `{ success: false, error: 'Service not configured' }` + server-side `console.error` — never expose key names. Env access **server-only** (route handler; never `NEXT_PUBLIC_*`).
4. `waitlist-form.tsx` (client): controlled form mirroring ai-gen.ai's layout (2-col grid on desktop), labels/placeholders/options from the Copy Pack, client-side zod validation with inline field errors, visually-hidden honeypot input (`tabIndex={-1}`, `autoComplete="off"`, `aria-hidden`, positioned off-screen — not `display:none`), RGPD consent checkbox whose label links to `https://www.ai-gen.ai/privacidad`, pending state on submit (disabled + spinner), success state (replace form body with the success message), error state (inline error + retry preserved input). POSTs to `/api/waitlist` with `locale`.
5. Mount the form in the PATCH 3 navy shell (remove the mailto fallback).

**Tests (RED first):**
- `route.test.ts`: valid body → PostgREST fetch called with service headers + `on_conflict=email`, 200; invalid email / missing consent → 400 with field errors and **no fetch**; honeypot filled → 200 and **no fetch**; 6th request same IP within window → 429; `OPTIONS` from `https://www.ai-gen.ai` → 204 + ACAO echo; from `https://evil.example` → no ACAO header; missing env → 503. Mock `global.fetch`; use fake timers for the throttle.
- `waitlist-form.test.tsx`: renders all fields from copy (ES + EN), consent unchecked blocks submit with visible error, success message on 200, honest error message on 500, honeypot input is `aria-hidden` and off-screen.

**Acceptance criteria:**
- Submitting the form on `/` inserts a row (verified in test via mocked PostgREST call; manually via Supabase table editor in staging).
- Duplicate email re-submit → still a success UX (idempotent upsert), no 500.
- `rg -n "SUPABASE_SERVICE_ROLE_KEY" apps/web/components apps/web/app --glob '!app/api/**'` → 0 hits (key never leaves the route handler).
- **Owner ops note (report it, don't do it):** add `SUPABASE_URL` + `SUPABASE_SERVICE_ROLE_KEY` (+ optional `WAITLIST_ALLOWED_ORIGINS`) to the c2pro.io web deployment env; run `alembic upgrade head`; follow-up in the **other repo**: point ai-gen.ai's form `action` at `https://www.c2pro.io/api/waitlist` (CORS is ready for it).
- `alembic heads` → exactly one head.

**Verify:** `pnpm vitest run app/api/waitlist components/landing/sections/waitlist-form.test.tsx && pnpm typecheck && pnpm lint` · backend: `cd apps/api && alembic heads`

---

  # PATCH 5 — SEO, metadata, sitemap/robots, OG image

   **Backlog ID:** `TASK-FRT-202` · **Priority:** P1 · **Depends on:** `TASK-FRT-200`

**Evidence:** current root metadata is app-flavored (`"C2Pro v3.0 - Coherence Monitor"` — this is what Google shows today), no canonical/hreflang, no sitemap/robots files, no OG image, `themeColor #00ACC1` (not a brand color).

**Files:**
- `apps/web/app/layout.tsx` (metadata defaults: `metadataBase`, title template, brand `themeColor`)
- `apps/web/app/page.tsx` + `apps/web/app/en/page.tsx` (per-locale `metadata` exports)
- `apps/web/app/sitemap.ts`, `apps/web/app/robots.ts` (new)
- `apps/web/app/opengraph-image.tsx` (new — `next/og` `ImageResponse`)
- `apps/web/components/landing/json-ld.tsx` (new)
- Tests: `app/seo.test.ts` (metadata objects), `sitemap`/`robots` unit tests

**Steps:**
1. `layout.tsx`: `metadataBase: new URL('https://www.c2pro.io')`, `title: { default: 'C2Pro · Inteligencia documental para compras y contratos', template: '%s · C2Pro' }`, description = ES meta below, `themeColor: '#0B1F3A'`. Keep icons.
2. Per-page metadata:
   - `/` (ES): title `C2Pro · Inteligencia documental para compras y contratos`; description `C2Pro cruza contrato, cronograma y presupuesto para detectar incoherencias, desviaciones y riesgos, con evidencia citada y validación humana experta. Únete al piloto.`; `alternates: { canonical: '/', languages: { 'es': '/', 'en': '/en', 'x-default': '/' } }`; `openGraph` (type website, locale `es_ES`, siteName C2Pro, url `/`) + `twitter: { card: 'summary_large_image' }`.
   - `/en`: title `C2Pro · Document intelligence for procurement and contracts`; description `C2Pro cross-checks contract, schedule and budget to surface inconsistencies, deviations and risks — with cited evidence and expert human validation. Join the pilot.`; canonical `/en`, same `languages` map, OG locale `en_US`.
3. `json-ld.tsx`: one `<script type="application/ld+json">` on both locales — `Organization` (name C2Pro, url https://www.c2pro.io, `parentOrganization` → Organization AI-Gen, url https://www.ai-gen.ai, email info@ai-gen.ai) + `SoftwareApplication` (name C2Pro, applicationCategory BusinessApplication, operatingSystem Web, offers: pilot program / preorder availability — **no invented ratings or prices**).
4. `sitemap.ts`: `/` (priority 1, `alternates.languages`) + `/en`. `robots.ts`: allow `/`, `/en`, `/demo`; disallow `/dashboard`, `/projects`, `/admin`, `/api`, `/(app)` internals; `sitemap: https://www.c2pro.io/sitemap.xml`.
5. `opengraph-image.tsx` (1200×630, `ImageResponse`): navy `#0B1F3A` background, "C2Pro" wordmark (serif feel — load Source Serif via `fetch`-less local file import if trivial, else system serif is acceptable inside ImageResponse), tagline `Inteligencia documental para compras y contratos`, small teal accent rule, "Parte del ecosistema AI-Gen" bottom-right in `#8FD8CF`. Also export `alt`.
6. Remove/replace any leftover `themeColor #00ACC1` viewport export.

**Tests (RED first):** import the exported `metadata` objects and assert titles/canonicals/hreflang maps; `sitemap()` returns both URLs; `robots()` disallows `/api` and `/dashboard`; json-ld component snapshot contains `parentOrganization` and **no** `aggregateRating`.

**Acceptance criteria:**
- `next build` output shows `/` and `/en` as static (`○`), `opengraph-image` route present.
- Rich-results sanity: JSON-LD parses (paste into validator manually), hreflang pair is reciprocal.
- Google-visible title no longer "C2Pro v3.0 - Coherence Monitor".

**Verify:** `pnpm vitest run app/seo.test.ts && pnpm typecheck && pnpm lint && pnpm build`

---

# Copy Pack (verbatim — do not edit)

> Sections consume these exact strings via `copy.ts`. `™` stays with Coherence Score™ on first mention per page. Numbers in the console mock are the real pilot-derived example and appear **only** inside the "Vista ilustrativa" console.

## ES (`/`)

**Header** — nav: `Producto` (#producto) · `Cómo funciona` (#como-funciona) · `Origen` (#origen) · `Piloto` (#waitlist). Auth: `Iniciar sesión` (/login) · CTA `Unirse al piloto` (#waitlist) · signed-in: `Ir al workspace` (/dashboard). Brand micro-tag: `un producto AI-Gen` (→ https://www.ai-gen.ai).

**Hero** — badge: `Programa piloto · en validación`. H1: `Tres documentos. Una sola verdad.` Lead: `C2Pro cruza contrato, cronograma y presupuesto para detectar incoherencias, desviaciones y riesgos — con evidencia citada y validación humana experta antes de cada decisión.` CTA1: `Unirse al piloto` (#waitlist). CTA2: `Ver demo ilustrativa` (/demo/coherence-v1). Trust note: `Acceso prioritario y condiciones de fundador para las primeras organizaciones piloto.`

**Console mock (ES)** — bar title: `C2Pro · Workspace del proyecto`; badges: `Vista ilustrativa`, `Human approval queue`. Rows: `Contrato_principal.pdf` → `Evidence linked` · `Cronograma_obra.pdf` → `2 desviaciones` (warning) · `Presupuesto_v3.xlsx` → `Desviación 2,8 %` (risk) · `Oferta_proveedor_A.pdf` → `Sin incidencias`. Evidence box — k: `Coherencia · Presupuesto · DET-BUD-SUM`; quote: `«La suma de partidas (636 M) difiere del total declarado (654 M): desviación del 2,8 %.»`; tags: `Contrato` `Cronograma` `Presupuesto`. Foot: `Validación · Especialista en compras` · badge `Pending approval`.

**Dimensions (#producto)** — eyebrow: `Auditoría tridimensional`. H2: `Contrato, cronograma y presupuesto, leídos como un solo sistema.` Prose: `La mayoría de los sobrecostes no viven en un documento: viven entre documentos. C2Pro construye una vista cruzada del proyecto y resume su estado con el Coherence Score™ — un índice 0–100 en el que cada hallazgo queda vinculado a su evidencia.` Cards: `Contrato` → `Cláusulas, penalizaciones, hitos y obligaciones, extraídos y trazados.` · `Cronograma` → `Plazos y dependencias, contrastados con lo que el contrato promete.` · `Presupuesto` → `Partidas y totales, cuadrados contra el precio contractual.` Chips label: `Seis dimensiones de análisis` — chips: `Alcance` `Presupuesto` `Calidad` `Técnica` `Legal` `Plazos`.

**Supervision (#supervision)** — eyebrow: `La ventaja de la supervisión humana`. H2: `Velocidad de máquina, criterio de experto.` Prose: `C2Pro no decide por ti. Procesa el volumen documental y eleva los hallazgos a un especialista que los valida antes de que lleguen a tu mesa. Esa supervisión es lo que convierte un análisis rápido en una decisión defendible.` Bullets: `**Hallazgos vinculados a su fuente.** Cada riesgo apunta a documento, página y cláusula.` · `**Revisión humana obligatoria** antes de emitir el informe.` · `**Trazabilidad de extremo a extremo,** de la carga al informe final.`

**How it works (#como-funciona)** — eyebrow: `Cómo funciona`. H2: `Un protocolo de control, no una caja negra.` Lead: `Entradas, control humano y salida. No publicamos la lógica interna del análisis.` Steps: `01 · Cargas la documentación` → `Contrato, cronograma, presupuesto y ofertas.` · `02 · El sistema analiza` → `Cruza documentos y detecta posibles incoherencias.` · `03 · Un experto valida` → `Revisión humana y priorización de hallazgos.` · `04 · Informe accionable` → `Con trazabilidad a la fuente.`

**Origin & limits (#origen)** — eyebrow: `Origen y límites`. H2: `Nace del oficio. Conoce sus límites.` Col 1 — h3: `Parte del ecosistema AI-Gen`; p: `C2Pro no es un software buscando problema: nace de años revisando pliegos, contratos y ofertas a mano, y del trabajo de AI-Gen en inteligencia documental aplicada con gobernanza. Conoce el ecosistema en ai-gen.ai.` (link `ai-gen.ai` → https://www.ai-gen.ai). Col 2 — h3: `Qué no hace`; p: `C2Pro no firma por ti, no sustituye el criterio del comprador y no promete detección perfecta. Señala, evidencia y prioriza; la decisión — y la responsabilidad — siguen siendo humanas. Todo informe pasa revisión experta antes de llegar a tu mesa.`

**Waitlist (#waitlist, navy)** — eyebrow: `Programa piloto en validación`. H2: `Plazas limitadas para organizaciones con alto volumen documental.` Lead: `Estamos incorporando un número limitado de organizaciones para validar C2Pro en casos reales. Acceso prioritario y condiciones de fundador para los primeros pilotos.` Checks: `Onboarding acompañado con especialista` · `Revisión humana experta de cada informe` · `Condiciones de fundador`. Form — title: `Solicitar acceso al piloto`; fields: `Nombre` (ph `Nombre y apellidos`) · `Empresa` (ph `Empresa`) · `Cargo` (ph `Tu cargo`, opcional) · `Email corporativo` (ph `nombre@empresa.com`) · `Volumen documental mensual (opcional)` → `Menos de 20 documentos` / `20–100 documentos` / `Más de 100 documentos`; consent: `Acepto el tratamiento de mis datos conforme a la política de privacidad (RGPD).` (link → https://www.ai-gen.ai/privacidad); submit: `Solicitar acceso`; success: `Gracias. Te contactaremos para coordinar tu acceso al piloto.`; error: `No hemos podido registrar tu solicitud. Inténtalo de nuevo o escríbenos a info@ai-gen.ai.`

**Footer** — tagline: `Inteligencia documental para compras y contratos`. Ecosystem: `Parte del ecosistema AI-Gen · The Intelligence Generation` (→ https://www.ai-gen.ai). Col `Producto`: `Cómo funciona` (#como-funciona) · `Demo ilustrativa` (/demo/coherence-v1) · `Piloto` (#waitlist) · `Iniciar sesión` (/login). Col `AI-Gen`: `Advisory` (https://www.ai-gen.ai/services) · `AI-Gen Lab` (https://www.ai-gen.ai/lab) · `Dossier` (https://www.ai-gen.ai/dossier) · `Nosotros` (https://www.ai-gen.ai/about). Col `Contacto`: `info@ai-gen.ai` (mailto) · `Acceso al piloto` (#waitlist) · `Solicitar diagnóstico` (https://www.ai-gen.ai/services#solicitud). Bottom: `© 2026 C2Pro · Parte de AI-Gen.ai` · `Aviso legal` (https://www.ai-gen.ai/aviso-legal) · `Privacidad (RGPD)` (https://www.ai-gen.ai/privacidad) · `Cookies` (https://www.ai-gen.ai/cookies) · lang switch: `EN` (→ /en).

## EN (`/en`)

**Header** — nav: `Product` (#producto) · `How it works` (#como-funciona) · `Origin` (#origen) · `Pilot` (#waitlist). Auth: `Sign in` (/login) · CTA `Join the pilot` (#waitlist) · signed-in: `Go to workspace` (/dashboard). Brand micro-tag: `an AI-Gen product` (→ https://www.ai-gen.ai).

**Hero** — badge: `Pilot program · in validation`. H1: `Three documents. One single truth.` Lead: `C2Pro cross-checks contract, schedule and budget to surface inconsistencies, deviations and risks — with cited evidence and expert human validation before every decision.` CTA1: `Join the pilot` (#waitlist). CTA2: `View illustrative demo` (/demo/coherence-v1). Trust note: `Priority access and founder terms for the first pilot organizations.`

**Console mock (EN)** — bar title: `C2Pro · Project workspace`; badges: `Illustrative view`, `Human approval queue`. Rows: `Master_contract.pdf` → `Evidence linked` · `Works_schedule.pdf` → `2 deviations` (warning) · `Budget_v3.xlsx` → `2.8 % deviation` (risk) · `Supplier_offer_A.pdf` → `No issues`. Evidence box — k: `Coherence · Budget · DET-BUD-SUM`; quote: `“The sum of line items (636 M) differs from the declared total (654 M): a 2.8 % deviation.”`; tags: `Contract` `Schedule` `Budget`. Foot: `Validation · Procurement specialist` · badge `Pending approval`.

**Dimensions** — eyebrow: `Three-dimensional audit`. H2: `Contract, schedule and budget, read as one system.` Prose: `Most cost overruns don't live in one document: they live between documents. C2Pro builds a cross-document view of your project and summarizes its state with the Coherence Score™ — a 0–100 index where every finding stays linked to its evidence.` Cards: `Contract` → `Clauses, penalties, milestones and obligations — extracted and traced.` · `Schedule` → `Deadlines and dependencies, checked against what the contract promises.` · `Budget` → `Line items and totals, reconciled against the contract price.` Chips label: `Six dimensions of analysis` — chips: `Scope` `Budget` `Quality` `Technical` `Legal` `Time`.

**Supervision** — eyebrow: `The human-oversight advantage`. H2: `Machine speed, expert judgment.` Prose: `C2Pro doesn't decide for you. It processes the document volume and raises findings to a specialist who validates them before they reach your desk. That oversight is what turns a fast analysis into a defensible decision.` Bullets: `**Findings linked to their source.** Every risk points to document, page and clause.` · `**Mandatory human review** before any report is issued.` · `**End-to-end traceability,** from upload to final report.`

**How it works** — eyebrow: `How it works`. H2: `A control protocol, not a black box.` Lead: `Inputs, human control, output. We don't publish the internal analysis logic.` Steps: `01 · Upload the documentation` → `Contract, schedule, budget and offers.` · `02 · The system analyzes` → `Cross-checks documents and flags potential inconsistencies.` · `03 · An expert validates` → `Human review and prioritization of findings.` · `04 · Actionable report` → `With traceability to the source.`

**Origin & limits** — eyebrow: `Origin and limits`. H2: `Born from the trade. Aware of its limits.` Col 1 — h3: `Part of the AI-Gen ecosystem`; p: `C2Pro is not software looking for a problem: it was born from years of reviewing tenders, contracts and offers by hand, and from AI-Gen's work in governed, applied document intelligence. Meet the ecosystem at ai-gen.ai.` (link). Col 2 — h3: `What it does not do`; p: `C2Pro doesn't sign for you, doesn't replace the buyer's judgment, and doesn't promise perfect detection. It flags, evidences and prioritizes; the decision — and the responsibility — remain human. Every report passes expert review before reaching your desk.`

**Waitlist** — eyebrow: `Pilot program in validation`. H2: `Limited seats for organizations with high document volume.` Lead: `We are onboarding a limited number of organizations to validate C2Pro on real cases. Priority access and founder terms for the first pilots.` Checks: `Guided onboarding with a specialist` · `Expert human review of every report` · `Founder terms`. Form — title: `Request pilot access`; fields: `Name` (ph `Full name`) · `Company` (ph `Company`) · `Role` (ph `Your role`, optional) · `Work email` (ph `name@company.com`) · `Monthly document volume (optional)` → `Fewer than 20 documents` / `20–100 documents` / `More than 100 documents`; consent: `I accept the processing of my data under the privacy policy (GDPR).` (link → https://www.ai-gen.ai/privacidad); submit: `Request access`; success: `Thank you. We'll contact you to coordinate your pilot access.`; error: `We couldn't register your request. Try again or write to info@ai-gen.ai.`

**Footer** — tagline: `Document intelligence for procurement and contracts`. Ecosystem: `Part of the AI-Gen ecosystem · The Intelligence Generation`. Col `Product`: `How it works` (#como-funciona) · `Illustrative demo` (/demo/coherence-v1) · `Pilot` (#waitlist) · `Sign in` (/login). Col `AI-Gen`: same four links as ES. Col `Contact`: `info@ai-gen.ai` · `Pilot access` (#waitlist) · `Request a diagnostic` (https://www.ai-gen.ai/services#solicitud). Bottom: `© 2026 C2Pro · Part of AI-Gen.ai` · `Legal notice` · `Privacy (GDPR)` · `Cookies` (same ai-gen.ai URLs) · lang switch: `ES` (→ /).

---

# Follow-ups (registered, out of this epic's scope)

1. **ai-gen.ai repo** (`AI-Gen-AI/2SB`): point the C2Pro waitlist form `action` at `https://www.c2pro.io/api/waitlist` and remove the `site.js` stub interception for that form (CORS on our side is ready). Also consider self-hosting its Google Fonts (RGPD).
2. **Ops (owner):** web deploy env vars (`SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, optional `WAITLIST_ALLOWED_ORIGINS`); run `alembic upgrade head`; after deploy, re-crawl c2pro.io in Search Console.
3. **Later, if EN traffic grows:** full i18n routing (next-intl) — out of scope while the landing is the only bilingual surface.
4. **Optional polish:** custom OG asset from a designer replacing the generated `opengraph-image`; real product screenshots (honestly labeled) replacing the illustrative console.

# Report format (per patch)

Report back: patch number + TASK id, what changed (files), RED evidence (which assertions failed first), GREEN evidence (exact commands + pass counts), lint/typecheck results, any `rg` acceptance greps, backlog files updated, deviations/discoveries (each new discovery must be registered as a task).
