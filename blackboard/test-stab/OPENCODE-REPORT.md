# TASK-QA-077 + TASK-1480 Report

PR title: `fix(tests): TASK-QA-077 + TASK-1480 — flake stabilization`

## Files Touched

- `apps/api/tests/unit/alerts/domain/test_sla_calculator.py`
- `apps/web/components/features/alerts/AlertReviewCenter.test.tsx`
- `apps/web/components/features/alerts/AlertUndoToast.test.tsx`
- `apps/web/components/features/alerts/alert-undo.test.ts`
- `C2PRO_MASTER_BACKLOG.md`
- `backlogs/QA_QUALITY_ASSURANCE.md`
- `blackboard.json`
- `blackboard/test-stab/OPENCODE-REPORT.md`

## Decisions

- Kept changes test-only. No production component or SLA service code changed.
- Installed `pytest-repeat` in the local Python 3.11 environment because `--count=5` was not available.
- Installed `freezegun` in the local Python 3.11 environment because the existing SLA test module already imported it and collection failed without it.
- Used node_modules junctions to the already-installed main checkout dependencies for local worktree verification after `pnpm install --offline` failed on unavailable `axios@1.15.0`.

## Acceptance Results

### API SLA

Command executed:

```powershell
C:\Users\esus_\AppData\Local\Programs\Python\Python311\python.exe -m pytest tests\unit\alerts\domain\test_sla_calculator.py tests\unit\alerts\domain\test_sla_serialization.py --count=5
```

Result:

```text
365 passed in 3.56s
```

Requested broad command status:

```powershell
C:\Users\esus_\AppData\Local\Programs\Python\Python311\python.exe -m pytest -k sla --count=5
```

Result:

```text
ERROR tests\golden\conftest.py
ModuleNotFoundError: No module named 'golden.evaluators'
```

This occurs before `-k sla` selection because `tests/golden/__init__.py` shadows `src/golden`. It is outside the allowed edit scope for this task.

### Alert Vitest

Command executed five consecutive times:

```powershell
pnpm vitest run components/features/alerts/AlertReviewCenter.test.tsx components/features/alerts/AlertUndoToast.test.tsx components/features/alerts/alert-undo.test.ts
```

Result:

```text
Run 1: Test Files 3 passed; Tests 11 passed
Run 2: Test Files 3 passed; Tests 11 passed
Run 3: Test Files 3 passed; Tests 11 passed
Run 4: Test Files 3 passed; Tests 11 passed
Run 5: Test Files 3 passed; Tests 11 passed
```

Stderr capture:

```text
0 React act() warnings
0 test timeouts
Non-blocking sourcemap warning repeated from @adobe/css-tools missing source files.
```

Requested glob status:

```powershell
pnpm vitest run "__tests__/**/{alerts,evidence}*"
```

Result:

```text
No test files found, exiting with code 1
```

There are no matching `apps/web/__tests__` alert/evidence files on this branch; executable alert tests are under `apps/web/components/features/alerts/`.

### TypeScript

Command executed:

```powershell
pnpm tsc --noEmit
```

Result: passed with no output.

## Open Questions

- Should `tests/golden/__init__.py` be removed or renamed so broad pytest collection can import `src/golden` consistently? This was not changed because it is outside TASK-QA-077 scope.
- Should the unavailable `axios@1.15.0` dependency be corrected in the lock/package metadata? This was not changed because the task forbids dependency changes.
