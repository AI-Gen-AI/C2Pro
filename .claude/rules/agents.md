# Agent Orchestration

> **Role policy, not model inventory.** Functional roles and hard limits are durable. Model/terminal assignment is session-specific and comes from the active control/session configuration; do not treat this file as a live model roster.

## Real Delegate Roster & Guardrails

Roles are **functional and model-agnostic**. Capabilities and hard limits attach to the **role**, not the model — a model dispatched as `Auditor` is read-only for that task even if it holds write roles elsewhere.

Dispatch by **role + the session/control assignment actually in force**. Never infer the active model from a stale documentation table.

### Roles

| Role | Purpose / may do | Hard limits (MUST NOT) |
|---|---|---|
| **Orchestrator** | Owns dispatch, review gating and merge-readiness decisions; delegates canonical control reconciliation. | Never accept delegate narrative over git/CI truth; never override the active `.c2pro` merge policy; do not let ordinary workers mutate canonical control state. |
| **Backend** | Edit `apps/api/src` + Alembic migrations; run backend; push branches; open PRs. | No self-merge; no backlog edits inside code PRs. |
| **Frontend** | Edit `apps/web`; run web; push; open PRs. | No self-merge; no backlog edits. |
| **Full-Stack** | Cross-cutting features spanning `apps/api` + `apps/web`; push; open PRs. | No self-merge; no backlog edits. |
| **DevOps / Infra** | CI (`.github/workflows`), Docker, deploy, dependency bumps (`requirements.txt`), migration lifecycle; push; open PRs. | No self-merge; never weaken security/CI gates or skip hooks without explicit Orchestrator sign-off. |
| **Test / QA** | Tests only: `apps/api/tests` + test-infra (`_bootstrap.py`, `conftest.py`); run suites; RED-first; push; open PRs. | **No `src/` business-logic edits**; no self-merge; no backlog edits. |
| **Verification Auditor** | **READ-ONLY.** Read code, run read-only checks, produce written findings/reports. | **NEVER edit, commit, or push ANY file; never merge; never edit the backlog.** Report only. |
| **Reconciler** | Single writer for `.c2pro/control/` / work-queue reconciliation; may update durable docs in a dedicated documentation/control PR. | No unrelated product-code edits; never infer lifecycle promotion from worker completion alone. |

### Assignment

Runtime model/terminal assignment is **session-specific**. Resolve it from the active control/session configuration used by the orchestrator. Do not edit role policy merely because a model is reassigned.

### Shared guardrails (all roles)

- **No self-merge** — workers never merge their own change. Merge authorization/action follows the active `.c2pro` merge policy; when it is `human_merge`, the agent stops at merge-ready evidence.
- **Canonical control writes go only via the Reconciler** under `.c2pro/`. Durable documentation follows `docs/DOCUMENTATION_GOVERNANCE.md`; legacy backlogs/blackboard remain read-only compatibility references.
- **Verify CI green** (all required jobs) before declaring any task done — local pass is not sufficient.
- **Name the functional role** and use the model/terminal assigned by the active session/control configuration.
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
