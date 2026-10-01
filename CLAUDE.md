# CLAUDE.md

Guidance for Claude Code and compatible coding agents working in C2Pro.

## Project

C2Pro is a multi-tenant Contract & Project Intelligence platform. Core product concepts include evidence/provenance, Coherence/Health, Project Controls and Human-in-the-Loop review.

## Canonical context — read this first

1. `docs/DOCUMENTATION_GOVERNANCE.md`
2. `docs/architecture/C2PRO_TECHNICAL_DESIGN_DOCUMENT_v4_2.md`
3. `docs/architecture/decisions/README.md`
4. `.c2pro/control/` + your assigned `.c2pro/work/<work_id>.yaml`
5. exact code/tests/CI for the SHA you are changing

Product lifecycle status comes from `validation/product/c2pro-master-product-control-v1.yaml`, not from a backlog or README.

Legacy `C2PRO_MASTER_BACKLOG.md`, `backlogs/*.md` and `blackboard.json` are cold/read-only references for ordinary workers.

## Stack

- **Backend:** FastAPI 0.141.x, Pydantic v2, SQLAlchemy/Alembic, Python 3.11.
- **Frontend:** Next.js 16.3.6, React 19.2.7, TypeScript 5.9, Tailwind 4.
- **Auth:** Clerk JWT → internal tenant/user mapping → PostgreSQL RLS.
- **Persistence:** PostgreSQL/Supabase + pgvector; Alembic application migration authority.
- **Async:** Celery + Redis.
- **Storage:** Cloudflare R2/S3-compatible.
- **AI:** Anthropic-oriented application layer behind adapters; LangChain/LangSmith.
- **Orchestration:** LangGraph 1.2.10 + `langgraph-checkpoint-postgres==3.1.2`.
- **Tooling:** Node 22, pnpm 10, pytest, Vitest, Playwright.

## Common commands

```bash
make help
make setup-local
make dev
make test
make test-api
make test-web
make lint
make typecheck
make build
make openapi
pnpm verify:openspec
```

Database:
```bash
make db-migrate
make db-migrate-create MSG="description"
make db-migrate-status
```

## Architecture

### Backend
`apps/api/src/` is domain-oriented/hexagonal.

- `analysis/adapters/graph/` — active LangGraph pipeline.
- `core/ai/` — provider/model routing/cost/AI infrastructure.
- `core/middleware/` and `core/auth/` — identity, tenant and request boundaries.
- `modules/` — hexagonal feature modules.
- top-level bounded contexts include documents, projects, alerts, coherence, procurement, WBS and stakeholders.

### Frontend
`apps/web/` uses the Next.js App Router:
- `app/(app)/` — authenticated product;
- `app/(auth)/` — Clerk auth;
- `components/`, `hooks/`, `lib/` — shared/domain UI;
- Vitest and Playwright test surfaces.

## Processing and checkpoint invariants

Do not reintroduce a document-wide shared checkpoint lineage for owned analysis.

Normal owned thread:
`document:{document_id}:g{generation}:f{fencing_token}:analysis`

Canonical durable writes re-verify exact processing authority in the same transaction. HITL resume binds the exact persisted checkpoint tuple. See ADR-026.

## Single-Writer Control Plane

Ordinary implementation, QA and review workers:

- read `.c2pro/control/` and assigned work envelope;
- do not mutate `C2PRO_MASTER_BACKLOG.md`, `backlogs/*.md` or `blackboard.json`;
- return a fenced YAML result matching `c2pro-implementation-result-v1`;
- report new findings/residual risks in that result;
- do not self-promote completion/lifecycle status.

Only the Planner/Master Reconciler writes canonical planning/control state.

## Documentation

Follow `.claude/rules/DOCUMENTATION_STRUCTURE.md`.

- architecture decision → ADR;
- platform composition → current TDD;
- durable operational procedure → runbook;
- test methodology/index → `docs/testing/`;
- proposed design/plan → approved spec/plan location with Proposed/In-flight status;
- historical evidence → archive/audit.

Do not create standalone completion-summary Markdown when PR evidence/structured result is sufficient.

## Security baseline

- new tenant data surfaces require correct RLS/isolation;
- PII handling precedes external model exposure where required;
- do not bypass MCP/auth wrappers;
- do not log credentials/DSNs/tokens;
- platform-operator identity is distinct from tenant identity;
- ownership/fencing failures are fail-closed.

## Database gotchas

- Alembic is application migration authority.
- Supabase SQL/config surfaces exist for platform/local/security support; follow migration authority runbook.
- checkpoint schema DDL is owner-bootstrap work via `apps/api/scripts/checkpoint_bootstrap.py`; runtime does not call `AsyncPostgresSaver.setup()`.

## CI

Primary PR pipeline is `.github/workflows/ci.yml`; dedicated guards include secret scan, install drift, dependency review/audit, CodeQL and Product-Control Guard. The branch ruleset is authoritative for required merge contexts.

Never bypass a gate to make CI green. Fix the defect or document a genuinely non-blocking external/advisory status.

## Source layout

```text
apps/               executables (api, web)
.c2pro/             canonical development control/work envelopes
docs/               architecture, ADRs, runbooks, testing, audits
infrastructure/     operational/database support
supabase/           Supabase CLI/platform surface
schemas/            shared schemas
roles/, skills/     agent role/skill definitions
context/, sandbox/  non-canonical working/experimental material
backlogs/           legacy/cold domain references
```

## graphify

When `graphify-out/graph.json` exists, prefer `graphify query/path/explain` for scoped codebase navigation. Update the graph after material code changes where the workflow requires it.
