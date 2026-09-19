# SonarCloud read-only access runbook

**Repository:** `AI-Gen-AI/C2Pro`  
**SonarCloud project key:** `AI-Gen-AI_C2Pro`  
**API host:** `https://sonarcloud.io`  
**Verified from C2Pro VPS:** 2026-09-19

## Canonical access mode

For read-only issue queries against the public C2Pro SonarCloud project, **no `SONAR_TOKEN` is required**.

Verified probe:

```bash
SONAR="https://sonarcloud.io"
PROJECT="AI-Gen-AI_C2Pro"

curl -fsS --max-time 20   "$SONAR/api/issues/search?componentKeys=$PROJECT&resolved=false&ps=1" |
jq -r '.total'
```

A successful public read returns HTTP 200 and valid JSON.

Exact issue lookup:

```bash
TARGET="<sonar-issue-key>"

curl -fsS --max-time 20   "$SONAR/api/issues/search?issues=$TARGET&resolved=false&ps=10" |
jq '{total, issues: [.issues[] | {key, rule, status, component, line, message}]}'
```

## Operational rules

1. **Do not search the VPS recursively for a Sonar token just to read public SonarCloud data.**
2. Use the public API first. Only investigate credentials if the public endpoint later returns an authorization failure such as HTTP 401/403.
3. Never print credential values while diagnosing auth. If a token becomes necessary, provision a dedicated least-privilege credential rather than reusing unrelated session/user credentials.
4. Treat `.total` as a **point-in-time count**, not as a historical baseline. Counts can change as analyses and issue state change.
5. For before/after debt reconciliation, bind the comparison to the exact Sonar analyses/revisions and identical query semantics. Do not fail a gate solely because today's total differs from a previously observed total.
6. Prefer exact issue keys/rules/components for targeted reconciliation over whole-project counts.

## 2026-09-19 verification note

The unauthenticated API probe from the VPS returned HTTP 200, and exact lookup of the R16 target issue worked without credentials. During the same investigation, whole-project unresolved counts differed from an earlier R20B observation, so historical debt deltas must be analysis-bound rather than inferred from a live total.

This runbook is the canonical starting point for future SonarCloud read-only investigations in C2Pro.
