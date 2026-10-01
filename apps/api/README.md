# C2Pro API

FastAPI backend for C2Pro's project-centric contract and project intelligence platform.

## Start with

- [Repository quick start](../../QUICK_START.md)
- [Current TDD v4.2](../../docs/architecture/C2PRO_TECHNICAL_DESIGN_DOCUMENT_v4_2.md)
- [ADR index](../../docs/architecture/decisions/README.md)
- [Database/runbooks](../../docs/runbooks/README.md)
- [Testing documentation](../../docs/testing/README.md)
- [API OpenAPI artifact](../../docs/api/README.md)

## Runtime stack

Verified from the current backend manifests:

- Python 3.11+
- FastAPI 0.141.1
- Pydantic v2
- SQLAlchemy async + PostgreSQL
- Alembic
- Redis / Celery
- LangGraph + PostgreSQL checkpointing
- Clerk-backed authentication/tenant context
- Anthropic/LangChain/LangSmith integration surfaces

Do not treat version numbers in historical architecture/audit documents as current dependency authority. `requirements.txt` / lock/config files are authoritative.

## Architecture

The backend is a modular monolith with domain/application/port/adapter boundaries where the bounded context has been migrated to that structure.

Major current concerns include:

- projects and canonical Project Controls/WBS;
- documents/evidence;
- analysis and ProjectGraph;
- Coherence / Health;
- HITL and Trusted-State Commit;
- procurement/stakeholders;
- security/tenant isolation;
- observability;
- Product Control validation/qualification support.

Architecture invariants are defined by the current TDD and ADRs, not this README.

## Local setup

From the repository root:

```bash
cp .env.example .env
python scripts/validate_local_postgres_password.py
docker compose up -d postgres redis minio minio-setup
```

Then:

```bash
cd apps/api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
alembic upgrade head
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

See `QUICK_START.md` for Windows/alternative paths.

## Authentication

The current production-facing auth architecture is Clerk-backed.

Backend auth code validates Clerk identity and resolves the internal tenant/user context required by protected application routes. Local JWT/test paths exist for supported test/bootstrap scenarios but must not be mistaken for the canonical production identity contract.

Relevant configuration lives in `src/config.py` and repository environment examples.

See:

- `docs/runbooks/CLERK_AUTH_DEV_PROD_GUIDE.md`
- `src/core/auth/`
- `src/core/middleware/`

## Database and migrations

Application schema history is managed with Alembic under `apps/api/alembic/`.

Typical local commands:

```bash
alembic heads
alembic current
alembic upgrade head
```

Database changes must preserve:

- tenant isolation / RLS contracts;
- migration ordering and mirror requirements;
- canonical WBS constraints;
- function/role privilege boundaries;
- rollback/upgrade semantics required by the affected gate.

Use the current database migration runbooks instead of old Sprint-1 migration instructions.

## Tests

```bash
cd apps/api
source .venv/bin/activate

python -m pytest
python -m ruff check .
python -m mypy src
```

CI runs a substantially broader matrix than one local `pytest`, including security, migrated-schema, integration, core/coherence/modules, coverage and Docker/runtime payload gates.

Executable CI truth: `.github/workflows/ci.yml`.

## OpenAPI

Regenerate the canonical API artifact after applicable contract/router changes:

```bash
make openapi
```

Commit generated contract changes together with the implementation and allow OpenAPI/API-drift tests to arbitrate consistency.

## Trusted-State Commit

Consequential HITL-gated output follows:

`candidate persisted → exact review binding → trusted commit → canonical ProjectGraph/Health/Coherence`

Persistence alone does not grant trust.

See ADR-026.

## Security

Backend changes must consider:

- authenticated tenant identity;
- fail-closed tenant-scoped persistence;
- RLS/database privileges;
- secret handling;
- exact approval/identity binding;
- evidence truthfulness;
- safe retries/idempotency;
- production/runtime separation.

Cross-tenant leakage and trust-boundary violations are release-blocking defect classes.

## Operations

Do not use backend scripts against production merely because they are callable locally.

For production qualification use the dedicated protected workflow/runbook:

- `.github/workflows/prod-synthetic-acceptance.yml`
- `docs/product/production-qualification-operator-runbook.md`

## Source-of-truth note

This file intentionally avoids static endpoint inventories and sprint percentages because those decay quickly.

For current API shape use:

- running OpenAPI;
- `docs/api/openapi.yaml`;
- current routers/source;
- executable tests.
