---
name: c2pro-patterns
description: Coding patterns extracted from C2Pro git history (200 commits analyzed)
version: 1.0.0
source: local-git-analysis
analyzed_commits: 200
generated: 2026-05-08
---

# C2Pro Patterns

## Commit Conventions

**Format**: `<type>(<scope>): <description> — <TASK-ID>`

Types by frequency:
- `feat` (44) — new feature or capability
- `chore` (39) — backlog updates, lint fixes, reconciliation
- `fix` (15) — bug fixes
- `test` (13) — test additions or corrections
- `merge` (11) — branch synchronization commits
- `ci` — GitHub Actions workflow changes
- `perf` — performance improvements
- `refactor` — structural refactoring without behavior change

**Scopes** (most common):
- `backlog` — always paired with chore when updating task status
- `ai` — LangSmith, LLM client, tracing
- `coherence` — Coherence Score engine
- `lint` — ruff violations
- `ops` — real-document operability tests
- `hitl` — Human-in-the-Loop workflow
- `ddd` — domain-driven design migration
- `security` — RLS, secret channel, auth

**Task ID pattern**: always append `— TASK-XXX-000` or `(TASK-XXX-000..NNN)` at end of message body.

**Special prefixes**:
- `[openapi]` — marks OpenAPI schema regeneration commits for CI drift gate detection
- `merge:` — branch sync commits (not a conventional commit type — used verbatim)

**Examples from history**:
```
feat(ddd): alerts bulk ops + workspace settings + WBS move node use cases
chore(backlog): mark TASK-BCK-041 complete — ruff ARG/SIM noqa pass (dab24151)
fix(security): timing-safe token comparison + fix LLMResponse usage metrics
test(ops): cover real document upload persistence (TASK-OPS-DOCFLOW-005)
chore(lint): silence 29 ARG + 7 SIM/F violations with noqa — TASK-BCK-041
[openapi] regenerate schema: add observability, ai_feedback, dlq, frontend_support, admin routers
```

---

## Code Architecture

### Backend (`apps/api/src/`)

```
src/
├── core/
│   ├── ai/                  # LLM client, LangSmith client, prompt registry, rollout router
│   │   ├── llm_client.py    # Primary LLM interface — @traced_llm_call decorator applied here
│   │   ├── langsmith_client.py
│   │   ├── langsmith_hub.py
│   │   └── usage_logger.py
│   ├── observability/       # Tracing decorators, span schemas — CANONICAL location
│   │   ├── langsmith_decorator.py  # THE canonical traced_llm_call (imported by llm_client)
│   │   ├── coherence_tracing.py
│   │   └── monitoring.py
│   ├── middleware/          # Tenant isolation, rate limit, auth, contract middleware
│   ├── security/            # Secret channel, RLS audit
│   └── frontend_support/    # Endpoints bridging MSW mocks to real API
├── modules/                 # Hexagonal modules (domain/application/ports/adapters)
│   ├── hitl/                # Human-in-the-Loop approval workflow
│   ├── coherence/           # Coherence scoring internals
│   ├── observability/       # LangSmith gateway port + adapter
│   └── decision_intelligence/
├── analysis/adapters/graph/ # ACTIVE LangGraph pipeline N1-N17 (the real orchestration path)
├── coherence/               # Coherence scoring engine + LangGraph subgraph
├── documents/               # Document upload, parsing, retrieval bounded context
├── projects/                # Projects bounded context
└── shared_kernel/           # Shared DTOs, enums
```

**Key invariants**:
- `core/ai/` = real AI code (LLM client, model router, prompt cache)
- `core/observability/langsmith_decorator.py` = canonical `traced_llm_call` decorator
- `analysis/adapters/graph/` = active N1-N17 pipeline (NOT `core/ai/orchestration/` — deleted)
- Any file named `orchestration/` is dead/legacy — do not recreate

### Frontend (`apps/web/`)

```
app/(app)/          # Authenticated product surface
components/
├── features/
│   ├── ai-analytics/   # Hottest frontend area — LangSmith dashboard components
│   ├── alerts/         # Alert management
│   └── coherence/      # Coherence score visualization
└── ui/                 # shadcn/ui primitives
lib/api/            # API client — most frequently changed frontend file
src/tests/
├── wireframes/     # WF-01..WF-06 wireframe tests
└── e2e/            # Playwright E2E tests
```

---

## Workflows

### Adding a Backend Feature (DDD Pattern)
1. Define domain entity in `modules/<domain>/domain/entities.py`
2. Define port (Protocol) in `modules/<domain>/ports/`
3. Implement use case in `modules/<domain>/application/`
4. Implement adapter in `modules/<domain>/adapters/`
5. Wire router in `<domain>/adapters/http/router.py`
6. Register router in `src/main.py`
7. Run `make openapi` to regenerate schema → commit with `[openapi]` prefix

### Database Migration
1. `make db-migrate-create MSG="description"` — creates Alembic revision
2. Migration file in `apps/api/alembic/versions/YYYYMMDD_HHMM_description.py`
3. Always: `SET LOCAL lock_timeout = '5s'` guard in DDL
4. Always: enable `FORCE ROW LEVEL SECURITY` on new tables
5. Always: add direct `tenant_id` column + RLS policy (fail-closed, no COALESCE fallback)
6. Mirror in `supabase/tests/NN_table_rls.sql` — SQL-level RLS verification test
7. `make db-migrate` to apply

### Task Lifecycle
1. Add `| [ ] | P1 | TASK-XXX-NNN | ... |` row to appropriate `backlogs/BCK_*.md`
2. Add entry to `C2PRO_MASTER_BACKLOG.md` (MANDATORY — single source of truth)
3. Implement with branch named `<type>/<kebab-description>`
4. Commit with `— TASK-XXX-NNN` in message
5. Mark complete: `chore(backlog): mark TASK-XXX-NNN complete — <sha-of-impl-commit>`
6. Update `C2PRO_MASTER_BACKLOG.md` `[ ] → [x]`

### Ruff Lint Fixes
- Auto-fix: `chore(lint): auto-fix N violations (W, UP, I rules) — TASK-BCK-040`
- Silence unfixable: `chore(lint): silence N ARG + M SIM violations with noqa`
- `ARG002` on interface methods → `# noqa: ARG002` on the def line (not `_ = arg`)
- Never use `--no-verify` to bypass lint gates

### OpenAPI Drift Gate
- Regenerate with `make openapi` after any router change
- Commit with `[openapi]` prefix — CI `openapi-drift.yml` watches for this token
- Schema lives at `docs/api/openapi.yaml`
- Schemathesis contract tests run against this schema (not a live DB)

### Push to Main
```bash
ALLOW_PUSH_MAIN=1 git push origin main   # Husky pre-push guard requires this env var
# Use Bash tool (not PowerShell) — ALLOW_PUSH_MAIN=1 is POSIX env syntax
```

---

## Testing Patterns

### Backend Tests (`apps/api/tests/`)
```
tests/
├── contract/schemathesis/   # OpenAPI contract tests — one file per router group
├── evals/                   # Real-document operability tests (C2PRO_AI_MOCK=1)
├── golden/                  # Golden regression tests
├── fixtures/
│   ├── documents/real/      # Real fixture documents (PDF, DOCX, TXT, BIN) + manifest.yaml
│   └── sdk_isolators.py     # Patch LangSmith/Anthropic SDK for tests
├── modules/hitl/            # HITL domain tests
└── unit/
    ├── core/ai/             # LLM client, langsmith unit tests
    ├── core/observability/  # Tracing decorator tests
    └── core/security/       # Secret channel, anonymizer tests
```

**Key patterns**:
- Skip real AI calls: `C2PRO_AI_MOCK=1 pytest`
- Contract tests skip if schema missing: `if not SCHEMA_PATH.exists(): pytest.skip(..., allow_module_level=True)`
- Schemathesis pattern: `_SCHEMA.include(path_regex=r"^/api/v1/<route>").parametrize()`
- Never mock settings singleton directly — use `monkeypatch` or `dependency_overrides`
- Mark tests: `@pytest.mark.contract`, `@pytest.mark.unit`, `@pytest.mark.operability`

### Frontend Tests (`apps/web/`)
```
src/tests/
├── wireframes/   # WF-01..WF-06 component structural tests (Vitest)
└── e2e/          # Playwright end-to-end tests
```

**Coverage targets**: 70%+ (enforced by CI coverage gates)

---

## Security Baseline

Every new feature must:
- [ ] Add `tenant_id` column to any new DB table
- [ ] Enable `FORCE ROW LEVEL SECURITY` + policy using direct `tenant_id` comparison (fail-closed)
- [ ] Create matching `supabase/tests/NN_<table>_rls.sql` verification test
- [ ] Run PII anonymizer (`pii_anonymizer_node` N2) before sending data to Claude
- [ ] Use `secrets.compare_digest()` for any shared-secret token comparison (never `!=`)
- [ ] Use `SecretStr` for secret fields in Pydantic settings
- [ ] Gate auth-required endpoints with `current_user: CurrentUser = Depends(get_current_user)`

---

## Multi-Agent / Worktree Patterns

- Worktrees live in `.worktrees/<branch-slug>/`
- Branch naming: `<agent>/<topic>` e.g. `coverage-gates/ai-codex`, `ops-docflow/backlog-reconcile`
- After merging, always audit with: `git log --oneline main..<branch> 2>/dev/null` — empty = merged
- Use `git diff --stat main...<branch>` to review what an unmerged branch adds
- Parallel agents get non-overlapping file sets to avoid conflicts

---

## CI / GitHub Actions

| Workflow | Trigger | Purpose |
|----------|---------|---------|
| `tests.yml` | PR + push | Full pytest + vitest suite |
| `openapi-drift.yml` | PR | Detect uncommitted schema drift |
| `wireframe-coverage.yml` | PR | Enforce WF-01..06 test coverage |
| `real-document-operability.yml` | PR + main | Real-doc corpus smoke tests |
| `golden-corpus-evals.yml` | PR | Golden regression guard |
| `qa-swarm.yml` | Manual | Multi-agent QA swarm |
| `frontend-ci.yml` | PR | ESLint + type-check + vitest |
| `deploy-staging.yml` | main push | Auto-deploy to staging |
| `deploy-production.yml` | Manual | Production deploy gate |
