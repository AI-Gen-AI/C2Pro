# Wave 3 INF Dispatch Brief - Gemini 2.5 Pro

You are executing the Infrastructure track for `EPIC-COVERAGE-GATES` on C2Pro.

## Context

Repo: `https://github.com/AI-Gen-AI/C2Pro`
Base branch: `main`
Do not push to `main`.
Do not touch `apps/api/src/core/ai/**` or `apps/api/tests/unit/core/ai/**`.

Tasks:

| Task | Meaning |
| --- | --- |
| `TASK-INF-016` | Add new coverage-improvement tests. |
| `TASK-INF-017` | Ensure all coverage-improvement tests pass. |
| `TASK-INF-018` | Reach at least 70% coverage on targeted infrastructure area. |
| `TASK-INF-019` | Prove no regression in existing tests. |

## Setup

```powershell
cd C:\Users\esus_\Documents\AI\ZTWQ\c2pro
git fetch origin
git worktree add .worktrees/coverage-gates-inf-gemini -b coverage-gates/inf-gemini origin/main
cd .worktrees/coverage-gates-inf-gemini
```

If Git reports dubious ownership, use per-command:

```powershell
git -c safe.directory=C:/Users/esus_/Documents/AI/ZTWQ/c2pro/.worktrees/coverage-gates-inf-gemini status --short
```

## Files Of Interest

Primary source:

```text
apps/api/src/core/observability/
apps/api/src/core/resilience/
apps/api/src/core/security/
apps/api/src/core/middleware/
apps/api/src/core/tasks/
apps/api/src/core/tenants/
```

Primary tests:

```text
apps/api/tests/unit/core/observability/
apps/api/tests/unit/core/resilience/
apps/api/tests/unit/core/security/
apps/api/tests/unit/test_celery_queue_config.py
apps/api/tests/core/
apps/api/tests/security/
```

Known RED item from Codex W6 measurement:

```text
tests/unit/core/observability/test_hitl_resume_metrics.py::test_checkpoint_load_errors_are_recorded
expected labels {"reason": "..."} but implementation emits {"error_type": "..."}.
Resolve the contract drift before enforcing coverage.
```

## Rules

Read first:

```text
blackboard.json
C2PRO_MASTER_BACKLOG.md
backlogs/INF_INFRASTRUCTURE.md
docs/testing/C2PRO_TEST_SUITES_INDEX_v1.1.md
```

Project constraints:

```text
Never run DB operations in unit tests.
Every repository query must filter by tenant_id.
Do not create a new backend module without approval.
Do not add external dependencies without approval.
Every new test/implementation docstring must include a Test Suite ID.
Do not edit AI modules.
Do not push to main.
```

For this wave, keep task tracking in:

```text
blackboard/coverage-gates/WAVE-3-INF-Gemini-REPORT.md
```

Do not create standalone planning docs elsewhere.

## Strategy

1. Fix the HITL metric label contract drift.
2. Add unit tests for low-coverage infrastructure files, prioritizing:
   - `src/core/resilience/decorators.py`
   - `src/core/security/secret_channel.py`
   - `src/core/security/audit_trail.py`
   - `src/core/security/anonymizer.py`
   - `src/core/observability/coherence_tracing.py`
   - `src/core/observability/coherence_span_schema.py`
   - `src/core/observability/router.py`
   - `src/core/observability/service.py`
3. Use integration tests only for DB/session behavior.
4. Add or adjust coverage configuration only for non-production examples/generated/static files, and document every omit.

## Acceptance Commands

Run from `apps/api`:

```powershell
$env:C2PRO_AI_MOCK='1'
C:\Users\esus_\AppData\Local\Programs\Python\Python311\python.exe -m pytest tests/unit/core/observability tests/unit/core/resilience tests/unit/core/security --cov=src/core/observability --cov=src/core/resilience --cov=src/core/security --cov-report=term-missing --cov-fail-under=70 -q
```

Optional targeted task gate:

```powershell
$env:C2PRO_AI_MOCK='1'
C:\Users\esus_\AppData\Local\Programs\Python\Python311\python.exe -m pytest tests/unit/test_celery_queue_config.py tests/unit/core/observability tests/unit/core/resilience tests/unit/core/security -q
```

Regression:

```powershell
$env:C2PRO_AI_MOCK='1'
C:\Users\esus_\AppData\Local\Programs\Python\Python311\python.exe -m pytest tests/ -x -q
```

Root lint:

```powershell
cd C:\Users\esus_\Documents\AI\ZTWQ\c2pro\.worktrees\coverage-gates-inf-gemini
pnpm lint
```

## Output Expectations

Create:

```text
blackboard/coverage-gates/WAVE-3-INF-Gemini-REPORT.md
```

Report must include:

```text
branch name
base commit
task IDs completed
files changed
coverage command output summary
full regression/lint result
known skips or blocked tests
```

Commit:

```text
feat(coverage): EPIC-COVERAGE-GATES Wave 3 - infrastructure coverage to 70% (TASK-INF-016..019)
```

PR title:

```text
feat(coverage): EPIC-COVERAGE-GATES Wave 3 - INF module coverage (TASK-INF-016..019)
```

Hard limits:

```text
Do not touch AI modules.
Do not touch frontend modules.
Do not push to main.
Do not broaden coverage omits to hide production infrastructure code.
```
