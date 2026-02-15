# I13 Real E2E Infra Runbook

Date: `2026-02-15`  
Owner: `@docs-agent`  
Scope: I13 real E2E bootstrap + execution without service-layer mocks

## Objective
Allow any engineer to run I13 real E2E deterministically from docs only, with:
- live app lifespan
- seeded auth/tenant context
- route contract available at `POST /api/v1/decision-intelligence/execute`
- infra preflight (DB + migrations + Redis)

## Prerequisites
- Python 3.11+
- Docker + Docker Compose available
- Repo root as current working directory
- Dependencies installed:

```powershell
python -m pip install --upgrade pip
pip install -r apps/api/requirements.txt
```

## Canonical Infra Bootstrap
Hard requirement path (recommended for I13 real E2E):

```powershell
python apps/api/scripts/bootstrap_test_infra.py --start-services --require-redis
```

What this guarantees:
1. DB port reachable (`localhost:5433` by default).
2. DB exists (`c2pro_test` by default).
3. Alembic is at head.
4. Redis reachable (`localhost:6379`).

## Test Execution (Local)
Use `PYTHONPATH=apps/api` and run the I13 route + real flow suites:

```powershell
$env:PYTHONPATH='apps/api'
pytest apps/api/tests/e2e/flows/test_i13_decision_intelligence_route_contract.py -q
pytest apps/api/tests/e2e/flows/test_i13_decision_intelligence_real_e2e.py -q
```

Expected outcome:
- route contract suite: `5 passed`
- real I13 E2E suite: `5 passed`
- no `401` auth bootstrap failures
- no `404` route-missing failures

## CI Contract (S6 Gate)
Blocking merge gate:
- Workflow: `.github/workflows/tests.yml`
- Job: `S6 I13 Real E2E (Blocking)` (`i13-real-e2e`)

Scheduled reliability:
- Workflow: `.github/workflows/i13-real-e2e-scheduled.yml`
- Runs nightly and on manual dispatch.

Artifacts produced:
- JUnit XML for I13 suites
- Infra preflight/diagnostics logs (including container status/logs on failure)

## Auth/Tenant Determinism Notes
- Real E2E uses deterministic seeded auth context fixtures.
- Random tenant JWT IDs are intentionally removed from I13 real E2E paths.
- Lifespan startup/shutdown remains enabled in E2E harness.

## Migration Patch Rationale
Patched migration:
- `apps/api/alembic/versions/20260124_0001_add_raci_evidence_text.py`

Rationale:
1. Migration previously failed when `stakeholder_wbs_raci` table was absent in partial/legacy states.
2. Upgrade/downgrade now use table/column existence guards to be idempotent.
3. This avoids bootstrap failures unrelated to I13 business assertions.

## Risk Notes
1. Guarded migration can mask upstream ordering issues if schema drift is severe.
2. Mitigation: keep `assert_head_revision` preflight check and monitor migration logs in CI artifacts.
3. If preflight passes but I13 still fails, treat as functional regression (not infra) and debug route/service behavior.

## Troubleshooting
1. `401 Unauthorized`:
   - verify seeded auth fixtures are loaded in `apps/api/tests/conftest.py`.
   - ensure tests are using seeded headers fixture, not random JWT claims.
2. `404 Not Found` on execute route:
   - verify router registration in `apps/api/src/main.py`.
   - verify endpoint path is exactly `/api/v1/decision-intelligence/execute`.
3. Redis bootstrap failure:
   - run `docker compose -f docker-compose.test.yml ps`.
   - inspect Redis logs in CI artifacts or local `docker compose logs redis-test`.
4. Migration mismatch:
   - rerun bootstrap command and check reported expected/applied Alembic head.

---

Last Updated: 2026-02-15

Changelog:
- 2026-02-15: Added first version of I13 real E2E infra runbook with bootstrap, CI contract, migration rationale, and risk notes.
