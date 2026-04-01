# Dashboard Route Migration Plan

Date: 2026-04-01
Task: `TASK-1422`
Status: Approved migration plan only. No runtime code changes in this task.

## Goal

Retire the legacy `apps/web/app/dashboard/` tree without breaking current `/dashboard` behavior, while preserving active local edits already made in that tree.

## Current Repo State

The repo does not match the old audit assumption that `app/dashboard/` is already a duplicate of `app/(app)/`.

Current legacy routes still present under `apps/web/app/dashboard/`:

- `apps/web/app/dashboard/page.tsx`
- `apps/web/app/dashboard/projects/[id]/budget/page.tsx`
- `apps/web/app/dashboard/projects/[id]/wbs/page.tsx`

Current `app/(app)/` coverage:

- present: `projects`, `projects/[id]`, `projects/[id]/analysis`, `projects/[id]/coherence`, `projects/[id]/documents`, `projects/[id]/evidence`, `projects/[id]/alerts`
- missing parity: top-level dashboard landing page, `projects/[id]/budget`, `projects/[id]/wbs`

Live dependency risk:

- `AppSidebar` still routes users to `/dashboard`
- multiple Playwright and integration tests still navigate to `/dashboard/...`
- active local edits exist in `apps/web/app/dashboard/page.tsx` and `apps/web/app/dashboard/page.test.tsx`

## Constraints

- Do not delete `apps/web/app/dashboard/` until parity is real and verified.
- Do not discard or overwrite active local dashboard edits.
- Keep `/dashboard` URLs working during the migration window.
- Do not use a big-bang route deletion.

## Migration Strategy

### Phase 1: Parity Build

Create the missing canonical route surface inside `apps/web/app/(app)/`:

- add dashboard landing page behavior equivalent to current `app/dashboard/page.tsx`
- add `projects/[id]/budget`
- add `projects/[id]/wbs`

Rule:

- copy current behavior first
- refactor second
- preserve the active local dashboard service migration already visible in the dirty worktree

### Phase 2: Compatibility Layer

Keep `/dashboard` entry points stable while canonical pages move under `app/(app)/`.

Preferred approach:

- keep `/dashboard` reachable through compatibility routes or redirects
- update navigation and tests incrementally, not all at once

Required verification:

- sidebar navigation
- direct deep links to `/dashboard/projects/[id]/budget`
- direct deep links to `/dashboard/projects/[id]/wbs`
- existing `/dashboard` E2E smoke paths

### Phase 3: Test Migration

Move route expectations away from the legacy tree in controlled batches:

- unit tests for dashboard page behavior
- integration tests that hardcode `/dashboard`
- Playwright specs that deep-link into `/dashboard/...`

Do not remove compatibility until this matrix is green.

### Phase 4: Legacy Tree Retirement

Remove `apps/web/app/dashboard/` only when all of the following are true:

- canonical parity exists under `app/(app)/`
- compatibility behavior is proven
- active local dashboard edits have been carried forward
- route/test references are updated or intentionally preserved through redirect coverage

## Acceptance Criteria

- canonical implementations exist for dashboard landing, budget, and WBS under `app/(app)/`
- current `/dashboard` URLs still work during transition
- active local edits from `app/dashboard/page.tsx` and `page.test.tsx` are preserved
- route and navigation tests cover the migration path
- only then can `TASK-1057` delete the legacy tree

## Execution Tasks

This plan creates three execution tasks:

- `TASK-1423`: implement canonical route parity under `app/(app)/`
- `TASK-1424`: preserve `/dashboard` compatibility and migrate route consumers/tests safely
- `TASK-1425`: retire `app/dashboard/` only after parity, compatibility, and active-edit carry-forward are verified

Additional execution follow-up discovered during `TASK-1424`:

- `TASK-1426`: migrate the remaining Playwright and integration deep-link specs that still hardcode `/dashboard/...` to canonical routes, while keeping explicit compatibility assertions for legacy URLs during the transition
- `TASK-1427`: replace temporary canonical route re-exports with standalone implementations under `app/(app)` so legacy `app/dashboard/` can be removed without breaking canonical pages

## Explicit Non-Goals

- no Clerk/auth changes
- no proxy changes
- no modification of `docs/coherence_engine/IMPLEMENTATION_PLAN_v3.md`
