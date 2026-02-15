# Test Infra Bootstrap Runbook

Date: `2026-02-15`  
Scope: `WS-B Test Infra Bootstrap Standardization`

## Objective
Provide one canonical command to prepare test infrastructure for local and CI execution:
- DB up/reachable
- target DB exists
- migrations at Alembic head
- Redis reachability checked with soft-fail policy (or hard-fail when required)

## Canonical Command
```powershell
python apps/api/scripts/bootstrap_test_infra.py --start-services
```

## Script
- `apps/api/scripts/bootstrap_test_infra.py`

## What It Does
1. Checks DB port reachability (`localhost:5433` by default).
2. If DB is unreachable and `--start-services` is passed:
   - runs `docker compose -f docker-compose.test.yml up -d postgres-test`
   - waits for DB port to become reachable.
3. Ensures target database exists (`c2pro_test` by default).
4. Runs `alembic upgrade head`.
5. Verifies applied `alembic_version` equals expected head revision.
6. Checks Redis reachability (`localhost:6379`):
   - if unreachable and `--start-services` is passed:
     - runs `docker compose -f docker-compose.test.yml up -d redis-test`
     - waits for Redis port to become reachable.
   - default: warning only (soft fail)
   - `--require-redis`: hard fail.

## Fail Policy
- **DB checks:** hard fail
- **DB existence / migrations / head validation:** hard fail
- **Redis reachability:** soft fail unless `--require-redis` is set

## CI Usage
`tests.yml` integration and e2e-security jobs now call:

```yaml
python apps/api/scripts/bootstrap_test_infra.py --start-services --require-redis
```

This enforces deterministic Redis availability for Event Bus integration paths.

For local runs where Redis is optional (soft-fail):

```yaml
python apps/api/scripts/bootstrap_test_infra.py --start-services
```

## Optional Flags
- `--db-host`, `--db-port`
- `--database-url`, `--admin-url`, `--database-name`
- `--wait-seconds`
- `--require-redis`

## Expected Success Output
```text
OK DB port reachable: <host>:<port>
OK DB exists: <name>
OK migrations at head: <revision>
OK Redis reachable ...  OR  WARN Redis not reachable ... Continuing (soft fail policy).
== Test infra bootstrap complete ==
```

---

Last Updated: 2026-02-15

Changelog:
- 2026-02-15: Added deterministic Redis startup via `redis-test` service when `--start-services` is used.
- 2026-02-15: Updated CI guidance to require Redis for integration and e2e-security bootstrap paths.
