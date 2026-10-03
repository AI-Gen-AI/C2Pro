# C2Pro Web

Current frontend setup and development reference.

> Historical note: this file originally documented the January 2026 Next.js 14 bootstrap. The frontend has since evolved materially; current dependency authority is `apps/web/package.json`.

## Current stack

Verified from `apps/web/package.json` at the 2026-10-01 documentation audit baseline:

- Next.js 16.3.6
- React / React DOM 19.2.7
- TypeScript 5.9.3
- Tailwind CSS 4.3.2
- Clerk `@clerk/nextjs`
- TanStack React Query
- Zustand
- Orval generated API contracts
- Vitest 4
- Playwright 1.61

Toolchain:

- Node >=22 <23
- pnpm >=10
- repository package manager: pnpm 10.25.0

## Documentation

- [Quick start](../../QUICK_START.md)
- [Current TDD](../../docs/architecture/C2PRO_TECHNICAL_DESIGN_DOCUMENT_v4_2.md)
- [Architecture decisions](../../docs/architecture/decisions/README.md)
- [Clerk auth guide](../../docs/runbooks/CLERK_AUTH_DEV_PROD_GUIDE.md)
- [Testing docs](../../docs/testing/README.md)

## Install

From repository root:

```bash
pnpm install --frozen-lockfile
```

Do not use npm/yarn; the monorepo enforces pnpm.

## Environment

Use `apps/web/.env.example` as the current development template.

Authenticated development requires the applicable Clerk development settings. Never place live production secrets in local committed files.

The frontend API target must match the backend environment you are running.

## Run locally

```bash
cd apps/web
pnpm dev
```

Default local URL: `http://localhost:3000`.

## Quality commands

```bash
pnpm typecheck
pnpm lint
pnpm test
pnpm test:all
pnpm test:coverage
pnpm build
pnpm test:e2e
```

Generated API drift check:

```bash
pnpm generate:api:check
```

The consolidated repository CI is authoritative for merge gating.

## Architecture

The web app uses Next.js App Router with:

- authenticated product surfaces;
- Clerk session/auth integration;
- typed backend API contracts;
- React Query for server state;
- Zustand where client state is appropriate;
- Playwright for end-to-end journeys;
- explicit production-acceptance project/config that disables unsafe evidence capture for the protected qualification path.

Do not infer the current route inventory from the original January bootstrap document. Source and tests are authoritative.

## Coherence and trust UI semantics

The UI must preserve backend truth semantics:

- null/insufficient-evidence score is not rendered as zero;
- trusted score is canonical;
- projected/pending-review score is visibly hypothetical;
- pending/rejected candidate state must not appear as accepted canonical project state;
- evidence locators must not fabricate page/bbox precision.

See ADR-009 and ADR-026.

## Demo mode

Where `NEXT_PUBLIC_APP_MODE=demo` is supported, demo mode is a product demonstration mechanism, not a production-validation path.

Never reuse demo/mock shortcuts for production qualification.

## Production qualification

The protected #715 Playwright path lives under `src/tests/e2e/prod-acceptance/`.

It has a stricter security contract than ordinary E2E:

- canonical production origin before credentials;
- dedicated synthetic production identity/tenant;
- exact provider/runtime binding;
- no arbitrary screenshots/video/trace leakage;
- fail closed before mutation when preflight is invalid.

Operator procedure:

`docs/product/production-qualification-operator-runbook.md`

## Dependency/version policy

Do not copy version tables from this README into architecture decisions.

When versions change, `package.json` / lockfile remain authoritative; update this short stack summary only when it materially helps onboarding.
