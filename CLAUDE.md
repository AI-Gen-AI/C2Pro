# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project

C2Pro — Contract Intelligence Platform. Tridimensional audit (Contract + Schedule + Budget) that uses AI to detect incoherencies before they cause cost overruns. Monorepo managed with pnpm workspaces (`pnpm-workspace.yaml` → `apps/*`).

**Core differentiators**: Coherence Score™ (cross-document incoherence metric) and HITL (Human-in-the-Loop approval gates). These are first-class domain concepts — treat them as such in all design decisions.

## Stack

- **Backend** (`apps/api`): FastAPI + Pydantic v2, SQLAlchemy + Alembic, Python 3.11+.
- **Frontend** (`apps/web`): Next.js 16 + React 19, Tailwind v4, shadcn/ui, Vitest + Playwright (MSW for mocks).
- **Infra**: Supabase PostgreSQL (RLS), Upstash Redis, Cloudflare R2, Claude API (Sonnet).
- **Auth**: Clerk (JWT). The `apps/api/src/core/middleware/clerk_auth.py` middleware validates Clerk JWTs. `CLERK_SECRET_KEY`, `CLERK_PUBLISHABLE_KEY`, and `CLERK_JWKS_URL` are required env vars.
- **Tooling**: Makefile is the primary entrypoint; `pnpm` at the root; `pip`/`pytest` inside `apps/api`.

## Common Commands

All orchestrated through the root `Makefile` — run `make help` for the full list.

### Setup
```bash
make setup                  # Supabase cloud setup (installs api deps, creates .env)
make setup-local            # Docker-based setup (api + web + infra)
make backend-init           # Install deps + run migrations (runs apps/api/setup.py)
```

### Development
```bash
make backend-dev            # Backend only, Supabase cloud (runs apps/api/dev.py)
make dev-api                # Backend uvicorn reload (requires venv activated)
make dev-web                # Frontend only (cd apps/web && npm run dev)
make dev                    # Full local dev (Docker infra + instructions for api/web)
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

# Skip real AI calls in backend tests
C2PRO_AI_MOCK=1 pytest apps/api/...
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
make db-migrate                              # alembic upgrade head
make db-migrate-create MSG="description"     # new Alembic revision
make db-migrate-status
make db-reset                                # DESTRUCTIVE
make db-shell                                # psql into local DB
```

### OpenAPI / OpenSpec
```bash
make openapi                # Regenerate OpenAPI YAML from runtime (apps/api/scripts/generate_openapi.py)
pnpm verify:openspec        # Verify OpenSpec change workflow (scripts/verify_openspec_change.py)
```

## Architecture

### Backend (`apps/api/src`)

Domain-oriented FastAPI app. Key directories:

#### Infrastructure / Cross-cutting (`core/`)
- `core/auth/` — Auth routes and Clerk JWT validation bootstrap
- `core/middleware/` — `TenantIsolationMiddleware`, `RateLimitMiddleware`, `APIContractMiddleware`, `RequestLoggingMiddleware`, `clerk_auth.py` — all lazy-imported via PEP 562
- `core/database.py`, `core/cache.py` — SQLAlchemy async engine + Redis init/teardown
- `core/ai/` — **Claude API integration layer**: `llm_client.py` (API wrapper with retry/fallback), `model_router.py` + `model_routing.yaml` (route to Haiku/Sonnet/Opus by cost), `prompt_cache.py`, `usage_analytics.py` (per-tenant token/cost tracking), `tools/` (`@register_tool` definitions), `service.py`

#### `ai/` (thin shim)
Re-exports from `analysis.adapters.graph` and `core.ai`. Contains a simplified extraction-critique-save graph for tests (`ai/graph/workflow.py`). Not the primary code path — look in `core/ai/` for the real implementations.

#### Active Analysis Pipeline (`analysis/adapters/graph/`)
**This is the real orchestration path.** A LangGraph `StateGraph` on `ProjectState`:

| Node | ID | Purpose |
|---|---|---|
| `document_ingestion` | N1 | Load raw document |
| `pii_anonymizer` | N2 | Strip PII before sending to Claude |
| `router` | N3 | Route by `doc_type` (contract/schedule/budget) |
| `risk_extractor` | N4 | Extract contract risks |
| `wbs_extractor` | N5 | Extract WBS structure |
| `stakeholder_extractor` | N6 | Identify stakeholders |
| `raci_generator` | N7 | Build RACI matrix |
| `coherence_scorer` | N8 | **Coherence Score™** computation. v1 enforces ADR-009 §14 active-weight guard (returns `None` + `score_reason="insufficient_active_weight"` when `active_weight < 0.35`); the deprecated `mean × coverage_ratio` collapse is gone. v2 (`services/v2/aggregator_v2.py`) runs shadow; cutover behind per-tenant `Tenant.settings.feature_flags.coherence_v2_enabled` (Phase D). |
| `budget_parser` | N9 | Parse budget line items |
| `knowledge_graph` | N10 | Build cross-document knowledge graph |
| `decision_intelligence` | N11 | Decision Intelligence analysis |
| `critique` | N12 | Quality gate — retry loop or proceed |
| `human_interrupt` | N13/N14 | **HITL gate** — pause for human approval |
| `citation_validator` | N15 | Validate AI citations against source |
| `final_assembler` | N16 | Assemble final result |
| `save_to_db` | N17 | Persist to PostgreSQL |

Set `C2PRO_AI_MOCK=1` to bypass Claude calls (routes directly to N6 in the critique branch).

#### Feature Modules (`modules/`)
Hexagonal-architecture modules (domain / application / ports / adapters):
- `modules/hitl/` — Human-in-the-Loop: approval workflows, notification settings router
- `modules/decision_intelligence/` — Decision Intelligence engine (`runtime.py` builds services at startup)
- `modules/coherence/` — Coherence scoring internals
- `modules/ingestion/`, `modules/extraction/`, `modules/retrieval/` — Document pipeline stages
- `modules/scoring/`, `modules/governance/`, `modules/wbs_bom/` — Scoring, audit, WBS/BOM linking
- `modules/ai/`, `modules/analysis/`, `modules/graph/` — Module-scoped AI and graph adapters

#### Feature Domains (top-level)
`documents/`, `projects/`, `alerts/`, `wbs/`, `coherence/`, `anonymizer/`, `mcp/`, `bulk_operations/`, `gamification/`, `golden/`, `procurement/`, `stakeholders/` — each bounded context with its own `adapters/http/router.py`.

`shared_kernel/` — shared domain types (`dtos.py`, `enums.py`).

### Frontend (`apps/web`)

Next.js App Router:
- `app/(app)/` — authenticated product surface (projects, documents, coherence, WBS, budget, RACI, alerts, HITL).
- `app/(auth)/` — auth flows (Clerk-managed).
- `app/api/` — route handlers.
- `components/` — shared UI (`ui/` = shadcn primitives, `layout/`, `features/`, domain components).
- MSW workers in `apps/web/public/` (configured via root `package.json` `msw.workerDirectory`).

### Monorepo Layout

```
apps/          — executables (api, web)
infrastructure/ — DB scripts, operational scripts
supabase/      — Supabase CLI workspace (local config + CLI migrations)
core/          — root-level Python: supervisor.py, guardrails.py, shared agent config
schemas/       — shared JSON schemas
roles/, skills/, agent_skills/, evals/ — AI agent definitions, eval harnesses, skill_registry.yaml
openspec/      — OpenSpec change workflow
docs/          — canonical: architecture ADRs, runbooks, planning, testing, audits
context/, sandbox/ — NON-CANONICAL: working memory / experiments
backlogs/      — BCK_*.md task specs (see project rules)
blackboard/    — SESSION_*.md active session notes
```

## Project-Specific Rules (CRITICAL)

These rules in `.claude/rules/` override general defaults. Backlog/task source of truth: `C2PRO_MASTER_BACKLOG.md` (root) and `backlogs/BCK_*.md` (per-domain, e.g. `backlogs/BCK_BACKEND.md`).

1. **`CRITICAL_BACKLOG_REQUIREMENT.md`** — Every task (created, updated, or completed) MUST be reflected in `C2PRO_MASTER_BACKLOG.md`. Update `[ ] → [x]` with verification details and append to the Change Log.

2. **`DOCUMENTATION_STRUCTURE.md`** — **Never create task-specific standalone markdown files** (no `TASK-XXX_SUMMARY.md`, no `FEATURE_*_PLAN.md`). All task documentation goes in exactly two places:
   - `backlogs/BCK_*.md` — specs, status, implementation details (inline).
   - `blackboard/SESSION_*.md` — active session scratch notes; consolidate back into backlogs when done.
   The root has many legacy `TASK-*`, `UNIFY-*`, `SPRINT_*` files — these predate the rule. Do not add new ones.

3. **Commit attribution** disabled globally — do not add Co-Authored-By trailers.

## Security Baseline

- **Multi-tenant RLS** is enforced at the PostgreSQL layer. Any new table needs RLS policies.
- **PII anonymization** (`apps/api/src/anonymizer/` and N2 `pii_anonymizer_node`) must run before data reaches Claude.
- **MCP endpoints** are security-hardened (Gate 3). Don't bypass auth wrappers in `apps/api/src/mcp/`.
- Required env vars: `DATABASE_URL`, `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `SUPABASE_SERVICE_ROLE_KEY`, `JWT_SECRET_KEY`, `CLERK_SECRET_KEY`, `CLERK_PUBLISHABLE_KEY`, `ANTHROPIC_API_KEY`, `REDIS_URL`, `R2_*`.

## Gotchas

- **Two `core/` directories**: root `core/` (supervisor, guardrails, agent config) vs `apps/api/src/core/` (backend infrastructure). They are unrelated.
- **Two AI directories**: `apps/api/src/core/ai/` has all real AI code (LLM client, model router, prompt cache, usage tracking). `apps/api/src/ai/` is a thin re-export shim for tests. `core/ai/orchestration/` was deleted (TASK-BCK-027) — do not recreate it.
- **Two migration systems**: Alembic (`apps/api/alembic/`, authoritative) and Supabase CLI (`supabase/`). Keep in sync when touching schema.
- **Active pipeline** is `apps/api/src/analysis/adapters/graph/` — any file named `orchestration/` elsewhere is dead or legacy.
- `context/` and `sandbox/` are explicitly non-canonical — do not cite as sources of truth.
- The root `package.json` is misnamed (`"name": "package.json"`); pnpm workspace is still the real entry point.
- **Push to `main`** requires `ALLOW_PUSH_MAIN=1 git push` (Husky pre-push guard).
- **`docs/api/openapi.yaml` is generated** — produced by `make openapi` (`apps/api/scripts/generate_openapi.py`). Do not hand-edit; regenerate after route changes.
