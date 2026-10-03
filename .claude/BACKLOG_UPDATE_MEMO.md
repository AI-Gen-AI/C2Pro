# Development Control Memo — Single-Writer .c2pro Plane

**Status:** ACTIVE  
**Last reconciled:** 2026-10-01  
**Audience:** all C2Pro implementation, QA, review and orchestration workers

## Critical invariant

Ordinary workers MUST NOT mutate legacy control/status files:

- `C2PRO_MASTER_BACKLOG.md`
- `backlogs/*.md`
- `blackboard.json`

They are legacy/cold reconciliation sources only.

Canonical development-control write state is under `.c2pro/`, owned by the authorized Planner / Master reconciliation flow.

## Worker bootstrap

Default worker context is bounded:

1. assigned `.c2pro/work/<work_id>.yaml`;
2. applicable `.c2pro/control/` policy;
3. exact source/tests/spec/ADR context needed by the work.

Do not parse full legacy backlogs by default.

## Worker completion

Return structured evidence rather than editing task registers.

Example shape:

```yaml
schema: c2pro-implementation-result-v1
work_id: C2PRO-DEV-XX
base_sha: <40-hex-base>
head_sha: <40-hex-head>
branch: <branch>
files_changed:
  - path/to/file
tests:
  - name: <test-or-check>
    status: PASS
ci_status: success
findings: []
residual_risks: []
recommendation: approve
pr_url: null
```

The current machine schema/work envelope wins if it evolves beyond this example.

## Reconciliation

Completion is not canonical merely because a worker returns PASS.

Planner/Master reconciliation considers, as applicable:

- exact head/base;
- independent review required by risk class;
- required CI/current attempt;
- merge state;
- residual findings/risks;
- effective authority.

Only then is canonical development-control state updated.

## Product lifecycle is separate

Do not confuse development completion with Product Control promotion.

Product programme/lifecycle authority is:

`validation/product/c2pro-master-product-control-v1.yaml`

A merged implementation may still be undeployed or not production-qualified.

## Compatibility

`core/supervisor.py`, blackboard and backlog sync tooling may remain for genuine legacy compatibility.

Under `.c2pro/control/legacy-compatibility.yaml`, modern `C2PRO-*` work uses the new control plane and must not silently fall back to legacy writes.
