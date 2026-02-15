# Redis Event Bus Implementation Plan

## 1. Objective

Implement a Redis-backed Event Bus aligned with C2Pro Hexagonal Architecture and modular monolith constraints, replacing in-memory-only behavior for cross-module async event flows.

## 2. Current State Summary

- Redis is already operational in the platform for:
  - Celery broker/backend.
  - Cache adapter.
  - Rate limiting.
- Event publishing to Redis exists via `EventPublisher`.
- Core Event Bus implementation in `apps/api/src/core/events/event_bus.py` remains in-memory and does not represent the intended Redis Pub/Sub runtime behavior.

## 3. Architectural Alignment

- Target architecture requires Event Bus via Redis Pub/Sub (`context/PLAN_ARQUITECTURA_v2.1.md`).
- Cross-module communication must be async through Event Bus or explicit ports.
- Tenant isolation remains mandatory: event channels and payload handling must preserve tenant boundaries.

## 4. Execution Roadmap (Delegation Plan)

### Step 1: Contract and Runtime Policy (`@planner-agent`)

- Freeze Event Bus contract for implementation:
  - `publish(topic, payload, tenant_id, correlation_id)`
  - `subscribe(topic, handler, tenant scope)`
  - `unsubscribe(token)`
- Define canonical channel naming:
  - `c2pro.{env}.{tenant_id}.{topic}`
- Define fallback policy:
  - Redis mandatory for production async cross-module flow.
  - In-memory allowed only for explicit local/test mode.

Definition of Done:

- Contract and policy documented as architecture note.
- Topic naming and tenant scoping rules are explicit and reviewable.

### Step 2: RED Phase Tests (`@qa-agent`)

- Create failing tests for Redis-backed event bus:
  - publish/subscribe through Redis channel.
  - tenant channel isolation.
  - reconnect/recover behavior.
  - serialization and malformed payload handling.
  - Redis outage behavior per policy.
- Ensure Suite ID docstrings are present in test files.

Definition of Done:

- Tests fail before implementation.
- Unit tests avoid DB access.

### Step 3: GREEN Phase Implementation (`@backend-tdd`)

- Implement `RedisEventBusAdapter` under `apps/api/src/core/events/`.
- Keep Redis code in infra/core adapter boundary only.
- Wire adapter through dependency injection in startup/bootstrap.
- Maintain compatibility with current `EventPublisher` usage.

Definition of Done:

- New Redis Event Bus tests pass.
- Existing event and integration suites remain green.
- No synchronous cross-module DB coupling is introduced.

### Step 4: Security and Reliability Validation (`@security-agent`)

- Add tests for:
  - tenant boundary enforcement at event transport level.
  - sensitive data log redaction in failures.
  - duplicate/replay handling strategy (idempotency/correlation metadata).

Definition of Done:

- Security tests pass.
- Telemetry contains safe metadata only.

### Step 5: Infrastructure and Documentation Closure (`@devops-agent`, `@docs-agent`)

- DevOps:
  - validate Redis readiness checks for local/CI bootstrap.
  - ensure deterministic integration-test Redis startup.
- Docs:
  - update event catalog documentation.
  - update progress tracking docs on completion:
    - `context/C2PRO_TDD_BACKLOG_v1.0.md`
    - `context/PLAN_ARQUITECTURA_v2.1.md`

Definition of Done:

- Runbook includes local and CI execution paths.
- Tracking docs reflect completion status and scope.

## 5. Increment Order (TDD)

1. Redis publish/subscribe happy path.
2. Tenant channel isolation.
3. Redis unavailable behavior (policy-driven).
4. Reconnect and retry semantics.
5. Observability and documentation finalization.

## 6. Risks and Controls

- Risk: Mixed in-memory and Redis paths diverge behavior.
  - Control: explicit environment policy and tests for each mode.
- Risk: Tenant leakage via channel naming or payload fields.
  - Control: tenant-scoped channel contract + security tests.
- Risk: Flaky integration tests due to service readiness.
  - Control: bootstrap readiness gates and deterministic startup sequence.

## 7. Completion Status

- [x] Step 1 - Contract and runtime policy documented.
- [x] Step 2 - RED tests created and verified failing before implementation.
- [x] Step 3 - GREEN implementation completed (`RedisEventBusAdapter` + DI wiring).
- [x] Step 4 - Security and reliability validation completed.
- [x] Step 5 - Infrastructure and documentation closure completed.

---

Last Updated: 2026-02-15

Changelog:

- 2026-02-15: Created initial Redis Event Bus implementation plan from planner handoff.
- 2026-02-15: Added completion status for Steps 1-5 and marked Step 5 as closed.
