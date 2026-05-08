# Wave 3 FRT Coverage Recovery Report

**Date**: 2026-05-07
**Branch**: `coverage-gates/ai-codex`
**Base commit**: `be68867b` (`origin/main`, after PR #108 and TASK-BCK-040 lint cleanup)
**Tasks**: `TASK-FRT-132`, `TASK-FRT-133`, `TASK-FRT-134`, `TASK-FRT-135`

## Summary

Salvaged the useful intent from the stale `coverage-gates/frt-opencode` handoff without taking its package manager workarounds, then rebased onto current `origin/main`.

Kept:

- Runtime backend URL normalization coverage.
- API highlight/helper coverage intent.
- Wave 3 frontend coverage report path.

Discarded:

- `apps/web/package.json` and `pnpm-lock.yaml` edits from the stale worktree.
- `vitest.config.mts` import change from `vitest/config` to `vitest`.
- Tests that duplicated production helper implementations inside test files.

## Files Changed

- `apps/web/app/api/runtime/backend-url/route.ts`
- `apps/web/app/api/runtime/backend-url/backend-url.test.ts`
- `apps/web/lib/api/index.ts`
- `apps/web/lib/api/index.test.ts`
- `blackboard/coverage-gates/WAVE-3-FRT-OpenCode-REPORT.md`
- `backlogs/FRT_FRONTEND.md`
- `C2PRO_MASTER_BACKLOG.md`
- `blackboard.json`

## Coverage Summary

Command:

```powershell
pnpm --filter c2pro-web exec vitest run app/api/runtime/backend-url/backend-url.test.ts lib/api/index.test.ts --coverage --coverage.include=app/api/runtime/backend-url/route.ts --coverage.include=lib/api/index.ts --config vitest.config.mts --configLoader native
```

Result:

```text
Test Files  2 passed (2)
Tests       15 passed (15)

All files: statements 80.20%, branches 70.66%, functions 93.75%, lines 79.56%
app/api/runtime/backend-url/route.ts: 100% statements, 100% branches, 100% functions, 100% lines
lib/api/index.ts: 77.38% statements, 66.15% branches, 93.10% functions, 76.54% lines
```

Branch coverage on `lib/api/index.ts` is below 70 because upload error branches and optional API wrapper branches are intentionally not all exercised in this focused slice. Overall targeted branch coverage is 70.66%.

## Regression Summary

Targeted tests:

```text
pnpm --filter c2pro-web exec vitest run app/api/runtime/backend-url/backend-url.test.ts lib/api/index.test.ts --config vitest.config.mts --configLoader native
Test Files 2 passed (2), Tests 15 passed (15)
```

Frontend integration regression:

```text
pnpm --filter c2pro-web test
Test Files 50 passed (50), Tests 124 passed (124)
```

Lint:

```text
pnpm --filter c2pro-web run lint
passed
```

## Known Notes

- Local non-escalated Vitest runs still hit Windows `spawn EPERM` in Vite/esbuild process spawning. Running the same commands outside the sandbox succeeds.
- Coverage output prints a sourcemap warning for `@adobe/css-tools`; it does not fail tests or coverage.
- No AI modules or infrastructure modules were modified.
