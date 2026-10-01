# Single-Writer Control Requirement

**Status:** Current  
**Severity:** Critical  
**Updated:** 2026-10-01

## Rule

Ordinary implementation, QA and review workers **MUST NOT** mutate:

- `C2PRO_MASTER_BACKLOG.md`;
- `backlogs/*.md`;
- `blackboard.json`.

They are legacy/cold references.

Canonical development control is written only by the Planner/Master Reconciler under `.c2pro/`.

## Worker bootstrap

Read only what is required:

1. `.c2pro/control/` routing/current state relevant to the task;
2. assigned `.c2pro/work/<work_id>.yaml`;
3. role-specific instructions;
4. relevant code/spec/ADRs.

## Worker return contract

Completion/new findings are transported through PR/standard output as:

```yaml
schema: c2pro-implementation-result-v1
work_id: C2PRO-DEV-XX
base_sha: <40-hex-base>
head_sha: <40-hex-head>
branch: <branch>
files_changed:
  - path/to/file
tests:
  - name: test_name
    status: PASS
ci_status: success
findings: []
residual_risks: []
recommendation: approve
pr_url: null
```

Do not commit a result file solely to transport this envelope.

## Canonical completion

Worker completion is provisional. It becomes canonical only after required review/CI, merge and Master/Planner reconciliation.

## Discovered work

Report newly discovered blockers/tasks in `findings` / `residual_risks`. The worker does not add them directly to legacy backlogs or canonical control state.
