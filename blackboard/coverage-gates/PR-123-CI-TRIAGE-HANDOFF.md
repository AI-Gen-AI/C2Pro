# PR #123 CI Triage Handoff

Updated: 2026-05-14T18:19:45+02:00

Branch: `ops-docflow/backlog-reconcile`

PR: https://github.com/AI-Gen-AI/C2Pro/pull/123

## Context

This handoff preserves the current CI repair state for `EPIC-OPS-DOCFLOW` after the PR was opened and multiple CI bootstrap failures were repaired. The branch is aligned with `origin/ops-docflow/backlog-reconcile` and clean as of this note.

## Commits Already Pushed

- `1511c0b` `test(ops): restore schemathesis collection dependency (TASK-OPS-DOCFLOW-015)`
- `19701d9` `test(ops): migrate legacy alert contract imports (TASK-OPS-DOCFLOW-016)`
- `5cb8133` `ci(ops): repair PR gate bootstrap failures`
- `475df37` `ci(frontend): sync pnpm lockfile with main`
- `8f81a91` `ci(agents): skip auditor when anthropic secret is absent`
- `90694f0` `ci(backend): repair remaining PR gates`
- `4cbe395` `ci(ops): repair remaining PR quality gates`
- `efbddbc` `ci(frontend): fix wireframe pnpm bootstrap`

## Current Passing Checks

- Code Auditor Agent
- Generate Coverage Report
- Integration Tests
- Lint
- OpenAPI Drift Check
- S5 Core AI Gates
- Secrets Scan
- Typecheck
- Wireframe TC Coverage
- Test Summary
- Vercel preview/deployment checks

## Current Failing Checks

- Multi-Tenant Isolation Tests
- Playwright E2E
- QA Swarm - Generate Tests
- Real Document Flow, Coverage, Golden Corpus, and Lint
- SonarCloud Code Analysis
- Tests + Drift Check
- Unit Tests (3.11)
- Unit Tests (3.12)

## Confirmed Root Causes

- Unit Tests 3.11/3.12: `apps/api/tests/unit/test_ci_deploy_production_workflow.py` still asserts the old direct GitHub Actions interpolation for `release_commit_sha`. The workflow was changed to pass `inputs.commit_sha` through `COMMIT_SHA` env variables to avoid shell-injection findings.
- Real Document Flow: current CI log shows `alerts.tenant_id` is inserted as null in the real-document API contract path.
- Multi-Tenant Isolation: current CI log shows PostgreSQL cannot find `auth_bootstrap.lookup_user_by_email` and `auth_bootstrap.create_user`.
- Tests + Drift Check: current CI log points at frontend `pnpm test`; local reproduction should be run after the workflow-test fix.

## Local Verification Already Completed

- `python -m pytest tests/unit/adapters/persistence/test_tenant_isolation_repositories.py tests/unit/core/test_privacy_anonymizer_fallback.py tests/unit/modules/hitl/test_resume_workflow_metrics.py::test_checkpoint_not_found_emits_checkpoint_load_error tests/unit/test_dockerfile_runtime.py tests/unit/test_backend_ci_guards.py -q`
- `python -m pytest tests/unit/test_backend_ci_guards.py -q`
- `python -m ruff check` on touched backend/agent files
- `pnpm lint` from `apps/web`
- `pnpm typecheck` from `apps/web`
- `git diff --check`

## Next Actions

1. Patch the stale `deploy-production.yml` unit-test assertion to verify the env-var based dispatch contract.
2. Reproduce and fix the `alerts.tenant_id` null insertion in the real-document flow contract.
3. Inspect and fix the missing `auth_bootstrap` schema/function path in multi-tenant isolation tests.
4. Re-run frontend `pnpm test` and inspect QA Swarm/Playwright logs for their latest post-bootstrap failures.
5. Re-check SonarCloud annotations after the next push because several previous hotspot causes have already been removed.
