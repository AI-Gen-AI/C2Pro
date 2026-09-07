# Test Infra Bootstrap Runbook

Date: `2026-02-15`  
Scope: `WS-B Test Infra Bootstrap Standardization`

## Objective
Provide one canonical command to prepare test infrastructure for local and CI execution:
- DB up/reachable
- canonical target DB exists
- migrations at Alembic head
- Redis reachability checked with soft-fail policy (or hard-fail when required)

## Canonical Command
```powershell
python apps/api/scripts/bootstrap_test_infra.py --start-services
```

## Script
- `apps/api/scripts/bootstrap_test_infra.py`

## Network Boundary
The bootstrap is intentionally restricted to local/CI services. Callers cannot provide a host, PostgreSQL DSN, admin DSN, or database name.

- PostgreSQL host: `127.0.0.1`
- PostgreSQL port: `5433` only
- PostgreSQL database: `c2pro_test`
- PostgreSQL admin database: `postgres`
- Redis host: `127.0.0.1`
- Redis ports: `6380` locally or `6379` in CI, selected only through the explicit `C2PRO_REDIS_TEST_PORT` allowlist

Use purpose-built migration/staging tools instead of this bootstrap script when a non-local database target is required.

## What It Does
1. Checks DB port reachability (`127.0.0.1:5433`).
2. If DB is unreachable and `--start-services` is passed:
   - runs `docker compose -f docker-compose.test.yml up -d postgres-test`
   - waits for DB port to become reachable.
3. Ensures the canonical target database exists (`c2pro_test`).
4. Runs `alembic upgrade head`.
5. Verifies applied `alembic_version` equals expected head revision.
6. Provisions the LangGraph checkpoint schema under the owner/bootstrap boundary.
7. Checks Redis reachability (`127.0.0.1:6380` locally by default, or `127.0.0.1:6379` in CI/service environments):
   - Local Docker Compose maps `redis-test` on host port `6380` to avoid conflicts with development Redis (`6379`).
   - In GitHub Actions / CI, the built-in Redis service runs natively on port `6379`.
   - CI selects `6379` with `C2PRO_REDIS_TEST_PORT=6379`; any other non-allowlisted value fails before a socket call.
   - if unreachable and `--start-services` is passed:
     - runs `docker compose -f docker-compose.test.yml up -d redis-test`
     - waits for Redis port to become reachable.
   - default: warning only (soft fail)
   - `--require-redis`: hard fail.

## Fail Policy
- **DB checks:** hard fail
- **DB existence / migrations / head validation / checkpoint bootstrap:** hard fail
- **Redis reachability:** soft fail unless `--require-redis` is set

## CI Usage
`ci.yml` jobs use the allowlisted CI Redis port:

```yaml
C2PRO_REDIS_TEST_PORT=6379 python apps/api/scripts/bootstrap_test_infra.py --start-services --require-redis
```

This enforces deterministic Redis availability for Event Bus integration paths without exposing a caller-controlled network destination.

For local runs where Redis is optional (soft-fail):

```yaml
python apps/api/scripts/bootstrap_test_infra.py --start-services
```

## Optional Flags
- `--start-services`
- `--wait-seconds`
- `--require-redis`
- `--recreate-db`

## Expected Success Output
```text
OK DB port reachable: 127.0.0.1:5433
OK DB exists: c2pro_test
OK migrations at head: <revision>
OK checkpoint schema is current
OK Redis reachable ...  OR  WARN Redis not reachable ... Continuing (soft fail policy).
== Test infra bootstrap complete ==
```

---

Last Updated: 2026-09-07

Changelog:
- 2026-09-07: Closed the local/CI network target boundary: fixed PostgreSQL target, removed caller-controlled DB/admin URLs and database name, and documented the Redis port allowlist.
- 2026-02-15: Added deterministic Redis startup via `redis-test` service when `--start-services` is used.
- 2026-02-15: Updated CI guidance to require Redis for integration and e2e-security bootstrap paths.
