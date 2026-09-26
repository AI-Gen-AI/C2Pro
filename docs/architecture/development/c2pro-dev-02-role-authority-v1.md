# C2PRO-DEV-02 — Role Model & Authority Hierarchy v1

**Status:** IMPLEMENTED / PENDING CI + HUMAN MERGE  
**Date:** 2026-08-24  
**Repository:** `AI-Gen-AI/C2Pro`  
**Base:** `main@3fa846d60cecd14239ddb0a953be5e34bede463d`  
**Parent plan:** `docs/architecture/development/c2pro-vps-development-control-plan-v1.md`

## 1. Decision

C2Pro Development authority is role-first and vendor-neutral:

```text
ROLE != WORKER != HARNESS != PROVIDER ROUTE != MODEL != ENTITLEMENT
```

A WORK item is owned by its stable identity and assigned role. Worker selection is replaceable runtime state.

Claude Code and Codex are the only **PRINCIPAL** workers in the initial authority model. Gemini CLI, Antigravity and OpenCode are **SUBORDINATE** surfaces. This is an authority ceiling only: actual VPS route readiness is not implied and is qualified later.

## 2. Canonical roles

Six compact canonical profiles replace the execution semantics previously spread across `roles/`, `.github/agents`, Claude rules and supervisor configuration.

| Role | Authority class | Purpose |
|---|---|---|
| `orchestrator` | control | workflow, authority, routing, review, remediation, escalation |
| `implementation_lead` | implementation | implement a bounded WORK envelope in isolated development execution |
| `independent_reviewer` | verification | independently review diff/tests/evidence and gate principal promotion |
| `qa` | verification | focused behavioral/regression verification |
| `security` | verification | security, tenant isolation, secrets and AI attack-surface review |
| `specialist` | advisory | bounded specialist/challenger analysis or delegated contribution |

Canonical role profiles live under `.c2pro/roles/` and contain no worker, model, provider, route or entitlement ownership.

### 2.1 Orchestrator

The Orchestrator is a role, not Claude or Codex. It can:

- validate effective campaign/work authority;
- create/update a bounded WORK envelope;
- select/switch eligible workers;
- create compact handoffs;
- request tests, independent review and challenger review;
- synthesize findings;
- authorize in-scope remediation;
- open a PR;
- emit `PR_APPROVED` only when all required gates pass.

It cannot broaden scope, override forbidden paths, infer production/secrets authority, bypass CI/review or self-approve material work performed by the same worker.

### 2.2 Implementation Lead

The role may inspect/modify in-scope code, add in-scope tests, run checks, commit within the bounded development workspace, record evidence and remediate approved findings.

It may not mutate canonical checkout/main, silently broaden scope, weaken tests, infer production authority, expose secrets or self-approve material work.

### 2.3 Independent Reviewer

The reviewer operates from WORK + diff/commit range + tests + evidence, not from the implementer's narrative.

For material work the reviewer worker must differ from the implementation worker. While acting as the independent reviewer it must not modify the implementation under review.

### 2.4 QA and Security

Legacy domain knowledge is preserved, but legacy session/backlog mechanics are removed.

QA preserves focused regression, test and acceptance verification. Security preserves Zero Trust, tenant-isolation and vulnerability review. Neither role independently grants principal promotion authority.

### 2.5 Specialist

Specialists can analyze, challenge and later perform bounded implementation when separately qualified. A subordinate contribution cannot promote itself.

## 3. Worker authority classes

### PRINCIPAL

- `claude_code`
- `codex`

Both are eligible for:

- Orchestrator;
- Implementation Lead;
- Independent Reviewer;
- QA;
- Security;
- Specialist.

They are peers at the authority layer. Routing preference is not permanent task ownership.

### SUBORDINATE

- `gemini_cli`
- `antigravity`
- `opencode`

Initial ceilings:

- no Orchestrator role;
- no Independent Principal Reviewer role;
- no principal-gate authority;
- material contribution requires an eligible principal gate.

Antigravity remains an execution surface independent from Gemini CLI. OpenCode remains a harness identity, not a model identity.

## 4. Qualification is separate from authority

This DEV-02 policy does **not** claim that any CLI is already ready on the VPS.

```text
routing eligibility != route qualification != entitlement
```

Principal VPS readiness belongs to `C2PRO-DEV-03`. Subordinate readiness belongs to `C2PRO-DEV-10`.

## 5. No-self-approval

For material or higher-risk work:

```text
implementation_worker != independent_principal_review_worker
```

Examples:

```text
Claude implements -> Codex principal review
Codex implements  -> Claude principal review
```

Changing role labels while retaining the same worker does not create independence.

## 6. Handoff and quota exhaustion

The same WORK can change workers without becoming a new task.

Preserved fields:

- `work_id`;
- `role`;
- `base_sha`;
- `scope`;
- `out_of_scope`;
- `acceptance_criteria`.

Initial reciprocal principal fallback:

```text
Claude Code -> Codex
Codex       -> Claude Code
```

Triggers include token limit, quota exhaustion, provider/session failure and Orchestrator reassignment.

The replacement worker cannot broaden scope or reset baseline.

## 7. Risk and review classes

| Risk | Independent principal | Challenger | Orchestrator synthesis |
|---|---|---|---|
| trivial | optional | no | no |
| normal | required | no | no |
| material | required | optional | no |
| architecture | required | required | required |
| security | required | required | required |
| high_blast_radius | required | required | required |

A challenger does not replace principal review.

Open-ended model debate is disabled by default. One directed adjudication round is allowed for a material disagreement; unresolved disagreement escalates to the owner.

## 8. PR promotion boundary

`PR_APPROVED` requires the applicable gates, including:

- required CI green;
- required tests pass;
- zero blocking findings;
- no scope deviation;
- forbidden paths untouched;
- valid effective authority;
- independent principal review when required.

Initial merge mode remains **human merge**.

## 9. Context budget

DEV-01 froze the bootstrap ceiling at 16 KiB. DEV-02 now includes the actual active role/routing/review authority in the bootstrap:

| Hot artifact | Bytes |
|---|---:|
| `current.yaml` | 1,113 |
| `work-queue.yaml` | 759 |
| `routing.yaml` | 2,535 |
| `review-policy.yaml` | 1,471 |
| active `orchestrator.yaml` | 1,689 |
| `C2PRO-DEV-02.yaml` | 2,170 |
| **Total** | **9,737** |

Usage: **59.4% of 16,384 bytes**.

Other role profiles, schemas, legacy material and completed WORK are not bootstrap hot context.

## 10. Deterministic validation

The focused control validator now checks:

- all six role profiles exist and are model/worker/provider neutral;
- only Claude Code and Codex are principal-gate eligible;
- subordinate workers cannot satisfy principal promotion;
- OpenCode remains a harness identity;
- Antigravity remains independent from Gemini CLI;
- material self-review is forbidden;
- risk/review rules are deterministic;
- open-ended model debate remains disabled;
- principal fallback is reciprocal;
- selecting Claude vs Codex does not change stable WORK identity;
- completed history remains excluded from hot state;
- legacy controls remain non-canonical and undeleted pending reconciliation;
- bootstrap context stays <=16 KiB.

Negative regression tests deliberately mutate subordinate authority, debate policy and completed-state controls and require validation failure.

## 11. Legacy role transition

DEV-02 does not delete `roles/`, `.github/agents`, `.claude/rules` or other legacy instruction surfaces. Their useful domain invariants remain reference inputs during transition.

The new `.c2pro/roles/` profiles are canonical for the new Development Control model. Later reconciliation will convert vendor-specific files into thin adapters or cold compatibility material without losing product knowledge.

## 12. Exit gate

DEV-02 is ready for DONE when:

1. focused `C2Pro Development Control` CI is green;
2. standard repository gates are green as applicable;
3. no blocking review finding remains;
4. the owner merges the PR.

The defining technical proof is:

> the same WORK can move between Claude Code and Codex while its stable identity remains unchanged.

## 13. Next work

`C2PRO-DEV-03 — Claude and Codex principal worker readiness`.

DEV-03 moves from repository design to the VPS and will inventory, install/update only where required, bind identities, and qualify non-interactive/read/write/denial/resource behavior for both principal coding surfaces.
