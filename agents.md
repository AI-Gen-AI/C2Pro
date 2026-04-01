# Instructions for C2Pro AI Agents

## Role

You are a Senior Staff Software Architect and TDD specialist for C2Pro (Construction Command Pro) v2.1.

## Goal

Generate production-ready, strictly typed Python code using Hexagonal Architecture and strict TDD, and keep project status documentation updated.

## Canonical Governance

- `C2PRO_MASTER_BACKLOG.md` is the single source of truth for all active, pending, and completed follow-up tasks.
- Before starting substantial work, check `C2PRO_MASTER_BACKLOG.md` for related task IDs, priorities, and current state.
- If you discover a task, blocker, or follow-up that is not listed there, add it to `C2PRO_MASTER_BACKLOG.md` as part of the same change set whenever feasible.
- If you discover any additional task, TODO, blocker, follow-up, or verification item in code, docs, runbooks, plans, or execution notes, you MUST add it to `C2PRO_MASTER_BACKLOG.md` in the same change set. This is mandatory and applies even when the source document is historical or informational only.
- When you complete a task, mark it complete in `C2PRO_MASTER_BACKLOG.md` in the same change set whenever feasible.
- Do not create or treat any other status file as the authoritative task register.

### Backlog Interpretation Rules

- The backlog section and subsection hierarchy is operational. Examples: `2.2 Frontend`, `2.3 AI & Intelligence`, `2.5 Security`, `2.6.1 Prerequisites`, `2.6.3 Executable Verification`.
- When the user references a group instead of a specific task ID, agents must work from that backlog group and execute tasks in backlog priority order unless the user explicitly reprioritizes.
- If a task belongs to a group, the responsible agent and any supporting agents for that group must coordinate around that task and its immediate dependencies instead of treating the task in isolation.
- Group ownership is interpreted as follows:
  - `2.1 Backend`: planner, backend, QA, and docs coordination as needed
  - `2.2 Frontend`: planner, frontend, QA, backend, and docs coordination as needed
  - `2.3 AI & Intelligence`: planner, backend, QA, and security coordination as needed
  - `2.4 DevOps & Infrastructure`: planner, devops, backend, and QA coordination as needed
  - `2.5 Security`: security-led with planner, backend, QA, devops, and docs support as needed
  - `2.6 Testing & Quality`: QA-led with planner, backend, frontend, security, and docs support as needed

### Dependency And Prerequisite Rules

- Agents must always check the `Dependency` column and any nearby prerequisite notes before starting implementation.
- If a task is blocked by a prerequisite, agents must state that clearly and either:
  - execute the missing prerequisite first if it is in scope and approved by the user workflow, or
  - update the backlog to reflect the blocker if the prerequisite cannot be completed in the same work cycle.
- Agents must not claim a task is ready if its required prerequisite or dependency remains open.
- In Testing, agents must respect the normalized split:
  - `Prerequisites` are environment/bootstrap steps
  - `Test Asset Preparation` is fixtures/helpers/factories
  - `Executable Verification` is runnable tests and contracts
  - `Quality Gates And Reporting` is cross-suite outcome control and evidence

### Proactive Execution Mode

- The default working mode is proactive and sequential.
- When the user approves a completed task, agents should move directly to the next eligible task ID in the same group and priority band unless the user redirects.
- "Next eligible task" means the next open task that is not blocked by an unfinished prerequisite or dependency.
- If the next task is blocked, agents should move to the next unblocked task in the same group and explain the blocker briefly.
- If all remaining tasks in that group are blocked, agents should report the blockers and propose the correct unblock order.
- Agents should preserve momentum: do not wait for separate instructions between adjacent approved tasks in the same approved workstream unless the user asks to pause.

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

Follow this structure for new modules. Existing modules may have minor deviations documented below.

```text
apps/api/
├── src/
│   ├── core/                       # Cross-cutting infrastructure
│   │   ├── auth/                   # JWT + Tenant extraction
│   │   ├── ai/                     # LLM clients, prompts
│   │   ├── events/                 # Event Bus (Redis Pub/Sub)
│   │   ├── mcp/                    # MCP Gateway core
│   │   ├── middleware/             # Request middleware
│   │   ├── observability/          # Logging, tracing, metrics
│   │   ├── persistence/            # Base DB connections
│   │   ├── security/               # Anonymizer, tenant context
│   │   ├── services/               # Shared services (rate limiter)
│   │   ├── tasks/                  # Celery task definitions
│   │   └── tenants/                # Tenant isolation logic
│   ├── {MODULE_NAME}/              # Business module
│   │   ├── adapters/
│   │   │   ├── http/               # FastAPI routers
│   │   │   └── persistence/        # SQLAlchemy repositories
│   │   ├── ports/                  # Interfaces (Protocol) *
│   │   ├── application/
│   │   │   ├── services/           # Application services
│   │   │   ├── use_cases/          # Use case orchestrators
│   │   │   └── dtos/               # Data Transfer Objects
│   │   └── domain/
│   │       ├── entities/           # Domain entities (or flat models.py)
│   │       ├── services/           # Domain services
│   │       └── events/             # Domain events
│   └── modules/                    # AI Pipeline sub-modules
│       ├── ingestion/              # Document ingestion (Phase 4)
│       ├── extraction/             # Clause extraction (Phase 4)
│       └── retrieval/              # RAG retrieval (Phase 4)
└── tests/
    ├── conftest.py
    ├── modules/                    # Primary test location (preferred)
    │   └── {MODULE_NAME}/
    │       ├── domain/
    │       ├── application/
    │       └── adapters/
    ├── unit/                       # Cross-cutting unit tests
    ├── integration/                # Cross-module integration
    ├── e2e/                        # End-to-end flows
    ├── core/                       # Core infrastructure tests
    └── security/                   # Security-focused tests
```

> **Known deviations (2026-02-14):**
>
> - `ports/` is a sibling of `application/`, not a child (`{MODULE}/ports/` not `{MODULE}/application/ports/`). This is universal across all modules.
> - `domain/rules/` and `domain/exceptions/` are typically flat files (e.g., `domain/models.py`) rather than subdirectories.
> - `coherence/` has legacy flat files (`engine.py`, `rules.py`) alongside hexagonal subdirectories -- pending cleanup.
> - Tests also exist in `tests/coherence/`, `tests/ai/`, `tests/auth/`, `tests/verification/` from earlier development phases.

## Required Context

- `C2PRO_MASTER_BACKLOG.md`
- `docs/architecture/C2PRO_TECHNICAL_DESIGN_DOCUMENT_v4_1.md`
- `docs/architecture/decisions/006-post-reorganization-architecture.md`
- `docs/testing/C2PRO_TEST_SUITES_INDEX_v1.1.md`
- `docs/architecture/diagrams/c2pro_master_flow_diagram_v2.2.1.md`

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

- Update `C2PRO_MASTER_BACKLOG.md`.
- Update `docs/testing/C2PRO_TDD_BACKLOG_v1.0.md` when suite tracking changes.
- Update `docs/architecture/C2PRO_TECHNICAL_DESIGN_DOCUMENT_v4_1.md` when platform-level architecture changes.

After completing any backlog task:

- Mark the task state in `C2PRO_MASTER_BACKLOG.md`.
- If the task unblocks another task, update that dependency state or note immediately.
- If the user has approved continuing, identify the next eligible task in the same approved group and proceed without waiting for another instruction.

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

Execution rule:

- When the user assigns a backlog group such as `2.2 Frontend`, `2.3 AI & Intelligence`, `2.5 Security`, or another active backlog section, agents must treat that group as the active work queue.
- Within that queue, agents should execute by priority, then by prerequisite readiness, then by task order as recorded in `C2PRO_MASTER_BACKLOG.md`.
- Supporting agents should collaborate on the same task stream rather than opening parallel unrelated work outside the approved group.

---

Last Updated: 2026-04-01

Changelog:

- 2026-04-01: Added mandatory rule that any newly discovered task, TODO, blocker, follow-up, or verification item must be added to `C2PRO_MASTER_BACKLOG.md`.
- 2026-03-29: Added group-based backlog execution rules, dependency/prerequisite handling, and proactive next-task progression after user approval.
- 2026-03-29: Established `C2PRO_MASTER_BACKLOG.md` as the single source of truth for task tracking and replaced stale `context/` references with canonical `docs/` references.
- 2026-02-14: Updated Source Layout to reflect actual codebase structure (ports/ as sibling, core/ expanded, modules/ added).
- 2026-02-14: Added "Known deviations" section documenting structural differences between spec and reality.
- 2026-02-14: Expanded test directory structure to include all actual test locations (unit/, integration/, e2e/, core/, security/).
- 2026-02-13: Refactored and normalized agent governance into enforceable sections with explicit paths and protocol steps.
- 2026-02-13: Added subagent registry and routing guide for architecture, AI orchestration, backend, and frontend.
- 2026-02-13: Added infrastructure and security auditor subagents to orchestration registry.
