# C2Pro Agent Pool v1 — Design

## Purpose

Build a minimal persistent execution pool on the Contabo VPS for four independent AI workers — Claude, Gemini, Codex and OpenCode — while ChatGPT remains the human-facing MASTER that defines Work Orders, reviews evidence and authorizes any subsequent write/merge action.

The goal is to eliminate repeated nightly launcher construction, repeated smoke-debugging and ad-hoc worktree setup. The pool must reduce operator effort to two normal actions: submit a Work Order and later inspect/harvest the results.

## Scope

Agent Pool v1 is deliberately small. It is an operational execution substrate for C2Pro development work, not a new multi-agent framework and not a replacement for the future AI-Gen control plane.

In scope:

- Four persistent lanes: `claude`, `gemini`, `codex`, `opencode`.
- One stable isolated Git worktree per lane.
- One persistent tmux shell/session per lane.
- Per-agent runtime identity and environment loading.
- A versioned task manifest and evidence contract.
- `submit`, `status`, `harvest`, `doctor`, and `reset-lane` commands.
- Exact HEAD/base guards for every task.
- Read-only/review mode by default.
- Evidence persistence under `/srv/c2pro/agent-pool/runs/<task-id>/`.
- Lane health states and bounded recovery.

Out of scope:

- Autonomous merge or deployment.
- Autonomous code-writing without explicit MASTER authorization.
- Cross-agent conversation or shared scratchpad during independent review.
- Building the full AI-Gen Master Orchestrator, Capability Resolver, Policy Engine or Work Graph runtime.
- Long-running daemon infrastructure beyond tmux/shell processes.

## Operating Model

The ChatGPT session remains MASTER. MASTER creates a Work Order containing target repository, exact HEAD/base, role-specific prompts, allowed actions, prohibited actions, expected evidence and completion contract.

The VPS Agent Pool only executes the Work Order. It does not decide scope, merge readiness or remediation. Each lane runs independently and writes its own result bundle.

Normal flow:

1. MASTER defines `TASK_ID`, HEAD/base and four prompts.
2. Operator runs one `agent-pool submit <task-dir-or-manifest>` command.
3. Pool verifies repository state, lane health and exact refs.
4. Pool refreshes each worktree to the exact requested HEAD without sharing working state.
5. Four lanes execute concurrently.
6. Operator may disconnect SSH and power off the local computer.
7. Later, `agent-pool status <TASK_ID>` reports lane states.
8. `agent-pool harvest <TASK_ID>` emits compact verdict/evidence pointers and preserves complete outputs.
9. MASTER reconciles findings and decides the next action.

## Filesystem Layout

Canonical runtime root:

```text
/srv/c2pro/agent-pool/
├── bin/
│   └── agent-pool
├── config/
│   ├── pool.env
│   └── lanes/
│       ├── claude.env
│       ├── gemini.env
│       ├── codex.env
│       └── opencode.env
├── worktrees/
│   ├── claude/
│   ├── gemini/
│   ├── codex/
│   └── opencode/
├── sessions/
│   ├── claude
│   ├── gemini
│   ├── codex
│   └── opencode
└── runs/
    └── <task-id>/
        ├── manifest.json
        ├── master-work-order.md
        ├── claude/
        ├── gemini/
        ├── codex/
        └── opencode/
```

Versioned implementation lives in the C2Pro repository under `ops/agent_pool/`; `/srv/c2pro/agent-pool/bin/agent-pool` is installed from that versioned source.

## Lane Isolation

Each lane has:

- its own detached worktree;
- its own tmux session;
- its own prompt and output files;
- its own environment loader;
- no permission to read sibling lane outputs during independent review;
- no permission to push, merge or mutate PR state unless a future Work Order explicitly changes mode.

A task may reuse the persistent worktree, but before every run the pool must verify the lane is idle, fetch the required refs, clean only pool-owned transient files, and detach/reset the worktree to the exact requested HEAD. Any unexpected tracked or untracked repository modification marks the lane `DIRTY` and blocks submission rather than deleting evidence blindly.

## Per-Agent Runtime Identity

The pool must not force all agents through one generic environment because prior failures showed that authentication/configuration differs per CLI.

### Claude

Run with the existing Claude CLI from the C2Pro toolchain. Prompts are supplied through stdin, never as a trailing argument after variadic tool flags. Review mode denies `Edit` and `Write` and allows read/search/shell inspection only.

### Gemini

Gemini uses its dedicated Linux identity and existing configuration. The canonical identity is `aigen-gemini`; its Gemini environment already contains `GOOGLE_CLOUD_PROJECT` and `GOOGLE_GENAI_USE_GCA=true` in `/home/aigen-gemini/.gemini/.env` with restricted permissions. Pool v1 must source that existing environment in the Gemini lane instead of copying or rediscovering the project value into a shared file.

The Gemini lane therefore runs under `aigen-gemini` (for example via `sudo -u aigen-gemini`/equivalent controlled invocation) and validates that the required project variable is present before starting a task. Missing configuration marks the lane `BROKEN_CONFIG`; it must not trigger repeated investigation on every task.

### Codex

Run the existing Codex CLI in read-only sandbox for review tasks. A non-zero usage/quota exit is classified as `BLOCKED_QUOTA`, distinct from implementation failure.

### OpenCode

Use an explicitly configured available model. The lane health check must validate the configured model against `opencode models` when the pool is installed or repaired, not before every task. A retired/unavailable model marks the lane `BROKEN_MODEL`.

## Pool Commands

`agent-pool doctor`

- Performs installation/health diagnostics.
- Validates tool binaries, tmux, repository, per-agent auth/config and configured OpenCode model.
- Does not execute a substantive review.
- Intended for setup or repairing a broken lane, not routine nightly use.

`agent-pool submit <manifest>`

- Validates manifest schema.
- Verifies exact remote PR/head/base guards when supplied.
- Refuses if a requested lane is already busy or dirty.
- Prepares lane worktree at the exact HEAD.
- Writes immutable run metadata.
- Starts each selected worker in its persistent tmux lane.
- Performs a bounded startup probation.
- Returns immediately after lanes are demonstrably running or have completed successfully.

`agent-pool status <task-id>`

Returns one compact state per lane:

- `QUEUED`
- `RUNNING`
- `COMPLETE`
- `FAILED`
- `BLOCKED_AUTH`
- `BLOCKED_CONFIG`
- `BLOCKED_QUOTA`
- `DIRTY`
- `TIMED_OUT`
- `NOT_REQUESTED`

`agent-pool harvest <task-id>`

- Never mutates code or task state.
- Prints completion matrix, exact reviewed SHA, exit code, verdict/recommendation signals, output sizes and evidence paths.
- Keeps full model output on disk; does not dump all logs unless explicitly requested.

`agent-pool reset-lane <lane>`

- Explicit maintenance operation.
- Allowed only when the lane is idle.
- Recreates the worktree/session after preserving previous run evidence.

## Work Order Contract

Every submitted task manifest contains:

```json
{
  "task_id": "pr604-r16e-r2",
  "repository": "AI-Gen-AI/C2Pro",
  "head": "<40-char-sha>",
  "base": "<40-char-sha>",
  "mode": "review",
  "lanes": ["claude", "gemini", "codex", "opencode"],
  "timeout_seconds": 27000,
  "prompts": {
    "claude": "prompts/claude.md",
    "gemini": "prompts/gemini.md",
    "codex": "prompts/codex.md",
    "opencode": "prompts/opencode.md"
  }
}
```

The run directory also contains the MASTER common constraints and role-specific prompts. Review mode is fail-closed: mutation wrappers block commit, push, merge, deployment and PR/Sonar transitions.

## Health and Recovery

Routine task submission must not repeat full toolchain forensics.

A lane may be used only when its cached health is `READY`. Health is established by `doctor` and updated when a run exposes a deterministic infrastructure problem.

Recovery policy:

- Invocation/configuration failure in the first probation window: at most one bounded automatic retry if the fix is deterministic and preconfigured.
- Auth/project/model/usage failure: stop that lane and classify it; do not loop.
- Model-generated technical finding: never retry automatically merely because the verdict is inconvenient.
- Dirty worktree: block and require explicit `reset-lane` or MASTER inspection.

## Evidence Contract

Each lane writes:

```text
started-at.txt
finished-at.txt
exit-code.txt
state.txt
head.txt
runner.log
agent-stderr.log
final-output.md
worktree-status-after.txt
```

The task root writes a machine-readable `summary.json` plus `manifest.json`. Results remain immutable after completion except for a separate reconciliation artifact written by MASTER tooling in the future.

## Security and Governance

Review mode is the v1 default. Shell wrappers prevent Git/GitHub/deployment mutations. Agent prompts also state the prohibition, but prompt instructions are not considered a security boundary.

Secrets are not copied into task manifests or evidence. Per-agent native credential stores/config files remain authoritative. Gemini's existing project environment is sourced in its own account and is not duplicated into public logs.

No lane may autonomously merge, deploy, alter Sonar issue state, change branch protection or write production databases.

## Relationship to AI-Gen

Agent Pool v1 is intentionally an operational precursor, not the final architecture. It provides empirical inputs for future AI-Gen components:

- MASTER Work Order -> future Work Order / Work Graph.
- Lane selection -> future Capability Resolver.
- Per-lane constraints -> future Policy / Risk Engine.
- Result bundles -> future Evidence / Evaluation layer.
- Independent workers -> future interchangeable execution runtimes.

The v1 implementation should therefore keep task manifests and evidence contracts explicit, but avoid implementing generalized orchestration abstractions prematurely.

## Acceptance Criteria

Agent Pool v1 is accepted when:

1. `agent-pool doctor` reports all configured lanes accurately, including Gemini using its existing dedicated environment.
2. A four-lane read-only smoke task can be submitted with one command.
3. The operator can disconnect SSH while tasks continue in tmux.
4. `agent-pool status <task-id>` reports correct lane states without reading full logs.
5. `agent-pool harvest <task-id>` returns compact decision signals and evidence paths.
6. Worktrees remain isolated and pinned to the requested HEAD.
7. A failed lane does not block successful lanes or cause repeated automatic retries.
8. No routine submission requires rediscovering CLI flags, Gemini project configuration or OpenCode model availability.
9. No commit, push, merge or deployment can occur in review mode.
10. The implementation remains small enough to be replaced later by the governed AI-Gen execution plane rather than becoming a competing framework.
