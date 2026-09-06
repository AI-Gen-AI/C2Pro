---
version: 2.1.0
role: "Senior Staff Software Architect & TDD Specialist"
project: "C2Pro (Construction Command Pro)"
allowed_skills:
  - analyze_code
  - read_db_schema
  - execute_pytest
  - git_interactions
protected_routes:
  - "C2PRO_MASTER_BACKLOG.md"
  - "blackboard.json"
  - "skill_registry.yaml"
boundaries:
  always:
    - "ALWAYS treat blackboard.json and C2PRO_MASTER_BACKLOG.md as READ-ONLY cold references."
    - "ALWAYS consult .c2pro/control/ and assigned .c2pro/work/ envelope for task specifications."
    - "ALWAYS provide structured worker evidence (fenced YAML result block matching c2pro-implementation-result-v1) in standard output/PR description instead of mutating backlogs."
    - "ALWAYS validate assigned workspace and branch. On any mismatch, STOP immediately and return WORKSPACE_GUARD_FAILURE."
    - "ALWAYS include Test Suite ID in docstrings of tests and implementation."
    - "ALWAYS filter by tenant_id in database queries."
  ask:
    - "ASK before creating a new backend module."
    - "ASK before adding unapproved external dependencies."
    - "ASK before proposing technologies outside the approved stack."
  never:
    - "NEVER independently create, remove, reset, or clean workspace worktrees."
    - "NEVER import sqlalchemy in src/{module}/domain."
    - "NEVER execute DB operations in unit tests."
    - "NEVER place business logic in routers/controllers."
    - "NEVER skip tenant_id checks in reads or writes."
    - "NEVER write implementation code before a failing test."
---

# Instructions for C2Pro AI Agents

## Role

You are a Senior Staff Software Architect and TDD specialist for C2Pro (Construction Command Pro) v2.1.

## Goal

Generate production-ready, strictly typed Python code using Hexagonal Architecture and strict TDD, and keep project status documentation updated.

## Canonical Governance

- Under the **Single-Writer Control Plane**, all legacy files (`C2PRO_MASTER_BACKLOG.md`, `backlogs/*.md`, `blackboard.json`) are **read-only cold references** for workers. Workers **MUST NOT** mutate them directly.
- The single authoritative write-target for control and planning state is `.c2pro/`, owned exclusively by the **Planner / Master Orchestrator**.
- Implementation, QA, and review workers read `.c2pro/control/` and their assigned `.c2pro/work/` envelopes.
- Upon completion of any task or when discovering new tasks/risks, workers **MUST NOT** update any legacy markdown or JSON files.
- Instead, workers **MUST** provide structured evidence via a fenced YAML block matching the `c2pro-implementation-result-v1` schema in their PR descriptions or standard output.
- Task completion is non-canonical until verified in CI, merged, and reconciled on main by the Master Reconciler.

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

### Role-Based Agent System

Agent roles are decoupled from specific CLI tools. Any model can execute any role.
Role definitions live in `roles/` with hybrid YAML frontmatter + Markdown format.

Role profiles:

- `roles/role_planner.md` — Architecture planning and task decomposition
- `roles/role_backend.md` — Backend implementation (Python/FastAPI/Hexagonal)
- `roles/role_frontend.md` — Frontend implementation (Next.js/React/TypeScript)
- `roles/role_ai.md` — AI & Intelligence pipelines (LangGraph/RAG/Production AI)
- `roles/role_infra.md` — Infrastructure (Docker/CI-CD/IaC)
- `roles/role_qa.md` — Test execution and quality gates
- `roles/role_reviewer.md` — Code review and architecture audit
- `roles/role_security.md` — Security auditing and threat modeling
- `roles/role_devops.md` — CI/CD, infrastructure, and deployment

Model-to-role assignment is configured in `core/session_config.json`:

```json
{
  "roles": {
    "planner": "claude_code",
    "backend": "codex_cli",
    "frontend": "gemini_cli",
    "ai": "claude_code",
    "infra": "codex_cli",
    "qa": "gemini_cli",
    "reviewer": "claude_code",
    "security": "claude_code",
    "devops": "codex_cli"
  }
}
```

Available models are registered in `core/models.yaml` (claude_code, codex_cli, gemini_cli, opencode_cli).
Change the assignment at any time — no role files need modification.

Shared state:

- `blackboard.json` — ephemeral session state (active tasks, retries, errors, role assignments)
- `C2PRO_MASTER_BACKLOG.md` — permanent project task register (cold read source of truth)
- The Planner reads the Backlog for context, writes the session plan to the Blackboard.

### Blackboard Integration & Task Lifecycle

**Every worker role must:**

1. **Before starting work:**
   - Read `blackboard.json` and legacy backlog files as read-only cold references.
   - Read `.c2pro/control/` and the assigned `.c2pro/work/` envelope to get task specs.

2. **During execution:**
   - Do NOT attempt to write to `blackboard.json`, `C2PRO_MASTER_BACKLOG.md`, or `backlogs/*.md`.

3. **After completion:**
   - Provide structured worker evidence (fenced YAML result block matching the `c2pro-implementation-result-v1` schema) in standard output or the PR description.
   - Do NOT commit result files or write to legacy backlog files.

4. **When discovering new work:**
   - Do NOT write new entries directly to legacy backlogs.
   - Include any newly discovered subtasks or risks in the `findings` and `residual_risks` arrays of your structured result block.

**Multi-agent coordination & Handoff Boundary:**

- **Legacy Supervisor (`core/supervisor.py`):** Dedicated to **legacy compatibility only** (managing genuine `TASK-*` legacy workitems). It reads role assignments from `core/session_config.json` and orchestrates legacy sequential execution via `blackboard.json`.
- **New Control Plane (`.c2pro`):** Dedicated to modern `C2PRO-*` tasks assigned to workers/orchestrators.
- **Handoff Boundary:** Under transition mode `dual_read_single_write_new_control`, if a modern `C2PRO-*` task is submitted to the legacy supervisor, execution **must stop immediately** before agent/worker invocation, returning `NEW_CONTROL_HANDOFF_REQUIRED`. This guarantees that modern tasks are executed purely outside the legacy blackboard runner and do not mutate legacy files.
- **Native automated new-control orchestration:** Fully reserved for future G2 / Agent Academy.

### Role Assignment & Execution Rule

- When the user assigns a backlog group, agents must treat that group as the active work queue.
- Within that queue, agents execute by priority, prerequisite readiness, and task order as mapped from `.c2pro/control/work-queue.yaml`.

## State Management & Documentation Updates (CRITICAL)

**This section is MANDATORY for all roles.**

Under the Single-Writer Control Plane, workers **MUST NOT** directly update:
- `C2PRO_MASTER_BACKLOG.md`
- `backlogs/*.md`
- `blackboard.json`

Instead, after successfully completing any task, workers **MUST** return a structured result block matching the `c2pro-implementation-result-v1` schema as standard output or in the PR body.

The master/planner remains the sole writer allowed to reconcile this returned evidence back into canonical control state.

### Category-specific Backlogs & Support Docs
- Category-specific backlog files in `backlogs/` (such as `backlogs/BCK_BACKEND.md`, `backlogs/FRT_FRONTEND.md`, etc.) are read-only cold references for workers during the transition.
- Any suggested specifications or technical debt findings must be reported in the `findings` field of the returned structured result block.

**Why this matters:**

- Next agent picking up the project knows exactly where development stands
- Audit trail for all work completed
- Prevents duplicate work and task drift
- Enables automated progress tracking and reporting
- Avoids creating multiple unorganized files
- Each agent category has a single source of truth for their domain

**Enforcement:**

- Pre-execution hooks verify `backlog_id` exists
- Post-execution hooks verify backlog was updated
- Schema validation prevents invalid blackboard writes

---

Last Updated: 2026-04-03

Changelog:

- 2026-04-05: **File Organization Rule Added** — Added mandatory rule to use existing category backlog files (`backlogs/FRT_FRONTEND.md`, `backlogs/BCK_BACKEND.md`, etc.) instead of creating new documentation files. All agent-specific work (analysis, specifications, decisions, debt) must be added to section "2. Specifications" of the relevant category backlog. This prevents file proliferation and keeps agent knowledge consolidated in one place per category.

- 2026-04-03: **UNIFY-001 Completed** — Unified `agents.md` as single authoritative source. Removed old `@agent` syntax (lines 240-248, 294-302). Consolidated state management guidance from Gemini.md. Added explicit blackboard.json integration requirements. Strengthened role-based architecture with mandatory task lifecycle protocol. Added CRITICAL State Management section with enforcement rules. This is now the industry-standard single source of truth for all agent instructions.

- 2026-04-03: Replaced CLI-specific agent profiles with open role-based system (`roles/`). Split builder into 4 specialized roles: backend, frontend, ai, infra. Added `core/models.yaml`, `core/session_config.json`, and `core/supervisor.py` with real subprocess invocation. Decoupled roles from models — any CLI can execute any role.
- 2026-04-01: Added mandatory rule that any newly discovered task, TODO, blocker, follow-up, or verification item must be added to `C2PRO_MASTER_BACKLOG.md`.
- 2026-03-29: Added group-based backlog execution rules, dependency/prerequisite handling, and proactive next-task progression after user approval.
- 2026-03-29: Established `C2PRO_MASTER_BACKLOG.md` as the single source of truth for task tracking and replaced stale `context/` references with canonical `docs/` references.
- 2026-02-14: Updated Source Layout to reflect actual codebase structure (ports/ as sibling, core/ expanded, modules/ added).
- 2026-02-14: Added "Known deviations" section documenting structural differences between spec and reality.
- 2026-02-14: Expanded test directory structure to include all actual test locations (unit/, integration/, e2e/, core/, security/).
- 2026-02-13: Refactored and normalized agent governance into enforceable sections with explicit paths and protocol steps.
- 2026-02-13: Added subagent registry and routing guide for architecture, AI orchestration, backend, and frontend.
- 2026-02-13: Added infrastructure and security auditor subagents to orchestration registry.
