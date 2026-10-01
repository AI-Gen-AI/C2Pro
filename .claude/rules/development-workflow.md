# Development Workflow

> **Status:** ACTIVE adapter  
> **Canonical work contract:** assigned `.c2pro/work/<work_id>.yaml`  
> **Last reconciled:** 2026-10-01

This file explains the default development sequence. The work envelope, current architecture and executable repository policy are authoritative.

## 1. Validate authority and workspace

Before implementation:

- verify exact work ID/base SHA/branch/workspace;
- read applicable `.c2pro/control/` policy;
- confirm scope, out-of-scope, acceptance criteria and required tests;
- stop on authority/workspace mismatch.

Do not bootstrap from legacy backlog/blackboard files unless the work envelope explicitly requests reconciliation/history.

## 2. Research proportionally

Reuse and primary-source verification are encouraged when they materially reduce risk.

Use, as appropriate:

- repository/code search;
- current package/vendor documentation;
- package registries;
- existing project patterns/ADRs.

Do not perform broad external research when the repository already contains the required contract.

## 3. Plan at the right altitude

For material work, capture the implementation approach before coding.

Do **not** automatically create PRD/architecture/system-design/task-list Markdown files for every feature.

Use the durable document owner defined by `DOCUMENTATION_STRUCTURE.md`:

- ADR for a durable architecture decision;
- TDD revision for platform-wide design;
- spec for a durable interface/product contract;
- runbook for operations;
- work envelope/PR for bounded execution detail.

## 4. TDD / executable contract

Where the workstream requires TDD:

1. RED — prove the missing/incorrect behavior.
2. GREEN — minimum implementation satisfying the contract.
3. REFACTOR — improve structure with tests green.

For bug fixes, add regression coverage at the narrowest useful layer.

Coverage thresholds are owned by current executable CI/ratchets, not a hard-coded percentage in this file.

## 5. Review

Apply `.c2pro/control/review-policy.yaml`.

- address blocking findings;
- preserve reviewer independence;
- use challenger/orchestrator synthesis where the risk class requires it;
- do not convert advisory disagreement into silent approval.

## 6. CI and merge

Required checks are discovered from the live target-branch ruleset plus package-specific gates.

For `main`, do not hard-code a permanent list here.

Evaluate only the sealed current head/run attempt. Pending is not failure; stale green runs do not qualify a new head.

## 7. Completion

Return structured execution evidence.

Ordinary workers do not update:

- `C2PRO_MASTER_BACKLOG.md`;
- `backlogs/*.md`;
- `blackboard.json`.

The Planner/Master reconciles canonical `.c2pro` state after applicable review, CI and merge.

Product lifecycle promotion, when relevant, is a separate Product Control YAML-first/evidence-guarded operation.
