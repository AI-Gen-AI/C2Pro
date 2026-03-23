# Auth Bootstrap Fallback Policy

## Purpose

Define how `auth_bootstrap` SQL helper failures are handled per environment while preserving fail-closed tenant isolation.

## Policy

- `AUTH_BOOTSTRAP_FALLBACK_MODE=deny`: never use ORM fallback.
- `AUTH_BOOTSTRAP_FALLBACK_MODE=non_production`: allow ORM fallback only outside production/staging.
- `AUTH_BOOTSTRAP_FALLBACK_MODE=always`: allow ORM fallback in all environments (temporary emergency mode only).

## Environment Defaults

- Development: `non_production`
- Test: `non_production`
- Staging: `deny`
- Production: `deny`

Staging matches production intentionally so pre-release validation catches blocked-fallback behavior before rollout.

## Telemetry Contract

When `AUTH_BOOTSTRAP_EMIT_METRICS=true`, auth bootstrap emits structured events:

- `event=auth_bootstrap_resolution`
- `operation` (`lookup_tenant_by_id`, `lookup_user_by_clerk_user_id`, etc.)
- `resolution_path` (`bootstrap_sql`, `orm_fallback`, `blocked`)
- `fallback_allowed` (bool)
- `fallback_blocked` (bool)
- `error_code`

## Operational Checks

1. In staging/production, verify no `resolution_path=orm_fallback` events during auth smoke tests.
2. If blocked fallback appears unexpectedly, check `AUTH_BOOTSTRAP_FALLBACK_MODE` and migration state for `auth_bootstrap.*` SQL functions.
3. For emergency recovery, temporary `always` mode is allowed only with incident ticket and rollback deadline.

## Rollback Guidance

- Preferred rollback: fix missing SQL function grants/migrations and keep `deny`.
- Last resort: temporarily set fallback mode to `always`, capture incident evidence, and revert to `deny` once database bootstrap path is healthy.
