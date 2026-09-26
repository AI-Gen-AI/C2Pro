# Codex Authentication and Workspace 401 Runbook

**Date:** 2026-09-26  
**Status:** Operational workaround validated; exact root cause not fully proven  
**Applies to:** C2Pro remote VPS / Codex CLI / ChatGPT authentication

## 1. Symptom

Codex CLI can report a healthy ChatGPT login and still fail at request time with:

```text
401 Unauthorized: Incorrect API key provided: sk-svcac…REDACTED
https://chatgpt.com/backend-api/codex/responses
```

Observed local state at the same time:

```text
Logged in using ChatGPT
stored API key: false
stored ChatGPT tokens: true
stored auth mode: chatgpt
```

Do not assume the YubiKey, Device Code flow, or ChatGPT account is broken solely from this runtime 401.

## 2. Known-Good Evidence from the Incident

The following checks passed:

- Device Code authentication completed successfully.
- `~/.codex/auth.json` used `auth_mode=chatgpt`.
- `OPENAI_API_KEY`, `CODEX_API_KEY`, `CODEX_ACCESS_TOKEN`,
  `OPENAI_BASE_URL`, `OPENAI_FEDERATION_RULE_ID` and
  `OPENAI_IDENTITY_TOKEN_FILE` were not set in the shell.
- `codex doctor` reported:
  - auth configured;
  - ChatGPT tokens stored;
  - no stored API key;
  - provider reachability healthy;
  - WebSocket handshake HTTP 101.
- The ChatGPT `access_token` from `auth.json` was accepted by the backend:
  a deliberately incomplete direct request returned HTTP 400
  (`model None is not supported`) rather than HTTP 401.
- Codex worked in `/tmp` with `--skip-git-repo-check`.
- Codex worked in a new clean Git repository in `/tmp`.
- Codex worked inside C2Pro when either:
  - `features.shell_snapshot=false`, or
  - `features.workspace_dependencies=false`.

This isolates the failure to workspace/runtime context rather than the basic ChatGPT login.

## 3. Remote / Headless Login

On a VPS, avoid relying on the default browser callback to:

```text
http://localhost:1455/auth/callback
```

because `localhost` in the browser is the operator workstation, not necessarily the VPS.

Use:

```bash
codex login --device-auth
```

Complete the Device Code flow in the browser. A registered security key may be requested as part of normal account authentication.

After login:

```bash
codex login status
```

Expected:

```text
Logged in using ChatGPT
```

## 4. First-Line Safe Diagnostics

### 4.1 Never print secrets

Do not run:

```bash
cat ~/.codex/auth.json
```

Instead inspect structure only:

```bash
python3 - <<'PY'
import json
from pathlib import Path

p = Path.home() / ".codex" / "auth.json"
d = json.loads(p.read_text())

print("auth_mode =", d.get("auth_mode"))
for name in ("id_token", "access_token", "refresh_token"):
    value = d.get("tokens", {}).get(name)
    if not isinstance(value, str):
        print(name, "= MISSING")
        continue
    if value.startswith("sk-"):
        kind = "API_KEY_LIKE"
    elif value.startswith("eyJ") and value.count(".") == 2:
        kind = "JWT_LIKE"
    else:
        kind = "OPAQUE_OTHER"
    print(f"{name}: type={kind}, length={len(value)}")
PY
```

Expected for ChatGPT auth:

- `auth_mode = chatgpt`
- id/access tokens are JWT-like
- no API-key-like access token

### 4.2 Check environment without showing values (Bash)

```bash
for v in \
  OPENAI_API_KEY \
  CODEX_API_KEY \
  CODEX_ACCESS_TOKEN \
  OPENAI_BASE_URL \
  OPENAI_FEDERATION_RULE_ID \
  OPENAI_IDENTITY_TOKEN_FILE
do
  if [ -n "${!v+x}" ]; then
    case "$v" in
      *KEY*|*TOKEN*) echo "$v=<SET>" ;;
      *) echo "$v=${!v}" ;;
    esac
  else
    echo "$v=<NOT SET>"
  fi
done
```

### 4.3 Run doctor

```bash
codex doctor --json
```

Pay attention to:

- `auth.credentials`
- `config.load`
- `network.provider_reachability`
- `network.websocket_reachability`
- `updates.status`

A healthy doctor is necessary but not sufficient. Always follow with a real request.

### 4.4 Smoke-test a real request

```bash
codex exec "Reply with only: CODEX_AUTH_OK"
```

This is the final proof that the runtime is using a valid identity.

## 5. Distinguish Auth Failure from CLI/Workspace Failure

If Codex says ChatGPT login is healthy but a request returns 401 with a different credential identity, use a direct backend A/B test without displaying the token.

> **Sensitive diagnostic — owner-only.** Run this only as the credential owner on that owner's host. Never modify it to print or log `token` or `account_id`. The `chatgpt.com/backend-api/codex/responses` endpoint is private/undocumented and may change. The helper below redacts common key/JWT/account-id patterns, but review all output before sharing it anywhere.

```bash
python3 - <<'PY'
import json
import re
import urllib.request
import urllib.error
from pathlib import Path

auth = json.loads((Path.home() / ".codex" / "auth.json").read_text())
token = auth["tokens"]["access_token"]
account_id = auth["tokens"].get("account_id")

req = urllib.request.Request(
    "https://chatgpt.com/backend-api/codex/responses",
    data=b"{}",
    method="POST",
    headers={
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        **({"ChatGPT-Account-Id": account_id} if account_id else {}),
    },
)

def redact(s):
    s = re.sub(r"sk-[A-Za-z0-9_-]+", "sk-...REDACTED", s)
    s = re.sub(r"eyJ[A-Za-z0-9._-]+", "JWT_REDACTED", s)
    if account_id:
        s = s.replace(account_id, "ACCOUNT_ID_REDACTED")
    return s

try:
    with urllib.request.urlopen(req, timeout=30) as r:
        print("HTTP", r.status)
        print(redact(r.read().decode("utf-8", "replace")[:2000]))
except urllib.error.HTTPError as e:
    print("HTTP", e.code)
    print(redact(e.read().decode("utf-8", "replace")[:2000]))
except Exception as e:
    print(type(e).__name__, str(e))
PY
```

Interpretation:

- **HTTP 400 due to missing/unsupported model:** authentication was accepted; investigate CLI/workspace behavior.
- **HTTP 401:** investigate account/token/session/backend auth before changing workspace settings.

Do not use this as a normal inference path; it is a diagnostic A/B test.

## 6. Isolate the Workspace

### 6.1 Test outside the repository

```bash
cd /tmp
codex exec --skip-git-repo-check "Reply with only: CODEX_AUTH_OK"
```

### 6.2 Test in a clean Git repository

```bash
rm -rf /tmp/codex-auth-test
mkdir /tmp/codex-auth-test
cd /tmp/codex-auth-test
git init -q

codex exec "Reply with only: CODEX_GIT_OK"
```

If both work but C2Pro fails, the problem is workspace-specific.

## 7. Isolate Feature State

Inside C2Pro test each feature separately.

### Shell snapshot off

```bash
cd /srv/aigen/dev/repos/C2Pro

codex exec \
  -c 'features.shell_snapshot=false' \
  "Reply with only: SHELL_SNAPSHOT_OFF_OK"
```

### Workspace dependencies off

```bash
cd /srv/aigen/dev/repos/C2Pro

codex exec \
  -c 'features.workspace_dependencies=false' \
  "Reply with only: WORKSPACE_DEPENDENCIES_OFF_OK"
```

During the 2026-09-26 incident both tests succeeded.

This proves a workspace/runtime-state interaction but does **not** prove which feature is independently defective.

## 8. Operational Workaround

Preferred temporary workaround:

```bash
cd /srv/aigen/dev/repos/C2Pro

codex \
  -c 'features.shell_snapshot=false'
```

Reason for preferring this variant:

- it preserved `workspace_dependencies`, useful for dependency analysis;
- it avoided changing credentials;
- it restored successful inference in the affected workspace.

Do not make the setting permanent until the issue is reproduced after cache/state cleanup or upstream behavior is understood.

## 9. Toolchain Version and npm Prefix Pitfall

Observed toolchain layout:

```text
/srv/c2pro/toolchain/bin/codex
  -> /srv/c2pro/toolchain/npm/bin/codex
```

Running package root before repair:

```text
/srv/c2pro/toolchain/npm/lib/node_modules/@openai/codex
```

But the normal global npm root was:

```text
/srv/c2pro/toolchain/node/v22.23.2/lib/node_modules
```

Therefore:

```bash
npm install -g @openai/codex
```

could update a different installation from the one actually executed.

Before any update, discover the active executable and npm roots:

```bash
readlink -f "$(command -v codex)"
npm prefix -g
npm root -g
codex --version
```

Then target the package root that actually backs the active Codex executable and use the **currently approved Codex version**. During this incident, the approved target was 0.157.0 and the command used was:

```bash
npm install -g \
  --prefix /srv/c2pro/toolchain/npm \
  @openai/codex@0.157.0
```

That version pin is historical evidence, not a standing recommendation; reusing it later could downgrade Codex.

After any update, verify:

```bash
hash -r
codex --version
codex doctor --json
```

`updates.status` should report local consistency.

## 10. What Not to Do

Do **not**:

- revoke a service-account key merely because its redacted prefix appears in a 401;
- paste full API keys, access tokens, refresh tokens or `auth.json` into chat/issues;
- delete `auth.json` before proving local auth storage is the problem;
- clear snapshots/caches before preserving diagnostic evidence;
- repeatedly redo Device Code login once a direct JWT request proves the token is accepted;
- assume upgrading Codex alone fixes a workspace-state bug;
- update the wrong npm root.

## 11. Incident Decision Tree

```text
Codex runtime 401
      |
      v
codex login status / doctor healthy?
      | no
      +--> repair login / network / config
      |
     yes
      |
      v
real codex exec succeeds?
      | yes --> done
      |
     no
      |
      v
direct JWT request accepted (HTTP 400 vs 401)?
      | no --> auth/backend issue
      |
     yes
      |
      v
/tmp or clean repo succeeds?
      | no --> CLI/global runtime issue
      |
     yes
      |
      v
workspace-specific
      |
      +--> shell_snapshot=false
      |
      +--> workspace_dependencies=false
      |
      v
use minimal workaround + investigate state separately
```

## 12. Incident Facts to Preserve

- Original Codex version: 0.153.4
- Updated Codex version: 0.157.0
- Authentication mode: ChatGPT / Device Code
- Direct JWT diagnostic: authenticated HTTP 400 on incomplete request
- Clean `/tmp` execution: PASS
- Clean Git repo execution: PASS
- C2Pro + `shell_snapshot=false`: PASS
- C2Pro + `workspace_dependencies=false`: PASS
- Exact root cause: **not yet proven**
- Safe operational mitigation: disable `shell_snapshot` for the affected workspace/session

## 13. Follow-Up

If the incident recurs:

1. preserve `codex doctor --json` output;
2. record Codex version and exact workspace;
3. run the smoke test outside the workspace;
4. test the two feature flags separately;
5. inspect snapshot/workspace state without exposing secrets;
6. only then decide whether to clean cache/state or file an upstream bug.

Related lesson: [LL-002](./LESSONS_LEARNED.md).
