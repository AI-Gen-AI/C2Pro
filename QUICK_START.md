# C2Pro - Quick Start Guide

Get the full-stack application running locally in **execution mode** (real backend) or **demo mode** (frontend-only with mock data).

## Related Docs

- [Repository README](./README.md)
- [Documentation index](./docs/README.md)
- [Runbooks index](./docs/runbooks/README.md)
- [API README](./apps/api/README.md)
- [Web setup README](./apps/web/README_SETUP.md)
- [Clerk auth dev vs production guide](./docs/runbooks/CLERK_AUTH_DEV_PROD_GUIDE.md)

---

## Prerequisites

| Tool | Version | Check |
|------|---------|-------|
| Python | 3.11+ | `python --version` |
| Node.js | 20+ | `node --version` |
| npm | 10+ | `npm --version` |
| Docker + Compose | Latest | `docker compose version` |
| Git | Any | `git --version` |

---

## 1. Execution Mode (Real Backend + Frontend)

This is the production-like setup where both the API and the web app connect to real services.

### 1.1 Start infrastructure services

```bash
docker compose up -d postgres redis minio minio-setup
```

This starts:
- **PostgreSQL 15** on `localhost:5432` (user: `postgres`, password: `postgres`, db: `c2pro`)
- **Redis 7** on `localhost:6379`
- **MinIO** on `localhost:9000` (console: `localhost:9001`, user/pass: `minioadmin`)

Wait for all services to be healthy:

```bash
docker compose ps
```

### 1.2 Configure environment

```bash
cp .env.example .env
```

Edit `.env` with your credentials. For **local Docker** development, use these values:

```bash
# Database -  Docker PostgreSQL
DATABASE_URL=postgresql://postgres:postgres@localhost:5432/c2pro

# Supabase -  Required for auth (get from https://supabase.com/dashboard)
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=eyJ...
SUPABASE_SERVICE_ROLE_KEY=eyJ...

# JWT -  Generate a random 32+ character string
JWT_SECRET_KEY=change-me-to-a-random-string-at-least-32-chars

# Redis -  Docker Redis
REDIS_URL=redis://localhost:6379

# Storage -  Use local filesystem for development
STORAGE_PROVIDER=local

# AI -  Optional, required for AI features
ANTHROPIC_API_KEY=sk-ant-...
```

> **Required variables:** `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `JWT_SECRET_KEY`

### 1.3 Start backend

```bash
cd apps/api

# Install dependencies
pip install -r requirements.txt

# Run database migrations
alembic upgrade head

# Start dev server (hot-reload enabled)
python dev.py
```

The API will be available at:
- **API:** http://localhost:8000
- **Swagger docs:** http://localhost:8000/docs
- **Health check:** http://localhost:8000/health

### 1.4 Start frontend

In a **new terminal**:

```bash
cd apps/web

# Install dependencies
pnpm install

# Start dev server
to fi
```

The web app will be available at http://localhost:3000.

### 1.5 Verify it works

```bash
# Backend health
curl http://localhost:8000/health
# Expected: {"status":"ok","app":"C2Pro API","version":"1.0.0",...}

# Register a user
curl -X POST http://localhost:8000/api/v1/auth/register \
  -H "Content-Type: application/json" \
  -d '{
    "company_name": "My Company",
    "email": "user@example.com",
    "password": "Password123!",
    "password_confirm": "Password123!",
    "first_name": "Test",
    "last_name": "User",
    "accept_terms": true
  }'

# Login
curl -X POST http://localhost:8000/api/v1/auth/login \
  -H "Content-Type: application/json" \
  -d '{"email": "user@example.com", "password": "Password123!"}'
```

---

## 2. Demo Mode (Frontend-Only, No Backend Required)

Demo mode runs the frontend with **MSW (Mock Service Worker)** intercepting all API calls. No backend, database, or external services are needed.

### 2.1 Start the frontend in demo mode

```bash
cd apps/web

# Install dependencies (if not already done)
pnpm install

# Start with demo mode enabled
NEXT_PUBLIC_APP_MODE=demo pnpm dev
```

The web app will be available at http://localhost:3000 with a "DEMO" banner.

### How demo mode works

- `NEXT_PUBLIC_APP_MODE=demo` activates MSW in the browser via `providers.tsx`
- MSW intercepts all HTTP calls to the API and returns realistic mock data
- Mock handlers are in `apps/web/mocks/handlers/` (~50 endpoints covered)
- Mock data is in `apps/web/mocks/data/`
- No backend, database, or Redis required

### Switching back to execution mode

Stop the dev server and restart without the env variable:

```bash
pnpm dev
# NEXT_PUBLIC_APP_MODE defaults to "production" -  no MSW, real API calls
```

---

## 3. Full-Stack with Docker Compose

To run everything (backend + infrastructure) in Docker:

```bash
# Ensure .env exists with valid credentials
cp .env.example .env  # then edit

# Start all services
docker compose up -d

# Check status
docker compose ps
docker compose logs -f api
```

Services:
| Service | URL | Purpose |
|---------|-----|---------|
| `api` | http://localhost:8000 | FastAPI backend |
| `postgres` | localhost:5432 | PostgreSQL database |
| `redis` | localhost:6379 | Cache + task queue |
| `minio` | http://localhost:9001 | Storage (S3-compatible) |

Then start the frontend separately:

```bash
cd apps/web && pnpm dev
```

---

## 4. Makefile Shortcuts

```bash
make help              # List all commands

# Setup
make setup             # Full setup (Supabase cloud)
make setup-local       # Setup with Docker PostgreSQL
make backend-init      # Run setup.py (deps + migrations)

# Development
make dev-infra         # Start Docker services only
make dev-api           # Start backend with reload
make dev-web           # Start frontend
make backend-dev       # Start backend (Supabase mode)

# Database
make db-migrate        # Apply migrations
make db-migrate-status # Check migration status
make db-migrate-create MSG="description"  # Create migration

# Testing
make test-api          # Backend tests
make test-web          # Frontend tests
make test              # All tests

# Quality
make lint              # Run linters
make format            # Format code
make typecheck         # Type checking
```

---

## 5. Environment Variables Reference

### Required (No Defaults)

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | PostgreSQL connection string |
| `SUPABASE_URL` | Supabase project URL |
| `SUPABASE_ANON_KEY` | Supabase anonymous key |
| `SUPABASE_SERVICE_ROLE_KEY` | Supabase service role key |
| `JWT_SECRET_KEY` | JWT signing secret (32+ chars) |

### Backend (Optional)

| Variable | Default | Purpose |
|----------|---------|---------|
| `ENVIRONMENT` | `development` | `development` / `staging` / `production` |
| `DEBUG` | `false` | Enable debug mode |
| `LOG_LEVEL` | `INFO` | `DEBUG` / `INFO` / `WARNING` / `ERROR` |
| `REDIS_URL` | `None` | Redis for cache + Celery |
| `ANTHROPIC_API_KEY` | `None` | Claude API for AI features |
| `STORAGE_PROVIDER` | `r2` | `r2` / `s3` / `local` |
| `CORS_ORIGINS` | `localhost:3000,3001` | Allowed CORS origins (CSV) |
| `MAX_UPLOAD_SIZE_MB` | `50` | Max file upload size |
| `SENTRY_DSN` | `None` | Error tracking |

### Frontend

| Variable | Default | Purpose |
|----------|---------|---------|
| `NEXT_PUBLIC_APP_MODE` | `production` | `production` / `demo` |
| `NEXT_PUBLIC_API_URL` | `http://localhost:8000/api/v1` | Backend API base URL |
| `NEXT_PUBLIC_SENTRY_DSN` | `None` | Frontend error tracking |

### Feature Flags

| Flag | Default | Description |
|------|---------|-------------|
| `FEATURE_COHERENCE_ANALYSIS` | `true` | Contract coherence scoring |
| `FEATURE_WBS_GENERATION` | `true` | Work Breakdown Structure |
| `FEATURE_BOM_GENERATION` | `true` | Bill of Materials |
| `FEATURE_STAKEHOLDER_EXTRACTION` | `true` | Stakeholder detection |
| `FEATURE_RACI_GENERATION` | `false` | RACI matrix (Phase 2) |
| `FEATURE_RFQ_GENERATION` | `false` | RFQ generation (Phase 2) |
| `FEATURE_EXPEDITING_VISION` | `false` | Expediting (Phase 3) |

---

## 6. Troubleshooting

### Backend won't start

```
RuntimeError: Database not initialized
```
Run `cd apps/api && alembic upgrade head` to apply migrations.

```
ValidationError: database_url field required
```
Ensure `.env` exists at the repo root with `DATABASE_URL` set.

```
Connection refused (port 5432)
```
Start PostgreSQL: `docker compose up -d postgres`

### Frontend won't connect to backend

Ensure `NEXT_PUBLIC_API_URL` points to the running backend (default: `http://localhost:8000/api/v1`). Check that the backend is healthy with `curl http://localhost:8000/health`.

### Port already in use

```bash
# Kill process on port 8000 (backend)
lsof -ti:8000 | xargs kill -9

# Kill process on port 3000 (frontend)
lsof -ti:3000 | xargs kill -9
```

### AI features not working

Set `ANTHROPIC_API_KEY` in `.env` with a valid key from https://console.anthropic.com/.

---

## Architecture Overview

```
C2Pro/
%%% apps/
%   %%% api/              # FastAPI backend (Python 3.11)
%   %   %%% src/          # Source code (DDD bounded contexts)
%   %   %%% dev.py        # Dev server entry point
%   %   %%% setup.py      # Initial setup script
%   %   -%%% alembic/      # Database migrations
%   -%%% web/              # Next.js frontend (React 19)
%       %%% app/          # App Router pages
%       %%% components/   # UI components (shadcn/ui)
%       %%% mocks/        # MSW handlers + demo data
%       -%%% stores/       # Zustand state management
%%% infrastructure/       # Docker, migrations, scripts
%%% docker-compose.yml    # Local dev services
%%% .env.example          # Environment template
-%%% Makefile              # Development shortcuts
```
