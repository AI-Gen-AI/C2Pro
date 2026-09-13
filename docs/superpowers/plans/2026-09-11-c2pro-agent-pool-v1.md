# C2Pro Agent Pool v1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a minimal persistent four-lane VPS agent pool for Claude, Gemini, Codex and OpenCode with stable worktrees/tmux sessions, per-agent environments, one-command submit/status/harvest, and fail-closed review-mode governance.

**Architecture:** Version the pool under `ops/agent_pool/` as small Bash modules with no new runtime dependency beyond Bash, Git, tmux, jq, gh and the existing agent CLIs. Install the versioned launcher into `/srv/c2pro/agent-pool/bin/agent-pool`; keep runtime state, worktrees and evidence outside the repository. Per-lane environment loaders preserve native agent authentication, especially Gemini's dedicated `aigen-gemini` identity and `/home/aigen-gemini/.gemini/.env`.

**Tech Stack:** Bash 5+, Git worktrees, tmux, jq, GitHub CLI, Claude Code, Gemini CLI, Codex CLI, OpenCode CLI.

**Spec:** `docs/superpowers/specs/2026-09-11-c2pro-agent-pool-v1-design.md`

## Global Constraints

- ChatGPT remains MASTER; the VPS pool executes Work Orders but never decides merge/deploy readiness.
- Review mode is the v1 default and must fail closed against commit, push, merge, deployment, PR/Sonar mutation and production database mutation.
- Persistent lanes: `claude`, `gemini`, `codex`, `opencode`.
- Runtime root: `/srv/c2pro/agent-pool`.
- Versioned source: `ops/agent_pool/`.
- Gemini must use the existing dedicated `aigen-gemini` identity and source `/home/aigen-gemini/.gemini/.env`; do not duplicate the project value into shared logs/config.
- Routine `submit` must not repeat full CLI/auth/model forensics; that belongs to `doctor` or explicit lane repair.
- One task failure must not cancel independent successful lanes.
- No new service/daemon framework beyond tmux/shell processes.
- No autonomous merge/deploy in v1.

---

## File Structure

Create the following focused units:

```text
ops/agent_pool/
├── agent-pool                  # user-facing command dispatcher
├── install.sh                  # idempotent VPS installation/update
├── lib/
│   ├── common.sh               # paths, logging, JSON helpers, guards
│   ├── lanes.sh                # per-agent config, doctor, lane reset
│   ├── worktrees.sh            # isolated worktree lifecycle
│   ├── runner.sh               # one lane/task execution contract
│   └── tasks.sh                # submit/status/harvest orchestration
├── config/
│   ├── pool.env.example        # non-secret pool defaults
│   └── lanes/
│       ├── claude.env.example
│       ├── gemini.env.example
│       ├── codex.env.example
│       └── opencode.env.example
└── tests/
    └── test_agent_pool.sh      # dependency-free shell acceptance tests
```

Runtime installation creates:

```text
/srv/c2pro/agent-pool/{bin,config/lanes,worktrees,runs,tmp}
```

No runtime evidence belongs in Git.

---

### Task 1: Command Skeleton, Canonical Paths, and Manifest Validation

**Files:**
- Create: `ops/agent_pool/agent-pool`
- Create: `ops/agent_pool/lib/common.sh`
- Create: `ops/agent_pool/tests/test_agent_pool.sh`

**Interfaces:**
- Consumes: environment variable `C2PRO_AGENT_POOL_ROOT`, default `/srv/c2pro/agent-pool`.
- Produces: `pool_die`, `pool_log`, `require_cmd`, `manifest_get`, `validate_task_id`, `validate_sha`, and command dispatch for `doctor|submit|status|harvest|reset-lane`.

- [ ] **Step 1: Write failing CLI tests**

Add to `ops/agent_pool/tests/test_agent_pool.sh`:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../../.." && pwd)"
CLI="$ROOT/ops/agent_pool/agent-pool"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

fail() { echo "FAIL: $*" >&2; exit 1; }

OUT="$(C2PRO_AGENT_POOL_ROOT="$TMP/pool" "$CLI" --help)" || fail "--help failed"
grep -q 'agent-pool doctor' <<<"$OUT" || fail "help missing doctor"
grep -q 'agent-pool submit' <<<"$OUT" || fail "help missing submit"
grep -q 'agent-pool status' <<<"$OUT" || fail "help missing status"
grep -q 'agent-pool harvest' <<<"$OUT" || fail "help missing harvest"

set +e
C2PRO_AGENT_POOL_ROOT="$TMP/pool" "$CLI" unknown >"$TMP/out" 2>"$TMP/err"
RC=$?
set -e
[[ "$RC" -eq 64 ]] || fail "unknown command rc=$RC"
grep -q 'unknown command' "$TMP/err" || fail "unknown command diagnostic missing"

echo "TASK1_TESTS=PASS"
```

- [ ] **Step 2: Run the test and verify it fails before implementation**

Run:

```bash
bash ops/agent_pool/tests/test_agent_pool.sh
```

Expected: non-zero because `ops/agent_pool/agent-pool` does not exist.

- [ ] **Step 3: Implement `common.sh`**

Create `ops/agent_pool/lib/common.sh` with:

```bash
#!/usr/bin/env bash

POOL_ROOT="${C2PRO_AGENT_POOL_ROOT:-/srv/c2pro/agent-pool}"
POOL_CONFIG="$POOL_ROOT/config"
POOL_RUNS="$POOL_ROOT/runs"
POOL_WORKTREES="$POOL_ROOT/worktrees"
POOL_TMP="$POOL_ROOT/tmp"

pool_log() { printf '%s\n' "$*"; }
pool_die() { local rc="$1"; shift; printf 'ERROR: %s\n' "$*" >&2; exit "$rc"; }
require_cmd() { command -v "$1" >/dev/null 2>&1 || pool_die 69 "missing command: $1"; }

validate_task_id() {
  [[ "$1" =~ ^[A-Za-z0-9][A-Za-z0-9._-]{0,79}$ ]] || pool_die 65 "invalid task_id: $1"
}

validate_sha() {
  [[ "$1" =~ ^[0-9a-f]{40}$ ]] || pool_die 65 "invalid git sha: $1"
}

manifest_get() {
  local manifest="$1" query="$2"
  jq -er "$query" "$manifest"
}
```

- [ ] **Step 4: Implement the command dispatcher**

Create `ops/agent_pool/agent-pool`:

```bash
#!/usr/bin/env bash
set -Eeuo pipefail

SELF_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# shellcheck source=lib/common.sh
source "$SELF_DIR/lib/common.sh"

usage() {
  cat <<'EOF'
Usage:
  agent-pool doctor
  agent-pool submit <manifest.json>
  agent-pool status <task-id>
  agent-pool harvest <task-id>
  agent-pool reset-lane <claude|gemini|codex|opencode>
EOF
}

case "${1:---help}" in
  -h|--help) usage ;;
  doctor|submit|status|harvest|reset-lane)
    cmd="$1"; shift
    source "$SELF_DIR/lib/lanes.sh"
    source "$SELF_DIR/lib/worktrees.sh"
    source "$SELF_DIR/lib/tasks.sh"
    "pool_${cmd//-/_}" "$@"
    ;;
  *) pool_die 64 "unknown command: $1" ;;
esac
```

Make executable.

- [ ] **Step 5: Run syntax and task tests**

Run:

```bash
bash -n ops/agent_pool/agent-pool ops/agent_pool/lib/common.sh
bash ops/agent_pool/tests/test_agent_pool.sh
```

Expected: `TASK1_TESTS=PASS`.

- [ ] **Step 6: Commit Task 1**

```bash
git add ops/agent_pool/agent-pool ops/agent_pool/lib/common.sh ops/agent_pool/tests/test_agent_pool.sh
git commit -m "feat(agent-pool): add command skeleton and guards"
```

---

### Task 2: Persistent Lane Configuration and `doctor`

**Files:**
- Create: `ops/agent_pool/lib/lanes.sh`
- Create: `ops/agent_pool/config/pool.env.example`
- Create: `ops/agent_pool/config/lanes/claude.env.example`
- Create: `ops/agent_pool/config/lanes/gemini.env.example`
- Create: `ops/agent_pool/config/lanes/codex.env.example`
- Create: `ops/agent_pool/config/lanes/opencode.env.example`
- Modify: `ops/agent_pool/tests/test_agent_pool.sh`

**Interfaces:**
- Produces: `lane_user`, `lane_cli`, `lane_health`, `pool_doctor`, `pool_reset_lane`.
- `lane_health <lane>` outputs exactly one state: `READY|BROKEN_AUTH|BROKEN_CONFIG|BROKEN_MODEL|BROKEN_TOOL`.

- [ ] **Step 1: Extend tests with fake CLIs and Gemini config**

Append a test fixture that prepends `$TMP/fakebin` to PATH, creates executable fake `claude`, `codex`, `opencode`, `tmux`, `gh`, and creates a fake Gemini home with `.gemini/.env` containing:

```bash
GOOGLE_CLOUD_PROJECT=test-project
GOOGLE_GENAI_USE_GCA=true
```

The fake `opencode models` must print `opencode/nemotron-3-ultra-free`. Assert that `doctor` prints one `READY` line per lane when `C2PRO_GEMINI_HOME` points to the fixture.

- [ ] **Step 2: Run test to verify `doctor` fails**

Run:

```bash
bash ops/agent_pool/tests/test_agent_pool.sh
```

Expected: failure because `lanes.sh` and `doctor` are not implemented.

- [ ] **Step 3: Add non-secret example configuration**

`pool.env.example`:

```bash
C2PRO_REPO_GH=AI-Gen-AI/C2Pro
C2PRO_REPO_DIR=/srv/aigen/dev/repos/C2Pro
C2PRO_OPENCODE_MODEL=opencode/nemotron-3-ultra-free
C2PRO_TASK_TIMEOUT_SECONDS=27000
C2PRO_STARTUP_PROBATION_SECONDS=180
```

`gemini.env.example` must contain only:

```bash
C2PRO_GEMINI_USER=aigen-gemini
C2PRO_GEMINI_HOME=/home/aigen-gemini
C2PRO_GEMINI_ENV=/home/aigen-gemini/.gemini/.env
```

Do not put `GOOGLE_CLOUD_PROJECT` in the repository example.

- [ ] **Step 4: Implement lane health functions**

`lanes.sh` must:

- require the configured CLI path/command;
- for Gemini, verify the dedicated env file exists, is readable by the Gemini identity and contains a non-empty `GOOGLE_CLOUD_PROJECT` or `GOOGLE_CLOUD_PROJECT_ID` without printing the value;
- verify `GOOGLE_GENAI_USE_GCA=true` is present;
- for OpenCode, verify the configured model is present in `opencode models`;
- classify deterministic failures instead of exiting the whole doctor run;
- write `$POOL_CONFIG/health/<lane>.state` during real installation/runtime doctor.

The Gemini check must use the dedicated identity rather than sourcing its file into the operator shell, e.g.:

```bash
sudo -u "$gemini_user" -H bash -lc '
  set -a
  source "$1"
  set +a
  [[ -n "${GOOGLE_CLOUD_PROJECT:-${GOOGLE_CLOUD_PROJECT_ID:-}}" ]]
  [[ "${GOOGLE_GENAI_USE_GCA:-}" == "true" ]]
' _ "$gemini_env"
```

- [ ] **Step 5: Run doctor tests**

Run:

```bash
bash -n ops/agent_pool/lib/lanes.sh
bash ops/agent_pool/tests/test_agent_pool.sh
```

Expected: all fixture lanes `READY` and no project value printed.

- [ ] **Step 6: Commit Task 2**

```bash
git add ops/agent_pool/lib/lanes.sh ops/agent_pool/config ops/agent_pool/tests/test_agent_pool.sh
git commit -m "feat(agent-pool): add persistent lane health checks"
```

---

### Task 3: Safe Persistent Worktree Lifecycle

**Files:**
- Create: `ops/agent_pool/lib/worktrees.sh`
- Modify: `ops/agent_pool/tests/test_agent_pool.sh`

**Interfaces:**
- Produces: `prepare_lane_worktree <lane> <sha>`, `assert_lane_clean <lane>`, `lane_worktree_path <lane>`.
- A dirty worktree must return state `DIRTY` and must never be cleaned automatically.

- [ ] **Step 1: Add isolated temporary Git repository tests**

Create a temporary bare remote + seed repository in the test script. Test that `prepare_lane_worktree claude <sha>` creates a detached worktree at the exact SHA. Then create an untracked file and verify a second preparation fails without deleting it.

- [ ] **Step 2: Run tests and observe expected failure**

```bash
bash ops/agent_pool/tests/test_agent_pool.sh
```

Expected: missing worktree implementation.

- [ ] **Step 3: Implement worktree preparation**

Core behavior:

```bash
lane_worktree_path() { printf '%s/%s\n' "$POOL_WORKTREES" "$1"; }

assert_lane_clean() {
  local wt
  wt="$(lane_worktree_path "$1")"
  [[ -e "$wt/.git" ]] || return 0
  [[ -z "$(git -C "$wt" status --porcelain)" ]] || return 22
}
```

`prepare_lane_worktree` must fetch required refs from the canonical repository, verify the requested object exists, refuse dirty lanes, create the worktree if absent, and for an existing clean pool-owned worktree detach it at the requested SHA using explicit Git commands. It must verify `rev-parse HEAD` equals the requested SHA after preparation.

- [ ] **Step 4: Run exact-head/dirty-state tests**

```bash
bash -n ops/agent_pool/lib/worktrees.sh
bash ops/agent_pool/tests/test_agent_pool.sh
```

Expected: exact SHA PASS; dirty worktree preserved and submission blocked.

- [ ] **Step 5: Commit Task 3**

```bash
git add ops/agent_pool/lib/worktrees.sh ops/agent_pool/tests/test_agent_pool.sh
git commit -m "feat(agent-pool): manage persistent isolated worktrees"
```

---

### Task 4: Review-Mode Runner and Mutation Guards

**Files:**
- Create: `ops/agent_pool/lib/runner.sh`
- Modify: `ops/agent_pool/tests/test_agent_pool.sh`

**Interfaces:**
- Consumes: lane, task directory, prompt path, exact HEAD, timeout.
- Produces each lane's required evidence files and final state.

- [ ] **Step 1: Add runner contract tests with fake agent CLIs**

Fake each model CLI to read its prompt and emit a deterministic verdict. Assert creation of:

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

Also test a fake non-zero agent exit maps to `FAILED`, while an injected quota message maps Codex to `BLOCKED_QUOTA` and Gemini project/auth messages map to `BLOCKED_AUTH`/`BLOCKED_CONFIG`.

- [ ] **Step 2: Add shell-level review mutation wrappers**

The runner creates a task-local `safe-bin/` ahead of PATH. Its `git` wrapper must deny at least:

```text
commit push merge rebase cherry-pick revert tag reset clean switch restore
```

The `gh` wrapper permits read-only commands such as `pr view`, `pr checks`, `issue view`, `run view/list`, `repo view` and GET-style `gh api`, while rejecting `-X`, `--method`, field arguments or explicit mutating HTTP methods.

Create deny wrappers for `railway`, `supabase`, and `vercel` in review mode.

- [ ] **Step 3: Implement exact lane invocations**

Claude must receive the prompt through stdin so variadic tool flags cannot consume it:

```bash
claude --print --output-format text --permission-mode plan \
  --allowedTools Read Glob Grep Bash \
  --disallowedTools Edit Write \
  < "$prompt"
```

Gemini must execute under the dedicated identity and source its env before invoking the CLI:

```bash
sudo -u "$gemini_user" -H bash -lc '
  set -Eeuo pipefail
  set -a; source "$1"; set +a
  cd "$2"
  exec gemini --skip-trust --approval-mode plan --output-format text --prompt "$(cat "$3")"
' _ "$gemini_env" "$worktree" "$prompt"
```

Codex review mode:

```bash
codex exec --sandbox read-only - < "$prompt"
```

OpenCode uses the configured validated model and read-only permission config:

```bash
OPENCODE_CONFIG_CONTENT="$policy_json" \
  opencode run --model "$C2PRO_OPENCODE_MODEL" "$(cat "$prompt")"
```

- [ ] **Step 4: Add post-run invariants**

After the model exits, write status, verify HEAD is unchanged, capture `git status --porcelain`, and mark the lane `DIRTY` rather than `COMPLETE` if repository state changed.

- [ ] **Step 5: Run runner tests**

```bash
bash -n ops/agent_pool/lib/runner.sh
bash ops/agent_pool/tests/test_agent_pool.sh
```

Expected: all runner states and mutation-denial tests PASS.

- [ ] **Step 6: Commit Task 4**

```bash
git add ops/agent_pool/lib/runner.sh ops/agent_pool/tests/test_agent_pool.sh
git commit -m "feat(agent-pool): add governed review runner"
```

---

### Task 5: `submit`, Startup Probation, and Independent Lane Failure

**Files:**
- Create: `ops/agent_pool/lib/tasks.sh`
- Modify: `ops/agent_pool/tests/test_agent_pool.sh`

**Interfaces:**
- Produces: `pool_submit`, task `manifest.json`, lane `state.txt`, and persistent tmux sessions.
- Submission succeeds when at least one requested healthy lane launches; unhealthy requested lanes are recorded individually and do not cancel other lanes unless manifest sets `require_all_lanes=true`.

- [ ] **Step 1: Add manifest fixture test**

Create a manifest containing exact 40-character HEAD/base values and prompt files for all four lanes. Test invalid SHA, missing prompt, duplicate task ID, busy lane and dirty lane rejection.

- [ ] **Step 2: Implement manifest validation**

Require:

- `.task_id`
- `.repository`
- `.head`
- `.base`
- `.mode == "review"`
- `.lanes` subset of four canonical names
- `.timeout_seconds` positive integer
- `.prompts.<lane>` file exists relative to the manifest directory.

- [ ] **Step 3: Implement task root and immutable manifest copy**

Create `$POOL_RUNS/$task_id`, copy prompts and canonicalize the submitted manifest to `$POOL_RUNS/$task_id/manifest.json`. Refuse if that task root already exists.

- [ ] **Step 4: Implement remote guards once per task**

When the manifest includes a PR number, use `gh api` read-only to verify remote HEAD/base/draft/open before any lane starts. Store the guard response as `pr-before.json`.

- [ ] **Step 5: Start independent tmux lane jobs**

Use stable session names `c2pro-agent-<lane>` as shells, but execute each task through a task-specific child command whose PID/task ID is recorded. Do not create a new long-lived tmux namespace per task.

- [ ] **Step 6: Implement bounded probation**

Poll requested launched lanes for `C2PRO_STARTUP_PROBATION_SECONDS` (default 180). A lane that exits non-zero in probation gets its classified state immediately. Never automatically retry auth/config/model/quota failures. At most one retry is allowed for a pre-classified deterministic invocation wrapper failure; v1 should normally surface the failure rather than invent a runtime fix.

- [ ] **Step 7: Verify independent failure behavior**

In tests, make fake Gemini fail while fake Claude/Codex/OpenCode continue and complete. Expected task submission does not kill successful lanes and final task summary contains the mixed states.

- [ ] **Step 8: Commit Task 5**

```bash
git add ops/agent_pool/lib/tasks.sh ops/agent_pool/tests/test_agent_pool.sh
git commit -m "feat(agent-pool): submit independent persistent lane work"
```

---

### Task 6: Compact `status` and `harvest`

**Files:**
- Modify: `ops/agent_pool/lib/tasks.sh`
- Modify: `ops/agent_pool/tests/test_agent_pool.sh`

**Interfaces:**
- `agent-pool status <task-id>`: compact one-line lane states.
- `agent-pool harvest <task-id>`: summary + decision signals + evidence paths; never full log dump by default.

- [ ] **Step 1: Add completed/mixed task fixtures**

Build fixture evidence for one `COMPLETE`, one `RUNNING`, one `BLOCKED_CONFIG`, one `NOT_REQUESTED`. Assert stable status output.

- [ ] **Step 2: Implement `status`**

Output format:

```text
TASK=pr604-r16e-r2 HEAD=<sha> MODE=review
claude   COMPLETE       exit=0   output_bytes=28110
Gemini   BLOCKED_CONFIG exit=55  output_bytes=0
codex    COMPLETE       exit=0   output_bytes=27848
opencode RUNNING        exit=-   output_bytes=0
```

Use canonical lowercase lane names in machine-readable JSON even if display alignment differs.

- [ ] **Step 3: Implement `harvest`**

Write/update `$task_root/summary.json` from evidence without mutating individual lane outputs. Print:

- task identity and exact HEAD/base;
- lane state matrix;
- `Executive Verdict`, `Severity: BLOCKER/HIGH`, `Merge blocking: YES`, `MASTER Recommendation`, and equivalent case-insensitive signals extracted from each completed `final-output.md`;
- full evidence file path for each lane;
- final note that MASTER reconciliation is required.

Do not concatenate entire model outputs by default.

- [ ] **Step 4: Test harvest does not change evidence**

Hash lane outputs before/after `harvest` and assert hashes are identical.

- [ ] **Step 5: Commit Task 6**

```bash
git add ops/agent_pool/lib/tasks.sh ops/agent_pool/tests/test_agent_pool.sh
git commit -m "feat(agent-pool): add compact status and harvest"
```

---

### Task 7: Idempotent VPS Installer and Real `doctor`

**Files:**
- Create: `ops/agent_pool/install.sh`
- Modify: `ops/agent_pool/tests/test_agent_pool.sh`

**Interfaces:**
- `install.sh` installs/updates the versioned pool without destroying worktrees/runs or credentials.

- [ ] **Step 1: Add installation fixture test**

Set `C2PRO_AGENT_POOL_ROOT` to a temporary path and run installer twice. Assert both succeed and previously created `$POOL_ROOT/runs/preserve-me/evidence.txt` survives the second install.

- [ ] **Step 2: Implement installation directories and copies**

Installer creates:

```bash
install -d -m 0750 "$POOL_ROOT/bin" "$POOL_ROOT/config/lanes" \
  "$POOL_ROOT/config/health" "$POOL_ROOT/worktrees" "$POOL_ROOT/runs" "$POOL_ROOT/tmp"
install -m 0750 "$SOURCE_DIR/agent-pool" "$POOL_ROOT/bin/agent-pool"
install -d -m 0750 "$POOL_ROOT/lib"
install -m 0640 "$SOURCE_DIR/lib/"*.sh "$POOL_ROOT/lib/"
```

The installed dispatcher must resolve libraries relative to installed location. Copy example config only when the real config does not yet exist.

- [ ] **Step 3: Preserve Gemini native configuration**

The installer records only the Gemini user/home/env path. It must not read and copy the actual project ID into pool files. `doctor` validates the existing native env under `aigen-gemini`.

- [ ] **Step 4: Make install run `doctor` once**

After installation, run:

```bash
"$POOL_ROOT/bin/agent-pool" doctor
```

Installation succeeds even if an optional lane is not READY, but prints the exact lane classification and exits non-zero only if core pool dependencies/repository are unavailable. This allows the pool to operate with 3/4 lanes while a fourth is explicitly broken.

- [ ] **Step 5: Run installer tests and shellcheck-style syntax checks**

```bash
bash -n ops/agent_pool/*.sh ops/agent_pool/lib/*.sh
bash ops/agent_pool/tests/test_agent_pool.sh
```

Expected: full test suite PASS and second install preserves runtime evidence.

- [ ] **Step 6: Commit Task 7**

```bash
git add ops/agent_pool/install.sh ops/agent_pool/tests/test_agent_pool.sh
git commit -m "feat(agent-pool): add idempotent VPS installer"
```

---

### Task 8: Real VPS Acceptance Without Touching PR604

**Files:**
- No production-code changes.
- Runtime evidence only under `/srv/c2pro/agent-pool/runs/agent-pool-v1-smoke-<timestamp>/`.

**Interfaces:**
- Validates the complete installed system before using it on a substantive PR.

- [ ] **Step 1: Install from an isolated implementation branch/worktree**

Run from the implementation worktree:

```bash
sudo -E bash ops/agent_pool/install.sh
```

Expected: pool installed; doctor lists per-lane health without printing secrets.

- [ ] **Step 2: Verify Gemini specifically uses the persistent native configuration**

Run:

```bash
/srv/c2pro/agent-pool/bin/agent-pool doctor
```

Expected Gemini state: `READY`, and output must not contain the project ID value itself.

- [ ] **Step 3: Submit a four-lane read-only smoke Work Order against current `main`**

Each prompt says: inspect exact HEAD read-only and return `<LANE>_POOL_OK <sha>`. No PR number is necessary for this smoke, so it cannot mutate/target PR604.

Run:

```bash
/srv/c2pro/agent-pool/bin/agent-pool submit /srv/c2pro/agent-pool-smoke/manifest.json
```

Expected: one task ID and four independent lane launch states.

- [ ] **Step 4: Disconnect/reconnect persistence check**

Detach from SSH, reconnect, then run:

```bash
/srv/c2pro/agent-pool/bin/agent-pool status <task-id>
```

Expected: processes/results persisted independently of the client session.

- [ ] **Step 5: Harvest smoke task**

```bash
/srv/c2pro/agent-pool/bin/agent-pool harvest <task-id>
```

Expected: compact evidence paths and exact reviewed SHA; no full logs dumped.

- [ ] **Step 6: Verify all four worktrees remained clean**

```bash
for lane in claude gemini codex opencode; do
  git -C "/srv/c2pro/agent-pool/worktrees/$lane" status --porcelain
done
```

Expected: no output.

- [ ] **Step 7: Run existing repository gates relevant to ops changes**

At minimum:

```bash
git diff --check main...HEAD
bash -n ops/agent_pool/*.sh ops/agent_pool/lib/*.sh
bash ops/agent_pool/tests/test_agent_pool.sh
```

Expected: all PASS.

- [ ] **Step 8: Commit any acceptance-only documentation adjustments, then request review**

No runtime evidence or secret-bearing config is committed.

---

## Plan Self-Review

- Spec coverage: all ten acceptance criteria map to Tasks 2–8.
- Secret handling: Gemini project value is never copied from its native protected environment; only the path and user are versioned.
- Failure isolation: Task 5 explicitly tests one broken lane while others complete.
- Routine efficiency: `doctor` owns expensive diagnostics; `submit/status/harvest` are the normal path.
- Mutation safety: Task 4 provides shell-level deny wrappers plus model-level read-only mode.
- No placeholder steps remain; commands, paths, states and interfaces are explicit.
- Scope remains v1-minimal: no generalized Work Graph, Capability Resolver or autonomous merge/deploy implementation.
