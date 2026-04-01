# Session Memo: 2026-03-31

## Scope

Frontend backlog execution for group `2.2 Frontend`, focused on `TASK-021`.

## Confirmed State

- `TASK-020` is complete and marked done in `C2PRO_MASTER_BACKLOG.md`.
- Verification evidence for `TASK-020`:
  - Full frontend suite green from `.vitest-current.json`
  - `452` suites passed
  - `558` tests passed
  - Coverage from `apps/web/coverage/coverage-summary.json`:
    - Lines: `82.17%`
    - Statements: `81.18%`
    - Functions: `82.59%`

## TASK-021 Goal

Add visual regression tests across core frontend pages.

## What Was Implemented

### Files changed

- `apps/web/package.json`
- `apps/web/playwright.config.ts`
- `apps/web/src/tests/e2e/core-pages.visual.spec.ts`

### Current implementation

- Added `npm run test:visual`
- Added Playwright project `visual-regression`
- Added manual-server bypass with `PLAYWRIGHT_SKIP_WEBSERVER=1`
- Added screenshot spec for core demo pages
- Spec hardened to:
  - run serially
  - use longer timeout
  - use reduced motion
  - use explicit screenshot settings

## Current Blocker

`TASK-021` is **not complete** and is **not marked done** in the backlog.

The blocker is not screenshot mismatch. The blocker is local app/dev-server instability under Playwright navigation.

### Latest failure pattern

- Running against manual server on `http://127.0.0.1:3100`
- Command used:

```powershell
$env:PLAYWRIGHT_SKIP_WEBSERVER='1'
$env:PLAYWRIGHT_BASE_URL='http://127.0.0.1:3100'
npm run test:visual -- --update-snapshots
```

- Result:
  - first route aborts with:
    - `page.goto: net::ERR_ABORTED; maybe frame was detached?`
  - latest failing route:
    - `/demo/documents`

### Earlier observations

- Playwright-managed `webServer` startup was unreliable in this workspace
- Health checks showed `socket hang up`
- A stale dev server on `:3000` interfered with managed startup
- Moving Playwright to `:3100` avoided port collision but not route instability
- Error context previously showed `Internal Server Error` for demo pages during some runs

## Important Decisions Already Made

- Do **not** mark `TASK-021` complete until screenshot baselines are actually generated and verified
- Keep the visual lane in place; the implementation is useful and should not be reverted
- Treat the current issue as app/runtime stability, not as a Playwright test-design problem

## Last Known Working Runtime Facts

- Manual `npm run dev -- --hostname 127.0.0.1 --port 3100` starts a listener
- Port check confirmed listener on `127.0.0.1:3100`
- Despite listener presence, Playwright navigation still aborts on demo routes

## Recommended Next Step For Tomorrow

1. Start fresh local server on `:3100`
2. Probe demo routes manually before Playwright:
   - `/demo/documents`
   - `/demo/alerts`
   - `/demo/stakeholders`
   - `/demo/raci`
   - `/demo/evidence`
3. If any route hangs or 500s, debug that route/runtime issue first
4. Once manual route access is stable, rerun:

```powershell
$env:PLAYWRIGHT_SKIP_WEBSERVER='1'
$env:PLAYWRIGHT_BASE_URL='http://127.0.0.1:3100'
npm run test:visual -- --update-snapshots
```

5. Only after green screenshot generation:
   - mark `TASK-021` done in `C2PRO_MASTER_BACKLOG.md`

## If TASK-021 Finally Passes

Expected closeout:

- mark `TASK-021` as `[x]`
- report generated visual baselines
- move to next eligible frontend task after `TASK-021`

