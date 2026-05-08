# Wave 3 FRT Dispatch Brief - OpenCode

You are executing the Frontend track for `EPIC-COVERAGE-GATES` on C2Pro.

## Context

Repo: `https://github.com/AI-Gen-AI/C2Pro`
Base branch: `main`
Do not push to `main`.
Do not touch backend AI or infrastructure modules.

Tasks:

| Task | Meaning |
| --- | --- |
| `TASK-FRT-132` | Add new coverage-improvement tests. |
| `TASK-FRT-133` | Ensure all coverage-improvement tests pass. |
| `TASK-FRT-134` | Reach at least 70% coverage on targeted frontend area. |
| `TASK-FRT-135` | Prove no regression in existing tests. |

## Setup

```powershell
cd C:\Users\esus_\Documents\AI\ZTWQ\c2pro
git fetch origin
git worktree add .worktrees/coverage-gates-frt-opencode -b coverage-gates/frt-opencode origin/main
cd .worktrees/coverage-gates-frt-opencode
```

If dependencies are missing:

```powershell
pnpm install
```

Codex W6 could not measure frontend coverage because `vitest` was not resolvable from `apps/web`; bootstrap dependencies before starting implementation.

## Files Of Interest

Primary source:

```text
apps/web/components/
apps/web/components/features/
apps/web/lib/api/
apps/web/app/(app)/
apps/web/app/api/
apps/web/src/components/
apps/web/hooks/
apps/web/stores/
```

Primary existing tests:

```text
apps/web/components/**/*.test.tsx
apps/web/lib/api/**/*.test.ts
apps/web/src/**/*.test.tsx
apps/web/__tests__/
apps/web/tests/
```

Likely coverage targets:

```text
apps/web/components/features/alerts/
apps/web/components/features/documents/
apps/web/components/coherence/
apps/web/lib/api/client.ts
apps/web/lib/api/index.ts
apps/web/lib/api/services/
apps/web/app/api/runtime/backend-url/route.ts
```

## Rules

Read first:

```text
blackboard.json
C2PRO_MASTER_BACKLOG.md
backlogs/FRT_FRONTEND.md
docs/testing/C2PRO_TEST_SUITES_INDEX_v1.1.md
```

Project constraints:

```text
Use existing Next.js, React, TypeScript, Vitest patterns.
Do not add unapproved external dependencies.
Do not touch `apps/api/src/core/ai/**`.
Do not touch infrastructure coverage work.
Do not push to main.
Every new test file should include a Test Suite ID in a top-level doc/comment.
```

For this wave, keep reporting in:

```text
blackboard/coverage-gates/WAVE-3-FRT-OpenCode-REPORT.md
```

Do not create standalone frontend analysis docs.

## Strategy

1. Make `pnpm vitest --coverage` executable in `apps/web`.
2. Identify the lowest-coverage frontend files from the coverage report.
3. Add focused Vitest tests around component behavior and API helper contracts.
4. Prefer unit/component tests over Playwright for the coverage gate.
5. Keep Playwright for smoke regression only if already green locally.
6. Add threshold config only to the targeted frontend coverage surface; document any excluded generated files.

## Acceptance Commands

From repo root:

```powershell
pnpm --filter ./apps/web vitest run --coverage
```

If the workspace filter is not configured, run from `apps/web`:

```powershell
pnpm vitest run --coverage
```

Threshold expectation:

```text
lines >= 70
branches >= 70 where practical
functions >= 70
statements >= 70
```

If this repo uses c8/v8 provider configuration, set thresholds in `apps/web/vitest.config.mts` or the existing coverage config. Do not hide production files through broad excludes.

Regression:

```powershell
pnpm lint
pnpm --filter ./apps/web test
```

Optional smoke:

```powershell
pnpm --filter ./apps/web playwright test --project=chromium
```

Only run Playwright if the environment is already bootstrapped.

## Output Expectations

Create:

```text
blackboard/coverage-gates/WAVE-3-FRT-OpenCode-REPORT.md
```

Report must include:

```text
branch name
base commit
task IDs completed
files changed
frontend coverage summary
Vitest command output summary
lint result
known skips or blocked suites
```

Commit:

```text
feat(coverage): EPIC-COVERAGE-GATES Wave 3 - frontend coverage to 70% (TASK-FRT-132..135)
```

PR title:

```text
feat(coverage): EPIC-COVERAGE-GATES Wave 3 - FRT module coverage (TASK-FRT-132..135)
```

Hard limits:

```text
Do not touch AI modules.
Do not touch infrastructure modules.
Do not push to main.
Do not create broad coverage excludes for normal production UI code.
```
