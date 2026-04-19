---
name: c2pro-patterns
description: Coding patterns, workflows, and conventions extracted from C2Pro contract intelligence platform
version: 1.0.0
source: local-git-analysis
analyzed_commits: 200
repository: c2pro
stack: Python (FastAPI), TypeScript (Next.js), PostgreSQL, Neo4j
---

# C2Pro Development Patterns

Comprehensive guide to coding standards, workflows, and architecture patterns for the C2Pro contract intelligence platform.

## Project Overview

**C2Pro** is a contract intelligence platform combining AI-powered document analysis, knowledge graphs, and multi-agent orchestration for project risk assessment and stakeholder management.

**Tech Stack:**
- **Backend**: Python 3.11+, FastAPI, LangGraph, PostgreSQL, Neo4j
- **Frontend**: Next.js 16, React 19, TypeScript, Tailwind CSS, Radix UI
- **AI/ML**: Anthropic Claude (multi-agent), LangGraph workflows, RAG pipelines
- **Testing**: pytest (backend), Vitest + Playwright (frontend)
- **CI/CD**: GitHub Actions with multi-gate validation

## Commit Conventions

### Format: Conventional Commits (69.5% adherence)

C2Pro strictly follows **conventional commits** with scoped prefixes:

```
<type>(<scope>): <description>

[optional body]
```

### Commit Types (by frequency)

| Type | Usage | Purpose |
|------|-------|---------|
| `chore` | 22 commits | Maintenance, dependencies, tooling |
| `fix` | 10 commits | Bug fixes, error corrections |
| `docs` | 9 commits | Documentation updates |
| `test` | 8 commits | Test additions, test fixes |
| `feat` | 5 commits | New features, enhancements |
| `ci` | 5 commits | CI/CD workflow changes |
| `refactor` | 2 commits | Code restructuring without behavior change |
| `style` | 1 commit | Code formatting, linting |
| `perf` | 3 commits | Performance optimizations |

### Common Scopes

- **Feature scopes**: `(rag)`, `(hitl)`, `(qa)`, `(observability)`
- **Infrastructure**: `(ci)`, `(docker)`, `(postgres)`, `(infra)`
- **Module scopes**: `(core-ai)`, `(frontend)`, `(security)`, `(tests)`
- **Task tracking**: `(TD-01)`, `(P1-03)`, `(I13)` (technical debt, priorities, initiatives)

### Examples

```bash
# Feature with scope
feat(rag): implement document upload and RAG Q&A pipeline

# Bug fix with task ID
fix(TD-01): implement _is_cached_none in LLMResultCache

# CI improvement
ci(frontend): install full playwright browser set in e2e jobs

# Test with priority marker
test(qa-swarm): add P0 coverage gap unit tests for 5 critical modules

# Chore with dependency scope
chore(deps): bump the npm_and_yarn group across 2 directories with 1 update
```

### Special Commit Markers

- **🚀 MILESTONE**: Major feature completions
- **Task IDs**: `TD-XX` (technical debt), `P0/P1/P2` (priority), `I##` (initiative)

## Code Architecture

### Backend Structure (Python/FastAPI)

```
apps/api/src/
├── ai/                    # AI orchestration and agents
│   ├── agents/            # Multi-agent definitions
│   └── graph/             # LangGraph workflows
├── analysis/              # Core analysis domain
│   └── adapters/
│       ├── ai/            # AI service adapters
│       │   ├── agents/    # Specialized agents (risk, WBS, RACI)
│       │   └── tools/     # LangChain tools
│       ├── graph/         # Neo4j knowledge graph
│       └── http/          # HTTP/REST adapters
├── core/                  # Cross-cutting concerns
│   ├── middleware/        # Tenant isolation, auth
│   ├── ai/                # Core AI utilities
│   └── mcp/               # MCP server integration
├── documents/             # Document ingestion
├── projects/              # Project management
├── stakeholders/          # Stakeholder tracking
├── coherence/             # Coherence scoring
├── alerts/                # Alert system
└── shared_kernel/         # Shared utilities

apps/api/tests/
├── unit/                  # Unit tests (isolated)
├── integration/           # Integration tests (DB, external services)
├── e2e/                   # End-to-end workflow tests
└── conftest.py            # Shared pytest fixtures
```

### Frontend Structure (Next.js/TypeScript)

```
apps/web/
├── app/                   # Next.js App Router
│   ├── (app)/             # Main app routes (authenticated)
│   ├── (auth)/            # Auth routes (sign-in/up)
│   ├── dashboard/         # Dashboard pages
│   ├── demo/              # Demo/public pages
│   └── providers.tsx      # React Query + Clerk providers
├── components/            # React components
│   ├── alerts/            # Alert-related components
│   ├── auth/              # Auth components (RBAC, protected routes)
│   ├── coherence/         # Coherence dashboard components
│   ├── evidence/          # Evidence/validation components
│   ├── features/          # Feature-specific logic
│   ├── layout/            # Layout components (header, nav)
│   └── ui/                # Radix UI primitives + shadcn
├── lib/                   # Utilities and API clients
│   ├── api/               # Generated API client (orval)
│   └── utils.ts           # Helper functions
├── mocks/                 # MSW mock handlers
└── tests/                 # Vitest + Playwright tests
```

### Key Architectural Patterns

1. **Hexagonal Architecture (Backend)**
   - Domain logic in core modules
   - Adapters for external services (AI, Graph, HTTP, Persistence)
   - Dependency injection via FastAPI `Depends()`

2. **Multi-Agent AI Orchestration**
   - LangGraph state machines for workflows
   - Specialized agents: `risk_agent`, `wbs_agent`, `stakeholder_extractor`
   - Fallback client with retry/circuit-breaker (`FallbackAIClient`)

3. **Knowledge Graph Integration**
   - Neo4j for entity relationships
   - Graph-based reasoning for risk propagation
   - Hybrid vector + graph search

4. **Frontend State Management**
   - React Query for server state
   - Zustand for client state (minimal usage)
   - MSW for API mocking in tests

## Testing Patterns

### Python Testing (pytest)

**Framework**: pytest 7.0+ with async support (`asyncio_mode = "auto"`)

**Test Organization**:
```
tests/
├── unit/                  # Fast, isolated tests
│   ├── core/              # Core utilities
│   └── ai/                # AI logic (mocked)
├── integration/           # DB, external services
│   └── adapters/
└── conftest.py            # Shared fixtures
```

**Test Markers** (from `pyproject.toml`):
```python
@pytest.mark.unit          # Fast unit tests
@pytest.mark.integration   # Integration tests
@pytest.mark.e2e           # End-to-end workflows
@pytest.mark.ai            # AI tests (may call APIs)
@pytest.mark.critical      # P0 critical tests
@pytest.mark.security      # Security tests
@pytest.mark.red_phase     # TDD RED phase
@pytest.mark.green_phase   # TDD GREEN phase
```

**Coverage Requirements**:
- Minimum: **70%** (`fail_under = 70` in `pyproject.toml`)
- Target: **80%+** (per project guidelines)

**Naming Convention**:
```python
def test_{module}_{scenario}_{expected}():
    # e.g., test_llm_fallback_client_retries_on_rate_limit()
    pass
```

### TypeScript Testing (Vitest + Playwright)

**Unit/Integration**: Vitest + React Testing Library
```typescript
// Component test pattern
import { render, screen } from '@testing-library/react'
import { describe, it, expect } from 'vitest'

describe('UserCard', () => {
  it('displays user email when provided', () => {
    render(<UserCard user={{ email: 'test@example.com' }} />)
    expect(screen.getByText('test@example.com')).toBeInTheDocument()
  })
})
```

**E2E**: Playwright
```typescript
// apps/web/tests/e2e/login.spec.ts
test('user can log in and access dashboard', async ({ page }) => {
  await page.goto('/sign-in')
  await page.fill('[name="email"]', 'test@example.com')
  await page.click('button[type="submit"]')
  await expect(page).toHaveURL('/dashboard')
})
```

**Test Scripts** (from `package.json`):
```bash
npm run test              # Integration tests only
npm run test:all          # All tests
npm run test:e2e          # Playwright E2E
npm run test:coverage     # With coverage report
```

## Workflows

### 1. Adding a New Backend Feature

**Typical file change pattern** (from git analysis):

1. **Define domain logic**:
   ```
   apps/api/src/{domain}/entities.py
   apps/api/src/{domain}/use_cases.py
   ```

2. **Add HTTP adapter**:
   ```
   apps/api/src/{domain}/adapters/http/router.py
   apps/api/src/{domain}/adapters/http/schemas.py
   ```

3. **Write tests** (TDD approach):
   ```
   apps/api/tests/unit/{domain}/test_{use_case}.py
   apps/api/tests/integration/{domain}/test_{router}.py
   ```

4. **Update main app**:
   ```
   apps/api/src/main.py  # Register router
   ```

5. **Commit**:
   ```bash
   git add .
   git commit -m "feat({domain}): add {feature} with {X} tests"
   ```

### 2. Database Migration Workflow

**Pattern observed**: No explicit Alembic migrations in recent commits
- Schema changes handled via ORM models
- One `chore(alembic)` commit suggests migrations exist but are infrequent

**Inferred workflow**:
```bash
# Modify ORM model
apps/api/src/{domain}/entities.py

# Generate migration (if using Alembic)
alembic revision --autogenerate -m "add {table/column}"

# Apply migration
alembic upgrade head
```

### 3. Frontend Component Addition

**Pattern** (from frequently changed files):

1. **Create component**:
   ```
   apps/web/components/{feature}/{ComponentName}.tsx
   ```

2. **Add tests**:
   ```
   apps/web/components/{feature}/{ComponentName}.test.tsx
   ```

3. **Export from index**:
   ```
   apps/web/components/{feature}/index.ts
   ```

4. **Update page**:
   ```
   apps/web/app/{route}/page.tsx
   ```

5. **Regenerate API client** (if backend API changed):
   ```bash
   npm run generate:api
   ```

### 4. Pull Request Workflow

**Branch naming**: `{agent}/{description}-{hash}`
- Examples: `claude/fix-cache-fallback-tests-obvZN`, `codex/enforce-coverage-gate-in-pr-checks`

**PR merge pattern** (24 PRs in 200 commits = 12% of commits):
- Squash merge strategy (inferred from linear history)
- PR titles become commit messages
- Automated checks: `secrets-scan`, `s5-core-ai-gates`, `frontend-e2e`

**PR checklist** (inferred from CI workflow):
```markdown
- [ ] All tests pass (`pytest`, `vitest`, `playwright`)
- [ ] Coverage gate met (70%+)
- [ ] Secrets scan passed (gitleaks)
- [ ] Type checking passed (`mypy`, `tsc`)
- [ ] Linting passed (`ruff`, `eslint`)
```

### 5. Multi-Agent QA Workflow

**Pattern observed**: `feat(qa)` commits with autonomous test generation

**Workflow**:
1. Run QA audit to identify coverage gaps
2. Generate test swarm tasks (`test_workflow_routing_swarm.py`)
3. Mark tests as `@pytest.mark.red_phase` (TDD RED)
4. Implement feature to pass tests
5. Mark tests as `@pytest.mark.green_phase` (TDD GREEN)

## Code Quality Standards

### Python (Ruff + MyPy)

**Configuration** (from `pyproject.toml`):
```toml
[tool.ruff]
target-version = "py311"
line-length = 100

[tool.ruff.lint]
select = ["E", "W", "F", "I", "B", "C4", "UP", "ARG", "SIM"]
ignore = ["E501", "B008", "B904"]

[tool.mypy]
strict = true
disallow_untyped_defs = true
```

**Code style**:
- **Imports**: Auto-sorted with `isort` (first-party = `["src"]`)
- **Type hints**: Required on all function signatures
- **Line length**: 100 characters
- **Quotes**: Double quotes (enforced by Ruff formatter)

### TypeScript (ESLint + TypeScript)

**Configuration**:
- ESLint with Next.js config (`eslint-config-next`)
- TypeScript 5.3.3 with strict mode
- Prettier (inferred from consistent formatting)

**Conventions**:
- **Imports**: Absolute imports via `@/` alias
- **Components**: `.tsx` extension, PascalCase names
- **Hooks**: `use*` prefix, `.ts` or `.tsx`
- **Utils**: `.ts` extension, camelCase functions

### API Contract Validation

**Pattern**: Contract tests for API/frontend alignment
```python
@pytest.mark.contract
def test_documents_entities_contract():
    """Verify GET /api/v1/projects/{id}/documents returns expected schema."""
    # Test API response matches frontend expectations
```

**OpenAPI schema validation**:
```bash
npm run verify:openspec  # Validates OpenAPI spec consistency
npm run generate:api:check  # Ensures generated client is up-to-date
```

## CI/CD Pipeline

### GitHub Actions Workflows

**File**: `.github/workflows/tests.yml`

**Jobs** (multi-gate validation):
1. **Secrets Scan** (gitleaks) - Prevents credential leaks
2. **S5 Core AI Gates** - Backend tests (I10-I12 initiatives + security)
3. **Frontend E2E** - Playwright tests
4. **Coverage Gate** - Enforces 70%+ coverage

**Triggers**:
- Push to `main`, `develop`
- Pull requests to `main`, `develop`
- Manual dispatch (`workflow_dispatch`)

**Timeout**: 10-15 minutes per job

## Dependencies Management

### Backend (Python)

**File**: `apps/api/requirements.txt`
- No `pyproject.toml` dependencies section (uses `requirements.txt`)
- Frequent updates: `fix(ci): add psycopg dependency`, `chore(deps): bump ...`

**Update pattern**:
```bash
# Add dependency
echo "new-package==1.0.0" >> apps/api/requirements.txt

# Install
pip install -r apps/api/requirements.txt

# Commit
git commit -m "chore(deps): add new-package for {reason}"
```

### Frontend (npm/pnpm)

**Package manager**: npm (primary), pnpm (lock file exists)
- `package-lock.json` and `pnpm-lock.yaml` both tracked
- Frequent `chore(deps): bump the npm_and_yarn group` commits

**Dependency updates**:
- Automated via Dependabot (24 commits in recent history)
- Group updates for security patches

## Security Practices

### Secrets Management

**Pattern**: Environment variables + gitleaks scanning
- `.env.example` checked in (no secrets)
- Gitleaks in CI prevents credential commits
- Clerk for authentication (API keys in env)

### Authentication/Authorization

**Backend**:
- Clerk JWT validation
- Tenant isolation middleware (`core/middleware/tenant_isolation.py`)
- RBAC tests: `test_alerts_router_authz.py`

**Frontend**:
- Clerk `<ProtectedRoute>` component
- RBAC components: `rbac-components.tsx`

### Security Testing

**Markers**: `@pytest.mark.security` for critical security tests
**Example**:
```python
@pytest.mark.security
def test_tenant_isolation_prevents_cross_tenant_access():
    # Verify tenant A cannot access tenant B's data
    pass
```

## Documentation Patterns

### Frequently Updated Docs

| File | Purpose | Update Frequency |
|------|---------|------------------|
| `docs/audits/REORGANIZATION_PLAN_CHECKLIST.md` | 39 changes | Project reorganization tracking |
| `context/C2PRO_TDD_BACKLOG_v1.0.md` | 15 changes | TDD backlog management |
| `docs/INFRASTRUCTURE_RECOVERY_TRACKER.md` | 10 changes | Infrastructure issue tracking |
| `docs/audits/multi_agent_qa_audit_report.md` | 7 changes | QA audit results |

### Documentation Workflow

**Pattern**: Docs updated in parallel with code changes
```bash
# Example from git log
feat(P1-03): add retry/circuit-breaker to FallbackAIClient + 22 tests
docs(audit): add implementation checklist to QA audit report
```

**Audit-driven development**:
1. Run technical audit → Generate report
2. Create checklist from audit findings
3. Implement fixes → Update checklist
4. Commit both code + docs

## AI-Specific Patterns

### Multi-Agent Architecture

**Agents** (from `apps/api/src/analysis/adapters/ai/agents/`):
- `risk_agent.py` - Risk identification
- `wbs_agent.py` - Work breakdown structure
- `stakeholder_extractor.py` - Stakeholder detection
- `raci_generator.py` - RACI matrix generation

**Orchestration**:
```python
# LangGraph workflow pattern
from langgraph.graph import StateGraph

workflow = StateGraph(AnalysisState)
workflow.add_node("extract_risks", risk_agent)
workflow.add_node("generate_wbs", wbs_agent)
workflow.add_edge("extract_risks", "generate_wbs")
```

### Cost Control

**Pattern**: `cost_controller.py` monitors LLM API usage
- Token tracking
- Budget enforcement
- Usage analytics

**Fallback strategy**: `llm_fallback_client.py`
- Retry with exponential backoff
- Circuit breaker pattern
- Model fallback (Sonnet → Haiku)

## Common Anti-Patterns to Avoid

Based on recent fixes in git history:

1. **❌ Re-exports creating circular dependencies**
   ```python
   # BAD: Importing from __init__.py re-export
   from src.analysis.adapters.ai import CostController

   # GOOD: Direct import
   from src.analysis.adapters.ai.cost_controller import CostController
   ```
   *Fix*: `Resolve TD-02 cost controller shim imports`

2. **❌ Excluding test files from type checking**
   ```yaml
   # BAD: Ignoring type errors in tests
   exclude: ["tests/**/*.py"]

   # GOOD: Type-check tests
   include: ["src/**/*.py", "tests/**/*.py"]
   ```
   *Fix*: `fix(ci): typecheck test files instead of excluding them`

3. **❌ Missing test markers for critical paths**
   ```python
   # BAD: No priority marker
   def test_authentication():
       pass

   # GOOD: Explicit criticality
   @pytest.mark.critical
   @pytest.mark.security
   def test_authentication():
       pass
   ```
   *Fix*: `Mark QA audit items done and tag P0 swarm tests red_phase`

4. **❌ Hardcoding test data paths**
   ```python
   # BAD: Absolute path
   doc = load_pdf("/users/dev/test.pdf")

   # GOOD: Relative to test fixture
   doc = load_pdf(tmp_path / "test.pdf")
   ```

## Related Skills

- `python-patterns` - Python idioms and best practices
- `python-testing` - pytest patterns and fixtures
- `frontend-patterns` - React/Next.js patterns
- `typescript-reviewer` - TypeScript code review standards
- `springboot-tdd` - TDD methodology (applicable to FastAPI)
- `api-design` - REST API conventions

---

**Generated**: 2026-03-23
**Analysis Period**: Last 200 commits (2026-01 to 2026-03)
**Project Phase**: Pre-release (Gate 7 certification)
**Maintained By**: Everything Claude Code skill-create

*Part of [Everything Claude Code](https://github.com/affaan-m/everything-claude-code)*
