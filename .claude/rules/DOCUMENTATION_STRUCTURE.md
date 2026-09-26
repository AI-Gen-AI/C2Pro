# Documentation Structure — Canonical Control Rules

> **Effective:** 2026-09-26  
> **Severity:** CRITICAL  
> **Purpose:** prevent documentation sprawl and split-brain programme/task state.

## 1. Current authorities

Current execution state is canonical only in:

- `.c2pro/control/current.yaml`
- `.c2pro/control/work-queue.yaml`
- authorized `.c2pro/work/<work_id>.yaml` envelopes

Product-programme lifecycle state is canonical only in:

- `validation/product/c2pro-master-product-control-v1.yaml`
- `docs/product/00-c2pro-master-product-control-v1.md` as its guarded human projection

## 2. Legacy surfaces are read-only

The following are historical / reconciliation inputs, not current write targets:

- `C2PRO_MASTER_BACKLOG.md`
- `backlogs/*.md`
- `blackboard.json`
- `blackboard/SESSION_*.md`

Ordinary workers MUST NOT mutate them. Historical documents may keep their original statements, but current guidance must clearly classify them as legacy/cold reference.

## 3. Do not create task-summary sprawl

Do **not** create standalone files merely to report that a task was planned, implemented, reviewed or completed, for example:

- `TASK-XXX_SUMMARY.md`
- `FEATURE_X_IMPLEMENTATION_PLAN.md`
- `*_COMPLETION_REPORT.md`

For current work:

1. scope and acceptance criteria belong in the authorized work envelope or approved product slice;
2. implementation/review evidence belongs in the PR and structured `c2pro-implementation-result-v1` output;
3. current execution state changes only through Master/Planner/Reconciler control-plane reconciliation after review/CI/merge;
4. product lifecycle changes only through the product-control YAML/Markdown pair with explicit evidence.

A durable architecture decision, runbook, policy, ADR, user-facing specification or reusable technical reference is **not** a task-summary file and may be created when its durable purpose is explicit.

## 4. Worker protocol

Workers:

- read the assigned `.c2pro/work/<work_id>.yaml`;
- read only the hot control context needed for that work;
- implement inside authorized scope;
- return structured evidence;
- do **not** self-promote completion into canonical control;
- do **not** write legacy backlog/blackboard state.

Planner/Master/Reconciler owns canonical planning/control mutations within its explicit authority.

## 5. Historical evidence

Do not rewrite historical reports so they appear current. When a historical file is operationally ambiguous, add a clear legacy/historical banner or pointer to current authority. Preserve original evidence and dates.

## 6. Anti-duplication rule

Before creating a new planning/status/control document, verify that the information does not already belong in:

- product-control YAML/MD;
- `.c2pro` control/work envelope;
- an existing ADR;
- an existing durable runbook/policy/specification.

If it belongs there, update the canonical owner instead of creating a parallel register.

## Related rules

- `.claude/rules/CRITICAL_BACKLOG_REQUIREMENT.md`
- `.claude/rules/agents.md`
- `.c2pro/control/legacy-compatibility.yaml`

No older instruction authorizes writing legacy control surfaces.
