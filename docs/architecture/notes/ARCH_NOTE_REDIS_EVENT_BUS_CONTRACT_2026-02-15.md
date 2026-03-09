# Architecture Note: Redis Event Bus Contract and Runtime Policy

## Scope

This note freezes the C2Pro Redis Event Bus contract and runtime policy for implementation and review.

## Contract (Frozen)

- `publish(topic, payload, tenant_id, correlation_id)`
- `subscribe(topic, handler, tenant_scope)`
- `unsubscribe(token)`

Contract rules:
- `tenant_id` is mandatory for `publish`.
- `subscribe` is tenant-scoped and must not receive cross-tenant events.
- `unsubscribe` is idempotent (`False` when token does not exist).

## Canonical Channel Naming

- `c2pro.{env}.{tenant_id}.{topic}`

Examples:
- `c2pro.dev.<tenant_id>.documents.uploaded`
- `c2pro.prod.<tenant_id>.coherence.completed`

## Topic Naming Rules

- Topic format: lowercase, dot-separated, bounded-context prefix.
- Examples: `documents.uploaded`, `alerts.created`, `coherence.completed`.
- Wildcard publishing from application code is not allowed.

## Tenant Scoping Rules

- Publish path must include tenant in channel namespace.
- Subscribe path must bind to explicit tenant scope.
- Cross-tenant fan-out is forbidden by default.
- Tenant scope checks are mandatory in adapter tests.

## Fallback Policy (Frozen)

- Redis mandatory for production async cross-module flow.
- In-memory allowed only for explicit local/test mode.

Operational interpretation:
- `prod`: fail fast if Redis-backed Event Bus is unavailable.
- `staging`: fail fast for parity.
- `test`: in-memory only when explicitly selected for unit scope; Redis required for Redis integration suites.
- `dev/local`: Redis preferred; in-memory only by explicit override flag.

## Review Checklist

- Contract signatures and rules are explicit.
- Channel naming convention is enforced.
- Tenant scoping is explicit and testable.
- Environment fallback behavior is deterministic and non-silent.

---

Last Updated: 2026-02-15

Changelog:
- 2026-02-15: Created architecture note to freeze Redis Event Bus contract and runtime policy (Step 1).
