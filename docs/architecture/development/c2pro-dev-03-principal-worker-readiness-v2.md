# C2PRO-DEV-03 v2 — Principal Worker Readiness

**Status:** PLANNED / RESTART PACKAGE  
**C2Pro baseline:** `d7d1e6c2a2491feaafa56ccb41aafd86d9df2a4d`  
**AI-Gen baseline reviewed:** `AI-Gen-AI/2SB@2bc886a8c90bb5d67b955c9ed18d71946e321f34`

## Decision

DEV-03 no longer treats Claude Code and Codex as interchangeable workers. C2Pro preserves both as **PRINCIPAL-capable**, while execution remains separately gated by role eligibility, route qualification, route health and fresh job-bound authority.

```text
principal capability
  != role eligibility
  != route qualification
  != route health
  != current job authority
```

Historical PR #565 is evidence/design input only. It closed without merge and its MR-DEV-01C assumptions are superseded.

## Current external authority

AI-Gen Agent Factory currently records:

- AF-DEV-01 DONE and independently reviewed;
- Academy authority model = `JOB_BOUND_CONSUMED_NO_STANDING_AUTHORITY`;
- Codex route `CODEX_OPENAI_DEFAULT` = `QUALIFIED_LIVE` for `BACKEND_ENGINEER`;
- Claude route `CLAUDE_ANTHROPIC_OPUS5_TARGET` = `QUALIFIED_BOUNDED` for `SOFTWARE_ARCHITECT` and `SYSTEM_COHERENCE_REVIEWER`;
- Claude current master route-health evidence also records `BLOCKED_REQUALIFICATION` / `live_routable=false`, so fresh route-health reconciliation is mandatory;
- no standing provider, merge, deployment or Product Runtime authority is inherited.

## Restart sequence

### DEV-03R0 — exact authority rebind
Freeze exact C2Pro and AI-Gen SHAs and the current Agent Factory route/role policy. Any later drift requires explicit reconciliation before qualification evidence is promoted.

### DEV-03R1 — non-secret host / identity / active-binary refresh
Revalidate only non-secret facts: OS identity, account/home metadata, CLI path/version/hash/provenance, sandbox/resource primitives and typed auth state. Never dump environment/session/token contents.

Recent C2Pro Codex evidence adds two mandatory rules:

1. **Login state is not execution proof.** A healthy `codex login status` / typed ChatGPT auth state does not prove a real request will use the same credential identity. Qualification requires a minimal bounded execution smoke under the exact job workspace, with only redacted/typed result metadata retained.
2. **Update target is not executable provenance.** Resolve `command -v` + `readlink -f` (or equivalent) and record the active installation root/version/hash before any update or qualification. Do not assume a generic global npm install changes the binary actually invoked by the C2Pro toolchain.

For workspace-specific failures, compare a clean disposable Git workspace with the bounded C2Pro job workspace before concluding authentication is broken. Workspace/session features may be isolated only as a diagnostic; a mitigation is not promoted to canonical policy without separate review.

### DEV-03R2 — route/role reconciliation
Build one record per principal containing worker id, OS identity, adapter, eligible roles, route state, route health, tool/workspace/network ceiling, exact model binding when applicable and fresh-authority requirement. Contradictions fail closed.

### DEV-03R3 — Codex bounded implementation
With a fresh authorized job/work ID, prove an isolated bounded implementation fixture, deterministic tests, job-local commit/candidate seal, denial of canonical main/runtime/secrets/cross-workspace, resource limits and a structured `c2pro-implementation-result-v1`.

### DEV-03R4 — Claude bounded architecture/coherence
Only after route-health revalidation. With fresh bounded authority, prove a read-only `SOFTWARE_ARCHITECT` or `SYSTEM_COHERENCE_REVIEWER` task, exact route/model evidence, denial of writes/merge/deploy/runtime, resource limits and a structured review/analysis result.

If the route remains blocked, record Claude as PRINCIPAL-capable but not currently live-routable. Do not fabricate readiness.

### DEV-03R5 — governed handoff
Prove that the semantic WORK survives reassignment:
- Codex implementation → Claude architecture/coherence review only when the Claude role/route is compatible;
- Claude finding → Codex implementation follow-up only when Codex role/route is compatible;
- unavailable target route → controlled BLOCKED/reassignment state.

Handoff preserves work ID, baseline, objective, scope, invariants, acceptance criteria, completed/remaining work, findings and evidence refs. Role or worker changes require explicit governed reassignment.

### DEV-03R6 — reconciliation
Record readiness per principal **and per role**. A single `READY=true` flag is insufficient.

## Exit gate

DEV-03 can close only when current evidence establishes:
1. exact C2Pro + AI-Gen baselines;
2. principal identity/provenance;
3. route/role eligibility and health;
4. fresh job-bound authority semantics;
5. required negative boundaries;
6. timeout/resource enforcement;
7. identity-preserving handoff;
8. independent review;
9. no standing authority inference.

This package itself grants no provider invocation or worker execution authority.
