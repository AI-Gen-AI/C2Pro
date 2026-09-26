# C2PRO-DEV-03 — Principal Worker Readiness v2

**Status:** PLANNED RESTART PACKAGE / EXECUTION NOT AUTHORIZED  
**C2Pro planning baseline:** `4c26ebc740139ff6754dcda6e3dd393c9e1d8f01`  
**AI-Gen authority baseline reviewed:** `2bc886a8c90bb5d67b955c9ed18d71946e321f34`  
**Issue:** #674  
**Historical input:** PR #565, closed without merge

## 1. Purpose

DEV-03 v2 qualifies Claude Code and Codex as C2Pro principal-capable execution surfaces **without conflating principal class, route qualification, role eligibility or current job authority**.

This package creates no provider invocation authority. Presence in Git, CI green, merge of this documentation package or historical qualification evidence does not authorize a live worker call.

## 2. Governing invariants

```text
principal capability
!= route qualification
!= role eligibility
!= route health
!= current job authority
```

A worker can be principal-capable while no currently healthy route exists for the requested role.

A subordinate worker can have a live-qualified route and still be unable to satisfy a C2Pro principal gate.

Worker handoff preserves semantic WORK identity. It never silently changes role, scope or acceptance criteria to make a route appear eligible.

## 3. Current external truth frozen for planning

At AI-Gen `2bc886a8c90bb5d67b955c9ed18d71946e321f34`:

### Codex
- worker identity: `aigen-codex`
- adapter: `codex_cli`
- route: `CODEX_OPENAI_DEFAULT`
- observed qualification: `QUALIFIED_LIVE`
- currently qualified Academy role: `BACKEND_ENGINEER`
- authority model: job-bound / consumed / no standing provider authority

### Claude Code
- worker identity: `aigen-claude`
- adapter: `claude_code`
- route: `CLAUDE_ANTHROPIC_OPUS5_TARGET`
- observed qualification: `QUALIFIED_BOUNDED`
- qualified roles: `SOFTWARE_ARCHITECT`, `SYSTEM_COHERENCE_REVIEWER`
- observed model: `claude-opus-5`
- observed workspace ceiling: job-local read-only
- current Agent Factory master records `route_health=BLOCKED_REQUALIFICATION` and `live_routable=false`

These are planning observations, not C2Pro-owned route authority. DEV-03 must re-read current Agent Factory truth before each live qualification slice.

## 4. Historical PR #565 disposition

### KEEP
- Claude Code + Codex are C2Pro principal-capable.
- role identity is separate from worker/model/route identity.
- raw credentials never enter Git evidence.
- canonical main, Runtime, secrets and cross-workspace denial require proof.
- resource ceilings and timeout are qualification gates.
- handoff preserves WORK identity.

### REVALIDATE
- host OS/resources;
- worker accounts, groups and HOME modes;
- CLI path/version/owner/mode/hash;
- typed auth state;
- sandbox primitives;
- route health.

### REPLACE
- MR-DEV-01C as a still-future global blocker;
- expectation of standing Development provider authority;
- requirement that both principals prove identical live capabilities;
- assumption that principal-to-principal fallback preserves the same role automatically.

## 5. Qualification slices

### DEV-03R0 — Rebind baselines
Freeze exact C2Pro and AI-Gen SHAs and re-read current routing/authority records before execution.

### DEV-03R1 — Host / identity refresh
Read-only, non-secret inventory only.

Record:
- OS identity;
- CLI binary path/version/provenance;
- owner/group/mode;
- sandbox/resource primitives;
- typed auth state: `AUTHENTICATED | NOT_AUTHENTICATED | REAUTH_REQUIRED | UNKNOWN`.

Never emit token, cookie, API key, session payload, email, organization identifier or environment dump.

### DEV-03R2 — Route/role reconciliation
For each principal record:
- C2Pro authority class;
- worker ID;
- OS identity;
- adapter;
- role eligibility;
- route;
- exact qualification state;
- route health;
- workspace/tool/network ceiling;
- exact model when qualification is model-specific;
- fresh authority requirement.

Contradictions fail closed.

### DEV-03R3 — Codex bounded implementation
Requires a **fresh job/work authority** issued by the governing Agent Factory path.

Prove:
- isolated job-local workspace;
- bounded implementation fixture;
- deterministic tests;
- allowed commit/candidate sealing only inside job scope;
- canonical main denial;
- Runtime/secrets/cross-workspace denial;
- timeout/resource enforcement;
- structured `c2pro-implementation-result-v1`.

This creates no standing authority.

### DEV-03R4 — Claude bounded architecture/coherence
Do not execute while current route health remains blocked.

After governing requalification and fresh job authority:
- use only `SOFTWARE_ARCHITECT` or `SYSTEM_COHERENCE_REVIEWER`;
- job-local read-only repository surface;
- no product-code write;
- no merge/deployment;
- exact route/model evidence;
- bounded result suitable for principal review evidence.

If requalification does not close, record **PRINCIPAL_CAPABLE / CURRENT_ROUTE_BLOCKED**, not READY.

### DEV-03R5 — Negative boundaries
Prove fail-closed behavior for:
- canonical main mutation;
- Product Runtime use/write;
- secrets access;
- other principal workspace access;
- forbidden paths;
- stale baseline/job authority.

### DEV-03R6 — Resource/timeout
Reuse the qualified Agent Factory job-bound resource policy. Evidence must show the actual enforced timeout/resource result, not only configuration text.

### DEV-03R7 — Role-compatible handoff
Valid examples:

```text
Codex BACKEND_ENGINEER implementation
  -> Claude SYSTEM_COHERENCE_REVIEWER
     only when Claude route is currently qualified/healthy for that role

Claude architecture finding
  -> Codex BACKEND_ENGINEER remediation
     through explicit role reassignment + fresh compatible authority
```

Invalid:

```text
Claude route unavailable
  -> silently relabel role so fallback can run

Codex implementation qualification
  -> infer Claude implementation qualification

subordinate live route
  -> satisfy principal review gate
```

When no compatible principal route is available, preserve WORK and enter a controlled blocked/reassignment state.

## 6. Activation rule

This branch intentionally does **not** edit:
- `.c2pro/control/current.yaml`
- `.c2pro/control/work-queue.yaml`

After #669 becomes canonical on `main`:

1. refresh the DEV-03 envelope `base_sha`;
2. reconcile current Agent Factory SHA and route truth;
3. bind `C2PRO-DEV-03` into hot control;
4. activate only the first authorized qualification slice;
5. keep provider invocation separately job-authorized and consumed.

## 7. DONE semantics

DEV-03 must not collapse to one global `READY=true`.

DONE requires a per-principal/per-role record answering:

```text
PRINCIPAL_CAPABLE?
EXECUTION_IDENTITY?
CURRENT_ROUTE?
QUALIFIED_ROLES?
ROUTE_HEALTH?
TYPED_AUTH_STATE?
FRESH_JOB_AUTHORITY_REQUIRED?
NEGATIVE_BOUNDARIES_PROVEN?
RESOURCE_TIMEOUT_PROVEN?
HANDOFF_SEMANTICS_PROVEN?
CURRENT_BLOCKERS?
```

A blocked Claude route may remain an explicit residual if the accepted operating model still preserves the required C2Pro principal-review guarantees through a separately qualified compatible principal path. That acceptance is a control decision, never inferred from technical capability alone.
