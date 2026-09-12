# C2PRO-DEV-03 — Claude Code + Codex Principal Worker Readiness

**Status:** ACTIVE / PHASE 03A HOST READINESS
**Baseline:** `0400c05e8af1458aaa14bc47a8378d9cdd560284`
**Scope:** Development only. No Product Runtime mutation. No direct `main` worker mutation.

## 1. Purpose

Qualify Claude Code and Codex as the two C2Pro PRINCIPAL coding workers on the VPS while reusing the AI-Gen AF-DEV execution plane and preserving the AI-Gen MR-DEV authority boundary.

DEV-03 does not infer readiness from documentation or from a local PC installation. Every readiness claim must be evidenced on the VPS.

## 2. Cross-project authority boundary

AI-Gen AF-DEV already provides the qualified execution substrate and separate dry-run adapters for `CLAUDE_CODE` and `CODEX_CLI`.

AI-Gen `MR-DEV-01C` remains the gate for live Development provider/model invocation. Therefore DEV-03 is split:

- **DEV-03A — host/readiness:** allowed now; inventory, identities, binary discovery/version, filesystem/security boundaries and non-provider local CLI checks.
- **DEV-03B — live principal qualification:** only after the AI-Gen MR-DEV-01C authority record explicitly permits the applicable live Development route/provider invocation.

C2Pro must not create an independent bypass around MR-DEV.

## 3. Principal semantics

- `claude_code` class = PRINCIPAL
- `codex` class = PRINCIPAL
- role identity remains separate from worker identity.
- qualification is per execution surface and identity.
- one principal does not inherit the other principal's auth, quota or readiness.
- raw credentials/session secrets never enter C2Pro Git evidence.

## 4. Work packages

### DEV-03A1 — VPS host baseline

Collect:

- current operator identity and host;
- OS/kernel;
- CPU/RAM/disk baseline;
- tmux state;
- Bubblewrap, `timeout`, `prlimit`, Git, Node/npm and Python availability;
- relevant service users and groups;
- canonical Development/Runtime filesystem metadata only, without traversing secret material.

### DEV-03A2 — principal binary inventory

For `claude` and `codex`, record:

- found/not found;
- resolved path;
- owner/group/mode;
- package/source where determinable;
- local `--version` result;
- no provider prompt or job is sent.

### DEV-03A3 — execution identity inventory

Determine which existing or new OS identities will own each principal worker. Required outcome:

- explicit Claude identity;
- explicit Codex identity;
- no passwordless sudo;
- canonical Development non-writable;
- Product Runtime non-writable and non-traversable under the AF-DEV sandbox boundary;
- cross-worker workspace denial.

Do not create users until inventory shows what already exists.

### DEV-03A4 — auth/session state

Record only typed state:

- `AUTHENTICATED`
- `NOT_AUTHENTICATED`
- `UNKNOWN`
- `REAUTH_REQUIRED`

Do not print environment values, tokens, cookies, API keys, session files or credential payloads.

Any required interactive login/account change is owner-assisted and remains outside unattended automation.

### DEV-03A5 — installation/update decision

Install or update only when required by evidence. Before any install:

- identify current source/version;
- identify intended official package/source;
- preserve worker isolation;
- do not replace unrelated system Node/Python stacks unnecessarily;
- no `curl | sh` style unreviewed install.

### DEV-03B1 — non-interactive provider smoke

**BLOCKED until MR-DEV-01C grants applicable live Development invocation authority.**

Each principal must return a deterministic trivial result through its qualified route without product mutation.

### DEV-03B2 — AF-DEV isolated read-only job

Each principal reads a job-local C2Pro clone and returns a bounded answer. Canonical Development and Runtime stay hidden/denied.

### DEV-03B3 — AF-DEV isolated write+commit job

Each principal makes one bounded fixture-only change and commit in a job-local clone. No remote push is needed for the qualification fixture.

### DEV-03B4 — negative security probes

Prove:

- canonical `main` cannot be written by worker identity;
- Runtime cannot be used or mutated;
- secrets cannot be read;
- other worker workspace cannot be read;
- forbidden path attempt fails closed;
- stale BASE_SHA fails closed.

### DEV-03B5 — resource/time enforcement

Prove timeout and resource ceiling behavior using the existing AF-DEV policy primitives.

### DEV-03B6 — reciprocal handoff readiness

Prove that the same WORK can be transferred Claude → Codex and Codex → Claude while preserving:

- `work_id`;
- role;
- `base_sha`;
- scope/out-of-scope;
- acceptance criteria;
- required tests;
- known findings.

## 5. First command block — DEV-03A1/A2 read-only inventory

Run as the normal VPS administrative Development operator. This block must not install, authenticate or mutate anything.

```bash
printf '\n=== C2PRO DEV-03A — PRINCIPAL WORKER HOST INVENTORY ===\n'
printf 'timestamp='; date -Is
printf 'user='; id -un
printf 'uid_gid='; id
printf 'host='; hostname
printf 'kernel='; uname -srmo
printf 'os='; . /etc/os-release && printf '%s %s\n' "$ID" "$VERSION_ID"

printf '\n--- RESOURCE BASELINE ---\n'
free -h
printf '\n'
df -h / /home /opt /srv 2>/dev/null || true

printf '\n--- REQUIRED LOCAL PRIMITIVES ---\n'
for c in git bwrap timeout prlimit node npm python3 tmux; do
  printf '%-10s ' "$c"
  if p=$(command -v "$c" 2>/dev/null); then
    printf 'FOUND %s\n' "$p"
  else
    printf 'NOT_FOUND\n'
  fi
done

printf '\n--- PRINCIPAL CLI DISCOVERY ---\n'
for c in claude codex; do
  printf '\n[%s]\n' "$c"
  if p=$(command -v "$c" 2>/dev/null); then
    printf 'path=%s\n' "$p"
    stat -c 'owner=%U group=%G mode=%a size=%s' "$p" 2>/dev/null || true
    printf 'version=' 
    "$c" --version 2>&1 | head -n 3 || true
  else
    printf 'status=NOT_FOUND\n'
  fi
done

printf '\n--- RELEVANT LOCAL IDENTITIES ---\n'
getent passwd | awk -F: '$1 ~ /(aigen|codex|claude|gemini|openclaw|opencode)/ {print $1 ":uid=" $3 ":gid=" $4 ":home=" $6 ":shell=" $7}'

printf '\n--- GROUPS ---\n'
getent group | awk -F: '$1 ~ /(aigen|codex|claude|gemini|openclaw|opencode)/ {print}'

printf '\n--- TMUX ---\n'
tmux ls 2>&1 || true

printf '\nC2PRO_DEV_03A1_A2=COMPLETE\n'
```

### Safety note

Do **not** run `env`, `printenv`, `cat ~/.config/...`, `cat ~/.claude/...`, `cat ~/.codex/...`, credential helpers, token files or session JSON while collecting this evidence.

## 6. Evidence handling

Paste the command output back into the working conversation. The orchestrator will classify it and update the machine-readable readiness record. Raw command output is not automatically committed; only normalized non-secret evidence is stored.

## 7. Exit gate

DEV-03 can be marked DONE only when both principals have:

1. explicit installation and binary provenance;
2. explicit worker identity;
3. typed auth/session state without secret disclosure;
4. non-interactive invocation under authorized MR-DEV route;
5. isolated read-only qualification PASS;
6. isolated bounded write+commit qualification PASS;
7. canonical main/Runtime/secrets denial PASS;
8. timeout/resource enforcement PASS;
9. reciprocal handoff continuity PASS;
10. compact evidence references frozen.

If MR-DEV-01C remains closed, DEV-03 remains `IN_PROGRESS_BLOCKED_AT_LIVE_INVOCATION` after all 03A checks are complete.
