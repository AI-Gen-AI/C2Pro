# C2Pro — Quick Start

Run the current C2Pro stack locally using the repository's pinned toolchain and supported development paths.

## Authority

- Platform architecture: [TDD v4.2](./docs/architecture/C2PRO_TECHNICAL_DESIGN_DOCUMENT_v4_2.md)
- Auth: [Clerk dev/prod guide](./docs/runbooks/CLERK_AUTH_DEV_PROD_GUIDE.md)
- Database/migrations: [Runbooks](./docs/runbooks/README.md)
- CI/release: [Release criteria](./docs/RELEASE_CRITERIA.md)
- Exact environment contract: `.env.example` and app-specific examples

Do not use this quick start as production configuration guidance.

## Prerequisites

| Tool | Repository contract |
|---|---|
| Python | 3.11+ |
| Node.js | >=22 <23 |
| pnpm | >=10; root pins pnpm 10.25.0 |
| Docker + Compose | current supported version |
| Git | current supported version |

The repository enforces pnpm; do not substitute npm/yarn.

## 1. Clone and install

```bash
git clone https://github.com/AI-Gen-AI/C2Pro.git
cd C2Pro

cp .env.example .env
# Configure LOCAL/DEVELOPMENT values only.

pnpm install --frozen-lockfile

cd apps/api
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cd ../..
```

On Windows PowerShell, activate the Python environment with the platform-appropriate `.venv` activation script or use WSL/Docker.

## 2. Local infrastructure

Set a local PostgreSQL password in the repo-root `.env`, then:

```bash
python scripts/validate_local_postgres_password.py
docker compose up -d postgres redis minio minio-setup
docker compose ps
```

Canonical local defaults are defined by `docker-compose.yml`; do not copy production credentials or DSNs into local files.

For CI-like disposable test infrastructure use the test bootstrap/runbooks rather than assuming the development ports equal CI ports.

## 3. Database schema

```bash
cd apps/api
source .venv/bin/activate
alembic upgrade head
cd ../..
```

Alembic is the application migration authority. Follow the database migration runbooks for Supabase/mirror requirements and production operations.

## 4. Start the backend

```bash
cd apps/api
source .venv/bin/activate
uvicorn src.main:app --reload --host 0.0.0.0 --port 8000
```

Useful local endpoints:

- API: `http://localhost:8000`
- OpenAPI UI: `http://localhost:8000/docs`
- Health: `http://localhost:8000/health`

## 5. Start the frontend

In another terminal:

```bash
cd apps/web
pnpm dev
```

Web: `http://localhost:3000`

The current frontend uses Clerk. Configure development Clerk values from `apps/web/.env.example` / repo environment examples when testing authenticated flows.

## 6. Demo mode

For frontend-only product exploration where the supported demo mocks apply:

```bash
cd apps/web
NEXT_PUBLIC_APP_MODE=demo pnpm dev
```

Demo mode is not production proof and must never be used for production qualification.

## 7. Common quality commands

### Backend

```bash
cd apps/api
source .venv/bin/activate

python -m ruff check .
python -m mypy src
python -m pytest
```

### Frontend

```bash
cd apps/web

pnpm typecheck
pnpm lint
pnpm test
pnpm build
pnpm test:e2e
```

### Repository helpers

```bash
make help
make openapi
make test
make lint
make typecheck
make build
```

The live CI workflow is `.github/workflows/ci.yml`; local commands are useful preflight, not a substitute for required GitHub checks.

## 8. Authentication

User-facing authentication is Clerk-backed.

Relevant development settings include:

- `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY`
- `CLERK_SECRET_KEY`
- `CLERK_ISSUER`
- `CLERK_JWKS_URL`

Use development/test Clerk instances for local/E2E work. Follow the Clerk runbook before any production auth operation.

Do not assume the legacy local email/password JWT examples represent the canonical production path.

## 9. Troubleshooting

### Database connection refused

```bash
docker compose ps
docker compose up -d postgres
```

Check `DATABASE_URL` against the environment/port you actually started.

### Redis unavailable

```bash
docker compose up -d redis
docker compose logs redis
```

### Migration mismatch

```bash
cd apps/api
alembic current
alembic heads
alembic upgrade head
```

There must be one authoritative head for release/CI contracts that require a clean migration chain.

### Frontend cannot authenticate

Check the Clerk development keys and configured URLs. See:

- `apps/web/.env.example`
- `docs/runbooks/CLERK_AUTH_DEV_PROD_GUIDE.md`

### Frontend cannot reach API

Check the frontend API URL variables against the local backend address and verify `http://localhost:8000/health`.

## 10. Production qualification warning

Do not adapt local/demo/E2E shortcuts to production.

The controlled production qualification path is:

[Production Qualification Operator Runbook](./docs/product/production-qualification-operator-runbook.md)

It uses a dedicated synthetic production identity/tenant, exact deployment identity checks and bounded evidence.
