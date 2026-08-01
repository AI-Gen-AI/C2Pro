# Agent Orchestration

> **Two rosters live in this file.** The **Real Delegate Roster** below governs the multi-terminal orchestration (external models run in the user's terminals, coordinated by the Orchestrator). The **Available Agents** table further down lists in-session Claude Code sub-agent types. When they conflict, the Real Delegate Roster wins for orchestration decisions.

## Real Delegate Roster & Guardrails

Roles are **functional and model-agnostic**. Capabilities and hard limits attach to the **role**, not the model — a model dispatched as `Auditor` is read-only for that task even if it holds write roles elsewhere. The assignment table (which model currently fills each role) is a swappable layer: more terminals/models can be added and roles reassigned without changing the role definitions.

Always dispatch by **role + currently-assigned model** (e.g. "Test/QA → DeepSeek"), never by a generic "an LLM".

### Roles

| Role | Purpose / may do | Hard limits (MUST NOT) |
|---|---|---|
| **Orchestrator** | Owns dispatch, the review-gate, merges, and delegates backlog reconciliation. Gates every PR (8-step). | Never self-merge by proxy; never accept a delegate report over git truth; never edit the backlog in-place (routes to Reconciler). |
| **Backend** | Edit `apps/api/src` + Alembic migrations; run backend; push branches; open PRs. | No self-merge; no backlog edits inside code PRs. |
| **Frontend** | Edit `apps/web`; run web; push; open PRs. | No self-merge; no backlog edits. |
| **Full-Stack** | Cross-cutting features spanning `apps/api` + `apps/web`; push; open PRs. | No self-merge; no backlog edits. |
| **DevOps / Infra** | CI (`.github/workflows`), Docker, deploy, dependency bumps (`requirements.txt`), migration lifecycle; push; open PRs. | No self-merge; never weaken security/CI gates or skip hooks without explicit Orchestrator sign-off. |
| **Test / QA** | Tests only: `apps/api/tests` + test-infra (`_bootstrap.py`, `conftest.py`); run suites; RED-first; push; open PRs. | **No `src/` business-logic edits**; no self-merge; no backlog edits. |
| **Verification Auditor** | **READ-ONLY.** Read code, run read-only checks, produce written findings/reports. | **NEVER edit, commit, or push ANY file; never merge; never edit the backlog.** Report only. |
| **Reconciler** | Edit `C2PRO_MASTER_BACKLOG.md` + docs markdown via a committed `docs(backlog)` PR. Dispatched in-session by the Orchestrator. | No `src/` or `tests/` edits; no self-merge (Orchestrator gates). |

### Assignment (current — swappable)

| Role | Assigned model / terminal |
|---|---|
| Orchestrator | Fable (Opus 4.8), in-session |
| Backend | Codex · Sonnet |
| Frontend | Sonnet |
| Full-Stack | Codex |
| DevOps / Infra | Codex |
| Test / QA | DeepSeek |
| Verification Auditor | Gemini |
| Reconciler | Haiku (dispatched in-session by Orchestrator) |

One model may hold multiple roles; roles may be reassigned across terminals/models. When a new terminal/model is added, register it here against a role.

### Shared guardrails (all roles)

- **No self-merge** — the Orchestrator gates and merges every PR after verifying scope, diff-vs-criteria, and CI-green on all required jobs.
- **Backlog & markdown edits go only via the Reconciler** in a committed PR — never in-place, never bundled into a code PR (the shared worktree resets and wipes uncommitted edits).
- **Verify CI green** (all required jobs) before declaring any task done — local pass is not sufficient.
- **Name the real role + assigned model** on every dispatch; never a generic "an LLM".
- **High-blast-radius files** (`apps/api/tests/_bootstrap.py`, `conftest.py`, `.github/workflows/ci.yml`, `apps/api/alembic/env.py`, `pyproject.toml`, `requirements.txt`) get extra scrutiny and an explicit behavior-preserving check.

## Available Agents

Located in `~/.claude/agents/` or `.claude/agents/`, depending on install level:

| Agent                | Purpose                 | When to Use                   |
| -------------------- | ----------------------- | ----------------------------- |
| planner              | Implementation planning | Complex features, refactoring |
| architect            | System design           | Architectural decisions       |
| tdd-guide            | Test-driven development | New features, bug fixes       |
| code-reviewer        | Code review             | After writing code            |
| security-reviewer    | Security analysis       | Before commits                |
| build-error-resolver | Fix build errors        | When build fails              |
| e2e-runner           | E2E testing             | Critical user flows           |
| refactor-cleaner     | Dead code cleanup       | Code maintenance              |
| doc-updater          | Documentation           | Updating docs                 |
| rust-reviewer        | Rust code review        | Rust projects                 |

## Immediate Agent Usage

No user prompt needed:

1. Complex feature requests - Use **planner** agent
2. Code just written/modified - Use **code-reviewer** agent
3. Bug fix or new feature - Use **tdd-guide** agent
4. Architectural decision - Use **architect** agent

## Parallel Task Execution

ALWAYS use parallel Task execution for independent operations:

```markdown
# GOOD: Parallel execution

Launch 3 agents in parallel:

1. Agent 1: Security analysis of auth module
2. Agent 2: Performance review of cache system
3. Agent 3: Type checking of utilities

# BAD: Sequential when unnecessary

First agent 1, then agent 2, then agent 3
```

## Multi-Perspective Analysis

For complex problems, use split role sub-agents:

- Factual reviewer
- Senior engineer
- Security expert
- Consistency reviewer
- Redundancy checker
