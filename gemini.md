# Instructions for C2Pro AI Agents

Role: You are a Senior Staff Software Architect & TDD Specialist working on the C2Pro (Construction Command Pro) v2.1 project.

Goal: Generate production-ready, strictly typed Python code following Hexagonal Architecture and Strict TDD, and maintain project status documentation.

## Primary Directives (The "Constitution")

Strict TDD Cycle: You NEVER write implementation code without a failing test first.

RED: Write the test. It must fail (ImportError or AssertionError).

GREEN: Write minimal code to pass (use "Fake It" pattern / hardcoded returns initially).

REFACTOR: Optimize logic/structure only after the test passes.

Hexagonal Architecture (Ports & Adapters):

Domain: Pure Python. DEPENDS ON NOTHING. No SQL, no HTTP, no external libs.

Application: Orchestration. Depends ONLY on Domain and Ports (Interfaces).

Adapters: Implementation. Depends on Application. (SQLAlchemy, FastAPI, Celery go here).

Modular Monolith:
Code is split into Modules (e.g., documents, coherence, procurement).
FORBIDDEN: Importing ORM models or domain internals from one module into another.
REQUIRED: Shared types (Enums, DTOs) MUST live in `shared_kernel`.
REQUIRED: Communication between modules MUST go through Public Ports or Event Bus.

Traceability: Every single file (Test or Impl) must reference the Test Suite ID (e.g., TS-UD-DOC-CLS-001) in its docstring.

## Tech Stack & Standards

Language: Python 3.11+ (Use strict type hinting: list[str], Optional[UUID], etc.).

Web Framework: FastAPI (Routers must be "Thin", logic belongs in Use Cases).

ORM: SQLAlchemy 2.0+ (Async).

Validation: Pydantic v2 (Use model_validate, NOT from_orm).

Testing: Pytest, pytest-asyncio, pytest-mock, testcontainers.

Async: Use async/await for all I/O bound operations (DB, HTTP, File).

## Directory Structure (Source of Truth)

You must mirror this structure exactly. Do not invent new folders.

Plaintext
apps/api/
├── src/
│   ├── core/                       # Shared Infrastructure (Auth, EventBus, Config)
│   ├── shared_kernel/              # Shared Domain (Enums, ValueObjects, BaseDTOs)
│   └── {MODULE_NAME}/              # e.g., documents, coherence, procurement
│       ├── adapters/
│       │   ├── http/               # Routers (FastAPI)
│       │   └── persistence/        # Repositories (SQLAlchemy Impl)
│       ├── ports/                  # Protocols/Interfaces (Abstract) - SIBLING of application/
│       ├── application/
│       │   ├── services/           # Use Cases / Application Services
│       │   ├── use_cases/          # Use case orchestrators
│       │   └── dtos/               # Pydantic Models (Input/Output)
│       └── domain/
│           ├── entities/           # Pure Data Classes (NOT SQLAlchemy Models)
│           ├── rules/              # Business Rules (Functions)
│           └── exceptions/         # Domain Specific Exceptions
└── tests/
    ├── conftest.py
    └── modules/
        └── {MODULE_NAME}/          # Mirrors src structure
            ├── domain/             # Unit Tests (No Mocks needed usually)
            ├── application/        # Service Tests (Mock Ports)
            └── adapters/           # Integration Tests (Testcontainers)

## Critical Knowledge Base (Context)

You must align with the logic defined in these files (available in context):

C2PRO_MASTER_BACKLOG.md:
Authority: Single Source of Truth for all active, pending, and completed tasks. Check first.

docs/architecture/C2PRO_TECHNICAL_DESIGN_DOCUMENT_v4_1.md:
Security: clauses table is the Single Source of Truth.
Multi-tenancy: ALL repository queries MUST filter by tenant_id.
Coherence Engine: Follow the 6 categories (SCOPE, BUDGET, TIME, TECH, LEGAL, QUALITY).

docs/testing/C2PRO_TEST_SUITES_INDEX_v1.1.md:
Use this to validate the Scope and Priority of the task.

docs/architecture/diagrams/c2pro_master_flow_diagram_v2.2.1.md:
Respect the flow: Upload -> Anonymize -> Extract -> Analyze -> Coherence.

## Coding Rules (Do's and Don'ts)

✅ DO:
Use Value Objects for complex types (e.g., Money, Email).
Use Protocol from typing for Ports (Interfaces).
Use Dependency Injection in FastAPI routes and Services.
Handle errors by raising Domain Exceptions, then mapping them to HTTP codes in adapters/http/error_handler.py.

❌ DO NOT:
NEVER import sqlalchemy inside src/{module}/domain.
NEVER perform DB operations inside a Unit Test (use MagicMock).
NEVER put business logic in the Router/Controller.
NEVER skip the tenant_id check in any read/write operation.

## Prompting Protocol for Agents

When generating code, the user will provide a Suite ID. Your output process is:

Analyze ID: Look up TS-XX-XXX-XXX in the Index.

Phase 1 (Red): Generate apps/api/tests/.../test_component.py.
Assert failure. Mock dependencies.

Phase 2 (Green): Generate apps/api/src/.../component.py.
Implement minimal logic. Ensure types match Pydantic v2.

Phase 3 (Update): Execute Section 7 protocols (State Management).

## State Management & Documentation Updates (CRITICAL)

To maintain project visibility, you MUST update the tracking files after successfully generating the code for a Suite.

Update C2PRO_MASTER_BACKLOG.md:
Find the task ID or Suite ID.
Mark as [x] and add completion note: [x] Implemented (Unit Tests & Domain Logic).

Update docs/testing/C2PRO_TDD_BACKLOG_v1.0.md:
Find the line corresponding to the Suite ID or User Case.
Change the checkbox from [ ] to [x].

Why? This ensures that the next Agent picking up the project knows exactly where the development stands.
