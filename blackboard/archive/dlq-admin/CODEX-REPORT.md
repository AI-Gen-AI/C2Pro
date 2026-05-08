# CODEX REPORT - TASK-BCK-042 - EPIC-DLQ-ADMIN

**Branch**: `dlq-admin/codex`
**PR title**: `feat(admin): TASK-BCK-042 — DLQ admin endpoints`
**Status**: complete
**Date**: 2026-04-27

## Summary

Implemented the admin DLQ surface under a new `src.admin` bounded context. The API now exposes `GET /api/v1/admin/dlq?status=pending` and `POST /api/v1/admin/dlq/{id}/retry`.

The list path is cross-tenant by design for admin review. Retry verifies the DLQ entry exists, then delegates to the existing `DLQService.increment_retry`; no DLQService internals were modified.

## Files touched

- `apps/api/src/admin/application/dtos/dlq.py` — Pydantic v2 response DTOs.
- `apps/api/src/admin/application/use_cases/list_dlq_entries.py` — Protocol port and list use case.
- `apps/api/src/admin/application/use_cases/retry_dlq_entry.py` — retry use case and missing-entry error.
- `apps/api/src/admin/adapters/http/router.py` — HTTP adapter, admin role guard, DLQService adapter.
- `apps/api/src/main.py` — mounted admin DLQ router.
- `apps/api/tests/unit/admin/test_dlq_use_cases.py` — use case tests.
- `apps/api/tests/integration/admin/test_dlq_router.py` — router/auth tests.
- `apps/api/src/core/observability/monitoring.py` — removed duplicate HITL metric definitions that blocked app import/OpenAPI on this main baseline.
- `apps/api/scripts/generate_openapi.py` — fixed repo-root resolution and stdout YAML output for the requested OpenAPI snapshot.
- `C2PRO_MASTER_BACKLOG.md` and `backlogs/BCK_BACKEND.md` — TASK-BCK-042 tracking.

## Acceptance results

RED:

```text
C:\Users\esus_\.pyenv\pyenv-win\versions\3.11.9\python.exe -m pytest tests\unit\admin tests\integration\admin -xvs
ModuleNotFoundError: No module named 'src.admin'
```

GREEN:

```text
cd apps/api
C:\Users\esus_\AppData\Local\Programs\Python\Python311\python.exe -m pytest tests\unit\admin tests\integration\admin -xvs
collected 7 items
tests\unit\admin\test_dlq_use_cases.py ...
tests\integration\admin\test_dlq_router.py ....
7 passed in 0.37s
```

OpenAPI snapshot:

```text
cd apps/api
$env:PYTHONPATH='.'; C:\Users\esus_\AppData\Local\Programs\Python\Python311\python.exe scripts\generate_openapi.py | Select-String -Pattern "/admin/dlq" -Context 0,4
  /api/v1/admin/dlq:
      get:
        tags:
        - Admin
        - DLQ
  /api/v1/admin/dlq/{dlq_id}/retry:
      post:
        tags:
        - Admin
        - DLQ
```

Tenant/admin isolation:

```text
tests/integration/admin/test_dlq_router.py::test_non_admin_token_returns_403_for_list_endpoint PASSED
tests/integration/admin/test_dlq_router.py::test_non_admin_token_returns_403_for_retry_endpoint PASSED
```

Monitoring import regression guard:

```text
cd apps/api
C:\Users\esus_\AppData\Local\Programs\Python\Python311\python.exe -m pytest tests\unit\core\observability\test_hitl_metrics.py tests\unit\core\observability\test_hitl_resume_metrics.py -q
18 passed
```

## Decisions

- Used the existing local JWT user-role path (`get_current_user` + `UserRole.ADMIN`) as the admin scope check. Importing `core.middleware.clerk_auth.require_admin` on this main baseline pulls observability and hit the duplicate Prometheus metric blocker before tests could collect.
- Kept the admin list operation cross-tenant. The router does not accept a tenant id, and the adapter uses a raw session for list-by-status. This matches the brief's admin cross-tenant note.
- Did not modify DLQService internals. The adapter wraps it for `get_by_id` and `increment_retry`.
- Fixed `scripts/generate_openapi.py` because the requested acceptance command otherwise could not import `src` from `apps/api` and did not emit OpenAPI YAML to stdout for grep-style snapshots.

## Open questions

- The older `src.core.dlq.router` remains in the tree but is no longer mounted from `src.main`. It can be deleted in a cleanup task if the team wants to remove the legacy router surface.
- PowerShell in this environment does not provide `grep`, so the report uses the equivalent `Select-String` snapshot. The script now prints YAML to stdout, so `grep -A4 "/admin/dlq"` will work where grep is available.
