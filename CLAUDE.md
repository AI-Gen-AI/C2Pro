# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

C2Pro — Contract Intelligence Platform. Tridimensional audit (Contract + Schedule + Budget) that uses AI to detect incoherencies before they cause cost overruns. Monorepo managed with pnpm workspaces (`pnpm-workspace.yaml` → `apps/*`).

## Stack

- **Backend** (`apps/api`): FastAPI + Pydantic v2, SQLAlchemy + Alembic, Python 3.11+.
- **Frontend** (`apps/web`): Next.js 16 + React 19, Tailwind v4, shadcn/ui, Vitest + Playwright (MSW for mocks).
- **Infra**: Supabase PostgreSQL (RLS), Upstash Redis, Cloudflare R2, Claude API (Sonnet).
- **Tooling**: Makefile is the primary entrypoint; `pnpm` at the root; `pip`/`pytest` inside `apps/api`.

## Common Commands

All orchestrated through the root `Makefile` — run `make help` for the full list.

### Setup
```bash
make setup                  # Supabase cloud setup (installs api deps, creates .env)
make setup-local            # Docker-based setup (api + web + infra)
make backend-init           # Install deps + run migrations
```

### Development
```bash
make dev                    # Full local dev (docker-compose up)
make backend-dev            # Backend only, Supabase cloud
make dev-api                # Backend in dev mode
make dev-web                # Frontend only
```

### Tests
```bash
make test                   # Full test suite
make test-api               # Backend: pytest in apps/api
make test-api-cov           # Backend with coverage
make test-web               # Frontend: vitest in apps/web

# Single test (backend)
cd apps/api && pytest tests/path/to/test_file.py::TestClass::test_name -xvs

# Single test (frontend)
cd apps/web && pnpm vitest run path/to/file.test.tsx
```

### Lint / Format / Types / Build
```bash
make lint                   # lint-api (ruff) + lint-web (eslint)
make format                 # black/ruff for api, prettier for web
make typecheck              # mypy + tsc
make build                  # build-api + build-web
```

### Database
```bash
make db-migrate                             # alembic upgrade head
make db-migrate-create MSG="description"    # new Alembic revision
make db-migrate-status
make db-reset                               # DESTRUCTIVE
make db-shell                               # psql into local DB
```

### OpenAPI
```bash
make openapi                # Regenerate OpenAPI YAML from runtime (apps/api/scripts/generate_openapi.py)
```

## Architecture

### Backend (`apps/api/src`)

Domain-oriented FastAPI app, not layered-by-type. Each top-level directory is a bounded context:

- `ai/` — Claude integration, prompts, model orchestration (core AI pipeline lives here, **not** in `core/ai/orchestration/` which was deleted — see TASK-BCK-027).
- `analysis/adapters/graph/` — **Active N1–N17 coherence pipeline**. This is the real orchestration path for analysis.
- `coherence/` — Coherence engine (Gate 5, in progress).
- `anonymizer/` — PII stripping before sending data to Claude (S1.5).
- `documents/` — Contract/schedule/budget ingestion and repository (SQLAlchemy).
- `mcp/` — MCP server wiring (Gate 3 security-hardened).
- `alerts/`, `bulk_operations/`, `gamification/`, `golden/`, `procurement/`, `projects/`, `stakeholders/`, `wbs/` — Additional feature modules.
- `shared_kernel/` — Cross-cutting domain types.
- `config.py`, `main.py` — FastAPI app factory and settings.

Migrations live in `apps/api/alembic/`. Database is Supabase PostgreSQL with Row Level Security enforced for multi-tenancy — **any new table needs RLS policies** (CTO Gate 1).

### Frontend (`apps/web`)

Next.js App Router:
- `app/(app)/` — authenticated product surface.
- `app/(auth)/` — auth flows.
- `app/api/` — route handlers.
- `components/`, `contexts/` — shared UI + React contexts.
- MSW workers served from `apps/web/public/` (configured via root `package.json` `msw.workerDirectory`).

### Monorepo Layout

- `apps/` — executables (api, web).
- `infrastructure/` — DB scripts, operational scripts.
- `supabase/` — Supabase CLI workspace (local config + CLI migrations; separate from Alembic).
- `core/` — top-level Python modules (`supervisor.py`, `guardrails.py`, shared config). Distinct from `apps/api/src/core`.
- `schemas/`, `roles/`, `skills/`, `agent_skills/`, `evals/` — AI agent definitions, evaluation harnesses, skill registries (`skill_registry.yaml`).
- `openspec/` — OpenSpec change workflow (`scripts/verify_openspec_change.py` via `pnpm verify:openspec`).
- `docs/` — canonical documentation (architecture, runbooks, planning, testing, audits, archive).
- `context/`, `sandbox/` — **non-canonical**: working memory / experiments. Don't treat as source of truth.
- `backlogs/`, `blackboard.json` — task tracking (see project rules below).

## Project-Specific Rules (CRITICAL)

These rules in `.claude/rules/` override general defaults. Read them before doing substantive work:

1. **`CRITICAL_BACKLOG_REQUIREMENT.md`** — Every task (created, updated, or completed) MUST be reflected in `C2PRO_MASTER_BACKLOG.md`. Update task status `[ ] → [x]` with verification details, and append to the Change Log. Non-negotiable.

2. **`DOCUMENTATION_STRUCTURE.md`** — **Never create task-specific standalone markdown files** (no `TASK-XXX_SUMMARY.md`, no `FEATURE_*_PLAN.md`). All task documentation goes in exactly two places:
   - `backlogs/BCK_*.md` — specs, status, implementation details (inline).
   - `blackboard/SESSION_*.md` — active session scratch notes, consolidated back into backlogs when done.

   The repo has many legacy `TASK-*`, `UNIFY-*`, `SPRINT_*` markdown files at the root — these predate the rule. Do not add new ones.

3. **Commit attribution** is disabled globally; do not add Co-Authored-By trailers.

## Security Baseline

- **Multi-tenant RLS** is enforced at the PostgreSQL layer (Gate 1). Test RLS for any new table.
- **PII anonymization** runs before any data leaves for Claude API (`apps/api/src/anonymizer/`).
- **MCP endpoints** are hardened per Gate 3 (23/23 tests) — don't bypass auth wrappers.
- Secrets: `.env` only, see `.env.example` for the required set (`DATABASE_URL`, `SUPABASE_*`, `ANTHROPIC_API_KEY`, `UPSTASH_REDIS_URL`, `R2_*`).

## Gotchas

- **Two `core/` directories** exist: root `core/` (supervisor, guardrails, Python agent config) vs `apps/api/src/core/` (backend internals). Don't confuse them.
- **Two migration systems**: Alembic (`apps/api/alembic/`, authoritative for backend schema) and Supabase CLI (`supabase/`, used for local Supabase dev). Keep them in sync when touching schema.
- **Active analysis pipeline** is `apps/api/src/analysis/adapters/graph/` (N1–N17), not any `orchestration/` folder.
- `context/` and `sandbox/` are explicitly non-canonical — don't cite them as sources.
- The root `package.json` is misnamed (`"name": "package.json"`); pnpm workspace is still the real entry point.
