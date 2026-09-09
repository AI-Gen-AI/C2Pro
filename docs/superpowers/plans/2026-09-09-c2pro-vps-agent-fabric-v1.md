# C2Pro VPS Agent Fabric v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a persistent, guarded VPS execution fabric for Claude, Codex, Gemini, and OpenCode that preserves C2Pro G1/G2 single-writer governance and can later be adopted by AI-Gen Agent Academy.

**Architecture:** AI CLIs run natively in four persistent tmux sessions and four persistent Git workspaces under `/srv/c2pro`; Docker remains an infrastructure/test boundary rather than the default agent shell. A small repository-owned fabric layer provides idempotent bootstrap, workspace guards, structured task envelopes, resource locks, state/logging, and reboot-safe recovery without becoming a second planning/control plane.

**Tech Stack:** Ubuntu 24.04, Bash, Python 3.11+, Git worktrees, tmux, flock, YAML/JSON Schema, pytest, GitHub CLI, Node.js/npm, Docker/Compose, Codex CLI, Claude Code, Gemini CLI, OpenCode.

**Spec:** `docs/superpowers/specs/2026-09-09-c2pro-vps-agent-fabric-v1-design.md`

## Global Constraints

- Existing OpenClaw, Qdrant, backups, Docker containers/volumes/networks, firewall rules, and production deployment configuration must remain untouched.
- Canonical control/planning state remains `.c2pro/control/*`; `/srv/c2pro/sessions/state/*` is operational state only.
- Workspace lifecycle owner is the orchestrator; workers may not create, remove, reset, clean, or repurpose workspaces.
- Exactly one persistent workspace per agent: `claude`, `codex`, `gemini`, `opencode`.
- Maximum one active writer task per workspace.
- Maximum two heavy agents concurrently; optional one lightweight reviewer if memory remains healthy.
- Maximum one Docker-heavy integration/security gate at a time via `docker-integration.lock`.
- Workers do not receive unrestricted Docker socket access through the supported dispatch path.
- Secrets are never committed, placed in task/result YAML, or written to shared shell history/logs.
- Provider env files under `/srv/c2pro/env/` must be owner-only (`0600`); directories containing them must not be group/world writable.
- Workspace/branch/HEAD mismatch must fail closed with `WORKSPACE_GUARD_FAILURE`.
- Reboot recovery recreates sessions but never automatically resumes interrupted writer tasks.
- Publication/merge remains MASTER-controlled; workers default to local commit only unless an explicit task envelope authorizes push.
- Every slice must be idempotent, independently testable, and safe to rerun.

---

## File Structure

The implementation will introduce the following focused files:

```text
.c2pro/schemas/agent-task.schema.yaml
scripts/development/agent_fabric/
├── bootstrap.sh              # host foundation + directory/tmux bootstrap
├── preflight.sh              # read-only host inventory and compatibility checks
├── status.sh                 # memory/swap/tmux/locks/docker/disk status
├── common.sh                 # shared shell constants + safe helpers
├── workspace_manager.py      # orchestrator-only persistent worktree lifecycle
├── workspace_guard.py        # fail-closed task workspace/branch/HEAD validation
├── dispatch.py               # task-envelope validation + tmux prompt dispatch
├── recover.py                # reboot/session reconstruction; never auto-resumes writers
├── docker_gate.sh            # flock-serialized approved Docker-heavy command wrapper
└── redact_log.py             # defensive log redaction before durable retention

tests/
├── test_vps_agent_fabric_foundation.py
├── test_vps_agent_fabric_workspaces.py
├── test_vps_agent_fabric_dispatch.py
└── test_vps_agent_fabric_recovery.py

docs/operations/C2PRO_VPS_AGENT_FABRIC_V1_RUNBOOK.md
```

The fabric scripts live under `scripts/development/agent_fabric/` because the current repository already places development-control validation under `scripts/development/`. The task schema lives under `.c2pro/schemas/` so it reuses the existing machine-validatable control-plane conventions without adding a new canonical planning store.

---

### Task 1: Read-only VPS preflight and foundation guardrails

**Files:**
- Create: `scripts/development/agent_fabric/common.sh`
- Create: `scripts/development/agent_fabric/preflight.sh`
- Create: `scripts/development/agent_fabric/status.sh`
- Create: `tests/test_vps_agent_fabric_foundation.py`

**Interfaces:**
- Consumes: existing Ubuntu host, existing Docker installation, existing C2Pro repository access.
- Produces: `preflight.sh` exit code + machine-readable `KEY=VALUE` lines; `status.sh`; common constants `FABRIC_ROOT=/srv/c2pro`, agent names, session names, and safe command helpers.

- [ ] **Step 1: Write RED tests for preflight non-destructiveness and constants**

Create `tests/test_vps_agent_fabric_foundation.py` with source-level invariants that can run on any CI host:

```python
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FABRIC = ROOT / "scripts" / "development" / "agent_fabric"


def test_preflight_is_read_only() -> None:
    text = (FABRIC / "preflight.sh").read_text()
    forbidden = [
        "apt-get install",
        "docker rm",
        "docker system prune",
        "git clean",
        "git reset --hard",
        "ufw ",
        "iptables ",
    ]
    for token in forbidden:
        assert token not in text


def test_common_declares_canonical_agents_and_root() -> None:
    text = (FABRIC / "common.sh").read_text()
    assert 'FABRIC_ROOT="/srv/c2pro"' in text
    for agent in ("claude", "codex", "gemini", "opencode"):
        assert agent in text
```

- [ ] **Step 2: Run the RED tests**

Run:

```bash
pytest tests/test_vps_agent_fabric_foundation.py -q
```

Expected: FAIL because the fabric files do not yet exist.

- [ ] **Step 3: Implement `common.sh`**

Use strict shell mode and fixed names:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail

FABRIC_ROOT="/srv/c2pro"
CONTROL_DIR="$FABRIC_ROOT/control"
WORKSPACES_DIR="$FABRIC_ROOT/workspaces"
SESSIONS_DIR="$FABRIC_ROOT/sessions"
STATE_DIR="$SESSIONS_DIR/state"
LOG_DIR="$SESSIONS_DIR/logs"
LOCK_DIR="$FABRIC_ROOT/locks"
ENV_DIR="$FABRIC_ROOT/env"
AGENTS=(claude codex gemini opencode)

session_name() { printf 'c2pro-%s' "$1"; }
workspace_path() { printf '%s/%s' "$WORKSPACES_DIR" "$1"; }
```

Do not add installation or mutation logic to `common.sh`.

- [ ] **Step 4: Implement read-only `preflight.sh`**

The script must only inspect and report. Required checks/output:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail
source "$(dirname "$0")/common.sh"

printf 'PREFLIGHT_SCHEMA=c2pro-vps-preflight-v1\n'
printf 'USER=%s\n' "$(id -un)"
printf 'UID=%s\n' "$(id -u)"
printf 'OS=%s\n' "$(. /etc/os-release && printf '%s %s' "$ID" "$VERSION_ID")"
printf 'MEM_KB=%s\n' "$(awk '/MemTotal/ {print $2}' /proc/meminfo)"
printf 'SWAP_KB=%s\n' "$(awk '/SwapTotal/ {print $2}' /proc/meminfo)"
printf 'ROOT_FREE_KB=%s\n' "$(df -Pk / | awk 'NR==2 {print $4}')"
for cmd in git gh tmux node npm python3 docker; do
  if command -v "$cmd" >/dev/null 2>&1; then
    printf 'CMD_%s=present\n' "${cmd^^}"
  else
    printf 'CMD_%s=missing\n' "${cmd^^}"
  fi
done

docker ps --format 'CONTAINER={{.Names}}|{{.Image}}|{{.Status}}' 2>/dev/null || true
tmux list-sessions -F 'TMUX={{.SessionName}}|{{.SessionAttached}}|{{.SessionWindows}}' 2>/dev/null || true
```

It may read `/srv`, `/opt`, `/home`, package/version metadata, current groups, Docker container metadata, disk/memory/swap state, and existing repository locations. It must not install, move, delete, restart, stop, or reconfigure anything.

- [ ] **Step 5: Implement `status.sh`**

Output only operational metrics:

```bash
printf 'memory_available_kb=%s\n' "$(awk '/MemAvailable/ {print $2}' /proc/meminfo)"
printf 'swap_used_kb=%s\n' "$(free -k | awk '/Swap:/ {print $3}')"
printf 'load_1m=%s\n' "$(awk '{print $1}' /proc/loadavg)"
printf 'fabric_disk_kb=%s\n' "$(du -sk "$FABRIC_ROOT" 2>/dev/null | awk '{print $1}' || printf 0)"
find "$LOCK_DIR" -maxdepth 1 -type f -printf 'lock=%f\n' 2>/dev/null || true
tmux list-sessions -F 'tmux={{.SessionName}}' 2>/dev/null || true
```

- [ ] **Step 6: Run tests and shell syntax validation**

Run:

```bash
bash -n scripts/development/agent_fabric/common.sh
bash -n scripts/development/agent_fabric/preflight.sh
bash -n scripts/development/agent_fabric/status.sh
pytest tests/test_vps_agent_fabric_foundation.py -q
```

Expected: PASS.

- [ ] **Step 7: Commit Task 1**

```bash
git add scripts/development/agent_fabric/common.sh \
        scripts/development/agent_fabric/preflight.sh \
        scripts/development/agent_fabric/status.sh \
        tests/test_vps_agent_fabric_foundation.py
git commit -m "feat(devops): add VPS agent fabric preflight"
```

---

### Task 2: Idempotent host foundation bootstrap

**Files:**
- Create: `scripts/development/agent_fabric/bootstrap.sh`
- Modify: `tests/test_vps_agent_fabric_foundation.py`
- Create: `docs/operations/C2PRO_VPS_AGENT_FABRIC_V1_RUNBOOK.md`

**Interfaces:**
- Consumes: successful Task 1 preflight; an operator with sudo where package/directory changes are required.
- Produces: `/srv/c2pro/{control,workspaces,sessions/state,sessions/logs,locks,env,scripts}` with guarded permissions; required host packages; persistent tmux session shells; optional emergency swap only when explicitly enabled.

- [ ] **Step 1: Add RED tests for idempotence and protected-service boundaries**

Add tests asserting `bootstrap.sh`:

```python
def test_bootstrap_never_mutates_existing_services() -> None:
    text = (FABRIC / "bootstrap.sh").read_text()
    forbidden = [
        "docker system prune",
        "docker volume rm",
        "docker network rm",
        "systemctl restart docker",
        "systemctl stop docker",
        "qdrant",
        "openclaw",
        "ufw ",
        "iptables ",
    ]
    for token in forbidden:
        assert token not in text


def test_bootstrap_requires_explicit_swap_opt_in() -> None:
    text = (FABRIC / "bootstrap.sh").read_text()
    assert "ENABLE_SWAP" in text
    assert 'ENABLE_SWAP:-0' in text
```

- [ ] **Step 2: Run RED tests**

Expected: FAIL because `bootstrap.sh` is absent.

- [ ] **Step 3: Implement foundation directory creation and permissions**

Use operator-configurable owner, defaulting to current sudo user/current user:

```bash
FABRIC_OWNER="${FABRIC_OWNER:-${SUDO_USER:-$(id -un)}}"
FABRIC_GROUP="${FABRIC_GROUP:-$(id -gn "$FABRIC_OWNER")}" 

sudo install -d -m 0750 -o "$FABRIC_OWNER" -g "$FABRIC_GROUP" \
  "$FABRIC_ROOT" "$CONTROL_DIR" "$WORKSPACES_DIR" \
  "$SESSIONS_DIR" "$STATE_DIR" "$LOG_DIR" "$LOCK_DIR" "$ENV_DIR" \
  "$FABRIC_ROOT/scripts"
chmod 0700 "$ENV_DIR"
```

Never recursively `chown` outside `/srv/c2pro`.

- [ ] **Step 4: Install only missing foundation packages**

Allowed foundation packages:

```text
git
curl
ca-certificates
tmux
jq
yq
gh
python3
python3-venv
python3-pip
```

Before `apt-get`, calculate missing packages with `dpkg-query`. Only if missing packages exist, run official Ubuntu apt update/install. Do not reinstall Docker.

- [ ] **Step 5: Add optional emergency swap with explicit opt-in**

Default: no change.

When `ENABLE_SWAP=1` and `SwapTotal == 0`, create a single fabric-owned `/swapfile-c2pro` sized by `SWAP_SIZE_GB` default `4`, permissions `0600`, `mkswap`, `swapon`, and append exactly one tagged `/etc/fstab` line after confirming none exists.

If swap already exists, report and do nothing.

- [ ] **Step 6: Create tmux shell sessions idempotently**

For each agent:

```bash
if ! tmux has-session -t "$(session_name "$agent")" 2>/dev/null; then
  tmux new-session -d -s "$(session_name "$agent")" -c "$FABRIC_ROOT"
fi
```

Task 2 sessions intentionally start at fabric root; Task 3 retargets them after workspaces exist.

- [ ] **Step 7: Write runbook foundation/rollback section**

Document exact operator commands:

```bash
./scripts/development/agent_fabric/preflight.sh
sudo FABRIC_OWNER="$USER" ./scripts/development/agent_fabric/bootstrap.sh
./scripts/development/agent_fabric/status.sh
```

Rollback for Task 2 may stop `c2pro-*` tmux sessions and remove only empty/fabric-created directories after operator inspection. It must not include an automatic recursive delete command.

- [ ] **Step 8: Verify idempotence**

On a disposable Linux environment or VPS after explicit operator approval, run bootstrap twice and compare directory ownership, tmux session count, Docker container list, and swap state. Expected: second run has zero additional side effects.

- [ ] **Step 9: Commit Task 2**

```bash
git add scripts/development/agent_fabric/bootstrap.sh \
        tests/test_vps_agent_fabric_foundation.py \
        docs/operations/C2PRO_VPS_AGENT_FABRIC_V1_RUNBOOK.md
git commit -m "feat(devops): bootstrap persistent VPS agent fabric"
```

---

### Task 3: Persistent workspace manager and fail-closed guard

**Files:**
- Create: `scripts/development/agent_fabric/workspace_manager.py`
- Create: `scripts/development/agent_fabric/workspace_guard.py`
- Create: `tests/test_vps_agent_fabric_workspaces.py`
- Modify: `docs/operations/C2PRO_VPS_AGENT_FABRIC_V1_RUNBOOK.md`

**Interfaces:**
- Consumes: `/srv/c2pro/control` canonical checkout or configured bare/source repository; `.c2pro/control/workspace-policy.yaml`.
- Produces: exactly four persistent orchestrator-owned worktrees and `WORKSPACE_GUARD_FAILURE` exit contract.

- [ ] **Step 1: Write RED unit tests for workspace policy**

Create tests around pure functions:

```python
from pathlib import Path
from scripts.development.agent_fabric.workspace_guard import GuardExpectation, validate_workspace


def test_wrong_workspace_fails_closed(tmp_path: Path) -> None:
    expected = GuardExpectation(
        agent="gemini",
        workspace=Path("/srv/c2pro/workspaces/gemini"),
        branch="fix/example",
        start_head="a" * 40,
        require_clean=True,
    )
    result = validate_workspace(tmp_path, expected)
    assert result.code == "WORKSPACE_GUARD_FAILURE"
```

Add cases for wrong branch, wrong HEAD, dirty tree when clean required, and another agent's workspace.

- [ ] **Step 2: Run RED tests**

Expected: import failure because guard module does not exist.

- [ ] **Step 3: Implement `GuardExpectation` and `GuardResult`**

```python
@dataclass(frozen=True)
class GuardExpectation:
    agent: Literal["claude", "codex", "gemini", "opencode"]
    workspace: Path
    branch: str
    start_head: str
    require_clean: bool = True

@dataclass(frozen=True)
class GuardResult:
    ok: bool
    code: str
    message: str
```

`validate_workspace()` must resolve real paths and invoke Git with `subprocess.run(..., check=True, text=True, capture_output=True)` without shell interpolation.

- [ ] **Step 4: Implement orchestrator-only `workspace_manager.py`**

Supported commands:

```text
status
ensure --agent <agent> --base-ref origin/main
```

`ensure` behavior:
- refuse if target path exists but is not the expected Git worktree;
- refuse to remove/reset/clean an existing workspace;
- add a missing worktree only under `/srv/c2pro/workspaces/<agent>`;
- never create arbitrary agent names;
- never execute automatically from worker dispatch.

Use `git worktree add --detach <path> <base-ref>` for initial creation, then leave branch assignment to an explicit task preparation step. Detached creation avoids inventing a shared branch at bootstrap.

- [ ] **Step 5: Retarget tmux sessions safely**

After workspace creation, recreate only empty/unstarted fabric tmux sessions so each session starts in its matching workspace. If a session already has an active process, report `SESSION_BUSY` and do not kill it.

- [ ] **Step 6: Run unit tests**

Expected: all guard/manager unit tests pass using temporary Git repositories; no test touches the real VPS repository.

- [ ] **Step 7: Commit Task 3**

```bash
git add scripts/development/agent_fabric/workspace_manager.py \
        scripts/development/agent_fabric/workspace_guard.py \
        tests/test_vps_agent_fabric_workspaces.py \
        docs/operations/C2PRO_VPS_AGENT_FABRIC_V1_RUNBOOK.md
git commit -m "feat(control): guard persistent VPS agent workspaces"
```

---

### Task 4: CLI installation and provider smoke checks

**Files:**
- Create: `scripts/development/agent_fabric/install_clis.sh`
- Create: `scripts/development/agent_fabric/cli_smoke.sh`
- Modify: `tests/test_vps_agent_fabric_foundation.py`
- Modify: `docs/operations/C2PRO_VPS_AGENT_FABRIC_V1_RUNBOOK.md`

**Interfaces:**
- Consumes: Task 2 host foundation, provider-native auth/environment supplied by operator.
- Produces: installed CLI executables and non-secret smoke status for Claude, Codex, Gemini, OpenCode.

- [ ] **Step 1: Write RED source-contract tests**

Assert installer:
- detects existing versions before installing;
- never echoes provider keys;
- never writes secrets into repository paths;
- never uses beta/pre-release OpenCode unless explicitly enabled.

- [ ] **Step 2: Implement idempotent installer**

The installer must expose independent functions:

```bash
ensure_codex
ensure_claude
ensure_gemini
ensure_opencode
```

Each function first checks the command/version and only installs when missing or when an explicit `UPGRADE_CLIS=1` is supplied. Installation commands must use each provider's current supported Linux installation path at implementation time and be pinned to stable channels where the provider supports them.

Do not automate OAuth credentials or capture device-login codes.

- [ ] **Step 3: Implement `cli_smoke.sh`**

Required output:

```text
CLI_CODEX=installed|missing|auth_required|ready
CLI_CLAUDE=installed|missing|auth_required|ready
CLI_GEMINI=installed|missing|auth_required|ready
CLI_OPENCODE=installed|missing|auth_required|ready
```

The smoke test may invoke `--version`, `auth status`, or equivalent read-only provider commands. It must never print tokens.

- [ ] **Step 4: Document one-time authentication**

Runbook must keep authentication outside shell history. For Gemini, document persistent non-secret `GOOGLE_CLOUD_PROJECT`/`GOOGLE_CLOUD_PROJECT_ID` configuration separately from tokens. For OpenCode, document provider routing without embedding API keys in checked-in files.

- [ ] **Step 5: Run smoke checks for all four CLIs**

Expected after one-time operator authentication: all four return `ready` or an explicitly documented `auth_required` pending manual provider login. No other task is blocked by one provider being temporarily unavailable because OpenCode is the fallback path.

- [ ] **Step 6: Commit Task 4**

```bash
git add scripts/development/agent_fabric/install_clis.sh \
        scripts/development/agent_fabric/cli_smoke.sh \
        tests/test_vps_agent_fabric_foundation.py \
        docs/operations/C2PRO_VPS_AGENT_FABRIC_V1_RUNBOOK.md
git commit -m "feat(devops): install and verify VPS agent CLIs"
```

---

### Task 5: Structured dispatch, state, logs, and concurrency locks

**Files:**
- Create: `.c2pro/schemas/agent-task.schema.yaml`
- Create: `scripts/development/agent_fabric/dispatch.py`
- Create: `scripts/development/agent_fabric/redact_log.py`
- Create: `tests/test_vps_agent_fabric_dispatch.py`
- Modify: `docs/operations/C2PRO_VPS_AGENT_FABRIC_V1_RUNBOOK.md`

**Interfaces:**
- Consumes: Task 3 workspace guard, existing `c2pro-implementation-result-v1` result contract, task YAML.
- Produces: validated `c2pro-agent-task-v1` dispatch, session state YAML, append-only sanitized log, tmux delivery, writer lock.

- [ ] **Step 1: Add RED schema tests**

Schema must require:

```yaml
schema: c2pro-agent-task-v1
task_id: C2PRO-EXAMPLE
agent: gemini
mode: writer
workspace: /srv/c2pro/workspaces/gemini
branch: fix/example
base_sha: 40-char-sha
expected_start_head: 40-char-sha
scope:
  allowed_paths: [apps/api/src/example.py]
  forbidden_paths: [.c2pro/control, C2PRO_MASTER_BACKLOG.md, blackboard.json]
authorizations:
  commit: true
  push: false
  merge: false
result_schema: c2pro-implementation-result-v1
```

Reject unknown agents, arbitrary workspace paths, missing authorizations, and `merge: true` for ordinary worker envelopes.

- [ ] **Step 2: Implement schema and parser**

Use `yaml.safe_load` plus `jsonschema` validation. Normalize no paths; compare resolved allowed roots explicitly.

- [ ] **Step 3: Acquire writer lock before dispatch**

Writer task lock path:

```text
/srv/c2pro/locks/writer-<agent>.lock
```

Use `fcntl.flock(..., LOCK_EX | LOCK_NB)`. If lock cannot be acquired, return `WORKSPACE_BUSY` and do not send prompt text.

Reviewer tasks do not take writer locks but still run workspace guard and may not write into a workspace with an active writer lock.

- [ ] **Step 4: Validate workspace before tmux dispatch**

Call `validate_workspace()` using task workspace/branch/expected start HEAD. Any mismatch returns `WORKSPACE_GUARD_FAILURE` before creating state/log files that imply execution began.

- [ ] **Step 5: Create operational state atomically**

Write YAML to a temporary file in `/srv/c2pro/sessions/state`, `fsync`, then `os.replace` to final path. Fields match the spec's `c2pro-agent-session-v1` contract and include `task_envelope_sha256`.

- [ ] **Step 6: Dispatch through tmux without shell-history secret leakage**

Write the prompt/task content to an owner-readable temporary file under `/srv/c2pro/sessions/` and use a per-agent wrapper that reads that file. Do not interpolate raw prompts into shell command strings.

- [ ] **Step 7: Implement `redact_log.py`**

Redact at minimum:

```text
Authorization: Bearer ...
*_API_KEY=...
*_TOKEN=...
postgresql://user:password@...
```

Use conservative regexes and replace secret values with `<REDACTED>` before durable retention.

- [ ] **Step 8: Test concurrency and guard failures**

Tests must prove:
- second writer for same agent fails `WORKSPACE_BUSY`;
- wrong workspace fails before tmux dispatch;
- push/merge authorization remains false unless explicitly set in envelope and policy permits it;
- logs do not retain synthetic secret fixtures.

- [ ] **Step 9: Commit Task 5**

```bash
git add .c2pro/schemas/agent-task.schema.yaml \
        scripts/development/agent_fabric/dispatch.py \
        scripts/development/agent_fabric/redact_log.py \
        tests/test_vps_agent_fabric_dispatch.py \
        docs/operations/C2PRO_VPS_AGENT_FABRIC_V1_RUNBOOK.md
git commit -m "feat(control): add guarded VPS agent dispatch"
```

---

### Task 6: Docker-heavy test serialization and reboot recovery

**Files:**
- Create: `scripts/development/agent_fabric/docker_gate.sh`
- Create: `scripts/development/agent_fabric/recover.py`
- Create: `tests/test_vps_agent_fabric_recovery.py`
- Modify: `docs/operations/C2PRO_VPS_AGENT_FABRIC_V1_RUNBOOK.md`

**Interfaces:**
- Consumes: Task 5 locks/state, existing repository Docker/test commands.
- Produces: one-at-a-time Docker-heavy execution and reboot-safe session reconstruction without automatic task continuation.

- [ ] **Step 1: RED tests for Docker lock and no auto-resume**

Source/behavior tests must assert:
- `docker_gate.sh` uses `/srv/c2pro/locks/docker-integration.lock` with `flock`;
- recovery marks `running` tasks `stopped` with reason `host_recovery`;
- recovery never sends prompts/`continue`/agent commands automatically.

- [ ] **Step 2: Implement `docker_gate.sh`**

Usage:

```bash
./docker_gate.sh -- <approved repository test command>
```

The wrapper takes the global lock, records start/end timestamps, executes the supplied command as the current operator, and returns the command's exact exit code. It must not grant Docker permissions or alter the Docker daemon.

- [ ] **Step 3: Implement `recover.py`**

Recovery flow:
1. validate `/srv/c2pro` paths;
2. read session state files;
3. atomically rewrite `running` to `stopped` with `stop_reason: host_recovery`;
4. recreate missing `c2pro-<agent>` tmux shell sessions in their persistent workspace;
5. print tasks requiring MASTER decision;
6. never resume task execution.

- [ ] **Step 4: Run tests**

Expected: lock serialization and recovery invariants pass without Docker daemon access in unit tests.

- [ ] **Step 5: Commit Task 6**

```bash
git add scripts/development/agent_fabric/docker_gate.sh \
        scripts/development/agent_fabric/recover.py \
        tests/test_vps_agent_fabric_recovery.py \
        docs/operations/C2PRO_VPS_AGENT_FABRIC_V1_RUNBOOK.md
git commit -m "feat(devops): serialize VPS integration gates and recovery"
```

---

### Task 7: #604 pilot and Academy handoff contract

**Files:**
- Create: `docs/operations/C2PRO_VPS_AGENT_FABRIC_V1_PILOT.md`
- Create: `docs/architecture/C2PRO_AGENT_FABRIC_ACADEMY_HANDOFF.md`
- Modify: `docs/operations/C2PRO_VPS_AGENT_FABRIC_V1_RUNBOOK.md`

**Interfaces:**
- Consumes: Tasks 1-6 fully green, authenticated CLIs, #604 Sonar/Codecov closeout work.
- Produces: real multi-agent pilot evidence and stable interfaces for later Academy orchestration.

- [ ] **Step 1: Run read-only Claude Sonar pilot**

Dispatch a reviewer envelope to Claude:
- PR #604
- read-only
- classify exact Sonar blockers
- no code modifications
- structured result required

Success evidence: state file, sanitized log, result block, workspace guard PASS.

- [ ] **Step 2: Run read-only Codex Codecov pilot concurrently**

Dispatch a reviewer envelope to Codex:
- PR #604
- diagnose 23.91% patch coverage
- distinguish uninstrumented subprocess/gate scripts from genuinely untested product logic
- no code modifications

Run concurrently with Claude while checking `status.sh`; do not start additional heavy writer.

- [ ] **Step 3: MASTER consolidates pilot findings**

Document in pilot report:
- both agent start/end HEADs;
- no workspace mutations for reviewers;
- logs preserved/redacted;
- memory/swap/load during overlap;
- whether locks behaved as designed;
- exact #604 findings.

- [ ] **Step 4: Execute one bounded writer pilot if #604 needs code changes**

Assign exactly one writer (Gemini by default) with allowed paths constrained to the approved Sonar/Codecov fix. Reviewer sessions remain read-only. Publication remains MASTER-authorized.

- [ ] **Step 5: Write Academy handoff contract**

Document stable interfaces Academy may adopt:

```text
workspace identity: /srv/c2pro/workspaces/<agent>
task schema: c2pro-agent-task-v1
result schema: c2pro-implementation-result-v1
operational state: c2pro-agent-session-v1
workspace mismatch: WORKSPACE_GUARD_FAILURE
writer concurrency: one writer lock per workspace
docker concurrency: one global integration lock
```

Explicitly state that Academy replaces manual dispatch/state coordination, not G1/G2 canonical planning authority.

- [ ] **Step 6: Acceptance check against all 15 spec criteria**

Record PASS/FAIL evidence for each acceptance criterion in the pilot document. Any failed criterion keeps Fabric v1 in `pilot` status.

- [ ] **Step 7: Commit Task 7**

```bash
git add docs/operations/C2PRO_VPS_AGENT_FABRIC_V1_PILOT.md \
        docs/architecture/C2PRO_AGENT_FABRIC_ACADEMY_HANDOFF.md \
        docs/operations/C2PRO_VPS_AGENT_FABRIC_V1_RUNBOOK.md
git commit -m "docs: validate VPS agent fabric pilot and Academy handoff"
```

---

## Final Verification

After all tasks:

```bash
python scripts/development/validate_c2pro_control.py
pytest tests/test_single_writer_control_plane.py -q
pytest tests/test_vps_agent_fabric_foundation.py -q
pytest tests/test_vps_agent_fabric_workspaces.py -q
pytest tests/test_vps_agent_fabric_dispatch.py -q
pytest tests/test_vps_agent_fabric_recovery.py -q
ruff check scripts/development/agent_fabric tests/test_vps_agent_fabric_*.py
git diff --check origin/main...HEAD
```

VPS operational proof:

```bash
scripts/development/agent_fabric/preflight.sh
scripts/development/agent_fabric/status.sh
scripts/development/agent_fabric/cli_smoke.sh
python scripts/development/agent_fabric/workspace_manager.py status
```

Then verify:
- four tmux sessions exist;
- four workspaces exist and are guarded;
- no unapproved Docker/container changes occurred;
- OpenClaw/Qdrant/backups remain healthy;
- no provider/database secrets appear under `/srv/c2pro/sessions/logs`;
- reboot recovery marks interrupted work stopped rather than resuming it;
- #604 Claude/Codex pilot completed from VPS.

## Self-Review Result

- **Spec coverage:** all 20 design sections and 15 acceptance criteria map to Tasks 1-7 or Final Verification.
- **Placeholder scan:** no TBD/TODO/fill-later steps remain; provider installation commands are intentionally resolved at implementation time because upstream-supported CLI installers can change, while the required stable-channel/idempotence contract is fixed here.
- **Type/interface consistency:** task/result/session schema names and workspace/session paths are consistent across Tasks 3, 5, 6, and 7.
- **Scope isolation:** no task changes C2Pro product behavior, OpenClaw/Qdrant, production deployment, firewall, or G1/G2 planning authority.
