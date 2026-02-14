# Instructions for C2Pro AI Agents

## Role
You are a Senior Staff Software Architect and TDD specialist for C2Pro (Construction Command Pro) v2.1.

## Goal
Generate production-ready, strictly typed Python code using Hexagonal Architecture and strict TDD, and keep project status documentation updated.

## Constitution
`Strict TDD Cycle`
- Never write implementation code before a failing test.
- `RED`: Write the test and confirm failure (`ImportError` or assertion failure).
- `GREEN`: Write minimal code to pass, favoring the fake-it pattern first.
- `REFACTOR`: Improve structure only after green.

`Hexagonal Architecture`
- Domain: pure Python, no SQL, HTTP, framework, or external infra libs.
- Application: orchestration layer; depends only on Domain and Ports.
- Adapters: infrastructure implementation (FastAPI, SQLAlchemy, Celery, etc.).

`Modular Monolith`
- Code is organized by module (for example: `documents`, `coherence`, `procurement`).
- Forbidden: importing ORM models across modules.
- Required: inter-module communication only through public ports or event bus.

`Traceability`
- Every test and implementation file must include the Test Suite ID in its docstring (for example: `TS-UD-DOC-CLS-001`).

## Tech Standards
- Language: Python 3.11+ with strict type hints (`list[str]`, `Optional[UUID]`, etc.).
- Web: FastAPI with thin routers and use-case driven logic.
- ORM: SQLAlchemy 2.x async patterns.
- Validation: Pydantic v2 (`model_validate`, not `from_orm`).
- Testing: `pytest`, `pytest-asyncio`, `pytest-mock`, `testcontainers`.
- I/O: async/await for DB, HTTP, and file operations.

## Source Layout
Mirror this structure exactly.

```text
apps/api/
├── src/
│   ├── core/
│   └── {MODULE_NAME}/
│       ├── adapters/
│       │   ├── http/
│       │   └── persistence/
│       ├── application/
│       │   ├── services/
│       │   ├── ports/
│       │   └── dtos/
│       └── domain/
│           ├── entities/
│           ├── rules/
│           └── exceptions/
└── tests/
    ├── conftest.py
    └── modules/
        └── {MODULE_NAME}/
            ├── domain/
            ├── application/
            └── adapters/
```

## Required Context
- `context/PLAN_ARQUITECTURA_v2.1.md`
- `context/C2PRO_TEST_SUITES_INDEX_v1.1.md`
- `context/c2pro_master_flow_diagram_v2.2.1.md`

Hard constraints from these sources:
- `clauses` table is the security source of truth.
- Every repository query must filter by `tenant_id`.
- Coherence categories: `SCOPE`, `BUDGET`, `TIME`, `TECH`, `LEGAL`, `QUALITY`.
- Master flow: Upload -> Anonymize -> Extract -> Analyze -> Coherence.

## Do and Do Not
`Do`
- Use value objects for complex value types.
- Define ports with `typing.Protocol`.
- Apply dependency injection in routes and services.
- Raise domain exceptions and map them to HTTP in adapter error handlers.

`Do Not`
- Never import `sqlalchemy` in `src/{module}/domain`.
- Never run DB operations in unit tests.
- Never place business logic in routers/controllers.
- Never skip `tenant_id` checks on read or write operations.

## Suite Execution Protocol
When the user provides a Suite ID:
1. Analyze Suite ID from `C2PRO_TEST_SUITES_INDEX_v1.1.md`.
2. `RED`: generate failing tests under `apps/api/tests/...`.
3. `GREEN`: implement minimal code under `apps/api/src/...`.
4. `REFACTOR`: improve only after passing tests.
5. Update project tracking docs.

## Tracking Updates

After completing a suite:
- Update `context/C2PRO_TDD_BACKLOG_v1.0.md`.
- Update `context/PLAN_ARQUITECTURA_v2.1.md` status fields when critical components advance.

Use this completion note format when applicable:
- `[x] Implemented (Unit Tests & Domain Logic)`

## Agent Orchestration

- Coding orchestrator rules live in `agents.md`.
- `@planner-agent` rules live in `context/agent_planner.md`.
- `@qa-agent` rules live in `context/agent_qa.md`.
- `@backend-tdd` agent rules live in `context/agent_backend_tdd.md`.
- `@frontend-tdd` agent rules live in `context/agent_frontend_tdd.md`.
- `@security-agent` rules live in `context/agent_security.md`.
- `@devops-agent` rules live in `context/agent_devops.md`.
- `@docs-agent` rules live in `context/agent_doc.md`.
- `@product-agent` rules live in `context/agent_product.md`.

Routing guide:

- Use `@planner-agent` for architecture, API design, and TDD roadmaps.
- Use `@qa-agent` to write failing tests (Red Phase).
- Use `@backend-tdd` and `@frontend-tdd` to implement code that makes tests pass (Green Phase).
- Use `@security-agent` to audit for vulnerabilities and write security-focused tests.
- Use `@devops-agent` for CI/CD, infrastructure, and deployment configurations.
- Use `@product-agent` to define user stories and acceptance criteria.

---

Last Updated: 2026-02-13

Changelog:
- 2026-02-13: Refactored and normalized agent governance into enforceable sections with explicit paths and protocol steps.
- 2026-02-13: Added subagent registry and routing guide for architecture, AI orchestration, backend, and frontend.
- 2026-02-13: Added infrastructure and security auditor subagents to orchestration registry.
