# C2Pro VPS Agent Fabric v1 — Interim Design

**Date:** 2026-09-09  
**Status:** Approved architecture; implementation pending  
**Scope:** Interim execution fabric for C2Pro engineering agents until AI-Gen Agent Academy becomes the canonical orchestrator.

## 1. Purpose

C2Pro development currently depends too heavily on a Windows laptop for long-running CLI sessions, local worktrees, Docker-backed security gates, and multiple AI coding agents. This has created operational friction: memory pressure, lost sessions after laptop shutdowns, duplicated worktrees, and manual coordination overhead.

The goal of VPS Agent Fabric v1 is to move long-running agent execution to the existing Linux VPS while preserving the governance model already introduced by G1/G2:

- MASTER/Planner remains the sole authority for task assignment and canonical planning state.
- Workers do not create or destroy workspaces.
- One persistent workspace is assigned to each agent.
- One active writer task per workspace.
- Workers return structured evidence; they do not update legacy planning files.
- Independent review remains mandatory before merge for security- or architecture-sensitive changes.

This is an interim execution substrate, not a replacement for AI-Gen Agent Academy. Academy should later assume orchestration over the same workers/workspaces rather than forcing another migration.

## 2. Design principles

1. **Persistent execution, disposable tasks.** tmux sessions and workspaces persist; individual task branches and agent prompts remain bounded.
2. **Single writer per workspace.** A worker may edit only its assigned workspace and only one branch/task at a time.
3. **No autonomous workspace lifecycle.** Workers cannot create/remove/reset worktrees or clean untracked files. Workspace lifecycle belongs to MASTER/orchestrator.
4. **Cloud coordination, VPS execution.** MASTER coordinates from ChatGPT; heavy CLI execution runs on the VPS.
5. **Docker for infrastructure, not agent shells.** PostgreSQL, Redis, gates, MCPs, and test dependencies may run in Docker. Claude/Codex/Gemini/OpenCode run natively on the VPS unless a later isolation requirement justifies containerization.
6. **Fail closed on workspace mismatch.** Any branch/path/task mismatch returns `WORKSPACE_GUARD_FAILURE` and stops.
7. **Explicit resource governance.** Persistent sessions do not imply unlimited concurrency.
8. **No secret sprawl.** Provider credentials live in protected per-agent environment files or provider-native auth stores, never in the repository or shared shell history.
9. **Auditability over convenience.** Every task must leave task/branch/HEAD/log evidence sufficient for post-run review.
10. **Academy-compatible boundaries.** Names, workspace ownership, structured result transport, and locks should be reusable by Academy.

## 3. Target architecture

```text
ChatGPT / MASTER
      |
      | task specification / review / decisions
      v
VPS: C2Pro Agent Fabric

  /srv/c2pro/
    control/                    canonical checkout used by orchestrator only
    workspaces/
      claude/                   persistent workspace
      codex/                    persistent workspace
      gemini/                   persistent workspace
      opencode/                 persistent workspace
    sessions/
      state/                    machine-readable session/task metadata
      logs/                     append-only task logs
    locks/
      docker-integration.lock
      publish.lock
    env/                        protected provider/runtime env files
    scripts/                    fabric bootstrap/guard/dispatch helpers

  tmux sessions:
    c2pro-claude
    c2pro-codex
    c2pro-gemini
    c2pro-opencode

  Docker:
    PostgreSQL test services
    Redis
    C2Pro integration dependencies
    MCP servers where containerization is useful (e.g. Sonar)
```

## 4. Agent roles

### 4.1 Claude

Primary use:
- architecture review
- cross-cutting code review
- Sonar/MCP investigations
- difficult debugging and design validation

Default posture:
- read-only reviewer unless explicitly assigned writer status by MASTER

### 4.2 Codex

Primary use:
- independent implementation review
- TDD/security verification
- focused implementation slices when explicitly assigned
- regression and invariant validation

Default posture:
- reviewer for security/architecture-sensitive work

### 4.3 Gemini

Primary use:
- bounded implementation slices
- test creation
- refactors with clear acceptance criteria
- CI/harness fixes

Default posture:
- writer when assigned a branch/task

### 4.4 OpenCode

Primary use:
- fallback execution path
- provider routing (e.g. NVIDIA/Nemotron/OpenRouter when configured)
- independent implementation or review when primary providers are unavailable

Default posture:
- writer/reviewer according to assigned task

### 4.5 MASTER

MASTER remains responsible for:
- selecting the next task
- deciding which agent is writer/reviewer
- setting expected branch/workspace/HEAD
- approving scope changes
- deciding whether findings are blockers
- authorizing publication/merge
- reconciling post-merge state through G2

No worker may self-promote to MASTER responsibilities.

## 5. Workspace model

Each agent receives exactly one persistent Git workspace under `/srv/c2pro/workspaces/<agent>`.

Rules:
- Workspaces are created only by the fabric bootstrap/orchestrator.
- Workers may not run `git worktree add/remove`, `git clean`, destructive `git reset`, or delete another workspace.
- Before every task the dispatcher verifies:
  - absolute workspace path
  - expected branch
  - expected base/HEAD
  - clean/allowed dirty state
  - assigned task ID
- A mismatch stops execution with `WORKSPACE_GUARD_FAILURE`.
- A workspace may have only one active writer task.
- Reviewers may inspect remote PRs or a dedicated read-only checkout, but must not write into a workspace with an active writer lock.

The fabric does not rely on agents remembering these rules; guard scripts enforce them before dispatch.

## 6. tmux session model

Four persistent tmux sessions are created once:

- `c2pro-claude`
- `c2pro-codex`
- `c2pro-gemini`
- `c2pro-opencode`

Each session starts in its assigned workspace and loads only that agent's environment.

A tmux session is persistent execution state, not canonical task state. After VPS reboot, processes may be gone; therefore each active task must also be recorded under `/srv/c2pro/sessions/state/` with at least:

```yaml
schema: c2pro-agent-session-v1
agent: gemini
workspace: /srv/c2pro/workspaces/gemini
task_id: C2PRO-...
branch: ...
base_sha: ...
expected_head: ...
mode: writer|reviewer
started_at: ...
status: running|stopped|completed|failed
log_file: ...
```

This file is operational state only; it is not canonical planning state and must not replace `.c2pro/control/*`.

## 7. Resource governance

The VPS has sufficient capacity for a small multi-agent fabric, but concurrency must be bounded.

Initial limits:
- maximum **2 heavy writer/analysis agents** running simultaneously
- optional **1 lightweight reviewer** in parallel if system memory remains healthy
- maximum **1 Docker-heavy integration/security gate** at a time via `docker-integration.lock`
- no unbounded subagent spawning from workers

The bootstrap must add or verify emergency swap without replacing existing memory management. Swap is a safety net, not capacity for sustained multi-agent execution.

The fabric should expose a lightweight status command reporting:
- total/free memory
- swap usage
- load average
- active tmux sessions
- active writer locks
- Docker container count
- disk usage under `/srv/c2pro`

No hard-coded CPU/RAM cgroup quotas are required in v1 unless measurement shows contention.

## 8. Docker boundary

Docker is used for infrastructure and test isolation, not as the default runtime for AI CLIs.

Allowed uses:
- PostgreSQL/Redis test services
- disposable DB/security gates
- C2Pro API/test containers when repository tooling expects them
- MCP services such as Sonar where containerization simplifies deployment

Security rule:
- Workers do not receive unrestricted Docker socket access by default.
- Any helper that runs Docker-heavy tests must use the global integration lock.
- If an agent requires Docker, it invokes approved fabric scripts rather than arbitrary privileged container commands where practical.

Direct Docker socket delegation to all four agents is out of scope for v1 because it effectively grants host-level privilege.

## 9. Provider authentication and secrets

Provider credentials are isolated per agent.

Requirements:
- no secrets committed to Git
- no provider tokens embedded in prompts or structured result files
- environment files under `/srv/c2pro/env/` use owner-only permissions (`chmod 600`)
- shell history must not contain raw secrets
- provider-native OAuth/device login is preferred where supported
- API-key providers use protected env files or provider-native credential stores

Expected integrations:
- Codex CLI
- Claude Code
- Gemini CLI (`GOOGLE_CLOUD_PROJECT`/`GOOGLE_CLOUD_PROJECT_ID` persisted when required)
- OpenCode with configured fallback providers such as NVIDIA/Nemotron/OpenRouter when available

Credentials for production databases, Railway, Supabase, Sonar, GitHub, or other infrastructure remain separate from model-provider credentials.

## 10. Git and publication model

Workers implement locally in their assigned workspace and may commit locally when the task explicitly permits it.

Default worker permissions:
- read repository
- edit assigned scope
- run tests
- commit locally

Default worker prohibitions:
- push unless task explicitly authorizes publication
- merge
- force-push unless MASTER explicitly authorizes a rebase/reconstruction operation
- update planning files
- create/delete worktrees

Publication is serialized using `publish.lock` where needed.

The expected lifecycle remains:

```text
MASTER task
  -> worker implementation
  -> structured implementation-result-v1
  -> publication / PR
  -> CI
  -> independent reviewer
  -> MASTER decision
  -> merge
  -> G2 reconciliation
```

## 11. Structured task dispatch

The interim fabric uses a small task envelope so prompts remain reproducible.

Minimum task fields:

```yaml
schema: c2pro-agent-task-v1
task_id: C2PRO-...
agent: gemini
mode: writer
workspace: /srv/c2pro/workspaces/gemini
branch: fix/...
base_sha: ...
expected_start_head: ...
scope:
  allowed_paths: []
  forbidden_paths: []
commands:
  verification: []
authorizations:
  commit: true
  push: false
  merge: false
result_schema: c2pro-implementation-result-v1
```

A dispatch helper validates this envelope before sending the task to a tmux pane.

The v1 dispatcher may still require the user to paste one MASTER-generated command into SSH. Fully autonomous ChatGPT-to-VPS dispatch is explicitly deferred to Academy or a later secure bridge.

## 12. Logging and traceability

Each task receives an append-only log file:

`/srv/c2pro/sessions/logs/<timestamp>-<agent>-<task_id>.log`

Logs should capture:
- dispatch envelope hash
- starting branch and HEAD
- command output from the agent session where practical
- final structured return
- exit status

Logs must not contain secrets. Sanitization of provider/system credentials is required before long-term retention.

Log rotation in v1:
- retain detailed task logs for 30 days
- retain compact session metadata longer if useful
- compress old logs
- never allow logs to consume the root filesystem unchecked

## 13. Reboot and recovery

A VPS reboot must not require reconstructing the development state manually.

On boot or manual recovery:
1. verify `/srv/c2pro` filesystem and permissions
2. verify repository/workspaces exist
3. recreate missing tmux sessions
4. do **not** automatically resume an interrupted writer task
5. inspect session state files and mark interrupted tasks `stopped`
6. require MASTER to decide resume/retry/rebase

Automatic task continuation after reboot is out of scope because stale branch/remote/CI evidence may make blind continuation unsafe.

## 14. Installation strategy

The bootstrap is idempotent and must not disturb existing VPS services such as OpenClaw, Qdrant, backups, or unrelated Docker containers.

It may install/verify:
- git
- gh
- tmux
- jq/yq
- Node.js LTS / npm where required by CLIs
- Python tooling needed by repository scripts
- Codex CLI
- Claude Code
- Gemini CLI
- OpenCode
- Docker client prerequisites already compatible with the host

It must not:
- reinstall Docker destructively
- alter existing firewall rules without a separate reviewed task
- delete existing containers/volumes/networks
- move existing OpenClaw/Qdrant data
- rotate provider credentials
- change production deployment configuration

## 15. Sonar/MCP pilot

The first operational pilot should use PR #604 tooling closeout because it is read-heavy and bounded.

Pilot sequence:
1. Claude session: Sonar MCP read-only issue inventory/classification
2. Codex session: Codecov patch coverage diagnosis
3. MASTER consolidates findings
4. one designated writer receives any necessary changes
5. CI/review/merge proceeds normally

This pilot validates:
- simultaneous reviewer sessions
- persistent tmux continuity
- structured logs
- locks
- repository/workspace guards
- provider authentication

## 16. Migration path to Academy

Agent Fabric v1 is intentionally thin.

Academy should later replace:
- manual SSH dispatch
- hand-maintained tmux task state
- simple resource locks
- manual result collection

Academy should reuse:
- persistent agent identities
- workspace ownership model
- structured task envelopes
- structured implementation results
- result/review/merge lifecycle
- provider configuration
- VPS execution capacity

No v1 component should become a competing planning/control plane.

## 17. Out of scope

Not part of v1:
- building a generic multi-agent framework
- autonomous merge approval
- autonomous production deployment
- replacing G1/G2 control state
- dynamic Kubernetes scheduling
- per-agent Docker-in-Docker environments
- unrestricted Docker socket access
- implementing Academy itself
- moving production C2Pro services solely for convenience
- redesigning C2Pro application architecture

## 18. Acceptance criteria

V1 is complete when all of the following are proven:

1. `/srv/c2pro` structure exists with correct ownership/permissions.
2. Four persistent workspaces exist and are independently guarded.
3. Four tmux sessions can be recreated idempotently.
4. Codex, Claude, Gemini, and OpenCode each execute a read-only smoke task.
5. At least two agents can operate concurrently without memory instability.
6. A writer task cannot start in the wrong workspace/branch/HEAD.
7. Workers cannot create/delete worktrees through the supported dispatch path.
8. Docker integration lock serializes heavy DB/security test runs.
9. Session/task metadata survives disconnects and enables post-run reconstruction.
10. Logs are written without provider/database secrets.
11. VPS reboot recovery recreates sessions but does not blindly resume stale tasks.
12. Sonar/Codecov pilot for #604 can be performed from VPS sessions.
13. Existing OpenClaw/Qdrant/backup workloads remain operational.
14. No production deployment configuration is changed as part of fabric bootstrap.
15. The structure is compatible with later Academy takeover without another workspace migration.

## 19. Rollback

Rollback of the fabric must be non-destructive to C2Pro and existing VPS services.

Procedure:
- stop `c2pro-*` tmux sessions
- archive `/srv/c2pro/sessions/logs`
- remove only fabric-created workspace directories after confirming no unpushed work
- remove fabric-specific env files
- uninstall agent CLIs only if desired
- leave GitHub repository, Docker engine, OpenClaw, Qdrant, existing containers, and production services untouched

No rollback step may run automatically without explicit operator approval.

## 20. Implementation decomposition

Implementation should be split into independently reviewable slices:

1. **Foundation and guardrails** — directories, permissions, tmux, resource/swap checks, locks, status command.
2. **Persistent Git workspaces** — one workspace per agent, ownership guards, no-worker-worktree policy.
3. **CLI installation/authentication** — Codex, Claude, Gemini, OpenCode; provider-specific smoke tests.
4. **Dispatch/state/logging** — task envelope validation, tmux dispatch, state files, sanitized logging.
5. **Docker/test governance** — integration lock and approved test wrappers.
6. **Pilot #604** — Sonar/Codecov read-only parallel review from VPS.
7. **Academy handoff contract** — document stable interfaces Academy can later consume.

Each slice must be independently testable and must not require changing C2Pro product behavior.