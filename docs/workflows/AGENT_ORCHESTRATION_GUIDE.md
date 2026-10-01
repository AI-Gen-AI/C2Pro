# Agent Orchestration Guide

**Version:** 2.0  
**Updated:** 2026-10-01  
**Status:** Current control-plane guide

## 1. Two execution planes

C2Pro is in a **dual-read / single-write-new-control** transition.

### Current control plane — `.c2pro/`

For modern `C2PRO-*` work:

- `.c2pro/control/` owns canonical routing/planning state;
- each worker receives an explicit `.c2pro/work/<work_id>.yaml` envelope;
- workers are role-based and model-agnostic;
- workers return structured `c2pro-implementation-result-v1` evidence;
- the Planner/Master Reconciler is the only writer that promotes accepted evidence into canonical control state.

### Legacy compatibility plane

`core/supervisor.py`, `blackboard.json`, `C2PRO_MASTER_BACKLOG.md` and `backlogs/*.md` remain for genuine legacy compatibility/context.

Ordinary modern workers **must not write** those files.

If a modern C2PRO task is routed into the legacy supervisor, it must hand off/stop according to the repository's new-control boundary rather than mutating legacy state.

## 2. Worker lifecycle

```text
Master/Planner
   |
   | creates/reconciles .c2pro control + work envelope
   v
Worker (backend/frontend/AI/infra/QA/etc.)
   |
   | branch/worktree + implementation/tests
   v
Structured result in PR/output
   |
   v
Independent review + CI
   |
   v
Merge
   |
   v
Master Reconciler updates canonical control state
```

A worker never self-declares canonical completion.

## 3. Roles

Roles are functional boundaries, not fixed model identities. Typical roles include:

- Orchestrator / Planner;
- Backend;
- Frontend;
- AI;
- Infrastructure / DevOps;
- Test / QA;
- Security;
- Verification Auditor;
- Reconciler.

Material self-approval is forbidden where the task/review policy requires independence.

## 4. Evidence contract

Workers return a fenced YAML block using schema `c2pro-implementation-result-v1` with:

- work id;
- base/head SHA;
- branch;
- files changed;
- tests;
- CI state;
- findings;
- residual risks;
- recommendation;
- PR URL.

The PR/check evidence is transport. The Master/Planner reconciles it into canonical control state.

## 5. Guardrails

- verify workspace/branch before editing;
- stay within assigned file/scope envelope;
- do not mutate legacy control files;
- do not bypass CI/security/product-control gates;
- stop/fail closed on authority mismatch;
- report scope expansion as a finding rather than silently absorbing it;
- preserve exact evidence SHAs.

## 6. Architecture/documentation changes

Use `docs/DOCUMENTATION_GOVERNANCE.md`:
- Accepted decision → ADR;
- platform-wide composition → TDD;
- proposal → Proposed/In-flight spec/plan;
- history → archive/audit;
- active execution state → `.c2pro`.

## 7. Legacy references

Historical agent documentation may describe blackboard/backlog mutation. Those descriptions are not current authority. This guide plus `agents.md`, `CLAUDE.md` and `.claude/rules/` govern current workers.
