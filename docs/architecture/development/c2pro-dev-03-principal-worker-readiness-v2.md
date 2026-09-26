# C2PRO-DEV-03 — Principal Worker Readiness v2

**Status:** PLANNED RESTART PACKAGE / EXECUTION NOT AUTHORIZED  
**C2Pro planning baseline:** `4c26ebc740139ff6754dcda6e3dd393c9e1d8f01`  
**AI-Gen authority baseline reviewed:** `bab45b6833b52bf79fc82e585171d6ef8f2d9584`  
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

Worker handoff preserves semantic WORK identity, including **role**. It never changes role, scope or acceptance criteria to make a route appear eligible. A role change is a separate linked work/review stage, not a handoff of the same WORK.

## 3. Current external truth frozen for planning

At AI-Gen `bab45b6833b52bf79fc82e585171d6ef8f2d9584`:

### Codex
- worker identity: `aigen-codex`
- adapter: `codex_cli`
- route: `CODEX_OPENAI_DEFAULT`
- observed qualification: `QUALIFIED_LIVE`
- currently qualified Academy role: `BACKEND_ENGINEER`
- current provider invocation state: `DEGRADED_EXTERNAL_AUTH_PATH`
- current registry evidence: `/models` entitlement succeeds while `/responses` returns HTTP 401; route qualification itself is not revoked
- live use therefore requires a fresh successful endpoint preflight before any provider invocation
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
- CLI path/version/owner/mode/hash and active executable installation root;
- typed auth state;
- sandbox primitives;
- route health.

### REPLACE
- MR-DEV-01C as a still-future global blocker;
- expectation of standing Development provider authority;
- requirement that both principals prove identical live capabilities;
- assumption that principal-to-principal fallback preserves the same role automatically.

## 4A. Durable execution-binding evidence

The current Agent Factory baseline includes fail-closed durable persistence for `SessionExecutionBindingV1` and `ExecutionLifecycleReceiptV1`.

DEV-03 uses those artifacts as **evidence binding**, not as a second authority source. The governing one-shot/job-bound authority remains authoritative for whether execution may occur.

Every live qualification leg therefore requires:
- one immutable canonical execution binding with externally verified SHA-256;
- binding fields matching work ID, worker, adapter, execution identity, route/authority refs and job workspace;
- monotonic lifecycle receipts published under the Agent Factory lock/atomic persistence rules;
- terminal disposition `CLOSED_CLEAN`, `FAILED_CLEAN` or explicit `RECONCILIATION_REQUIRED`;
- no reopened terminal lifecycle;
- fail-closed qualification if binding or receipt verification fails.

This makes cross-process handoff/qualification attributable to the exact bounded authority and workspace rather than to transient console output alone.

## 5. Qualification slices

### DEV-03R0 — Rebind baselines
Freeze exact C2Pro and AI-Gen SHAs and re-read current routing/authority records before execution.

### DEV-03R1 — Host / identity / active-executable refresh
Read-only, non-secret inventory only.

Record:
- OS identity;
- CLI binary path/version/provenance;
- the **resolved active executable** and installation root (`command -v` + `readlink -f` or equivalent);
- owner/group/mode;
- sandbox/resource primitives;
- typed auth state: `AUTHENTICATED | NOT_AUTHENTICATED | REAUTH_REQUIRED | UNKNOWN`;
- a minimal bounded execution-identity smoke result.

Two recent C2Pro Codex lessons are mandatory:

1. **Login state is not execution proof.** A healthy `codex login status` / typed ChatGPT auth state does not prove a real request will use the same credential identity. Qualification requires a minimal bounded execution smoke in the exact job workspace. Evidence records only typed/redacted outcome metadata, never tokens.
2. **Update target is not executable provenance.** A generic package update can modify a different installation from the binary reached by the C2Pro toolchain. Resolve the active executable root before any update, version assertion or qualification.

If a request works in a clean disposable Git workspace but fails in the bounded C2Pro job workspace, classify it as workspace/runtime-context evidence before concluding authentication itself is broken. Feature isolation may diagnose the interaction, but a temporary mitigation does not become policy automatically.

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

### DEV-03R3 — Codex endpoint preflight + bounded implementation
The current recorded provider invocation path is degraded. Do not infer live readiness from `QUALIFIED_LIVE`.

First require a fresh endpoint preflight that proves the actual invocation path is operational. Only then may a **fresh job/work authority** issued by the governing Agent Factory path be consumed.

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

### DEV-03R7 — Same-role principal handoff

A same-WORK handoff is valid only when the replacement principal has a qualified, healthy route for the **same canonical role**.

The immutable handoff identity is:

```text
work_id
role
base_sha
scope
out_of_scope
acceptance_criteria
```

Example of a valid handoff shape:

```text
WORK(role=implementation_lead, worker=principal-A)
  -> provider/quota failure
  -> WORK(role=implementation_lead, worker=principal-B)
```

but only when principal-B is actually route-qualified and authorized for `implementation_lead`.

A cross-role flow is **not** a handoff:

```text
implementation WORK
  -> independent review WORK/stage
  -> remediation WORK/stage
```

Those stages must be linked explicitly to the source work/campaign while keeping their own role identity.

At the current Agent Factory baseline, Codex is qualified for `BACKEND_ENGINEER` while Claude is qualified for `SOFTWARE_ARCHITECT` / `SYSTEM_COHERENCE_REVIEWER`. No shared exact qualified role between the two principals is currently proven. Therefore the reciprocal same-role handoff gate is honestly **BLOCKED**, not inferred from C2Pro's abstract eligibility table.

Invalid:

```text
Claude route unavailable
  -> silently relabel the same WORK to a Claude-qualified role

Codex implementation
  -> call Claude coherence review a handoff of the implementation WORK

Codex implementation qualification
  -> infer Claude implementation qualification

subordinate live route
  -> satisfy principal review gate
```

When no compatible same-role principal route exists, preserve the original WORK unchanged and enter a controlled blocked state or create a separately authorized linked stage.

## 6. C2Pro principal-review gate

C2Pro and Agent Academy use different authority classes for assurance.

Current Agent Academy truth:

- `INDEPENDENT_REVIEW_LEAD` → `OPENCODE_NEMOTRON / NVIDIA_NEMOTRON3_SUPER` is `QUALIFIED_LIVE`;
- under C2Pro authority, OpenCode/Nemotron remains **SUBORDINATE** and cannot satisfy the independent-principal promotion gate;
- Claude Code is principal-capable but is qualified only for `SOFTWARE_ARCHITECT` and `SYSTEM_COHERENCE_REVIEWER`, not `INDEPENDENT_REVIEW_LEAD`;
- Codex is principal-capable and qualified for `BACKEND_ENGINEER`; the same worker cannot independently approve its own material implementation.

Therefore DEV-03 currently has a **real promotion blocker**:

```text
material Codex implementation
    ↓
requires different PRINCIPAL reviewer
    ↓
no compatible healthy principal-review route proven yet
    ↓
BLOCK
```

The existing Nemotron route remains valuable as challenger/assurance evidence, but it cannot be promoted into a C2Pro principal gate by relabeling it.

Closure requires a fresh, explicit qualification of a compatible principal review route. Existing Claude coherence evidence may be supporting input but **qualification inheritance is forbidden**.

## 7. Activation rule

This branch intentionally does **not** edit:
- `.c2pro/control/current.yaml`
- `.c2pro/control/work-queue.yaml`

After #669 becomes canonical on `main`:

1. refresh the DEV-03 envelope `base_sha`;
2. reconcile current Agent Factory SHA and route truth;
3. bind `C2PRO-DEV-03` into hot control;
4. activate only the first authorized qualification slice;
5. keep provider invocation separately job-authorized and consumed.

## 8. DONE semantics

DEV-03 must not collapse to one global `READY=true`.

DONE requires a per-principal/per-role record answering:

```text
PRINCIPAL_CAPABLE?
EXECUTION_IDENTITY?
CURRENT_ROUTE?
QUALIFIED_ROLES?
ROUTE_HEALTH?
TYPED_AUTH_STATE?
ACTIVE_EXECUTABLE_PROVENANCE?
MINIMAL_EXECUTION_IDENTITY_SMOKE?
FRESH_JOB_AUTHORITY_REQUIRED?
NEGATIVE_BOUNDARIES_PROVEN?
RESOURCE_TIMEOUT_PROVEN?
DURABLE_EXECUTION_BINDING_PROVEN?
TERMINAL_LIFECYCLE_RECEIPT_PROVEN?
SAME_ROLE_HANDOFF_OR_BLOCKED_SEMANTICS_PROVEN?
CURRENT_BLOCKERS?
```

A blocked Claude route may remain an explicit residual only if the accepted operating model still preserves the required C2Pro principal-review guarantees through a separately qualified compatible principal path. At this planning baseline, that compatible path is **not yet proven**, so material promotion remains blocked. That acceptance is a control decision, never inferred from technical capability alone.
