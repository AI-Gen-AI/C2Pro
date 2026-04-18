# SESSION 2026-04-15 — Workspace Surface Audit

**Status:** Plan (not yet actioned)
**Scope:** Harness / tooling / MCP / hook gaps in C2Pro. Not a product backlog item — operational setup.
**Consolidate into:** `backlogs/DEV_DEVOPS.md` and `backlogs/SEC_SECURITY.md` once items are turned into real tasks with `TASK-*` IDs and added to `C2PRO_MASTER_BACKLOG.md`.

---

## Current Surface (snapshot)

**Harness**
- `~/.claude/settings.json`: model=opus, 1 plugin (`everything-claude-code@1.10.0`), **no hooks**, **no MCP servers**.
- No `.mcp.json`, no `AGENTS.md`, no `.codex` in repo.
- 3 worktrees active under `.claude/worktrees/`.
- Project-local `.claude/rules/` with 11 files, including two CRITICAL rules (backlog sync, no-new-task-docs) and unused `hooks.md` guidance.

**Env-backed services** (names only)
- AI: `ANTHROPIC_API_KEY`, Langsmith (`LANGSMITH_*`, `LANGCHAIN_TRACING_V2`), suspicious `OPEN_AI_APY_KEY` (likely typo)
- Data: Supabase, `DATABASE_URL`, Upstash Redis
- Auth: Clerk
- Storage: Cloudflare R2
- Notifications: Resend, SMTP, `BUDGET_ALERT_WEBHOOK_URL`
- Observability: Sentry (front + back)
- Feature flags: 7 `FEATURE_*` toggles

**Parity already provided by ECC**
- Python/FastAPI review loop (`python-reviewer`, `python-patterns`, `python-testing`, `tdd-guide`, `security-reviewer`)
- Next.js/TS review loop (`frontend-patterns`, `frontend-design`, `nextjs-turbopack`, `typescript-reviewer`, `e2e-runner`)
- DB review (`database-reviewer`, `postgres-patterns`, `database-migrations`)
- Notifications (`email-ops`, `unified-notifications-ops`)

## Primitive-only gaps

| Capability | Missing |
|---|---|
| Supabase RLS (Gates 1–4) | No audit skill covering CTO gate checklist per new table |
| Alembic ↔ Supabase CLI migrations | No drift detector |
| Clerk auth | No auth-ops workflow |
| Langsmith tracing | No trace-triage skill |
| Sentry | No triage → backlog workflow |
| Feature flags | No inventory / parity check between `apps/api` and `apps/web` |
| Backlog-sync rule | Enforced only by prose, not a hook |
| Hook automation | `.claude/rules/hooks.md` exists but no hooks configured |
| Worktree lifecycle | 3 live, no orchestration skill |

## Missing integrations

- **No MCP servers at all.** High-value candidates: Supabase MCP, GitHub MCP, Sentry MCP, Playwright MCP. Context7/Exa available at plugin level but not enabled here.
- **No LSP config** — Python/TS errors only surface via `make typecheck`.
- **Secret hygiene**: `OPEN_AI_APY_KEY` in `.env` appears to be a typo; confirm unused and remove.

---

## Plan — Top 5 moves (ordered by impact)

### 1. Wire PostToolUse + Stop hooks
**Why:** Nothing enforced today. `.claude/rules/hooks.md` already documents the pattern.
**How:** Populate `hooks:` block in `~/.claude/settings.json` (or project `.claude/settings.json`):
- PostToolUse `Write|Edit` on `**/*.py` → `ruff check --fix` + `black`
- PostToolUse `Write|Edit` on `apps/web/**/*.{ts,tsx,css}` → `pnpm prettier --write` + `pnpm eslint --fix`
- Stop → `cd apps/api && ruff check && mypy src` + `pnpm -C apps/web tsc --noEmit`
**Acceptance:** Edits on both apps auto-format; Stop fails if type errors present.

### 2. `c2pro-backlog-guard` Stop hook
**Why:** Operationalizes `CRITICAL_BACKLOG_REQUIREMENT.md`.
**How:** Stop hook script that inspects session diff; if any file under `apps/`, `core/`, `infrastructure/`, `supabase/`, or `backlogs/BCK_*.md` changed and `C2PRO_MASTER_BACKLOG.md` is untouched, exit 2 with instructions.
**Acceptance:** Attempting to Stop without backlog update blocks the session.

### 3. Enable Supabase + GitHub MCP servers
**Why:** Directly mitigates dual-migration drift risk and satisfies `development-workflow.md` Phase 0 (GitHub code search first).
**How:** Create `.mcp.json` at repo root with `supabase` and `github` MCP entries; add `enabledMcpjsonServers` to project settings. Keys already in `.env`.
**Acceptance:** `gh search code` and direct Supabase SQL/RLS introspection callable from Claude Code without shelling out.

### 4. `c2pro-rls-audit` skill
**Why:** Single highest-risk surface. Gate 1–4 are the project's security foundation.
**How:** Skill that, given a table name, runs the CTO Gate checklist: policy exists, tenant filter verified (`tenant_id` or equivalent), service-role vs anon split correct, pytest RLS coverage present in `apps/api/tests/`. Composes `database-reviewer` + `postgres-patterns` with C2Pro-specific gates.
**Acceptance:** `/c2pro-rls-audit <table>` produces PASS/FAIL per gate with remediation pointers.

### 5. `c2pro-migration-drift` skill
**Why:** `CLAUDE.md` explicitly flags dual-migration gotcha.
**How:** Skill diffs `apps/api/alembic/versions/` against `supabase/migrations/`; reports divergence (tables, columns, policies present in one but not the other). Later: wire as pre-commit hook.
**Acceptance:** Running the skill prints a structured drift report or "clean".

---

## Deferred (do only if requested)

- Sentry MCP + triage-to-backlog skill
- Langsmith trace-triage skill
- Clerk auth-ops skill
- Feature-flag inventory/parity skill
- Worktree lifecycle skill
- Playwright MCP binding

## Housekeeping

- Confirm `OPEN_AI_APY_KEY` in `.env` is unused; rename to `OPENAI_API_KEY` or delete.
- `package.json` name field is literally `"package.json"` — cosmetic fix.

---

## Next step after this plan

User wants to analyze the full contract/document analysis flow and coherence score pipeline (`apps/api/src/analysis/adapters/graph/` N1–N17 + `coherence/`). That walkthrough comes next, not part of this plan.
